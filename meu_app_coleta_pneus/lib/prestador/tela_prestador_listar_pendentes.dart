import 'package:flutter/material.dart';

import '../core/api/api_service.dart';

/// Tela que lista coletas disponíveis para aceite (somente PRESTADOR).
///
/// Consome GET /api/v1/collections/disponiveis e POST .../aceitar do backend.
/// Estados: carregando, vazio, erro, dados. Trata 401/403/404/409.
class TelaPrestadorListarPendentes extends StatefulWidget {
  const TelaPrestadorListarPendentes({super.key, required this.api});

  final ApiService api;

  @override
  State<TelaPrestadorListarPendentes> createState() =>
      _TelaPrestadorListarPendentesState();
}

class _TelaPrestadorListarPendentesState
    extends State<TelaPrestadorListarPendentes> {
  late Future<List<Map<String, dynamic>>> _future;
  final Set<String> _aceitando = {};

  @override
  void initState() {
    super.initState();
    _future = _carregar();
  }

  Future<List<Map<String, dynamic>>> _carregar() async {
    return widget.api.listarDisponiveis();
  }

  void _recarregar() {
    setState(() {
      _future = _carregar();
    });
  }

  Future<void> _aceitar(String coletaId) async {
    if (_aceitando.contains(coletaId)) return;
    setState(() => _aceitando.add(coletaId));

    try {
      await widget.api.aceitar(coletaId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Coleta aceita com sucesso!')),
      );
      _recarregar();
    } on Exception catch (e) {
      if (!mounted) return;
      final msg = _mensagemErro(e);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(msg)),
      );
      if (_ehErroRecarregar(e)) {
        _recarregar();
      }
    } finally {
      if (mounted) setState(() => _aceitando.remove(coletaId));
    }
  }

  String _mensagemErro(Exception e) {
    final texto = e.toString();
    if (texto.contains('Erro HTTP 401')) return 'Sessão expirada. Faça login novamente.';
    if (texto.contains('Erro HTTP 403')) return 'Acesso negado para este perfil.';
    if (texto.contains('Erro HTTP 404')) return 'Coleta ou perfil não encontrado.';
    if (texto.contains('Erro HTTP 409')) return 'Coleta já foi aceita por outro prestador.';
    return 'Erro de conexão. Tente novamente.';
  }

  bool _ehErroRecarregar(Exception e) {
    final texto = e.toString();
    return texto.contains('Erro HTTP 409');
  }

  String _formatarData(String? iso) {
    if (iso == null || iso.isEmpty) return '—';
    try {
      final dt = DateTime.parse(iso).toLocal();
      return '${dt.day.toString().padLeft(2, '0')}/'
          '${dt.month.toString().padLeft(2, '0')}/'
          '${dt.year} '
          '${dt.hour.toString().padLeft(2, '0')}:'
          '${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return iso;
    }
  }

  String _logradouro(Map<String, dynamic> endereco) {
    final rua = endereco['rua'] ?? endereco['logradouro'] ?? '';
    final numero = endereco['numero'] ?? '';
    final bairro = endereco['bairro'] ?? '';
    final partes = [
      if (rua.toString().isNotEmpty) rua.toString(),
      if (numero.toString().isNotEmpty) numero.toString(),
      if (bairro.toString().isNotEmpty) bairro.toString(),
    ];
    return partes.isEmpty ? '—' : partes.join(', ');
  }

  int _totalPneus(List<dynamic> itens) {
    return itens.fold<int>(
      0,
      (soma, item) =>
          soma + ((item['quantidade_declarada'] as num?)?.toInt() ?? 0),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Coletas Disponíveis'),
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
                      _mensagemErro(snapshot.error! as Exception),
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
                  const Text('Nenhuma coleta disponível'),
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
                final itens = c['itens'] as List? ?? [];
                final endereco = c['endereco_origem_json'] as Map<String, dynamic>? ?? {};
                final aceitando = _aceitando.contains(c['id']);
                return Card(
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                c['codigo_identificador'] ?? '',
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                            ),
                            if (aceitando)
                              const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(_logradouro(endereco)),
                        const SizedBox(height: 4),
                        Text(
                          'Agendada: ${_formatarData(c['data_agendada'])}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${_totalPneus(itens)} pneu(s) · ${itens.length} item(ns)',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const SizedBox(height: 8),
                        Align(
                          alignment: Alignment.centerRight,
                          child: ElevatedButton(
                            onPressed: aceitando ? null : () => _aceitar(c['id']),
                            child: const Text('Aceitar coleta'),
                          ),
                        ),
                      ],
                    ),
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
