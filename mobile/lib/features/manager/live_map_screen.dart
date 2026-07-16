import 'package:flutter/material.dart';
import 'package:maplibre_gl/maplibre_gl.dart';

import '../../l10n/generated/app_localizations.dart';

/// Xarita style URL.
///
/// TODO: o'z Martin tile-serveridagi style'ga almashtirish (PLAN.md §11),
/// masalan: `https://tiles.<domen>/styles/basic/style.json`
/// + oflayn MBTiles-pak — signal yo'q obyektlarda ham xarita ishlashi uchun.
const String kMapStyleUrl = 'https://demotiles.maplibre.org/style.json';

/// Rahbar: jonli xarita (PLAN.md §10).
class LiveMapScreen extends StatelessWidget {
  const LiveMapScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(l10n.liveMapTitle)),
      // TODO: WS `loc.{org}.{dept}` kanalidan jonli xodim-nuqtalari (klaster),
      // obyekt-poligonlari + bandlik-badge, filtrlar: bo'lim-daraxt, xodim
      // multi-select, obyekt bo'yicha (PLAN.md §10).
      body: MapLibreMap(
        styleString: kMapStyleUrl,
        initialCameraPosition: const CameraPosition(
          target: LatLng(41.311081, 69.240562), // Toshkent
          zoom: 10,
        ),
      ),
    );
  }
}
