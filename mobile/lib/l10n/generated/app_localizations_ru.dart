// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Russian (`ru`).
class AppLocalizationsRu extends AppLocalizations {
  AppLocalizationsRu([String locale = 'ru']) : super(locale);

  @override
  String get appTitle => 'Контроль сотрудников';

  @override
  String get loginTitle => 'Вход';

  @override
  String get loginButton => 'Войти';

  @override
  String get usernameLabel => 'Имя пользователя';

  @override
  String get passwordLabel => 'Пароль';

  @override
  String get activationTitle => 'Активация';

  @override
  String get inviteCodeLabel => 'Код приглашения';

  @override
  String get phoneLabel => 'Номер телефона';

  @override
  String get otpLabel => 'SMS-код подтверждения';

  @override
  String get checkinButton => 'Check-in';

  @override
  String get homeTitle => 'Главная';

  @override
  String get historyTitle => 'Моя история';

  @override
  String get tasksTitle => 'Задания';

  @override
  String get settingsTitle => 'Настройки';

  @override
  String get liveMapTitle => 'Живая карта';

  @override
  String get employeesTitle => 'Сотрудники';

  @override
  String get sitesTitle => 'Объекты';

  @override
  String get nextButton => 'Далее';

  @override
  String get backButton => 'Назад';

  @override
  String get submitButton => 'Отправить';

  @override
  String get commentLabel => 'Комментарий';

  @override
  String get checkinStepSite => 'Объект';

  @override
  String get checkinStepFace => 'Лицо';

  @override
  String get checkinStepSubmit => 'Отправка';

  @override
  String get checkinSuccessMessage =>
      'Check-in отправлен. Ожидается серверная проверка.';

  @override
  String get demoManagerToggle => 'Демо: войти в режиме руководителя';

  @override
  String get faceStepStart => 'Начать проверку лица (liveness)';

  @override
  String get faceStepRetake => 'Переснять';

  @override
  String get faceStepCaptured => 'Лицо подтверждено — liveness пройден';

  @override
  String get faceStepNotCaptured => 'Лицо ещё не проверено';

  @override
  String get faceHintInit => 'Камера запускается...';

  @override
  String get faceHintPosition => 'Поместите лицо в рамку';

  @override
  String get faceChallengeBlink => 'Моргните один раз';

  @override
  String get faceChallengeTurnLeft => 'Поверните голову налево';

  @override
  String get faceChallengeTurnRight => 'Поверните голову направо';

  @override
  String get faceChallengeSmile => 'Улыбнитесь';

  @override
  String get faceCapturing => 'Съёмка...';

  @override
  String get faceDone => 'Готово';

  @override
  String get faceCameraPermissionDenied =>
      'Нет доступа к камере. Разрешите в настройках.';

  @override
  String get faceCameraError => 'Ошибка камеры';

  @override
  String get faceStepLabel => 'Шаг';

  @override
  String get checkinResultTitle => 'Вердикт сервера';

  @override
  String get checkinVerdictPending => 'Ожидание';

  @override
  String get checkinVerdictVerified => 'Подтверждено';

  @override
  String get checkinVerdictFlagged => 'Отмечено';

  @override
  String get checkinVerdictRejected => 'Отклонено';

  @override
  String get checkinRiskScore => 'Риск-балл';

  @override
  String get checkinFaceScore => 'Балл лица';

  @override
  String get checkinInsideGeofence => 'Внутри геозоны';

  @override
  String get checkinSubmitError => 'Ошибка отправки';

  @override
  String get checkinFinish => 'Завершить';

  @override
  String get locationPermissionDenied => 'Нет доступа к геолокации';
}
