import 'package:flutter/material.dart';

import '../../l10n/generated/app_localizations.dart';

/// Sozlamalar: til, batareya-yordamchi, maxfiylik (PLAN.md §10).
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.settingsTitle)),
      body: ListView(
        children: [
          ListTile(
            leading: const Icon(Icons.language),
            title: const Text('Til / Язык'),
            subtitle: const Text("O'zbekcha (lotin)"),
            // TODO: uz/ru tanlovi — MaterialApp.locale'ni Riverpod provider
            // orqali boshqarish va tanlovni saqlash.
            onTap: () {},
          ),
          ListTile(
            leading: const Icon(Icons.battery_saver),
            title: const Text('Batareya-yordamchi'),
            subtitle: const Text(
              'Xiaomi/Vivo/Oppo: autostart va battery-whitelist sozlash',
            ),
            // TODO: OEM'ni aniqlab tegishli sozlamalar ekraniga yetaklash
            // (PLAN.md §8 — BYOD OEM-killer muammosi).
            onTap: () {},
          ),
          ListTile(
            leading: const Icon(Icons.privacy_tip_outlined),
            title: const Text('Maxfiylik'),
            subtitle: const Text(
              'Kuzatuv faqat smena ichida; biometrik rozilik shartlari',
            ),
            // TODO: rozilik-shablon matni (consents) + "meni kim ko'rdi" (v2).
            onTap: () {},
          ),
        ],
      ),
    );
  }
}
