import 'package:flutter/material.dart';

import '../../core/api/api_service.dart';

/// Tela de resumo / comprovante de uma coleta FINALIZADA para o CLIENTE (somente leitura).
///
/// Exibe dados fornecidos exclusivamente pelo backend:
/// - Identificação da coleta e status FINALIZADA.
/// - Endereço de origem e datas da coleta.
/// - Itens declarados na solicitação.
/// - Quantidade total e lista consolidada dos pneus conferidos/coletados:
///   DOT, marca, medida, número de fogo ou "Ilegível", alerta de idade obsoleto.
///
/// Não realiza cálculos financeiros no cliente nem envia dados ao servidor.
class TelaClienteResumoColeta extends StatefulWidget {
  const TelaClienteResumoColeta({
    super.key,
    required this.api,
    required this.coleta,
  });

  final ApiService api;
  final Map<String, dynamic> coleta;

  @override
  State<TelaClienteResumoColeta> createState() =>
      _TelaClienteResumoColetaState();
}

class _TelaClienteResumoColetaState extends State<TelaClienteResumoColeta> {
  late Map<String, dynamic> _coleta;
  List<Map<String, dynamic>> _pneus = [];
  bool _carregando = true;
  String? _erro;
  bool _contestando = false;
  bool _cancelando = false;

  String get _coletaId => widget.coleta['id'] as String? ?? '';
  String get _status => _coleta['status'] as String? ?? '';
  bool get _ehFinalizada => _status == 'FINALIZADA';
  bool get _podeContestar => _status == 'FINALIZADA';
  bool get _podeCancelar => _status == 'SOLICITADA';

  @override
  void initState() {
    super.initState();
    _coleta = widget.coleta;
    if (_ehFinalizada) {
      _carregar();
    } else {
      _carregando = false;
    }
  }

  Future<void> _carregar() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });

    try {
      final dados = await widget.api.obterColeta(_coletaId);
      if (!mounted) return;
      setState(() {
        _coleta = {..._coleta, ...dados};
        _pneus = List<Map<String, dynamic>>.from(
          _coleta['pneus'] ?? _coleta['itens_conferidos'] ?? [],
        );
        _carregando = false;
      });
    } catch (_) {
      if (!mounted) return;
      final pneusLocais = List<Map<String, dynamic>>.from(
        _coleta['pneus'] ?? _coleta['itens_conferidos'] ?? [],
      );
      if (pneusLocais.isNotEmpty) {
        setState(() {
          _pneus = pneusLocais;
          _carregando = false;
        });
      } else {
        setState(() {
          _erro = 'Não foi possível carregar os dados da coleta.';
          _carregando = false;
        });
      }
    }
  }

  Future<void> _contestar() async {
    if (_contestando) return;

    final confirmado = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Contestar coleta'),
        content: const Text(
          'Ao confirmar, a coleta será marcada como CONTESTADA. '
          'Esta ação altera o estado da coleta e será registrada no sistema. '
          'Deseja continuar?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Confirmar contestação'),
          ),
        ],
      ),
    );

    if (confirmado != true || !mounted) return;

    setState(() => _contestando = true);

    try {
      final resultado = await widget.api.contestarColeta(_coletaId);
      if (!mounted) return;
      setState(() {
        _coleta = {..._coleta, ...resultado};
        _contestando = false;
      });
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Contestação registrada. A coleta agora está como CONTESTADA.'),
          backgroundColor: Colors.green,
        ),
      );
    } on Exception catch (e) {
      if (!mounted) return;
      setState(() => _contestando = false);
      final mensagem = _mensagemErro(e);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(mensagem), backgroundColor: Colors.red),
      );
    }
  }

  Future<void> _cancelar() async {
    if (_cancelando) return;

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

    setState(() => _cancelando = true);

    try {
      final resultado = await widget.api.cancelarColeta(_coletaId);
      if (!mounted) return;
      setState(() {
        _coleta = {..._coleta, ...resultado};
        _cancelando = false;
      });
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Coleta cancelada com sucesso.'),
          backgroundColor: Colors.green,
        ),
      );
    } on Exception catch (e) {
      if (!mounted) return;
      setState(() => _cancelando = false);
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

  String _mensagemErro(Exception e) {
    final texto = e.toString();
    if (texto.contains('Erro HTTP 403')) {
      return 'Operação não permitida. Apenas o dono da coleta pode contestar.';
    }
    if (texto.contains('Erro HTTP 404')) {
      return 'Coleta não encontrada.';
    }
    if (texto.contains('Erro HTTP 409')) {
      return 'O estado da coleta mudou ou a operação não pode mais ser realizada.';
    }
    if (texto.contains('Erro HTTP 422')) {
      return 'Erro de validação. Tente novamente.';
    }
    return 'Erro de conexão. Verifique sua internet e tente novamente.';
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
    final rua =
        endereco['rua'] ?? endereco['logradouro'] ?? endereco['endereco'] ?? '';
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
      case 'CONTESTADA':
      case 'CANCELADA':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    final codigo = _coleta['codigo_identificador'] ?? _coletaId;

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
        _coleta['endereco_origem_json'] as Map<String, dynamic>? ?? {};
    final itensDeclarados = _coleta['itens'] as List? ?? [];

    return Scaffold(
      appBar: AppBar(
        title: Text('Resumo: $codigo'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Atualizar',
            onPressed: _carregar,
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
                          onPressed: _carregar,
                          icon: const Icon(Icons.refresh),
                          label: const Text('Tentar novamente'),
                        ),
                      ],
                    ),
                  ),
                )
              : Column(
                  children: [
                    Expanded(
                      child: SingleChildScrollView(
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
                                Chip(
                                  label: Text(_rotuloStatus(_status)),
                                  backgroundColor: _corStatus(_status),
                                  labelStyle: const TextStyle(color: Colors.white),
                                ),
                              ],
                            ),
                            const SizedBox(height: 16),
                            _secao(
                                context, 'Endereço de origem', _logradouro(endereco)),
                            const SizedBox(height: 8),
                            _secao(context, 'Data agendada',
                                _formatarData(_coleta['data_agendada'])),
                            const SizedBox(height: 8),
                            _secao(context, 'Criada em',
                                _formatarData(_coleta['criado_em'])),
                            if (itensDeclarados.isNotEmpty) ...[
                              const SizedBox(height: 16),
                              const Divider(),
                              const SizedBox(height: 8),
                              Text(
                                'Itens declarados (${itensDeclarados.length})',
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              const SizedBox(height: 8),
                              ...itensDeclarados.map(
                                (item) => Card(
                                  margin: const EdgeInsets.only(bottom: 4),
                                  child: ListTile(
                                    title:
                                        Text('${item['marca']} ${item['dimensao']}'),
                                    subtitle: Text(
                                        'Qtd declarada: ${item['quantidade_declarada']}'),
                                    dense: true,
                                  ),
                                ),
                              ),
                            ],
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
                    if (_podeCancelar)
                      Padding(
                        padding: const EdgeInsets.all(16),
                        child: SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: _cancelando ? null : _cancelar,
                            icon: _cancelando
                                ? const SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : const Icon(Icons.cancel_outlined),
                            label: Text(_cancelando ? 'Cancelando...' : 'Cancelar coleta'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.orange,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(vertical: 16),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                    ),
                    if (_podeContestar)
                      Padding(
                        padding: const EdgeInsets.all(16),
                        child: SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: _contestando ? null : _contestar,
                            icon: _contestando
                                ? const SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : const Icon(Icons.report_problem),
                            label: Text(_contestando ? 'Contestando...' : 'Contestar coleta'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.red,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(vertical: 16),
),
                        ),
                      ),
                    ),
                  ],
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