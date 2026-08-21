// lib/core/models/pneu.dart
class Pneu {
  final String id;
  final String clienteId;
  final String tipo;
  final int quantidade;
  final String status; // 'pendente', 'coletado', 'finalizado'
  final DateTime dataCriacao;
  final String endereco;
  final double? latitude;
  final double? longitude;

  Pneu({
    required this.id,
    required this.clienteId,
    required this.tipo,
    required this.quantidade,
    required this.status,
    required this.dataCriacao,
    required this.endereco,
    this.latitude,
    this.longitude,
  });

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'clienteId': clienteId,
      'tipo': tipo,
      'quantidade': quantidade,
      'status': status,
      'dataCriacao': dataCriacao.toIso8601String(),
      'endereco': endereco,
      'latitude': latitude,
      'longitude': longitude,
    };
  }

  factory Pneu.fromMap(Map<String, dynamic> map) {
    return Pneu(
      id: map['id'],
      clienteId: map['clienteId'],
      tipo: map['tipo'],
      quantidade: map['quantidade'],
      status: map['status'],
      dataCriacao: DateTime.parse(map['dataCriacao']),
      endereco: map['endereco'],
      latitude: map['latitude'],
      longitude: map['longitude'],
    );
  }
}
