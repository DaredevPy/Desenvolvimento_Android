import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/core/outbox/operacao_pendente.dart';
import 'package:meu_app_coleta_pneus/core/outbox/outbox_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Missão 23 — Política de Erros HTTP do Outbox.
///
/// Classifica respostas HTTP em definitivas (403, 404, 409, 413, 422) e
/// transitórias (401, 429, 5xx, rede). Operações com falha definitiva são
/// marcadas FALHA_DEFINITIVA, mantidas na fila para ação manual e não são
/// reenviadas automaticamente.
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

  Future<OperacaoPendente> agendarColeta(OutboxService servico) {
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
        const {
          'marca': 'Marca X',
          'dimensao': '205/55R16',
          'quantidade_declarada': 4,
        },
      ],
    );
  }

  group('Outbox - política de erros HTTP (Missão 23)', () {
    test('403 → FALHA_DEFINITIVA', () async {
      final servico = servicoCom((caminho, cabecalhos, corpo) async => 403);

      await agendarColeta(servico);
      await servico.sincronizarPendentes();

      final fila = await servico.pendentes();
      expect(fila, hasLength(1));
      expect(fila.single.status, StatusOperacaoOutbox.falhaDefinitiva);
      expect(fila.single.ultimoErro, 'HTTP 403');
      expect(fila.single.tentativas, 1);
    });

    test('404 → FALHA_DEFINITIVA', () async {
      final servico = servicoCom((caminho, cabecalhos, corpo) async => 404);

      await agendarColeta(servico);
      await servico.sincronizarPendentes();

      final fila = await servico.pendentes();
      expect(fila.single.status, StatusOperacaoOutbox.falhaDefinitiva);
      expect(fila.single.ultimoErro, 'HTTP 404');
    });

    test('409 → FALHA_DEFINITIVA', () async {
      final servico = servicoCom((caminho, cabecalhos, corpo) async => 409);

      await agendarColeta(servico);
      await servico.sincronizarPendentes();

      final fila = await servico.pendentes();
      expect(fila.single.status, StatusOperacaoOutbox.falhaDefinitiva);
      expect(fila.single.ultimoErro, 'HTTP 409');
    });

    test('413 → FALHA_DEFINITIVA', () async {
      final servico = servicoCom((caminho, cabecalhos, corpo) async => 413);

      await agendarColeta(servico);
      await servico.sincronizarPendentes();

      final fila = await servico.pendentes();
      expect(fila.single.status, StatusOperacaoOutbox.falhaDefinitiva);
      expect(fila.single.ultimoErro, 'HTTP 413');
    });

    test('422 → FALHA_DEFINITIVA', () async {
      final servico = servicoCom((caminho, cabecalhos, corpo) async => 422);

      await agendarColeta(servico);
      await servico.sincronizarPendentes();

      final fila = await servico.pendentes();
      expect(fila.single.status, StatusOperacaoOutbox.falhaDefinitiva);
      expect(fila.single.ultimoErro, 'HTTP 422');
    });

    test('401 → PENDENTE (transitório)', () async {
      final servico = servicoCom((caminho, cabecalhos, corpo) async => 401);

      await agendarColeta(servico);
      await servico.sincronizarPendentes();

      final fila = await servico.pendentes();
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
      expect(fila.single.ultimoErro, 'HTTP 401');
      expect(fila.single.tentativas, 1);
    });

    test('429 → PENDENTE (transitório)', () async {
      final servico = servicoCom((caminho, cabecalhos, corpo) async => 429);

      await agendarColeta(servico);
      await servico.sincronizarPendentes();

      final fila = await servico.pendentes();
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
      expect(fila.single.ultimoErro, 'HTTP 429');
    });

    test('500 → PENDENTE (transitório)', () async {
      final servico = servicoCom((caminho, cabecalhos, corpo) async => 500);

      await agendarColeta(servico);
      await servico.sincronizarPendentes();

      final fila = await servico.pendentes();
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
      expect(fila.single.ultimoErro, 'HTTP 500');
    });

    test('503 → PENDENTE (transitório)', () async {
      final servico = servicoCom((caminho, cabecalhos, corpo) async => 503);

      await agendarColeta(servico);
      await servico.sincronizarPendentes();

      final fila = await servico.pendentes();
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
      expect(fila.single.ultimoErro, 'HTTP 503');
    });

    test('falha de rede → PENDENTE (transitório)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos, corpo) async =>
            throw Exception('sem conexao com o backend'),
      );

      await agendarColeta(servico);
      await servico.sincronizarPendentes();

      final fila = await servico.pendentes();
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
      expect(fila.single.tentativas, 1);
    });

    test('código HTTP desconhecido (ex: 418) → PENDENTE (defensivo)', () async {
      final servico = servicoCom((caminho, cabecalhos, corpo) async => 418);

      await agendarColeta(servico);
      await servico.sincronizarPendentes();

      final fila = await servico.pendentes();
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
      expect(fila.single.ultimoErro, 'HTTP 418');
    });

    test('operação FALHA_DEFINITIVA não é reenviada automaticamente', () async {
      var envios = 0;
      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        envios += 1;
        return 422;
      });

      await agendarColeta(servico);

      await servico.sincronizarPendentes(); // marca definitiva
      await servico.sincronizarPendentes(); // não deve reenviar
      await servico.sincronizarPendentes(); // não deve reenviar

      expect(envios, 1);
      final fila = await servico.pendentes();
      expect(fila, hasLength(1));
      expect(fila.single.status, StatusOperacaoOutbox.falhaDefinitiva);
      expect(fila.single.tentativas, 1);
    });

    test('FALHA_DEFINITIVA não bloqueia operações posteriores', () async {
      final respostas = [403, 201];
      var indice = 0;

      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        return respostas[indice++];
      });

      await agendarColeta(servico); // operação A (vai falhar 403)
      await agendarColeta(servico); // operação B (vai funcionar)

      final concluidas = await servico.sincronizarPendentes();

      // A falha definitivamente e interrompe lote; B não é processada nesta
      // passagem mas NÃO está bloqueada — será processada na próxima.
      expect(concluidas, 0);
      var fila = await servico.pendentes();
      expect(fila, hasLength(2));
      expect(fila[0].status, StatusOperacaoOutbox.falhaDefinitiva);
      expect(fila[1].status, StatusOperacaoOutbox.pendente);

      // Segunda passagem: A é pulada, B é processada com sucesso.
      final concluidas2 = await servico.sincronizarPendentes();
      expect(concluidas2, 1);
      fila = await servico.pendentes();
      expect(fila, hasLength(1));
      expect(fila.single.status, StatusOperacaoOutbox.falhaDefinitiva);
    });

    test('status FALHA_DEFINITIVA sobrevive à persistência/reabertura', () async {
      final servico = servicoCom((caminho, cabecalhos, corpo) async => 422);

      await agendarColeta(servico);
      await servico.sincronizarPendentes();

      // Simula reabertura do app: nova instância, mesmo armazenamento.
      final servicoReaberto = servicoCom(null);
      final fila = await servicoReaberto.pendentes();

      expect(fila, hasLength(1));
      expect(fila.single.status, StatusOperacaoOutbox.falhaDefinitiva);
      expect(fila.single.ultimoErro, 'HTTP 422');
      expect(fila.single.tentativas, 1);
    });

    test('operações existentes continuam funcionando (regressão)', () async {
      final caminhosEnviados = <String>[];
      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        caminhosEnviados.add(caminho);
        return 201;
      });

      await servico.agendarCriacaoDeColeta(
        enderecoOrigemJson: const {'logradouro': 'Rua A'},
        dataAgendada: DateTime.utc(2026, 9, 1),
        itens: const [
          {'marca': 'M', 'dimensao': '205/55R16', 'quantidade_declarada': 2},
        ],
      );
      await servico.agendarCriacaoDeColeta(
        enderecoOrigemJson: const {'logradouro': 'Rua B'},
        dataAgendada: DateTime.utc(2026, 9, 2),
        itens: const [
          {'marca': 'N', 'dimensao': '195/65R15', 'quantidade_declarada': 3},
        ],
      );

      final concluidas = await servico.sincronizarPendentes();

      expect(concluidas, 2);
      expect(caminhosEnviados, hasLength(2));
      expect(await servico.pendentes(), isEmpty);
    });

    test('ID e payload preservados após FALHA_DEFINITIVA', () async {
      final servico = servicoCom((caminho, cabecalhos, corpo) async => 409);

      final operacao = await agendarColeta(servico);
      final idOriginal = operacao.id;
      final caminhoOriginal = operacao.caminho;
      final corpoOriginal = Map<String, dynamic>.from(operacao.corpo);

      await servico.sincronizarPendentes();

      final fila = await servico.pendentes();
      expect(fila.single.id, idOriginal);
      expect(fila.single.caminho, caminhoOriginal);
      expect(fila.single.corpo, corpoOriginal);
    });

    test('sucesso (200/201) continua removendo operação normalmente', () async {
      final servico = servicoCom((caminho, cabecalhos, corpo) async => 201);

      await agendarColeta(servico);

      final concluidas = await servico.sincronizarPendentes();

      expect(concluidas, 1);
      expect(await servico.pendentes(), isEmpty);
    });
  });
}
