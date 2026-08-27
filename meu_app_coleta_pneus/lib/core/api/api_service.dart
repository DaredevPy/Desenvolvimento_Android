import 'dart:convert';

import 'package:http/http.dart' as http;

import '../sessao/servico_sessao.dart';

/// Função de transporte para chamadas de leitura (GET). Retorna código e
/// corpo da resposta. Injetável para testes.
typedef EnviarLeitura = Future<RespostaHttp> Function(
  String caminho,
  Map<String, String> cabecalhos,
);

/// Cliente HTTP para operações de leitura no backend FastAPI.
///
/// Fornece métodos para consultar coletas via GET. Cada chamada inclui
/// automaticamente o token de sessão no cabeçalho Authorization.
///
/// Transporte HTTP injetável para testes sem servidor real.
class ApiService {
  ApiService({
    EnviarLeitura? enviar,
    String baseUrl = '',
    String? Function()? obterToken,
  })  : _enviar = enviar,
        _baseUrl = baseUrl,
        _obterToken = obterToken;

  final EnviarLeitura? _enviar;
  final String _baseUrl;
  final String? Function()? _obterToken;

  /// Lista coletas do usuário autenticado.
  ///
  /// CLIENTE: retorna suas próprias coletas.
  /// PRESTADOR: retorna coletas atribuídas.
  Future<List<Map<String, dynamic>>> listarMinhasColetas() async {
    final resposta = await _get('/api/v1/collections');
    return (jsonDecode(resposta.corpo) as List<dynamic>)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }

  /// Obtém uma coleta específica por ID (somente CLIENTE).
  ///
  /// Retorna 404 se a coleta não existir ou pertencer a outro cliente.
  Future<Map<String, dynamic>> obterColeta(String coletaId) async {
    final resposta = await _get('/api/v1/collections/$coletaId');
    return Map<String, dynamic>.from(
      jsonDecode(resposta.corpo) as Map,
    );
  }

  /// Lista coletas disponíveis para aceite (somente PRESTADOR).
  ///
  /// Retorna coletas com status SOLICITADA e sem prestador atribuído.
  Future<List<Map<String, dynamic>>> listarDisponiveis() async {
    final resposta = await _get('/api/v1/collections/disponiveis');
    return (jsonDecode(resposta.corpo) as List<dynamic>)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }

  Future<RespostaHttp> _get(String caminho) async {
    final cabecalhos = <String, String>{
      'Content-Type': 'application/json',
    };
    final token = _obterToken?.call();
    if (token != null && token.isNotEmpty) {
      cabecalhos['Authorization'] = 'Bearer $token';
    }
    final enviar = _enviar;
    final resposta = enviar != null
        ? await enviar(caminho, cabecalhos)
        : await _getViaHttp(caminho, cabecalhos);
    if (resposta.codigo != 200) {
      throw Exception('Erro HTTP ${resposta.codigo}');
    }
    return resposta;
  }

  Future<RespostaHttp> _getViaHttp(
    String caminho,
    Map<String, String> cabecalhos,
  ) async {
    final resposta = await http.get(
      Uri.parse('$_baseUrl$caminho'),
      headers: cabecalhos,
    );
    return RespostaHttp(resposta.statusCode, resposta.body);
  }
}
