import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_mlkit_face_detection/google_mlkit_face_detection.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../l10n/generated/app_localizations.dart';
import 'liveness.dart';

/// Liveness natijasi: olingan JPEG + qurilma-hukmi.
class FaceCaptureResult {
  const FaceCaptureResult({
    required this.jpegBytes,
    required this.livenessPassed,
    required this.localMatch,
  });

  final Uint8List jpegBytes;
  final bool livenessPassed;

  /// Qurilmada sifat-darvoza + liveness o'tdimi (server 1:1 emas — u serverda).
  final bool localMatch;
}

/// To'liq ekranli yuz-tekshirish sahifasi. Muvaffaqiyatda [FaceCaptureResult]
/// bilan `pop` qiladi.
class FaceCaptureScreen extends StatelessWidget {
  const FaceCaptureScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: Text(l10n.checkinStepFace),
      ),
      body: FaceLivenessView(
        onCaptured: (result) => Navigator.of(context).pop(result),
      ),
    );
  }
}

/// Old kamera oqimi + ML Kit yuz-detektsiya bilan liveness challenge'lari
/// (PLAN.md §6). Sifat-darvozadan so'ng 2 ta tasodifiy challenge; hammasi
/// o'tsa — still JPEG olinadi va [onCaptured] chaqiriladi.
class FaceLivenessView extends StatefulWidget {
  const FaceLivenessView({super.key, required this.onCaptured});

  final ValueChanged<FaceCaptureResult> onCaptured;

  @override
  State<FaceLivenessView> createState() => _FaceLivenessViewState();
}

enum _Phase { init, permissionDenied, gate, challenge, capturing, done, error }

// Old (selfie) kamera oqimida ML Kit InputImage'ga aylantirish uchun qurilma
// orientatsiyasi -> gradus jadvali (ML Kit rasmiy namunasidan).
const Map<DeviceOrientation, int> _orientations = {
  DeviceOrientation.portraitUp: 0,
  DeviceOrientation.landscapeLeft: 90,
  DeviceOrientation.portraitDown: 180,
  DeviceOrientation.landscapeRight: 270,
};

class _FaceLivenessViewState extends State<FaceLivenessView> {
  CameraController? _controller;
  FaceDetector? _detector;
  CameraDescription? _camera;

  bool _busy = false; // kadr qayta ishlanmoqda (throttle)
  bool _streaming = false;
  bool _disposed = false;

  late List<LivenessChallenge> _sequence;
  int _index = 0;
  ChallengeTracker? _tracker;

  _Phase _phase = _Phase.init;
  String? _errorText;

  @override
  void initState() {
    super.initState();
    _sequence = pickLivenessSequence();
    _start();
  }

  Future<void> _start() async {
    try {
      final status = await Permission.camera.request();
      if (!status.isGranted) {
        _set(() => _phase = _Phase.permissionDenied);
        return;
      }

      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        _fail('no-camera');
        return;
      }
      final front = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.front,
        orElse: () => cameras.first,
      );
      _camera = front;

      final controller = CameraController(
        front,
        ResolutionPreset.medium,
        enableAudio: false,
        imageFormatGroup: Platform.isAndroid
            ? ImageFormatGroup.nv21
            : ImageFormatGroup.bgra8888,
      );
      await controller.initialize();
      if (_disposed) {
        await controller.dispose();
        return;
      }

      _detector = FaceDetector(
        options: FaceDetectorOptions(
          enableClassification: true,
          enableTracking: true,
          performanceMode: FaceDetectorMode.fast,
          minFaceSize: 0.15,
        ),
      );
      _controller = controller;
      _set(() => _phase = _Phase.gate);

      await controller.startImageStream(_onImage);
      _streaming = true;
    } catch (e) {
      _fail(e.toString());
    }
  }

  Future<void> _onImage(CameraImage image) async {
    if (_busy || _disposed) return;
    final detector = _detector;
    final controller = _controller;
    if (detector == null || controller == null) return;
    if (_phase != _Phase.gate && _phase != _Phase.challenge) return;

    final inputImage = _toInputImage(image, controller);
    if (inputImage == null) return;

    _busy = true;
    try {
      final faces = await detector.processImage(inputImage);
      if (_disposed) return;
      _handleFaces(faces, image);
    } catch (_) {
      // Vaqtinchalik detektsiya xatolarini e'tiborsiz qoldiramiz.
    } finally {
      _busy = false;
    }
  }

  void _handleFaces(List<Face> faces, CameraImage image) {
    final signals = _signals(faces, image);

    switch (_phase) {
      case _Phase.gate:
        if (FaceQuality.passes(signals)) {
          _index = 0;
          _tracker = ChallengeTracker(_sequence[0]);
          _set(() => _phase = _Phase.challenge);
        }
      case _Phase.challenge:
        final tracker = _tracker;
        if (tracker == null || signals.faceCount != 1) return;
        if (tracker.feed(signals)) {
          if (_index + 1 < _sequence.length) {
            _index += 1;
            _tracker = ChallengeTracker(_sequence[_index]);
            _set(() {}); // keyingi challenge ko'rsatiladi
          } else {
            _capture();
          }
        }
      default:
        break;
    }
  }

  FaceSignals _signals(List<Face> faces, CameraImage image) {
    if (faces.isEmpty) return const FaceSignals();
    // Eng katta yuzni tanlaymiz.
    faces.sort((a, b) => (b.boundingBox.width * b.boundingBox.height)
        .compareTo(a.boundingBox.width * a.boundingBox.height));
    final f = faces.first;
    final shortSide =
        image.width < image.height ? image.width : image.height;
    final ratio = shortSide == 0 ? 0.0 : f.boundingBox.width / shortSide;
    return FaceSignals(
      faceCount: faces.length,
      faceWidthRatio: ratio,
      leftEyeOpen: f.leftEyeOpenProbability,
      rightEyeOpen: f.rightEyeOpenProbability,
      smiling: f.smilingProbability,
      headYaw: f.headEulerAngleY,
    );
  }

  InputImage? _toInputImage(CameraImage image, CameraController controller) {
    final camera = _camera;
    if (camera == null) return null;
    final sensorOrientation = camera.sensorOrientation;

    InputImageRotation? rotation;
    if (Platform.isIOS) {
      rotation = InputImageRotationValue.fromRawValue(sensorOrientation);
    } else {
      final compensation = _orientations[controller.value.deviceOrientation];
      if (compensation == null) return null;
      final rotationDeg = camera.lensDirection == CameraLensDirection.front
          ? (sensorOrientation + compensation) % 360
          : (sensorOrientation - compensation + 360) % 360;
      rotation = InputImageRotationValue.fromRawValue(rotationDeg);
    }
    if (rotation == null) return null;

    final format = InputImageFormatValue.fromRawValue(image.format.raw);
    if (format == null) return null;
    if (Platform.isAndroid && format != InputImageFormat.nv21) return null;
    if (Platform.isIOS && format != InputImageFormat.bgra8888) return null;

    if (image.planes.length != 1) return null;
    final plane = image.planes.first;

    return InputImage.fromBytes(
      bytes: plane.bytes,
      metadata: InputImageMetadata(
        size: Size(image.width.toDouble(), image.height.toDouble()),
        rotation: rotation,
        format: format,
        bytesPerRow: plane.bytesPerRow,
      ),
    );
  }

  Future<void> _capture() async {
    if (_phase == _Phase.capturing || _disposed) return;
    _set(() => _phase = _Phase.capturing);
    final controller = _controller;
    if (controller == null) return;
    try {
      if (_streaming) {
        await controller.stopImageStream();
        _streaming = false;
      }
      final file = await controller.takePicture();
      final bytes = await file.readAsBytes();
      if (_disposed) return;
      _set(() => _phase = _Phase.done);
      widget.onCaptured(FaceCaptureResult(
        jpegBytes: bytes,
        livenessPassed: true,
        localMatch: true,
      ));
    } catch (e) {
      _fail(e.toString());
    }
  }

  void _fail(String message) {
    _set(() {
      _phase = _Phase.error;
      _errorText = message;
    });
  }

  void _set(VoidCallback fn) {
    if (_disposed || !mounted) return;
    setState(fn);
  }

  @override
  void dispose() {
    _disposed = true;
    final controller = _controller;
    final detector = _detector;
    _controller = null;
    _detector = null;
    // Resurslarni fonda bo'shatamiz (dispose sinxron bo'lishi kerak).
    () async {
      try {
        if (_streaming) await controller?.stopImageStream();
      } catch (_) {}
      await controller?.dispose();
      await detector?.close();
    }();
    super.dispose();
  }

  String _instruction(AppLocalizations l10n, LivenessChallenge c) {
    switch (c) {
      case LivenessChallenge.blink:
        return l10n.faceChallengeBlink;
      case LivenessChallenge.turnLeft:
        return l10n.faceChallengeTurnLeft;
      case LivenessChallenge.turnRight:
        return l10n.faceChallengeTurnRight;
      case LivenessChallenge.smile:
        return l10n.faceChallengeSmile;
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final controller = _controller;

    if (_phase == _Phase.permissionDenied) {
      return _MessagePanel(
        icon: Icons.videocam_off,
        text: l10n.faceCameraPermissionDenied,
      );
    }
    if (_phase == _Phase.error) {
      return _MessagePanel(
        icon: Icons.error_outline,
        text: '${l10n.faceCameraError}: ${_errorText ?? ''}',
      );
    }
    if (controller == null || !controller.value.isInitialized) {
      return _MessagePanel(
        icon: Icons.camera_alt_outlined,
        text: l10n.faceHintInit,
        showSpinner: true,
      );
    }

    final String hint;
    switch (_phase) {
      case _Phase.gate:
        hint = l10n.faceHintPosition;
      case _Phase.challenge:
        hint = _instruction(l10n, _sequence[_index]);
      case _Phase.capturing:
        hint = l10n.faceCapturing;
      case _Phase.done:
        hint = l10n.faceDone;
      default:
        hint = l10n.faceHintInit;
    }

    final total = _sequence.length;
    final current = (_phase == _Phase.gate) ? 0 : _index + 1;

    return Stack(
      fit: StackFit.expand,
      children: [
        Center(
          child: AspectRatio(
            aspectRatio: 1 / controller.value.aspectRatio,
            child: CameraPreview(controller),
          ),
        ),
        // Yuz uchun oval yo'naltirgich.
        IgnorePointer(
          child: Center(
            child: FractionallySizedBox(
              widthFactor: 0.72,
              heightFactor: 0.5,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.white70, width: 2),
                  borderRadius: BorderRadius.circular(200),
                ),
              ),
            ),
          ),
        ),
        // Ko'rsatma va progress.
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          child: Container(
            padding: const EdgeInsets.fromLTRB(24, 20, 24, 40),
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Colors.transparent, Colors.black87],
              ),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (total > 0)
                  Text(
                    '${l10n.faceStepLabel} $current/$total',
                    style: const TextStyle(color: Colors.white70, fontSize: 13),
                  ),
                const SizedBox(height: 8),
                Text(
                  hint,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    for (var i = 0; i < total; i++)
                      Container(
                        margin: const EdgeInsets.symmetric(horizontal: 4),
                        width: 12,
                        height: 12,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: i < _index ||
                                  _phase == _Phase.capturing ||
                                  _phase == _Phase.done
                              ? Colors.greenAccent
                              : (i == _index && _phase == _Phase.challenge
                                  ? Colors.white
                                  : Colors.white24),
                        ),
                      ),
                  ],
                ),
                if (_phase == _Phase.capturing) ...[
                  const SizedBox(height: 16),
                  const CircularProgressIndicator(color: Colors.white),
                ],
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _MessagePanel extends StatelessWidget {
  const _MessagePanel({
    required this.icon,
    required this.text,
    this.showSpinner = false,
  });

  final IconData icon;
  final String text;
  final bool showSpinner;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 64, color: Colors.white70),
            const SizedBox(height: 16),
            Text(
              text,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white, fontSize: 16),
            ),
            if (showSpinner) ...[
              const SizedBox(height: 24),
              const CircularProgressIndicator(color: Colors.white),
            ],
          ],
        ),
      ),
    );
  }
}
