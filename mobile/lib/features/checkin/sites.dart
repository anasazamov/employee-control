import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';

/// Obyekt (site) — GET /v1/sites (docs/API.md). Faqat kerakli maydonlar.
class Site {
  const Site({
    required this.id,
    required this.name,
    required this.lat,
    required this.lon,
    required this.radiusM,
  });

  final String id;
  final String name;
  final double lat;
  final double lon;
  final int radiusM;

  factory Site.fromJson(Map<String, dynamic> j) => Site(
        id: j['id'] as String,
        name: j['name'] as String,
        lat: (j['lat'] as num).toDouble(),
        lon: (j['lon'] as num).toDouble(),
        radiusM: (j['radius_m'] as num?)?.toInt() ?? 150,
      );

  /// Berilgan nuqtagacha taxminiy masofa (metr, haversine).
  int distanceMeters(double fromLat, double fromLon) {
    const r = 6371000.0;
    double rad(double d) => d * pi / 180;
    final dLat = rad(lat - fromLat);
    final dLon = rad(lon - fromLon);
    final a = sin(dLat / 2) * sin(dLat / 2) +
        cos(rad(fromLat)) * cos(rad(lat)) * sin(dLon / 2) * sin(dLon / 2);
    return (2 * r * asin(sqrt(a))).round();
  }
}

/// Org obyektlari (autentifikatsiyalangan). dio interceptor tokenni qo'shadi.
final sitesProvider = FutureProvider.autoDispose<List<Site>>((ref) async {
  final dio = ref.read(dioProvider);
  final res = await dio.get<List<dynamic>>('/v1/sites');
  return (res.data ?? [])
      .map((e) => Site.fromJson(e as Map<String, dynamic>))
      .toList(growable: false);
});
