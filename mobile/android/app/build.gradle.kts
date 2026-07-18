plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "uz.employeecontrol.employee_control"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "uz.employeecontrol.employee_control"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        // ML Kit yuz-detektsiya minSdk 21+ (ba'zi funksiyalar 23) talab qiladi.
        // Flutter 3.44 build.gradle.kts migratsiyasi bu qatorni har build'da
        // flutter.minSdkVersion=24 ga qaytaradi — 24 >= 23, ML Kit uchun yetarli.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")

            // R8 full-mode optimizatsiyasi ML Kit vision telemetriya-loggerini
            // (zzmj konstruktori) buzib, InputImage.from*() har chaqirilganda
            // NullPointerException ("getClass() on null") beryapti — natijada
            // yuz-detektsiya HAR qurilmada ishlamaydi (Firebase/ML Kit #777 kabi
            // R8 xatolari). Shu tufayli release'da minifikatsiya/shrink o'chiriladi:
            // Flutter ilovasida hajm asosan Dart AOT'dan keladi, Java-shrink kritik
            // emas; to'g'rilik muhimroq.
            isMinifyEnabled = false
            isShrinkResources = false
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
