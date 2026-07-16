import 'dart:convert';

import '../../app/router.dart';

/// JWT payload'ini imzo-tekshiruvsiz dekodlaydi (rol/org uchun — server baribir
/// har so'rovda tokenni tasdiqlaydi; bu faqat UI uchun). Xato bo'lsa null.
Map<String, dynamic>? decodeJwtPayload(String token) {
  try {
    final parts = token.split('.');
    if (parts.length != 3) return null;
    var payload = parts[1].replaceAll('-', '+').replaceAll('_', '/');
    switch (payload.length % 4) {
      case 2:
        payload += '==';
      case 3:
        payload += '=';
    }
    return jsonDecode(utf8.decode(base64.decode(payload))) as Map<String, dynamic>;
  } catch (_) {
    return null;
  }
}

/// JWT `role` claim'idan ilova-rolini aniqlaydi (PLAN.md §10: rahbar rejimini
/// server hal qiladi). org_admin/hr/dept_head -> manager; field_employee -> xodim.
UserRole roleFromToken(String token) {
  final role = decodeJwtPayload(token)?['role'] as String?;
  return switch (role) {
    'org_admin' || 'hr' || 'dept_head' => UserRole.manager,
    _ => UserRole.fieldEmployee,
  };
}
