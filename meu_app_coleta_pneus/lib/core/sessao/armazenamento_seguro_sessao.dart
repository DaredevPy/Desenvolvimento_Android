import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'servico_sessao.dart';

/// Implementação de [ArmazenamentoSessao] sobre flutter_secure_storage:
/// Android Keystore (EncryptedSharedPreferences), iOS Keychain e
/// flutter_secure_storage_web no alvo Web (o navegador não oferece
/// armazenamento verdadeiramente seguro; o plugin cifra o valor em
/// localStorage — melhor esforço documentado, pendência registrada).
class ArmazenamentoSeguroSessao implements ArmazenamentoSessao {
  ArmazenamentoSeguroSessao({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  static const _chaveToken = 'sessao_access_token';

  final FlutterSecureStorage _storage;

  @override
  Future<void> salvar(String token) =>
      _storage.write(key: _chaveToken, value: token);

  @override
  Future<String?> ler() => _storage.read(key: _chaveToken);

  @override
  Future<void> remover() => _storage.delete(key: _chaveToken);
}
