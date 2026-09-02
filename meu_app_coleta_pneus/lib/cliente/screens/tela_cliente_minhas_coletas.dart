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
    setState(() => _future = _carregar());
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
                return Card(
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                  child: ListTile(
                    title: Text(c['codigo_identificador'] ?? ''),
                    subtitle: Text(
                      '${_rotuloStatus(c['status'] ?? '')} · '
                      '$totalItens pneu(s) · '
                      '${itens.length} item(ns)',
                    ),
                    trailing: const Icon(Icons.chevron_right),
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
