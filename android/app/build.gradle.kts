// Shipment pre-flight checker for Android: a full-screen WebView on the live Streamlit app.
// Built by GitHub Actions (.github/workflows/android-apk.yml). APP_URL can be overridden with the
// SHIPMENT_APP_URL environment variable at build time.
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val run = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()
val appUrl = System.getenv("SHIPMENT_APP_URL") ?: "https://shipment-checker-6vvfecfprrtpxjdmf5cjtz.streamlit.app/"

android {
    namespace = "app.shipmentchecker"
    compileSdk = 34

    defaultConfig {
        applicationId = "app.shipmentchecker"
        minSdk = 26
        targetSdk = 34
        versionCode = run
        versionName = "1.0.$run"
        buildConfigField("String", "APP_URL", "\"$appUrl\"")
    }
    buildFeatures {
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.activity:activity-ktx:1.9.3")
}
