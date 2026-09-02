import 'package:flutter/material.dart';

import '../core/api/api_service.dart';
import '../core/outbox/outbox_service.dart';

/// Tela de conferência para coleta em EM_CONFERENCIA.
///
/// Permite ao prestador:
/// 1. Visualizar itens declarados pelo cliente.
/// 2. Registrar pneus individualmente (DOT, marca, medida, número de fogo).
/// 3. Conferir pneus já registrados no backend.
/// 4. Concluir a conferência (quantidade conferida vs coletada).
///
/// Registro e conclusão são realizados via Outbox (offline-first).
class TelaPrestadorConferencia extends StatefulWidget {
  const TelaPrestadorConferencia({
    super.key,
    required this.api,
    required this.outbox,
    required this.coleta,
  });

  final ApiService api;
  final OutboxService outbox;
  final Map<String, dynamic> coleta;

  @override
  State<TelaPrestadorConferencia> createState() =>
      _TelaPrestadorConferenciaState();
}

class _TelaPrestadorConferenciaState extends State<TelaPrestadorConferencia> {
  final _formKey = GlobalKey<FormState>();
  final _dotController = TextEditingController();
  final _marcaController = TextEditingController();
  final _medidaController = TextEditingController();
  final _fogoController = TextEditingController();

  List<Map<String, dynamic>> _itensDeclarados = [];
  List<Map<String, dynamic>> _pneusExistentes = [];
  bool _carregando = true;
  bool _ilegivel = false;
  bool _processando = false;

  String get _coletaId => widget.coleta['id'] as String;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  @override
  void dispose() {
    _dotController.dispose();
    _marcaController.dispose();
    _medidaController.dispose();
    _fogoController.dispose();
    super.dispose();
  }

  Future<void> _carregar() async {
    setState(() => _carregando = true);
    try {
      final dados = await widget.api.iniciarConferencia(_coletaId);
      _itensDeclarados =
          List<Map<String, dynamic>>.from(dados['itens_declarados'] ?? []);
    } catch (_) {
      _itensDeclarados = [];
    }
    try {
      _pneusExistentes = await widget.api.listarPneusConferencia(_coletaId);
    } catch (_) {
      _pneusExistentes = [];
    }
    if (mounted) setState(() => _carregando = false);
  }

  String? _validarDot(String? value) {
    if (value == null || value.isEmpty) return 'Obrigatório';
    if (value.length != 4) return '4 dígitos (WWYY)';
    final semana = int.tryParse(value.substring(0, 2));
    if (semana == null || semana < 1 || semana > 53) return 'Semana 01-53';
    return null;
  }

  Future<void> _adicionarPneu() async {
    if (!_formKey.currentState!.validate()) return;

    final pneu = <String, dynamic>{
      'dot': _dotController.text,
      'marca': _marcaController.text,
      'medida': _medidaController.text,
      'numero_fogo_ilegivel': _ilegivel,
    };
    if (_ilegivel) {
      pneu['foto_pneu_url'] = 'pendente';
      pneu['observacoes'] = 'ILEGÍVEL - foto pendente';
    } else if (_fogoController.text.isNotEmpty) {
      pneu['numero_fogo'] = _fogoController.text;
    }

    setState(() {
      _pneusExistentes.add(pneu);
    });

    _dotController.clear();
    _fogoController.clear();
    _formKey.currentState!.reset();
    setState(() => _ilegivel = false);
  }

  Future<void> _registrarPneus() async {
    if (_pneusExistentes.isEmpty) return;
    setState(() => _processando = true);
    try {
      await widget.outbox.agendarRegistroPneus(
        coletaId: _coletaId,
        pneus: _pneusExistentes,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '${_pneusExistentes.length} pneu(s) agendado(s) para envio.',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Erro ao agendar registro.')),
      );
    } finally {
      if (mounted) setState(() => _processando = false);
    }
  }

  Future<void> _concluirConferencia() async {
    if (widget.coleta['status'] != 'EM_CONFERENCIA') {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Conferência só pode ser concluída com status EM_CONFERENCIA.',
          ),
        ),
      );
      return;
    }

    final qtdColetada = _pneusExistentes.length;

    if (qtdColetada == 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Registre pelo menos 1 pneu.')),
      );
      return;
    }

    setState(() => _processando = true);
    try {
      await widget.outbox.agendarConclusaoConferencia(
        coletaId: _coletaId,
        quantidadeConferida: qtdColetada,
        quantidadeColetada: qtdColetada,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Conferência concluída!')),
      );
      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Erro ao concluir conferência.')),
      );
    } finally {
      if (mounted) setState(() => _processando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Conferência'),
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
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _secaoItensDeclarados(context),
                  const SizedBox(height: 16),
                  _secaoFormulario(context),
                  const SizedBox(height: 16),
                  _secaoPneusRegistrados(context),
                  const SizedBox(height: 24),
                  _botoesAcao(context),
                ],
              ),
            ),
    );
  }

  Widget _secaoItensDeclarados(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Itens declarados',
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        if (_itensDeclarados.isEmpty)
          const Text('Nenhum item declarado')
        else
          ..._itensDeclarados.map(
            (item) => Card(
              margin: const EdgeInsets.only(bottom: 4),
              child: ListTile(
                title: Text('${item['marca']} ${item['dimensao']}'),
                subtitle: Text('Qtd: ${item['quantidade_declarada']}'),
                dense: true,
              ),
            ),
          ),
      ],
    );
  }

  Widget _secaoFormulario(BuildContext context) {
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Registrar pneu',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          TextFormField(
            controller: _dotController,
            decoration: const InputDecoration(
              labelText: 'DOT (WWYY)',
              hintText: 'Ex: 2324',
              border: OutlineInputBorder(),
            ),
            keyboardType: TextInputType.number,
            maxLength: 4,
            validator: _validarDot,
          ),
          const SizedBox(height: 8),
          TextFormField(
            controller: _marcaController,
            decoration: const InputDecoration(
              labelText: 'Marca',
              hintText: 'Ex: Michelin',
              border: OutlineInputBorder(),
            ),
            validator: (v) =>
                (v == null || v.isEmpty) ? 'Obrigatório' : null,
          ),
          const SizedBox(height: 8),
          TextFormField(
            controller: _medidaController,
            decoration: const InputDecoration(
              labelText: 'Medida',
              hintText: 'Ex: 275/80R22.5',
              border: OutlineInputBorder(),
            ),
            validator: (v) =>
                (v == null || v.isEmpty) ? 'Obrigatório' : null,
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextFormField(
                  controller: _fogoController,
                  decoration: const InputDecoration(
                    labelText: 'Nº Fogo',
                    border: OutlineInputBorder(),
                  ),
                  enabled: !_ilegivel,
                ),
              ),
              const SizedBox(width: 8),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('Ilegível'),
                  Switch(
                    value: _ilegivel,
                    onChanged: (v) => setState(() {
                      _ilegivel = v;
                      if (v) _fogoController.clear();
                    }),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _processando ? null : _adicionarPneu,
              icon: const Icon(Icons.add),
              label: const Text('Adicionar à lista'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _secaoPneusRegistrados(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Pneus registrados (${_pneusExistentes.length})',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        if (_pneusExistentes.isEmpty)
          const Text('Nenhum pneu registrado')
        else
          ..._pneusExistentes.map(
            (p) => Card(
              margin: const EdgeInsets.only(bottom: 4),
              child: ListTile(
                leading: CircleAvatar(
                  backgroundColor: (p['alerta_idade_obsoleto'] == true)
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
                  '${p['numero_fogo_ilegivel'] == true ? ' · Ilegível' : ''}',
                ),
                dense: true,
              ),
            ),
          ),
      ],
    );
  }

  Widget _botoesAcao(BuildContext context) {
    return Column(
      children: [
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: (_processando || _pneusExistentes.isEmpty)
                ? null
                : _registrarPneus,
            icon: _processando
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.cloud_upload),
            label: const Text('Registrar pneu(s)'),
          ),
        ),
        const SizedBox(height: 8),
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: _processando ? null : _concluirConferencia,
            icon: const Icon(Icons.check_circle),
            label: const Text('Concluir conferência'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.green,
              foregroundColor: Colors.white,
            ),
          ),
        ),
      ],
    );
  }
}
