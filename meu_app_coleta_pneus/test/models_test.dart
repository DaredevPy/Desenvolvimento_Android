import 'package:flutter_test/flutter_test.dart';
import 'package:meu_app_coleta_pneus/core/models/usuario.dart';
import 'package:meu_app_coleta_pneus/core/models/pneu.dart';

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

  group('Testes do Modelo Pneu', () {
    test('Criar pneu com dados válidos', () {
      final pneu = Pneu(
        id: '789',
        clienteId: '123',
        tipo: 'aro-16',
        quantidade: 4,
        status: 'pendente',
        dataCriacao: DateTime.now(),
        endereco: 'Rua das Flores, 123',
      );

      expect(pneu.id, equals('789'));
      expect(pneu.clienteId, equals('123'));
      expect(pneu.tipo, equals('aro-16'));
      expect(pneu.quantidade, equals(4));
    });

    test('Verificar endereco não vazio', () {
      final pneu = Pneu(
        id: '999',
        clienteId: '456',
        tipo: 'aro-15',
        quantidade: 2,
        status: 'coletado',
        dataCriacao: DateTime.now(),
        endereco: 'Avenida Principal, 456',
      );

      expect(pneu.endereco.isNotEmpty, isTrue);
    });

    test('Verificar status válido do pneu', () {
      final pneu = Pneu(
        id: '111',
        clienteId: '789',
        tipo: 'aro-17',
        quantidade: 1,
        status: 'finalizado',
        dataCriacao: DateTime.now(),
        endereco: 'Rua do Bairro, 789',
      );

      final statusValidos = ['pendente', 'coletado', 'finalizado'];
      expect(statusValidos.contains(pneu.status), isTrue);
    });

    test('Converter pneu para Map', () {
      final agora = DateTime.now();
      final pneu = Pneu(
        id: '222',
        clienteId: '333',
        tipo: 'aro-18',
        quantidade: 3,
        status: 'pendente',
        dataCriacao: agora,
        endereco: 'Rua Teste, 999',
      );

      final map = pneu.toMap();
      expect(map['id'], equals('222'));
      expect(map['quantidade'], equals(3));
    });
  });
}
