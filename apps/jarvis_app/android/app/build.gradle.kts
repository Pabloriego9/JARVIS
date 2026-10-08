plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.pabloriego.jarvis_app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.pabloriego.jarvis_app"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = 26
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("personal") {
            val signingStore = System.getenv("JARVIS_SIGNING_STORE")
            if (signingStore != null) {
                storeFile = file(signingStore)
                storePassword = System.getenv("JARVIS_SIGNING_STORE_PASSWORD")
                keyAlias = System.getenv("JARVIS_SIGNING_KEY_ALIAS")
                keyPassword = System.getenv("JARVIS_SIGNING_KEY_PASSWORD")
            }
        }
    }
    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("personal")
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

dependencies { implementation("androidx.documentfile:documentfile:1.1.0") }

gradle.taskGraph.whenReady {
    if (allTasks.any { it.name.contains("Release") } && System.getenv("JARVIS_SIGNING_STORE") == null) {
        throw GradleException("Release requiere la clave personal mediante JARVIS_SIGNING_STORE y sus variables de firma.")
    }
}
