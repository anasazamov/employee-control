import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/router.dart';
import 'l10n/generated/app_localizations.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: EmployeeControlApp()));
}

/// Bitta ilova, ikki rejim: dala xodimi va rahbar (docs/PLAN.md §10).
class EmployeeControlApp extends ConsumerWidget {
  const EmployeeControlApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: const Color(0xFF00639B),
      ),
      // i18n: uz (lotin) — default, ru — ikkinchi til (docs/PLAN.md §10).
      // TODO: tanlangan tilni Sozlamalar orqali o'zgartirish va saqlash.
      locale: const Locale('uz'),
      supportedLocales: const [Locale('uz'), Locale('ru')],
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      routerConfig: router,
    );
  }
}
