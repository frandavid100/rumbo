package es.david.rumbo.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

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

private val RumboShapes = Shapes(
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(20.dp),
    large = RoundedCornerShape(28.dp)
)

@Composable
fun RumboTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        shapes = RumboShapes,
        content = content
    )
}
