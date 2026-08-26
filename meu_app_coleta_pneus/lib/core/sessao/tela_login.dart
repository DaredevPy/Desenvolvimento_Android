import 'package:flutter/material.dart';

import 'servico_sessao.dart';

/// Tela de login mínima conectada ao [ServicoSessao].
///
/// Usa EXCLUSIVAMENTE [ServicoSessao.entrar()]. Não implementa nenhum
/// mecanismo adicional de autenticação. Após sucesso, navega para a
/// rota '/principal' (ou a definida em [rotaAposLogin]).
class TelaLogin extends StatefulWidget {
  const TelaLogin({
    super.key,
    required this.servicoSessao,
    this.rotaAposLogin = '/principal',
  });

  final ServicoSessao servicoSessao;
  final String rotaAposLogin;

  @override
  State<TelaLogin> createState() => _TelaLoginState();
}

class _TelaLoginState extends State<TelaLogin> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _senhaController = TextEditingController();
  bool _carregando = false;
  String? _erro;

  @override
  void dispose() {
    _emailController.dispose();
    _senhaController.dispose();
    super.dispose();
  }

  Future<void> _entrar() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _carregando = true;
      _erro = null;
    });

    try {
      await widget.servicoSessao.entrar(
        email: _emailController.text.trim(),
        senha: _senhaController.text,
      );
      if (mounted) {
        Navigator.pushReplacementNamed(context, widget.rotaAposLogin);
      }
    } on CredenciaisInvalidasExcecao {
      setState(() => _erro = 'E-mail ou senha inválidos.');
    } catch (e) {
      setState(() => _erro = 'Erro de conexão. Tente novamente.');
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Entrar')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.lock_outline, size: 64),
                const SizedBox(height: 32),
                TextFormField(
                  controller: _emailController,
                  decoration: const InputDecoration(
                    labelText: 'E-mail',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.email_outlined),
                  ),
                  keyboardType: TextInputType.emailAddress,
                  textInputAction: TextInputAction.next,
                  enabled: !_carregando,
                  validator: (v) {
                    if (v == null || v.trim().isEmpty) {
                      return 'Informe o e-mail';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _senhaController,
                  decoration: const InputDecoration(
                    labelText: 'Senha',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.lock_outlined),
                  ),
                  obscureText: true,
                  textInputAction: TextInputAction.done,
                  enabled: !_carregando,
                  onFieldSubmitted: (_) => _entrar(),
                  validator: (v) {
                    if (v == null || v.isEmpty) {
                      return 'Informe a senha';
                    }
                    return null;
                  },
                ),
                if (_erro != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    _erro!,
                    style: const TextStyle(color: Colors.red),
                    textAlign: TextAlign.center,
                  ),
                ],
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: ElevatedButton(
                    onPressed: _carregando ? null : _entrar,
                    child: _carregando
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Entrar'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
