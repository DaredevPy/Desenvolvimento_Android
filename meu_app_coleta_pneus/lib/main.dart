import 'package:flutter/material.dart';

import 'core/api/api_service.dart';
import 'core/outbox/outbox_service.dart';
import 'core/outbox/sincronizacao_automatica_outbox.dart';
import 'core/sessao/armazenamento_seguro_sessao.dart';
import 'core/sessao/servico_sessao.dart';
import 'core/sessao/tela_login.dart';
import 'cliente/screens/tela_cliente_minhas_coletas.dart';
import 'prestador/tela_prestador_listar_pendentes.dart';
import 'prestador/tela_prestador_minhas_coletas.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final baseUrlApi = const String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  final sessao = ServicoSessao(
    armazenamento: ArmazenamentoSeguroSessao(),
    baseUrl: baseUrlApi,
  );
  await sessao.carregar();

  final outbox = OutboxService(
    baseUrl: baseUrlApi,
    obterToken: () => sessao.tokenAtual,
  );
  SincronizacaoAutomaticaOutbox(outbox: outbox).iniciar();

  final api = ApiService(
    baseUrl: baseUrlApi,
    obterToken: () => sessao.tokenAtual,
  );

  runApp(MyApp(sessao: sessao, outbox: outbox, api: api));
}

class MyApp extends StatelessWidget {
  const MyApp({
    super.key,
    required this.sessao,
    required this.outbox,
    required this.api,
  });

  final ServicoSessao sessao;
  final OutboxService outbox;
  final ApiService api;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Coleta de Pneus',
      theme: ThemeData(primarySwatch: Colors.green),
      initialRoute: sessao.tokenAtual != null ? '/principal' : '/login',
      routes: {
        '/login': (_) => TelaLogin(servicoSessao: sessao),
        '/principal': (_) => TelaPrincipal(
              sessao: sessao,
              outbox: outbox,
              api: api,
            ),
      },
    );
  }
}

class TelaPrincipal extends StatelessWidget {
  const TelaPrincipal({
    super.key,
    required this.sessao,
    required this.outbox,
    required this.api,
  });

  final ServicoSessao sessao;
  final OutboxService outbox;
  final ApiService api;

  Future<void> _sair(BuildContext context) async {
    await sessao.sair();
    if (context.mounted) {
      Navigator.pushReplacementNamed(context, '/login');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Coleta de Pneus'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Sair',
            onPressed: () => _sair(context),
          ),
        ],
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ElevatedButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => TelaClienteMinhasColetas(
                      api: api,
                      outbox: outbox,
                    ),
                  ),
                );
              },
              style: ElevatedButton.styleFrom(
                minimumSize: const Size(200, 50),
              ),
              child: const Text('Sou Cliente'),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => TelaPrestadorListarPendentes(
                      api: api,
                    ),
                  ),
                );
              },
              style: ElevatedButton.styleFrom(
                minimumSize: const Size(200, 50),
              ),
              child: const Text('Coletas Disponíveis'),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => TelaPrestadorMinhasColetas(
                      api: api,
                    ),
                  ),
                );
              },
              style: ElevatedButton.styleFrom(
                minimumSize: const Size(200, 50),
              ),
              child: const Text('Minhas Coletas'),
            ),
          ],
        ),
      ),
    );
  }
}
