import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ru.dart';
import 'app_localizations_uz.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ru'),
    Locale('uz')
  ];

  /// No description provided for @appTitle.
  ///
  /// In uz, this message translates to:
  /// **'Xodimlar nazorati'**
  String get appTitle;

  /// No description provided for @loginTitle.
  ///
  /// In uz, this message translates to:
  /// **'Kirish'**
  String get loginTitle;

  /// No description provided for @loginButton.
  ///
  /// In uz, this message translates to:
  /// **'Kirish'**
  String get loginButton;

  /// No description provided for @usernameLabel.
  ///
  /// In uz, this message translates to:
  /// **'Foydalanuvchi nomi'**
  String get usernameLabel;

  /// No description provided for @passwordLabel.
  ///
  /// In uz, this message translates to:
  /// **'Parol'**
  String get passwordLabel;

  /// No description provided for @activationTitle.
  ///
  /// In uz, this message translates to:
  /// **'Faollashtirish'**
  String get activationTitle;

  /// No description provided for @inviteCodeLabel.
  ///
  /// In uz, this message translates to:
  /// **'Taklif kodi'**
  String get inviteCodeLabel;

  /// No description provided for @phoneLabel.
  ///
  /// In uz, this message translates to:
  /// **'Telefon raqami'**
  String get phoneLabel;

  /// No description provided for @otpLabel.
  ///
  /// In uz, this message translates to:
  /// **'SMS tasdiqlash kodi'**
  String get otpLabel;

  /// No description provided for @checkinButton.
  ///
  /// In uz, this message translates to:
  /// **'Check-in'**
  String get checkinButton;

  /// No description provided for @homeTitle.
  ///
  /// In uz, this message translates to:
  /// **'Bosh sahifa'**
  String get homeTitle;

  /// No description provided for @historyTitle.
  ///
  /// In uz, this message translates to:
  /// **'Tarixim'**
  String get historyTitle;

  /// No description provided for @tasksTitle.
  ///
  /// In uz, this message translates to:
  /// **'Topshiriqlar'**
  String get tasksTitle;

  /// No description provided for @settingsTitle.
  ///
  /// In uz, this message translates to:
  /// **'Sozlamalar'**
  String get settingsTitle;

  /// No description provided for @liveMapTitle.
  ///
  /// In uz, this message translates to:
  /// **'Jonli xarita'**
  String get liveMapTitle;

  /// No description provided for @employeesTitle.
  ///
  /// In uz, this message translates to:
  /// **'Xodimlar'**
  String get employeesTitle;

  /// No description provided for @sitesTitle.
  ///
  /// In uz, this message translates to:
  /// **'Obyektlar'**
  String get sitesTitle;

  /// No description provided for @nextButton.
  ///
  /// In uz, this message translates to:
  /// **'Keyingi'**
  String get nextButton;

  /// No description provided for @backButton.
  ///
  /// In uz, this message translates to:
  /// **'Orqaga'**
  String get backButton;

  /// No description provided for @submitButton.
  ///
  /// In uz, this message translates to:
  /// **'Yuborish'**
  String get submitButton;

  /// No description provided for @commentLabel.
  ///
  /// In uz, this message translates to:
  /// **'Izoh'**
  String get commentLabel;

  /// No description provided for @checkinStepSite.
  ///
  /// In uz, this message translates to:
  /// **'Obyekt'**
  String get checkinStepSite;

  /// No description provided for @checkinStepFace.
  ///
  /// In uz, this message translates to:
  /// **'Yuz'**
  String get checkinStepFace;

  /// No description provided for @checkinStepSubmit.
  ///
  /// In uz, this message translates to:
  /// **'Yuborish'**
  String get checkinStepSubmit;

  /// No description provided for @checkinSuccessMessage.
  ///
  /// In uz, this message translates to:
  /// **'Check-in yuborildi. Server tekshiruvi kutilmoqda.'**
  String get checkinSuccessMessage;

  /// No description provided for @demoManagerToggle.
  ///
  /// In uz, this message translates to:
  /// **'Demo: rahbar rejimida kirish'**
  String get demoManagerToggle;

  /// No description provided for @faceStepStart.
  ///
  /// In uz, this message translates to:
  /// **'Yuzni jonli tekshirishni boshlash'**
  String get faceStepStart;

  /// No description provided for @faceStepRetake.
  ///
  /// In uz, this message translates to:
  /// **'Qayta suratga olish'**
  String get faceStepRetake;

  /// No description provided for @faceStepCaptured.
  ///
  /// In uz, this message translates to:
  /// **'Yuz tasdiqlandi — liveness o\'tdi'**
  String get faceStepCaptured;

  /// No description provided for @faceStepNotCaptured.
  ///
  /// In uz, this message translates to:
  /// **'Yuz hali tekshirilmagan'**
  String get faceStepNotCaptured;

  /// No description provided for @faceHintInit.
  ///
  /// In uz, this message translates to:
  /// **'Kamera ishga tushmoqda...'**
  String get faceHintInit;

  /// No description provided for @faceHintPosition.
  ///
  /// In uz, this message translates to:
  /// **'Yuzingizni ramka ichiga joylashtiring'**
  String get faceHintPosition;

  /// No description provided for @faceChallengeBlink.
  ///
  /// In uz, this message translates to:
  /// **'Ko\'zingizni bir marta yuming va oching'**
  String get faceChallengeBlink;

  /// No description provided for @faceChallengeTurnLeft.
  ///
  /// In uz, this message translates to:
  /// **'Boshingizni chapga buring'**
  String get faceChallengeTurnLeft;

  /// No description provided for @faceChallengeTurnRight.
  ///
  /// In uz, this message translates to:
  /// **'Boshingizni o\'ngga buring'**
  String get faceChallengeTurnRight;

  /// No description provided for @faceChallengeSmile.
  ///
  /// In uz, this message translates to:
  /// **'Tabassum qiling'**
  String get faceChallengeSmile;

  /// No description provided for @faceCapturing.
  ///
  /// In uz, this message translates to:
  /// **'Suratga olinmoqda...'**
  String get faceCapturing;

  /// No description provided for @faceDone.
  ///
  /// In uz, this message translates to:
  /// **'Tayyor'**
  String get faceDone;

  /// No description provided for @faceCameraPermissionDenied.
  ///
  /// In uz, this message translates to:
  /// **'Kamera ruxsati berilmadi. Sozlamalardan ruxsat bering.'**
  String get faceCameraPermissionDenied;

  /// No description provided for @faceCameraError.
  ///
  /// In uz, this message translates to:
  /// **'Kamera xatosi'**
  String get faceCameraError;

  /// No description provided for @faceStepLabel.
  ///
  /// In uz, this message translates to:
  /// **'Bosqich'**
  String get faceStepLabel;

  /// No description provided for @checkinResultTitle.
  ///
  /// In uz, this message translates to:
  /// **'Server hukmi'**
  String get checkinResultTitle;

  /// No description provided for @checkinVerdictPending.
  ///
  /// In uz, this message translates to:
  /// **'Kutilmoqda'**
  String get checkinVerdictPending;

  /// No description provided for @checkinVerdictVerified.
  ///
  /// In uz, this message translates to:
  /// **'Tasdiqlandi'**
  String get checkinVerdictVerified;

  /// No description provided for @checkinVerdictFlagged.
  ///
  /// In uz, this message translates to:
  /// **'Bayroqlangan'**
  String get checkinVerdictFlagged;

  /// No description provided for @checkinVerdictRejected.
  ///
  /// In uz, this message translates to:
  /// **'Rad etildi'**
  String get checkinVerdictRejected;

  /// No description provided for @checkinRiskScore.
  ///
  /// In uz, this message translates to:
  /// **'Risk balli'**
  String get checkinRiskScore;

  /// No description provided for @checkinFaceScore.
  ///
  /// In uz, this message translates to:
  /// **'Yuz balli'**
  String get checkinFaceScore;

  /// No description provided for @checkinInsideGeofence.
  ///
  /// In uz, this message translates to:
  /// **'Geozona ichida'**
  String get checkinInsideGeofence;

  /// No description provided for @checkinSubmitError.
  ///
  /// In uz, this message translates to:
  /// **'Yuborishda xatolik'**
  String get checkinSubmitError;

  /// No description provided for @checkinFinish.
  ///
  /// In uz, this message translates to:
  /// **'Yakunlash'**
  String get checkinFinish;

  /// No description provided for @locationPermissionDenied.
  ///
  /// In uz, this message translates to:
  /// **'Lokatsiya ruxsati berilmadi'**
  String get locationPermissionDenied;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['ru', 'uz'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ru':
      return AppLocalizationsRu();
    case 'uz':
      return AppLocalizationsUz();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
