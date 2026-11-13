import java.util.Properties

// Chronify para Android: la misma app de escritorio (Python + web local) dentro de un APK.
// Chaquopy mete Python en la app; MainActivity arranca el servidor de web/server.py y lo enseña en un WebView.
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

val raiz = rootDir.parentFile  // carpeta del proyecto Chronify (core/, web/, fechas.json…)

// Versión: la misma que la de escritorio (core/version.py)
val version = Regex("VERSION = \"([0-9.]+)\"").find(raiz.resolve("core/version.py").readText())!!.groupValues[1]
val (ma, mi, pa) = version.split(".").map { it.toInt() }

android {
    namespace = "com.anxobt.chronify"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.anxobt.chronify"
        minSdk = 26
        targetSdk = 35
        // +100000: la numeración se reinició en 1.0.0 (antes llegó a 1.7.0 = 10700); así cada versión sigue siendo
        // mayor que la instalada y Android la deja instalar encima.
        versionCode = 100000 + ma * 10000 + mi * 100 + pa
        versionName = version
        ndk {
            abiFilters += listOf("arm64-v8a")  // móviles actuales; x86 solo haría falta para el emulador
        }
    }

    // Clave propia de Chronify (fuera del repo: ~/.android/chronify-release.jks; datos en keystore.properties,
    // ignorado por git). Todas las versiones van firmadas con ella para que se instalen encima de la anterior.
    // Sin ese archivo (otro PC) la depuración usa la clave de depuración y la release se para.
    val claves = rootProject.file("keystore.properties")
    signingConfigs {
        if (claves.exists()) create("chronify") {
            val p = Properties().apply { claves.inputStream().use { load(it) } }
            storeFile = file(p.getProperty("storeFile"))
            storePassword = p.getProperty("storePassword")
            keyAlias = p.getProperty("keyAlias")
            keyPassword = p.getProperty("keyPassword")
        }
    }

    // Una release firmada con la clave de depuración no se instalaría encima de las anteriores:
    // sin keystore.properties (otro PC, copia sin restaurar) se para en vez de firmar con ella.
    gradle.taskGraph.whenReady {
        if (!claves.exists() && allTasks.any { it.name.contains("Release") }) {
            throw GradleException("Falta android/keystore.properties (clave de firma ~/.android/chronify-release.jks): " +
                "sin ella el APK no se instala encima del anterior")
        }
    }

    buildTypes {
        val firma = if (claves.exists()) signingConfigs.getByName("chronify") else signingConfigs.getByName("debug")
        release {
            signingConfig = firma
            isMinifyEnabled = false
        }
        debug {
            signingConfig = firma  // la misma firma: se puede pasar de una a otra sin desinstalar
        }
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
    implementation("androidx.core:core:1.15.0")  // FileProvider para instalar actualizaciones
}

// Solo el código y el conocimiento verificado: nunca .env, caché, CSV ni nada personal
val copiarPython by tasks.registering(Sync::class) {
    from(raiz) {
        include("core/**", "web/**", "conocimiento/**", "fechas.json", "reglas.defecto.json", "artistas.json")
        exclude("**/__pycache__/**", "web/icono-*.ico")
    }
    into(layout.buildDirectory.dir("chronify-py"))
}
tasks.named("preBuild") { dependsOn(copiarPython) }
tasks.matching { it.name.endsWith("PythonSources") }.configureEach { dependsOn(copiarPython) }

chaquopy {
    defaultConfig {
        version = "3.14"
    }
    sourceSets {
        getByName("main") {
            srcDir("src/main/python")
            srcDir(layout.buildDirectory.dir("chronify-py"))
        }
    }
}
