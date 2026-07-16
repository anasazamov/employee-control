import 'package:flutter/material.dart';

import '../../l10n/generated/app_localizations.dart';

/// Rahbar: obyektlar ro'yxati bandlik bilan (PLAN.md §10) —
/// "Obyekt №14 — 3 xodim ichkarida", tap -> kim, qachondan beri.
class SitesScreen extends StatelessWidget {
  const SitesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    // TODO: GET /v1/sites?with=occupancy — site_presence'dan jonli bandlik
    // (Redis `t:{org}:site:occupants:{site_id}`, PLAN.md §8).
    final mockSites = <(String, int)>[
      ('Obyekt №14 — Sergeli qurilish maydoni', 3),
      ('Obyekt №7 — Chilonzor bino', 1),
      ('Obyekt №21 — Yunusobod ombor', 0),
    ];

    return Scaffold(
      appBar: AppBar(title: Text(l10n.sitesTitle)),
      body: ListView.builder(
        itemCount: mockSites.length,
        itemBuilder: (context, index) {
          final (name, occupants) = mockSites[index];
          return ListTile(
            leading: const Icon(Icons.location_city_outlined),
            title: Text(name),
            subtitle: Text(
              occupants > 0
                  ? '$occupants xodim ichkarida'
                  : 'Hozir hech kim yo\'q',
            ),
            trailing: occupants > 0
                ? CircleAvatar(radius: 14, child: Text('$occupants'))
                : null,
            // TODO: tap -> obyekt tafsiloti: ichkaridagilar, tashrif-tarixi,
            // rejalashtirilgan topshiriqlar.
            onTap: () {},
          );
        },
      ),
    );
  }
}
