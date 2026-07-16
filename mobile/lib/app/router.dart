import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/activation/activation_screen.dart';
import '../features/checkin/checkin_screen.dart';
import '../features/history/history_screen.dart';
import '../features/home/home_screen.dart';
import '../features/manager/employees_screen.dart';
import '../features/manager/live_map_screen.dart';
import '../features/manager/sites_screen.dart';
import '../features/settings/settings_screen.dart';
import '../features/tasks/tasks_screen.dart';
import '../l10n/generated/app_localizations.dart';

/// Foydalanuvchi roli — real ilovada server role-claim'idan keladi
/// (docs/PLAN.md §10: rahbar rejimini server hal qiladi).
enum UserRole { fieldEmployee, manager }

/// Faol sessiya (stub).
///
/// TODO: real ilovada JWT (org_id claim bilan) flutter_secure_storage'da
/// saqlanadi va qurilma-kalit (Keystore/Secure Enclave P-256) bilan bog'lanadi.
class Session {
  const Session({required this.role, required this.token});

  final UserRole role;
  final String token;
}

/// Sessiya holatini boshqaruvchi Notifier (Riverpod v2, kodgen'siz stub).
class SessionController extends Notifier<Session?> {
  @override
  Session? build() => null;

  /// Mock aktivatsiya — aktivatsiya oqimi tugaganda chaqiriladi.
  /// TODO: real oqim — POST /v1/auth/invite + POST /v1/auth/otp (PLAN.md §7).
  void activate({required UserRole role, String token = 'mock-token'}) {
    state = Session(role: role, token: token);
  }

  void clear() => state = null;
}

/// Sessiya router redirect'ini boshqaradi: sessiya yo'q -> /activation.
final sessionProvider =
    NotifierProvider<SessionController, Session?>(SessionController.new);

final routerProvider = Provider<GoRouter>((ref) {
  // Sessiya o'zgarganda redirect qayta hisoblanishi uchun ko'prik.
  final refresh = ValueNotifier<int>(0);
  ref.onDispose(refresh.dispose);
  ref.listen<Session?>(sessionProvider, (_, __) => refresh.value++);

  return GoRouter(
    initialLocation: '/home',
    refreshListenable: refresh,
    redirect: (context, state) {
      final session = ref.read(sessionProvider);
      final onActivation = state.matchedLocation == '/activation';

      if (session == null) {
        return onActivation ? null : '/activation';
      }
      if (onActivation) {
        return session.role == UserRole.manager ? '/m/map' : '/home';
      }

      // Rol va shell mosligi: rahbar faqat /m/*, xodim faqat xodim-shell'ida.
      final inManagerShell = state.matchedLocation.startsWith('/m/');
      if (session.role == UserRole.manager && !inManagerShell) {
        return '/m/map';
      }
      if (session.role == UserRole.fieldEmployee && inManagerShell) {
        return '/home';
      }
      return null;
    },
    routes: [
      // Shell'lardan tashqarida — aktivatsiya (PLAN.md §7).
      GoRoute(
        path: '/activation',
        builder: (context, state) => const ActivationScreen(),
      ),

      // Xodim rejimi shell'i (pastki navigatsiya).
      ShellRoute(
        builder: (context, state, child) =>
            _EmployeeShell(location: state.matchedLocation, child: child),
        routes: [
          GoRoute(
            path: '/home',
            builder: (context, state) => const HomeScreen(),
          ),
          GoRoute(
            path: '/checkin',
            builder: (context, state) => const CheckinScreen(),
          ),
          GoRoute(
            path: '/history',
            builder: (context, state) => const HistoryScreen(),
          ),
          GoRoute(
            path: '/tasks',
            builder: (context, state) => const TasksScreen(),
          ),
          GoRoute(
            path: '/settings',
            builder: (context, state) => const SettingsScreen(),
          ),
        ],
      ),

      // Rahbar rejimi shell'i.
      ShellRoute(
        builder: (context, state, child) =>
            _ManagerShell(location: state.matchedLocation, child: child),
        routes: [
          GoRoute(
            path: '/m/map',
            builder: (context, state) => const LiveMapScreen(),
          ),
          GoRoute(
            path: '/m/employees',
            builder: (context, state) => const EmployeesScreen(),
          ),
          GoRoute(
            path: '/m/sites',
            builder: (context, state) => const SitesScreen(),
          ),
        ],
      ),
    ],
  );
});

class _EmployeeShell extends StatelessWidget {
  const _EmployeeShell({required this.location, required this.child});

  final String location;
  final Widget child;

  static const List<String> _tabs = [
    '/home',
    '/checkin',
    '/history',
    '/tasks',
    '/settings',
  ];

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final index = _tabs.indexWhere((tab) => location.startsWith(tab));

    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: index < 0 ? 0 : index,
        onDestinationSelected: (i) => context.go(_tabs[i]),
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.home_outlined),
            label: l10n.homeTitle,
          ),
          NavigationDestination(
            icon: const Icon(Icons.fact_check_outlined),
            label: l10n.checkinButton,
          ),
          NavigationDestination(
            icon: const Icon(Icons.history),
            label: l10n.historyTitle,
          ),
          NavigationDestination(
            icon: const Icon(Icons.task_alt),
            label: l10n.tasksTitle,
          ),
          NavigationDestination(
            icon: const Icon(Icons.settings_outlined),
            label: l10n.settingsTitle,
          ),
        ],
      ),
    );
  }
}

class _ManagerShell extends StatelessWidget {
  const _ManagerShell({required this.location, required this.child});

  final String location;
  final Widget child;

  static const List<String> _tabs = ['/m/map', '/m/employees', '/m/sites'];

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final index = _tabs.indexWhere((tab) => location.startsWith(tab));

    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: index < 0 ? 0 : index,
        onDestinationSelected: (i) => context.go(_tabs[i]),
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.map_outlined),
            label: l10n.liveMapTitle,
          ),
          NavigationDestination(
            icon: const Icon(Icons.people_outline),
            label: l10n.employeesTitle,
          ),
          NavigationDestination(
            icon: const Icon(Icons.location_city_outlined),
            label: l10n.sitesTitle,
          ),
        ],
      ),
    );
  }
}
