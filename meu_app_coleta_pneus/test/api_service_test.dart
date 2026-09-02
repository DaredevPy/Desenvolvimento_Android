import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/core/api/api_service.dart';
import 'package:meu_app_coleta_pneus/core/sessao/servico_sessao.dart';

/// Testes unitários do ApiService (Missão 24).
///
/// Transporte HTTP injetado (sem servidor real).
void main() {
  ApiService servicoCom(
    Future<RespostaHttp> Function(
      String caminho,
      Map<String, String> cabecalhos,
    )?
    enviar, {
    Future<RespostaHttp> Function(
      String caminho,
      Map<String, String> cabecalhos,
      String corpo,
    )?
    enviarEscrita,
    String? Function()? obterToken,
  }) {
    return ApiService(
      enviar: enviar,
      enviarEscrita: enviarEscrita,
      obterToken: obterToken,
    );
  }

  Map<String, dynamic> coletaJson({String id = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'}) {
    return {
      'id': id,
      'codigo_identificador': 'COL-TEST123',
      'status': 'SOLICITADA',
      'endereco_origem_json': {'logradouro': 'Rua Teste', 'numero': '123'},
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

  group('ApiService - listarMinhasColetas', () {
    test('sucesso (200) retorna lista de coletas', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async {
          expect(caminho, '/api/v1/collections');
          return RespostaHttp(200, jsonEncode([coletaJson()]));
        },
      );

      final coletas = await servico.listarMinhasColetas();

      expect(coletas, hasLength(1));
      expect(coletas.first['id'], 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee');
      expect(coletas.first['status'], 'SOLICITADA');
    });

    test('sucesso (200) com lista vazia', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
      );

      final coletas = await servico.listarMinhasColetas();

      expect(coletas, isEmpty);
    });

    test('401 lança exceção', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(401, '{"detail":"Token inválido."}'),
      );

      expect(() => servico.listarMinhasColetas(), throwsA(isA<Exception>()));
    });

    test('erro de rede lança exceção', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => throw Exception('sem conexao'),
      );

      expect(() => servico.listarMinhasColetas(), throwsA(isA<Exception>()));
    });

    test('envia Authorization Bearer quando token disponível', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async {
          expect(cabecalhos['Authorization'], 'Bearer jwt.teste');
          return RespostaHttp(200, '[]');
        },
        obterToken: () => 'jwt.teste',
      );

      await servico.listarMinhasColetas();
    });

    test('não envia Authorization quando token é null', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async {
          expect(cabecalhos.containsKey('Authorization'), isFalse);
          return RespostaHttp(200, '[]');
        },
        obterToken: () => null,
      );

      await servico.listarMinhasColetas();
    });
  });

  group('ApiService - obterColeta', () {
    test('sucesso (200) retorna coleta por ID', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async {
          expect(caminho, '/api/v1/collections/11111111-2222-4333-8444-555555555555');
          return RespostaHttp(200, jsonEncode(coletaJson(id: '11111111-2222-4333-8444-555555555555')));
        },
      );

      final coleta = await servico.obterColeta('11111111-2222-4333-8444-555555555555');

      expect(coleta['id'], '11111111-2222-4333-8444-555555555555');
      expect(coleta['itens'], isA<List>());
    });

    test('404 lança exceção (coleta não encontrada)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(404, '{"detail":"Recurso não encontrado."}'),
      );

      expect(() => servico.obterColeta(' nonexistent-id '), throwsA(isA<Exception>()));
    });
  });

  group('ApiService - listarDisponiveis', () {
    test('sucesso (200) retorna coletas disponíveis', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async {
          expect(caminho, '/api/v1/collections/disponiveis');
          return RespostaHttp(200, jsonEncode([coletaJson(), coletaJson(id: 'aaaaaaaa-bbbb-4ccc-8ddd-ffffffffffff')]));
        },
      );

      final coletas = await servico.listarDisponiveis();

      expect(coletas, hasLength(2));
    });

    test('sucesso (200) com lista vazia', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
      );

      final coletas = await servico.listarDisponiveis();

      expect(coletas, isEmpty);
    });

    test('403 lança exceção (prestador não autorizado)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(403, '{"detail":"Acesso negado."}'),
      );

      expect(() => servico.listarDisponiveis(), throwsA(isA<Exception>()));
    });
  });

  group('ApiService - aceitar', () {
    test('sucesso (200) retorna coleta aceita', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async {
          expect(caminho, '/api/v1/collections/11111111-2222-4333-8444-555555555555/aceitar');
          expect(corpo, isEmpty);
          return RespostaHttp(200, jsonEncode({
            'id': '11111111-2222-4333-8444-555555555555',
            'status': 'ACEITA',
            'provider_id': 'pppppppp-pppp-4ppp-8ppp-pppppppppppp',
          }));
        },
      );

      final resultado = await servico.aceitar('11111111-2222-4333-8444-555555555555');

      expect(resultado['id'], '11111111-2222-4333-8444-555555555555');
      expect(resultado['status'], 'ACEITA');
      expect(resultado['provider_id'], 'pppppppp-pppp-4ppp-8ppp-pppppppppppp');
    });

    test('409 lança exceção (coleta já aceita por outro)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(409, '{"detail":"Coleta nao esta mais disponivel para aceite."}'),
      );

      expect(() => servico.aceitar('11111111-2222-4333-8444-555555555555'), throwsA(isA<Exception>()));
    });

    test('404 lança exceção (coleta não encontrada)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(404, '{"detail":"Recurso nao encontrado."}'),
      );

      expect(() => servico.aceitar('nonexistent-id'), throwsA(isA<Exception>()));
    });

    test('401 lança exceção (token inválido)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(401, '{"detail":"Nao autenticado."}'),
      );

      expect(() => servico.aceitar('11111111-2222-4333-8444-555555555555'), throwsA(isA<Exception>()));
    });

    test('403 lança exceção (perfil errado)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(403, '{"detail":"Acesso negado para este perfil."}'),
      );

      expect(() => servico.aceitar('11111111-2222-4333-8444-555555555555'), throwsA(isA<Exception>()));
    });

    test('erro de rede lança exceção', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            throw Exception('sem conexao'),
      );

      expect(() => servico.aceitar('11111111-2222-4333-8444-555555555555'), throwsA(isA<Exception>()));
    });

    test('envia Authorization Bearer quando token disponível', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async {
          expect(cabecalhos['Authorization'], 'Bearer jwt.teste');
          return RespostaHttp(200, jsonEncode({'id': 'x', 'status': 'ACEITA', 'provider_id': 'y'}));
        },
        obterToken: () => 'jwt.teste',
      );

      await servico.aceitar('x');
    });

    test('não envia Authorization quando token é null', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async {
          expect(cabecalhos.containsKey('Authorization'), isFalse);
          return RespostaHttp(200, jsonEncode({'id': 'x', 'status': 'ACEITA', 'provider_id': 'y'}));
        },
        obterToken: () => null,
      );

      await servico.aceitar('x');
    });
  });

  group('ApiService - avancarStatus', () {
    test('sucesso (200) avança para EM_DESLOCAMENTO', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async {
          expect(caminho, '/api/v1/collections/11111111-2222-4333-8444-555555555555/status');
          expect(corpo, jsonEncode({'novo_status': 'EM_DESLOCAMENTO'}));
          return RespostaHttp(200, jsonEncode({
            'id': '11111111-2222-4333-8444-555555555555',
            'status': 'EM_DESLOCAMENTO',
          }));
        },
      );

      final resultado = await servico.avancarStatus(
        '11111111-2222-4333-8444-555555555555',
        'EM_DESLOCAMENTO',
      );

      expect(resultado['id'], '11111111-2222-4333-8444-555555555555');
      expect(resultado['status'], 'EM_DESLOCAMENTO');
    });

    test('409 lança exceção (transição inválida)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(409, '{"detail":"Transição inválida a partir de ACEITA."}'),
      );

      expect(
        () => servico.avancarStatus('11111111-2222-4333-8444-555555555555', 'EM_DESLOCAMENTO'),
        throwsA(isA<Exception>()),
      );
    });

    test('404 lança exceção (coleta não encontrada)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(404, '{"detail":"Recurso não encontrado."}'),
      );

      expect(
        () => servico.avancarStatus('nonexistent', 'EM_DESLOCAMENTO'),
        throwsA(isA<Exception>()),
      );
    });

    test('401 lança exceção (token inválido)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(401, '{"detail":"Nao autenticado."}'),
      );

      expect(
        () => servico.avancarStatus('11111111-2222-4333-8444-555555555555', 'EM_DESLOCAMENTO'),
        throwsA(isA<Exception>()),
      );
    });

    test('403 lança exceção (perfil errado)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(403, '{"detail":"Acesso negado para este perfil."}'),
      );

      expect(
        () => servico.avancarStatus('11111111-2222-4333-8444-555555555555', 'EM_DESLOCAMENTO'),
        throwsA(isA<Exception>()),
      );
    });

    test('erro de rede lança exceção', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            throw Exception('sem conexao'),
      );

      expect(
        () => servico.avancarStatus('11111111-2222-4333-8444-555555555555', 'EM_DESLOCAMENTO'),
        throwsA(isA<Exception>()),
      );
    });

    test('envia Authorization Bearer quando token disponível', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async {
          expect(cabecalhos['Authorization'], 'Bearer jwt.teste');
          return RespostaHttp(200, jsonEncode({'id': 'x', 'status': 'EM_DESLOCAMENTO'}));
        },
        obterToken: () => 'jwt.teste',
      );

      await servico.avancarStatus('x', 'EM_DESLOCAMENTO');
    });

    test('não envia Authorization quando token é null', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async {
          expect(cabecalhos.containsKey('Authorization'), isFalse);
          return RespostaHttp(200, jsonEncode({'id': 'x', 'status': 'EM_DESLOCAMENTO'}));
        },
        obterToken: () => null,
      );

      await servico.avancarStatus('x', 'EM_DESLOCAMENTO');
    });
  });

  group('ApiService - contestarColeta', () {
    test('sucesso (200) retorna coleta contestada', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async {
          expect(caminho, '/api/v1/collections/11111111-2222-4333-8444-555555555555/contestar');
          expect(corpo, '{}');
          return RespostaHttp(200, jsonEncode({
            'id': '11111111-2222-4333-8444-555555555555',
            'status': 'CONTESTADA',
          }));
        },
      );

      final resultado = await servico.contestarColeta('11111111-2222-4333-8444-555555555555');

      expect(resultado['id'], '11111111-2222-4333-8444-555555555555');
      expect(resultado['status'], 'CONTESTADA');
    });

    test('403 lança exceção (não permitido)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(403, '{"detail":"Acesso negado."}'),
      );

      expect(() => servico.contestarColeta('11111111-2222-4333-8444-555555555555'), throwsA(isA<Exception>()));
    });

    test('404 lança exceção (coleta não encontrada)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(404, '{"detail":"Recurso não encontrado."}'),
      );

      expect(() => servico.contestarColeta('nonexistent-id'), throwsA(isA<Exception>()));
    });

    test('409 lança exceção (estado mudou)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(409, '{"detail":"Transição inválida a partir de CARREGADA."}'),
      );

      expect(() => servico.contestarColeta('11111111-2222-4333-8444-555555555555'), throwsA(isA<Exception>()));
    });

    test('422 lança exceção (validação)', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            RespostaHttp(422, '{"detail":"Erro de validação."}'),
      );

      expect(() => servico.contestarColeta('11111111-2222-4333-8444-555555555555'), throwsA(isA<Exception>()));
    });

    test('erro de rede lança exceção', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async =>
            throw Exception('sem conexao'),
      );

      expect(() => servico.contestarColeta('11111111-2222-4333-8444-555555555555'), throwsA(isA<Exception>()));
    });

    test('envia Authorization Bearer quando token disponível', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async {
          expect(cabecalhos['Authorization'], 'Bearer jwt.teste');
          return RespostaHttp(200, jsonEncode({'id': 'x', 'status': 'CONTESTADA'}));
        },
        obterToken: () => 'jwt.teste',
      );

      await servico.contestarColeta('x');
    });

    test('não envia Authorization quando token é null', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async {
          expect(cabecalhos.containsKey('Authorization'), isFalse);
          return RespostaHttp(200, jsonEncode({'id': 'x', 'status': 'CONTESTADA'}));
        },
        obterToken: () => null,
      );

      await servico.contestarColeta('x');
    });

    test('não envia X-Idempotency-Key', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async {
          expect(cabecalhos.containsKey('X-Idempotency-Key'), isFalse);
          return RespostaHttp(200, jsonEncode({'id': 'x', 'status': 'CONTESTADA'}));
        },
      );

      await servico.contestarColeta('x');
    });

    test('não envia valores financeiros', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async {
          final json = jsonDecode(corpo) as Map<String, dynamic>;
          expect(json.containsKey('valor'), isFalse);
          expect(json.containsKey('snapshot_valor_cliente'), isFalse);
          expect(json.containsKey('snapshot_valor_prestador'), isFalse);
          return RespostaHttp(200, jsonEncode({'id': 'x', 'status': 'CONTESTADA'}));
        },
      );

      await servico.contestarColeta('x');
    });

    test('não envia pneus', () async {
      final servico = servicoCom(
        (caminho, cabecalhos) async => RespostaHttp(200, '[]'),
        enviarEscrita: (caminho, cabecalhos, corpo) async {
          final json = jsonDecode(corpo) as Map<String, dynamic>;
          expect(json.containsKey('pneus'), isFalse);
          return RespostaHttp(200, jsonEncode({'id': 'x', 'status': 'CONTESTADA'}));
        },
      );

      await servico.contestarColeta('x');
    });
  });
}
