import 'dart:convert';

import 'package:http/http.dart' as http;

/// Aktivatsiya API mijozi (docs/API.md §Auth): invite resolve -> OTP -> activate.
/// Org yuz/OTP'dan OLDIN invite orqali aniqlanadi (PLAN.md §7).
class AuthApi {
  AuthApi({required this.baseUrl, http.Client? client})
      : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;

  Map<String, String> get _json => const {'Content-Type': 'application/json'};

  /// POST /v1/auth/invites/resolve — token -> {org_id, org_name, masked_phone}.
  Future<ResolvedInvite> resolveInvite(String token) async {
    final res = await _client.post(
      Uri.parse('$baseUrl/v1/auth/invites/resolve'),
      headers: _json,
      body: jsonEncode({'token': token}),
    );
    if (res.statusCode >= 400) {
      throw AuthApiException('invites/resolve', res.statusCode, res.body);
    }
    final j = jsonDecode(res.body) as Map<String, dynamic>;
    return ResolvedInvite(
      orgId: j['org_id'] as String,
      orgName: j['org_name'] as String,
      maskedPhone: j['masked_phone'] as String?,
    );
  }

  /// POST /v1/auth/otp/request — SMS OTP yuboradi. Staging (DEBUG=true) `dev_code`
  /// qaytaradi; prod'da null (faqat SMS).
  Future<String?> requestOtp(String token) async {
    final res = await _client.post(
      Uri.parse('$baseUrl/v1/auth/otp/request'),
      headers: _json,
      body: jsonEncode({'token': token}),
    );
    if (res.statusCode >= 400) {
      throw AuthApiException('otp/request', res.statusCode, res.body);
    }
    final j = jsonDecode(res.body) as Map<String, dynamic>;
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
    final res = await _client.post(
      Uri.parse('$baseUrl/v1/auth/activate'),
      headers: _json,
      body: jsonEncode({
        'token': token,
        'otp_code': otpCode,
        'device': {
          'platform': platform,
          'fingerprint': deviceFingerprint,
          if (model != null) 'model': model,
        },
      }),
    );
    if (res.statusCode >= 400) {
      throw AuthApiException('activate', res.statusCode, res.body);
    }
    final j = jsonDecode(res.body) as Map<String, dynamic>;
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
