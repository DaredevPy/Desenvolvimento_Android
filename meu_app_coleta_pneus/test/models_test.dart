import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/core/models/usuario.dart';

void main() {
  group('Testes do Modelo Usuário', () {
    test('Criar usuário com dados válidos', () {
      final usuario = Usuario(
        id: '123',
        nome: 'João Silva',
        email: 'joao@example.com',
        telefone: '11999999999',
        tipo: 'cliente',
      );

      expect(usuario.id, equals('123'));
      expect(usuario.nome, equals('João Silva'));
      expect(usuario.email, equals('joao@example.com'));
      expect(usuario.tipo, equals('cliente'));
    });

    test('Verificar se email é válido', () {
      final usuario = Usuario(
        id: '456',
        nome: 'Maria',
        email: 'maria@test.com',
        telefone: '11988888888',
        tipo: 'prestador',
      );

      expect(usuario.email.contains('@'), isTrue);
    });

    test('Converter usuário para Map', () {
      final usuario = Usuario(
        id: '789',
        nome: 'Pedro',
        email: 'pedro@example.com',
        telefone: '11987654321',
        tipo: 'cliente',
      );

      final map = usuario.toMap();
      expect(map['id'], equals('789'));
      expect(map['nome'], equals('Pedro'));
    });

    test('Criar usuário a partir de Map', () {
      final map = {
        'id': '999',
        'nome': 'Ana',
        'email': 'ana@example.com',
        'telefone': '11912345678',
        'tipo': 'prestador',
        'fotoPerfil': null,
        'dataCriacao': DateTime.now().toIso8601String(),
      };

      final usuario = Usuario.fromMap(map);
      expect(usuario.id, equals('999'));
      expect(usuario.nome, equals('Ana'));
    });
  });
}
