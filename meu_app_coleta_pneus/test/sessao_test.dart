import 'dart:async';
import 'dart:convert';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/core/outbox/operacao_pendente.dart';
import 'package:meu_app_coleta_pneus/core/outbox/outbox_service.dart';
import 'package:meu_app_coleta_pneus/core/outbox/sincronizacao_automatica_outbox.dart';
import 'package:meu_app_coleta_pneus/core/sessao/servico_sessao.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Armazenamento em memória substitui flutter_secure_storage nos testes.
class _ArmazenamentoMemoria implements ArmazenamentoSessao {
  String? _valor;

  @override
  Future<void> salvar(String token) async => _valor = token;

  @override
  Future<String?> ler() async => _valor;

  @override
  Future<void> remover() async => _valor = null;
}

/// Sessão do Flutter e integração com o Outbox (Missão 19 / docs 05 §1,
/// 08 §2 e 09 §2). O transporte HTTP é injetado e espelha EXATAMENTE os
/// contratos reais do backend: POST /api/v1/auth/login -> 200
/// {"access_token","token_type"} | 401 credenciais inválidas.
void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  ServicoSessao sessaoCom(
    RespostaHttp Function(String caminho, Map<String, String> cabecalhos,
            String corpo)
        responder, {
    ArmazenamentoSessao? armazenamento,
  }) {
    return ServicoSessao(
      armazenamento: armazenamento ?? _ArmazenamentoMemoria(),
      enviar: (caminho, cabecalhos, corpo) async =>
          responder(caminho, cabecalhos, corpo),
      baseUrl: 'https://api.teste',
    );
  }

  RespostaHttp loginOk(String token) => RespostaHttp(
      200, jsonEncode({'access_token': token, 'token_type': 'bearer'}));

  group('ServicoSessao - contratos de /api/v1/auth', () {
    test('login válido guarda o access_token em memória e no armazenamento',
        () async {
      final armazem = _ArmazenamentoMemoria();
      final pedidos = <Map<String, Object>>[];
      final sessao = sessaoCom(
        (caminho, cabecalhos, corpo) {
          pedidos.add({
            'caminho': caminho,
            'cabecalhos': cabecalhos,
            'corpo': corpo,
          });
          return loginOk('jwt.valido.abc');
        },
        armazenamento: armazem,
      );

      await sessao.entrar(
          email: 'prestador@teste.com', senha: 'senha-secreta');

      expect(sessao.tokenAtual, 'jwt.valido.abc');
      expect(await armazem.ler(), 'jwt.valido.abc');

      final pedido = pedidos.single;
      expect(pedido['caminho'], '/api/v1/auth/login');
      expect(
        jsonDecode(pedido['corpo'] as String),
        {'email': 'prestador@teste.com', 'senha': 'senha-secreta'},
      );
      expect(
        (pedido['cabecalhos'] as Map)['Content-Type'],
        contains('application/json'),
      );
      expect(await armazem.ler(), isNot(contains('senha-secreta')));
    });

    test('credenciais inválidas (401): exceção tipada e NADA é salvo',
        () async {
      final armazem = _ArmazenamentoMemoria();
      final sessao = sessaoCom(
        (caminho, cabecalhos, corpo) => const RespostaHttp(
          401,
          '{"detail":"Credenciais inválidas."}',
        ),
        armazenamento: armazem,
      );

      await expectLater(
        sessao.entrar(email: 'errado@teste.com', senha: 'errada'),
        throwsA(isA<CredenciaisInvalidasExcecao>()),
      );

      expect(sessao.tokenAtual, isNull);
      expect(await armazem.ler(), isNull);
    });

    test('falha de servidor (500): nada é salvo', () async {
      final sessao = sessaoCom(
        (caminho, cabecalhos, corpo) => const RespostaHttp(500, '{}'),
      );

      await expectLater(
        sessao.entrar(email: 'x@y.com', senha: 'z'),
        throwsA(isA<Exception>()),
      );
      expect(sessao.tokenAtual, isNull);
    });

    test('sessão é persistente: nova instância restaura o token', () async {
      final armazem = _ArmazenamentoMemoria();
      final primeira = sessaoCom(
        (caminho, cabecalhos, corpo) => loginOk('jwt.persistente'),
        armazenamento: armazem,
      );
      await primeira.entrar(email: 'a@b.com', senha: 's');

      final segunda = ServicoSessao(armazenamento: armazem);
      await segunda.carregar();

      expect(segunda.tokenAtual, 'jwt.persistente');
    });

    test('logout remove a sessão da memória e do armazenamento', () async {
      final armazem = _ArmazenamentoMemoria();
      final sessao = sessaoCom(
        (caminho, cabecalhos, corpo) => loginOk('jwt.para.logout'),
        armazenamento: armazem,
      );
      await sessao.entrar(email: 'a@b.com', senha: 's');

      await sessao.sair();

      expect(sessao.tokenAtual, isNull);
      expect(await armazem.ler(), isNull);
    });
  });

  group('Sessão x Outbox (docs 09 §§2/4)', () {
    test('token da sessão vai como Authorization Bearer em cada envio',
        () async {
      final sessao = sessaoCom(
        (caminho, cabecalhos, corpo) => loginOk('.jwt.outbox.'),
      );
      await sessao.entrar(email: 'p@teste.com', senha: 's');

      final cabecalhosCapturados = <Map<String, String>>[];
      final outbox = OutboxService(
        obterToken: () => sessao.tokenAtual,
        enviar: (caminho, cabecalhos, corpo) async {
          cabecalhosCapturados.add(cabecalhos);
          return 201;
        },
      );
      await outbox.agendarCriacaoDeColeta(
        enderecoOrigemJson: const {'cidade': 'São Paulo'},
        dataAgendada: DateTime.utc(2026, 9, 1, 12),
        itens: [
          const {
            'marca': 'Marca X',
            'dimensao': '205/55R16',
            'quantidade_declarada': 1,
          },
        ],
      );
      await outbox.sincronizarPendentes();

      expect(cabecalhosCapturados, hasLength(1));
      expect(cabecalhosCapturados.single['Authorization'],
          'Bearer .jwt.outbox.');
      expect(await outbox.pendentes(), isEmpty);
    });

    test('token expirado (401) NÃO apaga a operação; logout também não',
        () async {
      final sessao = sessaoCom(
        (caminho, cabecalhos, corpo) => loginOk('jwt.expirado'),
      );
      await sessao.entrar(email: 'p@teste.com', senha: 's');

      final autorizacoes = <String?>[];
      final outbox = OutboxService(
        obterToken: () => sessao.tokenAtual,
        enviar: (caminho, cabecalhos, corpo) async {
          autorizacoes.add(cabecalhos['Authorization']);
          return 401;
        },
      );
      await outbox.agendarFinalizacaoColeta(
        coletaId: '22222222-2222-4222-8222-222222222222',
      );

      await outbox.sincronizarPendentes();
      var fila = await outbox.pendentes();
      expect(fila, hasLength(1));
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
      expect(fila.single.tentativas, 1);

      await sessao.sair();
      await outbox.sincronizarPendentes();

      fila = await outbox.pendentes();
      expect(fila, hasLength(1));
      expect(fila.single.status, StatusOperacaoOutbox.pendente);
      expect(fila.single.tentativas, 2);
      expect(autorizacoes, ['Bearer jwt.expirado', null]);
    });

    test('reconexão sincroniza AUTENTICADO: mesma chave antes/depois do '
        'login, sem duplicar a operação', () async {
      TestWidgetsFlutterBinding.ensureInitialized();

      final conectividade =
          StreamController<List<ConnectivityResult>>.broadcast();
      addTearDown(conectividade.close);

      final chaves = <String?>[];
      var autenticado = false;

      final sessao = sessaoCom(
        (caminho, cabecalhos, corpo) => loginOk('jwt.novo.pos.login'),
      );
      final outbox = OutboxService(
        obterToken: () => sessao.tokenAtual,
        enviar: (caminho, cabecalhos, corpo) async {
          chaves.add(cabecalhos['X-Idempotency-Key']);
          if (!autenticado || !cabecalhos.containsKey('Authorization')) {
            return 401;
          }
          return 201;
        },
      );

      await outbox.agendarRegistroPneus(
        coletaId: '22222222-2222-4222-8222-222222222222',
        pneus: const [
          {
            'marca': 'Marca X',
            'medida': '205/55R16',
            'dot': '1224',
            'numero_fogo': 'NF123',
          },
        ],
      );

      final disparo = SincronizacaoAutomaticaOutbox(
        outbox: outbox,
        conectividade: conectividade.stream,
      );
      disparo.iniciar();
      addTearDown(disparo.descartar);
      await _flushMicrotasks();
      expect(await outbox.pendentes(), hasLength(1));

      await sessao.entrar(email: 'p@teste.com', senha: 's');
      autenticado = true;
      conectividade.add([ConnectivityResult.wifi]);
      await _flushMicrotasks();

      final fila = await outbox.pendentes();
      expect(fila, isEmpty,
          reason: 'retry autenticado confirmou a operação');
      expect(chaves, hasLength(2));
      expect(chaves.first, chaves.last,
          reason: 'idempotência intacta: MESMA chave nas duas tentativas');
    });
  });
}

Future<void> _flushMicrotasks() async {
  for (var i = 0; i < 8; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}
