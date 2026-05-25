// lib/telas/cliente/tela_cliente_adicionar_pneu.dart
import 'package:flutter/material.dart';
import '../../models/pneu.dart';
import '../../services/cliente_service.dart';
import 'package:uuid/uuid.dart';

class TelaClienteAdicionarPneu extends StatefulWidget {
  final String clienteId;

  const TelaClienteAdicionarPneu({Key? key, required this.clienteId})
      : super(key: key);

  @override
  State<TelaClienteAdicionarPneu> createState() => _TelaClienteAdicionarPneuState();
}

class _TelaClienteAdicionarPneuState extends State<TelaClienteAdicionarPneu> {
  final _formKey = GlobalKey<FormState>();
  final _clienteService = ClienteService();

  String _tipoPneu = 'carro';
  int _quantidade = 4;
  String _endereco = '';

  final List<String> _tiposPneu = ['carro', 'moto', 'caminhão', 'trator'];

  Future<void> _salvarPneu() async {
    if (_formKey.currentState!.validate()) {
      _formKey.currentState!.save();

      final novoPneu = Pneu(
        id: Uuid().v4(),
        clienteId: widget.clienteId,
        tipo: _tipoPneu,
        quantidade: _quantidade,
        status: 'pendente',
        dataCriacao: DateTime.now(),
        endereco: _endereco,
      );

      try {
        await _clienteService.adicionarPneu(novoPneu);
        
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Pneu adicionado com sucesso!')),
        );
        Navigator.pop(context);
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erro: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Adicionar Pneu')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            children: [
              DropdownButtonFormField<String>(
                value: _tipoPneu,
                decoration: InputDecoration(labelText: 'Tipo de Pneu'),
                items: _tiposPneu.map((tipo) {
                  return DropdownMenuItem(value: tipo, child: Text(tipo));
                }).toList(),
                onChanged: (value) => setState(() => _tipoPneu = value!),
              ),
              TextFormField(
                decoration: InputDecoration(labelText: 'Quantidade'),
                keyboardType: TextInputType.number,
                initialValue: '4',
                onSaved: (value) => _quantidade = int.parse(value!),
                validator: (value) {
                  if (value == null || int.tryParse(value) == null) {
                    return 'Digite um número válido';
                  }
                  return null;
                },
              ),
              TextFormField(
                decoration: InputDecoration(labelText: 'Endereço'),
                onSaved: (value) => _endereco = value!,
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return 'Digite o endereço';
                  }
                  return null;
                },
              ),
              SizedBox(height: 20),
              ElevatedButton(
                onPressed: _salvarPneu,
                child: Text('Salvar'),
                style: ElevatedButton.styleFrom(minimumSize: Size(double.infinity, 50)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}