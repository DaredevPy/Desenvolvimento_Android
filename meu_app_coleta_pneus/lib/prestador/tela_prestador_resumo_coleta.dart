import 'package:flutter/material.dart';

import '../core/api/api_service.dart';

/// Tela de resumo / comprovante de uma coleta FINALIZADA (somente leitura).
///
/// Exibe dados fornecidos exclusivamente pelo backend:
/// - Identificação da coleta e status FINALIZADA.
/// - Endereço e datas da coleta.
/// - Quantidade e lista consolidada dos pneus conferidos (DOT, marca, medida,
///   número de fogo ou ilegível, alerta de idade).
///
/// Não realiza cálculos financeiros locais nem envia dados ao servidor.
class TelaPrestadorResumoColeta extends StatefulWidget {
  const TelaPrestadorResumoColeta({
    super.key,
    required this.api,
    required this.coleta,
  });

  final ApiService api;
  final Map<String, dynamic> coleta;

  @override
  State<TelaPrestadorResumoColeta> createState() =>
      _TelaPrestadorResumoColetaState();
}

class _TelaPrestadorResumoColetaState extends State<TelaPrestadorResumoColeta> {
  List<Map<String, dynamic>> _pneus = [];
  bool _carregando = true;
  String? _erro;

  String get _coletaId => widget.coleta['id'] as String? ?? '';
  String get _status => widget.coleta['status'] as String? ?? '';
  bool get _ehFinalizada => _status == 'FINALIZADA';

  @override
  void initState() {
    super.initState();
    if (_ehFinalizada) {
      _carregarPneus();
    } else {
      _carregando = false;
    }
  }

  Future<void> _carregarPneus() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });

    try {
      final pneus = await widget.api.listarPneusConferencia(_coletaId);
      if (!mounted) return;
      setState(() {
        _pneus = pneus;
        _carregando = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _erro = 'Não foi possível carregar os pneus da coleta.';
        _carregando = false;
      });
    }
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
    final cidade = endereco['cidade'] ?? '';
    final partes = [
      if (rua.toString().isNotEmpty) rua.toString(),
      if (numero.toString().isNotEmpty) numero.toString(),
      if (bairro.toString().isNotEmpty) bairro.toString(),
      if (cidade.toString().isNotEmpty) cidade.toString(),
    ];
    return partes.isEmpty ? '—' : partes.join(', ');
  }

  @override
  Widget build(BuildContext context) {
    final codigo = widget.coleta['codigo_identificador'] ?? _coletaId;

    if (!_ehFinalizada) {
      return Scaffold(
        appBar: AppBar(title: const Text('Resumo da Coleta')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.lock_outline, size: 48, color: Colors.orange),
                const SizedBox(height: 16),
                Text(
                  'Coleta não finalizada',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                const Text(
                  'O resumo consolidado só está disponível para coletas no status FINALIZADA.',
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      );
    }

    final endereco =
        widget.coleta['endereco_origem_json'] as Map<String, dynamic>? ?? {};

    return Scaffold(
      appBar: AppBar(
        title: Text('Resumo: $codigo'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Atualizar',
            onPressed: _carregarPneus,
          ),
        ],
      ),
      body: _carregando
          ? const Center(child: CircularProgressIndicator())
          : _erro != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.error_outline,
                            size: 48, color: Colors.red),
                        const SizedBox(height: 16),
                        Text(_erro!, textAlign: TextAlign.center),
                        const SizedBox(height: 16),
                        ElevatedButton.icon(
                          onPressed: _carregarPneus,
                          icon: const Icon(Icons.refresh),
                          label: const Text('Tentar novamente'),
                        ),
                      ],
                    ),
                  ),
                )
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              codigo,
                              style: Theme.of(context).textTheme.headlineSmall,
                            ),
                          ),
                          const Chip(
                            label: Text('Finalizada'),
                            backgroundColor: Colors.green,
                            labelStyle: TextStyle(color: Colors.white),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      _secao(
                          context, 'Endereço de origem', _logradouro(endereco)),
                      const SizedBox(height: 8),
                      _secao(context, 'Data agendada',
                          _formatarData(widget.coleta['data_agendada'])),
                      const SizedBox(height: 8),
                      _secao(context, 'Criada em',
                          _formatarData(widget.coleta['criado_em'])),
                      const SizedBox(height: 16),
                      const Divider(),
                      const SizedBox(height: 8),
                      Text(
                        'Pneus conferidos (${_pneus.length})',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 8),
                      if (_pneus.isEmpty)
                        const Text('Nenhum pneu conferido registrado.')
                      else
                        ..._pneus.map(
                          (p) => Card(
                            margin: const EdgeInsets.only(bottom: 8),
                            child: ListTile(
                              leading: CircleAvatar(
                                backgroundColor:
                                    (p['alerta_idade_obsoleto'] == true)
                                        ? Colors.red
                                        : Colors.green,
                                child: Text(
                                  (p['dot'] as String? ?? '?').substring(0, 2),
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 12,
                                  ),
                                ),
                              ),
                              title: Text('${p['marca']} ${p['medida']}'),
                              subtitle: Text(
                                'DOT: ${p['dot']}'
                                '${p['numero_fogo'] != null ? ' · Fogo: ${p['numero_fogo']}' : ''}'
                                '${p['numero_fogo_ilegivel'] == true ? ' · Ilegível' : ''}'
                                '${p['idade_calculada_anos'] != null ? ' · Idade: ${p['idade_calculada_anos']} anos' : ''}',
                              ),
                              dense: true,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
    );
  }

  Widget _secao(BuildContext context, String titulo, String valor) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(titulo, style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 2),
        Text(valor, style: Theme.of(context).textTheme.bodyLarge),
      ],
    );
  }
}
