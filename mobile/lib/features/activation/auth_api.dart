import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

/// Aktivatsiya API mijozi (docs/API.md §Auth): invite resolve -> OTP -> activate.
/// Org yuz/OTP'dan OLDIN invite orqali aniqlanadi (PLAN.md §7).
class AuthApi {
  AuthApi({required this.baseUrl, http.Client? client, Duration? timeout})
      : _client = client ?? http.Client(),
        _timeout = timeout ?? const Duration(seconds: 15);

  final String baseUrl;
  final http.Client _client;
  final Duration _timeout;

  /// POST + timeout + xato-normalizatsiya (cheksiz osilib qolmaslik uchun).
  Future<Map<String, dynamic>> _post(String stage, String path, Object body) async {
    try {
      final res = await _client
          .post(
            Uri.parse('$baseUrl$path'),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode(body),
          )
          .timeout(_timeout);
      if (res.statusCode >= 400) {
        throw AuthApiException(stage, res.statusCode, res.body);
      }
      return jsonDecode(res.body) as Map<String, dynamic>;
    } on TimeoutException {
      throw AuthApiException(stage, 0, 'server javob bermadi (vaqt tugadi)');
    } on SocketException catch (e) {
      throw AuthApiException(stage, 0, 'serverga ulanib bo\'lmadi: ${e.message}');
    } on http.ClientException catch (e) {
      throw AuthApiException(stage, 0, e.message);
    }
  }

  /// POST /v1/auth/invites/resolve — token -> {org_id, org_name, masked_phone}.
  Future<ResolvedInvite> resolveInvite(String token) async {
    final j = await _post('invites/resolve', '/v1/auth/invites/resolve', {'token': token});
    return ResolvedInvite(
      orgId: j['org_id'] as String,
      orgName: j['org_name'] as String,
      maskedPhone: j['masked_phone'] as String?,
    );
  }

  /// POST /v1/auth/otp/request — SMS OTP yuboradi. Staging (DEBUG=true) `dev_code`
  /// qaytaradi; prod'da null (faqat SMS).
  Future<String?> requestOtp(String token) async {
    final j = await _post('otp/request', '/v1/auth/otp/request', {'token': token});
    return j['dev_code'] as String?;
  }

  /// POST /v1/auth/activate — OTP + qurilma-bog'lash -> JWT + user.
  Future<ActivationResult> activate({
    required String token,
    required String otpCode,
    required String deviceFingerprint,
    String platform = 'android',
    String? model,
  }) async {
    final j = await _post('activate', '/v1/auth/activate', {
      'token': token,
      'otp_code': otpCode,
      'device': {
        'platform': platform,
        'fingerprint': deviceFingerprint,
        if (model != null) 'model': model,
      },
    });
    final user = (j['user'] as Map<String, dynamic>?) ?? const {};
    return ActivationResult(
      accessToken: j['access_token'] as String,
      refreshToken: j['refresh_token'] as String?,
      role: user['role'] as String?,
      orgName: user['org_name'] as String?,
    );
  }

  void close() => _client.close();
}

class ResolvedInvite {
  const ResolvedInvite({
    required this.orgId,
    required this.orgName,
    this.maskedPhone,
  });

  final String orgId;
  final String orgName;
  final String? maskedPhone;
}

class ActivationResult {
  const ActivationResult({
    required this.accessToken,
    this.refreshToken,
    this.role,
    this.orgName,
  });

  final String accessToken;
  final String? refreshToken;
  final String? role;
  final String? orgName;
}

class AuthApiException implements Exception {
  AuthApiException(this.stage, this.statusCode, this.body);

  final String stage;
  final int statusCode;
  final String body;

  /// Server `{"detail": "..."}` xabarini ajratib oladi (foydalanuvchiga ko'rsatish).
  String get detail {
    try {
      final j = jsonDecode(body) as Map<String, dynamic>;
      return (j['detail'] ?? body).toString();
    } catch (_) {
      return body;
    }
  }

  @override
  String toString() => 'AuthApiException($stage: HTTP $statusCode — $detail)';
}
