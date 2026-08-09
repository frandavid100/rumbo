package es.david.rumbo

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import es.david.rumbo.data.AppRepository
import es.david.rumbo.ui.RumboApp
import es.david.rumbo.ui.RumboTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val repository = AppRepository(applicationContext)
        setContent {
            RumboTheme {
                RumboApp(repository)
            }
        }
    }
}
