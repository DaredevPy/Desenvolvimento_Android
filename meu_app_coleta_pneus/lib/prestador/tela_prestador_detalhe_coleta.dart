import 'package:flutter/material.dart';

import '../core/api/api_service.dart';
import '../core/outbox/outbox_service.dart';
import 'tela_prestador_conferencia.dart';
import 'tela_prestador_resumo_coleta.dart';

/// Tela de detalhe de uma coleta do Prestador.
///
/// Exibe informações da coleta e permite avançar o status quando aplicável.
/// Transições suportadas: ACEITA → EM_DESLOCAMENTO, EM_DESLOCAMENTO → EM_CONFERENCIA.
class TelaPrestadorDetalheColeta extends StatefulWidget {
  const TelaPrestadorDetalheColeta({
    super.key,
    required this.api,
    required this.outbox,
    required this.coleta,
  });

  final ApiService api;
  final OutboxService outbox;
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

  @override
  void didUpdateWidget(TelaPrestadorDetalheColeta oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.coleta != widget.coleta) {
      _coleta = widget.coleta;
    }
  }

  String get _status => _coleta['status'] as String? ?? '';

  bool get _podeIniciarDeslocamento => _status == 'ACEITA';
  bool get _podeIniciarConferencia => _status == 'EM_DESLOCAMENTO';
  bool get _podeAbrirConferencia => _status == 'EM_CONFERENCIA';
  bool get _podeFinalizar => _status == 'CARREGADA';
  bool get _podeVerResumo => _status == 'FINALIZADA';

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

  Future<void> _iniciarConferencia() async {
    if (_processando) return;
    setState(() => _processando = true);

    try {
      final resultado = await widget.api.avancarStatus(
        _coleta['id'],
        'EM_CONFERENCIA',
      );
      if (!mounted) return;
      setState(() {
        _coleta = {..._coleta, ...resultado};
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Conferência iniciada!')),
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

  Future<void> _abrirConferencia() async {
    final resultado = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => TelaPrestadorConferencia(
          api: widget.api,
          outbox: widget.outbox,
          coleta: _coleta,
        ),
      ),
    );
    if (resultado == true && mounted) {
      setState(() {
        _coleta = {..._coleta, 'status': 'CARREGADA'};
      });
    }
  }

  void _abrirResumo() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => TelaPrestadorResumoColeta(
          api: widget.api,
          coleta: _coleta,
        ),
      ),
    );
  }

  Future<void> _finalizarColeta() async {
    if (_processando || !_podeFinalizar) return;
    setState(() => _processando = true);

    try {
      await widget.outbox.agendarFinalizacaoColeta(
        coletaId: _coleta['id'] as String,
      );
      if (!mounted) return;
      setState(() {
        _coleta = {..._coleta, 'status': 'FINALIZADA'};
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Coleta finalizada com sucesso!')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Erro ao agendar finalização.')),
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
            if (_podeIniciarConferencia)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _processando ? null : _iniciarConferencia,
                  icon: _processando
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.assignment),
                  label: const Text('Iniciar conferência'),
                ),
              ),
            if (_podeAbrirConferencia)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _abrirConferencia,
                  icon: const Icon(Icons.playlist_add_check),
                  label: const Text('Abrir conferência'),
                ),
              ),
            if (_podeFinalizar)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _processando ? null : _finalizarColeta,
                  icon: _processando
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.check_circle),
                  label: const Text('Finalizar coleta'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green,
                    foregroundColor: Colors.white,
                  ),
                ),
              ),
            if (_podeVerResumo)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _abrirResumo,
                  icon: const Icon(Icons.receipt_long),
                  label: const Text('Ver resumo da coleta'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blueGrey,
                    foregroundColor: Colors.white,
                  ),
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
