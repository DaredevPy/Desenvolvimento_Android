import 'package:flutter/material.dart';

import '../core/api/api_service.dart';

/// Tela de detalhe de uma coleta do Prestador.
///
/// Exibe informações da coleta e permite avançar o status quando aplicável.
/// Transições suportadas: ACEITA → EM_DESLOCAMENTO.
/// Conferência (EM_DESLOCAMENTO → EM_CONFERENCIA) será implementada em missão futura.
class TelaPrestadorDetalheColeta extends StatefulWidget {
  const TelaPrestadorDetalheColeta({
    super.key,
    required this.api,
    required this.coleta,
  });

  final ApiService api;
  final Map<String, dynamic> coleta;

  @override
  State<TelaPrestadorDetalheColeta> createState() =>
      _TelaPrestadorDetalheColetaState();
}

class _TelaPrestadorDetalheColetaState
    extends State<TelaPrestadorDetalheColeta> {
  late Map<String, dynamic> _coleta;
  bool _processando = false;

  @override
  void initState() {
    super.initState();
    _coleta = widget.coleta;
  }

  String get _status => _coleta['status'] as String? ?? '';

  bool get _podeIniciarDeslocamento => _status == 'ACEITA';

  Future<void> _iniciarDeslocamento() async {
    if (_processando) return;
    setState(() => _processando = true);

    try {
      final resultado = await widget.api.avancarStatus(
        _coleta['id'],
        'EM_DESLOCAMENTO',
      );
      if (!mounted) return;
      setState(() {
        _coleta = {..._coleta, ...resultado};
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Deslocamento iniciado!')),
      );
    } on Exception catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(_mensagemErro(e))),
      );
    } finally {
      if (mounted) setState(() => _processando = false);
    }
  }

  String _mensagemErro(Exception e) {
    final texto = e.toString();
    if (texto.contains('Erro HTTP 401')) return 'Sessão expirada. Faça login novamente.';
    if (texto.contains('Erro HTTP 403')) return 'Acesso negado para este perfil.';
    if (texto.contains('Erro HTTP 404')) return 'Coleta ou perfil não encontrado.';
    if (texto.contains('Erro HTTP 409')) return 'Transição inválida. Status atual pode ter mudado.';
    return 'Erro de conexão. Tente novamente.';
  }

  String _rotuloStatus(String status) {
    const mapa = {
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
      case 'CANCELADA':
      case 'CONTESTADA':
        return Colors.red;
      default:
        return Colors.grey;
    }
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
    final rua = endereco['rua'] ?? endereco['logradouro'] ?? '';
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

  @override
  Widget build(BuildContext context) {
    final itens = _coleta['itens'] as List? ?? [];
    final endereco = _coleta['endereco_origem_json'] as Map<String, dynamic>? ?? {};

    return Scaffold(
      appBar: AppBar(
        title: Text(_coleta['codigo_identificador'] ?? 'Detalhe'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    _coleta['codigo_identificador'] ?? '',
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
            _secao(context, 'Endereço de origem', _logradouro(endereco)),
            const SizedBox(height: 8),
            _secao(context, 'Data agendada', _formatarData(_coleta['data_agendada'])),
            const SizedBox(height: 8),
            _secao(context, 'Criado em', _formatarData(_coleta['criado_em'])),
            const SizedBox(height: 16),
            Text('Itens declarados', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            if (itens.isEmpty)
              const Text('Nenhum item declarado')
            else
              ...itens.map((item) => Card(
                    margin: const EdgeInsets.only(bottom: 4),
                    child: ListTile(
                      title: Text('${item['marca']} ${item['dimensao']}'),
                      subtitle: Text('Qtd: ${item['quantidade_declarada']}'),
                      dense: true,
                    ),
                  )),
            const SizedBox(height: 24),
            if (_podeIniciarDeslocamento)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _processando ? null : _iniciarDeslocamento,
                  icon: _processando
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.directions_car),
                  label: const Text('Iniciar deslocamento'),
                ),
              ),
          ],
        ),
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
