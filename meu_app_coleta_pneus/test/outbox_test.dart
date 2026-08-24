import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/core/outbox/operacao_pendente.dart';
import 'package:meu_app_coleta_pneus/core/outbox/outbox_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Fundação do fluxo Outbox Offline (Missão 16 / docs 09 §§2-4).
///
/// O transporte HTTP é injetado (`enviar`) para exercitar falhas de rede,
/// replays do backend e a integridade da fila sem servidor real.
void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
  });

  OutboxService servicoCom(
    Future<int> Function(
      String caminho,
      Map<String, String> cabecalhos,
      String corpo,
    )?
    enviar,
  ) {
    return OutboxService(enviar: enviar);
  }

  Future<OperacaoPendente> agendarColeta(
    OutboxService servico, {
    int quantidadeDeclarada = 4,
  }) {
    return servico.agendarCriacaoDeColeta(
      enderecoOrigemJson: const {
        'logradouro': 'Rua Teste',
        'numero': '123',
        'bairro': 'Centro',
        'cidade': 'São Paulo',
        'uf': 'SP',
        'cep': '01001-000',
      },
      dataAgendada: DateTime.utc(2026, 9, 1, 12),
      itens: [
        {
          'marca': 'Marca X',
          'dimensao': '205/55R16',
          'quantidade_declarada': quantidadeDeclarada,
        },
      ],
    );
  }

  group('Outbox - fundação offline', () {
    test('operação criada offline fica PENDENTE na fila local', () async {
      final servico = servicoCom(null);

      final operacao = await agendarColeta(servico);

      final fila = await servico.pendentes();
      expect(fila, hasLength(1));
      expect(fila.single.id, operacao.id);
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
      expect(fila.single.caminho, '/api/v1/collections');
      expect(fila.single.tentativas, 0);
    });

    test('operação pendente sobrevive à recriação do serviço (fechou/abriu app)',
        () async {
      final operacao = await agendarColeta(servicoCom(null));

      final servicoReaberto =
          servicoCom(null); // nova instância, mesmo armazenamento
      final fila = await servicoReaberto.pendentes();

      expect(fila.single.id, operacao.id);
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
    });

    test('chave de idempotência gerada é UUIDv4', () async {
      final padraoUuidV4 = RegExp(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        caseSensitive: false,
      );

      final operacao = await agendarColeta(servicoCom(null));

      expect(padraoUuidV4.hasMatch(operacao.id), isTrue,
          reason: 'id deveria ser UUIDv4: ${operacao.id}');
    });

    test('retry reutiliza exatamente a MESMA chave e corpo', () async {
      final chaves = <String>[];
      final corpos = <String>[];
      var chamadas = 0;

      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        chamadas += 1;
        chaves.add(cabecalhos['X-Idempotency-Key']!);
        corpos.add(corpo);
        if (chamadas == 1) {
          throw Exception('sem conexao com o backend');
        }
        return 201;
      });

      await agendarColeta(servico);

      await servico.sincronizarPendentes(); // falha de rede
      await servico.sincronizarPendentes(); // retry

      expect(chamadas, 2);
      expect(chaves, hasLength(2));
      expect(chaves.first, chaves.last,
          reason: 'retry deve reusar a mesma chave do agendamento original');
      expect(corpos.first, corpos.last,
          reason: 'corpo deve ser reenviado idêntico (hash validado no backend)');
    });

    test('falha de rede mantém a operação PENDENTE na fila', () async {
      final servico = servicoCom(
        (caminho, cabecalhos, corpo) async =>
            throw Exception('sem conexao com o backend'),
      );

      await agendarColeta(servico);

      await servico.sincronizarPendentes();

      final fila = await servico.pendentes();
      expect(fila, hasLength(1));
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
      expect(fila.single.tentativas, 1);
      expect(fila.single.ultimoErro, isNotNull);
    });

    test('sucesso confirmado pelo backend conclui e remove a operação',
        () async {
      final servico = servicoCom(
        (caminho, cabecalhos, corpo) async => 201,
      );

      await agendarColeta(servico);

      final concluidas = await servico.sincronizarPendentes();

      expect(concluidas, 1);
      expect(await servico.pendentes(), isEmpty);
    });

    test('duas operações agendadas possuem chaves distintas', () async {
      final servico = servicoCom(null);

      final primeira = await agendarColeta(servico, quantidadeDeclarada: 2);
      final segunda = await agendarColeta(servico, quantidadeDeclarada: 3);

      expect(primeira.id, isNot(segunda.id));
    });

    test('replay do backend não duplica o efeito da operação', () async {
      // Cenário: o backend PROCESSOU e criou a coleta, mas a resposta se
      // perdeu; no retry a chave repetida devolve a resposta armazenada
      // (200) sem criar nada novamente.
      var criacoesNoBackend = 0;
      var chamadas = 0;
      final chavesVistas = <String>{};

      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        chamadas += 1;
        final chave = cabecalhos['X-Idempotency-Key']!;
        if (chavesVistas.add(chave)) {
          criacoesNoBackend += 1;
        }
        if (chamadas == 1) {
          throw Exception('resposta perdida no caminho de volta');
        }
        return 200; // replay da resposta armazenada
      });

      await agendarColeta(servico);

      await servico.sincronizarPendentes(); // rede falhou após criação
      await servico.sincronizarPendentes(); // retry -> replay seguro

      expect(chamadas, 2);
      expect(criacoesNoBackend, 1, reason: 'efeito único no backend');
      expect(await servico.pendentes(), isEmpty);
    });

    test('sincronização executada novamente não reenvia operação concluída',
        () async {
      var envios = 0;
      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        envios += 1;
        return 201;
      });

      await agendarColeta(servico);

      await servico.sincronizarPendentes();
      await servico.sincronizarPendentes();
      final concluidasNaTerceiraPassagem =
          await servico.sincronizarPendentes();

      expect(envios, 1, reason: 'não deve haver reenvio nem duplicação');
      expect(concluidasNaTerceiraPassagem, 0);
      expect(await servico.pendentes(), isEmpty);
    });

    test('fila permanece íntegra quando uma operação falha', () async {
      final caminhosEnviados = <String>[];
      final chavesEnviadas = <String>[];
      var redeDisponivel = false;

      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        if (!redeDisponivel) {
          throw Exception('offline');
        }
        caminhosEnviados.add(caminho);
        chavesEnviadas.add(cabecalhos['X-Idempotency-Key']!);
        return 201;
      });

      final primeira = await agendarColeta(servico, quantidadeDeclarada: 1);
      final segunda = await agendarColeta(servico, quantidadeDeclarada: 2);
      final terceira = await agendarColeta(servico, quantidadeDeclarada: 3);

      // Sem rede: apenas a primeira falha; as demais NÃO são enviadas fora
      // de ordem e continuam intactas.
      await servico.sincronizarPendentes();

      var fila = await servico.pendentes();
      expect(fila.map((op) => op.id).toList(),
          [primeira.id, segunda.id, terceira.id],
          reason: 'ordem cronológica preservada');
      expect(caminhosEnviados, isEmpty);
      expect(fila.first.tentativas, 1);

      // Rede volta: todas seguem em ordem, cada uma com sua própria chave.
      redeDisponivel = true;
      await servico.sincronizarPendentes();

      expect(caminhosEnviados.length, 3);
      expect(chavesEnviadas, [primeira.id, segunda.id, terceira.id]);
      fila = await servico.pendentes();
      expect(fila, isEmpty);
    });
  });

  group('Outbox - integração com a conferência (Missão 17)', () {
    const coletaId = '22222222-2222-4222-8222-222222222222';

    Map<String, dynamic> pneuValido() => const {
          'marca': 'Marca X',
          'medida': '205/55R16',
          'dot': '1224',
          'numero_fogo': 'NF123',
        };

    test('registro de pneus offline fica pendente com contrato correto',
        () async {
      final servico = servicoCom(null);

      await servico.agendarRegistroPneus(
        coletaId: coletaId,
        pneus: [pneuValido()],
      );

      final fila = await servico.pendentes();
      expect(fila, hasLength(1));
      expect(
        fila.single.caminho,
        '/api/v1/collections/$coletaId/conferencia/pneus',
      );
      expect(fila.single.corpo, {
        'pneus': [pneuValido()],
      });
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
    });

    test('conclusão offline fica pendente com as quantidades independentes',
        () async {
      final servico = servicoCom(null);

      await servico.agendarConclusaoConferencia(
        coletaId: coletaId,
        quantidadeConferida: 3,
        quantidadeColetada: 2,
      );

      final fila = await servico.pendentes();
      expect(fila.single.caminho,
          '/api/v1/collections/$coletaId/conferencia/concluir');
      expect(fila.single.corpo, {
        'quantidade_conferida': 3,
        'quantidade_coletada': 2,
      });
    });

    test('finalização offline fica pendente com corpo vazio estrito', () async {
      final servico = servicoCom(null);

      await servico.agendarFinalizacaoColeta(coletaId: coletaId);

      final fila = await servico.pendentes();
      expect(fila.single.caminho, '/api/v1/collections/$coletaId/finalizar');
      expect(fila.single.corpo, isEmpty);
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
    });

    test('operações da conferência possuem chaves UUIDv4 distintas', () async {
      final padraoUuidV4 = RegExp(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        caseSensitive: false,
      );
      final servico = servicoCom(null);

      final pneus = await servico.agendarRegistroPneus(
        coletaId: coletaId,
        pneus: [pneuValido()],
      );
      final conclusao = await servico.agendarConclusaoConferencia(
        coletaId: coletaId,
        quantidadeConferida: 1,
        quantidadeColetada: 1,
      );
      final finalizacao =
          await servico.agendarFinalizacaoColeta(coletaId: coletaId);

      expect(pneus.id, isNot(conclusao.id));
      expect(conclusao.id, isNot(finalizacao.id));
      expect(pneus.id, isNot(finalizacao.id));
      for (final op in [pneus, conclusao, finalizacao]) {
        expect(padraoUuidV4.hasMatch(op.id), isTrue);
      }
    });

    test('ciclo completo sincroniza em ordem e remove cada operação',
        () async {
      final caminhosEnviados = <String>[];
      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        caminhosEnviados.add(caminho);
        return 201;
      });

      await servico.agendarRegistroPneus(
        coletaId: coletaId,
        pneus: [pneuValido()],
      );
      await servico.agendarConclusaoConferencia(
        coletaId: coletaId,
        quantidadeConferida: 3,
        quantidadeColetada: 2,
      );
      await servico.agendarFinalizacaoColeta(coletaId: coletaId);

      final concluidas = await servico.sincronizarPendentes();

      expect(concluidas, 3);
      expect(caminhosEnviados, [
        '/api/v1/collections/$coletaId/conferencia/pneus',
        '/api/v1/collections/$coletaId/conferencia/concluir',
        '/api/v1/collections/$coletaId/finalizar',
      ]);
      expect(await servico.pendentes(), isEmpty);
    });

    test('falha no meio do lote preserva a fila; retomada reusa chave/payload '
        'e o backend não duplica', () async {
      final chavesPorOp = <String, List<String>>{};
      final corposPorOp = <String, List<String>>{};
      final criacoesPorChave = <String>{};
      var redeDisponivel = false;

      OperacaoPendente? pneus;
      OperacaoPendente? conclusao;
      OperacaoPendente? finalizacao;

      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        if (!redeDisponivel) {
          throw Exception('offline');
        }
        final chave = cabecalhos['X-Idempotency-Key']!;
        chavesPorOp.putIfAbsent(chave, () => []).add(chave);
        corposPorOp.putIfAbsent(chave, () => []).add(corpo);
        if (criacoesPorChave.add(chave)) {
          return 201; // primeira vez que o backend vê a chave: cria
        }
        return 200; // replay da resposta armazenada
      });

      pneus = await servico.agendarRegistroPneus(
        coletaId: coletaId,
        pneus: [pneuValido()],
      );
      conclusao = await servico.agendarConclusaoConferencia(
        coletaId: coletaId,
        quantidadeConferida: 3,
        quantidadeColetada: 2,
      );
      finalizacao = await servico.agendarFinalizacaoColeta(coletaId: coletaId);

      // Sem rede: apenas a primeira falha; lote interrompido, fila intacta.
      await servico.sincronizarPendentes();

      var fila = await servico.pendentes();
      expect(fila.map((op) => op.id).toList(),
          [pneus.id, conclusao.id, finalizacao.id]);
      expect(fila.first.tentativas, 1);
      expect(fila.skip(1).every((op) => op.tentativas == 0), isTrue);

      // Retomada posterior: mesmas chaves, mesmos payloads, ordem preservada.
      redeDisponivel = true;
      await servico.sincronizarPendentes();

      expect(chavesPorOp.keys.toList(), [pneus.id, conclusao.id, finalizacao.id]);
      expect(chavesPorOp[pneus.id], hasLength(1));
      expect(corposPorOp[pneus.id]!.single,
          jsonEncode({'pneus': [pneuValido()]}));
      expect(corposPorOp[finalizacao.id]!.single, '{}');

      // Replay seguro: cada chave gerou efeito único no backend.
      fila = await servico.pendentes();
      expect(fila, isEmpty);
      expect(criacoesPorChave.length, 3);

      // Nova passagem não reenvia nada.
      final concluidasNaRetomadaExtra = await servico.sincronizarPendentes();
      expect(concluidasNaRetomadaExtra, 0);
    });
  });
}
