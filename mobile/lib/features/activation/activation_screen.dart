import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/router.dart';
import '../../core/api/api_client.dart';
import '../../core/auth/jwt.dart';
import '../../l10n/generated/app_localizations.dart';
import 'auth_api.dart';

/// Invite -> OTP -> activate haqiqiy oqimi (docs/PLAN.md §7, API.md §Auth).
///
/// 1) HR bergan taklif-tokeni kiritiladi -> POST /invites/resolve (org aniqlanadi).
/// 2) POST /otp/request -> SMS OTP (staging DEBUG=true'da `dev_code` qaytadi va
///    qulaylik uchun avtomatik to'ldiriladi).
/// 3) POST /activate -> JWT + qurilma-bog'lash. Token secure-storage'ga saqlanadi;
///    rol JWT'dan aniqlanadi va sessiya o'rnatiladi (router redirect qiladi).
class ActivationScreen extends ConsumerStatefulWidget {
  const ActivationScreen({super.key});

  @override
  ConsumerState<ActivationScreen> createState() => _ActivationScreenState();
}

class _ActivationScreenState extends ConsumerState<ActivationScreen> {
  static const int _stepCount = 3;

  final PageController _pageController = PageController();
  final TextEditingController _inviteController = TextEditingController();
  final TextEditingController _otpController = TextEditingController();

  int _step = 0;
  bool _busy = false;
  String? _error;

  String? _inviteToken;
  ResolvedInvite? _resolved;
  String? _devCode; // staging DEBUG=true bo'lsa

  @override
  void dispose() {
    _pageController.dispose();
    _inviteController.dispose();
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

  String _errText(Object e) =>
      e is AuthApiException ? e.detail : e.toString();

  Future<void> _resolveInvite() async {
    final token = _inviteController.text.trim();
    if (token.isEmpty) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final api = ref.read(authApiProvider);
      final resolved = await api.resolveInvite(token);
      _inviteToken = token;
      _resolved = resolved;
      // OTP darhol so'raladi; staging'da dev_code qaytadi.
      _devCode = await api.requestOtp(token);
      if (_devCode != null) _otpController.text = _devCode!;
      if (!mounted) return;
      setState(() => _busy = false);
      _goToStep(1);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = _errText(e);
      });
    }
  }

  Future<void> _resendOtp() async {
    if (_inviteToken == null) return;
    setState(() => _busy = true);
    try {
      _devCode = await ref.read(authApiProvider).requestOtp(_inviteToken!);
      if (_devCode != null) _otpController.text = _devCode!;
    } catch (_) {
      // jim — foydalanuvchi qayta urinadi
    }
    if (mounted) setState(() => _busy = false);
  }

  Future<void> _activate() async {
    final code = _otpController.text.trim();
    if (code.isEmpty || _inviteToken == null) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final tokens = ref.read(tokenStoreProvider);
      final fp = await tokens.deviceFingerprint();
      final result = await ref.read(authApiProvider).activate(
            token: _inviteToken!,
            otpCode: code,
            deviceFingerprint: fp,
          );
      // Token secure-storage'ga — interceptor shu yerdan o'qiydi.
      await tokens.save(result.accessToken);
      final role = roleFromToken(result.accessToken);
      if (!mounted) return;
      setState(() => _busy = false);
      // Sessiya o'rnatiladi; router redirect qiladi.
      ref.read(sessionProvider.notifier).activate(
            role: role,
            token: result.accessToken,
          );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = _errText(e);
      });
    }
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
            if (_error != null)
              Container(
                width: double.infinity,
                color: Theme.of(context).colorScheme.errorContainer,
                padding: const EdgeInsets.all(12),
                child: Text(
                  _error!,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onErrorContainer,
                  ),
                ),
              ),
            Expanded(
              child: PageView(
                controller: _pageController,
                physics: const NeverScrollableScrollPhysics(),
                children: [
                  _InviteStep(
                    controller: _inviteController,
                    busy: _busy,
                    onContinue: _resolveInvite,
                  ),
                  _OtpStep(
                    controller: _otpController,
                    busy: _busy,
                    orgName: _resolved?.orgName,
                    maskedPhone: _resolved?.maskedPhone,
                    devCode: _devCode,
                    onVerify: _activate,
                    onResend: _resendOtp,
                    onBack: () => _goToStep(0),
                  ),
                  const SizedBox.shrink(),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _InviteStep extends StatelessWidget {
  const _InviteStep({
    required this.controller,
    required this.busy,
    required this.onContinue,
  });

  final TextEditingController controller;
  final bool busy;
  final Future<void> Function() onContinue;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'HR bergan taklif-tokenini kiriting (QR/havoladan) yoki qo\'lda joylang.',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          const SizedBox(height: 16),
          TextField(
            controller: controller,
            minLines: 1,
            maxLines: 3,
            decoration: InputDecoration(
              labelText: l10n.inviteCodeLabel,
              border: const OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: busy ? null : onContinue,
            child: busy
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(l10n.nextButton),
          ),
        ],
      ),
    );
  }
}

class _OtpStep extends StatelessWidget {
  const _OtpStep({
    required this.controller,
    required this.busy,
    required this.orgName,
    required this.maskedPhone,
    required this.devCode,
    required this.onVerify,
    required this.onResend,
    required this.onBack,
  });

  final TextEditingController controller;
  final bool busy;
  final String? orgName;
  final String? maskedPhone;
  final String? devCode;
  final Future<void> Function() onVerify;
  final Future<void> Function() onResend;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (orgName != null)
            Text(
              orgName!,
              style: Theme.of(context).textTheme.titleMedium,
            ),
          const SizedBox(height: 8),
          Text(
            maskedPhone != null
                ? '$maskedPhone raqamiga yuborilgan 6 xonali kodni kiriting.'
                : 'Telefoningizga yuborilgan 6 xonali kodni kiriting.',
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          if (devCode != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                'Test-server kodi: $devCode',
                style: TextStyle(color: Theme.of(context).colorScheme.primary),
              ),
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
          FilledButton(
            onPressed: busy ? null : onVerify,
            child: busy
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(l10n.activationTitle),
          ),
          TextButton(
            onPressed: busy ? null : onResend,
            child: const Text('Kodni qayta yuborish'),
          ),
          TextButton(onPressed: busy ? null : onBack, child: Text(l10n.backButton)),
        ],
      ),
    );
  }
}
