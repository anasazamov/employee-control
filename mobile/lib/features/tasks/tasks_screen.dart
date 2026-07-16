import 'package:flutter/material.dart';

import '../../l10n/generated/app_localizations.dart';

/// Topshiriqlar ro'yxati (PLAN.md §10).
class TasksScreen extends StatelessWidget {
  const TasksScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    // TODO: GET /v1/assignments — muddat, holat; v2'da kech-ochiladigan
    // topshiriqlar (reveal_at) va push-bildirishnoma.
    final mockTasks = <(String, String, bool)>[
      ('Obyekt №14 tekshiruvi', 'Bugun, 18:00 gacha', false),
      ('Obyekt №7 hisobot fotosi', 'Ertaga, 12:00 gacha', false),
      ('Obyekt №21 nazorat tashrifi', 'Kecha yakunlangan', true),
    ];

    return Scaffold(
      appBar: AppBar(title: Text(l10n.tasksTitle)),
      body: ListView.builder(
        itemCount: mockTasks.length,
        itemBuilder: (context, index) {
          final (title, deadline, done) = mockTasks[index];
          return ListTile(
            leading: Icon(
              done ? Icons.task_alt : Icons.radio_button_unchecked,
              color: done ? Colors.green : null,
            ),
            title: Text(title),
            subtitle: Text(deadline),
          );
        },
      ),
    );
  }
}
