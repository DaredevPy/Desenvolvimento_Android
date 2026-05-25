import 'package:flutter_test/flutter_test.dart';

void main() {
  group('App Basic Tests', () {
    test('Teste 1: Verificar se 2 + 2 = 4', () {
      expect(2 + 2, equals(4));
    });

    test('Teste 2: Verificar String vazia', () {
      final String vazia = '';
      expect(vazia.isEmpty, isTrue);
    });

    test('Teste 3: Verificar lista não vazia', () {
      final List<int> numeros = [1, 2, 3];
      expect(numeros.length, equals(3));
    });

    test('Teste 4: Verificar booleano verdadeiro', () {
      final bool ativo = true;
      expect(ativo, isTrue);
    });
  });
}
