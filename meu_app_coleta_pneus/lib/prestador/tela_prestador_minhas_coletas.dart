import 'package:flutter/material.dart';

import '../core/api/api_service.dart';
import '../core/outbox/outbox_service.dart';
import 'tela_prestador_detalhe_coleta.dart';

/// Tela que lista coletas atribuídas ao Prestador (qualquer status).
///
/// Consome GET /api/v1/collections (PRESTADOR: filtra por provider_id).
/// Estados: carregando, vazio, erro, dados. Pull-to-refresh.
class TelaPrestadorMinhasColetas extends StatefulWidget {
  const TelaPrestadorMinhasColetas({
    super.key,
    required this.api,
    required this.outbox,
  });

  final ApiService api;
  final OutboxService outbox;

  @override
  State<TelaPrestadorMinhasColetas> createState() =>
      _TelaPrestadorMinhasColetasState();
}

class _TelaPrestadorMinhasColetasState
    extends State<TelaPrestadorMinhasColetas> {
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
    setState(() {
      _future = _carregar();
    });
  }

  String _rotuloStatus(String status) {
    const mapa = {
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

  Color _corStatus(String status) {
    switch (status) {
      case 'ACEITA':
        return Colors.orange;
      case 'EM_DESLOCAMENTO':
        return Colors.blue;
      case 'EM_CONFERENCIA':
        return Colors.purple;
      case 'CARREGADA':
        return Colors.teal;
      case 'FINALIZADA':
        return Colors.green;
      case 'CANCELADA':
      case 'CONTESTADA':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  void _abrirDetalhe(Map<String, dynamic> coleta) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => TelaPrestadorDetalheColeta(
          api: widget.api,
          outbox: widget.outbox,
          coleta: coleta,
        ),
      ),
    );
    _recarregar();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Minhas Coletas'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Atualizar',
            onPressed: _recarregar,
          ),
        ],
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
                      textAlign: TextAlign.center,
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
                  const Text('Nenhuma coleta atribuída'),
                  const SizedBox(height: 8),
                  OutlinedButton(
                    onPressed: _recarregar,
                    child: const Text('Atualizar'),
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
                final status = c['status'] as String? ?? '';
                final itens = c['itens'] as List? ?? [];
                final totalPneus = itens.fold<int>(
                  0,
                  (soma, item) =>
                      soma + ((item['quantidade_declarada'] as num?)?.toInt() ?? 0),
                );
                return Card(
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: _corStatus(status),
                      child: Text(
                        status.substring(0, 1),
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                      ),
                    ),
                    title: Text(c['codigo_identificador'] ?? ''),
                    subtitle: Text(
                      '${_rotuloStatus(status)} · $totalPneus pneu(s)',
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
