import 'dart:convert';

import 'package:http/http.dart' as http;

import 'operacao_pendente.dart';
import 'outbox_store.dart';

/// Função de transporte do envio. Retorna o código HTTP de resposta e
/// lança exceção em falha de rede. Injetável para testes.
typedef EnviarRequisicao = Future<int> Function(
  String caminho,
  Map<String, String> cabecalhos,
  String corpo,
);

/// Fundação do fluxo Outbox Offline (doc 09 §§2-4).
///
/// Fluxo por operação: gravação local imediata -> tentativa de envio com
/// `X-Idempotency-Key` UUIDv4 -> sucesso confirmado pelo backend descarta
/// o item; qualquer falha mantém a operação PENDENTE com a MESMA chave
/// para retry seguro (o backend deduplica replays).
///
/// Operações offline suportadas (escopo doc 09 §2): criação de coleta,
/// registro de pneus conferidos, conclusão da conferência e finalização —
/// todas já protegidas por idempotência no backend (Missões 12/13).
class OutboxService {
  OutboxService({
    OutboxStore? store,
    EnviarRequisicao? enviar,
    String baseUrl = '',
    String Function()? obterToken,
  })  : _store = store ?? OutboxStore(),
        _enviar = enviar,
        _baseUrl = baseUrl,
        _obterToken = obterToken;

  final OutboxStore _store;
  final EnviarRequisicao? _enviar;
  final String _baseUrl;
  final String Function()? _obterToken;

  /// Registra uma criação de coleta para envio futuro.
  ///
  /// Contrato do backend (ColetaCreateRequest, extra="forbid"):
  /// itens = {marca, dimensao, quantidade_declarada, observacao?};
  /// data_agendada é enviada em ISO 8601 com fuso (UTC).
  Future<OperacaoPendente> agendarCriacaoDeColeta({
    required Map<String, dynamic> enderecoOrigemJson,
    required DateTime dataAgendada,
    required List<Map<String, dynamic>> itens,
  }) {
    return agendar(
      caminho: '/api/v1/collections',
      corpo: {
        'endereco_origem_json': enderecoOrigemJson,
        'data_agendada': dataAgendada.toUtc().toIso8601String(),
        'itens': itens,
      },
    );
  }

  /// Registra o lote de pneus conferidos para envio futuro
  /// (RegistroPneusRequest: {"pneus": [...]}).
  Future<OperacaoPendente> agendarRegistroPneus({
    required String coletaId,
    required List<Map<String, dynamic>> pneus,
  }) {
    return agendar(
      caminho: '/api/v1/collections/$coletaId/conferencia/pneus',
      corpo: {'pneus': pneus},
    );
  }

  /// Registra a conclusão da conferência (ConclusaoConferenciaRequest:
  /// quantidades conferida/coletada independentes; divergências exigem
  /// justificativa no backend — doc AGENTS §4.5).
  Future<OperacaoPendente> agendarConclusaoConferencia({
    required String coletaId,
    required int quantidadeConferida,
    required int quantidadeColetada,
  }) {
    return agendar(
      caminho: '/api/v1/collections/$coletaId/conferencia/concluir',
      corpo: {
        'quantidade_conferida': quantidadeConferida,
        'quantidade_coletada': quantidadeColetada,
      },
    );
  }

  /// Registra a finalização da coleta. O backend exige corpo vazio estrito
  /// (nenhum valor financeiro aceito do cliente — FinalizacaoRequest).
  Future<OperacaoPendente> agendarFinalizacaoColeta({required String coletaId}) {
    return agendar(
      caminho: '/api/v1/collections/$coletaId/finalizar',
      corpo: const {},
    );
  }

  /// Agrega qualquer operação de escrita à fila local.
  Future<OperacaoPendente> agendar({
    required String caminho,
    required Map<String, dynamic> corpo,
  }) {
    return _store.inserir(OperacaoPendente.nova(caminho: caminho, corpo: corpo));
  }

  Future<List<OperacaoPendente>> pendentes() => _store.carregar();

  /// Tenta sincronizar as pendências em ordem cronológica estrita
  /// (doc 09 §3.1.4).
  ///
  /// - Sucesso (200/201): marca SINCRONIZADA e descarta o item.
  /// - Falha de rede ou HTTP: registra tentativa/erro e interrompe o lote;
  ///   os itens seguintes permanecem intactos na fila (ordem preservada).
  /// - Registros marcados como sincronizados que sobraram de um corte entre
  ///   marcação e descarte são removidos no início da próxima passagem.
  ///
  /// Retorna a quantidade de operações confirmadas nesta passagem.
  Future<int> sincronizarPendentes() async {
    var concluidas = 0;
    for (final operacao in await _store.carregar()) {
      if (operacao.status != StatusOperacaoOutbox.pendente) {
        await _store.remover(operacao.id);
        continue;
      }
      try {
        final codigo = await _despachar(operacao);
        if (codigo == 200 || codigo == 201) {
          operacao.marcarSincronizada();
          await _store.atualizar(operacao);
          await _store.remover(operacao.id);
          concluidas += 1;
          continue;
        }
        operacao.registrarFalha('HTTP $codigo');
        await _store.atualizar(operacao);
        break;
      } catch (erro) {
        // Falha de rede NUNCA apaga a operação (docs 09 §2 e 11 §M16).
        operacao.registrarFalha(erro.toString());
        await _store.atualizar(operacao);
        break;
      }
    }
    return concluidas;
  }

  Future<int> _despachar(OperacaoPendente operacao) {
    final cabecalhos = <String, String>{
      'Content-Type': 'application/json; charset=utf-8',
      // MESMA chave em toda tentativa: é ela que torna o retry seguro.
      'X-Idempotency-Key': operacao.id,
    };
    final token = _obterToken?.call();
    if (token != null && token.isNotEmpty) {
      cabecalhos['Authorization'] = 'Bearer $token';
    }
    final corpo = jsonEncode(operacao.corpo);
    final enviar = _enviar;
    if (enviar != null) {
      return enviar(operacao.caminho, cabecalhos, corpo);
    }
    return _enviarViaHttp(operacao.caminho, cabecalhos, corpo);
  }

  Future<int> _enviarViaHttp(
    String caminho,
    Map<String, String> cabecalhos,
    String corpo,
  ) async {
    final resposta = await http.post(
      Uri.parse('$_baseUrl$caminho'),
      headers: cabecalhos,
      body: corpo,
    );
    return resposta.statusCode;
  }
}
