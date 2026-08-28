import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/core/api/api_service.dart';
import 'package:meu_app_coleta_pneus/core/sessao/servico_sessao.dart';
import 'package:meu_app_coleta_pneus/prestador/tela_prestador_listar_pendentes.dart';

Map<String, dynamic> _coletaJson({
  String id = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
  String codigo = 'COL-TEST123',
}) {
  return {
    'id': id,
    'codigo_identificador': codigo,
    'status': 'SOLICITADA',
    'endereco_origem_json': {'rua': 'Rua Teste', 'numero': '123', 'bairro': 'Centro'},
    'data_agendada': '2026-09-01T12:00:00+00:00',
    'provider_id': null,
    'criado_em': '2026-08-20T10:00:00+00:00',
    'itens': [
      {'marca': 'Michelin', 'dimensao': '275/80R22.5', 'quantidade_declarada': 10, 'observacao': null},
    ],
  };
}

ApiService _apiCom({
  Future<RespostaHttp> Function(String, Map<String, String>)? listar,
  Future<RespostaHttp> Function(String, Map<String, String>, String)? aceitar,
}) {
  return ApiService(
    enviar: listar,
    enviarEscrita: aceitar,
    obterToken: () => 'jwt.teste',
  );
}

Widget _envolver(ApiService api) {
  return MaterialApp(
    home: TelaPrestadorListarPendentes(api: api),
  );
}

void main() {
  group('TelaPrestadorListarPendentes', () {
    testWidgets('exibe carregando e depois lista de coletas', (tester) async {
      final api = _apiCom(
        listar: (_, __) async =>
            RespostaHttp(200, jsonEncode([_coletaJson(), _coletaJson(id: 'bbbbbbbb-cccc-4ddd-8eee-ffffffffffff', codigo: 'COL-456')])),
      );
      await tester.pumpWidget(_envolver(api));

      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      await tester.pumpAndSettle();

      expect(find.text('COL-TEST123'), findsOneWidget);
      expect(find.text('COL-456'), findsOneWidget);
      expect(find.text('Aceitar coleta'), findsNWidgets(2));
    });

    testWidgets('lista vazia mostra mensagem e botão atualizar', (tester) async {
      final api = _apiCom(
        listar: (_, __) async => RespostaHttp(200, '[]'),
      );
      await tester.pumpWidget(_envolver(api));
      await tester.pumpAndSettle();

      expect(find.text('Nenhuma coleta disponível'), findsOneWidget);
      expect(find.text('Atualizar'), findsOneWidget);
    });

    testWidgets('erro de rede mostra mensagem e botão tentar novamente', (tester) async {
      final api = _apiCom(
        listar: (_, __) async => throw Exception('sem conexao'),
      );
      await tester.pumpWidget(_envolver(api));
      await tester.pumpAndSettle();

      expect(find.text('Erro de conexão. Tente novamente.'), findsOneWidget);
      expect(find.text('Tentar novamente'), findsOneWidget);
    });

    testWidgets('401 mostra mensagem de sessão expirada', (tester) async {
      final api = _apiCom(
        listar: (_, __) async => RespostaHttp(401, '{}'),
      );
      await tester.pumpWidget(_envolver(api));
      await tester.pumpAndSettle();

      expect(find.text('Sessão expirada. Faça login novamente.'), findsOneWidget);
    });

    testWidgets('403 mostra mensagem de acesso negado', (tester) async {
      final api = _apiCom(
        listar: (_, __) async => RespostaHttp(403, '{}'),
      );
      await tester.pumpWidget(_envolver(api));
      await tester.pumpAndSettle();

      expect(find.text('Acesso negado para este perfil.'), findsOneWidget);
    });

    testWidgets('aceitar com sucesso recarrega lista', (tester) async {
      var chamadasListar = 0;
      final api = _apiCom(
        listar: (_, __) async {
          chamadasListar++;
          if (chamadasListar == 1) {
            return RespostaHttp(200, jsonEncode([_coletaJson()]));
          }
          return RespostaHttp(200, '[]');
        },
        aceitar: (_, __, ___) async =>
            RespostaHttp(200, jsonEncode({'id': 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee', 'status': 'ACEITA', 'provider_id': 'p1'})),
      );
      await tester.pumpWidget(_envolver(api));
      await tester.pumpAndSettle();

      expect(find.text('Aceitar coleta'), findsOneWidget);

      await tester.tap(find.text('Aceitar coleta'));
      await tester.pumpAndSettle();

      expect(find.text('Coleta aceita com sucesso!'), findsOneWidget);
      expect(find.text('Nenhuma coleta disponível'), findsOneWidget);
    });

    testWidgets('coleta desaparece após aceite (lista recarrega)', (tester) async {
      var chamadasListar = 0;
      final api = _apiCom(
        listar: (_, __) async {
          chamadasListar++;
          if (chamadasListar == 1) {
            return RespostaHttp(200, jsonEncode([_coletaJson()]));
          }
          return RespostaHttp(200, '[]');
        },
        aceitar: (_, __, ___) async =>
            RespostaHttp(200, jsonEncode({'id': 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee', 'status': 'ACEITA', 'provider_id': 'p1'})),
      );
      await tester.pumpWidget(_envolver(api));
      await tester.pumpAndSettle();

      expect(find.text('COL-TEST123'), findsOneWidget);

      await tester.tap(find.text('Aceitar coleta'));
      await tester.pumpAndSettle();

      expect(find.text('COL-TEST123'), findsNothing);
      expect(find.text('Nenhuma coleta disponível'), findsOneWidget);
    });

    testWidgets('409 no aceite mostra conflito e recarrega', (tester) async {
      var chamadasListar = 0;
      final api = _apiCom(
        listar: (_, __) async {
          chamadasListar++;
          if (chamadasListar == 1) {
            return RespostaHttp(200, jsonEncode([_coletaJson()]));
          }
          return RespostaHttp(200, '[]');
        },
        aceitar: (_, __, ___) async =>
            RespostaHttp(409, '{"detail":"Coleta ja aceita."}'),
      );
      await tester.pumpWidget(_envolver(api));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Aceitar coleta'));
      await tester.pumpAndSettle();

      expect(find.text('Coleta já foi aceita por outro prestador.'), findsOneWidget);
      expect(find.text('Nenhuma coleta disponível'), findsOneWidget);
    });

    testWidgets('404 no aceite mostra mensagem e recarrega', (tester) async {
      var chamadasListar = 0;
      final api = _apiCom(
        listar: (_, __) async {
          chamadasListar++;
          if (chamadasListar == 1) {
            return RespostaHttp(200, jsonEncode([_coletaJson()]));
          }
          return RespostaHttp(200, '[]');
        },
        aceitar: (_, __, ___) async =>
            RespostaHttp(404, '{"detail":"Recurso nao encontrado."}'),
      );
      await tester.pumpWidget(_envolver(api));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Aceitar coleta'));
      await tester.pumpAndSettle();

      expect(find.text('Coleta ou perfil não encontrado.'), findsOneWidget);
    });

    testWidgets('botão atualizar na AppBar recarrega lista', (tester) async {
      var chamadasListar = 0;
      final api = _apiCom(
        listar: (_, __) async {
          chamadasListar++;
          return RespostaHttp(200, jsonEncode(chamadasListar == 1 ? [_coletaJson()] : []));
        },
      );
      await tester.pumpWidget(_envolver(api));
      await tester.pumpAndSettle();

      expect(find.text('COL-TEST123'), findsOneWidget);

      await tester.tap(find.byIcon(Icons.refresh));
      await tester.pumpAndSettle();

      expect(find.text('Nenhuma coleta disponível'), findsOneWidget);
    });

    testWidgets('botão tentar novamente na tela de erro recarrega', (tester) async {
      var chamadasListar = 0;
      final api = _apiCom(
        listar: (_, __) async {
          chamadasListar++;
          if (chamadasListar == 1) {
            return RespostaHttp(401, '{}');
          }
          return RespostaHttp(200, jsonEncode([_coletaJson()]));
        },
      );
      await tester.pumpWidget(_envolver(api));
      await tester.pumpAndSettle();

      expect(find.text('Sessão expirada. Faça login novamente.'), findsOneWidget);

      await tester.tap(find.text('Tentar novamente'));
      await tester.pumpAndSettle();

      expect(find.text('COL-TEST123'), findsOneWidget);
    });

    testWidgets('exibe endereço formatado da coleta', (tester) async {
      final api = _apiCom(
        listar: (_, __) async => RespostaHttp(200, jsonEncode([_coletaJson()])),
      );
      await tester.pumpWidget(_envolver(api));
      await tester.pumpAndSettle();

      expect(find.text('Rua Teste, 123, Centro'), findsOneWidget);
    });

    testWidgets('exibe quantidade de pneus e itens', (tester) async {
      final api = _apiCom(
        listar: (_, __) async => RespostaHttp(200, jsonEncode([_coletaJson()])),
      );
      await tester.pumpWidget(_envolver(api));
      await tester.pumpAndSettle();

      expect(find.text('10 pneu(s) · 1 item(ns)'), findsOneWidget);
    });
  });
}
