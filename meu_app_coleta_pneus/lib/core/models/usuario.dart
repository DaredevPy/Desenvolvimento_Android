// lib/core/models/usuario.dart
class Usuario {
  final String id;
  final String nome;
  final String email;
  final String telefone;
  final String tipo; // 'cliente' ou 'prestador'
  final String? fotoPerfil;
  final DateTime dataCriacao;

  Usuario({
    required this.id,
    required this.nome,
    required this.email,
    required this.telefone,
    required this.tipo,
    this.fotoPerfil,
    DateTime? dataCriacao,
  }) : dataCriacao = dataCriacao ?? DateTime.now();

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'nome': nome,
      'email': email,
      'telefone': telefone,
      'tipo': tipo,
      'fotoPerfil': fotoPerfil,
      'dataCriacao': dataCriacao.toIso8601String(),
    };
  }

  factory Usuario.fromMap(Map<String, dynamic> map) {
    return Usuario(
      id: map['id'],
      nome: map['nome'],
      email: map['email'],
      telefone: map['telefone'],
      tipo: map['tipo'],
      fotoPerfil: map['fotoPerfil'],
      dataCriacao: map['dataCriacao'] != null 
        ? DateTime.parse(map['dataCriacao']) 
        : DateTime.now(),
    );
  }
}
