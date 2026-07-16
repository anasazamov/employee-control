// Qurilmadagi liveness mantig'i (foto-hujumga qarshi) uchun unit-testlar.
// Bu testlar sof Dart mantig'ini tekshiradi — kamera/ML Kit talab qilinmaydi.

import 'dart:math';

import 'package:employee_control/features/checkin/checkin_api.dart';
import 'package:employee_control/features/checkin/liveness.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('FaceQuality sifat-darvozasi', () {
    test('bitta bo\'lmagan yuzni rad etadi', () {
      expect(FaceQuality.passes(const FaceSignals(faceCount: 0)), isFalse);
      expect(
        FaceQuality.passes(
            const FaceSignals(faceCount: 2, faceWidthRatio: 0.5)),
        isFalse,
      );
    });

    test('yetarli katta, ochiq ko\'zli bitta yuzni qabul qiladi', () {
      expect(
        FaceQuality.passes(const FaceSignals(
          faceCount: 1,
          faceWidthRatio: 0.4,
          leftEyeOpen: 0.9,
          rightEyeOpen: 0.9,
        )),
        isTrue,
      );
    });

    test('kichik yuzni rad etadi', () {
      expect(
        FaceQuality.passes(
            const FaceSignals(faceCount: 1, faceWidthRatio: 0.1)),
        isFalse,
      );
    });
  });

  group('ChallengeTracker — blink', () {
    test('ochiq -> yumilgan -> ochiq o\'tishini talab qiladi', () {
      final t = ChallengeTracker(LivenessChallenge.blink);
      expect(
          t.feed(const FaceSignals(leftEyeOpen: 0.9, rightEyeOpen: 0.9)),
          isFalse); // armed
      expect(
          t.feed(const FaceSignals(leftEyeOpen: 0.1, rightEyeOpen: 0.1)),
          isFalse); // dipped
      expect(
          t.feed(const FaceSignals(leftEyeOpen: 0.9, rightEyeOpen: 0.9)),
          isTrue); // passed
      expect(t.passed, isTrue);
    });

    test('statik ochiq ko\'z hech qachon o\'tmaydi (foto-hujum)', () {
      final t = ChallengeTracker(LivenessChallenge.blink);
      for (var i = 0; i < 10; i++) {
        expect(
            t.feed(const FaceSignals(leftEyeOpen: 0.9, rightEyeOpen: 0.9)),
            isFalse);
      }
    });
  });

  group('ChallengeTracker — bosh burilishi', () {
    test('turnLeft musbat yaw talab qiladi', () {
      final t = ChallengeTracker(LivenessChallenge.turnLeft);
      expect(t.feed(const FaceSignals(headYaw: 5)), isFalse);
      expect(t.feed(const FaceSignals(headYaw: 30)), isTrue);
    });

    test('turnRight manfiy yaw talab qiladi', () {
      final t = ChallengeTracker(LivenessChallenge.turnRight);
      expect(t.feed(const FaceSignals(headYaw: -5)), isFalse);
      expect(t.feed(const FaceSignals(headYaw: -30)), isTrue);
    });
  });

  group('ChallengeTracker — smile', () {
    test('neytral -> tabassum o\'tishini talab qiladi', () {
      final t = ChallengeTracker(LivenessChallenge.smile);
      expect(t.feed(const FaceSignals(smiling: 0.1)), isFalse);
      expect(t.feed(const FaceSignals(smiling: 0.9)), isTrue);
    });
  });

  group('pickLivenessSequence', () {
    test('2 ta har xil challenge qaytaradi', () {
      final seq = pickLivenessSequence(random: Random(42));
      expect(seq.length, 2);
      expect(seq.toSet().length, 2);
    });
  });

  group('generateUuidV4', () {
    test('RFC 4122 v4 formatida', () {
      final id = generateUuidV4();
      expect(
        RegExp(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
            .hasMatch(id),
        isTrue,
      );
    });
  });
}
