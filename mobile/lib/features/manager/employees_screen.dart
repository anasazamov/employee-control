import 'package:flutter/material.dart';

import '../../l10n/generated/app_localizations.dart';

/// Rahbar: xodimlar ro'yxati — presence + "hozir qaysi obyektda" (PLAN.md §10).
class EmployeesScreen extends StatelessWidget {
  const EmployeesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    // TODO: GET /v1/employees (RBAC-doira: o'z subtree) — presence,
    // "hozir qaysi obyektda" ustuni, bo'lim-daraxt filtri.
    final mockEmployees = <(String, String, IconData)>[
      ('Aliyev Botir', 'Obyekt №14 da', Icons.location_on),
      ('Karimova Nilufar', "Yo'lda", Icons.directions_walk),
      ('Rahimov Jasur', 'Oflayn (32 daqiqa)', Icons.cloud_off),
    ];

    return Scaffold(
      appBar: AppBar(title: Text(l10n.employeesTitle)),
      body: ListView.builder(
        itemCount: mockEmployees.length,
        itemBuilder: (context, index) {
          final (name, status, icon) = mockEmployees[index];
          return ListTile(
            leading: const CircleAvatar(child: Icon(Icons.person_outline)),
            title: Text(name),
            subtitle: Text(status),
            trailing: Icon(icon),
            // TODO: tap -> xodim tafsiloti (obyekt-segmentli timeline,
            // playback, PLAN.md §10).
            onTap: () {},
          );
        },
      ),
    );
  }
}
