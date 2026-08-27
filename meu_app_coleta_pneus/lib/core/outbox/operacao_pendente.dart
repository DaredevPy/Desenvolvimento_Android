import 'package:uuid/uuid.dart';

/// Estado de uma operação na fila Outbox (doc 09 §3.1).
enum StatusOperacaoOutbox { pendente, sincronizada, falhaDefinitiva }

/// Operação de escrita criada offline, aguardando envio ao backend.
///
/// O [id] é um UUIDv4 gerado no momento do agendamento e é a própria
/// `X-Idempotency-Key` enviada em toda tentativa (docs 09 §4.1 e 11 §M13):
/// o backend deduplica replays, então o retry SEMPRE reutiliza esta chave.
class OperacaoPendente {
  OperacaoPendente({
    required this.id,
    required this.caminho,
    required this.corpo,
    required this.criadoEm,
    this.status = StatusOperacaoOutbox.pendente,
    this.tentativas = 0,
    this.ultimoErro,
  });

  /// UUIDv4: identidade local e chave de idempotência no backend.
  final String id;

  /// Caminho do endpoint REST (ex.: '/api/v1/collections').
  final String caminho;

  /// Payload JSON exato a ser enviado (reenviado idêntico em cada tentativa,
  /// pois o backend valida o hash do corpo contra a chave).
  final Map<String, dynamic> corpo;
  final DateTime criadoEm;
  StatusOperacaoOutbox status;

  /// Quantidade de tentativas de envio já realizadas sem confirmação.
  int tentativas;

  /// Último erro observado (rede ou HTTP), apenas informativo.
  String? ultimoErro;

  factory OperacaoPendente.nova({
    required String caminho,
    required Map<String, dynamic> corpo,
  }) {
    return OperacaoPendente(
      id: const Uuid().v4(),
      caminho: caminho,
      corpo: corpo,
      criadoEm: DateTime.now().toUtc(),
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'caminho': caminho,
      'corpo': corpo,
      'criado_em': criadoEm.toIso8601String(),
      'status': status.name,
      'tentativas': tentativas,
      'ultimo_erro': ultimoErro,
    };
  }

  factory OperacaoPendente.fromMap(Map<String, dynamic> map) {
    return OperacaoPendente(
      id: map['id'] as String,
      caminho: map['caminho'] as String,
      corpo: Map<String, dynamic>.from(map['corpo'] as Map),
      criadoEm: DateTime.parse(map['criado_em'] as String),
      status: StatusOperacaoOutbox.values.firstWhere(
        (s) => s.name == map['status'],
        orElse: () => StatusOperacaoOutbox.pendente,
      ),
      tentativas: (map['tentativas'] as num?)?.toInt() ?? 0,
      ultimoErro: map['ultimo_erro'] as String?,
    );
  }

  void registrarFalha(String erro, {bool definitivo = false}) {
    tentativas += 1;
    ultimoErro = erro;
    status = definitivo
        ? StatusOperacaoOutbox.falhaDefinitiva
        : StatusOperacaoOutbox.pendente;
  }

  void marcarSincronizada() {
    status = StatusOperacaoOutbox.sincronizada;
    ultimoErro = null;
  }
}
