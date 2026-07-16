import 'package:flutter/material.dart';

import '../../l10n/generated/app_localizations.dart';

/// Xodimning check-in tarixi (PLAN.md §10).
class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    // TODO: GET /v1/checkins/my — kunlik guruhlangan ro'yxat +
    // kun-marshrut playback slayderi (PLAN.md §10).
    final mockEntries = <(String, String, String)>[
      ('Obyekt №14', '16.07.2026 09:15', 'verified'),
      ('Obyekt №7', '15.07.2026 14:02', 'pending'),
      ('Obyekt №21', '14.07.2026 11:40', 'flagged'),
    ];

    return Scaffold(
      appBar: AppBar(title: Text(l10n.historyTitle)),
      body: ListView.separated(
        itemCount: mockEntries.length,
        separatorBuilder: (context, index) => const Divider(height: 1),
        itemBuilder: (context, index) {
          final (site, time, verdict) = mockEntries[index];
          return ListTile(
            leading: Icon(switch (verdict) {
              'verified' => Icons.check_circle_outline,
              'pending' => Icons.hourglass_top,
              _ => Icons.flag_outlined,
            }),
            title: Text(site),
            subtitle: Text(time),
            trailing: Text(verdict),
            // TODO: tap -> check-in tafsiloti ekrani (selfie, xarita, verdikt).
            onTap: () {},
          );
        },
      ),
    );
  }
}
