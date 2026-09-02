import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/core/api/api_service.dart';
import 'package:meu_app_coleta_pneus/core/outbox/outbox_service.dart';
import 'package:meu_app_coleta_pneus/core/sessao/servico_sessao.dart';
import 'package:meu_app_coleta_pneus/prestador/tela_prestador_detalhe_coleta.dart';
import 'package:meu_app_coleta_pneus/prestador/tela_prestador_resumo_coleta.dart';
import 'package:shared_preferences/shared_preferences.dart';

Map<String, dynamic> _coletaJson({
  String id = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
  String codigo = 'COL-FIN123',
  String status = 'FINALIZADA',
}) {
  return {
    'id': id,
    'codigo_identificador': codigo,
    'status': status,
    'endereco_origem_json': {
      'rua': 'Av. Principal',
      'numero': '500',
      'bairro': 'Distrito Industrial',
      'cidade': 'São Paulo',
    },
    'data_agendada': '2026-09-01T14:00:00+00:00',
    'provider_id': 'pppppppp-pppp-4ppp-8ppp-pppppppppppp',
    'criado_em': '2026-08-20T10:00:00+00:00',
    'itens': [
      {'marca': 'Michelin', 'dimensao': '275/80R22.5', 'quantidade_declarada': 2, 'observacao': null},
    ],
  };
}

final _pneusExemplo = [
  {
    'id': 'pneu-1',
    'dot': '2324',
    'numero_fogo': 'FOGO-001',
    'numero_fogo_ilegivel': false,
    'idade_calculada_anos': 2.0,
    'alerta_idade_obsoleto': false,
    'marca': 'Michelin',
    'medida': '275/80R22.5',
  },
  {
    'id': 'pneu-2',
    'dot': '1015',
    'numero_fogo': null,
    'numero_fogo_ilegivel': true,
    'idade_calculada_anos': 11.4,
    'alerta_idade_obsoleto': true,
    'marca': 'Pirelli',
    'medida': '295/80R22.5',
  },
];

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

Widget _envolver(Widget child) {
  return MaterialApp(home: child);
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('TelaPrestadorResumoColeta', () {
    testWidgets('exibe carregando e depois dados da coleta finalizada e lista de pneus', (tester) async {
      final api = _apiCom(
        leitura: (caminho, cabecalhos) async {
          expect(caminho, contains('/conferencia/pneus'));
          return RespostaHttp(200, jsonEncode(_pneusExemplo));
        },
      );

      await tester.pumpWidget(_envolver(
        TelaPrestadorResumoColeta(api: api, coleta: _coletaJson()),
      ));

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await tester.pumpAndSettle();

      expect(find.text('Resumo: COL-FIN123'), findsOneWidget);
      expect(find.text('Finalizada'), findsOneWidget);
      expect(find.text('Av. Principal, 500, Distrito Industrial, São Paulo'), findsOneWidget);
      expect(find.text('Pneus conferidos (2)'), findsOneWidget);
      expect(find.text('Michelin 275/80R22.5'), findsOneWidget);
      expect(find.text('Pirelli 295/80R22.5'), findsOneWidget);
      expect(find.textContaining('DOT: 2324'), findsOneWidget);
      expect(find.textContaining('Fogo: FOGO-001'), findsOneWidget);
      expect(find.textContaining('Ilegível'), findsOneWidget);
      expect(find.textContaining('Idade: 11.4 anos'), findsOneWidget);
    });

    testWidgets('lista vazia de pneus exibe aviso informativo', (tester) async {
      final api = _apiCom(
        leitura: (_, __) async => RespostaHttp(200, '[]'),
      );

      await tester.pumpWidget(_envolver(
        TelaPrestadorResumoColeta(api: api, coleta: _coletaJson()),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Pneus conferidos (0)'), findsOneWidget);
      expect(find.text('Nenhum pneu conferido registrado.'), findsOneWidget);
    });

    testWidgets('bloqueia acesso para coleta com status diferente de FINALIZADA', (tester) async {
      var chamouLeitura = false;
      final api = _apiCom(
        leitura: (_, __) async {
          chamouLeitura = true;
          return RespostaHttp(200, '[]');
        },
      );

      await tester.pumpWidget(_envolver(
        TelaPrestadorResumoColeta(
          api: api,
          coleta: _coletaJson(status: 'EM_CONFERENCIA'),
        ),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Coleta não finalizada'), findsOneWidget);
      expect(
        find.text('O resumo consolidado só está disponível para coletas no status FINALIZADA.'),
        findsOneWidget,
      );
      expect(chamouLeitura, isFalse);
    });

    testWidgets('trata erro de leitura e permite tentar novamente', (tester) async {
      var tentativas = 0;
      final api = _apiCom(
        leitura: (_, __) async {
          tentativas++;
          if (tentativas == 1) {
            throw Exception('Falha de rede');
          }
          return RespostaHttp(200, jsonEncode(_pneusExemplo));
        },
      );

      await tester.pumpWidget(_envolver(
        TelaPrestadorResumoColeta(api: api, coleta: _coletaJson()),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Não foi possível carregar os pneus da coleta.'), findsOneWidget);
      expect(find.text('Tentar novamente'), findsOneWidget);

      await tester.tap(find.text('Tentar novamente'));
      await tester.pumpAndSettle();

      expect(find.text('Pneus conferidos (2)'), findsOneWidget);
      expect(find.text('Michelin 275/80R22.5'), findsOneWidget);
    });

    testWidgets('botão atualizar na AppBar recarrega os pneus', (tester) async {
      var chamadas = 0;
      final api = _apiCom(
        leitura: (_, __) async {
          chamadas++;
          return RespostaHttp(200, jsonEncode(_pneusExemplo));
        },
      );

      await tester.pumpWidget(_envolver(
        TelaPrestadorResumoColeta(api: api, coleta: _coletaJson()),
      ));
      await tester.pumpAndSettle();
      expect(chamadas, 1);

      await tester.tap(find.byIcon(Icons.refresh));
      await tester.pumpAndSettle();
      expect(chamadas, 2);
    });

    testWidgets('navegação a partir da TelaPrestadorDetalheColeta abre o resumo', (tester) async {
      final api = _apiCom(
        leitura: (_, __) async => RespostaHttp(200, jsonEncode(_pneusExemplo)),
      );
      final outbox = OutboxService();
      final coleta = _coletaJson(status: 'FINALIZADA');

      await tester.pumpWidget(_envolver(
        TelaPrestadorDetalheColeta(api: api, outbox: outbox, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Ver resumo da coleta'), findsOneWidget);
      await tester.tap(find.text('Ver resumo da coleta'));
      await tester.pumpAndSettle();

      expect(find.byType(TelaPrestadorResumoColeta), findsOneWidget);
      expect(find.text('Pneus conferidos (2)'), findsOneWidget);
    });
  });
}
