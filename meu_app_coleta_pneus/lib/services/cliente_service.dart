// lib/services/cliente_service.dart
import 'package:cloud_firestore/cloud_firestore.dart';
import '../models/pneu.dart';
import 'firebase_service.dart';

class ClienteService {
  final FirebaseService _firebaseService = FirebaseService();

  Future<void> adicionarPneu(Pneu pneu) async {
    try {
      await _firebaseService.pneus.doc(pneu.id).set(pneu.toMap());
    } catch (e) {
      throw Exception('Erro ao adicionar pneu: $e');
    }
  }

  Stream<List<Pneu>> listarMeusPneus(String clienteId) {
    return _firebaseService.pneus
        .where('clienteId', isEqualTo: clienteId)
        .orderBy('dataCriacao', descending: true)
        .snapshots()
        .map((snapshot) => snapshot.docs
            .map((doc) => Pneu.fromMap(doc.data() as Map<String, dynamic>))
            .toList());
  }
}