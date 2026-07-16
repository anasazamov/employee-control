import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// API bazaviy manzili.
///
/// TODO: real domen + muhit bo'yicha --dart-define orqali konfiguratsiya
/// (dev/stage/prod). Endpoint yo'llari /v1 prefiksi bilan yoziladi,
/// masalan: POST /v1/auth/invite, POST /v1/auth/otp, POST /v1/checkins.
const String kApiBaseUrl = 'https://api.example.uz';

/// Auth-token uchun xavfsiz saqlash (Keystore / Keychain).
class TokenStore {
  const TokenStore(this._storage);

  final FlutterSecureStorage _storage;

  static const String _tokenKey = 'auth_token';

  Future<String?> read() => _storage.read(key: _tokenKey);

  Future<void> save(String token) => _storage.write(key: _tokenKey, value: token);

  Future<void> clear() => _storage.delete(key: _tokenKey);
}

final tokenStoreProvider = Provider<TokenStore>((ref) {
  // TODO: AndroidOptions(encryptedSharedPreferences: true) va iOS
  // accessibility opsiyalarini production'da aniq belgilash.
  return const TokenStore(FlutterSecureStorage());
});

/// Har so'rovga Bearer-token qo'shadigan interceptor.
class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._tokens);

  final TokenStore _tokens;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await _tokens.read();
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  // TODO: onError'da 401 -> token yangilash yoki sessiyani tozalab
  // /activation'ga qaytarish; oflayn xatolarda Drift navbatiga yozish.
}

/// Umumiy dio mijozi.
final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(
    BaseOptions(
      baseUrl: kApiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 20),
    ),
  );
  dio.interceptors.add(AuthInterceptor(ref.read(tokenStoreProvider)));
  // TODO: retry-interceptor (batch-ingestion idempotent, PLAN.md §8) va
  // faqat debug rejimda LogInterceptor qo'shish.
  return dio;
});
