// lib/main.dart
import 'package:flutter/material.dart';
import 'services/firebase_service.dart';
import 'telas/cliente/tela_cliente_adicionar_pneu.dart';
import 'telas/prestador/tela_prestador_listar_pendentes.dart';

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
      appBar: AppBar(title: Text('Coleta de Pneus')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ElevatedButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => TelaClienteAdicionarPneu(clienteId: 'cliente123'),
                  ),
                );
              },
              child: Text('Sou Cliente'),
              style: ElevatedButton.styleFrom(minimumSize: Size(200, 50)),
            ),
            SizedBox(height: 20),
            ElevatedButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => TelaPrestadorListarPendentes(),
                  ),
                );
              },
              child: Text('Sou Prestador'),
              style: ElevatedButton.styleFrom(minimumSize: Size(200, 50)),
            ),
          ],
        ),
      ),
    );
  }
}