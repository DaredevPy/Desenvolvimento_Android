import 'package:flutter/material.dart';

import '../../core/api/api_service.dart';
import '../../core/outbox/outbox_service.dart';
import 'tela_cliente_criar_coleta.dart';
import 'tela_cliente_resumo_coleta.dart';

/// Tela que lista as coletas do Cliente autenticado.
///
/// Usa ApiService para ler do backend. Exibe estados: carregando, vazio,
/// erro e dados. Botão para criar nova coleta via Outbox.
class TelaClienteMinhasColetas extends StatefulWidget {
  const TelaClienteMinhasColetas({
    super.key,
    required this.api,
    required this.outbox,
  });

  final ApiService api;
  final OutboxService outbox;

  @override
  State<TelaClienteMinhasColetas> createState() => _TelaClienteMinhasColetasState();
}

class _TelaClienteMinhasColetasState extends State<TelaClienteMinhasColetas> {
  late Future<List<Map<String, dynamic>>> _future;

  @override
  void initState() {
    super.initState();
    _future = _carregar();
  }

  Future<List<Map<String, dynamic>>> _carregar() async {
    return widget.api.listarMinhasColetas();
  }

  void _recarregar() {
    _future = _carregar();
    setState(() {});
  }

  void _navegarCriarColeta() async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => TelaClienteCriarColeta(outbox: widget.outbox),
      ),
    );
    _recarregar();
  }

  void _abrirDetalhe(Map<String, dynamic> coleta) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => TelaClienteResumoColeta(
          api: widget.api,
          coleta: coleta,
        ),
      ),
    );
    _recarregar();
  }

  bool _podeCancelar(String status) => status == 'SOLICITADA';

  Future<void> _cancelar(Map<String, dynamic> coleta) async {
    final coletaId = coleta['id'] as String;
    final confirmado = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancelar coleta'),
        content: const Text(
          'Ao confirmar, a coleta será marcada como CANCELADA. '
          'Esta ação não pode ser desfeita. Deseja continuar?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Confirmar cancelamento'),
          ),
        ],
      ),
    );

    if (confirmado != true || !mounted) return;

    try {
      await widget.api.cancelarColeta(coletaId);
      if (!mounted) return;
      _recarregar();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Coleta cancelada com sucesso.'),
          backgroundColor: Colors.green,
        ),
      );
    } on Exception catch (e) {
      if (!mounted) return;
      final mensagem = _mensagemErroCancelar(e);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(mensagem), backgroundColor: Colors.red),
      );
    }
  }

  String _mensagemErroCancelar(Exception e) {
    final texto = e.toString();
    if (texto.contains('Erro HTTP 403')) {
      return 'Operação não permitida. Apenas o dono da coleta pode cancelar.';
    }
    if (texto.contains('Erro HTTP 404')) {
      return 'Coleta não encontrada.';
    }
    if (texto.contains('Erro HTTP 409')) {
      return 'A coleta não pode ser cancelada no estado atual (somente SOLICITADA).';
    }
    if (texto.contains('Erro HTTP 422')) {
      return 'Erro de validação. Tente novamente.';
    }
    return 'Erro de conexão. Verifique sua internet e tente novamente.';
  }

  String _rotuloStatus(String status) {
    const mapa = {
      'RASCUNHO': 'Rascunho',
      'SOLICITADA': 'Solicitada',
      'ACEITA': 'Aceita',
      'EM_DESLOCAMENTO': 'Em deslocamento',
      'EM_CONFERENCIA': 'Em conferência',
      'CARREGADA': 'Carregada',
      'FINALIZADA': 'Finalizada',
      'CONTESTADA': 'Contestada',
      'CANCELADA': 'Cancelada',
    };
    return mapa[status] ?? status;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Minhas Coletas')),
      floatingActionButton: FloatingActionButton(
        onPressed: _navegarCriarColeta,
        child: const Icon(Icons.add),
      ),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.error_outline, size: 48, color: Colors.red),
                    const SizedBox(height: 16),
                    Text(
                      'Erro ao carregar coletas',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    OutlinedButton(
                      onPressed: _recarregar,
                      child: const Text('Tentar novamente'),
                    ),
                  ],
                ),
              ),
            );
          }
          final coletas = snapshot.data ?? [];
          if (coletas.isEmpty) {
            return Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.inbox, size: 64, color: Colors.grey),
                  const SizedBox(height: 16),
                  const Text('Nenhuma coleta encontrada'),
                  const SizedBox(height: 8),
                  OutlinedButton(
                    onPressed: _navegarCriarColeta,
                    child: const Text('Criar primeira coleta'),
                  ),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: () async => _recarregar(),
            child: ListView.builder(
              itemCount: coletas.length,
              itemBuilder: (context, index) {
                final c = coletas[index];
                final itens = c['itens'] as List? ?? [];
                final totalItens = itens.fold<int>(
                  0,
                  (soma, item) => soma + ((item['quantidade_declarada'] as num?)?.toInt() ?? 0),
                );
                final status = c['status'] as String? ?? '';
                return Card(
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                  child: ListTile(
                    title: Text(c['codigo_identificador'] ?? ''),
                    subtitle: Text(
                      '${_rotuloStatus(status)} · '
                      '$totalItens pneu(s) · '
                      '${itens.length} item(ns)',
                    ),
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (_podeCancelar(status))
                          IconButton(
                            icon: const Icon(Icons.cancel_outlined, color: Colors.red),
                            tooltip: 'Cancelar coleta',
                            onPressed: () => _cancelar(c),
                          ),
                        const Icon(Icons.chevron_right),
                      ],
                    ),
                    onTap: () => _abrirDetalhe(c),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
