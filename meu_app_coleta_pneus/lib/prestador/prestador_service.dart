// lib/prestador/prestador_service.dart
import 'package:cloud_firestore/cloud_firestore.dart';
import '../core/models/pneu.dart';
import '../core/services/firebase_service.dart';

class PrestadorService {
  final FirebaseService _firebaseService = FirebaseService();

  Stream<List<Pneu>> listarPneusPendentes() {
    return _firebaseService.pneus
        .where('status', isEqualTo: 'pendente')
        .orderBy('dataCriacao', descending: true)
        .snapshots()
        .map((snapshot) => snapshot.docs
            .map((doc) => Pneu.fromMap(doc.data() as Map<String, dynamic>))
            .toList());
  }

  Future<void> atualizarStatusPneu(String pneuId, String novoStatus) async {
    try {
      await _firebaseService.pneus.doc(pneuId).update({
        'status': novoStatus,
        'dataAtualizacao': FieldValue.serverTimestamp(),
      });
    } catch (e) {
      throw Exception('Erro ao atualizar status: $e');
    }
  }
}
