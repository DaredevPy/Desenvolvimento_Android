import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/core/api/api_service.dart';
import 'package:meu_app_coleta_pneus/core/outbox/outbox_service.dart';
import 'package:meu_app_coleta_pneus/core/sessao/servico_sessao.dart';
import 'package:meu_app_coleta_pneus/prestador/tela_prestador_conferencia.dart';
import 'package:shared_preferences/shared_preferences.dart';

Map<String, dynamic> _coletaJson({
  String id = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
  String status = 'EM_CONFERENCIA',
}) {
  return {
    'id': id,
    'codigo_identificador': 'COL-TEST123',
    'status': status,
    'itens': [
      {'marca': 'Michelin', 'dimensao': '275/80R22.5', 'quantidade_declarada': 10},
    ],
  };
}

const _iniciarConferenciaResponse = {
  'id': 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
  'status': 'EM_CONFERENCIA',
  'itens_declarados': [
    {'marca': 'Michelin', 'dimensao': '275/80R22.5', 'quantidade_declarada': 10, 'observacao': null},
  ],
};

const _itensVaziosResponse = {
  'id': 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
  'status': 'EM_CONFERENCIA',
  'itens_declarados': <Map<String, dynamic>>[],
};

/// Mock que responde POST (escrita) e GET (leitura).
ApiService _apiCom({
  Future<RespostaHttp> Function(String, Map<String, String>)? leitura,
  Future<RespostaHttp> Function(String, Map<String, String>, String)? escrita,
}) {
  return ApiService(
    enviar: leitura,
    enviarEscrita: escrita,
    obterToken: () => 'jwt.teste',
  );
}

OutboxService _outboxCom({
  Future<int> Function(String, Map<String, String>, String)? enviar,
}) {
  return OutboxService(enviar: enviar);
}

Widget _envolver(Widget child) {
  return MaterialApp(home: child);
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('TelaPrestadorConferencia', () {
    testWidgets('exibe carregando e depois itens declarados', (tester) async {
      final api = _apiCom(
        escrita: (_, __, ___) async =>
            RespostaHttp(200, jsonEncode(_iniciarConferenciaResponse)),
      );
      final outbox = _outboxCom();
      await tester.pumpWidget(_envolver(
        TelaPrestadorConferencia(api: api, outbox: outbox, coleta: _coletaJson()),
      ));
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await tester.pumpAndSettle();
      expect(find.text('Itens declarados'), findsOneWidget);
      expect(find.text('Michelin 275/80R22.5'), findsOneWidget);
    });

    testWidgets('lista vazia mostra mensagem', (tester) async {
      final api = _apiCom(
        escrita: (_, __, ___) async =>
            RespostaHttp(200, jsonEncode(_itensVaziosResponse)),
      );
      final outbox = _outboxCom();
      await tester.pumpWidget(_envolver(
        TelaPrestadorConferencia(api: api, outbox: outbox, coleta: _coletaJson()),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Nenhum item declarado'), findsOneWidget);
    });

    testWidgets('erro de rede mostra itens vazios e formulario', (tester) async {
      final api = _apiCom(
        escrita: (_, __, ___) async => throw Exception('sem conexao'),
      );
      final outbox = _outboxCom();
      await tester.pumpWidget(_envolver(
        TelaPrestadorConferencia(api: api, outbox: outbox, coleta: _coletaJson()),
      ));
      await tester.pumpAndSettle();
      expect(find.text('Nenhum item declarado'), findsOneWidget);
      expect(find.text('Registrar pneu'), findsOneWidget);
    });

    testWidgets('formulario exibe campos obrigatorios', (tester) async {
      final api = _apiCom(
        escrita: (_, __, ___) async =>
            RespostaHttp(200, jsonEncode(_itensVaziosResponse)),
      );
      final outbox = _outboxCom();
      await tester.pumpWidget(_envolver(
        TelaPrestadorConferencia(api: api, outbox: outbox, coleta: _coletaJson()),
      ));
      await tester.pumpAndSettle();

      expect(find.text('DOT (WWYY)'), findsOneWidget);
      expect(find.text('Marca'), findsOneWidget);
      expect(find.text('Medida'), findsOneWidget);
      expect(find.text('Nº Fogo'), findsOneWidget);
    });

    testWidgets('adicionar pneu a lista local', (tester) async {
      final api = _apiCom(
        escrita: (_, __, ___) async =>
            RespostaHttp(200, jsonEncode(_itensVaziosResponse)),
      );
      final outbox = _outboxCom();
      await tester.pumpWidget(_envolver(
        TelaPrestadorConferencia(api: api, outbox: outbox, coleta: _coletaJson()),
      ));
      await tester.pumpAndSettle();

      await tester.enterText(find.widgetWithText(TextFormField, 'DOT (WWYY)'), '2324');
      await tester.enterText(find.widgetWithText(TextFormField, 'Marca'), 'Michelin');
      await tester.enterText(find.widgetWithText(TextFormField, 'Medida'), '275/80R22.5');
      await tester.tap(find.text('Adicionar à lista'));
      await tester.pumpAndSettle();

      expect(find.text('Pneus registrados (1)'), findsOneWidget);
      expect(find.text('Michelin 275/80R22.5'), findsWidgets);
      expect(find.text('DOT: 2324'), findsOneWidget);
    });

    testWidgets('validacao DOT rejeita valor invalido', (tester) async {
      final api = _apiCom(
        escrita: (_, __, ___) async =>
            RespostaHttp(200, jsonEncode(_itensVaziosResponse)),
      );
      final outbox = _outboxCom();
      await tester.pumpWidget(_envolver(
        TelaPrestadorConferencia(api: api, outbox: outbox, coleta: _coletaJson()),
      ));
      await tester.pumpAndSettle();

      await tester.enterText(find.widgetWithText(TextFormField, 'DOT (WWYY)'), '12');
      await tester.enterText(find.widgetWithText(TextFormField, 'Marca'), 'Michelin');
      await tester.enterText(find.widgetWithText(TextFormField, 'Medida'), '275/80R22.5');
      await tester.tap(find.text('Adicionar à lista'));
      await tester.pumpAndSettle();

      expect(find.text('4 dígitos (WWYY)'), findsOneWidget);
    });

    testWidgets('botao ilegivel desabilita campo numero fogo', (tester) async {
      final api = _apiCom(
        escrita: (_, __, ___) async =>
            RespostaHttp(200, jsonEncode(_itensVaziosResponse)),
      );
      final outbox = _outboxCom();
      await tester.pumpWidget(_envolver(
        TelaPrestadorConferencia(api: api, outbox: outbox, coleta: _coletaJson()),
      ));
      await tester.pumpAndSettle();

      final fogoField = find.widgetWithText(TextFormField, 'Nº Fogo');
      expect(tester.widget<TextFormField>(fogoField).enabled, isTrue);

      await tester.tap(find.byType(Switch));
      await tester.pumpAndSettle();

      expect(tester.widget<TextFormField>(fogoField).enabled, isFalse);
    });

    testWidgets('registrar pneus agendado no outbox', (tester) async {
      final api = _apiCom(
        escrita: (_, __, ___) async =>
            RespostaHttp(200, jsonEncode(_itensVaziosResponse)),
      );
      final outbox = _outboxCom(enviar: (_, __, ___) async => 201);
      await tester.pumpWidget(_envolver(
        TelaPrestadorConferencia(api: api, outbox: outbox, coleta: _coletaJson()),
      ));
      await tester.pumpAndSettle();

      await tester.enterText(find.widgetWithText(TextFormField, 'DOT (WWYY)'), '2324');
      await tester.enterText(find.widgetWithText(TextFormField, 'Marca'), 'Michelin');
      await tester.enterText(find.widgetWithText(TextFormField, 'Medida'), '275/80R22.5');
      await tester.tap(find.text('Adicionar à lista'));
      await tester.pumpAndSettle();

      await tester.ensureVisible(find.text('Registrar pneu(s)'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Registrar pneu(s)'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('1 pneu(s) agendado(s) para envio.'), findsOneWidget);
    });

    testWidgets('concluir conferencia com sucesso', (tester) async {
      final api = _apiCom(
        escrita: (_, __, ___) async =>
            RespostaHttp(200, jsonEncode(_itensVaziosResponse)),
      );
      final outbox = _outboxCom(enviar: (_, __, ___) async => 200);
      await tester.pumpWidget(_envolver(
        TelaPrestadorConferencia(api: api, outbox: outbox, coleta: _coletaJson()),
      ));
      await tester.pumpAndSettle();

      await tester.enterText(find.widgetWithText(TextFormField, 'DOT (WWYY)'), '2324');
      await tester.enterText(find.widgetWithText(TextFormField, 'Marca'), 'Michelin');
      await tester.enterText(find.widgetWithText(TextFormField, 'Medida'), '275/80R22.5');
      await tester.tap(find.text('Adicionar à lista'));
      await tester.pumpAndSettle();

      await tester.ensureVisible(find.text('Concluir conferência'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Concluir conferência'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.text('Conferência concluída!'), findsOneWidget);
    });

    testWidgets('concluir sem pneus mostra aviso', (tester) async {
      final api = _apiCom(
        escrita: (_, __, ___) async =>
            RespostaHttp(200, jsonEncode(_itensVaziosResponse)),
      );
      final outbox = _outboxCom();
      await tester.pumpWidget(_envolver(
        TelaPrestadorConferencia(api: api, outbox: outbox, coleta: _coletaJson()),
      ));
      await tester.pumpAndSettle();

      await tester.ensureVisible(find.text('Concluir conferência'));
      await tester.tap(find.text('Concluir conferência'));
      await tester.pumpAndSettle();

      expect(find.text('Registre pelo menos 1 pneu.'), findsOneWidget);
    });
  });
}
