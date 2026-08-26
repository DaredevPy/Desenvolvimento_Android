import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/widgets.dart';

import 'outbox_service.dart';

/// Disparo automático da sincronização do Outbox (doc 09 §3).
///
/// Executa [OutboxService.sincronizarPendentes] em três gatilhos externos e
/// pontuais — nenhum timer/retry próprio, portanto não existe loop de
/// tentativas; uma passagem que falha só é retomada pelo PRÓXIMO evento:
/// - início do aplicativo ([iniciar]);
/// - retorno ao primeiro plano (ciclo de vida `resumed`);
/// - restabelecimento da conexão (stream de conectividade).
///
/// Uma única passagem roda por vez: disparo recebido durante sincronização
/// em curso é ignorado (o próximo evento dispara nova passagem). A fila
/// vazia não gera requisição e falha preserva as operações com a mesma
/// chave/payload — garantias herdadas do serviço.
class SincronizacaoAutomaticaOutbox with WidgetsBindingObserver {
  SincronizacaoAutomaticaOutbox({
    required OutboxService outbox,
    Stream<List<ConnectivityResult>>? conectividade,
  })  : _outbox = outbox,
        _conectividadeInjetada = conectividade;

  final OutboxService _outbox;

  /// Injetável para testes; em produção usa o plugin connectivity_plus.
  final Stream<List<ConnectivityResult>>? _conectividadeInjetada;

  StreamSubscription<List<ConnectivityResult>>? _assinatura;
  bool _sincronizando = false;

  /// Registra os gatilhos e executa a primeira tentativa (app iniciando).
  void iniciar() {
    WidgetsBinding.instance.addObserver(this);
    final conectividade =
        _conectividadeInjetada ?? Connectivity().onConnectivityChanged;
    _assinatura = conectividade.listen(_aoMudarConectividade);
    _tentarSincronizar();
  }

  /// Remove os gatilhos (isolamento entre testes; no app vive até o fim).
  void descartar() {
    WidgetsBinding.instance.removeObserver(this);
    _assinatura?.cancel();
    _assinatura = null;
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState estado) {
    if (estado == AppLifecycleState.resumed) {
      _tentarSincronizar();
    }
  }

  void _aoMudarConectividade(List<ConnectivityResult> resultados) {
    // Lista nunca vazia; [ConnectivityResult.none] sozinho significa sem
    // rede — tentativa seria perda certa e a fila deve aguardar conexão.
    if (resultados.any((r) => r != ConnectivityResult.none)) {
      _tentarSincronizar();
    }
  }

  Future<void> _tentarSincronizar() async {
    if (_sincronizando) {
      return;
    }
    _sincronizando = true;
    try {
      await _outbox.sincronizarPendentes();
    } catch (_) {
      // Melhor-esforço: erro fora do fluxo normal (ex.: persistência local)
      // não pode derrubar o app nem disparar retry em cascata; a operação
      // permanece na fila para o próximo evento.
    } finally {
      _sincronizando = false;
    }
  }
}
