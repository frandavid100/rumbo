package es.david.rumbo.ui

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.platform.LocalContext

private val AppBackground = Color(0xFFFFF5F3)
private val CardWhite = Color(0xFFFFFFFF)
private val SearchAndPanel = Color(0xFFFFDAD6)
private val SearchAndPanelStrong = Color(0xFFFFCFCB)
private val PrimaryRed = Color(0xFF8F4A50)
private val DarkText = Color(0xFF3B2023)
private val SecondaryText = Color(0xFF75565A)

private val LightColors = lightColorScheme(
    primary = PrimaryRed,
    onPrimary = Color.White,
    primaryContainer = SearchAndPanel,
    onPrimaryContainer = DarkText,
    secondary = Color(0xFF855257),
    onSecondary = Color.White,
    secondaryContainer = SearchAndPanel,
    onSecondaryContainer = DarkText,
    tertiary = Color(0xFF76565A),
    background = AppBackground,
    onBackground = DarkText,
    surface = SearchAndPanel,
    onSurface = DarkText,
    surfaceVariant = SearchAndPanel,
    onSurfaceVariant = SecondaryText,
    surfaceDim = AppBackground,
    surfaceBright = CardWhite,
    surfaceContainerLowest = CardWhite,
    surfaceContainerLow = CardWhite,
    surfaceContainer = Color(0xFFFFE9E6),
    surfaceContainerHigh = CardWhite,
    surfaceContainerHighest = SearchAndPanelStrong,
    outline = Color(0xFFAA888B),
    outlineVariant = Color(0xFFEBC0BD),
    error = Color(0xFFBA1A1A)
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFFFB2B8),
    onPrimary = Color(0xFF561D25),
    primaryContainer = Color(0xFF71333B),
    onPrimaryContainer = Color(0xFFFFDADC),
    secondary = Color(0xFFE6BDC0),
    background = Color(0xFF201A1B),
    onBackground = Color(0xFFECE0E0),
    surface = Color(0xFF292223),
    onSurface = Color(0xFFECE0E0),
    surfaceContainer = Color(0xFF302829),
    surfaceContainerHigh = Color(0xFF3B3233),
    surfaceContainerHighest = Color(0xFF473D3E),
    onSurfaceVariant = Color(0xFFD4C2C3),
    outline = Color(0xFF9D8C8D),
    outlineVariant = Color(0xFF514446)
)



private fun ColorScheme.deeperLightSurfaces(): ColorScheme {
    val sourceLow = surfaceContainerLow
    val sourceContainer = surfaceContainer
    val sourceHigh = surfaceContainerHigh
    val sourceHighest = surfaceContainerHighest
    val pageTone = lerp(sourceContainer, sourceLow, 0.28f)
    val cardTone = lerp(sourceHigh, sourceHighest, 0.24f)
    return copy(
        // Preserve Android's dynamic hue/chroma. Move the page only slightly
        // lighter than before and filled cards only slightly darker.
        background = pageTone,
        surface = cardTone,
        surfaceVariant = pageTone,
        surfaceContainerLowest = surfaceContainerLowest,
        surfaceContainerLow = sourceLow,
        surfaceContainer = sourceContainer,
        surfaceContainerHigh = sourceHigh,
        surfaceContainerHighest = cardTone
    )
}

@Composable
fun RumboTheme(content: @Composable () -> Unit) {
    val darkTheme = isSystemInDarkTheme()
    val context = LocalContext.current
    val colors = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && darkTheme ->
            dynamicDarkColorScheme(context)
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            dynamicLightColorScheme(context).deeperLightSurfaces()
        darkTheme -> DarkColors
        else -> LightColors.deeperLightSurfaces()
    }
    MaterialTheme(
        colorScheme = colors,
        content = content
    )
}
