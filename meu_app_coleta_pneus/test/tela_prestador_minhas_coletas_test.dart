import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/core/api/api_service.dart';
import 'package:meu_app_coleta_pneus/core/outbox/operacao_pendente.dart';
import 'package:meu_app_coleta_pneus/core/outbox/outbox_service.dart';
import 'package:meu_app_coleta_pneus/core/sessao/servico_sessao.dart';
import 'package:meu_app_coleta_pneus/prestador/tela_prestador_minhas_coletas.dart';
import 'package:meu_app_coleta_pneus/prestador/tela_prestador_detalhe_coleta.dart';
import 'package:shared_preferences/shared_preferences.dart';

Map<String, dynamic> _coletaJson({
  String id = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
  String codigo = 'COL-TEST123',
  String status = 'ACEITA',
}) {
  return {
    'id': id,
    'codigo_identificador': codigo,
    'status': status,
    'endereco_origem_json': {'rua': 'Rua Teste', 'numero': '123', 'bairro': 'Centro'},
    'data_agendada': '2026-09-01T12:00:00+00:00',
    'provider_id': 'pppppppp-pppp-4ppp-8ppp-pppppppppppp',
    'criado_em': '2026-08-20T10:00:00+00:00',
    'itens': [
      {'marca': 'Michelin', 'dimensao': '275/80R22.5', 'quantidade_declarada': 10, 'observacao': null},
    ],
  };
}

ApiService _apiCom({
  Future<RespostaHttp> Function(String, Map<String, String>)? listar,
  Future<RespostaHttp> Function(String, Map<String, String>, String)? escrita,
}) {
  return ApiService(
    enviar: listar,
    enviarEscrita: escrita,
    obterToken: () => 'jwt.teste',
  );
}

OutboxService _outboxDummy({
  Future<int> Function(String, Map<String, String>, String)? enviar,
}) =>
    OutboxService(enviar: enviar);

Widget _envolver(Widget child) {
  return MaterialApp(home: child);
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });
  group('TelaPrestadorMinhasColetas', () {
    testWidgets('exibe carregando e depois lista de coletas', (tester) async {
      final api = _apiCom(
        listar: (_, __) async =>
            RespostaHttp(200, jsonEncode([_coletaJson(), _coletaJson(id: 'bbbbbbbb-cccc-4ddd-8eee-ffffffffffff', codigo: 'COL-456')])),
      );
      await tester.pumpWidget(_envolver(TelaPrestadorMinhasColetas(api: api, outbox: _outboxDummy())));

      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      await tester.pumpAndSettle();

      expect(find.text('COL-TEST123'), findsOneWidget);
      expect(find.text('COL-456'), findsOneWidget);
    });

    testWidgets('lista vazia mostra mensagem', (tester) async {
      final api = _apiCom(
        listar: (_, __) async => RespostaHttp(200, '[]'),
      );
      await tester.pumpWidget(_envolver(TelaPrestadorMinhasColetas(api: api, outbox: _outboxDummy())));
      await tester.pumpAndSettle();

      expect(find.text('Nenhuma coleta atribuída'), findsOneWidget);
    });

    testWidgets('erro de rede mostra mensagem e botão tentar novamente', (tester) async {
      final api = _apiCom(
        listar: (_, __) async => throw Exception('sem conexao'),
      );
      await tester.pumpWidget(_envolver(TelaPrestadorMinhasColetas(api: api, outbox: _outboxDummy())));
      await tester.pumpAndSettle();

      expect(find.text('Erro ao carregar coletas'), findsOneWidget);
      expect(find.text('Tentar novamente'), findsOneWidget);
    });

    testWidgets('401 mostra erro', (tester) async {
      final api = _apiCom(
        listar: (_, __) async => RespostaHttp(401, '{}'),
      );
      await tester.pumpWidget(_envolver(TelaPrestadorMinhasColetas(api: api, outbox: _outboxDummy())));
      await tester.pumpAndSettle();

      expect(find.text('Erro ao carregar coletas'), findsOneWidget);
    });

    testWidgets('exibe status e quantidade de pneus', (tester) async {
      final api = _apiCom(
        listar: (_, __) async => RespostaHttp(200, jsonEncode([_coletaJson()])),
      );
      await tester.pumpWidget(_envolver(TelaPrestadorMinhasColetas(api: api, outbox: _outboxDummy())));
      await tester.pumpAndSettle();

      expect(find.text('Aceita · 10 pneu(s)'), findsOneWidget);
    });

    testWidgets('selecionar coleta navega para detalhe', (tester) async {
      final api = _apiCom(
        listar: (_, __) async => RespostaHttp(200, jsonEncode([_coletaJson()])),
      );
      await tester.pumpWidget(_envolver(TelaPrestadorMinhasColetas(api: api, outbox: _outboxDummy())));
      await tester.pumpAndSettle();

      await tester.tap(find.text('COL-TEST123'));
      await tester.pumpAndSettle();

      expect(find.text('Iniciar deslocamento'), findsOneWidget);
    });

    testWidgets('botão refresh recarrega lista', (tester) async {
      var chamadas = 0;
      final api = _apiCom(
        listar: (_, __) async {
          chamadas++;
          return RespostaHttp(200, jsonEncode(chamadas == 1 ? [_coletaJson()] : []));
        },
      );
      await tester.pumpWidget(_envolver(TelaPrestadorMinhasColetas(api: api, outbox: _outboxDummy())));
      await tester.pumpAndSettle();

      expect(find.text('COL-TEST123'), findsOneWidget);

      await tester.tap(find.byIcon(Icons.refresh));
      await tester.pumpAndSettle();

      expect(find.text('Nenhuma coleta atribuída'), findsOneWidget);
    });
  });

  group('TelaPrestadorDetalheColeta', () {
    testWidgets('exibe detalhes da coleta', (tester) async {
      final api = _apiCom();
      final coleta = _coletaJson();
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      expect(find.text('COL-TEST123'), findsNWidgets(2));
      expect(find.text('Aceita'), findsOneWidget);
      expect(find.text('Iniciar deslocamento'), findsOneWidget);
      expect(find.text('Michelin 275/80R22.5'), findsOneWidget);
    });

    testWidgets('botão deslocamento aparece apenas para ACEITA', (tester) async {
      final api = _apiCom();
      final coleta = _coletaJson(status: 'EM_DESLOCAMENTO');
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Iniciar deslocamento'), findsNothing);
    });

    testWidgets('iniciar deslocamento com sucesso atualiza status', (tester) async {
      final api = _apiCom(
        escrita: (caminho, cabecalhos, corpo) async {
          expect(caminho, contains('/status'));
          expect(corpo, contains('EM_DESLOCAMENTO'));
          return RespostaHttp(200, jsonEncode({
            'id': 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
            'status': 'EM_DESLOCAMENTO',
          }));
        },
      );
      final coleta = _coletaJson();
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Iniciar deslocamento'));
      await tester.pumpAndSettle();

      expect(find.text('Deslocamento iniciado!'), findsOneWidget);
      expect(find.text('Em deslocamento'), findsOneWidget);
      expect(find.text('Iniciar deslocamento'), findsNothing);
    });

    testWidgets('409 no deslocamento mostra erro de transição', (tester) async {
      final api = _apiCom(
        escrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(409, '{"detail":"Transição inválida."}'),
      );
      final coleta = _coletaJson();
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Iniciar deslocamento'));
      await tester.pumpAndSettle();

      expect(find.text('Transição inválida. Status atual pode ter mudado.'), findsOneWidget);
    });

    testWidgets('401 no deslocamento mostra sessão expirada', (tester) async {
      final api = _apiCom(
        escrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(401, '{}'),
      );
      final coleta = _coletaJson();
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Iniciar deslocamento'));
      await tester.pumpAndSettle();

      expect(find.text('Sessão expirada. Faça login novamente.'), findsOneWidget);
    });

    testWidgets('erro de rede no deslocamento mostra mensagem genérica', (tester) async {
      final api = _apiCom(
        escrita: (caminho, cabecalhos, corpo) async =>
            throw Exception('sem conexao'),
      );
      final coleta = _coletaJson();
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Iniciar deslocamento'));
      await tester.pumpAndSettle();

      expect(find.text('Erro de conexão. Tente novamente.'), findsOneWidget);
    });

    testWidgets('exibe itens declarados', (tester) async {
      final api = _apiCom();
      final coleta = _coletaJson();
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Itens declarados'), findsOneWidget);
      expect(find.text('Michelin 275/80R22.5'), findsOneWidget);
      expect(find.text('Qtd: 10'), findsOneWidget);
    });

    testWidgets('exibe endereço formatado', (tester) async {
      final api = _apiCom();
      final coleta = _coletaJson();
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Rua Teste, 123, Centro'), findsOneWidget);
    });

    testWidgets('botão conferência aparece para EM_DESLOCAMENTO', (tester) async {
      final api = _apiCom();
      final coleta = _coletaJson(status: 'EM_DESLOCAMENTO');
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Iniciar conferência'), findsOneWidget);
      expect(find.text('Iniciar deslocamento'), findsNothing);
    });

    testWidgets('botão conferência não aparece para ACEITA', (tester) async {
      final api = _apiCom();
      final coleta = _coletaJson(status: 'ACEITA');
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Iniciar conferência'), findsNothing);
    });

    testWidgets('iniciar conferência com sucesso atualiza status', (tester) async {
      final api = _apiCom(
        escrita: (caminho, cabecalhos, corpo) async {
          expect(caminho, contains('/status'));
          expect(corpo, contains('EM_CONFERENCIA'));
          return RespostaHttp(200, jsonEncode({
            'id': 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
            'status': 'EM_CONFERENCIA',
          }));
        },
      );
      final coleta = _coletaJson(status: 'EM_DESLOCAMENTO');
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Iniciar conferência'));
      await tester.pumpAndSettle();

      expect(find.text('Conferência iniciada!'), findsOneWidget);
      expect(find.text('Em conferência'), findsOneWidget);
      expect(find.text('Iniciar conferência'), findsNothing);
    });

    testWidgets('409 na conferência mostra erro de transição', (tester) async {
      final api = _apiCom(
        escrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(409, '{"detail":"Transição inválida."}'),
      );
      final coleta = _coletaJson(status: 'EM_DESLOCAMENTO');
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Iniciar conferência'));
      await tester.pumpAndSettle();

      expect(find.text('Transição inválida. Status atual pode ter mudado.'), findsOneWidget);
    });

    testWidgets('401 na conferência mostra sessão expirada', (tester) async {
      final api = _apiCom(
        escrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(401, '{}'),
      );
      final coleta = _coletaJson(status: 'EM_DESLOCAMENTO');
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Iniciar conferência'));
      await tester.pumpAndSettle();

      expect(find.text('Sessão expirada. Faça login novamente.'), findsOneWidget);
    });

    testWidgets('erro de rede na conferência mostra mensagem genérica', (tester) async {
      final api = _apiCom(
        escrita: (caminho, cabecalhos, corpo) async =>
            throw Exception('sem conexao'),
      );
      final coleta = _coletaJson(status: 'EM_DESLOCAMENTO');
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: _outboxDummy(), coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Iniciar conferência'));
      await tester.pumpAndSettle();

      expect(find.text('Erro de conexão. Tente novamente.'), findsOneWidget);
    });

    testWidgets('botão finalizar coleta aparece apenas para CARREGADA', (tester) async {
      final api = _apiCom();
      final outbox = _outboxDummy();

      // Status CARREGADA: botão deve aparecer
      final coletaCarregada = _coletaJson(status: 'CARREGADA');
      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: outbox, coleta: coletaCarregada),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Finalizar coleta'), findsOneWidget);

      // Outros status: botão NÃO deve aparecer
      for (final st in ['ACEITA', 'EM_DESLOCAMENTO', 'EM_CONFERENCIA', 'FINALIZADA']) {
        await tester.pumpWidget(_envolver(
          TelaPrestadorDetalheColeta(api: api, outbox: outbox, coleta: _coletaJson(status: st)),
        ));
        await tester.pumpAndSettle();
        expect(find.text('Finalizar coleta'), findsNothing);
      }
    });

    testWidgets('finalização válida agenda operação no Outbox com corpo vazio estrito e sem valores financeiros', (tester) async {
      final api = _apiCom();
      final outbox = _outboxDummy(enviar: (_, __, ___) async => 200);
      final coleta = _coletaJson(status: 'CARREGADA');

      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: outbox, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Finalizar coleta'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('Coleta finalizada com sucesso!'), findsOneWidget);
      expect(find.text('Finalizada'), findsOneWidget);
      expect(find.text('Finalizar coleta'), findsNothing);

      final fila = await outbox.pendentes();
      expect(fila.length, 1);
      final op = fila.first;
      expect(op.caminho, '/api/v1/collections/aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee/finalizar');
      // Doc AGENTS §4.2 e §3: Flutter NUNCA envia valores financeiros, corpo é vazio estrito {}
      expect(op.corpo, isEmpty);
      expect(op.corpo, isA<Map<String, dynamic>>());

      // Sincroniza e descarta
      final sincronizadas = await outbox.sincronizarPendentes();
      expect(sincronizadas, 1);
      expect(await outbox.pendentes(), isEmpty);
    });

    testWidgets('operação offline de finalização permanece pendente no Outbox com UUIDv4 preservado', (tester) async {
      final api = _apiCom();
      final outbox = _outboxDummy(enviar: (_, __, ___) async => throw Exception('Sem rede'));
      final coleta = _coletaJson(status: 'CARREGADA');

      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: outbox, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Finalizar coleta'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('Coleta finalizada com sucesso!'), findsOneWidget);
      expect(find.text('Finalizada'), findsOneWidget);

      final fila = await outbox.pendentes();
      expect(fila.length, 1);
      final op = fila.first;
      expect(op.caminho, '/api/v1/collections/aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee/finalizar');
      expect(op.corpo, isEmpty);
      expect(op.status, StatusOperacaoOutbox.pendente);

      final padraoUuidV4 = RegExp(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        caseSensitive: false,
      );
      expect(padraoUuidV4.hasMatch(op.id), isTrue);
    });
  });
}
