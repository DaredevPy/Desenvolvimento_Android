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
    String? Function()? obterToken,
  }) {
    return ApiService(enviar: enviar, obterToken: obterToken);
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
}
