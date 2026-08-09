package es.david.rumbo.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF286442),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFB6F1C8),
    onPrimaryContainer = Color(0xFF072113),
    secondary = Color(0xFF4F6355),
    secondaryContainer = Color(0xFFD2E8D6),
    tertiary = Color(0xFF3A656F),
    background = Color(0xFFF7FAF7),
    surface = Color(0xFFF7FAF7),
    surfaceVariant = Color(0xFFE0E5E0),
    error = Color(0xFFBA1A1A)
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF9BD5AD),
    onPrimary = Color(0xFF093821),
    primaryContainer = Color(0xFF1E5034),
    onPrimaryContainer = Color(0xFFB6F1C8),
    secondary = Color(0xFFB7CCBC),
    tertiary = Color(0xFFA2CED9),
    background = Color(0xFF101511),
    surface = Color(0xFF101511)
)

@Composable
fun RumboTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        content = content
    )
}
