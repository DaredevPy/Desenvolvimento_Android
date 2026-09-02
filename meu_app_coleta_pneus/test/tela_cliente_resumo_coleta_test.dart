import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/cliente/screens/tela_cliente_minhas_coletas.dart';
import 'package:meu_app_coleta_pneus/cliente/screens/tela_cliente_resumo_coleta.dart';
import 'package:meu_app_coleta_pneus/core/api/api_service.dart';
import 'package:meu_app_coleta_pneus/core/outbox/outbox_service.dart';
import 'package:meu_app_coleta_pneus/core/sessao/servico_sessao.dart';
import 'package:shared_preferences/shared_preferences.dart';

Map<String, dynamic> _coletaFinalizadaJson({
  String id = '11111111-2222-4333-8444-555555555555',
  String codigo = 'COL-CLI-FIN',
  String status = 'FINALIZADA',
}) {
  return {
    'id': id,
    'codigo_identificador': codigo,
    'status': status,
    'endereco_origem_json': {
      'rua': 'Av. Paulista',
      'numero': '1000',
      'bairro': 'Bela Vista',
      'cidade': 'São Paulo',
    },
    'data_agendada': '2026-09-01T10:00:00+00:00',
    'provider_id': 'pppppppp-pppp-4ppp-8ppp-pppppppppppp',
    'criado_em': '2026-08-25T08:00:00+00:00',
    'itens': [
      {'marca': 'Michelin', 'dimensao': '275/80R22.5', 'quantidade_declarada': 2, 'observacao': null},
    ],
    'pneus': [
      {
        'id': 'pneu-101',
        'dot': '2324',
        'numero_fogo': 'FOGO-101',
        'numero_fogo_ilegivel': false,
        'idade_calculada_anos': 2.0,
        'alerta_idade_obsoleto': false,
        'marca': 'Michelin',
        'medida': '275/80R22.5',
      },
      {
        'id': 'pneu-102',
        'dot': '1216',
        'numero_fogo': null,
        'numero_fogo_ilegivel': true,
        'idade_calculada_anos': 10.4,
        'alerta_idade_obsoleto': true,
        'marca': 'Michelin',
        'medida': '275/80R22.5',
      },
    ],
  };
}

ApiService _apiCom({
  Future<RespostaHttp> Function(String, Map<String, String>)? leitura,
  Future<RespostaHttp> Function(String, Map<String, String>, String)? escrita,
}) {
  return ApiService(
    enviar: leitura,
    enviarEscrita: escrita,
    obterToken: () => 'jwt.cliente',
  );
}

Widget _envolver(Widget child) {
  return MaterialApp(home: child);
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('TelaClienteResumoColeta', () {
    testWidgets('Cliente visualiza resumo de sua coleta FINALIZADA com dados dos pneus', (tester) async {
      final coleta = _coletaFinalizadaJson();
      final api = _apiCom(
        leitura: (caminho, cabecalhos) async {
          expect(caminho, '/api/v1/collections/${coleta['id']}');
          expect(cabecalhos['Authorization'], 'Bearer jwt.cliente');
          return RespostaHttp(200, jsonEncode(coleta));
        },
      );

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await tester.pumpAndSettle();

      expect(find.text('Resumo: COL-CLI-FIN'), findsOneWidget);
      expect(find.text('Finalizada'), findsOneWidget);
      expect(find.text('Av. Paulista, 1000, Bela Vista, São Paulo'), findsOneWidget);
      expect(find.text('Itens declarados (1)'), findsOneWidget);
      expect(find.text('Michelin 275/80R22.5'), findsWidgets);
      expect(find.text('Pneus conferidos (2)'), findsOneWidget);
      expect(find.textContaining('DOT: 2324'), findsOneWidget);
      expect(find.textContaining('Fogo: FOGO-101'), findsOneWidget);
      expect(find.textContaining('Ilegível'), findsOneWidget);
      expect(find.textContaining('Idade: 10.4 anos'), findsOneWidget);
    });

    testWidgets('bloqueia/impede exibição de resumo para coleta não finalizada', (tester) async {
      var chamouEndpoint = false;
      final api = _apiCom(
        leitura: (_, __) async {
          chamouEndpoint = true;
          return RespostaHttp(200, '{}');
        },
      );
      final coleta = _coletaFinalizadaJson(status: 'SOLICITADA');

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Coleta não finalizada'), findsOneWidget);
      expect(
        find.text('O resumo consolidado só está disponível para coletas no status FINALIZADA.'),
        findsOneWidget,
      );
      expect(chamouEndpoint, isFalse);
    });

    testWidgets('trata erro de leitura e permite tentar novamente', (tester) async {
      var chamadas = 0;
      final coleta = _coletaFinalizadaJson();
      final api = _apiCom(
        leitura: (_, __) async {
          chamadas++;
          if (chamadas == 1) {
            throw Exception('Falha de conexão');
          }
          return RespostaHttp(200, jsonEncode(coleta));
        },
      );

      // Passa coleta sem pneus locais para testar a tela de erro
      final coletaSemPneusLocais = Map<String, dynamic>.from(coleta)..remove('pneus');

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coletaSemPneusLocais),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Não foi possível carregar os dados da coleta.'), findsOneWidget);
      expect(find.text('Tentar novamente'), findsOneWidget);

      await tester.tap(find.text('Tentar novamente'));
      await tester.pumpAndSettle();

      expect(find.text('Pneus conferidos (2)'), findsOneWidget);
    });

    testWidgets('botão atualizar na AppBar recarrega os dados do cliente', (tester) async {
      var chamadas = 0;
      final coleta = _coletaFinalizadaJson();
      final api = _apiCom(
        leitura: (_, __) async {
          chamadas++;
          return RespostaHttp(200, jsonEncode(coleta));
        },
      );

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));
      await tester.pumpAndSettle();
      expect(chamadas, 1);

      await tester.tap(find.byIcon(Icons.refresh));
      await tester.pumpAndSettle();
      expect(chamadas, 2);
    });

    testWidgets('botão Contestar aparece apenas quando status é FINALIZADA', (tester) async {
      final coleta = _coletaFinalizadaJson();
      final api = _apiCom(
        leitura: (_, __) async => RespostaHttp(200, jsonEncode(coleta)),
      );

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Contestar coleta'), findsOneWidget);
      expect(find.byIcon(Icons.report_problem), findsOneWidget);
    });

    testWidgets('botão Contestar NÃO aparece quando status é CONTESTADA', (tester) async {
      final coleta = _coletaFinalizadaJson(status: 'CONTESTADA');
      final api = _apiCom(
        leitura: (_, __) async => RespostaHttp(200, jsonEncode(coleta)),
      );

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Contestar coleta'), findsNothing);
      expect(find.byIcon(Icons.report_problem), findsNothing);
    });

    testWidgets('botão Contestar NÃO aparece em outros estados (ex: CARREGADA)', (tester) async {
      final coleta = _coletaFinalizadaJson(status: 'CARREGADA');
      final api = _apiCom(
        leitura: (_, __) async => RespostaHttp(200, jsonEncode(coleta)),
      );

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      expect(find.text('Contestar coleta'), findsNothing);
    });

    testWidgets('confirmação antes de enviar contestação', (tester) async {
      final coleta = _coletaFinalizadaJson();
      final api = _apiCom(
        leitura: (_, __) async => RespostaHttp(200, jsonEncode(coleta)),
        escrita: (_, __, ___) async => RespostaHttp(200, jsonEncode({
          'id': coleta['id'],
          'status': 'CONTESTADA',
        })),
      );

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      // Encontra o botão "Contestar coleta" (ElevatedButton)
      final botaoContestar = find.widgetWithText(ElevatedButton, 'Contestar coleta');
      expect(botaoContestar, findsOneWidget);

      await tester.tap(botaoContestar);
      await tester.pumpAndSettle();

      // Dialog aberto: verifica título e botões
      expect(find.byType(AlertDialog), findsOneWidget);
      expect(find.descendant(of: find.byType(AlertDialog), matching: find.text('Contestar coleta')), findsOneWidget);
      expect(find.text('Confirmar contestação'), findsOneWidget);
      expect(find.text('Cancelar'), findsOneWidget);
    });

    testWidgets('sucesso altera estado para CONTESTADA', (tester) async {
      final coleta = _coletaFinalizadaJson();
      final api = _apiCom(
        leitura: (_, __) async => RespostaHttp(200, jsonEncode(coleta)),
        escrita: (_, __, ___) async => RespostaHttp(200, jsonEncode({
          'id': coleta['id'],
          'status': 'CONTESTADA',
        })),
      );

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      // Botão de contestar existe inicialmente
      expect(find.widgetWithText(ElevatedButton, 'Contestar coleta'), findsOneWidget);

      final botaoContestar = find.widgetWithText(ElevatedButton, 'Contestar coleta');
      await tester.tap(botaoContestar);
      await tester.pumpAndSettle();

      await tester.tap(find.text('Confirmar contestação'));
      await tester.pumpAndSettle();

      // Aguarda o SnackBar
      await tester.pump(const Duration(seconds: 1));

      // Confirma que o SnackBar de sucesso aparece
      expect(find.text('Contestação registrada. A coleta agora está como CONTESTADA.'), findsOneWidget);
      // Botão de contestar desaparece (estado não é mais FINALIZADA)
      expect(find.widgetWithText(ElevatedButton, 'Contestar coleta'), findsNothing);
    });

    testWidgets('duplo clique é bloqueado durante contestação', (tester) async {
      final coleta = _coletaFinalizadaJson();
      var chamadasEscrita = 0;
      final api = _apiCom(
        leitura: (_, __) async => RespostaHttp(200, jsonEncode(coleta)),
        escrita: (_, __, ___) async {
          chamadasEscrita++;
          await Future.delayed(const Duration(milliseconds: 50));
          return RespostaHttp(200, jsonEncode({
            'id': coleta['id'],
            'status': 'CONTESTADA',
          }));
        },
      );

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Contestar coleta'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Confirmar contestação'));
      await tester.pump(); // não espera terminar

      // Tenta tocar novamente enquanto está processando
      await tester.tap(find.text('Contestar coleta'));
      await tester.pumpAndSettle();

      // Deve ter feito apenas uma chamada de escrita
      expect(chamadasEscrita, 1);
    });

    testWidgets('tratamento 403 - operação não permitida', (tester) async {
      final coleta = _coletaFinalizadaJson();
      final api = _apiCom(
        leitura: (_, __) async => RespostaHttp(200, jsonEncode(coleta)),
        escrita: (_, __, ___) async => RespostaHttp(403, '{"detail":"Acesso negado."}'),
      );

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Contestar coleta'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Confirmar contestação'));
      await tester.pumpAndSettle();

      expect(find.text('Operação não permitida. Apenas o dono da coleta pode contestar.'), findsOneWidget);
    });

    testWidgets('tratamento 404 - coleta não encontrada', (tester) async {
      final coleta = _coletaFinalizadaJson();
      final api = _apiCom(
        leitura: (_, __) async => RespostaHttp(200, jsonEncode(coleta)),
        escrita: (_, __, ___) async => RespostaHttp(404, '{"detail":"Recurso não encontrado."}'),
      );

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Contestar coleta'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Confirmar contestação'));
      await tester.pumpAndSettle();

      expect(find.text('Coleta não encontrada.'), findsOneWidget);
    });

    testWidgets('tratamento 409 - estado mudou ou operação não pode ser realizada', (tester) async {
      final coleta = _coletaFinalizadaJson();
      final api = _apiCom(
        leitura: (_, __) async => RespostaHttp(200, jsonEncode(coleta)),
        escrita: (_, __, ___) async => RespostaHttp(409, '{"detail":"Transição inválida."}'),
      );

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Contestar coleta'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Confirmar contestação'));
      await tester.pumpAndSettle();

      expect(find.text('O estado da coleta mudou ou a operação não pode mais ser realizada.'), findsOneWidget);
    });

    testWidgets('tratamento 422 - erro de validação', (tester) async {
      final coleta = _coletaFinalizadaJson();
      final api = _apiCom(
        leitura: (_, __) async => RespostaHttp(200, jsonEncode(coleta)),
        escrita: (_, __, ___) async => RespostaHttp(422, '{"detail":"Erro de validação."}'),
      );

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Contestar coleta'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Confirmar contestação'));
      await tester.pumpAndSettle();

      expect(find.text('Erro de validação. Tente novamente.'), findsOneWidget);
    });

    testWidgets('erro de rede - mensagem genérica', (tester) async {
      final coleta = _coletaFinalizadaJson();
      final api = _apiCom(
        leitura: (_, __) async => RespostaHttp(200, jsonEncode(coleta)),
        escrita: (_, __, ___) async => throw Exception('sem conexao'),
      );

      await tester.pumpWidget(_envolver(
        TelaClienteResumoColeta(api: api, coleta: coleta),
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Contestar coleta'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Confirmar contestação'));
      await tester.pumpAndSettle();

      expect(find.text('Erro de conexão. Verifique sua internet e tente novamente.'), findsOneWidget);
    });

    testWidgets('tocar em coleta na TelaClienteMinhasColetas abre TelaClienteResumoColeta', (tester) async {
      final coleta = _coletaFinalizadaJson();
      final api = _apiCom(
        leitura: (caminho, __) async {
          if (caminho == '/api/v1/collections') {
            return RespostaHttp(200, jsonEncode([coleta]));
          }
          return RespostaHttp(200, jsonEncode(coleta));
        },
      );
      final outbox = OutboxService();

      await tester.pumpWidget(_envolver(
        TelaClienteMinhasColetas(api: api, outbox: outbox),
      ));
      await tester.pumpAndSettle();

      expect(find.text('COL-CLI-FIN'), findsOneWidget);
      await tester.tap(find.text('COL-CLI-FIN'));
      await tester.pumpAndSettle();

      expect(find.byType(TelaClienteResumoColeta), findsOneWidget);
      expect(find.text('Resumo: COL-CLI-FIN'), findsOneWidget);
    });
  });
}
