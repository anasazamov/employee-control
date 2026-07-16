import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/router.dart';
import '../../l10n/generated/app_localizations.dart';

/// Invite -> telefon -> SMS OTP bosqichli aktivatsiya oqimi (docs/PLAN.md §7).
///
/// Hozircha to'liq mock: hech qanday tarmoq so'rovi yuborilmaydi, OTP
/// tasdig'i sessiyani (rol bilan) o'rnatadi va router redirect kerakli
/// shell'ga o'tkazadi.
class ActivationScreen extends ConsumerStatefulWidget {
  const ActivationScreen({super.key});

  @override
  ConsumerState<ActivationScreen> createState() => _ActivationScreenState();
}

class _ActivationScreenState extends ConsumerState<ActivationScreen> {
  static const int _stepCount = 3;

  final PageController _pageController = PageController();
  final TextEditingController _inviteCodeController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _otpController = TextEditingController();

  int _step = 0;
  bool _managerDemo = false;
  bool _submitting = false;

  @override
  void dispose() {
    _pageController.dispose();
    _inviteCodeController.dispose();
    _phoneController.dispose();
    _otpController.dispose();
    super.dispose();
  }

  void _goToStep(int step) {
    setState(() => _step = step);
    _pageController.animateToPage(
      step,
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeInOut,
    );
  }

  void _submitInviteCode() {
    // TODO: POST /v1/auth/invite — QR/deep-link (https://app.<domen>/a/{token})
    // tokeni yoki 8 belgili qo'lda teriladigan kodni tekshiradi; javobda
    // tenant-kontekst keladi: {org_id, nom, logo, rang, maskali-telefon} —
    // ilova o'zini shu kontekstga "kiyintiradi" (PLAN.md §7).
    _goToStep(1);
  }

  void _requestOtp() {
    // TODO: POST /v1/auth/otp — HR bazasidagi telefon raqamiga SMS OTP
    // yuboriladi (Eskiz.uz). Yuz yolg'iz hech qachon qurilma bog'lamaydi —
    // OTP majburiy ikkinchi omil (PLAN.md §7).
    _goToStep(2);
  }

  Future<void> _verifyOtp() async {
    setState(() => _submitting = true);
    // TODO: POST /v1/auth/otp (verify) — OTP tasdig'i + qurilma-bog'lash:
    // Keystore/Secure Enclave P-256 kalit, 1 faol qurilma/(org, xodim).
    await Future<void>.delayed(const Duration(milliseconds: 600));
    if (!mounted) return;
    setState(() => _submitting = false);

    // Mock: sessiya o'rnatiladi; keyingi navigatsiyani router redirect qiladi.
    ref.read(sessionProvider.notifier).activate(
          role: _managerDemo ? UserRole.manager : UserRole.fieldEmployee,
        );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.activationTitle)),
      body: SafeArea(
        child: Column(
          children: [
            LinearProgressIndicator(value: (_step + 1) / _stepCount),
            Expanded(
              child: PageView(
                controller: _pageController,
                physics: const NeverScrollableScrollPhysics(),
                children: [
                  _InviteCodeStep(
                    controller: _inviteCodeController,
                    onContinue: _submitInviteCode,
                  ),
                  _PhoneStep(
                    controller: _phoneController,
                    onContinue: _requestOtp,
                    onBack: () => _goToStep(0),
                  ),
                  _OtpStep(
                    controller: _otpController,
                    managerDemo: _managerDemo,
                    submitting: _submitting,
                    onManagerDemoChanged: (value) =>
                        setState(() => _managerDemo = value),
                    onVerify: _verifyOtp,
                    onBack: () => _goToStep(1),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _InviteCodeStep extends StatelessWidget {
  const _InviteCodeStep({required this.controller, required this.onContinue});

  final TextEditingController controller;
  final VoidCallback onContinue;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // TODO(l10n): yordamchi matnlarni ARB'ga ko'chirish.
          // TODO: QR-skaner tugmasi va deep-link orqali avtomatik to'ldirish.
          Text(
            'HR bergan 8 belgili taklif kodini kiriting yoki QR-kodni skanerlang.',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          const SizedBox(height: 16),
          TextField(
            controller: controller,
            textCapitalization: TextCapitalization.characters,
            maxLength: 8,
            decoration: InputDecoration(
              labelText: l10n.inviteCodeLabel,
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton(onPressed: onContinue, child: Text(l10n.nextButton)),
        ],
      ),
    );
  }
}

class _PhoneStep extends StatelessWidget {
  const _PhoneStep({
    required this.controller,
    required this.onContinue,
    required this.onBack,
  });

  final TextEditingController controller;
  final VoidCallback onContinue;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'HR bazasidagi telefon raqamingizni tasdiqlang — unga SMS kod yuboriladi.',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          const SizedBox(height: 16),
          TextField(
            controller: controller,
            keyboardType: TextInputType.phone,
            decoration: InputDecoration(
              labelText: l10n.phoneLabel,
              hintText: '+998 90 123 45 67',
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton(onPressed: onContinue, child: Text(l10n.nextButton)),
          TextButton(onPressed: onBack, child: Text(l10n.backButton)),
        ],
      ),
    );
  }
}

class _OtpStep extends StatelessWidget {
  const _OtpStep({
    required this.controller,
    required this.managerDemo,
    required this.submitting,
    required this.onManagerDemoChanged,
    required this.onVerify,
    required this.onBack,
  });

  final TextEditingController controller;
  final bool managerDemo;
  final bool submitting;
  final ValueChanged<bool> onManagerDemoChanged;
  final VoidCallback onVerify;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Telefoningizga yuborilgan 6 xonali kodni kiriting.',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          const SizedBox(height: 16),
          TextField(
            controller: controller,
            keyboardType: TextInputType.number,
            maxLength: 6,
            decoration: InputDecoration(
              labelText: l10n.otpLabel,
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 8),
          // Skelet uchun demo-tumbler: rahbar rejimini sinash imkoni.
          // Real ilovada rolni server role-claim'i belgilaydi.
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(l10n.demoManagerToggle),
            value: managerDemo,
            onChanged: submitting ? null : onManagerDemoChanged,
          ),
          const SizedBox(height: 8),
          FilledButton(
            onPressed: submitting ? null : onVerify,
            child: submitting
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(l10n.activationTitle),
          ),
          TextButton(
            onPressed: submitting ? null : onBack,
            child: Text(l10n.backButton),
          ),
        ],
      ),
    );
  }
}
