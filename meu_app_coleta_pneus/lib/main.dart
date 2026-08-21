// lib/main.dart
import 'package:flutter/material.dart';
import 'core/services/firebase_service.dart';
import 'cliente/tela_cliente_adicionar_pneu.dart';
import 'prestador/tela_prestador_listar_pendentes.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  final firebaseService = FirebaseService();
  await firebaseService.init();
  
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Coleta de Pneus',
      theme: ThemeData(primarySwatch: Colors.green),
      home: TelaPrincipal(),
    );
  }
}

class TelaPrincipal extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Coleta de Pneus')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ElevatedButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => const TelaClienteAdicionarPneu(clienteId: 'cliente123'),
                  ),
                );
              },
              style: ElevatedButton.styleFrom(minimumSize: const Size(200, 50)),
              child: const Text('Sou Cliente'),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => TelaPrestadorListarPendentes(),
                  ),
                );
              },
              style: ElevatedButton.styleFrom(minimumSize: const Size(200, 50)),
              child: const Text('Sou Prestador'),
            ),
          ],
        ),
      ),
    );
  }
}