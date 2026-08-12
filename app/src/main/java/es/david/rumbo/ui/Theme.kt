package es.david.rumbo.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import android.os.Build
import androidx.compose.ui.graphics.Color

private val AppBackground = Color(0xFFF3F3F3)
private val CardWhite = Color(0xFFFFFFFF)
private val NeutralControl = Color(0xFFE8E8EA)
private val NeutralText = Color(0xFF1B1B1D)
private val SecondaryText = Color(0xFF707074)

private val LightColors = lightColorScheme(
    primary = Color(0xFF343438),
    onPrimary = Color.White,
    primaryContainer = NeutralControl,
    onPrimaryContainer = NeutralText,
    secondary = Color(0xFF5F5F64),
    onSecondary = Color.White,
    secondaryContainer = NeutralControl,
    onSecondaryContainer = NeutralText,
    tertiary = Color(0xFF6B6B70),
    background = AppBackground,
    onBackground = NeutralText,
    surface = CardWhite,
    onSurface = NeutralText,
    surfaceVariant = Color(0xFFE6E6E8),
    onSurfaceVariant = SecondaryText,
    surfaceDim = AppBackground,
    surfaceBright = CardWhite,
    surfaceContainerLowest = CardWhite,
    surfaceContainerLow = CardWhite,
    surfaceContainer = CardWhite,
    surfaceContainerHigh = CardWhite,
    surfaceContainerHighest = CardWhite,
    outline = Color(0xFFC8C8CC),
    outlineVariant = Color(0xFFE1E1E4),
    error = Color(0xFFBA1A1A)
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFD1D1D5),
    onPrimary = Color(0xFF29292C),
    primaryContainer = Color(0xFF444448),
    onPrimaryContainer = Color(0xFFF1F1F3),
    secondary = Color(0xFFC7C7CB),
    background = Color(0xFF111113),
    surface = Color(0xFF1B1B1E),
    surfaceContainer = Color(0xFF1B1B1E),
    surfaceContainerHigh = Color(0xFF232326),
    surfaceContainerHighest = Color(0xFF29292D)
)


@Composable
fun RumboTheme(content: @Composable () -> Unit) {
    val darkTheme = isSystemInDarkTheme()
    val context = LocalContext.current
    val colors = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && darkTheme -> dynamicDarkColorScheme(context)
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> dynamicLightColorScheme(context)
        darkTheme -> DarkColors
        else -> LightColors
    }
    MaterialTheme(
        colorScheme = colors,
        content = content
    )
}
