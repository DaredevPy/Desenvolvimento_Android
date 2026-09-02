import 'dart:convert';

import 'package:http/http.dart' as http;

import '../sessao/servico_sessao.dart';

/// Função de transporte para chamadas de leitura (GET). Retorna código e
/// corpo da resposta. Injetável para testes.
typedef EnviarLeitura = Future<RespostaHttp> Function(
  String caminho,
  Map<String, String> cabecalhos,
);

/// Função de transporte para chamadas de escrita (POST). Retorna código e
/// corpo da resposta. Injetável para testes.
typedef EnviarEscrita = Future<RespostaHttp> Function(
  String caminho,
  Map<String, String> cabecalhos,
  String corpo,
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
    EnviarEscrita? enviarEscrita,
    String baseUrl = '',
    String? Function()? obterToken,
  })  : _enviar = enviar,
        _enviarEscrita = enviarEscrita,
        _baseUrl = baseUrl,
        _obterToken = obterToken;

  final EnviarLeitura? _enviar;
  final EnviarEscrita? _enviarEscrita;
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

  /// Aceita uma coleta disponível (somente PRESTADOR).
  ///
  /// Operação transacional: o backend executa um UPDATE atômico com condições
  /// de concorrência. Retorna 409 se já foi aceita por outro prestador.
  ///
  /// Retorna mapa com {id, status, provider_id}.
  Future<Map<String, dynamic>> aceitar(String coletaId) async {
    final resposta = await _post('/api/v1/collections/$coletaId/aceitar', '');
    return Map<String, dynamic>.from(
      jsonDecode(resposta.corpo) as Map,
    );
  }

  /// Avança o status de uma coleta (somente PRESTADOR).
  ///
  /// Transições suportadas pelo backend:
  /// - ACEITA → EM_DESLOCAMENTO
  /// - EM_DESLOCAMENTO → EM_CONFERENCIA
  /// - EM_CONFERENCIA → CARREGADA
  ///
  /// Retorna mapa com {id, status}.
  Future<Map<String, dynamic>> avancarStatus(
    String coletaId,
    String novoStatus,
  ) async {
    final corpo = jsonEncode({'novo_status': novoStatus});
    final resposta = await _postComBody(
      '/api/v1/collections/$coletaId/status',
      corpo,
    );
    return Map<String, dynamic>.from(
      jsonDecode(resposta.corpo) as Map,
    );
  }

  /// Lista pneus já registrados na conferência (somente PRESTADOR).
  ///
  /// Retorna lista de pneus com dot, numero_fogo, idade, alerta, marca, medida.
  Future<List<Map<String, dynamic>>> listarPneusConferencia(
    String coletaId,
  ) async {
    final resposta = await _get(
      '/api/v1/collections/$coletaId/conferencia/pneus',
    );
    return (jsonDecode(resposta.corpo) as List<dynamic>)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }

  /// Inicia a conferência de uma coleta (somente PRESTADOR).
  ///
  /// Transição: EM_DESLOCAMENTO → EM_CONFERENCIA.
  /// Retorna {id, status, itens_declarados}.
  Future<Map<String, dynamic>> iniciarConferencia(String coletaId) async {
    final resposta = await _post(
      '/api/v1/collections/$coletaId/conferencia/iniciar',
      '',
    );
    return Map<String, dynamic>.from(
      jsonDecode(resposta.corpo) as Map,
    );
  }

  /// Contesta uma coleta FINALIZADA (somente CLIENTE dono da coleta).
  ///
  /// Transição: FINALIZADA → CONTESTADA.
  /// Corpo vazio estrito: {}.
  /// Não envia X-Idempotency-Key (decisão arquitetural).
  /// Retorna mapa com {id, status}.
  Future<Map<String, dynamic>> contestarColeta(String coletaId) async {
    final resposta = await _post(
      '/api/v1/collections/$coletaId/contestar',
      '{}',
    );
    return Map<String, dynamic>.from(
      jsonDecode(resposta.corpo) as Map,
    );
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

  Future<RespostaHttp> _post(String caminho, String corpo) async {
    final cabecalhos = <String, String>{
      'Content-Type': 'application/json',
    };
    final token = _obterToken?.call();
    if (token != null && token.isNotEmpty) {
      cabecalhos['Authorization'] = 'Bearer $token';
    }
    final enviar = _enviarEscrita;
    final resposta = enviar != null
        ? await enviar(caminho, cabecalhos, corpo)
        : await _postViaHttp(caminho, cabecalhos, corpo);
    if (resposta.codigo != 200) {
      throw Exception('Erro HTTP ${resposta.codigo}');
    }
    return resposta;
  }

  Future<RespostaHttp> _postViaHttp(
    String caminho,
    Map<String, String> cabecalhos,
    String corpo,
  ) async {
    final resposta = await http.post(
      Uri.parse('$_baseUrl$caminho'),
      headers: cabecalhos,
      body: corpo,
    );
    return RespostaHttp(resposta.statusCode, resposta.body);
  }

  Future<RespostaHttp> _postComBody(
    String caminho,
    String corpo,
  ) async {
    final cabecalhos = <String, String>{
      'Content-Type': 'application/json',
    };
    final token = _obterToken?.call();
    if (token != null && token.isNotEmpty) {
      cabecalhos['Authorization'] = 'Bearer $token';
    }
    final enviar = _enviarEscrita;
    final resposta = enviar != null
        ? await enviar(caminho, cabecalhos, corpo)
        : await _postViaHttp(caminho, cabecalhos, corpo);
    if (resposta.codigo != 200) {
      throw Exception('Erro HTTP ${resposta.codigo}');
    }
    return resposta;
  }
}
