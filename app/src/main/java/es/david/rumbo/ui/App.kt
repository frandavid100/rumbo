@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package es.david.rumbo.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AddCircle
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Eco
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.Grain
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.LocalFlorist
import androidx.compose.material.icons.filled.Opacity
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material.icons.filled.Restaurant
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import es.david.rumbo.data.AppRepository
import es.david.rumbo.logic.FoodSimilarityEngine
import es.david.rumbo.logic.RecommendationEngine
import es.david.rumbo.model.ActivityLevel
import es.david.rumbo.model.AppData
import es.david.rumbo.model.BodyAssessment
import es.david.rumbo.model.DietCompliance
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.Measurement
import es.david.rumbo.model.RecommendedGoal
import es.david.rumbo.model.Sex
import es.david.rumbo.model.UserProfile
import es.david.rumbo.model.WeightGoal
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.abs
import kotlin.math.pow

private enum class Screen(val label: String, val icon: ImageVector, val inNavigation: Boolean = true) {
    HOME("Inicio", Icons.Default.Home),
    ADD("Añadir", Icons.Default.AddCircle, false),
    MEASUREMENT_DETAIL("Medición", Icons.Default.Home, false),
    EDIT_MEASUREMENT("Editar medición", Icons.Default.Home, false),
    FOODS("Alimentos", Icons.Default.Restaurant),
    ADD_FOOD("Añadir alimento", Icons.Default.Restaurant, false),
    FOOD_DETAIL("Alimento", Icons.Default.Restaurant, false),
    EDIT_FOOD("Editar alimento", Icons.Default.Restaurant, false),
    PROFILE("Perfiles", Icons.Default.Person),
    GOAL_EXPLANATION("Objetivos", Icons.Default.Home, false),
    BODY_EXPLANATION("Situación corporal", Icons.Default.Home, false),
    RECOMMENDATION_EXPLANATION("Recomendación", Icons.Default.Home, false)
}

@Composable
fun RumboApp(repository: AppRepository) {
    var data by remember { mutableStateOf(repository.load()) }
    var screenName by rememberSaveable {
        mutableStateOf(if (data.isActiveProfileReady) Screen.HOME.name else Screen.PROFILE.name)
    }
    var selectedMeasurementId by rememberSaveable { mutableStateOf<Long?>(null) }
    var selectedFoodId by rememberSaveable { mutableStateOf<Long?>(null) }
    val screen = Screen.valueOf(screenName)
    val profileReady = data.isActiveProfileReady
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    val exportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/json")
    ) { uri ->
        uri ?: return@rememberLauncherForActivityResult
        runCatching {
            context.contentResolver.openOutputStream(uri)?.use {
                it.write(repository.exportJson().toByteArray(Charsets.UTF_8))
            } ?: error("No se pudo abrir el archivo")
        }.onSuccess {
            scope.launch { snackbarHostState.showSnackbar("Copia de seguridad guardada") }
        }.onFailure {
            scope.launch { snackbarHostState.showSnackbar("No se pudo guardar la copia") }
        }
    }

    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri ->
        uri ?: return@rememberLauncherForActivityResult
        runCatching {
            val raw = context.contentResolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() }
                ?: error("No se pudo leer el archivo")
            repository.importJson(raw)
        }.onSuccess {
            data = it
            screenName = if (it.isActiveProfileReady) Screen.HOME.name else Screen.PROFILE.name
            scope.launch { snackbarHostState.showSnackbar("Copia importada") }
        }.onFailure {
            scope.launch { snackbarHostState.showSnackbar("El archivo no contiene una copia válida") }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                navigationIcon = {
                    if (!screen.inNavigation) {
                        IconButton(onClick = {
                            screenName = when {
                                screen == Screen.EDIT_MEASUREMENT && selectedMeasurementId != null ->
                                    Screen.MEASUREMENT_DETAIL.name
                                screen == Screen.EDIT_FOOD && selectedFoodId != null ->
                                    Screen.FOOD_DETAIL.name
                                screen in setOf(Screen.ADD_FOOD, Screen.FOOD_DETAIL) -> Screen.FOODS.name
                                else -> Screen.HOME.name
                            }
                        }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                        }
                    }
                },
                title = {
                    Column {
                        Text("Rumbo", fontWeight = FontWeight.SemiBold)
                        Text(
                            "Calorías con contexto, no con prisas",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                actions = {
                    if (data.profile != null) {
                        ProfileSwitcher(
                            profiles = data.profiles.map { it.profile },
                            activeProfile = data.profile,
                            onSelect = {
                                data = repository.switchProfile(it)
                                screenName = if (data.isActiveProfileReady) Screen.HOME.name else Screen.PROFILE.name
                            },
                            onManage = { screenName = Screen.PROFILE.name }
                        )
                    }
                }
            )
        },
        bottomBar = {
            if (profileReady && screen.inNavigation) {
                NavigationBar {
                    Screen.entries.filter { it.inNavigation }.forEach { destination ->
                        NavigationBarItem(
                            selected = screen == destination,
                            onClick = { screenName = destination.name },
                            icon = { Icon(destination.icon, contentDescription = destination.label) },
                            label = { Text(destination.label) }
                        )
                    }
                }
            }
        },
        floatingActionButton = {
            if (profileReady && screen in setOf(Screen.HOME, Screen.FOODS)) {
                val addingFood = screen == Screen.FOODS
                FloatingActionButton(onClick = {
                    screenName = if (addingFood) Screen.ADD_FOOD.name else Screen.ADD.name
                }) {
                    Icon(
                        Icons.Default.Add,
                        contentDescription = if (addingFood) "Añadir un alimento" else "Añadir una medición"
                    )
                }
            }
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            when {
                !profileReady -> ProfileScreen(
                    profile = data.profile,
                    profiles = data.profiles.map { it.profile },
                    isOnboarding = data.profile == null,
                    requiresBaseline = true,
                    onCreate = { profile, baseline ->
                        data = repository.saveProfileWithBaseline(profile, baseline)
                        screenName = Screen.HOME.name
                    },
                    onSave = { data = repository.saveProfile(it) },
                    onSwitch = {
                        data = repository.switchProfile(it)
                        screenName = if (data.isActiveProfileReady) Screen.HOME.name else Screen.PROFILE.name
                    },
                    onDelete = { data = repository.deleteProfile(it) },
                    onExport = null,
                    onImport = { importLauncher.launch(arrayOf("application/json", "text/plain")) }
                )
                screen == Screen.HOME -> HomeScreen(
                    data = data,
                    onAdd = { screenName = Screen.ADD.name },
                    onGoalChange = { data = repository.setGoal(it) },
                    onExplainGoal = { screenName = Screen.GOAL_EXPLANATION.name },
                    onExplainBody = { screenName = Screen.BODY_EXPLANATION.name },
                    onExplainRecommendation = { screenName = Screen.RECOMMENDATION_EXPLANATION.name },
                    onOpenMeasurement = {
                        selectedMeasurementId = it
                        screenName = Screen.MEASUREMENT_DETAIL.name
                    }
                )
                screen == Screen.ADD -> AddMeasurementScreen(
                    data = data,
                    onSave = {
                        data = repository.addMeasurement(it)
                        screenName = Screen.HOME.name
                    }
                )
                screen == Screen.MEASUREMENT_DETAIL -> {
                    val measurement = data.measurements.firstOrNull { it.id == selectedMeasurementId }
                    if (measurement == null) {
                        screenName = Screen.HOME.name
                    } else {
                        MeasurementDetailScreen(
                            measurement = measurement,
                            onEdit = { screenName = Screen.EDIT_MEASUREMENT.name },
                            onDelete = {
                                data = repository.deleteMeasurement(measurement.id)
                                selectedMeasurementId = null
                                screenName = Screen.HOME.name
                            }
                        )
                    }
                }
                screen == Screen.EDIT_MEASUREMENT -> {
                    val measurement = data.measurements.firstOrNull { it.id == selectedMeasurementId }
                    if (measurement == null) {
                        screenName = Screen.HOME.name
                    } else {
                        AddMeasurementScreen(
                            data = data,
                            initial = measurement,
                            onSave = {
                                data = repository.addMeasurement(it)
                                screenName = Screen.MEASUREMENT_DETAIL.name
                            }
                        )
                    }
                }
                screen == Screen.FOODS -> FoodsScreen(
                    foods = data.foods,
                    onOpenFood = {
                        selectedFoodId = it
                        screenName = Screen.FOOD_DETAIL.name
                    }
                )
                screen == Screen.ADD_FOOD -> FoodEditorScreen(
                    foods = data.foods,
                    onSave = {
                        data = repository.saveFood(it)
                        selectedFoodId = it.id
                        screenName = Screen.FOOD_DETAIL.name
                    }
                )
                screen == Screen.FOOD_DETAIL -> {
                    val food = data.foods.firstOrNull { it.id == selectedFoodId }
                    if (food == null) {
                        screenName = Screen.FOODS.name
                    } else {
                        FoodDetailScreen(
                            food = food,
                            foods = data.foods,
                            onOpenFood = { selectedFoodId = it },
                            onEdit = { screenName = Screen.EDIT_FOOD.name },
                            onDelete = {
                                data = repository.deleteFood(food.id)
                                selectedFoodId = null
                                screenName = Screen.FOODS.name
                            }
                        )
                    }
                }
                screen == Screen.EDIT_FOOD -> {
                    val food = data.foods.firstOrNull { it.id == selectedFoodId }
                    if (food == null) {
                        screenName = Screen.FOODS.name
                    } else {
                        FoodEditorScreen(
                            foods = data.foods,
                            initial = food,
                            onSave = {
                                data = repository.saveFood(it)
                                screenName = Screen.FOOD_DETAIL.name
                            }
                        )
                    }
                }
                screen == Screen.PROFILE -> ProfileScreen(
                    profile = data.profile,
                    profiles = data.profiles.map { it.profile },
                    isOnboarding = false,
                    requiresBaseline = false,
                    onCreate = { profile, baseline ->
                        data = repository.saveProfileWithBaseline(profile, baseline)
                        screenName = Screen.HOME.name
                    },
                    onSave = {
                        data = repository.saveProfile(it)
                        scope.launch { snackbarHostState.showSnackbar("Datos personales guardados") }
                    },
                    onSwitch = {
                        data = repository.switchProfile(it)
                        screenName = if (data.isActiveProfileReady) Screen.HOME.name else Screen.PROFILE.name
                    },
                    onDelete = { data = repository.deleteProfile(it) },
                    onExport = { exportLauncher.launch("rumbo-copia-${LocalDate.now()}.json") },
                    onImport = { importLauncher.launch(arrayOf("application/json", "text/plain")) }
                )
                screen == Screen.GOAL_EXPLANATION -> GoalExplanationScreen(data)
                screen == Screen.BODY_EXPLANATION -> BodyExplanationScreen(data)
                screen == Screen.RECOMMENDATION_EXPLANATION -> RecommendationExplanationScreen(data)
            }
        }
    }
}

@Composable
private fun ProfileSwitcher(
    profiles: List<UserProfile>,
    activeProfile: UserProfile?,
    onSelect: (Long) -> Unit,
    onManage: () -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        TextButton(onClick = { expanded = true }) {
            Icon(Icons.Default.Person, contentDescription = null)
            Spacer(Modifier.width(4.dp))
            Text(activeProfile?.name ?: "Perfil", maxLines = 1)
            Icon(Icons.Default.ArrowDropDown, contentDescription = null)
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            profiles.forEach { profile ->
                DropdownMenuItem(
                    leadingIcon = {
                        if (profile.id == activeProfile?.id) {
                            Icon(Icons.Default.Check, contentDescription = null)
                        }
                    },
                    text = { Text(profile.name) },
                    onClick = {
                        expanded = false
                        onSelect(profile.id)
                    }
                )
            }
            HorizontalDivider()
            DropdownMenuItem(
                leadingIcon = { Icon(Icons.Default.PersonAdd, contentDescription = null) },
                text = { Text("Gestionar perfiles") },
                onClick = {
                    expanded = false
                    onManage()
                }
            )
        }
    }
}

@Composable
private fun HomeScreen(
    data: AppData,
    onAdd: () -> Unit,
    onGoalChange: (WeightGoal) -> Unit,
    onExplainGoal: () -> Unit,
    onExplainBody: () -> Unit,
    onExplainRecommendation: () -> Unit,
    onOpenMeasurement: (Long) -> Unit
) {
    val profile = data.profile
    val latest = data.measurements.maxWithOrNull(compareBy<Measurement> { it.date }.thenBy { it.id })
    val recommendation = latest?.recommendation
    val assessment = profile?.let { RecommendationEngine.assessBody(it, data.measurements) }
    val recommendedGoal = profile?.let { RecommendationEngine.recommendGoal(it, data.measurements) }
    val goal = RecommendationEngine.effectiveValues(data.measurements).goal

    LazyColumn(
        contentPadding = PaddingValues(start = 24.dp, top = 12.dp, end = 24.dp, bottom = 96.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp)
    ) {
        if (assessment != null) {
            item {
                BodyProgressSection(
                    profile = profile,
                    measurements = data.measurements,
                    assessment = assessment,
                    onExplain = onExplainBody
                )
            }
        }
        item { HorizontalDivider() }
        recommendedGoal?.let { result ->
            item { RecommendedGoalSection(result) }
        }
        item {
            GoalSection(
                goal = goal,
                onGoalChange = onGoalChange,
                onExplain = onExplainGoal
            )
        }
        item {
            if (recommendation == null) {
                EmptyRecommendationSection(hasMeasurements = data.measurements.isNotEmpty(), onAdd = onAdd)
            } else {
                RecommendationSection(recommendation, onExplainRecommendation)
            }
        }
        item { HorizontalDivider() }
        item {
            Text("Historial", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        }
        if (data.measurements.isEmpty()) {
            item {
                Text(
                    "Todavía no hay mediciones",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(vertical = 16.dp)
                )
            }
        } else {
            items(
                data.measurements.sortedWith(
                    compareByDescending<Measurement> { it.date }.thenByDescending { it.id }
                ),
                key = { it.id }
            ) { measurement ->
                HistoryEntry(measurement = measurement, onClick = { onOpenMeasurement(measurement.id) })
                HorizontalDivider(Modifier.padding(top = 4.dp))
            }
        }
    }
}

@Composable
private fun BodyProgressSection(
    profile: UserProfile,
    measurements: List<Measurement>,
    assessment: BodyAssessment,
    onExplain: () -> Unit
) {
    val ordered = measurements.sortedWith(compareBy<Measurement> { it.date }.thenBy { it.id })
    val heightM = profile.heightCm / 100.0
    val bmiPoints = ordered.mapNotNull { item ->
        item.weightKg?.let { item.date to it / heightM.pow(2) }
    }
    val waistPoints = ordered.mapNotNull { item ->
        item.waistCm?.let { item.date to it / profile.heightCm }
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        assessment.bmi?.let {
            BodyIndicator(
                label = "IMC",
                value = formatOneDecimal(it),
                interpretation = assessment.bmiInterpretation.orEmpty()
            )
            ProgressChart(
                points = bmiPoints,
                minimum = 15.0,
                maximum = 40.0,
                bands = listOf(
                    RiskBand(15.0, 18.5, Color(0xFFE57373)),
                    RiskBand(18.5, 25.0, Color(0xFF66BB6A)),
                    RiskBand(25.0, 30.0, Color(0xFFFFCA4B)),
                    RiskBand(30.0, 40.0, Color(0xFFE57373))
                ),
                thresholds = listOf(18.5 to "18,5", 25.0 to "25", 30.0 to "30")
            )
        }
        if (assessment.bmi != null && assessment.waistToHeightRatio != null) HorizontalDivider()
        assessment.waistToHeightRatio?.let {
            BodyIndicator(
                label = "Cintura/altura",
                value = formatTwoDecimals(it),
                interpretation = assessment.waistInterpretation.orEmpty()
            )
            ProgressChart(
                points = waistPoints,
                minimum = 0.35,
                maximum = 0.70,
                bands = listOf(
                    RiskBand(0.35, 0.40, Color(0xFFBDBDBD)),
                    RiskBand(0.40, 0.50, Color(0xFF66BB6A)),
                    RiskBand(0.50, 0.60, Color(0xFFFFCA4B)),
                    RiskBand(0.60, 0.70, Color(0xFFE57373))
                ),
                thresholds = listOf(0.40 to "0,40", 0.50 to "0,50", 0.60 to "0,60")
            )
        }
        TextButton(onClick = onExplain) {
            Text("Entender la situación corporal")
        }
    }
}

@Composable
private fun BodyIndicator(
    label: String,
    value: String,
    interpretation: String
) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(interpretation, style = MaterialTheme.typography.bodySmall)
        }
        Text(value, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
    }
}

private data class RiskBand(val start: Double, val end: Double, val color: Color)

@Composable
private fun ProgressChart(
    points: List<Pair<LocalDate, Double>>,
    minimum: Double,
    maximum: Double,
    bands: List<RiskBand>,
    thresholds: List<Pair<Double, String>>
) {
    val lineColor = MaterialTheme.colorScheme.primary
    val labelColor = MaterialTheme.colorScheme.onSurfaceVariant
    val labelSize = with(LocalDensity.current) { 11.sp.toPx() }
    Canvas(Modifier.fillMaxWidth().height(138.dp)) {
        val top = 8.dp.toPx()
        val bottom = size.height - 8.dp.toPx()
        val left = 8.dp.toPx()
        val right = size.width - 48.dp.toPx()
        val valueRange = maximum - minimum
        fun yFor(value: Double): Float = bottom -
            ((value - minimum) / valueRange).coerceIn(0.0, 1.0).toFloat() * (bottom - top)

        bands.forEach { band ->
            val bandTop = yFor(band.end)
            val bandBottom = yFor(band.start)
            drawRect(
                band.color.copy(alpha = 0.30f),
                topLeft = Offset(0f, bandTop),
                size = Size(size.width, bandBottom - bandTop)
            )
        }

        val paint = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply {
            color = labelColor.toArgb()
            textSize = labelSize
            textAlign = android.graphics.Paint.Align.RIGHT
            typeface = android.graphics.Typeface.create(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD)
        }
        thresholds.forEach { (threshold, label) ->
            val y = yFor(threshold)
            drawLine(labelColor.copy(alpha = 0.35f), Offset(0f, y), Offset(size.width, y), strokeWidth = 1.dp.toPx())
            drawContext.canvas.nativeCanvas.drawText(label, size.width - 4.dp.toPx(), y - 3.dp.toPx(), paint)
        }

        if (points.isNotEmpty()) {
            val firstDay = points.minOf { it.first }.toEpochDay()
            val lastDay = points.maxOf { it.first }.toEpochDay()
            val dayRange = (lastDay - firstDay).coerceAtLeast(1L)
            val offsets = points.map { (date, value) ->
                val x = if (points.size == 1) {
                    (left + right) / 2f
                } else {
                    left + ((date.toEpochDay() - firstDay).toFloat() / dayRange.toFloat()) * (right - left)
                }
                Offset(x, yFor(value))
            }
            offsets.zipWithNext().forEach { (start, end) ->
                drawLine(lineColor, start, end, strokeWidth = 3.dp.toPx(), cap = StrokeCap.Round)
            }
            offsets.forEach { point ->
                drawCircle(Color.White, radius = 5.dp.toPx(), center = point)
                drawCircle(lineColor, radius = 3.5.dp.toPx(), center = point)
            }
        }
    }
    if (points.isNotEmpty()) {
        val first = points.first().first.format(DateTimeFormatter.ofPattern("dd/MM/yy"))
        val last = points.last().first.format(DateTimeFormatter.ofPattern("dd/MM/yy"))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(first, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (last != first) {
                Text(last, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun RecommendedGoalSection(recommendation: RecommendedGoal) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            "Objetivo recomendado",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            recommendation.goal.label,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary
        )
        Text(
            recommendation.explanation,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun GoalSection(
    goal: WeightGoal,
    onGoalChange: (WeightGoal) -> Unit,
    onExplain: () -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SelectorField(
            label = "Objetivo elegido",
            selectedLabel = goal.label,
            options = WeightGoal.entries,
            optionLabel = { it.label },
            onSelect = onGoalChange,
            onClear = null
        )
        TextButton(onClick = onExplain) { Text("Entender los objetivos") }
    }
}

@Composable
private fun RecommendationSection(
    recommendation: es.david.rumbo.model.Recommendation,
    onExplain: () -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(verticalAlignment = Alignment.Bottom) {
            Text(
                recommendation.calories.toString(),
                style = MaterialTheme.typography.displayMedium,
                fontWeight = FontWeight.Bold,
                color = if (recommendation.isSafetyLimited) {
                    MaterialTheme.colorScheme.tertiary
                } else MaterialTheme.colorScheme.primary
            )
            Spacer(Modifier.width(6.dp))
            Text("kcal/día", modifier = Modifier.padding(bottom = 8.dp))
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            MacroValue("Proteína", recommendation.proteinGrams)
            MacroValue("Hidratos", recommendation.carbohydrateGrams)
            MacroValue("Grasa", recommendation.fatGrams)
        }
        if (recommendation.calculation != null) {
            TextButton(onClick = onExplain) {
                Text("Entender la recomendación")
            }
        }
    }
}

@Composable
private fun GoalExplanationScreen(data: AppData) {
    val goal = RecommendationEngine.effectiveValues(data.measurements).goal
    val assessment = data.profile?.let { RecommendationEngine.assessGoal(it, data.measurements) }
    val recommended = data.profile?.let { RecommendationEngine.recommendGoal(it, data.measurements) }

    LazyColumn(
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item {
            Text("Entender los objetivos", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        }
        item {
            NarrativeSection(
                title = "Objetivo recomendado: ${recommended?.goal?.label ?: "—"}",
                body = recommended?.explanation
                    ?: "Todavía no hay suficientes datos corporales para proponer un objetivo."
            )
        }
        item {
            NarrativeSection(
                title = "Objetivo elegido: ${goal.label}",
                body = assessment?.let { "${it.headline}. ${it.explanation}" }
                    ?: "Este objetivo se utilizará para orientar la recomendación energética."
            )
        }
        item {
            NarrativeSection(
                title = "Qué cambia al elegir un objetivo",
                body = "El objetivo indica la dirección y la velocidad prudente que debe intentar favorecer la recomendación: perder peso, mantenerlo o ganarlo. No promete por sí solo perder grasa o ganar músculo; para eso también importan el entrenamiento, la proteína, el descanso y la constancia."
            )
        }
        item {
            NarrativeSection(
                title = "Por qué no siempre se aplica literalmente",
                body = "Rumbo contrasta la elección con el IMC, la relación cintura/altura y la evolución registrada. Si perder o ganar peso no parece razonable con esos indicadores, limita el ajuste o recomienda mantener y observar en vez de producir una dieta potencialmente perjudicial."
            )
        }
        item {
            Text(
                "Cada cambio de objetivo queda fechado. Las recomendaciones anteriores conservan el objetivo que estaba vigente cuando se calcularon.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun BodyExplanationScreen(data: AppData) {
    val assessment = data.profile?.let { RecommendationEngine.assessBody(it, data.measurements) }
    val uriHandler = LocalUriHandler.current

    LazyColumn(
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item {
            Text("Entender la situación corporal", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        }
        assessment?.bmi?.let { bmi ->
            item {
                NarrativeSection(
                    title = "IMC: ${formatOneDecimal(bmi)} · ${assessment.bmiInterpretation.orEmpty()}",
                    body = "El IMC relaciona peso y altura y sirve para estimar riesgo en población adulta. Es útil como primera señal, pero no distingue grasa de músculo ni describe por completo la composición corporal."
                )
            }
        }
        assessment?.waistToHeightRatio?.let { ratio ->
            item {
                NarrativeSection(
                    title = "Cintura/altura: ${formatTwoDecimals(ratio)} · ${assessment.waistInterpretation.orEmpty()}",
                    body = "La relación cintura/altura añade información sobre la grasa abdominal. Entre 0,40 y 0,49 suele considerarse saludable; entre 0,50 y 0,59 indica riesgo aumentado; y desde 0,60, riesgo alto. Por debajo de 0,40 también conviene interpretar el resultado con cautela."
                )
            }
        }
        item {
            NarrativeSection(
                title = "Cómo se usan juntos",
                body = "Rumbo no decide a partir de una sola cifra. Usa el IMC como contexto general y la cintura/altura como señal abdominal. Si ambos evolucionan de forma distinta, evita atribuir automáticamente cualquier cambio de peso a grasa o músculo y prefiere mantener la recomendación hasta disponer de más datos."
            )
        }
        item {
            TextButton(
                onClick = {
                    uriHandler.openUri("https://www.nice.org.uk/guidance/ng246/chapter/Identifying-and-assessing-overweight-obesity-and-central-adiposity")
                }
            ) { Text("Consultar los criterios médicos de NICE") }
        }
    }
}

@Composable
private fun RecommendationExplanationScreen(data: AppData) {
    val latest = data.measurements.maxWithOrNull(compareBy<Measurement> { it.date }.thenBy { it.id })
    val recommendation = latest?.recommendation
    val calculation = recommendation?.calculation
    val profile = data.profile
    val goal = RecommendationEngine.effectiveValues(data.measurements).goal

    if (recommendation == null || calculation == null || profile == null) {
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Text("Todavía no hay una recomendación que explicar")
        }
        return
    }

    val direction = when {
        calculation.appliedWeeklyRateKg < 0.0 -> "perder"
        calculation.appliedWeeklyRateKg > 0.0 -> "ganar"
        else -> "mantener"
    }
    val goalText = if (calculation.appliedWeeklyRateKg == 0.0) {
        "Has elegido «${goal.label.lowercase()}». Por tanto, el cálculo no añade un déficit ni un superávit y toma el mantenimiento como referencia."
    } else {
        val adjustmentAction = if (calculation.goalAdjustmentCalories < 0.0) "resta" else "añade"
        "Has elegido «${goal.label.lowercase()}». Para $direction aproximadamente ${formatTwoDecimals(abs(calculation.appliedWeeklyRateKg))} kg por semana, la aplicación $adjustmentAction ${formatOneDecimal(abs(calculation.goalAdjustmentCalories))} kcal diarias respecto al mantenimiento."
    }

    LazyColumn(
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item {
            Text("Cómo se obtiene tu recomendación", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        }
        item {
            Text(
                "La recomendación de ${recommendation.calories} kcal/día para ${profile.name} se construye por etapas. Cada una responde a una pregunta distinta.",
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        item {
            NarrativeSection(
                title = "La energía que tu cuerpo necesita en reposo",
                body = "Aunque permanecieras todo el día en reposo, tu organismo gastaría energía para respirar, mantener la temperatura, hacer circular la sangre y sostener el funcionamiento de los órganos. Es el metabolismo basal. Rumbo lo estima en ${formatOneDecimal(calculation.restingCalories)} kcal/día mediante Mifflin–St Jeor, una fórmula que utiliza tu último peso (${formatOneDecimal(calculation.weightKg)} kg), altura (${formatOneDecimal(calculation.heightCm)} cm), edad (${calculation.ageYears} años) y el sexo usado por la fórmula. Esta cifra es solo el punto de partida, no la recomendación final."
            )
        }
        item {
            NarrativeSection(
                title = "El efecto de tu actividad",
                body = "Tu nivel actual es «${calculation.activity.label.lowercase()}»: ${calculation.activity.description.lowercase()}. Al incorporar el movimiento cotidiano y el ejercicio, Rumbo estima que necesitarías unas ${formatOneDecimal(calculation.maintenanceCalories)} kcal/día para mantener el peso si la estimación inicial fuese exacta."
            )
        }
        item {
            NarrativeSection(title = "El ajuste por tu objetivo", body = goalText)
        }
        calculation.goalSafetyExplanation?.let { safety ->
            item {
                NarrativeSection(
                    title = "Protección aplicada al objetivo",
                    body = safety.replaceFirstChar(Char::uppercaseChar) + ". La preferencia elegida queda registrada, pero no se convierte en una recomendación insegura."
                )
            }
        }
        calculation.energyLimitExplanation?.let { limit ->
            item {
                NarrativeSection(
                    title = "Límite energético",
                    body = limit.replaceFirstChar(Char::uppercaseChar) + ". Este límite modifica el cálculo en ${formatSignedKcal(calculation.energyLimitAdjustmentCalories)} kcal/día."
                )
            }
        }
        item {
            val historyChange = if (abs(calculation.historyAdjustmentCalories) < 0.05) {
                "Por ahora no añade ninguna corrección."
            } else {
                "Con esos datos aplica una corrección de ${formatSignedKcal(calculation.historyAdjustmentCalories)} kcal/día."
            }
            NarrativeSection(
                title = "Lo que aprende del historial",
                body = calculation.historyExplanation.replaceFirstChar(Char::uppercaseChar) + ". $historyChange Rumbo exige suficiente tiempo, pesos y valoraciones de cumplimiento para no reaccionar al ruido de unos pocos días."
            )
        }
        calculation.previousLimitExplanation?.let { limit ->
            item {
                NarrativeSection(
                    title = "Cambios graduales",
                    body = limit.replaceFirstChar(Char::uppercaseChar) + ". Así evita saltos bruscos provocados por una sola medición."
                )
            }
        }
        item {
            NarrativeSection(
                title = "Resultado final",
                body = "Tras combinar todas las etapas, el resultado es ${formatOneDecimal(calculation.beforeRoundingCalories)} kcal/día. Rumbo lo redondea al múltiplo de 25 más cercano para convertirlo en una cifra práctica: ${recommendation.calories} kcal/día."
            )
        }
        item {
            Text(
                "Es una estimación que se irá contrastando con la evolución real. No sustituye una valoración sanitaria individual.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun NarrativeSection(title: String, body: String) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainer)) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(body, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun MacroValue(label: String, grams: Int) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text("$grams g", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
        Text(label, style = MaterialTheme.typography.labelMedium)
    }
}

@Composable
private fun EmptyRecommendationSection(hasMeasurements: Boolean, onAdd: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(
            if (hasMeasurements) "Falta un peso" else "Todavía no hay mediciones",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold
        )
        Text(
            if (hasMeasurements) {
                "La cintura se ha guardado, pero hace falta al menos un peso para estimar las necesidades energéticas."
            } else {
                "Añade peso o cintura. La primera recomendación aparecerá en cuanto exista un peso."
            }
        )
        Button(onClick = onAdd) { Text("Añadir medición") }
    }
}

@Composable
private fun MeasurementDetailScreen(
    measurement: Measurement,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    var confirmDelete by remember { mutableStateOf(false) }
    if (confirmDelete) {
        DeleteMeasurementDialog(
            measurement = measurement,
            onConfirm = onDelete,
            onDismiss = { confirmDelete = false }
        )
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text(
            measurement.date.format(DateTimeFormatter.ofPattern("dd/MM/yyyy")),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold
        )
        DetailLine("Peso", measurement.weightKg?.let { "${formatDecimal(it)} kg" } ?: "Sin cambio")
        DetailLine("Cintura", measurement.waistCm?.let { "${formatDecimal(it)} cm" } ?: "Sin cambio")
        DetailLine("Actividad", measurement.activity?.let { "${it.label} · ${it.description}" } ?: "Se conserva la anterior")
        DetailLine("Cumplimiento", measurement.compliance?.label ?: "Sin indicar")
        DetailLine("Objetivo", measurement.goal?.label ?: "Se conserva el anterior")

        measurement.recommendation?.let { recommendation ->
            HorizontalDivider()
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom) {
                Text(
                    "${recommendation.calories}",
                    style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary
                )
                Spacer(Modifier.width(5.dp))
                Text("kcal/día", modifier = Modifier.padding(bottom = 4.dp))
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                MacroValue("Proteína", recommendation.proteinGrams)
                MacroValue("Hidratos", recommendation.carbohydrateGrams)
                MacroValue("Grasa", recommendation.fatGrams)
            }
            Text(
                recommendation.reason,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        } ?: Text(
            "Esta entrada no pudo generar una recomendación porque todavía faltaba un peso.",
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        Button(onClick = onEdit, modifier = Modifier.fillMaxWidth()) { Text("Editar entrada") }
        TextButton(onClick = { confirmDelete = true }, modifier = Modifier.fillMaxWidth()) {
            Text("Eliminar entrada", color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun DetailLine(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value)
    }
}

@Composable
private fun AddMeasurementScreen(
    data: AppData,
    initial: Measurement? = null,
    onSave: (Measurement) -> Unit
) {
    val isEditing = initial != null
    var date by rememberSaveable(initial?.id) { mutableStateOf(initial?.date ?: LocalDate.now()) }
    var weight by rememberSaveable(initial?.id) {
        mutableStateOf(initial?.weightKg?.let(::formatDecimal) ?: "")
    }
    var waist by rememberSaveable(initial?.id) {
        mutableStateOf(initial?.waistCm?.let(::formatDecimal) ?: "")
    }
    var activity by remember(initial?.id) { mutableStateOf(initial?.activity) }
    var compliance by remember(initial?.id) { mutableStateOf(initial?.compliance) }
    var goal by remember(initial?.id) { mutableStateOf(initial?.goal) }
    var error by rememberSaveable(initial?.id) { mutableStateOf<String?>(null) }
    var showDatePicker by remember { mutableStateOf(false) }
    val inherited = RecommendationEngine.effectiveValues(
        data.measurements.filterNot { it.id == initial?.id }
    )

    if (showDatePicker) {
        val initialMillis = date.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()
        val pickerState = androidx.compose.material3.rememberDatePickerState(initialSelectedDateMillis = initialMillis)
        DatePickerDialog(
            onDismissRequest = { showDatePicker = false },
            confirmButton = {
                TextButton(onClick = {
                    pickerState.selectedDateMillis?.let {
                        date = Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate()
                    }
                    showDatePicker = false
                }) { Text("Aceptar") }
            },
            dismissButton = { TextButton(onClick = { showDatePicker = false }) { Text("Cancelar") } }
        ) { DatePicker(pickerState) }
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text(
            if (isEditing) "Editar entrada" else "Nueva medición",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold
        )
        OutlinedButton(onClick = { showDatePicker = true }, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Default.CalendarMonth, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text(date.format(DateTimeFormatter.ofPattern("dd/MM/yyyy")))
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            NumericField("Peso (kg)", weight, { weight = it }, Modifier.weight(1f))
            NumericField("Cintura (cm)", waist, { waist = it }, Modifier.weight(1f))
        }
        Text(
            if (isEditing) {
                "Los campos vacíos indican que esta entrada no modificó ese dato."
            } else {
                "Puedes rellenar solo uno de los dos. Los valores vacíos no borran la última medición."
            },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        SelectorField(
            label = "Actividad",
            selectedLabel = activity?.label ?: "Usar la anterior · ${inherited.activity.label}",
            options = ActivityLevel.entries,
            optionLabel = { "${it.label} · ${it.description}" },
            onSelect = { activity = it },
            onClear = { activity = null }
        )
        SelectorField(
            label = "Cumplimiento desde la medición anterior",
            selectedLabel = compliance?.label ?: "Sin indicar",
            options = DietCompliance.entries,
            optionLabel = { it.label },
            onSelect = { compliance = it },
            onClear = { compliance = null }
        )
        if (isEditing) {
            SelectorField(
                label = "Cambio de objetivo",
                selectedLabel = goal?.label ?: "Sin cambio",
                options = WeightGoal.entries,
                optionLabel = { it.label },
                onSelect = { goal = it },
                onClear = { goal = null }
            )
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        Button(
            onClick = {
                val parsedWeight = parseDecimal(weight)
                val parsedWaist = parseDecimal(waist)
                error = when {
                    weight.isNotBlank() && parsedWeight == null -> "El peso no es válido."
                    waist.isNotBlank() && parsedWaist == null -> "La cintura no es válida."
                    !isEditing && parsedWeight == null && parsedWaist == null -> "Introduce al menos el peso o la cintura."
                    isEditing && parsedWeight == null && parsedWaist == null && activity == null &&
                        compliance == null && goal == null -> "La entrada no puede quedar completamente vacía."
                    parsedWeight != null && parsedWeight !in 30.0..350.0 -> "El peso debe estar entre 30 y 350 kg."
                    parsedWaist != null && parsedWaist !in 35.0..250.0 -> "La cintura debe estar entre 35 y 250 cm."
                    else -> null
                }
                if (error == null) {
                    onSave(
                        Measurement(
                            id = initial?.id ?: System.currentTimeMillis(),
                            date = date,
                            weightKg = parsedWeight,
                            waistCm = parsedWaist,
                            activity = activity,
                            compliance = compliance,
                            goal = if (isEditing) goal else null
                        )
                    )
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) { Text(if (isEditing) "Guardar cambios" else "Guardar y recalcular") }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun DeleteMeasurementDialog(
    measurement: Measurement,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("¿Eliminar esta medición?") },
        text = {
            Text(
                "Se eliminará la entrada del ${measurement.date.format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}. Esta acción no se puede deshacer."
            )
        },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text("Eliminar", color = MaterialTheme.colorScheme.error)
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } }
    )
}

@Composable
private fun HistoryEntry(measurement: Measurement, onClick: () -> Unit) {
    val isGoalChange = measurement.goal != null && measurement.weightKg == null &&
        measurement.waistCm == null && measurement.activity == null && measurement.compliance == null
    val summary = if (isGoalChange) {
        "Cambio de objetivo · ${measurement.goal.label}"
    } else {
        buildList {
            measurement.weightKg?.let { add("${formatDecimal(it)} kg") }
            measurement.waistCm?.let { add("${formatDecimal(it)} cm de cintura") }
        }.joinToString(" · ").ifBlank { "Registro de contexto" }
    }

    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(
                measurement.date.format(DateTimeFormatter.ofPattern("dd/MM/yyyy")),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold
            )
            Text(summary, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (measurement.recommendation != null) {
            Text(
                "${measurement.recommendation.calories}\nkcal/día",
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.End,
                style = MaterialTheme.typography.bodyMedium
            )
        } else {
            Text("Pendiente", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun FoodsScreen(foods: List<Food>, onOpenFood: (Long) -> Unit) {
    var query by rememberSaveable { mutableStateOf("") }
    val normalizedQuery = normalizeSearch(query)
    val filtered = remember(foods, normalizedQuery) {
        foods.filter { food ->
            normalizedQuery.isBlank() || listOfNotNull(
                food.name,
                food.category.label,
                food.brand,
                food.family,
                food.subcategory,
                food.retailer,
                food.barcode
            ).any { normalizeSearch(it).contains(normalizedQuery) }
        }.sortedWith(compareBy<Food> { it.category.ordinal }.thenBy { it.name.lowercase() })
    }
    val grouped = remember(filtered) { filtered.groupBy { it.category } }

    LazyColumn(
        contentPadding = PaddingValues(start = 20.dp, top = 16.dp, end = 20.dp, bottom = 96.dp),
        verticalArrangement = Arrangement.spacedBy(0.dp)
    ) {
        item {
            Text("Alimentos", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(12.dp))
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("Buscar por nombre o categoría") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                singleLine = true
            )
            Spacer(Modifier.height(8.dp))
            Text(
                "${foods.size} alimentos · valores nutricionales por 100 g o 100 ml",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(12.dp))
        }
        FoodCategory.entries.forEach { category ->
            val categoryFoods = grouped[category].orEmpty()
            if (categoryFoods.isNotEmpty()) {
                item(key = "header_${category.name}") {
                    Text(
                        category.label,
                        modifier = Modifier.padding(top = 12.dp, bottom = 5.dp),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
                items(categoryFoods, key = { it.id }) { food ->
                    FoodListEntry(food = food, onClick = { onOpenFood(food.id) })
                    HorizontalDivider()
                }
            }
        }
        if (filtered.isEmpty()) {
            item {
                Text(
                    if (foods.isEmpty()) "Todavía no hay alimentos." else "No hay resultados para «$query».",
                    modifier = Modifier.padding(vertical = 24.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun FoodListEntry(food: Food, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        FoodCategoryBadge(food.category)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(food.name, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyLarge)
            Text(
                "P ${formatNutrient(food.proteinGrams)} · H ${formatNutrient(food.carbohydrateGrams)} · " +
                    "G ${formatNutrient(food.fatGrams)} · " +
                    (food.fiberGrams?.let { "Fibra ${formatDecimal(it)} g" } ?: "Fibra no indicada"),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        Text(
            food.calories?.let { "${formatDecimal(it)}\nkcal" } ?: "—\nkcal",
            textAlign = TextAlign.End,
            fontWeight = FontWeight.SemiBold
        )
    }
}

@Composable
private fun FoodCategoryBadge(category: FoodCategory) {
    val color = foodCategoryColor(category)
    Box(
        Modifier.size(40.dp).background(color.copy(alpha = 0.16f), CircleShape),
        contentAlignment = Alignment.Center
    ) {
        Icon(foodCategoryIcon(category), contentDescription = category.label, tint = color)
    }
}

private fun foodCategoryColor(category: FoodCategory): Color = when (category) {
    FoodCategory.CARBOHYDRATE -> Color(0xFF9A6700)
    FoodCategory.FRUIT -> Color(0xFF9C3D78)
    FoodCategory.FAT -> Color(0xFFD05A00)
    FoodCategory.PROTEIN -> Color(0xFF2563A6)
    FoodCategory.VEGETABLE -> Color(0xFF287A3D)
    FoodCategory.OTHER -> Color(0xFF666B73)
}

private fun foodCategoryIcon(category: FoodCategory): ImageVector = when (category) {
    FoodCategory.CARBOHYDRATE -> Icons.Default.Grain
    FoodCategory.FRUIT -> Icons.Default.LocalFlorist
    FoodCategory.FAT -> Icons.Default.Opacity
    FoodCategory.PROTEIN -> Icons.Default.FitnessCenter
    FoodCategory.VEGETABLE -> Icons.Default.Eco
    FoodCategory.OTHER -> Icons.Default.Restaurant
}

@Composable
private fun FoodDetailScreen(
    food: Food,
    foods: List<Food>,
    onOpenFood: (Long) -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    var confirmDelete by remember { mutableStateOf(false) }
    val uriHandler = LocalUriHandler.current
    val similarFoods = FoodSimilarityEngine.findSimilar(food, foods)
    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("¿Eliminar ${food.name}?") },
            text = { Text("Se eliminará del catálogo de alimentos. Esta acción no se puede deshacer.") },
            confirmButton = {
                TextButton(onClick = onDelete) { Text("Eliminar", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { confirmDelete = false }) { Text("Cancelar") }
            }
        )
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            FoodCategoryBadge(food.category)
            Column(Modifier.weight(1f)) {
                Text(food.name, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text(
                    listOfNotNull(food.brand, food.subcategory ?: food.family).joinToString(" · ")
                        .ifBlank { food.category.label },
                    color = foodCategoryColor(food.category),
                    fontWeight = FontWeight.SemiBold
                )
            }
        }
        if (food.barcode != null || food.retailer != null || food.source != null) {
            food.barcode?.let { MetadataLine("Código EAN", it) }
            food.retailer?.let { MetadataLine("Comercio identificado", it) }
            food.source?.let { MetadataLine("Fuente", it) }
        }
        HorizontalDivider()
        Text("Valores por 100 g o 100 ml", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(
            food.calories?.let { "${formatDecimal(it)} kcal" } ?: "Energía no indicada",
            style = MaterialTheme.typography.headlineLarge,
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.Bold
        )
        NutritionLine("Grasas", food.fatGrams)
        NutritionLine("de las cuales saturadas", food.saturatedFatGrams)
        NutritionLine("Carbohidratos", food.carbohydrateGrams)
        NutritionLine("de los cuales azúcares", food.sugarGrams)
        NutritionLine("Proteínas", food.proteinGrams)
        NutritionLine("Fibra", food.fiberGrams)
        NutritionLine("Sal", food.saltGrams)
        food.legalName?.let {
            HorizontalDivider()
            Text("Denominación legal", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(it, style = MaterialTheme.typography.bodyMedium)
        }
        food.ingredients?.let {
            Text("Ingredientes", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(it, style = MaterialTheme.typography.bodyMedium)
        }
        if (food.links.isNotEmpty()) {
            HorizontalDivider()
            Text("Enlaces", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            food.links.forEach { link ->
                Row(
                    Modifier.fillMaxWidth().clickable { uriHandler.openUri(link) }.padding(vertical = 5.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Text(linkLabel(link), modifier = Modifier.weight(1f), color = MaterialTheme.colorScheme.primary)
                    Icon(
                        Icons.AutoMirrored.Filled.OpenInNew,
                        contentDescription = "Abrir enlace",
                        tint = MaterialTheme.colorScheme.primary
                    )
                }
            }
        }
        HorizontalDivider()
        Text("Alimentos similares", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(
            "Misma subcategoría culinaria y composición suficientemente próxima para intercambiar cantidades parecidas sin alterar mucho los macros.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        if (similarFoods.isEmpty()) {
            Text(
                "No hay sustitutos suficientemente próximos en el catálogo actual.",
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        } else {
            similarFoods.forEach { similar ->
                FoodListEntry(food = similar, onClick = { onOpenFood(similar.id) })
                HorizontalDivider()
            }
        }
        Spacer(Modifier.height(4.dp))
        Button(onClick = onEdit, modifier = Modifier.fillMaxWidth()) { Text("Editar alimento") }
        TextButton(onClick = { confirmDelete = true }, modifier = Modifier.fillMaxWidth()) {
            Text("Eliminar alimento", color = MaterialTheme.colorScheme.error)
        }
    }
}

private fun linkLabel(link: String): String = runCatching {
    java.net.URI(link).host?.removePrefix("www.")
}.getOrNull().orEmpty().ifBlank { link }

@Composable
private fun NutritionLine(label: String, grams: Double?) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(grams?.let { "${formatDecimal(it)} g" } ?: "No indicada", fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun MetadataLine(label: String, value: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, modifier = Modifier.padding(start = 16.dp), fontWeight = FontWeight.SemiBold)
    }
}

private fun formatNutrient(value: Double?): String =
    value?.let { "${formatDecimal(it)} g" } ?: "—"

@Composable
private fun FoodEditorScreen(foods: List<Food>, initial: Food? = null, onSave: (Food) -> Unit) {
    val isEditing = initial != null
    var name by rememberSaveable(initial?.id) { mutableStateOf(initial?.name.orEmpty()) }
    var category by remember(initial?.id) { mutableStateOf(initial?.category ?: FoodCategory.OTHER) }
    var calories by rememberSaveable(initial?.id) { mutableStateOf(initial?.calories?.let(::formatDecimal).orEmpty()) }
    var fat by rememberSaveable(initial?.id) { mutableStateOf(initial?.fatGrams?.let(::formatDecimal).orEmpty()) }
    var carbohydrates by rememberSaveable(initial?.id) {
        mutableStateOf(initial?.carbohydrateGrams?.let(::formatDecimal).orEmpty())
    }
    var protein by rememberSaveable(initial?.id) { mutableStateOf(initial?.proteinGrams?.let(::formatDecimal).orEmpty()) }
    var fiber by rememberSaveable(initial?.id) { mutableStateOf(initial?.fiberGrams?.let(::formatDecimal).orEmpty()) }
    var linksText by rememberSaveable(initial?.id) { mutableStateOf(initial?.links?.joinToString("\n").orEmpty()) }
    var error by rememberSaveable(initial?.id) { mutableStateOf<String?>(null) }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text(
            if (isEditing) "Editar alimento" else "Nuevo alimento",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold
        )
        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Nombre") },
            singleLine = true
        )
        SelectorField(
            label = "Categoría",
            selectedLabel = category.label,
            options = FoodCategory.entries,
            optionLabel = { it.label },
            onSelect = { category = it },
            onClear = null
        )
        Text(
            "Información nutricional por 100 g",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold
        )
        NumericField("Kilocalorías", calories, { calories = it }, Modifier.fillMaxWidth())
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            NumericField("Grasas (g)", fat, { fat = it }, Modifier.weight(1f))
            NumericField("Hidratos (g)", carbohydrates, { carbohydrates = it }, Modifier.weight(1f))
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            NumericField("Proteínas (g)", protein, { protein = it }, Modifier.weight(1f))
            NumericField("Fibra (g)", fiber, { fiber = it }, Modifier.weight(1f))
        }
        Text(
            "La fibra puede dejarse vacía si no figura en la etiqueta.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        OutlinedTextField(
            value = linksText,
            onValueChange = { linksText = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Enlaces (uno por línea)") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            minLines = 3,
            maxLines = 6
        )
        Text(
            "Puedes añadir hasta diez páginas del producto o fuentes de información nutricional.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        Button(
            onClick = {
                val values = listOf(calories, fat, carbohydrates, protein).map(::parseDecimal)
                val parsedFiber = fiber.takeIf { it.isNotBlank() }?.let(::parseDecimal)
                val parsedLinks = linksText.lines().map(String::trim).filter(String::isNotEmpty).distinct()
                error = when {
                    name.trim().isEmpty() -> "Introduce el nombre del alimento."
                    name.trim().length > 160 -> "El nombre no puede superar 160 caracteres."
                    foods.any { it.id != initial?.id && it.name.trim().equals(name.trim(), ignoreCase = true) } ->
                        "Ya existe un alimento con ese nombre."
                    values.any { it == null } -> "Completa todos los valores nutricionales con números válidos."
                    fiber.isNotBlank() && parsedFiber == null -> "La fibra no es un número válido."
                    values[0]!! !in 0.0..1000.0 -> "Las kilocalorías deben estar entre 0 y 1000."
                    values.drop(1).any { it!! !in 0.0..100.0 } ->
                        "Cada nutriente debe estar entre 0 y 100 g por cada 100 g."
                    parsedFiber != null && parsedFiber !in 0.0..100.0 ->
                        "La fibra debe estar entre 0 y 100 g por cada 100 g."
                    parsedLinks.size > 10 -> "Solo se pueden guardar diez enlaces por alimento."
                    parsedLinks.any { it.length > 500 || (!it.startsWith("https://") && !it.startsWith("http://")) } ->
                        "Cada enlace debe comenzar por https:// o http://."
                    else -> null
                }
                if (error == null) {
                    onSave(
                        Food(
                            id = initial?.id ?: System.currentTimeMillis(),
                            name = name.trim(),
                            category = category,
                            calories = values[0]!!,
                            fatGrams = values[1]!!,
                            carbohydrateGrams = values[2]!!,
                            proteinGrams = values[3]!!,
                            fiberGrams = parsedFiber,
                            links = parsedLinks
                        )
                    )
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) { Text(if (isEditing) "Guardar cambios" else "Añadir alimento") }
    }
}

private fun normalizeSearch(value: String): String = java.text.Normalizer
    .normalize(value.lowercase(Locale.getDefault()), java.text.Normalizer.Form.NFD)
    .replace("\\p{M}+".toRegex(), "")

@Composable
private fun ProfileScreen(
    profile: UserProfile?,
    profiles: List<UserProfile>,
    isOnboarding: Boolean,
    requiresBaseline: Boolean,
    onCreate: (UserProfile, Measurement) -> Unit,
    onSave: (UserProfile) -> Unit,
    onSwitch: (Long) -> Unit,
    onDelete: (Long) -> Unit,
    onExport: (() -> Unit)?,
    onImport: () -> Unit
) {
    var creating by rememberSaveable { mutableStateOf(isOnboarding) }
    val editedProfile = if (creating) null else profile
    var name by rememberSaveable(editedProfile?.id, creating) { mutableStateOf(editedProfile?.name ?: "") }
    var height by rememberSaveable(editedProfile?.id, creating) {
        mutableStateOf(editedProfile?.heightCm?.let(::formatDecimal) ?: "")
    }
    var birthYear by rememberSaveable(editedProfile?.id, creating) {
        mutableStateOf(editedProfile?.birthYear?.toString() ?: "")
    }
    var sex by remember(editedProfile?.id, creating) { mutableStateOf(editedProfile?.sex ?: Sex.MALE) }
    var initialWeight by rememberSaveable(editedProfile?.id, creating) { mutableStateOf("") }
    var initialWaist by rememberSaveable(editedProfile?.id, creating) { mutableStateOf("") }
    var initialGoal by remember(editedProfile?.id, creating) { mutableStateOf<WeightGoal?>(null) }
    var error by rememberSaveable { mutableStateOf<String?>(null) }
    var pendingDelete by remember { mutableStateOf<UserProfile?>(null) }
    val needsBaseline = creating || requiresBaseline

    pendingDelete?.let { selected ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            title = { Text("¿Eliminar el perfil de ${selected.name}?") },
            text = { Text("Se eliminarán también todas sus mediciones y recomendaciones. Esta acción no se puede deshacer.") },
            confirmButton = {
                TextButton(onClick = {
                    onDelete(selected.id)
                    pendingDelete = null
                }) { Text("Eliminar", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton(onClick = { pendingDelete = null }) { Text("Cancelar") } }
        )
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text(
            when {
                isOnboarding -> "Configura tu primer perfil"
                requiresBaseline -> "Completa tu perfil"
                else -> "Perfiles"
            },
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold
        )
        Text(
            when {
                needsBaseline -> "Introduce también el peso, la cintura y el objetivo iniciales. Rumbo necesita los tres para ofrecer una pantalla principal útil desde el primer momento."
                else -> "Si corriges estos datos, las recomendaciones se recalculan; tus mediciones originales no cambian."
            },
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        if (!isOnboarding && profiles.isNotEmpty()) {
            profiles.forEach { listed ->
                OutlinedButton(
                    onClick = { onSwitch(listed.id) },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(
                        if (listed.id == profile?.id) Icons.Default.Check else Icons.Default.Person,
                        contentDescription = null
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(listed.name, modifier = Modifier.weight(1f))
                    if (listed.id == profile?.id) Text("Activo")
                }
            }
            FilledTonalButton(
                onClick = { creating = true },
                modifier = Modifier.fillMaxWidth()
            ) {
                Icon(Icons.Default.PersonAdd, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Añadir otro perfil")
            }
            HorizontalDivider(Modifier.padding(vertical = 6.dp))
            Text(
                if (creating) "Nuevo perfil" else "Datos de ${profile?.name}",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
        }
        OutlinedTextField(
            value = name,
            onValueChange = { name = it.take(30) },
            label = { Text("Nombre del perfil") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        NumericField("Altura (cm)", height, { height = it }, Modifier.fillMaxWidth())
        OutlinedTextField(
            value = birthYear,
            onValueChange = { birthYear = it.filter(Char::isDigit).take(4) },
            label = { Text("Año de nacimiento") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        SelectorField(
            label = "Sexo usado por la fórmula",
            selectedLabel = sex.label,
            options = Sex.entries,
            optionLabel = { it.label },
            onSelect = { sex = it },
            onClear = null
        )
        if (needsBaseline) {
            HorizontalDivider(Modifier.padding(vertical = 4.dp))
            Text("Situación inicial", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                NumericField("Peso (kg)", initialWeight, { initialWeight = it }, Modifier.weight(1f))
                NumericField("Cintura (cm)", initialWaist, { initialWaist = it }, Modifier.weight(1f))
            }
            SelectorField(
                label = "Objetivo inicial",
                selectedLabel = initialGoal?.label ?: "Selecciona un objetivo",
                options = WeightGoal.entries,
                optionLabel = { it.label },
                onSelect = { initialGoal = it },
                onClear = null
            )
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        Button(
            onClick = {
                val candidate = UserProfile(
                    id = editedProfile?.id ?: System.currentTimeMillis(),
                    name = name.trim(),
                    heightCm = parseDecimal(height) ?: 0.0,
                    birthYear = birthYear.toIntOrNull() ?: 0,
                    sex = sex
                )
                val parsedWeight = parseDecimal(initialWeight)
                val parsedWaist = parseDecimal(initialWaist)
                error = when {
                    !candidate.isValid() -> "Revisa el nombre, la altura y el año de nacimiento. La app está diseñada para personas adultas."
                    needsBaseline && (parsedWeight == null || parsedWeight !in 30.0..350.0) -> "Introduce un peso válido entre 30 y 350 kg."
                    needsBaseline && (parsedWaist == null || parsedWaist !in 35.0..250.0) -> "Introduce una cintura válida entre 35 y 250 cm."
                    needsBaseline && initialGoal == null -> "Selecciona un objetivo inicial."
                    else -> null
                }
                if (error == null) {
                    if (needsBaseline) {
                        onCreate(
                            candidate,
                            Measurement(
                                id = System.currentTimeMillis(),
                                date = LocalDate.now(),
                                weightKg = parsedWeight,
                                waistCm = parsedWaist,
                                goal = initialGoal
                            )
                        )
                    } else {
                        onSave(candidate)
                    }
                    creating = false
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(
                when {
                    creating -> "Crear perfil"
                    requiresBaseline -> "Completar perfil"
                    else -> "Guardar cambios"
                }
            )
        }

        if (!isOnboarding && !creating && profiles.size > 1 && profile != null) {
            TextButton(onClick = { pendingDelete = profile }, modifier = Modifier.fillMaxWidth()) {
                Text("Eliminar este perfil", color = MaterialTheme.colorScheme.error)
            }
        }

        if (!isOnboarding && creating) {
            TextButton(onClick = { creating = false }, modifier = Modifier.fillMaxWidth()) {
                Text("Cancelar")
            }
        }

        HorizontalDivider(Modifier.padding(vertical = 8.dp))
        Text("Copia de seguridad", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Text(
            "Todo se guarda localmente. La copia incluye todos los perfiles y sus historiales.",
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        if (onExport != null) {
            OutlinedButton(onClick = onExport, modifier = Modifier.fillMaxWidth()) { Text("Exportar copia de seguridad") }
        }
        OutlinedButton(onClick = onImport, modifier = Modifier.fillMaxWidth()) { Text("Importar copia de seguridad") }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun NumericField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier
) {
    OutlinedTextField(
        value = value,
        onValueChange = { raw ->
            onValueChange(raw.filter { it.isDigit() || it == ',' || it == '.' }.take(7))
        },
        label = { Text(label) },
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
        singleLine = true,
        modifier = modifier
    )
}

@Composable
private fun <T> SelectorField(
    label: String,
    selectedLabel: String,
    options: List<T>,
    optionLabel: (T) -> String,
    onSelect: (T) -> Unit,
    onClear: (() -> Unit)?
) {
    var expanded by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(label, style = MaterialTheme.typography.labelLarge)
        Box(Modifier.fillMaxWidth()) {
            OutlinedButton(onClick = { expanded = true }, modifier = Modifier.fillMaxWidth()) {
                Text(selectedLabel, modifier = Modifier.weight(1f))
            }
            DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                if (onClear != null) {
                    DropdownMenuItem(
                        text = { Text("Usar valor anterior / sin indicar") },
                        onClick = {
                            onClear()
                            expanded = false
                        }
                    )
                    HorizontalDivider()
                }
                options.forEach { option ->
                    DropdownMenuItem(
                        text = { Text(optionLabel(option)) },
                        onClick = {
                            onSelect(option)
                            expanded = false
                        }
                    )
                }
            }
        }
    }
}

private fun parseDecimal(value: String): Double? = value.trim().replace(',', '.').toDoubleOrNull()

private fun formatDecimal(value: Double): String =
    if (value % 1.0 == 0.0) value.toInt().toString() else String.format(java.util.Locale.US, "%.1f", value)

private val spanishLocale: Locale = Locale.forLanguageTag("es-ES")

private fun formatOneDecimal(value: Double): String = String.format(spanishLocale, "%.1f", value)

private fun formatTwoDecimals(value: Double): String = String.format(spanishLocale, "%.2f", value)

private fun formatSignedKcal(value: Double): String = when {
    value > 0.05 -> "+${formatOneDecimal(value)}"
    value < -0.05 -> "−${formatOneDecimal(abs(value))}"
    else -> "0,0"
}
