import 'dart:math';

/// Qurilmadagi liveness ("jonli yuz") challenge'lari — foto-of-a-foto hujumiga
/// qarshi (PLAN.md §6). Har bir challenge ML Kit yuz-atributlaridagi *dinamik
/// o'zgarishni* talab qiladi (statik surat o'ta olmaydi):
///
/// - [blink]      — ikkala ko'z ochiq -> yumilgan -> yana ochiq (prob pasayib, ko'tariladi)
/// - [turnLeft]   — bosh chapga buriladi (headEulerAngleY musbat chegaradan oshadi)
/// - [turnRight]  — bosh o'ngga buriladi (headEulerAngleY manfiy chegaradan oshadi)
/// - [smile]      — neytral -> tabassum (smilingProbability keskin ko'tariladi)
enum LivenessChallenge { blink, turnLeft, turnRight, smile }

/// Bitta kadrdan olingan yuz-signallari (ML Kit `Face`'dan chiqariladi).
class FaceSignals {
  const FaceSignals({
    this.faceCount = 0,
    this.faceWidthRatio = 0,
    this.leftEyeOpen,
    this.rightEyeOpen,
    this.smiling,
    this.headYaw,
  });

  /// Kadrda topilgan yuzlar soni (sifat-nazorati: aynan 1 bo'lishi kerak).
  final int faceCount;

  /// Yuz ramkasi kengligining kadr qisqa tomoniga nisbati (0..1) — yaqinlik.
  final double faceWidthRatio;

  /// Chap ko'z ochiqlik ehtimoli (0..1), classification yoqilганda.
  final double? leftEyeOpen;

  /// O'ng ko'z ochiqlik ehtimoli (0..1).
  final double? rightEyeOpen;

  /// Tabassum ehtimoli (0..1).
  final double? smiling;

  /// Boshning vertikal o'q atrofidagi burilishi (gradus). Musbat — bir tomon,
  /// manfiy — qarama-qarshi tomon (old kamerada oyna-aks bo'lishi mumkin).
  final double? headYaw;

  /// Ikkala ko'zdan eng pastini qaytaradi (blink aniqlash uchun).
  double? get minEyeOpen {
    final l = leftEyeOpen;
    final r = rightEyeOpen;
    if (l == null && r == null) return null;
    if (l == null) return r;
    if (r == null) return l;
    return min(l, r);
  }
}

/// Yuz sifat-darvozasi: aynan bitta yuz, yetarlicha katta va ko'zlar ochiq.
class FaceQuality {
  const FaceQuality._();

  /// Yuz ramkasi kadr qisqa tomonining kamida shu ulushini egallashi kerak.
  /// Yumshoqroq — turli qurilma/masofa uchun (aks holda darvoza o'tmaydi).
  static const double minFaceWidthRatio = 0.20;

  /// Ko'z ochiqligi minimal ehtimoli (classification bo'lganda tekshiriladi).
  static const double minEyeOpen = 0.3;

  static bool passes(FaceSignals s) {
    if (s.faceCount != 1) return false;
    if (s.faceWidthRatio < minFaceWidthRatio) return false;
    final left = s.leftEyeOpen;
    final right = s.rightEyeOpen;
    // Klassifikatsiya mavjud bo'lsa — ko'zlar ochiqligini talab qilamiz.
    if (left != null && left < minEyeOpen) return false;
    if (right != null && right < minEyeOpen) return false;
    return true;
  }
}

/// Bitta challenge'ning holat-mashinasi. Kadrlar `feed` orqali beriladi;
/// challenge bajarilgan lahzada `feed` `true` qaytaradi (bir marta).
class ChallengeTracker {
  ChallengeTracker(this.challenge);

  final LivenessChallenge challenge;

  // Blink / smile uchun "rising edge" holati.
  bool _armed = false; // boshlang'ich (ochiq ko'z / neytral yuz) ko'rildi
  bool _dipped = false; // oraliq holat (yumilgan ko'z / kam tabassum) ko'rildi

  bool _passed = false;
  bool get passed => _passed;

  // Chegaralar (yumshoqroq — dalada ishonchli o'tishi uchun).
  static const double _eyeOpenHi = 0.55;
  static const double _eyeClosedLo = 0.35;
  static const double _smileHi = 0.6;
  static const double _smileLo = 0.4;
  // Front kamerada headYaw belgisi qurilmaga bog'liq (oyna-aks) — shuning uchun
  // burilishni IKKI tomonlama qabul qilamiz (|yaw| > chegara).
  static const double _yawDeg = 16;

  /// Yangi kadrni qayta ishlaydi. Challenge shu kadrda bajarilsa `true`.
  bool feed(FaceSignals s) {
    if (_passed) return false;
    switch (challenge) {
      case LivenessChallenge.blink:
        final eye = s.minEyeOpen;
        if (eye == null) return false;
        if (!_armed && eye > _eyeOpenHi) _armed = true;
        if (_armed && eye < _eyeClosedLo) _dipped = true;
        if (_armed && _dipped && eye > _eyeOpenHi) return _pass();
        return false;
      case LivenessChallenge.smile:
        final sm = s.smiling;
        if (sm == null) return false;
        if (!_armed && sm < _smileLo) _armed = true;
        if (_armed && sm > _smileHi) return _pass();
        return false;
      case LivenessChallenge.turnLeft:
      case LivenessChallenge.turnRight:
        // Ikki tomonlama: boshni istalgan tomonga burish yetarli (belgi noaniq).
        final y = s.headYaw;
        if (y == null) return false;
        if (y.abs() > _yawDeg) return _pass();
        return false;
    }
  }

  bool _pass() {
    _passed = true;
    return true;
  }
}

/// {blink, turnLeft, turnRight, smile} to'plamidan tasodifiy 2 ta challenge
/// tanlaydi (har check-in sessiyasida boshqacha ketma-ketlik — bu foto-hujumni
/// qiyinlashtiradi). [random] test uchun in'ektsiya qilinadi.
List<LivenessChallenge> pickLivenessSequence({Random? random, int count = 2}) {
  final rng = random ?? Random.secure();
  final pool = List<LivenessChallenge>.of(LivenessChallenge.values)..shuffle(rng);
  return pool.take(count).toList(growable: false);
}
