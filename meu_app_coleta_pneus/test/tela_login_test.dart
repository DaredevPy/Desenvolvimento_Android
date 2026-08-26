import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/core/sessao/servico_sessao.dart';
import 'package:meu_app_coleta_pneus/core/sessao/tela_login.dart';

class _ArmazenamentoMemoria implements ArmazenamentoSessao {
  String? _valor;

  @override
  Future<void> salvar(String token) async => _valor = token;

  @override
  Future<String?> ler() async => _valor;

  @override
  Future<void> remover() async => _valor = null;
}

ServicoSessao _sessaoCom(
  Future<RespostaHttp> Function(String, Map<String, String>, String) responder,
) {
  return ServicoSessao(
    armazenamento: _ArmazenamentoMemoria(),
    enviar: (c, h, b) => responder(c, h, b),
    baseUrl: 'https://api.teste',
  );
}

Widget _envolver(ServicoSessao sessao) {
  return MaterialApp(
    home: TelaLogin(servicoSessao: sessao),
  );
}

final _botaoEntrar = find.byWidgetPredicate(
  (w) => w is ElevatedButton && w.child is Text,
);

void main() {
  group('TelaLogin', () {
    testWidgets('exibe campos de e-mail, senha e botão Entrar', (tester) async {
      final sessao = _sessaoCom(
        (_, __, ___) async => const RespostaHttp(200, '{}'),
      );
      await tester.pumpWidget(_envolver(sessao));

      expect(find.byType(TextFormField), findsNWidgets(2));
      expect(find.text('E-mail'), findsOneWidget);
      expect(find.text('Senha'), findsOneWidget);
      expect(_botaoEntrar, findsOneWidget);
    });

    testWidgets('validação: campos vazios mostram erro', (tester) async {
      final sessao = _sessaoCom(
        (_, __, ___) async => const RespostaHttp(200, '{}'),
      );
      await tester.pumpWidget(_envolver(sessao));

      await tester.tap(_botaoEntrar);
      await tester.pumpAndSettle();

      expect(find.text('Informe o e-mail'), findsOneWidget);
      expect(find.text('Informe a senha'), findsOneWidget);
    });

    testWidgets('login válido navega para rota de sucesso', (tester) async {
      final sessao = _sessaoCom(
        (_, __, ___) async => RespostaHttp(
          200,
          jsonEncode({'access_token': 'jwt.ok', 'token_type': 'bearer'}),
        ),
      );
      await tester.pumpWidget(MaterialApp(
        initialRoute: '/login',
        routes: {
          '/login': (_) => TelaLogin(servicoSessao: sessao),
          '/principal': (_) => const Scaffold(body: Text('OK')),
        },
      ));

      await tester.enterText(find.byType(TextFormField).first, 'a@b.com');
      await tester.enterText(find.byType(TextFormField).last, 'senha');
      await tester.tap(_botaoEntrar);
      await tester.pumpAndSettle();

      expect(find.text('OK'), findsOneWidget);
      expect(sessao.tokenAtual, 'jwt.ok');
    });

    testWidgets('401 mostra credenciais inválidas', (tester) async {
      final sessao = _sessaoCom(
        (_, __, ___) async => const RespostaHttp(401, '{}'),
      );
      await tester.pumpWidget(_envolver(sessao));

      await tester.enterText(find.byType(TextFormField).first, 'x@y.com');
      await tester.enterText(find.byType(TextFormField).last, 'errada');
      await tester.tap(_botaoEntrar);
      await tester.pumpAndSettle();

      expect(find.text('E-mail ou senha inválidos.'), findsOneWidget);
      expect(sessao.tokenAtual, isNull);
    });

    testWidgets('erro de conexão mostra mensagem genérica', (tester) async {
      final sessao = _sessaoCom(
        (_, __, ___) async => throw Exception('fail'),
      );
      await tester.pumpWidget(_envolver(sessao));

      await tester.enterText(find.byType(TextFormField).first, 'a@b.com');
      await tester.enterText(find.byType(TextFormField).last, 'senha');
      await tester.tap(_botaoEntrar);
      await tester.pumpAndSettle();

      expect(find.text('Erro de conexão. Tente novamente.'), findsOneWidget);
      expect(sessao.tokenAtual, isNull);
    });

    testWidgets('estado de carregamento aparece durante login', (tester) async {
      var completar = Completer<void>();
      final sessao = _sessaoCom((_, __, ___) async {
        await completar.future;
        return RespostaHttp(
          200,
          jsonEncode({'access_token': 'jwt.ok', 'token_type': 'bearer'}),
        );
      });
      await tester.pumpWidget(_envolver(sessao));

      await tester.enterText(find.byType(TextFormField).first, 'a@b.com');
      await tester.enterText(find.byType(TextFormField).last, 'senha');
      await tester.tap(_botaoEntrar);
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      completar.complete();
      await tester.pumpAndSettle();
    });
  });
}
