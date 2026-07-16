import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../l10n/generated/app_localizations.dart';

/// Xodim bosh sahifasi: smena, sync-holat, Check-in tugmasi (PLAN.md §10).
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.homeTitle)),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // TODO: joriy smena — GET /v1/shifts/current (kuzatuv faqat
            // smena ichida, PLAN.md §8).
            const Card(
              child: ListTile(
                leading: Icon(Icons.schedule),
                title: Text('Smena: 09:00 – 18:00 (mock)'),
                subtitle: Text('Kuzatuv faqat smena ichida ishlaydi'),
              ),
            ),
            const SizedBox(height: 12),
            // TODO: sync-chip — Drift'dagi oflayn navbat holati (PLAN.md §9).
            const Card(
              child: ListTile(
                leading: Icon(Icons.cloud_done_outlined),
                title: Text('Sinxronizatsiya: hammasi yuborilgan (mock)'),
              ),
            ),
            const Spacer(),
            FilledButton.icon(
              style: FilledButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
              ),
              onPressed: () => context.go('/checkin'),
              icon: const Icon(Icons.fact_check_outlined),
              label: Text(l10n.checkinButton),
            ),
          ],
        ),
      ),
    );
  }
}
