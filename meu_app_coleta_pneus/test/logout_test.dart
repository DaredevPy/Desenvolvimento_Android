import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/core/outbox/outbox_service.dart';
import 'package:meu_app_coleta_pneus/core/sessao/servico_sessao.dart';
import 'package:meu_app_coleta_pneus/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _ArmazenamentoMemoria implements ArmazenamentoSessao {
  String? _valor;

  @override
  Future<void> salvar(String token) async => _valor = token;

  @override
  Future<String?> ler() async => _valor;

  @override
  Future<void> remover() async => _valor = null;
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('Logout', () {
    testWidgets('botão de logout existe na AppBar', (tester) async {
      final armazem = _ArmazenamentoMemoria();
      final sessao = ServicoSessao(
        armazenamento: armazem,
        enviar: (_, __, ___) async => RespostaHttp(
          200,
          jsonEncode({'access_token': 'jwt.ok', 'token_type': 'bearer'}),
        ),
        baseUrl: 'https://api.teste',
      );
      await sessao.entrar(email: 'a@b.com', senha: 's');

      await tester.pumpWidget(MaterialApp(
        home: TelaPrincipal(sessao: sessao),
      ));

      expect(find.byIcon(Icons.logout), findsOneWidget);
    });

    testWidgets('tap no logout chama sair() e limpa token', (tester) async {
      final armazem = _ArmazenamentoMemoria();
      final sessao = ServicoSessao(
        armazenamento: armazem,
        enviar: (_, __, ___) async => RespostaHttp(
          200,
          jsonEncode({'access_token': 'jwt.ok', 'token_type': 'bearer'}),
        ),
        baseUrl: 'https://api.teste',
      );
      await sessao.entrar(email: 'a@b.com', senha: 's');
      expect(sessao.tokenAtual, isNotNull);

      await tester.pumpWidget(MaterialApp(
        routes: {
          '/login': (_) => const Scaffold(body: Text('LOGIN')),
          '/principal': (_) => TelaPrincipal(sessao: sessao),
        },
        home: TelaPrincipal(sessao: sessao),
      ));

      await tester.tap(find.byIcon(Icons.logout));
      await tester.pumpAndSettle();

      expect(sessao.tokenAtual, isNull);
      expect(await armazem.ler(), isNull);
    });

    testWidgets('após logout navega para /login', (tester) async {
      final armazem = _ArmazenamentoMemoria();
      final sessao = ServicoSessao(
        armazenamento: armazem,
        enviar: (_, __, ___) async => RespostaHttp(
          200,
          jsonEncode({'access_token': 'jwt.ok', 'token_type': 'bearer'}),
        ),
        baseUrl: 'https://api.teste',
      );
      await sessao.entrar(email: 'a@b.com', senha: 's');

      await tester.pumpWidget(MaterialApp(
        routes: {
          '/login': (_) => const Scaffold(body: Text('LOGIN')),
          '/principal': (_) => TelaPrincipal(sessao: sessao),
        },
        home: TelaPrincipal(sessao: sessao),
      ));

      await tester.tap(find.byIcon(Icons.logout));
      await tester.pumpAndSettle();

      expect(find.text('LOGIN'), findsOneWidget);
    });

    testWidgets('outbox pendente permanece intacto após logout', (tester) async {
      final armazem = _ArmazenamentoMemoria();
      final sessao = ServicoSessao(
        armazenamento: armazem,
        enviar: (_, __, ___) async => RespostaHttp(
          200,
          jsonEncode({'access_token': 'jwt.ok', 'token_type': 'bearer'}),
        ),
        baseUrl: 'https://api.teste',
      );
      await sessao.entrar(email: 'a@b.com', senha: 's');

      final outbox = OutboxService(
        enviar: (_, __, ___) async => 201,
        obterToken: () => sessao.tokenAtual,
      );
      await outbox.agendarCriacaoDeColeta(
        enderecoOrigemJson: const {'cidade': 'SP'},
        dataAgendada: DateTime.utc(2026, 10, 1),
        itens: const [
          {'marca': 'X', 'dimensao': '205/55R16', 'quantidade_declarada': 1},
        ],
      );
      final pendentes = await outbox.pendentes();
      expect(pendentes, hasLength(1));

      await tester.pumpWidget(MaterialApp(
        routes: {
          '/login': (_) => const Scaffold(body: Text('LOGIN')),
          '/principal': (_) => TelaPrincipal(sessao: sessao),
        },
        home: TelaPrincipal(sessao: sessao),
      ));

      await tester.tap(find.byIcon(Icons.logout));
      await tester.pumpAndSettle();

      final pendentesApos = await outbox.pendentes();
      expect(pendentesApos, hasLength(1));
    });

    testWidgets('token antigo não é reutilizado após logout', (tester) async {
      final armazem = _ArmazenamentoMemoria();
      final sessao = ServicoSessao(
        armazenamento: armazem,
        enviar: (_, __, ___) async => RespostaHttp(
          200,
          jsonEncode({'access_token': 'jwt.ok', 'token_type': 'bearer'}),
        ),
        baseUrl: 'https://api.teste',
      );
      await sessao.entrar(email: 'a@b.com', senha: 's');
      final tokenAntigo = sessao.tokenAtual;

      await tester.pumpWidget(MaterialApp(
        routes: {
          '/login': (_) => const Scaffold(body: Text('LOGIN')),
          '/principal': (_) => TelaPrincipal(sessao: sessao),
        },
        home: TelaPrincipal(sessao: sessao),
      ));

      await tester.tap(find.byIcon(Icons.logout));
      await tester.pumpAndSettle();

      expect(sessao.tokenAtual, isNull);
      expect(sessao.tokenAtual, isNot(tokenAntigo));
    });
  });
}
