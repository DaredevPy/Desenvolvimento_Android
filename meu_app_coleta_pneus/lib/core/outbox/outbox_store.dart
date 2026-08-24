import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import 'operacao_pendente.dart';

/// Persistência local do Outbox.
///
/// Grava a fila em `shared_preferences` (funciona em Android, iOS e Web),
/// garantindo que operações pendentes sobrevivam ao fechamento do app
/// (doc 09 §3.1.2). A fila preserva a ordem cronológica de inserção
/// (doc 09 §3.1.4).
class OutboxStore {
  static const _chaveArmazenamento = 'outbox_operacoes';

  Future<List<OperacaoPendente>> carregar() async {
    final prefs = await SharedPreferences.getInstance();
    final bruto = prefs.getString(_chaveArmazenamento);
    if (bruto == null || bruto.isEmpty) {
      return [];
    }
    final lista = jsonDecode(bruto) as List<dynamic>;
    return lista
        .map((item) => OperacaoPendente.fromMap(item as Map<String, dynamic>))
        .toList();
  }

  Future<void> _salvar(List<OperacaoPendente> operacoes) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _chaveArmazenamento,
      jsonEncode(operacoes.map((op) => op.toMap()).toList()),
    );
  }

  /// Agrega a operação ao fim da fila e a retorna.
  Future<OperacaoPendente> inserir(OperacaoPendente operacao) async {
    final operacoes = await carregar();
    operacoes.add(operacao);
    await _salvar(operacoes);
    return operacao;
  }

  Future<void> atualizar(OperacaoPendente operacao) async {
    final operacoes = await carregar();
    final indice = operacoes.indexWhere((op) => op.id == operacao.id);
    if (indice == -1) {
      return;
    }
    operacoes[indice] = operacao;
    await _salvar(operacoes);
  }

  Future<void> remover(String id) async {
    final operacoes = await carregar();
    operacoes.removeWhere((op) => op.id == id);
    await _salvar(operacoes);
  }
}
