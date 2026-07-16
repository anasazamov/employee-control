import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../l10n/generated/app_localizations.dart';

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

/// Check-in oqimi holati: 4 bosqich (PLAN.md §9) —
/// 1 OBYEKT -> 2 YUZ -> 3 IZOH -> 4 YUBORISH.
class CheckinState {
  const CheckinState({
    this.step = 0,
    this.selectedSiteId,
    this.faceVerified = false,
    this.comment = '',
    this.submitting = false,
  });

  final int step;
  final String? selectedSiteId;
  final bool faceVerified;
  final String comment;
  final bool submitting;

  CheckinState copyWith({
    int? step,
    String? selectedSiteId,
    bool? faceVerified,
    String? comment,
    bool? submitting,
  }) {
    return CheckinState(
      step: step ?? this.step,
      selectedSiteId: selectedSiteId ?? this.selectedSiteId,
      faceVerified: faceVerified ?? this.faceVerified,
      comment: comment ?? this.comment,
      submitting: submitting ?? this.submitting,
    );
  }
}

class CheckinController extends Notifier<CheckinState> {
  @override
  CheckinState build() => const CheckinState();

  void selectSite(String siteId) =>
      state = state.copyWith(selectedSiteId: siteId);

  /// Mock yuz-tekshiruv.
  ///
  /// TODO: google_mlkit_face_detection bilan kamera-oqimda detektsiya +
  /// 2 tasodifiy liveness-challenge (ko'z yumish / burilish / tabassum),
  /// so'ng MobileFaceNet (TFLite) 1:1 — natija faqat maslahat, yakuniy hukm
  /// server InsightFace'da (PLAN.md §6). 3× lokal fail bo'lsa ham yuborishga
  /// ruxsat: 'unverified_on_device' bayrog'i bilan (PLAN.md §9).
  void mockFaceCapture() => state = state.copyWith(faceVerified: true);

  void setComment(String value) => state = state.copyWith(comment: value);

  void goToStep(int step) => state = state.copyWith(step: step);

  /// Mock yuborish.
  ///
  /// TODO: kanonik JSON qurilma-kaliti bilan imzolanadi -> POST /v1/checkins;
  /// online -> verdikt 1–2 s; offline -> Drift navbatiga yoziladi va
  /// "signal topilganda yuboriladi" (PLAN.md §9).
  Future<void> submit() async {
    state = state.copyWith(submitting: true);
    await Future<void>.delayed(const Duration(milliseconds: 800));
    state = state.copyWith(submitting: false);
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

  Future<void> _handleContinue() async {
    final l10n = AppLocalizations.of(context);
    final state = ref.read(checkinControllerProvider);
    final controller = ref.read(checkinControllerProvider.notifier);

    switch (state.step) {
      case 0:
        if (state.selectedSiteId != null) {
          controller.goToStep(1);
        }
      case 1:
        controller.goToStep(2);
      case 2:
        controller.goToStep(3);
      case 3:
        await controller.submit();
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(l10n.checkinSuccessMessage)),
        );
        controller.reset();
        _commentController.clear();
        context.go('/home');
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
        onStepContinue: () => _handleContinue(),
        onStepCancel:
            state.step == 0 ? null : () => controller.goToStep(state.step - 1),
        onStepTapped: (index) {
          // Faqat orqaga qaytishga ruxsat.
          if (index < state.step) controller.goToStep(index);
        },
        controlsBuilder: (context, details) {
          final isLast = state.step == 3;
          final canContinue = switch (state.step) {
            0 => state.selectedSiteId != null,
            _ => true,
          };
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
                      : Text(isLast ? l10n.submitButton : l10n.nextButton),
                ),
                const SizedBox(width: 8),
                if (state.step > 0)
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
              verified: state.faceVerified,
              onMockCapture: controller.mockFaceCapture,
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
  const _FaceStep({required this.verified, required this.onMockCapture});

  final bool verified;
  final VoidCallback onMockCapture;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // TODO: ML Kit liveness — kamera-preview shu joyga keladi
        // (google_mlkit_face_detection + tasodifiy 2 challenge, PLAN.md §6).
        Container(
          height: 220,
          width: double.infinity,
          decoration: BoxDecoration(
            border: Border.all(color: Theme.of(context).colorScheme.outline),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                verified ? Icons.verified_user : Icons.face,
                size: 64,
                color: verified ? Colors.green : null,
              ),
              const SizedBox(height: 8),
              Text(
                verified
                    ? 'Yuz tekshirildi (mock)'
                    : 'Kamera oldi (stub)',
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: verified ? null : onMockCapture,
          icon: const Icon(Icons.camera_alt_outlined),
          label: const Text('Yuzni tekshirish (mock)'),
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

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('${l10n.checkinStepSite}: ${site?.name ?? '—'}'),
        const SizedBox(height: 4),
        Text(
          '${l10n.checkinStepFace}: '
          '${state.faceVerified ? 'OK (on-device)' : 'unverified_on_device'}',
        ),
        const SizedBox(height: 4),
        Text(
          '${l10n.commentLabel}: '
          '${state.comment.isEmpty ? '—' : state.comment}',
        ),
        const SizedBox(height: 12),
        Text(
          // TODO(l10n): ARB'ga ko'chirish.
          'Yozuv qurilma-kaliti bilan imzolanadi va serverda mustaqil '
          'tekshiriladi. Oflaynda navbatga yoziladi.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ],
    );
  }
}
