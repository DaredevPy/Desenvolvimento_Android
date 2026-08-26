import 'dart:convert';

import 'package:http/http.dart' as http;

/// Resposta bruta do transporte HTTP injetável (código + corpo).
class RespostaHttp {
  const RespostaHttp(this.codigo, this.corpo);

  final int codigo;
  final String corpo;
}

/// Função de transporte das chamadas de autenticação. Injetável para testes
/// (mesmo padrão do OutboxService, porém retorna também o corpo, pois o
/// login precisa extrair o access_token da resposta).
typedef EnviarAutenticacao = Future<RespostaHttp> Function(
  String caminho,
  Map<String, String> cabecalhos,
  String corpo,
);

/// Persistência do token de sessão. Abstração mínima para permitir a
/// implementação segura multiplataforma (Android Keystore / iOS Keychain /
/// Web) e o dublê em memória nos testes.
abstract class ArmazenamentoSessao {
  Future<void> salvar(String token);
  Future<String?> ler();
  Future<void> remover();
}

/// Credenciais rejeitadas pelo backend (HTTP 401 em /auth/login).
class CredenciaisInvalidasExcecao implements Exception {
  @override
  String toString() => 'Credenciais inválidas.';
}

/// Sessão do usuário contra a API real (docs 08 §2 e 05 §1).
///
/// Consome EXCLUSIVAMENTE os contratos existentes do backend:
/// POST /api/v1/auth/login -> {"access_token","token_type"} (200),
/// 401 para credenciais inválidas. O JWT é stateless com expiração curta
/// (ACCESS_TOKEN_EXPIRE_MINUTES no backend): não há refresh nem endpoint de
/// logout no servidor, portanto [sair] apenas descarta o token localmente.
///
/// A senha é transmitida somente na requisição de login (HTTPS) e NUNCA é
/// persistida. O token fica no [ArmazenamentoSessao] seguro e em memória;
/// o Outbox obtém-no por [tokenAtual].
class ServicoSessao {
  ServicoSessao({
    required ArmazenamentoSessao armazenamento,
    EnviarAutenticacao? enviar,
    String baseUrl = '',
  })  : _armazenamento = armazenamento,
        _enviarInjetado = enviar,
        _baseUrl = baseUrl;

  static const _caminhoLogin = '/api/v1/auth/login';

  final ArmazenamentoSessao _armazenamento;
  final EnviarAutenticacao? _enviarInjetado;
  final String _baseUrl;

  String? _token;

  /// Token atual em memória (síncrono de propósito: é lido pelo Outbox a
  /// cada envio). Disponível após [carregar] ou um [entrar] bem-sucedido.
  String? get tokenAtual => _token;

  /// Restaura a sessão persistida (chamar uma vez no arranque do app,
  /// ANTES de iniciar a sincronização automática do Outbox).
  Future<void> carregar() async {
    _token ??= await _armazenamento.ler();
  }

  /// Autentica com os contratos reais de /auth/login.
  ///
  /// - 200: guarda o access_token (memória + armazenamento seguro).
  /// - 401: [CredenciaisInvalidasExcecao]; nada é salvo.
  /// - outros códigos/falha de rede: exceção propagada; nada é salvo.
  Future<void> entrar({required String email, required String senha}) async {
    final resposta = await (_enviarInjetado ?? _enviarViaHttp)(
      _caminhoLogin,
      const {'Content-Type': 'application/json; charset=utf-8'},
      jsonEncode({'email': email, 'senha': senha}),
    );

    if (resposta.codigo == 401) {
      throw CredenciaisInvalidasExcecao();
    }
    if (resposta.codigo != 200) {
      throw Exception('Falha no login (HTTP ${resposta.codigo}).');
    }

    final dados = jsonDecode(resposta.corpo);
    final token = dados['access_token'];
    if (token is! String || token.isEmpty) {
      throw Exception('Resposta de login sem access_token válido.');
    }
    _token = token;
    await _armazenamento.salvar(token);
  }

  /// Descarta a sessão local (memória + armazenamento). O JWT stateless já
  /// emitido segue válido no servidor até expirar (revogação é decisão
  /// pendente documentada no STATUS_DO_PROJETO.md §8).
  Future<void> sair() async {
    _token = null;
    await _armazenamento.remover();
  }

  Future<RespostaHttp> _enviarViaHttp(
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
}
