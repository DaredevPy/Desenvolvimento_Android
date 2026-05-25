// lib/telas/prestador/tela_prestador_listar_pendentes.dart
import 'package:flutter/material.dart';
import '../../services/prestador_service.dart';
import '../../widgets/card_pneu.dart';

class TelaPrestadorListarPendentes extends StatelessWidget {
  final prestadorService = PrestadorService();

  TelaPrestadorListarPendentes({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Pneus Pendentes'),
        backgroundColor: Colors.orange,
      ),
      body: StreamBuilder(
        stream: prestadorService.listarPneusPendentes(),
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return Center(child: Text('Erro: ${snapshot.error}'));
          }

          if (snapshot.connectionState == ConnectionState.waiting) {
            return Center(child: CircularProgressIndicator());
          }

          final pneus = snapshot.data ?? [];

          if (pneus.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.check_circle, size: 64, color: Colors.green),
                  SizedBox(height: 16),
                  Text('Nenhum pneu pendente'),
                ],
              ),
            );
          }

          return ListView.builder(
            itemCount: pneus.length,
            itemBuilder: (context, index) {
              final pneu = pneus[index];
              return CardPneu(
                pneu: pneu,
                onStatusChanged: () => _iniciarColeta(context, pneu.id),
              );
            },
          );
        },
      ),
    );
  }

  void _iniciarColeta(BuildContext context, String pneuId) async {
    try {
      await prestadorService.atualizarStatusPneu(pneuId, 'coletado');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Coleta iniciada!')),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Erro: $e')),
      );
    }
  }
}