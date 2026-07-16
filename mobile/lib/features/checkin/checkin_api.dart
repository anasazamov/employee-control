import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

/// POST /v1/checkins/selfie-url javobi — presigned MinIO PUT (docs/API.md).
class SelfieUpload {
  const SelfieUpload({
    required this.url,
    required this.objectKey,
    required this.bucket,
  });

  /// Presigned PUT URL'i (ochiq MinIO xostiga ishora qiladi).
  final String url;

  /// Obyekt kaliti — keyin check-in'da `selfie_key` sifatida yuboriladi.
  final String objectKey;
  final String bucket;

  factory SelfieUpload.fromJson(Map<String, dynamic> j) => SelfieUpload(
        url: j['url'] as String,
        objectKey: (j['object_key'] ?? j['objectKey']) as String,
        bucket: (j['bucket'] ?? '') as String,
      );
}

/// POST /v1/checkins javobi (CheckinOut, docs/API.md). Server yuz-hukmi shu
/// yerda: `verdict` (pending|verified|flagged|rejected) va `risk_score`.
/// `server_face_score` — yuz-worker qo'ygan ball (dastlab bo'lmasligi mumkin).
class CheckinResult {
  const CheckinResult({
    this.id,
    this.verdict,
    this.riskScore,
    this.verdictReasons = const [],
    this.serverFaceScore,
    this.insideGeofence,
    this.duplicate,
  });

  final String? id;
  final String? verdict;
  final num? riskScore;
  final List<String> verdictReasons;
  final num? serverFaceScore;
  final bool? insideGeofence;
  final bool? duplicate;

  factory CheckinResult.fromJson(Map<String, dynamic> j) => CheckinResult(
        id: j['id']?.toString(),
        verdict: j['verdict'] as String?,
        riskScore: j['risk_score'] as num?,
        verdictReasons: (j['verdict_reasons'] as List?)
                ?.map((e) => e.toString())
                .toList(growable: false) ??
            const [],
        serverFaceScore:
            (j['server_face_score'] ?? j['face_score'] ?? j['face_match_score'])
                as num?,
        insideGeofence: j['inside_geofence'] as bool?,
        duplicate: j['duplicate'] as bool?,
      );
}

/// Check-in tarmoq-oqimidagi xatolik (bosqich + HTTP status + tan matni).
class CheckinApiException implements Exception {
  CheckinApiException(this.stage, this.statusCode, this.body);

  final String stage;
  final int statusCode;
  final String body;

  @override
  String toString() =>
      'CheckinApiException($stage: HTTP $statusCode ${body.isEmpty ? '' : '— $body'})';
}

/// Check-in yuborish uchun mijoz: selfie-url -> presigned PUT -> checkins POST
/// (docs/API.md). Presigned PUT'ga Authorization *qo'shilmaydi* (MinIO imzosini
/// buzmaslik uchun).
class CheckinApi {
  CheckinApi({
    required this.baseUrl,
    required this.tokenReader,
    http.Client? client,
  }) : _client = client ?? http.Client();

  final String baseUrl;

  /// Auth-token manbai (flutter_secure_storage). Null bo'lsa — sarlavhasiz.
  final Future<String?> Function() tokenReader;

  final http.Client _client;

  Future<Map<String, String>> _authHeaders() async {
    final token = await tokenReader();
    return {
      'Content-Type': 'application/json',
      if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',
    };
  }

  /// POST /v1/checkins/selfie-url — presigned PUT manzilini oladi.
  Future<SelfieUpload> requestSelfieUrl() async {
    final res = await _client
        .post(
          Uri.parse('$baseUrl/v1/checkins/selfie-url'),
          headers: await _authHeaders(),
        )
        .timeout(const Duration(seconds: 15));
    if (res.statusCode >= 400) {
      throw CheckinApiException('selfie-url', res.statusCode, res.body);
    }
    return SelfieUpload.fromJson(
        jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// Selfie JPEG baytlarini presigned URL'ga to'g'ridan-to'g'ri PUT qiladi.
  Future<void> putSelfie(String url, Uint8List jpegBytes) async {
    final res = await _client
        .put(
          Uri.parse(url),
          headers: const {'Content-Type': 'image/jpeg'},
          body: jpegBytes,
        )
        .timeout(const Duration(seconds: 30));
    if (res.statusCode >= 400) {
      throw CheckinApiException('selfie-put', res.statusCode, res.body);
    }
  }

  /// POST /v1/checkins — server yuz-tekshiruvini ishga tushiradi. Idempotent
  /// (`checkin_id`).
  Future<CheckinResult> submitCheckin({
    required String checkinId,
    required String ts,
    required String selfieKey,
    required bool localMatch,
    required bool livenessPassed,
    double? lat,
    double? lon,
    double? accuracyM,
    String? siteId,
    String? comment,
    Map<String, dynamic>? deviceIntegrity,
  }) async {
    final body = <String, dynamic>{
      'checkin_id': checkinId,
      'ts': ts,
      if (lat != null) 'lat': lat,
      if (lon != null) 'lon': lon,
      if (accuracyM != null) 'accuracy_m': accuracyM,
      if (siteId != null) 'site_id': siteId,
      if (comment != null && comment.isNotEmpty) 'comment': comment,
      'selfie_key': selfieKey,
      'face': {
        'local_match': localMatch,
        'liveness_passed': livenessPassed,
      },
      if (deviceIntegrity != null) 'device_integrity': deviceIntegrity,
    };
    final res = await _client
        .post(
          Uri.parse('$baseUrl/v1/checkins'),
          headers: await _authHeaders(),
          body: jsonEncode(body),
        )
        .timeout(const Duration(seconds: 25));
    if (res.statusCode >= 400) {
      throw CheckinApiException('checkins', res.statusCode, res.body);
    }
    return CheckinResult.fromJson(
        jsonDecode(res.body) as Map<String, dynamic>);
  }

  void close() => _client.close();
}

/// `checkin_id` uchun RFC 4122 v4 UUID (idempotentlik kaliti) — qo'shimcha
/// paketsiz, Random.secure() bilan.
String generateUuidV4() {
  final rng = Random.secure();
  final b = List<int>.generate(16, (_) => rng.nextInt(256));
  b[6] = (b[6] & 0x0f) | 0x40; // version 4
  b[8] = (b[8] & 0x3f) | 0x80; // variant 10xx
  String h(int start, int end) {
    final sb = StringBuffer();
    for (var i = start; i < end; i++) {
      sb.write(b[i].toRadixString(16).padLeft(2, '0'));
    }
    return sb.toString();
  }

  return '${h(0, 4)}-${h(4, 6)}-${h(6, 8)}-${h(8, 10)}-${h(10, 16)}';
}
