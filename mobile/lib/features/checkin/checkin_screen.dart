import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';

import '../../core/api/api_client.dart';
import '../../l10n/generated/app_localizations.dart';
import 'checkin_api.dart';
import 'face_liveness_view.dart';

/// Yaqin obyekt (site) modeli — mock.
///
/// TODO: geolocator joriy nuqtasi bo'yicha GET /v1/sites/nearby yoki Drift
/// keshidan; geofence ENTER trigger'ida obyekt avtotanlanadi (PLAN.md §9).
class NearbySite {
  const NearbySite({
    required this.id,
    required this.name,
    required this.distanceMeters,
  });

  final String id;
  final String name;
  final int distanceMeters;
}

const List<NearbySite> _mockNearbySites = [
  NearbySite(
    id: 'site-14',
    name: 'Obyekt №14 — Sergeli qurilish maydoni',
    distanceMeters: 42,
  ),
  NearbySite(
    id: 'site-07',
    name: 'Obyekt №7 — Chilonzor bino',
    distanceMeters: 310,
  ),
  NearbySite(
    id: 'site-21',
    name: 'Obyekt №21 — Yunusobod ombor',
    distanceMeters: 980,
  ),
];

NearbySite? _siteById(String? id) {
  for (final site in _mockNearbySites) {
    if (site.id == id) return site;
  }
  return null;
}

/// CheckinApi provideri — bazaviy URL (api_client.dart) + secure-storage token.
final checkinApiProvider = Provider<CheckinApi>((ref) {
  final tokens = ref.read(tokenStoreProvider);
  final api = CheckinApi(baseUrl: kApiBaseUrl, tokenReader: tokens.read);
  ref.onDispose(api.close);
  return api;
});

/// Check-in oqimi holati: 4 bosqich (PLAN.md §9) —
/// 1 OBYEKT -> 2 YUZ -> 3 IZOH -> 4 YUBORISH.
class CheckinState {
  const CheckinState({
    this.step = 0,
    this.selectedSiteId,
    this.selfieJpeg,
    this.livenessPassed = false,
    this.localMatch = false,
    this.comment = '',
    this.submitting = false,
    this.result,
    this.error,
  });

  final int step;
  final String? selectedSiteId;

  /// Olingan selfie JPEG baytlari (liveness o'tgach).
  final Uint8List? selfieJpeg;
  final bool livenessPassed;
  final bool localMatch;
  final String comment;
  final bool submitting;

  /// Server hukmi (POST /v1/checkins javobi) — yuborilgach.
  final CheckinResult? result;
  final String? error;

  bool get faceCaptured => selfieJpeg != null;

  CheckinState copyWith({
    int? step,
    String? selectedSiteId,
    Uint8List? selfieJpeg,
    bool? livenessPassed,
    bool? localMatch,
    String? comment,
    bool? submitting,
    CheckinResult? result,
    String? error,
  }) {
    return CheckinState(
      step: step ?? this.step,
      selectedSiteId: selectedSiteId ?? this.selectedSiteId,
      selfieJpeg: selfieJpeg ?? this.selfieJpeg,
      livenessPassed: livenessPassed ?? this.livenessPassed,
      localMatch: localMatch ?? this.localMatch,
      comment: comment ?? this.comment,
      submitting: submitting ?? this.submitting,
      result: result ?? this.result,
      error: error ?? this.error,
    );
  }
}

class CheckinController extends Notifier<CheckinState> {
  @override
  CheckinState build() => const CheckinState();

  void selectSite(String siteId) =>
      state = state.copyWith(selectedSiteId: siteId);

  /// Qurilmadagi ML Kit liveness natijasini (selfie + hukm) saqlaydi.
  void setFaceResult(FaceCaptureResult r) {
    state = state.copyWith(
      selfieJpeg: r.jpegBytes,
      livenessPassed: r.livenessPassed,
      localMatch: r.localMatch,
    );
  }

  void setComment(String value) => state = state.copyWith(comment: value);

  void goToStep(int step) => state = state.copyWith(step: step);

  /// Yuborish oqimi: selfie-url -> presigned PUT -> POST /v1/checkins.
  /// GPS joriy nuqtadan (geolocator), hukm serverdan qaytadi.
  Future<void> submit() async {
    final jpeg = state.selfieJpeg;
    if (jpeg == null) return;

    // submitting=true, oldingi natija/xatoni tozalaymiz.
    state = CheckinState(
      step: state.step,
      selectedSiteId: state.selectedSiteId,
      selfieJpeg: jpeg,
      livenessPassed: state.livenessPassed,
      localMatch: state.localMatch,
      comment: state.comment,
      submitting: true,
    );

    try {
      final api = ref.read(checkinApiProvider);
      final position = await _currentPosition();

      final upload = await api.requestSelfieUrl();
      await api.putSelfie(upload.url, jpeg);

      final result = await api.submitCheckin(
        checkinId: generateUuidV4(),
        ts: DateTime.now().toUtc().toIso8601String(),
        selfieKey: upload.objectKey,
        localMatch: state.localMatch,
        livenessPassed: state.livenessPassed,
        lat: position?.latitude,
        lon: position?.longitude,
        accuracyM: position?.accuracy,
        siteId: state.selectedSiteId,
        comment: state.comment,
        deviceIntegrity: {
          'platform': Platform.isAndroid ? 'android' : 'ios',
          'debug': true,
        },
      );

      state = state.copyWith(submitting: false, result: result);
    } catch (e) {
      state = state.copyWith(submitting: false, error: e.toString());
    }
  }

  /// Joriy GPS nuqtasi — ruxsat/servis bo'lmasa null (check-in baribir ketadi).
  Future<Position?> _currentPosition() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) return null;
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        return null;
      }
      return await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 12),
        ),
      );
    } catch (_) {
      return null;
    }
  }

  void reset() => state = const CheckinState();
}

final checkinControllerProvider =
    NotifierProvider<CheckinController, CheckinState>(CheckinController.new);

class CheckinScreen extends ConsumerStatefulWidget {
  const CheckinScreen({super.key});

  @override
  ConsumerState<CheckinScreen> createState() => _CheckinScreenState();
}

class _CheckinScreenState extends ConsumerState<CheckinScreen> {
  final TextEditingController _commentController = TextEditingController();

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  Future<void> _startFaceCapture() async {
    final result = await Navigator.of(context).push<FaceCaptureResult>(
      MaterialPageRoute(builder: (_) => const FaceCaptureScreen()),
    );
    if (result == null || !mounted) return;
    ref.read(checkinControllerProvider.notifier).setFaceResult(result);
  }

  Future<void> _handleContinue() async {
    final l10n = AppLocalizations.of(context);
    final state = ref.read(checkinControllerProvider);
    final controller = ref.read(checkinControllerProvider.notifier);

    switch (state.step) {
      case 0:
        if (state.selectedSiteId != null) controller.goToStep(1);
      case 1:
        if (state.faceCaptured) controller.goToStep(2);
      case 2:
        controller.goToStep(3);
      case 3:
        if (state.result != null) {
          // Yuborilgan — yakunlash.
          controller.reset();
          _commentController.clear();
          context.go('/home');
          return;
        }
        await controller.submit();
        if (!mounted) return;
        final after = ref.read(checkinControllerProvider);
        final messenger = ScaffoldMessenger.of(context);
        if (after.result != null) {
          messenger.showSnackBar(
            SnackBar(content: Text(l10n.checkinSuccessMessage)),
          );
        } else if (after.error != null) {
          messenger.showSnackBar(
            SnackBar(
              content: Text('${l10n.checkinSubmitError}: ${after.error}'),
            ),
          );
        }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final state = ref.watch(checkinControllerProvider);
    final controller = ref.read(checkinControllerProvider.notifier);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.checkinButton)),
      body: Stepper(
        currentStep: state.step,
        onStepContinue: _handleContinue,
        onStepCancel:
            state.step == 0 ? null : () => controller.goToStep(state.step - 1),
        onStepTapped: (index) {
          if (index < state.step) controller.goToStep(index);
        },
        controlsBuilder: (context, details) {
          final isLast = state.step == 3;
          final submitted = state.result != null;
          final canContinue = switch (state.step) {
            0 => state.selectedSiteId != null,
            1 => state.faceCaptured,
            _ => true,
          };
          final String label;
          if (!isLast) {
            label = l10n.nextButton;
          } else if (submitted) {
            label = l10n.checkinFinish;
          } else {
            label = l10n.submitButton;
          }
          return Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Row(
              children: [
                FilledButton(
                  onPressed: state.submitting || !canContinue
                      ? null
                      : details.onStepContinue,
                  child: state.submitting
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Text(label),
                ),
                const SizedBox(width: 8),
                if (state.step > 0 && !submitted)
                  TextButton(
                    onPressed: state.submitting ? null : details.onStepCancel,
                    child: Text(l10n.backButton),
                  ),
              ],
            ),
          );
        },
        steps: [
          Step(
            title: Text(l10n.checkinStepSite),
            isActive: state.step >= 0,
            state: state.step > 0 ? StepState.complete : StepState.indexed,
            content: _SiteStep(
              selectedSiteId: state.selectedSiteId,
              onSelect: controller.selectSite,
            ),
          ),
          Step(
            title: Text(l10n.checkinStepFace),
            isActive: state.step >= 1,
            state: state.step > 1 ? StepState.complete : StepState.indexed,
            content: _FaceStep(
              captured: state.faceCaptured,
              selfie: state.selfieJpeg,
              onStart: _startFaceCapture,
            ),
          ),
          Step(
            title: Text(l10n.commentLabel),
            isActive: state.step >= 2,
            state: state.step > 2 ? StepState.complete : StepState.indexed,
            content: TextField(
              controller: _commentController,
              onChanged: controller.setComment,
              maxLines: 3,
              decoration: InputDecoration(
                labelText: l10n.commentLabel,
                border: const OutlineInputBorder(),
              ),
            ),
          ),
          Step(
            title: Text(l10n.checkinStepSubmit),
            isActive: state.step >= 3,
            state: StepState.indexed,
            content: _SummaryStep(state: state),
          ),
        ],
      ),
    );
  }
}

class _SiteStep extends StatelessWidget {
  const _SiteStep({required this.selectedSiteId, required this.onSelect});

  final String? selectedSiteId;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    // >150 m uzoqlikdagi obyekt tanlansa ham ruxsat, lekin oldindan
    // bayroqlanadi (PLAN.md §9 — trigger B).
    return Column(
      children: [
        for (final site in _mockNearbySites)
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.location_on_outlined),
            title: Text(site.name),
            subtitle: Text('${site.distanceMeters} m'),
            trailing: site.id == selectedSiteId
                ? const Icon(Icons.check_circle)
                : null,
            selected: site.id == selectedSiteId,
            onTap: () => onSelect(site.id),
          ),
      ],
    );
  }
}

class _FaceStep extends StatelessWidget {
  const _FaceStep({
    required this.captured,
    required this.selfie,
    required this.onStart,
  });

  final bool captured;
  final Uint8List? selfie;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final scheme = Theme.of(context).colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          height: 220,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            border: Border.all(color: scheme.outline),
            borderRadius: BorderRadius.circular(12),
          ),
          clipBehavior: Clip.antiAlias,
          child: captured && selfie != null
              ? Stack(
                  fit: StackFit.expand,
                  children: [
                    Image.memory(selfie!, fit: BoxFit.cover),
                    Positioned(
                      right: 8,
                      top: 8,
                      child: CircleAvatar(
                        backgroundColor: Colors.green,
                        child: const Icon(Icons.check, color: Colors.white),
                      ),
                    ),
                  ],
                )
              : Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.face_retouching_natural,
                        size: 64, color: scheme.primary),
                    const SizedBox(height: 8),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      child: Text(
                        l10n.faceStepNotCaptured,
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],
                ),
        ),
        const SizedBox(height: 12),
        if (captured)
          Text(
            l10n.faceStepCaptured,
            style: TextStyle(color: Colors.green.shade700),
          ),
        const SizedBox(height: 8),
        OutlinedButton.icon(
          onPressed: onStart,
          icon: Icon(captured ? Icons.refresh : Icons.camera_alt_outlined),
          label: Text(captured ? l10n.faceStepRetake : l10n.faceStepStart),
        ),
      ],
    );
  }
}

class _SummaryStep extends StatelessWidget {
  const _SummaryStep({required this.state});

  final CheckinState state;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final site = _siteById(state.selectedSiteId);
    final result = state.result;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('${l10n.checkinStepSite}: ${site?.name ?? '—'}'),
        const SizedBox(height: 4),
        Text(
          '${l10n.checkinStepFace}: '
          '${state.livenessPassed ? 'liveness OK (on-device)' : 'unverified_on_device'}',
        ),
        const SizedBox(height: 4),
        Text(
          '${l10n.commentLabel}: '
          '${state.comment.isEmpty ? '—' : state.comment}',
        ),
        const SizedBox(height: 12),
        if (result != null) _VerdictCard(result: result),
        if (state.error != null)
          Card(
            color: Theme.of(context).colorScheme.errorContainer,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Text('${l10n.checkinSubmitError}: ${state.error}'),
            ),
          ),
        if (result == null && state.error == null)
          Text(
            'Yozuv serverda mustaqil tekshiriladi (yuz-worker hukmi). '
            'Oflaynda navbatga yoziladi.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
      ],
    );
  }
}

class _VerdictCard extends StatelessWidget {
  const _VerdictCard({required this.result});

  final CheckinResult result;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final (label, color, icon) = _verdictStyle(l10n, result.verdict);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.checkinResultTitle,
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Row(
              children: [
                Icon(icon, color: color),
                const SizedBox(width: 8),
                Text(
                  label,
                  style: TextStyle(
                    color: color,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            if (result.riskScore != null)
              Text('${l10n.checkinRiskScore}: ${result.riskScore}'),
            if (result.serverFaceScore != null)
              Text('${l10n.checkinFaceScore}: ${result.serverFaceScore}'),
            if (result.insideGeofence != null)
              Text(
                '${l10n.checkinInsideGeofence}: '
                '${result.insideGeofence! ? '✓' : '✗'}',
              ),
            if (result.verdictReasons.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  result.verdictReasons.join(', '),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
          ],
        ),
      ),
    );
  }

  (String, Color, IconData) _verdictStyle(
      AppLocalizations l10n, String? verdict) {
    switch (verdict) {
      case 'verified':
        return (l10n.checkinVerdictVerified, Colors.green, Icons.verified);
      case 'flagged':
        return (l10n.checkinVerdictFlagged, Colors.orange, Icons.flag);
      case 'rejected':
        return (l10n.checkinVerdictRejected, Colors.red, Icons.cancel);
      default:
        return (
          l10n.checkinVerdictPending,
          Colors.blueGrey,
          Icons.hourglass_top
        );
    }
  }
}
