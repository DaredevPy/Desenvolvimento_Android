import 'dart:async';
import 'dart:convert';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/core/outbox/operacao_pendente.dart';
import 'package:meu_app_coleta_pneus/core/outbox/outbox_service.dart';
import 'package:meu_app_coleta_pneus/core/outbox/sincronizacao_automatica_outbox.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Disparo automático da sincronização do Outbox (Missão 18 / doc 09 §3).
///
/// Os dois gatilhos são injetados: a stream de conectividade vem de um
/// StreamController (simula queda/reconexão) e o ciclo de vida é simulado
/// pelo próprio binding (`handleAppLifecycleStateChanged`). O transporte
/// HTTP é o mesmo espião dos testes das Missões 16/17.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late StreamController<List<ConnectivityResult>> conectividade;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    conectividade = StreamController<List<ConnectivityResult>>();
  });

  tearDown(() async {
    await conectividade.close();
  });

  SincronizacaoAutomaticaOutbox disparoCom(
    OutboxService servico,
  ) {
    final disparo = SincronizacaoAutomaticaOutbox(
      outbox: servico,
      conectividade: conectividade.stream,
    );
    disparo.iniciar();
    addTearDown(disparo.descartar);
    return disparo;
  }

  OutboxService servicoCom(
    Future<int> Function(
      String caminho,
      Map<String, String> cabecalhos,
      String corpo,
    )
        enviar,
  ) {
    return OutboxService(enviar: enviar);
  }

  Future<OperacaoPendente> agendarColeta(
    OutboxService servico, {
    int quantidadeDeclarada = 1,
  }) {
    return servico.agendarCriacaoDeColeta(
      enderecoOrigemJson: const {'cidade': 'São Paulo', 'uf': 'SP'},
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

  Future<void> flushMicrotasks() async {
    for (var i = 0; i < 8; i++) {
      await Future<void>.delayed(Duration.zero);
    }
  }

  void voltarAoAplicativo() {
    // Passa por paused para garantir transição real mesmo que o binding
    // já esteja resumed (estado repetido não notifica observadores).
    WidgetsBinding.instance.handleAppLifecycleStateChanged(
      AppLifecycleState.paused,
    );
    WidgetsBinding.instance.handleAppLifecycleStateChanged(
      AppLifecycleState.resumed,
    );
  }

  group('Sincronização automática do Outbox (Missão 18)', () {
    test('app inicia com fila pendente: sincroniza sozinho e remove '
        'após confirmação', () async {
      var envios = 0;
      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        envios += 1;
        return 201;
      });
      await agendarColeta(servico);

      disparoCom(servico);
      await flushMicrotasks();

      expect(envios, 1, reason: 'disparo inicial deve enviar sem esperar UI');
      expect(await servico.pendentes(), isEmpty);
    });

    test('reconexão dispara envio; evento de queda ([none]) não dispara; '
        'retry automático usa a MESMA chave', () async {
      var redeDisponivel = false;
      final chaves = <String>[];
      var envios = 0;
      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        chaves.add(cabecalhos['X-Idempotency-Key']!);
        envios += 1;
        if (!redeDisponivel) {
          throw Exception('offline');
        }
        return 201;
      });
      final operacao = await agendarColeta(servico);

      disparoCom(servico);
      await flushMicrotasks();
      expect(envios, 1, reason: 'primeira tentativa falha offline');
      expect(await servico.pendentes(), hasLength(1));

      // Rede cai formalmente: nenhum envio deve ocorrer.
      redeDisponivel = true;
      conectividade.add([ConnectivityResult.none]);
      await flushMicrotasks();
      expect(envios, 1);

      // Conexão restabelecida: retry automático.
      conectividade.add([ConnectivityResult.wifi]);
      await flushMicrotasks();

      expect(envios, 2);
      expect(chaves, [operacao.id, operacao.id],
          reason: 'retry automático reutiliza a chave de idempotência');
      expect(await servico.pendentes(), isEmpty);
    });

    test('retorno ao aplicativo dispara sincronização; estados em segundo '
        'plano não disparam', () async {
      var envios = 0;
      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        envios += 1;
        return 201;
      });

      // Operação já pendente quando o aplicativo inicia.
      await agendarColeta(servico);
      disparoCom(servico);
      await flushMicrotasks();
      expect(envios, 1);

      // Segunda operação criada com o app vivo; app vai para segundo plano.
      await agendarColeta(servico, quantidadeDeclarada: 2);
      void irParaSegundoPlano() {
        WidgetsBinding.instance.handleAppLifecycleStateChanged(
          AppLifecycleState.inactive,
        );
        WidgetsBinding.instance.handleAppLifecycleStateChanged(
          AppLifecycleState.hidden,
        );
        WidgetsBinding.instance.handleAppLifecycleStateChanged(
          AppLifecycleState.paused,
        );
      }

      irParaSegundoPlano();
      await flushMicrotasks();
      expect(envios, 1, reason: 'pausa/segundo plano NÃO deve disparar');
      expect(await servico.pendentes(), hasLength(1));

      // Retorno ao primeiro plano: dispara.
      WidgetsBinding.instance.handleAppLifecycleStateChanged(
        AppLifecycleState.hidden,
      );
      WidgetsBinding.instance.handleAppLifecycleStateChanged(
        AppLifecycleState.inactive,
      );
      voltarAoAplicativo();
      await flushMicrotasks();

      expect(envios, 2);
      expect(await servico.pendentes(), isEmpty);
    });

    test('fila vazia ou já concluída: nenhum gatilho gera requisição',
        () async {
      var envios = 0;
      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        envios += 1;
        return 201;
      });

      // Fila vazia desde o início: todos os gatilhos, zero requisições.
      disparoCom(servico);
      await flushMicrotasks();
      conectividade.add([ConnectivityResult.wifi]);
      voltarAoAplicativo();
      await flushMicrotasks();
      expect(envios, 0);

      // Operação pendente: o PRÓXIMO evento dispara o envio (única vez).
      await agendarColeta(servico);
      conectividade.add([ConnectivityResult.wifi]);
      await flushMicrotasks();
      expect(envios, 1);
      expect(await servico.pendentes(), isEmpty);

      voltarAoAplicativo();
      await flushMicrotasks();
      conectividade.add([ConnectivityResult.mobile]);
      await flushMicrotasks();
      expect(envios, 1, reason: 'operação concluída nunca é reenviada');
    });

    test('gatilhos simultâneos produzem UMA única passagem; guarda é '
        'liberada para eventos posteriores', () async {
      final bloqueio = Completer<int>();
      final chaves = <String>[];
      var envios = 0;
      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        chaves.add(cabecalhos['X-Idempotency-Key']!);
        envios += 1;
        return bloqueio.future;
      });

      final primeira = await agendarColeta(servico, quantidadeDeclarada: 1);
      final segunda = await agendarColeta(servico, quantidadeDeclarada: 2);

      disparoCom(servico);
      await flushMicrotasks();
      expect(envios, 1, reason: 'passagem em curso bloqueada no transporte');

      // Dois gatilhos DURANTE a passagem bloqueada: devem ser ignorados.
      conectividade.add([ConnectivityResult.wifi]);
      voltarAoAplicativo();
      await flushMicrotasks();
      expect(envios, 1, reason: 'não pode haver segunda passagem simultânea');

      bloqueio.complete(201);
      await flushMicrotasks();

      expect(chaves, [primeira.id, segunda.id],
          reason: 'a MESMA passagem consumiu as duas, em ordem');
      expect(await servico.pendentes(), isEmpty);

      // Guarda liberada: novo evento volta a sincronizar normalmente.
      await agendarColeta(servico, quantidadeDeclarada: 3);
      conectividade.add([ConnectivityResult.ethernet]);
      await flushMicrotasks();
      expect(envios, 3, reason: 'A e B na 1ª passagem, C na passagem nova');
      expect(await servico.pendentes(), isEmpty);
    });

    test('falha preserva a fila e NÃO existe retry espontâneo (sem loop)',
        () async {
      var envios = 0;
      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        envios += 1;
        throw Exception('backend inacessivel');
      });
      await agendarColeta(servico);

      disparoCom(servico);
      await flushMicrotasks();
      var fila = await servico.pendentes();
      expect(envios, 1);
      expect(fila, hasLength(1));
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
      expect(fila.single.tentativas, 1);

      // Tempo passa SEM novos eventos: nada deve ser enviado por conta própria.
      await Future<void>.delayed(const Duration(milliseconds: 150));
      expect(envios, 1, reason: 'sem timer interno: nenhum retry automático');

      // Somente um novo evento externo tenta novamente — e a fila permanece.
      conectividade.add([ConnectivityResult.wifi]);
      await flushMicrotasks();
      fila = await servico.pendentes();
      expect(envios, 2);
      expect(fila.single.tentativas, 2);
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
    });

    test('retomada após falha mantém ORDEM, MESMA chave e MESMO payload '
        '(ciclo completo da conferência)', () async {
      const coletaId = '22222222-2222-4222-8222-222222222222';
      var redeDisponivel = false;
      final chavesPorChamada = <String>[];
      final corposPorChamada = <String>[];
      final servico = servicoCom((caminho, cabecalhos, corpo) async {
        chavesPorChamada.add(cabecalhos['X-Idempotency-Key']!);
        corposPorChamada.add(corpo);
        if (!redeDisponivel) {
          throw Exception('offline');
        }
        return 201;
      });

      final pneus = await servico.agendarRegistroPneus(
        coletaId: coletaId,
        pneus: [
          const {
            'marca': 'Marca X',
            'medida': '205/55R16',
            'dot': '1224',
            'numero_fogo': 'NF123',
          },
        ],
      );
      final conclusao = await servico.agendarConclusaoConferencia(
        coletaId: coletaId,
        quantidadeConferida: 3,
        quantidadeColetada: 2,
      );
      final finalizacao =
          await servico.agendarFinalizacaoColeta(coletaId: coletaId);

      // App inicia offline: só a primeira operação tenta (e falha).
      disparoCom(servico);
      await flushMicrotasks();
      expect(chavesPorChamada, [pneus.id]);

      // Retorno ao app já com rede: lote inteiro na ordem original.
      redeDisponivel = true;
      voltarAoAplicativo();
      await flushMicrotasks();

      expect(chavesPorChamada, [
        pneus.id, // primeira tentativa (falha)
        pneus.id, // retomada: MESMA chave
        conclusao.id,
        finalizacao.id,
      ]);
      expect(corposPorChamada[0], corposPorChamada[1],
          reason: 'payload idêntico entre tentativa falha e retomada');
      expect(
        corposPorChamada[2],
        jsonEncode({'quantidade_conferida': 3, 'quantidade_coletada': 2}),
      );
      expect(corposPorChamada[3], '{}');
      expect(await servico.pendentes(), isEmpty);
    });
  });
}
