// lib/core/widgets/card_pneu.dart
import 'package:flutter/material.dart';
import '../models/pneu.dart';

class CardPneu extends StatelessWidget {
  final Pneu pneu;
  final VoidCallback? onStatusChanged;

  const CardPneu({
    Key? key,
    required this.pneu,
    this.onStatusChanged,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(8.0),
      child: ListTile(
        leading: CircleAvatar(
          child: Icon(Icons.tire_repair),
          backgroundColor: _getStatusColor(pneu.status),
        ),
        title: Text('${pneu.quantidade}x Pneu ${pneu.tipo}'),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Status: ${_getStatusText(pneu.status)}'),
            Text('Endereço: ${pneu.endereco}'),
            Text('Data: ${_formatDate(pneu.dataCriacao)}'),
          ],
        ),
        trailing: pneu.status == 'pendente'
            ? ElevatedButton(
                onPressed: onStatusChanged,
                child: Text('Iniciar Coleta'),
              )
            : null,
      ),
    );
  }

  Color _getStatusColor(String status) {
    switch (status) {
      case 'pendente':
        return Colors.orange;
      case 'coletado':
        return Colors.blue;
      case 'finalizado':
        return Colors.green;
      default:
        return Colors.grey;
    }
  }

  String _getStatusText(String status) {
    switch (status) {
      case 'pendente':
        return 'Aguardando coleta';
      case 'coletado':
        return 'Em coleta';
      case 'finalizado':
        return 'Finalizado';
      default:
        return status;
    }
  }

  String _formatDate(DateTime date) {
    return '${date.day}/${date.month}/${date.year} ${date.hour}:${date.minute}';
  }
}
