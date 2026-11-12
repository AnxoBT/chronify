package com.anxobt.chronify

import android.app.Activity
import android.app.DownloadManager
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.WindowInsets
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.Toast
import androidx.core.content.FileProvider
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.SecureRandom
import kotlin.concurrent.thread

/**
 * Chronify en el móvil: arranca el servidor de Python (el mismo de escritorio) en 127.0.0.1 y lo enseña
 * en un WebView. Lo que no es de la app (Spotify, enlaces a canciones, GitHub) se abre fuera.
 */
class MainActivity : Activity() {
    private lateinit var web: WebView
    private var subida: ValueCallback<Array<Uri>>? = null

    companion object {
        const val PUERTO = 8766
        const val BASE = "http://127.0.0.1:$PUERTO"
        private const val ELEGIR_ARCHIVO = 1

        /** Clave del servidor local (una por arranque de la app): otras apps del móvil también llegan a
         *  127.0.0.1, pero sin la clave el servidor no les contesta. La pantalla la recibe en ?k= (cookie). */
        val SECRETO: String by lazy {
            ByteArray(32).also { SecureRandom().nextBytes(it) }.joinToString("") { "%02x".format(it) }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.parseColor("#171d23")
        window.navigationBarColor = Color.parseColor("#0f1317")
        web = WebView(this)
        web.setBackgroundColor(Color.parseColor("#0f1317"))
        // Android 15 dibuja la app por debajo de la barra de estado (hora, batería) y de la de navegación:
        // el contenedor deja ese hueco para que no tapen la cabecera de Chronify. Su fondo pinta las barras.
        val marco = FrameLayout(this).apply {
            setBackgroundColor(Color.parseColor("#171d23"))
            addView(web)
            setOnApplyWindowInsetsListener { v, insets ->
                if (Build.VERSION.SDK_INT >= 30) {
                    val b = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout())
                    v.setPadding(b.left, b.top, b.right, b.bottom)
                } else {
                    @Suppress("DEPRECATION")
                    v.setPadding(insets.systemWindowInsetLeft, insets.systemWindowInsetTop,
                        insets.systemWindowInsetRight, insets.systemWindowInsetBottom)
                }
                insets
            }
        }
        setContentView(marco)
        configurarWeb()
        web.loadDataWithBaseURL(null, PANTALLA_CARGA, "text/html", "utf-8", null)

        if (!Python.isStarted()) Python.start(AndroidPlatform(this))
        val datos = File(filesDir, "datos").apply { mkdirs() }.absolutePath
        thread(name = "arranque") {
            Python.getInstance().getModule("chronify_android").callAttr("arrancar", datos, PUERTO, SECRETO)
            // para sincronizar por USB: el PC la lee con adb. Desde Android 11 otras apps no pueden leer esta carpeta.
            if (Build.VERSION.SDK_INT >= 30) {
                try { getExternalFilesDir(null)?.let { File(it, "clave-sincro.txt").writeText(SECRETO) } } catch (e: Exception) {}
            }
            // espera a que el servidor conteste (la primera vez extrae los archivos: unos segundos)
            repeat(200) {
                if (responde()) {
                    runOnUiThread { web.loadUrl("$BASE/?k=$SECRETO") }
                    return@thread
                }
                Thread.sleep(150)
            }
            runOnUiThread { Toast.makeText(this, "Chronify no ha podido arrancar", Toast.LENGTH_LONG).show() }
        }
    }

    private fun responde(): Boolean = try {
        (URL("$BASE/api/ping").openConnection() as HttpURLConnection).run {
            connectTimeout = 500; readTimeout = 1000
            val ok = responseCode == 200
            disconnect(); ok
        }
    } catch (e: Exception) { false }

    /** Lo llama la página: mientras haya una tarea larga (ordenar, MusicBrainz…) la pantalla no se apaga,
     *  porque con la pantalla apagada Android pausa la app y la tarea se queda parada. */
    inner class Puente {
        @JavascriptInterface
        fun mantenerPantalla(si: Boolean) = runOnUiThread {
            if (si) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    private fun configurarWeb() {
        web.addJavascriptInterface(Puente(), "ChronifyAndroid")
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            setSupportMultipleWindows(false)  // target=_blank → misma vista → se intercepta abajo
            builtInZoomControls = false
            textZoom = 100
        }
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, req: WebResourceRequest): Boolean {
                val url = req.url
                if (url.host == "127.0.0.1" && url.path == "/android/instalar") {
                    instalarActualizacion(); return true
                }
                if (url.host == "127.0.0.1" && url.port == PUERTO) return false  // la propia app
                abrirFuera(url)  // Spotify (login y canciones), MusicBrainz, GitHub…
                return true
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            // <input type=file> (Importar zip): selector de archivos de Android
            override fun onShowFileChooser(v: WebView, cb: ValueCallback<Array<Uri>>, p: FileChooserParams): Boolean {
                subida?.onReceiveValue(null)
                subida = cb
                val i = Intent(Intent.ACTION_GET_CONTENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*")
                return try {
                    startActivityForResult(Intent.createChooser(i, "Elige el zip de Exportify"), ELEGIR_ARCHIVO); true
                } catch (e: Exception) {
                    subida = null; false
                }
            }
        }
        // enlaces "descargar" (txt para pegar en Spotify): a la carpeta Descargas del móvil
        web.setDownloadListener { url, _, disposicion, tipo, _ ->
            val nombre = Regex("filename=\"?([^\";]+)").find(disposicion ?: "")?.groupValues?.get(1)
                ?: (Uri.parse(url).getQueryParameter("lista") ?: "chronify") + ".txt"
            val dm = getSystemService(DOWNLOAD_SERVICE) as DownloadManager
            dm.enqueue(DownloadManager.Request(Uri.parse(url)).setMimeType(tipo).addRequestHeader("X-Chronify-Clave", SECRETO)
                .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, nombre))
            Toast.makeText(this, "Descargando $nombre", Toast.LENGTH_SHORT).show()
        }
    }

    /** Abre el instalador de Android con el APK que ha descargado la actualización (files/datos/Chronify.apk). */
    private fun instalarActualizacion() {
        if (Build.VERSION.SDK_INT >= 26 && !packageManager.canRequestPackageInstalls()) {
            Toast.makeText(this, "Permite instalar apps de Chronify y vuelve a pulsar Actualizar", Toast.LENGTH_LONG).show()
            startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:$packageName")))
            web.loadUrl(BASE)
            return
        }
        val apk = File(filesDir, "datos/Chronify.apk")
        val uri = FileProvider.getUriForFile(this, "$packageName.archivos", apk)
        startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK))
        web.loadUrl(BASE)
    }

    private fun abrirFuera(url: Uri) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, url))
        } catch (e: Exception) {
            Toast.makeText(this, "No hay ninguna app para abrir $url", Toast.LENGTH_LONG).show()
        }
    }

    @Deprecated("Activity sin androidx: la API clásica basta")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (requestCode == ELEGIR_ARCHIVO) {
            subida?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data))
            subida = null
        } else super.onActivityResult(requestCode, resultCode, data)
    }

    @Deprecated("Activity sin androidx: la API clásica basta")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    override fun onResume() {
        super.onResume()
        // al volver del login de Spotify (navegador), refresca para ver "conectado"
        if (web.url?.startsWith(BASE) == true) Handler(Looper.getMainLooper()).postDelayed({
            web.evaluateJavascript("typeof pintarSpotify === 'function' && pintarSpotify()", null)
        }, 300)
    }
}

private const val PANTALLA_CARGA = """<html><body style="background:#0f1317;color:#8994a0;font:16px system-ui;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0">Abriendo Chronify…</body></html>"""
