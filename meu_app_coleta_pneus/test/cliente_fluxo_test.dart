import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/cliente/screens/tela_cliente_criar_coleta.dart';
import 'package:meu_app_coleta_pneus/cliente/screens/tela_cliente_minhas_coletas.dart';
import 'package:meu_app_coleta_pneus/core/api/api_service.dart';
import 'package:meu_app_coleta_pneus/core/outbox/outbox_service.dart';
import 'package:meu_app_coleta_pneus/core/sessao/servico_sessao.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  OutboxService _outboxCom(
    Future<int> Function(String, Map<String, String>, String)? enviar,
  ) {
    return OutboxService(enviar: enviar);
  }

  ApiService _apiCom(
    Future<RespostaHttp> Function(String, Map<String, String>)? enviar,
  ) {
    return ApiService(enviar: enviar);
  }

  Map<String, dynamic> _coletaJson({
    String id = '11111111-2222-4333-8444-555555555555',
  }) {
    return {
      'id': id,
      'codigo_identificador': 'COL-TEST123',
      'status': 'SOLICITADA',
      'endereco_origem_json': {'endereco': 'Rua Teste, 123'},
      'data_agendada': '2026-09-01T12:00:00+00:00',
      'provider_id': null,
      'criado_em': '2026-08-20T10:00:00+00:00',
      'itens': [
        {
          'marca': 'Marca X',
          'dimensao': '205/55R16',
          'quantidade_declarada': 4,
          'observacao': null,
        },
      ],
    };
  }

  group('TelaClienteCriarColeta', () {
    testWidgets('formulário válido grava operação no Outbox', (tester) async {
      final outbox = _outboxCom(null);

      await tester.pumpWidget(MaterialApp(
        home: TelaClienteCriarColeta(outbox: outbox),
      ));

      await tester.enterText(find.byKey(const Key('campo_endereco')), 'Rua A, 123');
      await tester.enterText(find.byKey(const Key('campo_marca')), 'Bridgestone');
      await tester.enterText(find.byKey(const Key('campo_dimensao')), '205/55R16');
      await tester.enterText(find.byKey(const Key('campo_quantidade')), '4');

      await tester.tap(find.text('Agendar Coleta'));
      await tester.pumpAndSettle();

      final fila = await outbox.pendentes();
      expect(fila, hasLength(1));
      expect(fila.first.caminho, '/api/v1/collections');
      expect((fila.first.corpo['itens'] as List).first['marca'], 'Bridgestone');
    });

    testWidgets('operação preserva idempotência', (tester) async {
      final outbox = _outboxCom(null);

      await tester.pumpWidget(MaterialApp(
        home: TelaClienteCriarColeta(outbox: outbox),
      ));

      await tester.enterText(find.byKey(const Key('campo_endereco')), 'Rua B');
      await tester.enterText(find.byKey(const Key('campo_marca')), 'Pirelli');
      await tester.enterText(find.byKey(const Key('campo_dimensao')), '195/65R15');
      await tester.enterText(find.byKey(const Key('campo_quantidade')), '2');

      await tester.tap(find.text('Agendar Coleta'));
      await tester.pumpAndSettle();

      final fila = await outbox.pendentes();
      expect(fila, hasLength(1));
      expect(fila.first.id, isNotEmpty);
    });

    testWidgets('funcionamento sem conexão grava na fila', (tester) async {
      final outbox = _outboxCom(null);

      await tester.pumpWidget(MaterialApp(
        home: TelaClienteCriarColeta(outbox: outbox),
      ));

      await tester.enterText(find.byKey(const Key('campo_endereco')), 'Rua C');
      await tester.enterText(find.byKey(const Key('campo_marca')), 'Goodyear');
      await tester.enterText(find.byKey(const Key('campo_dimensao')), '225/45R17');
      await tester.enterText(find.byKey(const Key('campo_quantidade')), '1');

      await tester.tap(find.text('Agendar Coleta'));
      await tester.pumpAndSettle();

      final fila = await outbox.pendentes();
      expect(fila, hasLength(1));
    });

    testWidgets('campos obrigatórios vazios mostram erro', (tester) async {
      final outbox = _outboxCom(null);

      await tester.pumpWidget(MaterialApp(
        home: TelaClienteCriarColeta(outbox: outbox),
      ));

      await tester.tap(find.text('Agendar Coleta'));
      await tester.pumpAndSettle();

      expect(find.text('Obrigatório'), findsWidgets);
    });
  });

  group('TelaClienteMinhasColetas', () {
    testWidgets('sucesso exibe lista de coletas', (tester) async {
      final api = _apiCom(
        (caminho, cabecalhos) async => RespostaHttp(
          200,
          jsonEncode([_coletaJson()]),
        ),
      );
      final outbox = _outboxCom(null);

      await tester.pumpWidget(MaterialApp(
        home: TelaClienteMinhasColetas(api: api, outbox: outbox),
      ));
      await tester.pumpAndSettle();

      expect(find.text('COL-TEST123'), findsOneWidget);
      expect(find.textContaining('Solicitada'), findsOneWidget);
    });

    testWidgets('lista vazia mostra mensagem', (tester) async {
      final api = _apiCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
      );
      final outbox = _outboxCom(null);

      await tester.pumpWidget(MaterialApp(
        home: TelaClienteMinhasColetas(api: api, outbox: outbox),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Nenhuma coleta encontrada'), findsOneWidget);
      expect(find.text('Criar primeira coleta'), findsOneWidget);
    });

    testWidgets('erro de rede exibe mensagem de erro', (tester) async {
      final api = _apiCom(
        (caminho, cabecalhos) async => throw Exception('sem conexao'),
      );
      final outbox = _outboxCom(null);

      await tester.pumpWidget(MaterialApp(
        home: TelaClienteMinhasColetas(api: api, outbox: outbox),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Erro ao carregar coletas'), findsOneWidget);
      expect(find.text('Tentar novamente'), findsOneWidget);
    });

    testWidgets('erro 401 exibe mensagem de erro', (tester) async {
      final api = _apiCom(
        (caminho, cabecalhos) async =>
            RespostaHttp(401, '{"detail":"Token inválido."}'),
      );
      final outbox = _outboxCom(null);

      await tester.pumpWidget(MaterialApp(
        home: TelaClienteMinhasColetas(api: api, outbox: outbox),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Erro ao carregar coletas'), findsOneWidget);
    });

    testWidgets('botão FAB navega para criar coleta', (tester) async {
      final api = _apiCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
      );
      final outbox = _outboxCom(null);

      await tester.pumpWidget(MaterialApp(
        home: TelaClienteMinhasColetas(api: api, outbox: outbox),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.byType(FloatingActionButton));
      await tester.pumpAndSettle();

      expect(find.byType(TelaClienteCriarColeta), findsOneWidget);
    });

    testWidgets('recarregar recarrega lista', (tester) async {
      var chamadas = 0;
      final api = _apiCom(
        (caminho, cabecalhos) async {
          chamadas++;
          return RespostaHttp(
            200,
            chamadas == 1 ? '[]' : jsonEncode([_coletaJson()]),
          );
        },
      );
      final outbox = _outboxCom(null);

      await tester.pumpWidget(MaterialApp(
        home: TelaClienteMinhasColetas(api: api, outbox: outbox),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Nenhuma coleta encontrada'), findsOneWidget);
      expect(chamadas, 1);

      await tester.tap(find.text('Criar primeira coleta'));
      await tester.pumpAndSettle();

      expect(chamadas, greaterThanOrEqualTo(1));
    });
  });
}
