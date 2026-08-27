import 'package:flutter/material.dart';

import '../../core/outbox/outbox_service.dart';

/// Tela para o Cliente criar uma nova coleta de pneus.
///
/// Envia a operação via OutboxService (preserva offline). O backend
/// recebe a criação via POST /api/v1/collections com X-Idempotency-Key.
class TelaClienteCriarColeta extends StatefulWidget {
  const TelaClienteCriarColeta({
    super.key,
    required this.outbox,
  });

  final OutboxService outbox;

  @override
  State<TelaClienteCriarColeta> createState() => _TelaClienteCriarColetaState();
}

class _TelaClienteCriarColetaState extends State<TelaClienteCriarColeta> {
  final _formKey = GlobalKey<FormState>();
  final _enderecoController = TextEditingController();
  final _dataController = TextEditingController();
  final _marcaController = TextEditingController();
  final _dimensaoController = TextEditingController();
  final _quantidadeController = TextEditingController(text: '1');
  final _observacaoController = TextEditingController();

  static const _chaveEndereco = Key('campo_endereco');
  static const _chaveMarca = Key('campo_marca');
  static const _chaveDimensao = Key('campo_dimensao');
  static const _chaveQuantidade = Key('campo_quantidade');
  bool _salvando = false;

  @override
  void dispose() {
    _enderecoController.dispose();
    _dataController.dispose();
    _marcaController.dispose();
    _dimensaoController.dispose();
    _quantidadeController.dispose();
    _observacaoController.dispose();
    super.dispose();
  }

  Future<void> _selecionarData() async {
    final agora = DateTime.now();
    final data = await showDatePicker(
      context: context,
      initialDate: agora,
      firstDate: agora,
      lastDate: DateTime(agora.year + 1),
    );
    if (data != null && mounted) {
      final hora = await showTimePicker(
        context: context,
        initialTime: TimeOfDay.fromDateTime(agora),
      );
      if (hora != null && mounted) {
        final completo = DateTime(
          data.year,
          data.month,
          data.day,
          hora.hour,
          hora.minute,
        );
        _dataController.text = completo.toIso8601String();
      }
    }
  }

  Future<void> _salvar() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _salvando = true);

    try {
      await widget.outbox.agendarCriacaoDeColeta(
        enderecoOrigemJson: {'endereco': _enderecoController.text},
        dataAgendada: _dataController.text.isNotEmpty
            ? DateTime.parse(_dataController.text).toUtc()
            : DateTime.now().toUtc(),
        itens: [
          {
            'marca': _marcaController.text,
            'dimensao': _dimensaoController.text,
            'quantidade_declarada': int.parse(_quantidadeController.text),
            if (_observacaoController.text.isNotEmpty)
              'observacao': _observacaoController.text,
          },
        ],
      );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Coleta agendada. Será enviada quando houver conexão.')),
        );
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erro ao agendar: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _salvando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Criar Coleta')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                key: _chaveEndereco,
                controller: _enderecoController,
                decoration: const InputDecoration(
                  labelText: 'Endereço de origem',
                  hintText: 'Rua, número, bairro, cidade - UF',
                ),
                validator: (v) => (v == null || v.isEmpty) ? 'Obrigatório' : null,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _dataController,
                decoration: const InputDecoration(
                  labelText: 'Data agendada (opcional)',
                  hintText: 'Toque para selecionar',
                ),
                readOnly: true,
                onTap: _selecionarData,
              ),
              const SizedBox(height: 24),
              Text('Itens', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              TextFormField(
                key: _chaveMarca,
                controller: _marcaController,
                decoration: const InputDecoration(labelText: 'Marca'),
                validator: (v) => (v == null || v.isEmpty) ? 'Obrigatório' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                key: _chaveDimensao,
                controller: _dimensaoController,
                decoration: const InputDecoration(labelText: 'Dimensão'),
                validator: (v) => (v == null || v.isEmpty) ? 'Obrigatório' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                key: _chaveQuantidade,
                controller: _quantidadeController,
                decoration: const InputDecoration(labelText: 'Quantidade'),
                keyboardType: TextInputType.number,
                validator: (v) {
                  if (v == null || v.isEmpty) return 'Obrigatório';
                  final n = int.tryParse(v);
                  if (n == null || n < 1) return 'Mínimo 1';
                  return null;
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _observacaoController,
                decoration: const InputDecoration(labelText: 'Observação (opcional)'),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: _salvando ? null : _salvar,
                style: ElevatedButton.styleFrom(
                  minimumSize: const Size(double.infinity, 48),
                ),
                child: _salvando
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Agendar Coleta'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
