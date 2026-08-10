@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package es.david.rumbo.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.BackHandler
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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.ui.draw.shadow
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AddCircle
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Circle
import androidx.compose.material.icons.filled.Cake
import androidx.compose.material.icons.filled.AcUnit
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Eco
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.Grain
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.LocalFlorist
import androidx.compose.material.icons.filled.LocalFireDepartment
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Opacity
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material.icons.filled.Restaurant
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.listSaver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import es.david.rumbo.data.AppRepository
import es.david.rumbo.logic.FoodSimilarityEngine
import es.david.rumbo.logic.MealPlanEvaluator
import es.david.rumbo.logic.MealQuantityOptimizer
import es.david.rumbo.logic.PlanNutritionAssessment
import es.david.rumbo.logic.QuantityOptimizationResult
import es.david.rumbo.logic.RecommendationEngine
import es.david.rumbo.logic.TargetFit
import es.david.rumbo.logic.WeeklyMenuGenerator
import es.david.rumbo.logic.PlanningConflictException
import es.david.rumbo.model.ActivityLevel
import es.david.rumbo.model.AppData
import es.david.rumbo.model.BodyAssessment
import es.david.rumbo.model.DietCompliance
import es.david.rumbo.model.Dish
import es.david.rumbo.model.DishIngredient
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.Measurement
import es.david.rumbo.model.MenuHistoryEntry
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedDish
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanWeek
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.PlanningSlot
import es.david.rumbo.model.RecommendedGoal
import es.david.rumbo.model.Sex
import es.david.rumbo.model.UserProfile
import es.david.rumbo.model.WeightGoal
import es.david.rumbo.model.WeekDay
import es.david.rumbo.model.dominantCategory
import es.david.rumbo.model.nutrition
import es.david.rumbo.model.nutritionForGrams
import es.david.rumbo.model.resolvedGrams
import es.david.rumbo.model.sanitizedDayAmounts
import es.david.rumbo.model.totalWeightGrams
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.abs
import kotlin.math.pow
import kotlin.math.roundToInt

private enum class Screen(val label: String, val icon: ImageVector, val inNavigation: Boolean = true) {
    HOME("Inicio", Icons.Default.Home),
    ADD("Añadir", Icons.Default.AddCircle, false),
    MEASUREMENT_DETAIL("Medición", Icons.Default.Home, false),
    EDIT_MEASUREMENT("Editar medición", Icons.Default.Home, false),
    PLANNER("Plan", Icons.Default.CalendarMonth, false),
    AUTO_PLANNING("Generación automática", Icons.Default.CalendarMonth, false),
    ADD_PLANNED_MEAL("Añadir comida", Icons.Default.CalendarMonth, false),
    EDIT_PLANNED_MEAL("Editar comida", Icons.Default.CalendarMonth, false),
    DISHES("Platos", Icons.Default.Restaurant, false),
    ADD_DISH("Añadir plato", Icons.Default.Restaurant, false),
    DISH_DETAIL("Plato", Icons.Default.Restaurant, false),
    EDIT_DISH("Editar plato", Icons.Default.Restaurant, false),
    FOODS("Alimentos y platos", Icons.Default.Search, false),
    ADD_FOOD("Añadir alimento", Icons.Default.Restaurant, false),
    FOOD_DETAIL("Alimento", Icons.Default.Restaurant, false),
    EDIT_FOOD("Editar alimento", Icons.Default.Restaurant, false),
    PROFILE("Perfiles", Icons.Default.Person, false),
    SETTINGS("Opciones", Icons.Default.Person, false),
    GOAL_EXPLANATION("Objetivos", Icons.Default.Home, false),
    BODY_EXPLANATION("Situación corporal", Icons.Default.Home, false),
    RECOMMENDATION_EXPLANATION("Recomendación", Icons.Default.Home, false)
}

private enum class PlannerView(val label: String) {
    WEEK("Semana"),
    TODAY("Hoy"),
    DAY("Día")
}

@Composable
fun RumboApp(repository: AppRepository) {
    var data by remember { mutableStateOf(repository.load()) }
    var screenName by rememberSaveable {
        mutableStateOf(if (data.isActiveProfileReady) Screen.HOME.name else Screen.PROFILE.name)
    }
    var selectedMeasurementId by rememberSaveable { mutableStateOf<Long?>(null) }
    var selectedFoodId by rememberSaveable { mutableStateOf<Long?>(null) }
    var selectedPlannedMealId by rememberSaveable { mutableStateOf<Long?>(null) }
    var selectedDishId by rememberSaveable { mutableStateOf<Long?>(null) }
    var draftMealTypeName by rememberSaveable { mutableStateOf<String?>(null) }
    var plannerWeekName by rememberSaveable { mutableStateOf(PlanWeek.CURRENT.name) }
    var draftMealDayName by rememberSaveable { mutableStateOf<String?>(null) }
    var draftFoodId by rememberSaveable { mutableStateOf<Long?>(null) }
    var draftDishId by rememberSaveable { mutableStateOf<Long?>(null) }
    var foodReturnScreenName by rememberSaveable { mutableStateOf<String?>(null) }
    var dishReturnScreenName by rememberSaveable { mutableStateOf<String?>(null) }
    val screen = Screen.valueOf(screenName)
    val profileReady = data.isActiveProfileReady
    val currentRecommendation = data.measurements
        .maxWithOrNull(compareBy<Measurement> { it.date }.thenBy { it.id })
        ?.recommendation
    val allPlannedMeals = data.profiles.flatMap { it.plannedMeals }
    val preferredFoodIds = remember(data.dishes, allPlannedMeals) {
        buildSet {
            data.dishes.flatMapTo(this) { dish -> dish.ingredients.map { it.foodId } }
            allPlannedMeals.flatMapTo(this) { meal -> meal.items.map { it.foodId } }
        }
    }
    val preferredDishIds = remember(allPlannedMeals) {
        allPlannedMeals.flatMap { meal -> meal.dishes.map { it.dishId } }.toSet()
    }
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var mealShares by remember { mutableStateOf(loadMealShares(context)) }
    var adjustmentRange by remember { mutableStateOf(loadAdjustmentRange(context)) }
    var detailMenuExpanded by remember { mutableStateOf(false) }
    var pendingTopDelete by remember { mutableStateOf<Screen?>(null) }
    val screenStateHolder = rememberSaveableStateHolder()
    val navigateBack = {
        screenName = when {
            screen == Screen.EDIT_MEASUREMENT && selectedMeasurementId != null ->
                Screen.MEASUREMENT_DETAIL.name
            screen == Screen.EDIT_FOOD && selectedFoodId != null ->
                Screen.FOOD_DETAIL.name
            screen in setOf(Screen.ADD_PLANNED_MEAL, Screen.EDIT_PLANNED_MEAL) ->
                Screen.PLANNER.name
            screen == Screen.EDIT_DISH && selectedDishId != null -> Screen.DISH_DETAIL.name
            screen == Screen.DISH_DETAIL && dishReturnScreenName != null -> {
                val destination = dishReturnScreenName!!
                dishReturnScreenName = null
                destination
            }
            screen in setOf(Screen.ADD_DISH, Screen.DISH_DETAIL) -> Screen.FOODS.name
            screen == Screen.FOOD_DETAIL && foodReturnScreenName != null -> {
                val destination = foodReturnScreenName!!
                foodReturnScreenName = null
                destination
            }
            screen in setOf(Screen.ADD_FOOD, Screen.FOOD_DETAIL) -> Screen.FOODS.name
            else -> Screen.HOME.name
        }
    }

    BackHandler(enabled = profileReady && screen != Screen.HOME) { navigateBack() }

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

    if (pendingTopDelete != null) {
        val deletingFood = pendingTopDelete == Screen.FOOD_DETAIL
        val itemName = if (deletingFood) {
            data.foods.firstOrNull { it.id == selectedFoodId }?.name
        } else {
            data.dishes.firstOrNull { it.id == selectedDishId }?.name
        }.orEmpty()
        AlertDialog(
            onDismissRequest = { pendingTopDelete = null },
            title = { Text("¿Eliminar ${itemName}?") },
            text = {
                Text(
                    if (deletingFood) "Se eliminará del catálogo y de las comidas que lo utilicen."
                    else "Se eliminará el plato y se quitará de las comidas planificadas."
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        if (deletingFood) {
                            selectedFoodId?.let { data = repository.deleteFood(it) }
                            selectedFoodId = null
                        } else {
                            selectedDishId?.let { data = repository.deleteDish(it) }
                            selectedDishId = null
                        }
                        pendingTopDelete = null
                        screenName = Screen.FOODS.name
                    }
                ) { Text("Eliminar", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { pendingTopDelete = null }) { Text("Cancelar") }
            }
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                modifier = Modifier.shadow(2.dp),
                navigationIcon = {
                    if (profileReady && screen == Screen.HOME && data.profile != null) {
                        ProfileSwitcher(
                            profiles = data.profiles.map { it.profile },
                            activeProfile = data.profile,
                            onSelect = {
                                data = repository.switchProfile(it)
                                screenName = if (data.isActiveProfileReady) Screen.HOME.name else Screen.PROFILE.name
                            },
                            onManage = { screenName = Screen.PROFILE.name },
                            onSettings = { screenName = Screen.SETTINGS.name }
                        )
                    } else if (!screen.inNavigation) {
                        IconButton(onClick = navigateBack) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                        }
                    }
                },
                title = {
                    when (screen) {
                        Screen.EDIT_PLANNED_MEAL ->
                            Text("Editar comida", fontWeight = FontWeight.SemiBold)
                        Screen.ADD_PLANNED_MEAL ->
                            Text("Nueva comida", fontWeight = FontWeight.SemiBold)
                        Screen.ADD ->
                            Text("Nueva medición", fontWeight = FontWeight.SemiBold)
                        Screen.EDIT_MEASUREMENT ->
                            Text("Editar medición", fontWeight = FontWeight.SemiBold)
                        Screen.PROFILE ->
                            Text(if (data.profile == null) "Nuevo perfil" else "Perfiles", fontWeight = FontWeight.SemiBold)
                        Screen.BODY_EXPLANATION, Screen.RECOMMENDATION_EXPLANATION ->
                            Text("Situación y objetivo", fontWeight = FontWeight.SemiBold)
                        Screen.PLANNER ->
                            Text("Menú semanal", fontWeight = FontWeight.SemiBold)
                        Screen.AUTO_PLANNING ->
                            Text("Generación automática", fontWeight = FontWeight.SemiBold)
                        Screen.FOODS ->
                            Text("Alimentos y platos", fontWeight = FontWeight.SemiBold)
                        Screen.FOOD_DETAIL ->
                            Text("Alimento", fontWeight = FontWeight.SemiBold)
                        Screen.DISH_DETAIL ->
                            Text("Plato", fontWeight = FontWeight.SemiBold)
                        Screen.ADD_FOOD, Screen.EDIT_FOOD ->
                            Text(if (screen == Screen.ADD_FOOD) "Nuevo alimento" else "Editar alimento", fontWeight = FontWeight.SemiBold)
                        Screen.ADD_DISH, Screen.EDIT_DISH ->
                            Text(if (screen == Screen.ADD_DISH) "Nuevo plato" else "Editar plato", fontWeight = FontWeight.SemiBold)
                        else -> Column {
                            Text("Rumbo", fontWeight = FontWeight.SemiBold)
                            Text(
                                "Calorías con contexto, no con prisas",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                },
                actions = {
                    if (screen in setOf(Screen.FOOD_DETAIL, Screen.DISH_DETAIL)) {
                        Box {
                            IconButton(onClick = { detailMenuExpanded = true }) {
                                Icon(Icons.Default.MoreVert, contentDescription = "Opciones")
                            }
                            DropdownMenu(
                                expanded = detailMenuExpanded,
                                onDismissRequest = { detailMenuExpanded = false }
                            ) {
                                if (screen == Screen.FOOD_DETAIL) {
                                    DropdownMenuItem(
                                        text = { Text("Editar") },
                                        onClick = {
                                            detailMenuExpanded = false
                                            screenName = Screen.EDIT_FOOD.name
                                        }
                                    )
                                }
                                val foodBelongsToDish = screen == Screen.FOOD_DETAIL &&
                                    data.dishes.any { dish ->
                                        dish.ingredients.any { it.foodId == selectedFoodId }
                                    }
                                DropdownMenuItem(
                                    text = {
                                        Text(
                                            if (foodBelongsToDish) "Eliminar primero los platos que lo usan"
                                            else "Eliminar"
                                        )
                                    },
                                    enabled = !foodBelongsToDish,
                                    onClick = {
                                        detailMenuExpanded = false
                                        pendingTopDelete = screen
                                    }
                                )
                            }
                        }
                    }
                    if (profileReady && screen == Screen.HOME) {
                        IconButton(onClick = { screenName = Screen.FOODS.name }) {
                            Icon(Icons.Default.Search, contentDescription = "Buscar alimentos y platos")
                        }
                    }
                }
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            screenStateHolder.SaveableStateProvider(screenName) {
            when {
                !profileReady -> ProfileScreen(
                    profile = data.profile,
                    profiles = data.profiles.map { it.profile },
                    isOnboarding = data.profile == null,
                    requiresBaseline = true,
                    mealShares = mealShares,
                    onCreate = { profile, baseline, shares ->
                        data = repository.saveProfileWithBaseline(profile, baseline)
                        saveMealShares(context, shares)
                        mealShares = shares
                        screenName = Screen.HOME.name
                    },
                    onSave = { data = repository.saveProfile(it) },
                    onSwitch = {
                        data = repository.switchProfile(it)
                        screenName = if (data.isActiveProfileReady) Screen.HOME.name else Screen.PROFILE.name
                    },
                    onDelete = { data = repository.deleteProfile(it) }
                )
                screen == Screen.HOME -> HomeScreen(
                    data = data,
                    onGoalChange = { data = repository.setWeeklyRate(it) },
                    onAddMeasurement = { screenName = Screen.ADD.name },
                    onExplainBody = { screenName = Screen.BODY_EXPLANATION.name },
                    onOpenPlanner = {
                        plannerWeekName = PlanWeek.CURRENT.name
                        screenName = Screen.PLANNER.name
                    },
                    onOpenMeal = {
                        plannerWeekName = PlanWeek.CURRENT.name
                        selectedPlannedMealId = it
                        screenName = Screen.EDIT_PLANNED_MEAL.name
                    },
                    onOpenFoods = { screenName = Screen.FOODS.name },
                    onAddMissingMeal = { type, day ->
                        plannerWeekName = PlanWeek.CURRENT.name
                        screenStateHolder.removeState(Screen.ADD_PLANNED_MEAL.name)
                        draftMealTypeName = type.name
                        draftMealDayName = day.name
                        draftFoodId = null
                        draftDishId = null
                        screenName = Screen.ADD_PLANNED_MEAL.name
                    },
                    onApplyAdjustedMeals = { meals ->
                        data = repository.savePlannedMeals(meals, PlanWeek.CURRENT)
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
                screen == Screen.PLANNER -> WeeklyPlannerScreen(
                    meals = data.activeProfileData?.plannedMeals.orEmpty(),
                    planningRules = data.activeProfileData?.planningRules.orEmpty(),
                    menuHistory = data.activeProfileData?.menuHistory.orEmpty(),
                    foods = data.foods,
                    dishes = data.dishes,
                    recommendation = currentRecommendation,
                    mealShares = mealShares,
                    initialWeek = PlanWeek.valueOf(plannerWeekName),
                    onWeekChange = { plannerWeekName = it.name },
                    onApplyGeneratedMenu = { result, week ->
                        data = repository.applyGeneratedMenu(result, week)
                    },
                    onOpenMeal = { mealId, week ->
                        plannerWeekName = week.name
                        selectedPlannedMealId = mealId
                        screenName = Screen.EDIT_PLANNED_MEAL.name
                    },
                    onAddMissing = { type, day, week ->
                        plannerWeekName = week.name
                        screenStateHolder.removeState(Screen.ADD_PLANNED_MEAL.name)
                        draftMealTypeName = type.name
                        draftMealDayName = day.name
                        draftFoodId = null
                        draftDishId = null
                        screenName = Screen.ADD_PLANNED_MEAL.name
                    },
                    onApplyAdjustedMeals = { meals, week ->
                        data = repository.savePlannedMeals(meals, week)
                    }
                )
                screen == Screen.AUTO_PLANNING -> AutomaticPlanningScreen(
                    rules = data.activeProfileData?.planningRules.orEmpty(),
                    foods = data.foods,
                    dishes = data.dishes,
                    onSaveRule = { data = repository.savePlanningRule(it) },
                    onDeleteRule = { kind, id -> data = repository.deletePlanningRule(kind, id) }
                )
                screen == Screen.ADD_PLANNED_MEAL -> PlannedMealEditorScreen(
                    foods = data.foods,
                    dishes = data.dishes,
                    existingMeals = data.activeProfileData?.plannedMeals.orEmpty(),
                    recommendation = currentRecommendation,
                    mealShares = mealShares,
                    adjustmentRange = adjustmentRange,
                    initialType = draftMealTypeName?.let { MealType.valueOf(it) },
                    initialPlanWeek = PlanWeek.valueOf(plannerWeekName),
                    initialDays = draftMealDayName?.let { setOf(WeekDay.valueOf(it)) }.orEmpty(),
                    initialFoodId = draftFoodId,
                    initialDishId = draftDishId,
                    preferredFoodIds = preferredFoodIds,
                    preferredDishIds = preferredDishIds,
                    onCreateDish = { data = repository.saveDish(it) },
                    onOpenFood = {
                        selectedFoodId = it
                        foodReturnScreenName = Screen.ADD_PLANNED_MEAL.name
                        screenName = Screen.FOOD_DETAIL.name
                    },
                    onOpenDish = {
                        selectedDishId = it
                        dishReturnScreenName = Screen.ADD_PLANNED_MEAL.name
                        screenName = Screen.DISH_DETAIL.name
                    },
                    onSave = {
                        data = repository.savePlannedMeal(it)
                        draftMealTypeName = null
                        draftMealDayName = null
                        draftFoodId = null
                        draftDishId = null
                        screenName = Screen.PLANNER.name
                    }
                )
                screen == Screen.EDIT_PLANNED_MEAL -> {
                    val meal = data.activeProfileData?.plannedMeals
                        ?.firstOrNull { it.id == selectedPlannedMealId }
                    if (meal == null) {
                        screenName = Screen.PLANNER.name
                    } else {
                        PlannedMealEditorScreen(
                            foods = data.foods,
                            dishes = data.dishes,
                            existingMeals = data.activeProfileData?.plannedMeals.orEmpty(),
                            recommendation = currentRecommendation,
                            mealShares = mealShares,
                            adjustmentRange = adjustmentRange,
                            initial = meal,
                            preferredFoodIds = preferredFoodIds,
                            preferredDishIds = preferredDishIds,
                            onCreateDish = { data = repository.saveDish(it) },
                            onOpenFood = {
                                selectedFoodId = it
                                foodReturnScreenName = Screen.EDIT_PLANNED_MEAL.name
                                screenName = Screen.FOOD_DETAIL.name
                            },
                            onOpenDish = {
                                selectedDishId = it
                                dishReturnScreenName = Screen.EDIT_PLANNED_MEAL.name
                                screenName = Screen.DISH_DETAIL.name
                            },
                            onSave = {
                                data = repository.savePlannedMeal(it)
                                screenName = Screen.PLANNER.name
                            },
                            onDelete = {
                                data = repository.deletePlannedMeal(meal.id)
                                selectedPlannedMealId = null
                                screenName = Screen.PLANNER.name
                            }
                        )
                    }
                }
                screen == Screen.DISHES -> {
                    screenName = Screen.FOODS.name
                }
                screen == Screen.ADD_DISH -> DishEditorScreen(
                    foods = data.foods,
                    preferredFoodIds = preferredFoodIds,
                    onSave = {
                        data = repository.saveDish(it)
                        selectedDishId = it.id
                        screenName = Screen.DISH_DETAIL.name
                    }
                )
                screen == Screen.DISH_DETAIL -> {
                    val dish = data.dishes.firstOrNull { it.id == selectedDishId }
                    if (dish == null) {
                        screenName = Screen.FOODS.name
                    } else {
                        DishDetailScreen(
                            dish = dish,
                            foods = data.foods,
                            plannedMeals = data.activeProfileData?.plannedMeals.orEmpty(),
                            onOpenFood = {
                                selectedFoodId = it
                                foodReturnScreenName = Screen.DISH_DETAIL.name
                                screenName = Screen.FOOD_DETAIL.name
                            },
                            onOpenMeal = {
                                selectedPlannedMealId = it
                                screenName = Screen.EDIT_PLANNED_MEAL.name
                            },
                            onAddToMeal = { mealId ->
                                val meal = data.activeProfileData?.plannedMeals?.firstOrNull { it.id == mealId }
                                if (meal != null) {
                                    val existing = meal.dishes.firstOrNull { it.dishId == dish.id }
                                    val amount = dish.totalWeightGrams().takeIf { it > 0.0 } ?: 100.0
                                    val updated = if (existing == null) {
                                        meal.copy(dishes = meal.dishes + PlannedDish(dish.id, amount, false, amount * 0.5, amount * 1.5))
                                    } else {
                                        meal.copy(dishes = meal.dishes.map {
                                            if (it.dishId == dish.id) it.copy(
                                                grams = it.grams + amount,
                                                minimumGrams = (it.grams + amount) * 0.5,
                                                maximumGrams = (it.grams + amount) * 1.5
                                            ) else it
                                        })
                                    }
                                    data = repository.savePlannedMeal(updated)
                                }
                            },
                            onAddNewMeal = {
                                screenStateHolder.removeState(Screen.ADD_PLANNED_MEAL.name)
                                draftFoodId = null
                                draftDishId = dish.id
                                draftMealTypeName = null
                                draftMealDayName = null
                                screenName = Screen.ADD_PLANNED_MEAL.name
                            },
                            planningRule = data.activeProfileData?.planningRules?.firstOrNull {
                                it.itemKind == PlannedItemKind.DISH && it.itemId == dish.id
                            },
                            onSavePlanningRule = { data = repository.savePlanningRule(it) },
                            onDeletePlanningRule = {
                                data = repository.deletePlanningRule(PlannedItemKind.DISH, dish.id)
                            },
                            onEdit = { screenName = Screen.EDIT_DISH.name },
                            onDelete = {
                                data = repository.deleteDish(dish.id)
                                selectedDishId = null
                                screenName = Screen.FOODS.name
                            }
                        )
                    }
                }
                screen == Screen.EDIT_DISH -> {
                    val dish = data.dishes.firstOrNull { it.id == selectedDishId }
                    if (dish == null) {
                        screenName = Screen.FOODS.name
                    } else {
                        DishEditorScreen(
                            foods = data.foods,
                            initial = dish,
                            preferredFoodIds = preferredFoodIds,
                            onSave = {
                                data = repository.saveDish(it)
                                screenName = Screen.DISH_DETAIL.name
                            },
                            onDelete = {
                                data = repository.deleteDish(dish.id)
                                selectedDishId = null
                                screenName = Screen.FOODS.name
                            }
                        )
                    }
                }
                screen == Screen.FOODS -> FoodDishCatalogScreen(
                    foods = data.foods,
                    dishes = data.dishes,
                    onOpenFood = {
                        selectedFoodId = it
                        foodReturnScreenName = null
                        screenName = Screen.FOOD_DETAIL.name
                    },
                    onOpenDish = {
                        selectedDishId = it
                        dishReturnScreenName = null
                        screenName = Screen.DISH_DETAIL.name
                    },
                    onAddFood = { screenName = Screen.ADD_FOOD.name },
                    onAddDish = { screenName = Screen.ADD_DISH.name }
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
                            plannedMeals = data.activeProfileData?.plannedMeals.orEmpty(),
                            dishes = data.dishes,
                            onOpenFood = { selectedFoodId = it },
                            onOpenMeal = {
                                selectedPlannedMealId = it
                                screenName = Screen.EDIT_PLANNED_MEAL.name
                            },
                            onAddToMeal = { mealId ->
                                val meal = data.activeProfileData?.plannedMeals?.firstOrNull { it.id == mealId }
                                if (meal != null) {
                                    val existing = meal.items.firstOrNull { it.foodId == food.id }
                                    val amount = 100.0
                                    val updated = if (existing == null) {
                                        meal.copy(items = meal.items + PlannedFood(food.id, amount, false, amount * 0.5, amount * 1.5))
                                    } else {
                                        meal.copy(items = meal.items.map {
                                            if (it.foodId == food.id) it.copy(
                                                grams = it.grams + amount,
                                                minimumGrams = (it.grams + amount) * 0.5,
                                                maximumGrams = (it.grams + amount) * 1.5
                                            ) else it
                                        })
                                    }
                                    data = repository.savePlannedMeal(updated)
                                }
                            },
                            onAddNewMeal = {
                                screenStateHolder.removeState(Screen.ADD_PLANNED_MEAL.name)
                                draftFoodId = food.id
                                draftDishId = null
                                draftMealTypeName = null
                                draftMealDayName = null
                                screenName = Screen.ADD_PLANNED_MEAL.name
                            },
                            planningRule = data.activeProfileData?.planningRules?.firstOrNull {
                                it.itemKind == PlannedItemKind.FOOD && it.itemId == food.id
                            },
                            onSavePlanningRule = { data = repository.savePlanningRule(it) },
                            onDeletePlanningRule = {
                                data = repository.deletePlanningRule(PlannedItemKind.FOOD, food.id)
                            },
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
                    mealShares = mealShares,
                    onCreate = { profile, baseline, shares ->
                        data = repository.saveProfileWithBaseline(profile, baseline)
                        saveMealShares(context, shares)
                        mealShares = shares
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
                    onDelete = { data = repository.deleteProfile(it) }
                )
                screen == Screen.SETTINGS -> SettingsScreen(
                    mealShares = mealShares,
                    adjustmentRange = adjustmentRange,
                    onSaveMealShares = {
                        saveMealShares(context, it)
                        mealShares = it
                    },
                    onSaveAdjustmentRange = {
                        saveAdjustmentRange(context, it)
                        adjustmentRange = it
                    },
                    onExport = { exportLauncher.launch("rumbo-copia-${LocalDate.now()}.json") },
                    onImport = { importLauncher.launch(arrayOf("application/json", "text/plain")) }
                )
                screen == Screen.GOAL_EXPLANATION -> GoalExplanationScreen(data)
                screen in setOf(Screen.BODY_EXPLANATION, Screen.RECOMMENDATION_EXPLANATION) ->
                    BodyExplanationScreen(
                        data = data,
                        onOpenMeasurement = {
                            selectedMeasurementId = it
                            screenName = Screen.MEASUREMENT_DETAIL.name
                        }
                    )
            }
            }
        }
    }
}

@Composable
private fun ProfileSwitcher(
    profiles: List<UserProfile>,
    activeProfile: UserProfile?,
    onSelect: (Long) -> Unit,
    onManage: () -> Unit,
    onSettings: () -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        IconButton(onClick = { expanded = true }) {
            Box(
                Modifier.size(36.dp).background(profileColor(activeProfile?.id), CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    activeProfile?.name?.trim()?.firstOrNull()?.uppercase() ?: "?",
                    color = Color.White,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            }
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
            DropdownMenuItem(
                text = { Text("Opciones") },
                onClick = {
                    expanded = false
                    onSettings()
                }
            )
        }
    }
}

private fun profileColor(id: Long?): Color {
    val colors = listOf(
        Color(0xFF455A64), Color(0xFF5D4037), Color(0xFF6A1B9A),
        Color(0xFF1565C0), Color(0xFF00695C), Color(0xFFAD1457)
    )
    val index = (((id ?: 0L) % colors.size) + colors.size) % colors.size
    return colors[index.toInt()]
}

@Composable
private fun HomeScreen(
    data: AppData,
    onGoalChange: (Double?) -> Unit,
    onAddMeasurement: () -> Unit,
    onExplainBody: () -> Unit,
    onOpenPlanner: () -> Unit,
    onOpenMeal: (Long) -> Unit,
    onOpenFoods: () -> Unit,
    onAddMissingMeal: (MealType, WeekDay) -> Unit,
    onApplyAdjustedMeals: (List<PlannedMeal>) -> Unit
) {
    val profile = data.profile
    val latest = data.measurements.maxWithOrNull(compareBy<Measurement> { it.date }.thenBy { it.id })
    val recommendation = latest?.recommendation
    val assessment = profile?.let { RecommendationEngine.assessBody(it, data.measurements) }
    val recommendedGoal = profile?.let { RecommendationEngine.recommendGoal(it, data.measurements) }
    val effectiveGoal = RecommendationEngine.effectiveValues(data.measurements)
    val goal = effectiveGoal.goal
    val foodsById = remember(data.foods) { data.foods.associateBy { it.id } }
    val dishesById = remember(data.dishes) { data.dishes.associateBy { it.id } }
    val meals = data.activeProfileData?.plannedMeals.orEmpty()
        .filter { it.planWeek == PlanWeek.CURRENT }

    LazyColumn(
        contentPadding = PaddingValues(start = 16.dp, top = 12.dp, end = 16.dp, bottom = 96.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        if (assessment != null && recommendedGoal != null) {
            item {
                BodyGoalNutritionCard(
                    assessment = assessment,
                    recommendedGoal = recommendedGoal,
                    weightKg = RecommendationEngine.effectiveValues(data.measurements).weightKg,
                    goal = goal,
                    chosenWeeklyRate = effectiveGoal.weeklyRateKg,
                    recommendation = recommendation,
                    onGoalChange = onGoalChange,
                    onExplain = onExplainBody,
                    onAddMeasurement = onAddMeasurement
                )
            }
        }
        val missingWeight = effectiveGoal.weightKg == null
        val missingWaist = effectiveGoal.waistCm == null
        if (missingWeight || missingWaist) {
            item {
                MissingMeasurementCard(
                    missingWeight = missingWeight,
                    missingWaist = missingWaist,
                    onAddMeasurement = onAddMeasurement
                )
            }
        }
        item {
            TodayPlanSection(
                meals = meals,
                foodsById = foodsById,
                dishesById = dishesById,
                recommendation = recommendation,
                onOpenPlanner = onOpenPlanner,
                onOpenMeal = onOpenMeal,
                onAddMissing = onAddMissingMeal,
                onApplyAdjustedMeals = onApplyAdjustedMeals
            )
        }
        item {
            HomeShoppingSection(
                meals = meals,
                foodsById = foodsById,
                dishesById = dishesById,
                profileId = profile?.id,
                onOpenFoods = onOpenFoods
            )
        }
    }
}

@Composable
private fun MissingMeasurementCard(
    missingWeight: Boolean,
    missingWaist: Boolean,
    onAddMeasurement: () -> Unit
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(
                if (missingWeight) "Añade tu peso" else "Añade tu cintura",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            HorizontalDivider()
            Text(
                when {
                    missingWeight && missingWaist ->
                        "Añade una primera medición para que Rumbo pueda valorar tu situación."
                    missingWeight ->
                        "La cintura ya permite orientar el objetivo, pero con el peso también podremos calcular el IMC y las calorías que necesitas."
                    else ->
                        "El peso ya permite calcular las calorías, pero la cintura hará más precisa la valoración de la distribución abdominal."
                },
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            OutlinedButton(onClick = onAddMeasurement, modifier = Modifier.fillMaxWidth()) {
                Text(if (missingWeight) "Añadir peso" else "Añadir cintura")
            }
        }
    }
}

@Composable
private fun BodyGoalNutritionCard(
    assessment: BodyAssessment,
    recommendedGoal: RecommendedGoal,
    weightKg: Double?,
    goal: WeightGoal,
    chosenWeeklyRate: Double?,
    recommendation: es.david.rumbo.model.Recommendation?,
    onGoalChange: (Double?) -> Unit,
    onExplain: () -> Unit,
    onAddMeasurement: () -> Unit
) {
    var choosingGoal by remember { mutableStateOf(false) }
    var manualMagnitude by rememberSaveable { mutableStateOf("") }
    var manualDirection by remember { mutableStateOf(-1.0) }
    var manualError by rememberSaveable { mutableStateOf<String?>(null) }
    val recommendedRate = RecommendationEngine.weeklyRateFor(recommendedGoal.goal, weightKg) ?: 0.0
    val selectedRate = if (goal == WeightGoal.AUTOMATIC) {
        recommendedRate
    } else {
        chosenWeeklyRate ?: RecommendationEngine.weeklyRateFor(goal, weightKg) ?: 0.0
    }
    if (choosingGoal) {
        AlertDialog(
            onDismissRequest = { choosingGoal = false },
            title = { Text("Cambiar objetivo semanal") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Rumbo recomienda ${weeklyRateAction(recommendedRate)} cada semana.")
                    OutlinedButton(
                        onClick = {
                            onGoalChange(null)
                            choosingGoal = false
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        if (goal == WeightGoal.AUTOMATIC) {
                            Icon(Icons.Default.Check, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                        }
                        Text("Volver a lo recomendado")
                    }
                    HorizontalDivider()
                    Text("Elegir una cifra manual", fontWeight = FontWeight.SemiBold)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(
                            selected = manualDirection < 0.0,
                            onClick = { manualDirection = -1.0 },
                            label = { Text("Perder") }
                        )
                        FilterChip(
                            selected = manualDirection > 0.0,
                            onClick = { manualDirection = 1.0 },
                            label = { Text("Ganar") }
                        )
                    }
                    OutlinedTextField(
                        value = manualMagnitude,
                        onValueChange = {
                            manualMagnitude = it.filter { char ->
                                char.isDigit() || char == ',' || char == '.'
                            }.take(12)
                            manualError = null
                        },
                        label = { Text("Kg por semana") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Text(
                        "La cifra elegida se conserva, pero el cálculo puede limitarla por seguridad.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    manualError?.let {
                        Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    val magnitude = parseDecimal(manualMagnitude)
                    if (magnitude == null || !magnitude.isFinite() || magnitude < 0.0) {
                        manualError = "Introduce una cifra numérica válida."
                    } else {
                        onGoalChange(if (magnitude == 0.0) 0.0 else magnitude * manualDirection)
                        choosingGoal = false
                    }
                }) { Text("Usar esta cifra") }
            },
            dismissButton = {
                TextButton(onClick = { choosingGoal = false }) { Text("Cancelar") }
            }
        )
    }
    Card(Modifier.fillMaxWidth().clickable(onClick = onExplain)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            HomeCardHeader("Situación y objetivo")
            CombinedBodyScale(assessment)
            Text(
                weeklyGoalSummary(
                    recommendedRate = recommendedRate,
                    selectedRate = selectedRate,
                    automatic = goal == WeightGoal.AUTOMATIC,
                    appliedRate = recommendation?.calculation?.appliedWeeklyRateKg
                ) + if (recommendation == null) "" else " Para ello, cada día debes consumir:",
                style = MaterialTheme.typography.bodyLarge
            )
            if (recommendation == null) {
                Text(
                    "Añade una medición con peso para calcular los objetivos nutricionales.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            } else {
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    NutritionGoalMetric(
                        "Calorías", "${recommendation.calories} kcal",
                        Icons.Default.LocalFireDepartment, MaterialTheme.colorScheme.onSurface
                    )
                    NutritionGoalMetric(
                        "Proteína", "${recommendation.proteinGrams} g",
                        foodCategoryIcon(FoodCategory.PROTEIN), foodCategoryColor(FoodCategory.PROTEIN)
                    )
                    NutritionGoalMetric(
                        "Hidratos", "${recommendation.carbohydrateGrams} g",
                        foodCategoryIcon(FoodCategory.CARBOHYDRATE), foodCategoryColor(FoodCategory.CARBOHYDRATE)
                    )
                    NutritionGoalMetric(
                        "Grasa", "${recommendation.fatGrams} g",
                        foodCategoryIcon(FoodCategory.FAT), foodCategoryColor(FoodCategory.FAT)
                    )
                }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = onAddMeasurement, modifier = Modifier.weight(1f)) {
                    Text("Añadir medición")
                }
                OutlinedButton(onClick = { choosingGoal = true }, modifier = Modifier.weight(1f)) {
                    Text("Cambiar objetivo")
                }
            }
        }
    }
}

@Composable
private fun HomeCardHeader(title: String, showArrow: Boolean = true) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(title, modifier = Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
            if (showArrow) {
                Icon(
                    Icons.AutoMirrored.Filled.ArrowForward,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(20.dp)
                )
            }
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    }
}

@Composable
private fun CombinedBodyScale(assessment: BodyAssessment) {
    val labelColor = MaterialTheme.colorScheme.onSurface
    val labelSize = with(LocalDensity.current) { 12.sp.toPx() }
    Canvas(Modifier.fillMaxWidth().height(72.dp)) {
        val barTop = 32.dp.toPx()
        val barHeight = 8.dp.toPx()
        val gradient = Brush.horizontalGradient(
            0.00f to Color(0xFFE57373),
            0.25f to Color(0xFFFFCA4B),
            0.50f to Color(0xFF66BB6A),
            0.75f to Color(0xFFFFCA4B),
            1.00f to Color(0xFFE57373),
            startX = 0f,
            endX = size.width
        )
        drawRoundRect(
            brush = gradient,
            topLeft = Offset(0f, barTop),
            size = Size(size.width, barHeight),
            cornerRadius = CornerRadius(barHeight / 2f, barHeight / 2f)
        )
        val paint = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply {
            color = labelColor.toArgb()
            textSize = labelSize
            textAlign = android.graphics.Paint.Align.CENTER
            typeface = android.graphics.Typeface.create(
                android.graphics.Typeface.DEFAULT,
                android.graphics.Typeface.BOLD
            )
        }
        fun marker(position: Double, label: String, above: Boolean) {
            val x = (position.coerceIn(0.04, 0.96) * size.width).toFloat()
            val lineStart = if (above) 17.dp.toPx() else barTop
            val lineEnd = if (above) barTop + barHeight else 55.dp.toPx()
            drawLine(
                labelColor,
                Offset(x, lineStart),
                Offset(x, lineEnd),
                strokeWidth = 2.dp.toPx()
            )
            val textY = if (above) 13.dp.toPx() else 69.dp.toPx()
            drawContext.canvas.nativeCanvas.drawText(label, x, textY, paint)
        }
        assessment.bmi?.let {
            marker(
                mapRiskValue(it, listOf(14.0, 16.0, 18.5, 25.0, 30.0, 40.0)),
                "IMC ${formatOneDecimal(it)}",
                true
            )
        }
        assessment.waistToHeightRatio?.let {
            marker(
                mapRiskValue(it, listOf(0.30, 0.35, 0.40, 0.50, 0.60, 0.70)),
                "C/A ${formatTwoDecimals(it)}",
                false
            )
        }
    }
}

private fun mapRiskValue(value: Double, thresholds: List<Double>): Double {
    val positions = listOf(0.0, 0.20, 0.40, 0.60, 0.80, 1.0)
    if (value <= thresholds.first()) return positions.first()
    if (value >= thresholds.last()) return positions.last()
    val index = thresholds.zipWithNext().indexOfFirst { (start, end) -> value in start..end }
    val fraction = (value - thresholds[index]) / (thresholds[index + 1] - thresholds[index])
    return positions[index] + fraction * (positions[index + 1] - positions[index])
}

private fun weeklyRateAction(rate: Double): String = when {
    abs(rate) < 0.005 -> "mantener el peso"
    rate < 0.0 -> "perder ${formatOneDecimal(abs(rate))} kg"
    else -> "ganar ${formatOneDecimal(rate)} kg"
}

private fun weeklyGoalSummary(
    recommendedRate: Double,
    selectedRate: Double,
    automatic: Boolean,
    appliedRate: Double?
): String {
    if (automatic) {
        return "Te recomendamos ${weeklyRateAction(recommendedRate)} cada semana."
    }
    val applied = appliedRate ?: selectedRate
    if (abs(applied - selectedRate) < 0.005) {
        return "Te recomendamos ${weeklyRateAction(recommendedRate)} cada semana, " +
            "pero tú has elegido ${weeklyRateAction(selectedRate)}."
    }
    val safeLimit = when {
        abs(applied) < 0.005 && selectedRate < 0.0 ->
            "en tu situación no es recomendable perder peso"
        abs(applied) < 0.005 && selectedRate > 0.0 ->
            "en tu situación no es recomendable ganar peso"
        selectedRate < 0.0 ->
            "en tu situación no es recomendable perder más de ${formatOneDecimal(abs(applied))} kg cada semana"
        selectedRate > 0.0 ->
            "en tu situación no es recomendable ganar más de ${formatOneDecimal(abs(applied))} kg cada semana"
        else ->
            "en tu situación se recomienda mantener el peso"
    }
    return "Has elegido ${weeklyRateAction(selectedRate)} cada semana, pero $safeLimit."
}


@Composable
private fun NutritionGoalMetric(
    label: String,
    value: String,
    icon: ImageVector,
    color: Color,
    modifier: Modifier = Modifier
) {
    Row(
        modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center
    ) {
        Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(20.dp))
        Spacer(Modifier.width(4.dp))
        Text(
            value,
            color = color,
            style = MaterialTheme.typography.bodyLarge,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1
        )
    }
}

@Composable
private fun TodayPlanSection(
    meals: List<PlannedMeal>,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    recommendation: es.david.rumbo.model.Recommendation?,
    onOpenPlanner: () -> Unit,
    onOpenMeal: (Long) -> Unit,
    onAddMissing: (MealType, WeekDay) -> Unit,
    onApplyAdjustedMeals: (List<PlannedMeal>) -> Unit
) {
    val today = WeekDay.entries[LocalDate.now().dayOfWeek.value - 1]
    val todayMeals = meals.filter { today in it.days }.associateBy { it.type }
    val assessment = recommendation?.let {
        MealPlanEvaluator.assessDay(today, meals, foodsById, dishesById, it)
    }
    var optimizationPreview by remember { mutableStateOf<QuantityOptimizationResult?>(null) }
    var optimizationMessage by remember { mutableStateOf<String?>(null) }
    optimizationPreview?.let { result ->
        QuantityOptimizationPreviewDialog(
            result = result,
            onApply = {
                onApplyAdjustedMeals(result.meals)
                optimizationPreview = null
            },
            onDismiss = { optimizationPreview = null }
        )
    }
    optimizationMessage?.let { message ->
        AlertDialog(
            onDismissRequest = { optimizationMessage = null },
            title = { Text("Ajustar cantidades") },
            text = { Text(message) },
            confirmButton = {
                TextButton(onClick = { optimizationMessage = null }) { Text("Entendido") }
            }
        )
    }
    Card(Modifier.fillMaxWidth().clickable(onClick = onOpenPlanner)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            HomeCardHeader("Menú de hoy, ${today.label.lowercase()}")
            assessment?.let { TodayNutritionSummary(it) }
            Text(
                todayAssessmentText(assessment),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            MealType.entries.forEachIndexed { index, type ->
                val meal = todayMeals[type]
                val entries = meal?.let {
                    it.dishes.mapNotNull { planned ->
                        dishesById[planned.dishId]?.let { dish ->
                            MenuItemLine(
                                dish.name,
                                it.resolvedGrams(planned, today),
                                dish.dominantCategory(foodsById),
                                locked = !planned.adjustable
                            )
                        }
                    } + it.items.mapNotNull { planned ->
                        foodsById[planned.foodId]?.let { food ->
                            MenuItemLine(
                                food.name,
                                it.resolvedGrams(planned, today),
                                food.category,
                                locked = !planned.adjustable
                            )
                        }
                    }
                }.orEmpty()
                Column(
                    Modifier.fillMaxWidth().padding(vertical = 5.dp),
                    verticalArrangement = Arrangement.spacedBy(9.dp)
                ) {
                    Row(
                        Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            type.label,
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                    if (entries.isNotEmpty()) {
                        entries.forEach { entry ->
                            Row(
                                Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                SmallFoodCategoryBadge(entry.category)
                                Text(entry.name, modifier = Modifier.weight(1f))
                                if (entry.locked) {
                                    Icon(
                                        Icons.Default.Lock,
                                        contentDescription = "Cantidad fijada por ti",
                                        modifier = Modifier.size(17.dp),
                                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                Text(
                                    "${formatDecimal(entry.grams)} g",
                                    fontWeight = FontWeight.SemiBold,
                                    textAlign = TextAlign.End
                                )
                            }
                        }
                    }
                }
                if (index < MealType.entries.lastIndex) {
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(
                    onClick = {
                        if (recommendation == null) {
                            optimizationMessage = "Necesitas una recomendación nutricional antes de ajustar el menú."
                        } else {
                            val result = MealQuantityOptimizer.optimize(
                                meals, foodsById, dishesById, recommendation
                            )
                            if (result.changes.isNotEmpty()) optimizationPreview = result
                            else optimizationMessage = if (result.days.isEmpty()) {
                                "Completa el día y marca uno o varios elementos como ajustables. Las cantidades fijas nunca se modifican."
                            } else {
                                "Las cantidades actuales ya son la mejor combinación encontrada dentro de los límites indicados."
                            }
                        }
                    },
                    modifier = Modifier.weight(1f)
                ) { Text("Ajustar cantidades") }
                OutlinedButton(
                    onClick = onOpenPlanner,
                    modifier = Modifier.weight(1f)
                ) { Text("Ver menú semanal") }
            }
        }
    }
}

private data class MenuItemLine(
    val name: String,
    val grams: Double,
    val category: FoodCategory,
    val locked: Boolean
)

@Composable
private fun TodayNutritionSummary(assessment: PlanNutritionAssessment) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        NutritionPercentMetric(
            "Calorías", assessment.actual.calories, assessment.target.calories,
            Icons.Default.LocalFireDepartment, MaterialTheme.colorScheme.onSurface, Modifier.weight(1f)
        )
        NutritionPercentMetric(
            "Proteína", assessment.actual.proteinGrams, assessment.target.proteinGrams,
            foodCategoryIcon(FoodCategory.PROTEIN), foodCategoryColor(FoodCategory.PROTEIN), Modifier.weight(1f)
        )
        NutritionPercentMetric(
            "Hidratos", assessment.actual.carbohydrateGrams, assessment.target.carbohydrateGrams,
            foodCategoryIcon(FoodCategory.CARBOHYDRATE), foodCategoryColor(FoodCategory.CARBOHYDRATE), Modifier.weight(1f)
        )
        NutritionPercentMetric(
            "Grasa", assessment.actual.fatGrams, assessment.target.fatGrams,
            foodCategoryIcon(FoodCategory.FAT), foodCategoryColor(FoodCategory.FAT), Modifier.weight(1f)
        )
    }
}

@Composable
private fun NutritionPercentMetric(
    label: String,
    actual: Double,
    target: Double,
    icon: ImageVector,
    color: Color,
    modifier: Modifier = Modifier
) {
    val ratio = if (target > 0.0) actual / target else 0.0
    Row(
        modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center
    ) {
        Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(20.dp))
        Spacer(Modifier.width(4.dp))
        Text(
            "${(ratio * 100).roundToInt()} %",
            color = color,
            style = MaterialTheme.typography.bodyLarge,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1
        )    }
}

private fun todayAssessmentText(assessment: PlanNutritionAssessment?): String {
    if (assessment == null) return "Añade una medición para poder valorar este menú."
    if (assessment.missingMealTypes.isNotEmpty()) {
        return "Faltan: ${assessment.missingMealTypes.joinToString { it.label.lowercase() }}."
    }
    if (!assessment.actual.isComplete) return "Faltan datos nutricionales para valorar el menú completo."
    val nutrients = listOf(
        Triple("calorías", assessment.actual.calories, assessment.target.calories),
        Triple("proteína", assessment.actual.proteinGrams, assessment.target.proteinGrams),
        Triple("hidratos", assessment.actual.carbohydrateGrams, assessment.target.carbohydrateGrams),
        Triple("grasa", assessment.actual.fatGrams, assessment.target.fatGrams)
    )
    val below = nutrients.filter { (_, actual, target) -> target > 0.0 && actual < target * 0.90 }
        .map { it.first }
    val above = nutrients.filter { (_, actual, target) -> target > 0.0 && actual > target * 1.10 }
        .map { it.first }
    if (below.isEmpty() && above.isEmpty()) return "El menú del día está bien ajustado a tus objetivos."
    return buildList {
        if (below.isNotEmpty()) add("Por debajo del objetivo: ${below.joinToString()}.")
        if (above.isNotEmpty()) add("Por encima del objetivo: ${above.joinToString()}.")
    }.joinToString(" ")
}

@Composable
private fun HomeShoppingSection(
    meals: List<PlannedMeal>,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    profileId: Long?,
    onOpenFoods: () -> Unit
) {
    val amounts = remember(meals, dishesById) {
        MealPlanEvaluator.weeklyFoodAmounts(meals, dishesById)
    }
    val entries = remember(amounts, foodsById) {
        amounts.mapNotNull { (foodId, grams) -> foodsById[foodId]?.let { it to grams } }
            .sortedBy { it.first.name.lowercase() }
    }
    val context = LocalContext.current
    val shoppingPreferences = remember { context.getSharedPreferences("shopping_state", 0) }
    val preferenceKey = "available_foods_${profileId ?: 0L}"
    var availableFoodIds by remember(profileId) {
        mutableStateOf(
            shoppingPreferences.getStringSet(preferenceKey, emptySet())
                .orEmpty()
                .mapNotNull(String::toLongOrNull)
        )
    }
    fun saveAvailableFoods(updated: List<Long>) {
        availableFoodIds = updated
        shoppingPreferences.edit()
            .putStringSet(preferenceKey, updated.map(Long::toString).toSet())
            .apply()
    }
    val neededEntries = entries.filterNot { (food, _) -> food.id in availableFoodIds }
    val notNeededEntries = entries.filter { (food, _) -> food.id in availableFoodIds }

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Box(Modifier.fillMaxWidth().clickable(onClick = onOpenFoods)) {
                HomeCardHeader("Lista de la compra")
            }
            if (entries.isEmpty()) {
                Text("El plan todavía no contiene alimentos.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                Text(
                    "Por comprar",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(top = 4.dp)
                )
                neededEntries.forEach { (food, grams) ->
                    HomeShoppingEntry(
                        food = food,
                        grams = grams,
                        checked = false,
                        onCheckedChange = { available ->
                            if (available) saveAvailableFoods(availableFoodIds + food.id)
                        }
                    )
                }
                if (notNeededEntries.isNotEmpty()) {
                    HorizontalDivider(Modifier.padding(vertical = 4.dp))
                    Text(
                        "No hace falta comprar",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    notNeededEntries.forEach { (food, grams) ->
                        HomeShoppingEntry(
                            food = food,
                            grams = grams,
                            checked = true,
                            onCheckedChange = { available ->
                                if (!available) saveAvailableFoods(availableFoodIds - food.id)
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun HomeShoppingEntry(
    food: Food,
    grams: Double,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(2.dp)
    ) {
        Checkbox(
            checked = checked,
            onCheckedChange = onCheckedChange,
            modifier = Modifier.size(32.dp)
        )
        Text(food.name, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
        Text("${formatDecimal(grams)} g", fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun BodyIndicator(
    label: String,
    value: String
) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom) {
        Text(
            label,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold
        )
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
    Canvas(Modifier.fillMaxWidth().height(118.dp)) {
        val top = 6.dp.toPx()
        val bottom = size.height - 6.dp.toPx()
        val left = 8.dp.toPx()
        val right = size.width - 48.dp.toPx()
        val valueRange = maximum - minimum
        fun yFor(value: Double): Float = bottom -
            ((value - minimum) / valueRange).coerceIn(0.0, 1.0).toFloat() * (bottom - top)
        fun stopFor(value: Double): Float =
            (1.0 - (value - minimum) / valueRange).coerceIn(0.0, 1.0).toFloat()

        val topBand = bands.maxByOrNull { it.end }
        val bottomBand = bands.minByOrNull { it.start }
        val gradientStops = buildList {
            topBand?.let { add(0f to it.color.copy(alpha = 0.38f)) }
            bands.sortedByDescending { (it.start + it.end) / 2.0 }.forEach { band ->
                add(stopFor((band.start + band.end) / 2.0) to band.color.copy(alpha = 0.38f))
            }
            bottomBand?.let { add(1f to it.color.copy(alpha = 0.38f)) }
        }.distinctBy { it.first }.sortedBy { it.first }
        val gradient = Brush.verticalGradient(
            *gradientStops.toTypedArray(),
            startY = top,
            endY = bottom
        )
        drawRoundRect(
            brush = gradient,
            topLeft = Offset(0f, top),
            size = Size(size.width, bottom - top),
            cornerRadius = CornerRadius(8.dp.toPx(), 8.dp.toPx())
        )

        val paint = android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply {
            color = labelColor.toArgb()
            textSize = labelSize
            textAlign = android.graphics.Paint.Align.RIGHT
            typeface = android.graphics.Typeface.create(
                android.graphics.Typeface.DEFAULT,
                android.graphics.Typeface.BOLD
            )
        }
        thresholds.forEach { (threshold, label) ->
            val y = yFor(threshold)
            drawLine(
                labelColor.copy(alpha = 0.28f),
                Offset(0f, y),
                Offset(size.width, y),
                strokeWidth = 1.dp.toPx()
            )
            drawContext.canvas.nativeCanvas.drawText(label, size.width - 6.dp.toPx(), y - 4.dp.toPx(), paint)
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
                drawLine(lineColor, start, end, strokeWidth = 2.5.dp.toPx(), cap = StrokeCap.Round)
            }
            offsets.forEach { point ->
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
                color = MaterialTheme.colorScheme.onSurface
            )
            Spacer(Modifier.width(6.dp))
            Text("kcal/día", modifier = Modifier.padding(bottom = 8.dp))
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            MacroValue(
                "Proteína",
                recommendation.proteinGrams,
                foodCategoryColor(FoodCategory.PROTEIN)
            )
            MacroValue(
                "Hidratos",
                recommendation.carbohydrateGrams,
                foodCategoryColor(FoodCategory.CARBOHYDRATE)
            )
            MacroValue(
                "Grasa",
                recommendation.fatGrams,
                foodCategoryColor(FoodCategory.FAT)
            )
        }
        if (recommendation.calculation != null) {
            TextButton(onClick = onExplain) {
                Text("Entender esta recomendación")
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
private fun PlainNarrativeSection(title: String, body: String) {
    Column(
        Modifier.fillMaxWidth().padding(top = 8.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Text(
            body,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

private const val NICE_BODY_ASSESSMENT_URL =
    "https://www.nice.org.uk/guidance/ng246/chapter/Identifying-and-assessing-overweight-obesity-and-central-adiposity"
private const val NHS_WEIGHT_LOSS_RATE_URL =
    "https://www.nhs.uk/live-well/healthy-weight/managing-your-weight/tips-to-help-you-lose-weight/"
private const val MIFFLIN_ST_JEOR_URL =
    "https://pubmed.ncbi.nlm.nih.gov/2305711/"
private const val ENERGY_BALANCE_MODEL_URL =
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC3859816/"
private const val PROTEIN_META_ANALYSIS_URL =
    "https://pubmed.ncbi.nlm.nih.gov/28698222/"

private fun bmiExplanation(bmi: Double): String {
    val interpretation = when {
        bmi < 18.5 ->
            "Tu IMC es ${formatOneDecimal(bmi)}, por debajo del intervalo habitual. Esto puede indicar que tu peso es bajo para tu altura."
        bmi < 25.0 ->
            "Tu IMC es ${formatOneDecimal(bmi)}, dentro del intervalo habitual. Tu peso y tu altura guardan una proporción adecuada según este indicador."
        bmi < 30.0 ->
            "Tu IMC es ${formatOneDecimal(bmi)}, un poco por encima del intervalo habitual."
        bmi < 35.0 ->
            "Tu IMC es ${formatOneDecimal(bmi)}, claramente por encima del intervalo habitual."
        else ->
            "Tu IMC es ${formatOneDecimal(bmi)}, bastante por encima del intervalo habitual."
    }
    return "El IMC relaciona tu peso con tu altura y sirve para estimar si ambos están proporcionados. " +
        interpretation +
        " Es solo una referencia, porque no distingue entre grasa y músculo, así que conviene interpretarlo junto con tu cintura."
}

private fun waistToHeightExplanation(ratio: Double, heightCm: Double?): String {
    val percentage = formatDecimal(ratio * 100.0)
    val interpretation = when {
        ratio < 0.40 ->
            "Tu cintura equivale al $percentage % de tu altura, por debajo del intervalo habitual. Este resultado debe interpretarse junto con tu peso y tu IMC."
        ratio < 0.50 ->
            "Tu cintura equivale al $percentage % de tu altura y se encuentra dentro de la referencia recomendada."
        ratio < 0.60 ->
            "Tu cintura equivale al $percentage % de tu altura, ligeramente por encima de la referencia recomendada."
        else ->
            "Tu cintura equivale al $percentage % de tu altura, claramente por encima de la referencia recomendada."
    }
    val target = if (ratio >= 0.50 && heightCm != null) {
        " Lo ideal es que mida menos de la mitad de tu altura; en tu caso, menos de ${formatOneDecimal(heightCm / 2.0)} cm."
    } else {
        ""
    }
    return "Este índice compara el tamaño de tu cintura con tu altura y ayuda a estimar la grasa acumulada alrededor del abdomen. " +
        interpretation + target
}

private fun combinedBodyExplanation(bmi: Double, ratio: Double): String = when {
    bmi >= 35.0 ->
        "La prioridad debería ser una pérdida de peso gradual y sostenida. Con un IMC de este nivel, la cintura aporta poca información adicional para decidir el objetivo, aunque sigue siendo útil para seguir el progreso. Puede ser recomendable contar también con supervisión sanitaria."
    bmi < 18.5 && ratio < 0.50 ->
        "Tu prioridad debería ser ganar peso de forma gradual, procurando que una parte importante sea músculo. Para ello conviene comer algo más, tomar suficiente proteína y entrenar fuerza con regularidad. No parece adecuado reducir calorías."
    bmi < 18.5 ->
        "Aunque tu cintura es elevada, perder más peso podría no ser conveniente. Lo más adecuado sería mejorar la composición corporal: mantener o aumentar ligeramente las calorías, tomar suficiente proteína y entrenar fuerza. Es una combinación poco habitual y merece interpretarse con cautela."
    bmi < 25.0 && ratio < 0.50 ->
        "Tus resultados no señalan la necesidad de cambiar de peso. Mantenerlo mientras conservas una alimentación adecuada y cierta actividad física sería un objetivo razonable. Si quieres mejorar la composición corporal, puedes hacerlo mediante fuerza y suficiente proteína sin reducir calorías."
    bmi < 25.0 && ratio < 0.60 ->
        "Tu peso no necesita bajar mucho, pero sí sería conveniente reducir la cintura. Lo más adecuado sería perder grasa lentamente mientras mantienes o aumentas el músculo, con un ajuste calórico pequeño, suficiente proteína y entrenamiento de fuerza. La cintura será más informativa que el peso para valorar el progreso."
    bmi < 25.0 ->
        "Aunque tu peso total está dentro del intervalo habitual, la acumulación abdominal es elevada. Reducir la cintura debería ser la prioridad, mediante una pérdida moderada de grasa, actividad física regular y entrenamiento de fuerza para conservar músculo."
    ratio < 0.50 ->
        "Tienes más peso del habitual, pero sin una acumulación abdominal elevada. Si entrenas fuerza y tomas suficiente proteína, parte de ese peso podría ser músculo y sería razonable priorizar una pérdida lenta o la recomposición corporal. Si no es así, una reducción gradual de peso probablemente mejoraría tu situación."
    ratio < 0.60 ->
        "Lo más adecuado sería perder grasa de forma gradual, procurando conservar el músculo. Para ello conviene combinar un déficit calórico moderado con suficiente proteína, entrenamiento de fuerza y actividad física regular. Deberían disminuir tanto el peso como la cintura."
    else ->
        "La prioridad debería ser reducir de forma gradual el peso y, especialmente, la cintura. Conviene evitar objetivos extremos y combinar una alimentación con déficit moderado, suficiente proteína, entrenamiento de fuerza y actividad aeróbica regular."
}

@Composable
private fun BodyExplanationScreen(
    data: AppData,
    onOpenMeasurement: (Long) -> Unit
) {
    val profile = data.profile
    val assessment = profile?.let { RecommendationEngine.assessBody(it, data.measurements) }
    val recommendedGoal = profile?.let { RecommendationEngine.recommendGoal(it, data.measurements) }
    val latest = data.measurements.maxWithOrNull(compareBy<Measurement> { it.date }.thenBy { it.id })
    val recommendation = latest?.recommendation
    val calculation = recommendation?.calculation
    val uriHandler = LocalUriHandler.current
    val ordered = data.measurements.sortedWith(compareBy<Measurement> { it.date }.thenBy { it.id })
    val heightM = profile?.heightCm?.div(100.0)
    val bmiPoints = if (heightM == null) emptyList() else ordered.mapNotNull { item ->
        item.weightKg?.let { item.date to it / heightM.pow(2) }
    }
    val waistPoints = if (profile == null) emptyList() else ordered.mapNotNull { item ->
        item.waistCm?.let { item.date to it / profile.heightCm }
    }

    LazyColumn(
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp)
    ) {
        assessment?.bmi?.let { bmi ->
            item {
                BodyIndicator(
                    label = "IMC",
                    value = formatOneDecimal(bmi)
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
                Spacer(Modifier.height(10.dp))
                Text(
                    bmiExplanation(bmi),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface
                )
                TextButton(
                    onClick = { uriHandler.openUri(NICE_BODY_ASSESSMENT_URL) },
                    contentPadding = PaddingValues(0.dp)
                ) { Text("Fuente: criterios de NICE sobre el IMC") }
            }
        }
        assessment?.waistToHeightRatio?.let { ratio ->
            item {
                BodyIndicator(
                    label = "Cintura / altura",
                    value = formatTwoDecimals(ratio)
                )
                ProgressChart(
                    points = waistPoints,
                    minimum = 0.35,
                    maximum = 0.70,
                    bands = listOf(
                        RiskBand(0.35, 0.40, Color(0xFFFFCA4B)),
                        RiskBand(0.40, 0.50, Color(0xFF66BB6A)),
                        RiskBand(0.50, 0.60, Color(0xFFFFCA4B)),
                        RiskBand(0.60, 0.70, Color(0xFFE57373))
                    ),
                    thresholds = listOf(0.40 to "0,40", 0.50 to "0,50", 0.60 to "0,60")
                )
                Spacer(Modifier.height(10.dp))
                Text(
                    waistToHeightExplanation(ratio, profile.heightCm),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface
                )
                TextButton(
                    onClick = { uriHandler.openUri(NICE_BODY_ASSESSMENT_URL) },
                    contentPadding = PaddingValues(0.dp)
                ) { Text("Fuente: criterios de NICE sobre cintura y altura") }
            }
        }
        if (assessment?.bmi != null && assessment.waistToHeightRatio != null) {
            item {
                Text(
                    "Nuestra recomendación",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold
                )
                Spacer(Modifier.height(10.dp))
                Text(
                    combinedBodyExplanation(assessment.bmi, assessment.waistToHeightRatio),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface
                )
                recommendedGoal?.let { result ->
                    Spacer(Modifier.height(12.dp))
                    Text(
                        result.explanation,
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    if (result.goal in setOf(WeightGoal.LOSE_SLOWLY, WeightGoal.LOSE_FASTER)) {
                        TextButton(
                            onClick = { uriHandler.openUri(NHS_WEIGHT_LOSS_RATE_URL) },
                            contentPadding = PaddingValues(0.dp)
                        ) { Text("Referencia: ritmo gradual recomendado por el NHS") }
                    }
                }

                if (recommendation != null && calculation != null) {
                    val requestedRate = calculation.goalAdjustmentCalories * 7.0 / 7700.0
                    val goalBasedCalories =
                        calculation.maintenanceCalories + calculation.goalAdjustmentCalories
                    val goalCalculation = when {
                        abs(requestedRate) < 0.0001 ->
                            "Como el objetivo es mantener el peso, no aplicamos déficit ni superávit y tomamos como referencia las ${formatOneDecimal(calculation.maintenanceCalories)} kcal con las que estimamos que mantendrías el peso."
                        requestedRate < 0.0 ->
                            "Para perder ${formatOneDecimal(abs(requestedRate))} kg por semana necesitas un déficit aproximado de ${formatOneDecimal(abs(calculation.goalAdjustmentCalories))} kcal diarias. Lo restamos a las ${formatOneDecimal(calculation.maintenanceCalories)} kcal de mantenimiento y obtenemos ${formatOneDecimal(goalBasedCalories)} kcal."
                        else ->
                            "Para ganar ${formatOneDecimal(requestedRate)} kg por semana necesitas un superávit aproximado de ${formatOneDecimal(calculation.goalAdjustmentCalories)} kcal diarias. Lo añadimos a las ${formatOneDecimal(calculation.maintenanceCalories)} kcal de mantenimiento y obtenemos ${formatOneDecimal(goalBasedCalories)} kcal."
                    }
                    val adjustments = buildList {
                        calculation.goalSafetyExplanation?.let {
                            add(it.replaceFirstChar(Char::uppercaseChar) + ".")
                        }
                        calculation.energyLimitExplanation?.let {
                            add(
                                it.replaceFirstChar(Char::uppercaseChar) +
                                    " y modifica el cálculo en ${formatSignedKcal(calculation.energyLimitAdjustmentCalories)} kcal."
                            )
                        }
                        if (abs(calculation.historyAdjustmentCalories) >= 0.05) {
                            add(
                                calculation.historyExplanation.replaceFirstChar(Char::uppercaseChar) +
                                    "; por eso aplica ${formatSignedKcal(calculation.historyAdjustmentCalories)} kcal."
                            )
                        } else {
                            add(calculation.historyExplanation.replaceFirstChar(Char::uppercaseChar) + ".")
                        }
                        calculation.previousLimitExplanation?.let {
                            add(it.replaceFirstChar(Char::uppercaseChar) + ".")
                        }
                    }.joinToString(" ")
                    Spacer(Modifier.height(12.dp))
                    Text(
                        "Según tu peso, altura, edad y sexo, Mifflin–St Jeor estima un gasto de ${formatOneDecimal(calculation.restingCalories)} kcal al día en reposo. Al incorporar tu actividad «${calculation.activity.label.lowercase()}», estimamos un mantenimiento de ${formatOneDecimal(calculation.maintenanceCalories)} kcal.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Spacer(Modifier.height(10.dp))
                    Text(
                        "$goalCalculation",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Spacer(Modifier.height(10.dp))
                    Text(
                        "$adjustments Tras los ajustes obtenemos ${formatOneDecimal(calculation.beforeRoundingCalories)} kcal y redondeamos al múltiplo de 25 más cercano: ${recommendation.calories} kcal al día.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    TextButton(
                        onClick = { uriHandler.openUri(MIFFLIN_ST_JEOR_URL) },
                        contentPadding = PaddingValues(0.dp)
                    ) { Text("Referencia: fórmula de Mifflin–St Jeor") }
                    TextButton(
                        onClick = { uriHandler.openUri(ENERGY_BALANCE_MODEL_URL) },
                        contentPadding = PaddingValues(0.dp)
                    ) { Text("Referencia: déficit energético y cambio de peso") }

                    val calculationHeightM = calculation.heightCm / 100.0
                    val proteinReferenceWeight =
                        minOf(calculation.weightKg, 30.0 * calculationHeightM.pow(2))
                    val proteinContext = when {
                        calculation.goalAdjustmentCalories < 0.0 ->
                            "Priorizamos ${recommendation.proteinGrams} g de proteína para ayudar a conservar músculo durante la pérdida de grasa."
                        calculation.goalAdjustmentCalories > 0.0 ->
                            "Priorizamos ${recommendation.proteinGrams} g de proteína para favorecer que parte del peso ganado sea músculo, especialmente si entrenas fuerza."
                        else ->
                            "Priorizamos ${recommendation.proteinGrams} g de proteína para facilitar el mantenimiento y desarrollo muscular."
                    }
                    val referenceWeightText =
                        if (proteinReferenceWeight < calculation.weightKg - 0.05) {
                            " Para calcularla usamos un peso de referencia de ${formatOneDecimal(proteinReferenceWeight)} kg, porque hacerlo sobre todo tu peso actual produciría una cifra innecesariamente alta."
                        } else {
                            ""
                        }
                    Spacer(Modifier.height(12.dp))
                    Text(
                        buildAnnotatedString {
                            val marker = "${recommendation.proteinGrams} g de proteína"
                            val parts = proteinContext.split(marker, limit = 2)
                            append(parts.first())
                            withStyle(
                                SpanStyle(
                                    color = foodCategoryColor(FoodCategory.PROTEIN),
                                    fontWeight = FontWeight.SemiBold
                                )
                            ) { append(marker) }
                            if (parts.size > 1) append(parts[1])
                            append(referenceWeightText)
                        },
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Spacer(Modifier.height(10.dp))
                    Text(
                        buildAnnotatedString {
                            append("Reservamos aproximadamente el 25 % de las calorías para ")
                            withStyle(
                                SpanStyle(
                                    color = foodCategoryColor(FoodCategory.FAT),
                                    fontWeight = FontWeight.SemiBold
                                )
                            ) { append("${recommendation.fatGrams} g de grasa") }
                            append(" y completamos las calorías restantes con ")
                            withStyle(
                                SpanStyle(
                                    color = foodCategoryColor(FoodCategory.CARBOHYDRATE),
                                    fontWeight = FontWeight.SemiBold
                                )
                            ) { append("${recommendation.carbohydrateGrams} g de hidratos") }
                            append(" para aportar energía.")
                        },
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Spacer(Modifier.height(10.dp))
                    Text(
                        "Este no es el único reparto saludable posible, pero ofrece un equilibrio razonable entre composición corporal, energía y facilidad para mantener la dieta.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    TextButton(
                        onClick = { uriHandler.openUri(PROTEIN_META_ANALYSIS_URL) },
                        contentPadding = PaddingValues(0.dp)
                    ) { Text("Referencia: proteína y conservación muscular") }
                }
            }
        }
        item { HorizontalDivider() }
        item {
            Text(
                "Historial",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold
            )
        }
        if (data.measurements.isEmpty()) {
            item {
                Text(
                    "Todavía no hay mediciones",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }
        } else {
            items(
                data.measurements.sortedWith(
                    compareByDescending<Measurement> { it.date }.thenByDescending { it.id }
                ),
                key = { "body_history_${it.id}" }
            ) { measurement ->
                HistoryEntry(measurement = measurement, onClick = { onOpenMeasurement(measurement.id) })
                HorizontalDivider()
            }
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
private fun MacroValue(label: String, grams: Int, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            "$grams g",
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.titleMedium,
            color = color
        )
        Text(label, style = MaterialTheme.typography.labelMedium, color = color)
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
                    color = MaterialTheme.colorScheme.onSurface
                )
                Spacer(Modifier.width(5.dp))
                Text("kcal/día", modifier = Modifier.padding(bottom = 4.dp))
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                MacroValue(
                    "Proteína",
                    recommendation.proteinGrams,
                    foodCategoryColor(FoodCategory.PROTEIN)
                )
                MacroValue(
                    "Hidratos",
                    recommendation.carbohydrateGrams,
                    foodCategoryColor(FoodCategory.CARBOHYDRATE)
                )
                MacroValue(
                    "Grasa",
                    recommendation.fatGrams,
                    foodCategoryColor(FoodCategory.FAT)
                )
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
    var weight by rememberSaveable(initial?.id) { mutableStateOf(initial?.weightKg?.let(::formatDecimal) ?: "") }
    var waist by rememberSaveable(initial?.id) { mutableStateOf(initial?.waistCm?.let(::formatDecimal) ?: "") }
    var activity by remember(initial?.id) { mutableStateOf(initial?.activity) }
    var compliance by remember(initial?.id) { mutableStateOf(initial?.compliance) }
    var goal by remember(initial?.id) { mutableStateOf(initial?.goal) }
    var error by rememberSaveable(initial?.id) { mutableStateOf<String?>(null) }
    var showDatePicker by remember { mutableStateOf(false) }
    val inherited = RecommendationEngine.effectiveValues(data.measurements.filterNot { it.id == initial?.id })

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
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Medición", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                HorizontalDivider()
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
                    if (isEditing) "Deja vacío un dato si esta entrada no lo modificó."
                    else "Puedes registrar solo uno. El otro conservará su último valor conocido.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                WaistMeasurementHelp()
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Contexto", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                HorizontalDivider()
                SelectorField(
                    label = "Actividad habitual",
                    selectedLabel = activity?.label ?: "Mantener la anterior · \${inherited.activity.label}",
                    options = ActivityLevel.entries,
                    optionLabel = { "\${it.label} · \${it.description}" },
                    onSelect = { activity = it },
                    onClear = { activity = null }
                )
                SelectorField(
                    label = "Cómo has seguido el plan",
                    selectedLabel = compliance?.label ?: "Sin indicar",
                    options = DietCompliance.entries,
                    optionLabel = { it.label },
                    onSelect = { compliance = it },
                    onClear = { compliance = null }
                )
                Text(
                    "Indica, desde la medición anterior, si comiste aproximadamente lo previsto o una cantidad distinta.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
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
            }
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        OutlinedButton(
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

private data class PlanningCandidate(
    val kind: PlannedItemKind,
    val id: Long,
    val name: String,
    val defaultGrams: Double
)


@Composable
private fun PlanningRuleCards(
    itemKind: PlannedItemKind,
    itemId: Long,
    defaultGrams: Double,
    rule: PlanningRule?,
    onSave: (PlanningRule) -> Unit,
    onDelete: () -> Unit
) {
    var editingFixedType by remember(itemKind, itemId) { mutableStateOf<MealType?>(null) }
    var fixedAmount by remember(itemKind, itemId, editingFixedType, rule?.fixedGrams) {
        mutableStateOf(
            editingFixedType?.let { type ->
                rule?.fixedGrams?.get(type)?.let(::formatDecimal)
            }.orEmpty()
        )
    }
    val base = rule ?: PlanningRule(
        itemKind = itemKind,
        itemId = itemId,
        allowedMealTypes = emptySet(),
        fixedSlots = emptySet(),
        frequency = PlanningFrequency.NEVER,
        preferredGrams = defaultGrams
    )

    fun persist(updated: PlanningRule) {
        if (updated.frequency == PlanningFrequency.NEVER && updated.fixedSlots.isEmpty()) {
            onDelete()
        } else {
            onSave(updated)
        }
    }

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Añadirlo al menú", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
            HorizontalDivider()
            Text(
                "Rumbo lo tendrá en cuenta al generar nuevas semanas.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium
            )
            SelectorField(
                label = "Frecuencia",
                selectedLabel = if (rule == null || base.frequency == PlanningFrequency.NEVER) {
                    "No añadir aleatoriamente"
                } else base.frequency.label,
                options = PlanningFrequency.entries,
                optionLabel = {
                    if (it == PlanningFrequency.NEVER) "No añadir aleatoriamente" else it.label
                },
                onSelect = { selected ->
                    val allowed = if (
                        selected != PlanningFrequency.NEVER && base.allowedMealTypes.isEmpty()
                    ) MealType.entries.toSet() else base.allowedMealTypes
                    persist(base.copy(frequency = selected, allowedMealTypes = allowed))
                },
                onClear = null
            )
            if (base.frequency != PlanningFrequency.NEVER) {
                Text("Puede aparecer en", fontWeight = FontWeight.SemiBold)
                MealType.entries.chunked(3).forEach { types ->
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        types.forEach { type ->
                            FilterChip(
                                selected = type in base.allowedMealTypes,
                                onClick = {
                                    val updated = if (type in base.allowedMealTypes) {
                                        base.allowedMealTypes - type
                                    } else base.allowedMealTypes + type
                                    if (updated.isNotEmpty()) {
                                        persist(base.copy(allowedMealTypes = updated))
                                    }
                                },
                                label = { Text(type.label) }
                            )
                        }
                    }
                }
            }
        }
    }

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Comidas fijas", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
            HorizontalDivider()
            Text(
                "Añade todas las combinaciones de comida y día en las que debe aparecer siempre.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium
            )
            val configuredTypes = MealType.entries.filter { type ->
                base.fixedSlots.any { it.mealType == type }
            }
            if (configuredTypes.isNotEmpty()) {
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    configuredTypes.forEach { type ->
                        FilterChip(
                            selected = editingFixedType == type,
                            onClick = { editingFixedType = type },
                            label = { Text(type.label) }
                        )
                    }
                }
            }
            SelectorField(
                label = "Añadir o editar",
                selectedLabel = editingFixedType?.label ?: "Elegir comida",
                options = MealType.entries,
                optionLabel = { it.label },
                onSelect = { editingFixedType = it },
                onClear = null
            )
            editingFixedType?.let { type ->
                FixedDayRow(
                    label = "Días fijos en ${type.label.lowercase()}",
                    type = type,
                    selected = base.fixedSlots,
                    onChange = { updatedSlots ->
                        val hasType = updatedSlots.any { it.mealType == type }
                        persist(
                            base.copy(
                                fixedSlots = updatedSlots,
                                fixedGrams = if (hasType) base.fixedGrams
                                else base.fixedGrams - type
                            )
                        )
                    }
                )
                OutlinedTextField(
                    value = fixedAmount,
                    onValueChange = { fixedAmount = it.take(8) },
                    label = { Text("Cantidad fija (opcional)") },
                    placeholder = { Text("Cualquier cantidad") },
                    suffix = { Text("g", color = MaterialTheme.colorScheme.onSurfaceVariant) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Text(
                    "Si lo dejas vacío, Rumbo ajustará la cantidad a las necesidades de esa comida.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                OutlinedButton(
                    onClick = {
                        val grams = parseDecimal(fixedAmount)
                        val amounts = if (fixedAmount.isBlank()) {
                            base.fixedGrams - type
                        } else {
                            base.fixedGrams + (type to checkNotNull(grams))
                        }
                        persist(base.copy(fixedGrams = amounts))
                    },
                    enabled = fixedAmount.isBlank() ||
                        (parseDecimal(fixedAmount)?.let { it in 0.1..5000.0 } == true),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(if (fixedAmount.isBlank()) "Permitir cualquier cantidad" else "Guardar cantidad")
                }
            }
            if (configuredTypes.isEmpty() && editingFixedType == null) {
                Text(
                    "Todavía no hay ninguna comida fija.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
    }
}

@Composable
private fun AutomaticPlanningScreen(
    rules: List<PlanningRule>,
    foods: List<Food>,
    dishes: List<Dish>,
    onSaveRule: (PlanningRule) -> Unit,
    onDeleteRule: (PlannedItemKind, Long) -> Unit
) {
    val foodsById = remember(foods) { foods.associateBy { it.id } }
    val candidates = remember(foods, dishes) {
        dishes.map { dish ->
            PlanningCandidate(
                PlannedItemKind.DISH,
                dish.id,
                dish.name,
                dish.totalWeightGrams().coerceAtLeast(100.0)
            )
        } + foods.filter { it.hasComparableNutrition() }.map { food ->
            PlanningCandidate(PlannedItemKind.FOOD, food.id, food.name, 100.0)
        }
    }
    var query by rememberSaveable { mutableStateOf("") }
    var editing by remember { mutableStateOf<PlanningRule?>(null) }

    editing?.let { rule ->
        val name = candidates.firstOrNull { it.kind == rule.itemKind && it.id == rule.itemId }?.name
            ?: "Elemento"
        PlanningRuleDialog(
            name = name,
            initial = rule,
            onSave = {
                onSaveRule(it)
                editing = null
            },
            onDelete = rules.any { it.itemKind == rule.itemKind && it.itemId == rule.itemId }
                .takeIf { it }
                ?.let {
                    {
                        onDeleteRule(rule.itemKind, rule.itemId)
                        editing = null
                    }
                },
            onDismiss = { editing = null }
        )
    }

    LazyColumn(
        contentPadding = PaddingValues(start = 16.dp, top = 12.dp, end = 16.dp, bottom = 48.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    HomeCardHeader("Tu repertorio", showArrow = false)
                    Text(
                        "Elige qué sueles comer y establece cuándo puede usarlo Rumbo. La generación se limita a comidas y cenas.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    if (rules.isEmpty()) {
                        Text(
                            "Añade suficientes alternativas para cubrir tanto comidas como cenas.",
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }
        }

        if (rules.isNotEmpty()) {
            item {
                Text(
                    "Elementos configurados",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
            }
            items(rules, key = { "rule_${it.itemKind}_${it.itemId}" }) { rule ->
                val candidate = candidates.firstOrNull {
                    it.kind == rule.itemKind && it.id == rule.itemId
                }
                Card(
                    Modifier.fillMaxWidth().clickable { editing = rule }
                ) {
                    Row(
                        Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Icon(
                            if (rule.itemKind == PlannedItemKind.DISH) Icons.Default.Restaurant
                            else foodCategoryIcon(foodsById[rule.itemId]?.category ?: FoodCategory.OTHER),
                            contentDescription = null
                        )
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                            Text(candidate?.name ?: "Elemento", style = MaterialTheme.typography.bodyLarge)
                            Text(
                                buildList {
                                    add(rule.allowedMealTypes.joinToString(" y ") { it.label.lowercase() })
                                    add(rule.frequency.label.lowercase())
                                    if (rule.fixedSlots.isNotEmpty()) {
                                        add("${rule.fixedSlots.size} huecos fijos")
                                    }
                                }.joinToString(" · "),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = "Editar")
                    }
                }
            }
        }

        item {
            Text(
                "Añadir al repertorio",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = query,
                onValueChange = { query = it.take(80) },
                label = { Text("Buscar alimento o plato") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
        }
        val configuredKeys = rules.mapTo(mutableSetOf()) { it.itemKind to it.itemId }
        val visible = candidates.asSequence()
            .filterNot { (it.kind to it.id) in configuredKeys }
            .filter { query.isBlank() || it.name.contains(query, ignoreCase = true) }
            .take(30)
            .toList()
        items(visible, key = { "candidate_${it.kind}_${it.id}" }) { candidate ->
            Row(
                Modifier
                    .fillMaxWidth()
                    .clickable {
                        editing = PlanningRule(
                            itemKind = candidate.kind,
                            itemId = candidate.id,
                            allowedMealTypes = setOf(MealType.LUNCH, MealType.DINNER),
                            frequency = PlanningFrequency.NORMAL,
                            preferredGrams = candidate.defaultGrams
                        )
                    }
                    .padding(horizontal = 8.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(candidate.name, modifier = Modifier.weight(1f))
                Icon(Icons.Default.Add, contentDescription = "Añadir")
            }
        }
    }
}

@Composable
private fun PlanningRuleDialog(
    name: String,
    initial: PlanningRule,
    onSave: (PlanningRule) -> Unit,
    onDelete: (() -> Unit)?,
    onDismiss: () -> Unit
) {
    var lunch by remember(initial) { mutableStateOf(MealType.LUNCH in initial.allowedMealTypes) }
    var dinner by remember(initial) { mutableStateOf(MealType.DINNER in initial.allowedMealTypes) }
    var frequency by remember(initial) { mutableStateOf(initial.frequency) }
    var preferred by rememberSaveable(initial) { mutableStateOf(formatDecimal(initial.preferredGrams)) }
    var minimum by rememberSaveable(initial) { mutableStateOf(formatDecimal(initial.minimumFactor)) }
    var maximum by rememberSaveable(initial) { mutableStateOf(formatDecimal(initial.maximumFactor)) }
    var fixedSlots by remember(initial) { mutableStateOf(initial.fixedSlots) }
    var error by remember { mutableStateOf<String?>(null) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(name, maxLines = 2, overflow = TextOverflow.Ellipsis) },
        text = {
            LazyColumn(
                Modifier.fillMaxWidth().heightIn(max = 540.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                item {
                    Text("Puede aparecer en", fontWeight = FontWeight.SemiBold)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(
                            selected = lunch,
                            onClick = {
                                lunch = !lunch
                                if (!lunch) fixedSlots = fixedSlots.filterNot {
                                    it.mealType == MealType.LUNCH
                                }.toSet()
                            },
                            label = { Text("Comida") }
                        )
                        FilterChip(
                            selected = dinner,
                            onClick = {
                                dinner = !dinner
                                if (!dinner) fixedSlots = fixedSlots.filterNot {
                                    it.mealType == MealType.DINNER
                                }.toSet()
                            },
                            label = { Text("Cena") }
                        )
                    }
                }
                item {
                    SelectorField(
                        label = "Aparición adicional",
                        selectedLabel = frequency.label,
                        options = PlanningFrequency.entries,
                        optionLabel = { it.label },
                        onSelect = { frequency = it },
                        onClear = null
                    )
                }
                item {
                    Text("Cantidad habitual y límites", fontWeight = FontWeight.SemiBold)
                    Text(
                        "Rumbo conservará las proporciones de los platos y moverá la ración dentro de estos factores.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(Modifier.height(6.dp))
                    NumericField("Cantidad habitual (g)", preferred, { preferred = it }, Modifier.fillMaxWidth())
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        NumericField("Mínimo ×", minimum, { minimum = it }, Modifier.weight(1f))
                        NumericField("Máximo ×", maximum, { maximum = it }, Modifier.weight(1f))
                    }
                }
                if (lunch) {
                    item {
                        FixedDayRow(
                            label = "Días fijos en la comida",
                            type = MealType.LUNCH,
                            selected = fixedSlots,
                            onChange = { fixedSlots = it }
                        )
                    }
                }
                if (dinner) {
                    item {
                        FixedDayRow(
                            label = "Días fijos en la cena",
                            type = MealType.DINNER,
                            selected = fixedSlots,
                            onChange = { fixedSlots = it }
                        )
                    }
                }
                error?.let { message ->
                    item { Text(message, color = MaterialTheme.colorScheme.error) }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                val allowed = buildSet {
                    if (lunch) add(MealType.LUNCH)
                    if (dinner) add(MealType.DINNER)
                }
                val draft = initial.copy(
                    allowedMealTypes = allowed,
                    fixedSlots = fixedSlots.filter { it.mealType in allowed }.toSet(),
                    frequency = frequency,
                    preferredGrams = parseDecimal(preferred) ?: 0.0,
                    minimumFactor = parseDecimal(minimum) ?: 0.0,
                    maximumFactor = parseDecimal(maximum) ?: 0.0
                )
                if (draft.isValid()) onSave(draft)
                else error = "Selecciona comida o cena y revisa la cantidad y los límites."
            }) { Text("Guardar") }
        },
        dismissButton = {
            Row {
                onDelete?.let {
                    TextButton(onClick = it) {
                        Text("Quitar", color = MaterialTheme.colorScheme.error)
                    }
                }
                TextButton(onClick = onDismiss) { Text("Cancelar") }
            }
        }
    )
}

@Composable
private fun FixedDayRow(
    label: String,
    type: MealType,
    selected: Set<PlanningSlot>,
    onChange: (Set<PlanningSlot>) -> Unit
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(label, fontWeight = FontWeight.SemiBold)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            WeekDay.entries.forEach { day ->
                val slot = PlanningSlot(day, type)
                FilterChip(
                    selected = slot in selected,
                    onClick = {
                        onChange(if (slot in selected) selected - slot else selected + slot)
                    },
                    label = { Text(day.shortLabel) },
                    modifier = Modifier.width(43.dp)
                )
            }
        }
    }
}


@Composable
private fun WeeklyPlannerScreen(
    meals: List<PlannedMeal>,
    planningRules: List<PlanningRule>,
    menuHistory: List<MenuHistoryEntry>,
    foods: List<Food>,
    dishes: List<Dish>,
    recommendation: es.david.rumbo.model.Recommendation?,
    mealShares: Map<MealType, Double>,
    initialWeek: PlanWeek,
    onWeekChange: (PlanWeek) -> Unit,
    onApplyGeneratedMenu: (es.david.rumbo.logic.GeneratedWeeklyMenu, PlanWeek) -> Unit,
    onOpenMeal: (Long, PlanWeek) -> Unit,
    onAddMissing: (MealType, WeekDay, PlanWeek) -> Unit,
    onApplyAdjustedMeals: (List<PlannedMeal>, PlanWeek) -> Unit
) {
    var selectedWeek by rememberSaveable { mutableStateOf(initialWeek) }
    val visibleMeals = remember(meals, selectedWeek) {
        meals.filter { it.planWeek == selectedWeek }
    }
    val foodsById = remember(foods) { foods.associateBy { it.id } }
    val dishesById = remember(dishes) { dishes.associateBy { it.id } }
    val assessments = remember(visibleMeals, foodsById, dishesById, recommendation) {
        recommendation?.let { target ->
            WeekDay.entries.associateWith { day ->
                MealPlanEvaluator.assessDay(day, visibleMeals, foodsById, dishesById, target)
            }
        }.orEmpty()
    }
    var optimizationPreview by remember { mutableStateOf<QuantityOptimizationResult?>(null) }
    var optimizationMessage by remember { mutableStateOf<String?>(null) }
    var generationMessage by remember { mutableStateOf<String?>(null) }

    generationMessage?.let { message ->
        AlertDialog(
            onDismissRequest = { generationMessage = null },
            title = { Text("Generar semana") },
            text = { Text(message) },
            confirmButton = {
                TextButton(onClick = { generationMessage = null }) { Text("Entendido") }
            }
        )
    }
    optimizationPreview?.let { result ->
        QuantityOptimizationPreviewDialog(
            result = result,
            onApply = {
                onApplyAdjustedMeals(result.meals, selectedWeek)
                optimizationPreview = null
            },
            onDismiss = { optimizationPreview = null }
        )
    }
    optimizationMessage?.let { message ->
        AlertDialog(
            onDismissRequest = { optimizationMessage = null },
            title = { Text("Ajustar cantidades") },
            text = { Text(message) },
            confirmButton = {
                TextButton(onClick = { optimizationMessage = null }) { Text("Entendido") }
            }
        )
    }

    LazyColumn(
        contentPadding = PaddingValues(start = 16.dp, top = 12.dp, end = 16.dp, bottom = 96.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                PlanWeek.entries.forEach { week ->
                    FilterChip(
                        selected = selectedWeek == week,
                        onClick = {
                            selectedWeek = week
                            onWeekChange(week)
                        },
                        label = { Text(week.label) },
                        modifier = Modifier.weight(1f)
                    )
                }
            }
        }
        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    HomeCardHeader("Valoración semanal", showArrow = false)
                    if (recommendation != null) {
                        WeeklyNutritionSummary(assessments.values.toList())
                    }
                    Text(
                        weeklyAssessmentText(assessments.values.toList(), recommendation),
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    OutlinedButton(
                        onClick = {
                            if (recommendation == null) {
                                generationMessage = "Necesitas una recomendación nutricional para generar la semana."
                            } else {
                                runCatching {
                                    WeeklyMenuGenerator.generate(
                                        currentMeals = visibleMeals,
                                        rules = planningRules,
                                        history = menuHistory,
                                        foodsById = foodsById,
                                        dishesById = dishesById,
                                        recommendation = recommendation,
                                        mealShares = mealShares
                                    )
                                }.onSuccess {
                                    onApplyGeneratedMenu(it, selectedWeek)
                                    generationMessage = "Semana generada. Se han respetado las comidas fijas y las frecuencias elegidas."
                                }.onFailure {
                                    generationMessage = it.message ?: "No se pudo generar una semana válida."
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) { Text(if (menuHistory.isEmpty()) "Generar menú semanal" else "Regenerar menú semanal") }
                    OutlinedButton(
                        onClick = {
                            if (recommendation == null) {
                                optimizationMessage =
                                    "Necesitas una recomendación nutricional antes de ajustar el plan."
                            } else {
                                val result = MealQuantityOptimizer.optimize(
                                    visibleMeals, foodsById, dishesById, recommendation
                                )
                                if (result.changes.isNotEmpty()) optimizationPreview = result
                                else optimizationMessage = if (result.days.isEmpty()) {
                                    "Completa al menos un día y marca uno o varios elementos como ajustables. Los elementos fijos nunca se modifican."
                                } else {
                                    "Las cantidades actuales ya son la mejor combinación encontrada dentro de los límites indicados."
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) { Text("Ajustar cantidades") }
                }
            }
        }

        items(WeekDay.entries, key = { "weekly_card_${it.name}" }) { day ->
            WeeklyDayCard(
                day = day,
                meals = visibleMeals,
                foodsById = foodsById,
                dishesById = dishesById,
                assessment = assessments[day],
                onOpenMeal = { onOpenMeal(it, selectedWeek) },
                onAddMissing = { type, day -> onAddMissing(type, day, selectedWeek) }
            )
        }
    }
}

@Composable
private fun WeeklyNutritionSummary(assessments: List<PlanNutritionAssessment>) {
    if (assessments.isEmpty()) return
    val actualCalories = assessments.sumOf { it.actual.calories }
    val targetCalories = assessments.sumOf { it.target.calories }
    val actualProtein = assessments.sumOf { it.actual.proteinGrams }
    val targetProtein = assessments.sumOf { it.target.proteinGrams }
    val actualCarbohydrates = assessments.sumOf { it.actual.carbohydrateGrams }
    val targetCarbohydrates = assessments.sumOf { it.target.carbohydrateGrams }
    val actualFat = assessments.sumOf { it.actual.fatGrams }
    val targetFat = assessments.sumOf { it.target.fatGrams }

    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        NutritionPercentMetric(
            "Calorías", actualCalories, targetCalories,
            Icons.Default.LocalFireDepartment, MaterialTheme.colorScheme.onSurface, Modifier.weight(1f)
        )
        NutritionPercentMetric(
            "Proteína", actualProtein, targetProtein,
            foodCategoryIcon(FoodCategory.PROTEIN), foodCategoryColor(FoodCategory.PROTEIN), Modifier.weight(1f)
        )
        NutritionPercentMetric(
            "Hidratos", actualCarbohydrates, targetCarbohydrates,
            foodCategoryIcon(FoodCategory.CARBOHYDRATE),
            foodCategoryColor(FoodCategory.CARBOHYDRATE),
            Modifier.weight(1f)
        )
        NutritionPercentMetric(
            "Grasa", actualFat, targetFat,
            foodCategoryIcon(FoodCategory.FAT), foodCategoryColor(FoodCategory.FAT), Modifier.weight(1f)
        )
    }
}

private fun weeklyAssessmentText(
    assessments: List<PlanNutritionAssessment>,
    recommendation: es.david.rumbo.model.Recommendation?
): String {
    if (recommendation == null) return "Añade una medición para poder valorar el menú semanal."
    if (assessments.isEmpty()) return "Todavía no hay días que se puedan valorar."
    val incompleteDays = assessments.count { it.missingMealTypes.isNotEmpty() }
    if (incompleteDays > 0) {
        return if (incompleteDays == 1) {
            "Falta completar un día de la semana antes de poder valorar el conjunto."
        } else {
            "Falta completar $incompleteDays días de la semana antes de poder valorar el conjunto."
        }
    }
    if (assessments.any { !it.actual.isComplete }) {
        return "Faltan datos nutricionales para valorar el menú semanal completo."
    }
    val nutrients = listOf(
        Triple("calorías", assessments.sumOf { it.actual.calories }, assessments.sumOf { it.target.calories }),
        Triple("proteína", assessments.sumOf { it.actual.proteinGrams }, assessments.sumOf { it.target.proteinGrams }),
        Triple(
            "hidratos",
            assessments.sumOf { it.actual.carbohydrateGrams },
            assessments.sumOf { it.target.carbohydrateGrams }
        ),
        Triple("grasa", assessments.sumOf { it.actual.fatGrams }, assessments.sumOf { it.target.fatGrams })
    )
    val below = nutrients.filter { (_, actual, target) -> target > 0.0 && actual < target * 0.90 }
        .map { it.first }
    val above = nutrients.filter { (_, actual, target) -> target > 0.0 && actual > target * 1.10 }
        .map { it.first }
    if (below.isEmpty() && above.isEmpty()) {
        return "El menú semanal está bien ajustado a tus objetivos."
    }
    return buildList {
        if (below.isNotEmpty()) add("Por debajo del objetivo semanal: ${below.joinToString()}.")
        if (above.isNotEmpty()) add("Por encima del objetivo semanal: ${above.joinToString()}.")
    }.joinToString(" ")
}

@Composable
private fun WeeklyDayCard(
    day: WeekDay,
    meals: List<PlannedMeal>,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    assessment: PlanNutritionAssessment?,
    onOpenMeal: (Long) -> Unit,
    onAddMissing: (MealType, WeekDay) -> Unit
) {
    val dayMeals = meals.filter { day in it.days }.associateBy { it.type }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            HomeCardHeader(day.label, showArrow = false)
            MealType.entries.forEachIndexed { index, type ->
                val meal = dayMeals[type]
                val entries = meal?.let {
                    it.dishes.mapNotNull { planned ->
                        dishesById[planned.dishId]?.let { dish ->
                            MenuItemLine(
                                dish.name,
                                it.resolvedGrams(planned, day),
                                dish.dominantCategory(foodsById),
                                locked = !planned.adjustable
                            )
                        }
                    } + it.items.mapNotNull { planned ->
                        foodsById[planned.foodId]?.let { food ->
                            MenuItemLine(
                                food.name,
                                it.resolvedGrams(planned, day),
                                food.category,
                                locked = !planned.adjustable
                            )
                        }
                    }
                }.orEmpty()
                Column(
                    Modifier.fillMaxWidth().padding(vertical = 5.dp),
                    verticalArrangement = Arrangement.spacedBy(9.dp)
                ) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            type.label,
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                    if (entries.isNotEmpty()) {
                        entries.forEach { entry ->
                            Row(
                                Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                SmallFoodCategoryBadge(entry.category)
                                Text(entry.name, modifier = Modifier.weight(1f))
                                if (entry.locked) {
                                    Icon(
                                        Icons.Default.Lock,
                                        contentDescription = "Cantidad fijada por ti",
                                        modifier = Modifier.size(17.dp),
                                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                Text(
                                    "${formatDecimal(entry.grams)} g",
                                    fontWeight = FontWeight.SemiBold,
                                    textAlign = TextAlign.End
                                )
                            }
                        }
                    }
                }
                if (index < MealType.entries.lastIndex) {
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                }
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            assessment?.let { TodayNutritionSummary(it) }
            Text(
                todayAssessmentText(assessment),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
        }
    }
}

@Composable
private fun QuantityOptimizationPreviewDialog(
    result: QuantityOptimizationResult,
    onApply: () -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Revisar ajuste") },
        text = {
            LazyColumn(
                Modifier.fillMaxWidth().heightIn(max = 520.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                item {
                    Text(
                        "Se mantienen intactas todas las cantidades fijas. Las ajustables se resuelven por separado para cada día.",
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
                result.days.forEach { summary ->
                    item(key = "summary_${summary.day.name}") {
                        Text(summary.day.label, fontWeight = FontWeight.Bold)
                        Text(
                            "${formatDecimal(summary.before.actual.calories)} → ${formatDecimal(summary.after.actual.calories)} kcal · " +
                                "P ${formatDecimal(summary.before.actual.proteinGrams)} → ${formatDecimal(summary.after.actual.proteinGrams)} g",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            "H ${formatDecimal(summary.before.actual.carbohydrateGrams)} → ${formatDecimal(summary.after.actual.carbohydrateGrams)} g · " +
                                "G ${formatDecimal(summary.before.actual.fatGrams)} → ${formatDecimal(summary.after.actual.fatGrams)} g",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    val dayChanges = result.changes.filter { it.day == summary.day }
                    items(dayChanges, key = { "${it.day.name}_${it.mealId}_${it.label}" }) { change ->
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(
                                "${change.mealType.label}: ${change.label}",
                                modifier = Modifier.weight(1f),
                                style = MaterialTheme.typography.bodySmall
                            )
                            Text(
                                "${formatDecimal(change.beforeGrams)} → ${formatDecimal(change.afterGrams)} g",
                                fontWeight = FontWeight.SemiBold,
                                style = MaterialTheme.typography.bodySmall
                            )
                        }
                    }
                    item(key = "divider_${summary.day.name}") { HorizontalDivider() }
                }
                item {
                    Text(
                        "Si no existe una combinación exacta, esta es la más próxima encontrada respetando los límites.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        },
        confirmButton = { Button(onClick = onApply) { Text("Aplicar") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } }
    )
}

@Composable
private fun DayNutritionEntry(
    day: WeekDay,
    meals: List<PlannedMeal>,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    recommendation: es.david.rumbo.model.Recommendation?,
    onClick: (() -> Unit)?
) {
    val assessment = recommendation?.let {
        MealPlanEvaluator.assessDay(day, meals, foodsById, dishesById, it)
    }
    val modifier = Modifier
        .fillMaxWidth()
        .then(if (onClick == null) Modifier else Modifier.clickable(onClick = onClick))
        .padding(vertical = 10.dp)
    Column(modifier, verticalArrangement = Arrangement.spacedBy(5.dp)) {
        if (onClick != null) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(day.label, modifier = Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                Text(
                    assessment?.overall?.fitLabel() ?: "Sin objetivo",
                    color = assessment?.overall?.fitColor() ?: MaterialTheme.colorScheme.onSurfaceVariant,
                    fontWeight = FontWeight.SemiBold,
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
        if (assessment == null) {
            Text(
                "No hay una recomendación calórica disponible.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodySmall
            )
        } else {
            NutritionTargetLine(assessment)
            if (onClick == null) {
                Text(
                    assessment.overall.fitLabel(),
                    color = assessment.overall.fitColor(),
                    fontWeight = FontWeight.SemiBold,
                    style = MaterialTheme.typography.bodyMedium
                )
            }
            if (assessment.missingMealTypes.isNotEmpty()) {
                Text(
                    "Faltan: ${assessment.missingMealTypes.joinToString { it.label.lowercase() }}.",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall
                )
            } else if (!assessment.actual.isComplete) {
                Text(
                    "Algún alimento no tiene todos los datos nutricionales.",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }
    }
}

@Composable
private fun NutritionTargetLine(assessment: PlanNutritionAssessment) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        NutrientComparison(
            label = "kcal",
            actual = assessment.actual.calories,
            target = assessment.target.calories,
            fit = assessment.fits.calories,
            modifier = Modifier.weight(1.25f)
        )
        NutrientComparison(
            label = "P",
            actual = assessment.actual.proteinGrams,
            target = assessment.target.proteinGrams,
            fit = assessment.fits.protein,
            modifier = Modifier.weight(1f)
        )
        NutrientComparison(
            label = "H",
            actual = assessment.actual.carbohydrateGrams,
            target = assessment.target.carbohydrateGrams,
            fit = assessment.fits.carbohydrates,
            modifier = Modifier.weight(1f)
        )
        NutrientComparison(
            label = "G",
            actual = assessment.actual.fatGrams,
            target = assessment.target.fatGrams,
            fit = assessment.fits.fat,
            modifier = Modifier.weight(1f)
        )
    }
}

@Composable
private fun NutrientComparison(
    label: String,
    actual: Double,
    target: Double,
    fit: TargetFit,
    modifier: Modifier = Modifier
) {
    Column(modifier) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            "${formatDecimal(actual)}/${formatDecimal(target)}",
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.SemiBold,
            color = fit.fitColor()
        )
    }
}

@Composable
private fun TargetFit.fitColor(): Color = when (this) {
    TargetFit.ON_TARGET -> Color(0xFF2E7D32)
    TargetFit.CLOSE -> Color(0xFF9A6700)
    TargetFit.OUTSIDE, TargetFit.INCOMPLETE -> MaterialTheme.colorScheme.error
}

private fun TargetFit.fitLabel(): String = when (this) {
    TargetFit.ON_TARGET -> "Dentro del objetivo"
    TargetFit.CLOSE -> "Cerca del objetivo"
    TargetFit.OUTSIDE -> "Fuera del objetivo"
    TargetFit.INCOMPLETE -> "Plan incompleto"
}

@Composable
private fun PlannedMealListEntry(
    meal: PlannedMeal,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    recommendation: es.david.rumbo.model.Recommendation?,
    showDays: Boolean,
    day: WeekDay?,
    onClick: () -> Unit
) {
    val totals = meal.nutrition(foodsById, dishesById, day)
    val assessment = recommendation?.let {
        MealPlanEvaluator.assessMeal(meal, foodsById, dishesById, it, day)
    }
    val days = WeekDay.entries.filter(meal.days::contains).joinToString(" · ") { it.shortLabel }
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            if (showDays) {
                Text(days, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            }
            meal.items.forEach { item ->
                val food = foodsById[item.foodId]
                Row(
                    Modifier.fillMaxWidth().padding(vertical = 2.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    if (food != null) {
                        SmallFoodCategoryBadge(food.category)
                    } else {
                        Spacer(Modifier.size(24.dp))
                    }
                    Text(
                        food?.name ?: "Alimento eliminado",
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Text(
                        plannedAmountLabel(meal, item, day),
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
            meal.dishes.forEach { plannedDish ->
                val dish = dishesById[plannedDish.dishId]
                Row(
                    Modifier.fillMaxWidth().padding(vertical = 2.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    if (dish != null) {
                        SmallFoodCategoryBadge(dish.dominantCategory(foodsById))
                    } else {
                        Spacer(Modifier.size(24.dp))
                    }
                    Text(
                        dish?.name ?: "Plato eliminado",
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    Text(
                        plannedAmountLabel(meal, plannedDish, day),
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
            if (assessment != null) {
                NutritionTargetLine(assessment)
                Text(
                    assessment.overall.fitLabel(),
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                    color = assessment.overall.fitColor()
                )
            } else {
                Text(
                    "P ${formatDecimal(totals.proteinGrams)} g · H ${formatDecimal(totals.carbohydrateGrams)} g · " +
                        "G ${formatDecimal(totals.fatGrams)} g",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        if (assessment == null) {
            Text(
                if (totals.isComplete) "${formatDecimal(totals.calories)}\nkcal" else "datos\nincompletos",
                textAlign = TextAlign.End,
                fontWeight = FontWeight.SemiBold,
                style = MaterialTheme.typography.bodyMedium
            )
        }
    }
}

private fun plannedAmountLabel(meal: PlannedMeal, item: PlannedFood, day: WeekDay?): String {
    if (day != null || !item.adjustable) return "${formatDecimal(meal.resolvedGrams(item, day))} g"
    val values = meal.days.map { meal.resolvedGrams(item, it) }
    return amountRangeLabel(values)
}

private fun plannedAmountLabel(meal: PlannedMeal, item: PlannedDish, day: WeekDay?): String {
    if (day != null || !item.adjustable) return "${formatDecimal(meal.resolvedGrams(item, day))} g"
    val values = meal.days.map { meal.resolvedGrams(item, it) }
    return amountRangeLabel(values)
}

private fun amountRangeLabel(values: List<Double>): String {
    val minimum = values.minOrNull() ?: 0.0
    val maximum = values.maxOrNull() ?: minimum
    return if (abs(maximum - minimum) < 0.5) "${formatDecimal(minimum)} g"
    else "${formatDecimal(minimum)}–${formatDecimal(maximum)} g"
}

private data class AmountDraft(
    val grams: String,
    val adjustable: Boolean = false,
    val minimum: String = "",
    val maximum: String = ""
)

private val amountDraftMapSaver: Saver<Map<Long, AmountDraft>, Any> = listSaver(
    save = { drafts ->
        drafts.flatMap { (id, draft) ->
            listOf(id.toString(), draft.grams, draft.adjustable, draft.minimum, draft.maximum)
        }
    },
    restore = { values ->
        values.chunked(5).associate { parts ->
            parts[0].toString().toLong() to AmountDraft(
                grams = parts[1].toString(),
                adjustable = parts[2] as Boolean,
                minimum = parts[3].toString(),
                maximum = parts[4].toString()
            )
        }
    }
)

private val weekDaySetSaver: Saver<Set<WeekDay>, Any> = listSaver(
    save = { days -> days.map { it.name } },
    restore = { values -> values.map { WeekDay.valueOf(it.toString()) }.toSet() }
)

private val longSetSaver: Saver<Set<Long>, Any> = listSaver(
    save = { values -> values.map { it.toString() } },
    restore = { values -> values.map { it.toString().toLong() }.toSet() }
)

private fun AmountDraft.toPlannedFood(foodId: Long): PlannedFood? {
    val amount = parseDecimal(grams) ?: return null
    val minimumAmount = if (adjustable) parseDecimal(minimum) ?: return null else amount * 0.5
    val maximumAmount = if (adjustable) parseDecimal(maximum) ?: return null else amount * 1.5
    return PlannedFood(foodId, amount, adjustable, minimumAmount, maximumAmount)
        .takeIf { it.isValid() }
}

private fun AmountDraft.toPlannedDish(dishId: Long): PlannedDish? {
    val amount = parseDecimal(grams) ?: return null
    val minimumAmount = if (adjustable) parseDecimal(minimum) ?: return null else amount * 0.5
    val maximumAmount = if (adjustable) parseDecimal(maximum) ?: return null else amount * 1.5
    return PlannedDish(dishId, amount, adjustable, minimumAmount, maximumAmount)
        .takeIf { it.isValid() }
}

private fun AmountDraft.withAdjustable(
    enabled: Boolean,
    divisor: Double = 2.0,
    multiplier: Double = 1.5
): AmountDraft {
    if (!enabled) return copy(adjustable = false)
    val amount = parseDecimal(grams) ?: 100.0
    return copy(
        adjustable = true,
        minimum = formatDecimal((amount / divisor.coerceAtLeast(1.0)).coerceAtLeast(0.1)),
        maximum = formatDecimal((amount * multiplier.coerceAtLeast(1.0)).coerceAtMost(5000.0))
    )
}

private fun adjustMealAmounts(
    itemAmounts: Map<Long, AmountDraft>,
    dishAmounts: Map<Long, AmountDraft>,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    targetCalories: Double
): Pair<Map<Long, AmountDraft>, Map<Long, AmountDraft>> {
    fun foodCalories(foodId: Long, grams: Double): Double =
        (foodsById[foodId]?.calories ?: 0.0) * grams / 100.0
    fun dishCalories(dishId: Long, grams: Double): Double =
        dishesById[dishId]?.nutritionForGrams(foodsById, grams)?.calories ?: 0.0

    val fixedCalories =
        itemAmounts.filterValues { !it.adjustable }.entries.sumOf { (id, draft) ->
            foodCalories(id, parseDecimal(draft.grams) ?: 0.0)
        } +
        dishAmounts.filterValues { !it.adjustable }.entries.sumOf { (id, draft) ->
            dishCalories(id, parseDecimal(draft.grams) ?: 0.0)
        }
    val adjustableCalories =
        itemAmounts.filterValues { it.adjustable }.entries.sumOf { (id, draft) ->
            foodCalories(id, parseDecimal(draft.grams) ?: 0.0)
        } +
        dishAmounts.filterValues { it.adjustable }.entries.sumOf { (id, draft) ->
            dishCalories(id, parseDecimal(draft.grams) ?: 0.0)
        }
    if (adjustableCalories <= 0.0) return itemAmounts to dishAmounts
    val factor = ((targetCalories - fixedCalories) / adjustableCalories).coerceAtLeast(0.0)

    fun adjusted(draft: AmountDraft): AmountDraft {
        if (!draft.adjustable) return draft
        val current = parseDecimal(draft.grams) ?: return draft
        val minimum = parseDecimal(draft.minimum) ?: current
        val maximum = parseDecimal(draft.maximum) ?: current
        return draft.copy(grams = formatDecimal((current * factor).coerceIn(minimum, maximum)))
    }
    return itemAmounts.mapValues { adjusted(it.value) } to
        dishAmounts.mapValues { adjusted(it.value) }
}

@Composable
private fun PlannedMealEditorScreen(
    foods: List<Food>,
    dishes: List<Dish>,
    existingMeals: List<PlannedMeal>,
    recommendation: es.david.rumbo.model.Recommendation?,
    mealShares: Map<MealType, Double>,
    adjustmentRange: Pair<Double, Double>,
    initial: PlannedMeal? = null,
    initialType: MealType? = null,
    initialPlanWeek: PlanWeek = PlanWeek.CURRENT,
    initialDays: Set<WeekDay> = emptySet(),
    initialFoodId: Long? = null,
    initialDishId: Long? = null,
    preferredFoodIds: Set<Long>,
    preferredDishIds: Set<Long>,
    onCreateDish: (Dish) -> Unit,
    onOpenFood: (Long) -> Unit,
    onOpenDish: (Long) -> Unit,
    onSave: (PlannedMeal) -> Unit,
    onDelete: (() -> Unit)? = null
) {
    var type by rememberSaveable(initial?.id, initialType) {
        mutableStateOf(initial?.type ?: initialType ?: MealType.BREAKFAST)
    }
    var selectedDays by rememberSaveable(initial?.id, initialDays, stateSaver = weekDaySetSaver) {
        mutableStateOf(initial?.days ?: initialDays)
    }
    var itemAmounts by rememberSaveable(initial?.id, stateSaver = amountDraftMapSaver) {
        mutableStateOf(initial?.items?.associate {
            it.foodId to AmountDraft(
                formatDecimal(it.grams), it.adjustable,
                formatDecimal(it.minimumGrams), formatDecimal(it.maximumGrams)
            )
        }.orEmpty().ifEmpty {
            initialFoodId?.let { mapOf(it to AmountDraft("100")) }.orEmpty()
        })
    }
    var dishAmounts by rememberSaveable(initial?.id, stateSaver = amountDraftMapSaver) {
        mutableStateOf(initial?.dishes?.associate {
            it.dishId to AmountDraft(
                formatDecimal(it.grams), it.adjustable,
                formatDecimal(it.minimumGrams), formatDecimal(it.maximumGrams)
            )
        }.orEmpty().ifEmpty {
            initialDishId?.let { mapOf(it to AmountDraft("100")) }.orEmpty()
        })
    }
    var choosingElement by remember { mutableStateOf(false) }
    var selectedForDish by rememberSaveable(stateSaver = longSetSaver) { mutableStateOf(emptySet<Long>()) }
    var expandedFoodMenuId by remember { mutableStateOf<Long?>(null) }
    var expandedDishMenuId by remember { mutableStateOf<Long?>(null) }
    var replacingFoodId by remember { mutableStateOf<Long?>(null) }
    var namingDish by remember { mutableStateOf(false) }
    var newDishName by remember { mutableStateOf("") }
    var confirmDelete by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val foodsById = remember(foods) { foods.associateBy { it.id } }
    val dishesById = remember(dishes) { dishes.associateBy { it.id } }
    val planWeek = initial?.planWeek ?: initialPlanWeek
    val occupiedDays = existingMeals.asSequence()
        .filter {
            it.id != initial?.id && it.planWeek == planWeek && it.type == type
        }
        .flatMap { it.days.asSequence() }
        .toSet()
    val previewItems = itemAmounts.mapNotNull { (foodId, draft) -> draft.toPlannedFood(foodId) }
    val previewDishes = dishAmounts.mapNotNull { (dishId, draft) -> draft.toPlannedDish(dishId) }
    val previewAssessment = if (
        recommendation != null && (previewItems.isNotEmpty() || previewDishes.isNotEmpty()) &&
        previewItems.size == itemAmounts.size && previewDishes.size == dishAmounts.size
    ) {
        MealPlanEvaluator.assessMeal(
            PlannedMeal(
                id = initial?.id ?: 1L,
                type = type,
                planWeek = planWeek,
                days = selectedDays.ifEmpty { setOf(WeekDay.MONDAY) },
                items = previewItems,
                dishes = previewDishes
            ),
            foodsById,
            dishesById,
            recommendation,
            mealShare = mealShares[type] ?: 0.20
        )
    } else {
        null
    }

    if (choosingElement) {
        MealItemPickerDialog(
            foods = foods,
            dishes = dishes,
            excludedFoodIds = itemAmounts.keys,
            excludedDishIds = dishAmounts.keys,
            preferredFoodIds = preferredFoodIds,
            preferredDishIds = preferredDishIds,
            onChooseFood = {
                itemAmounts = itemAmounts + (it to AmountDraft("100"))
                choosingElement = false
            },
            onChooseDish = {
                val recipeWeight = dishesById[it]?.totalWeightGrams() ?: 100.0
                dishAmounts = dishAmounts + (it to AmountDraft(formatDecimal(recipeWeight)))
                choosingElement = false
            },
            onDismiss = { choosingElement = false }
        )
    }
    replacingFoodId?.let { sourceId ->
        foodsById[sourceId]?.let { source ->
            SimilarFoodReplacementDialog(
                source = source,
                foods = foods,
                excludedFoodIds = itemAmounts.keys,
                onChoose = { replacementId ->
                    val draft = itemAmounts[sourceId] ?: AmountDraft("100")
                    itemAmounts = (itemAmounts - sourceId) + (replacementId to draft)
                    selectedForDish = selectedForDish - sourceId
                    replacingFoodId = null
                },
                onDismiss = { replacingFoodId = null }
            )
        }
    }
    if (namingDish) {
        AlertDialog(
            onDismissRequest = { namingDish = false },
            title = { Text("Crear plato") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Los alimentos seleccionados se sustituirán por un único plato con el mismo peso total.")
                    OutlinedTextField(
                        value = newDishName,
                        onValueChange = { newDishName = it.take(80) },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("Nombre del plato") },
                        singleLine = true
                    )
                }
            },
            confirmButton = {
                TextButton(
                    enabled = newDishName.isNotBlank() &&
                        selectedForDish.size >= 2 &&
                        selectedForDish.all { foodId ->
                            itemAmounts[foodId]?.toPlannedFood(foodId) != null
                        },
                    onClick = {
                        val ingredients = selectedForDish.mapNotNull { foodId ->
                            itemAmounts[foodId]?.toPlannedFood(foodId)?.let { DishIngredient(foodId, it.grams) }
                        }
                        if (ingredients.size == selectedForDish.size && ingredients.size >= 2) {
                            val dish = Dish(System.currentTimeMillis(), newDishName.trim(), ingredients)
                            itemAmounts = itemAmounts - selectedForDish
                            dishAmounts = dishAmounts +
                                (dish.id to AmountDraft(formatDecimal(dish.totalWeightGrams())))
                            selectedForDish = emptySet()
                            newDishName = ""
                            namingDish = false
                            onCreateDish(dish)
                        }
                    }
                ) { Text("Crear") }
            },
            dismissButton = { TextButton(onClick = { namingDish = false }) { Text("Cancelar") } }
        )
    }
    if (confirmDelete && onDelete != null) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("¿Eliminar esta comida?") },
            text = { Text("Se quitará de todos los días a los que está asignada.") },
            confirmButton = {
                TextButton(onClick = onDelete) { Text("Eliminar", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancelar") } }
        )
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Box(Modifier.fillMaxWidth()) {
                    OutlinedButton(onClick = { expandedFoodMenuId = Long.MIN_VALUE }, modifier = Modifier.fillMaxWidth()) {
                        Text(type.label, modifier = Modifier.weight(1f))
                        Icon(Icons.Default.ArrowDropDown, contentDescription = null)
                    }
                    DropdownMenu(
                        expanded = expandedFoodMenuId == Long.MIN_VALUE,
                        onDismissRequest = { expandedFoodMenuId = null }
                    ) {
                        MealType.entries.forEach { newType ->
                            DropdownMenuItem(
                                text = { Text(newType.label) },
                                onClick = {
                                    type = newType
                                    val unavailable = existingMeals.asSequence()
                                        .filter { it.id != initial?.id && it.type == newType }
                                        .flatMap { it.days.asSequence() }.toSet()
                                    selectedDays = selectedDays - unavailable
                                    expandedFoodMenuId = null
                                }
                            )
                        }
                    }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    WeekDay.entries.forEach { day ->
                        FilterChip(
                            selected = day in selectedDays,
                            onClick = {
                                selectedDays = if (day in selectedDays) selectedDays - day else selectedDays + day
                            },
                            enabled = day !in occupiedDays,
                            label = { Text(day.shortLabel) },
                            colors = FilterChipDefaults.filterChipColors(
                                containerColor = MaterialTheme.colorScheme.surfaceContainerHigh,
                                selectedContainerColor = MaterialTheme.colorScheme.outlineVariant,
                                labelColor = MaterialTheme.colorScheme.onSurface,
                                selectedLabelColor = MaterialTheme.colorScheme.onSurface
                            ),
                            modifier = Modifier.weight(1f)
                        )
                    }
                }
                if (occupiedDays.isNotEmpty()) {
                    Text(
                        "Los días desactivados ya tienen ${type.label.lowercase()}.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                previewAssessment?.let { assessment ->
                    HorizontalDivider(Modifier.padding(top = 4.dp))
                    TodayNutritionSummary(assessment)
                    Text(
                        assessment.overall.fitLabel(),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    OutlinedButton(
                        onClick = {
                            if (itemAmounts.values.none { it.adjustable } &&
                                dishAmounts.values.none { it.adjustable }
                            ) {
                                error = "Permite ajustar al menos un elemento desde su menú de opciones."
                            } else {
                                val adjusted = adjustMealAmounts(
                                    itemAmounts,
                                    dishAmounts,
                                    foodsById,
                                    dishesById,
                                    assessment.target.calories
                                )
                                itemAmounts = adjusted.first
                                dishAmounts = adjusted.second
                                error = null
                            }
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) { Text("Ajustar cantidades") }
                }
            }
        }
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Alimentos y platos", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        dishAmounts.forEach { (dishId, draft) ->
            val dish = dishesById[dishId] ?: return@forEach
            Column {
                Row(
                    Modifier.fillMaxWidth().padding(start = 12.dp, top = 6.dp, bottom = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Column(
                        Modifier.weight(1f).clickable { onOpenDish(dishId) },
                        verticalArrangement = Arrangement.spacedBy(3.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            SmallFoodCategoryBadge(dish.dominantCategory(foodsById))
                            if (!draft.adjustable) {
                                Icon(
                                    Icons.Default.Lock,
                                    contentDescription = "Cantidad fija",
                                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                            Text(
                                dish.name,
                                modifier = Modifier.weight(1f),
                                style = MaterialTheme.typography.bodyLarge,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                        val grams = parseDecimal(draft.grams)
                        val calories = grams?.let { dish.nutritionForGrams(foodsById, it).calories }
                        Text(
                            calories?.let { "${formatDecimal(it)} kcal en esta cantidad" }
                                ?: "Introduce una cantidad",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    CompactGramField(draft.grams) {
                        dishAmounts = dishAmounts + (dishId to draft.copy(grams = it))
                    }
                    Box {
                        IconButton(onClick = { expandedDishMenuId = dishId }) {
                            Icon(Icons.Default.MoreVert, contentDescription = "Opciones de ${dish.name}")
                        }
                        DropdownMenu(
                            expanded = expandedDishMenuId == dishId,
                            onDismissRequest = { expandedDishMenuId = null }
                        ) {
                            DropdownMenuItem(
                                text = { Text(if (draft.adjustable) "Dejar cantidad fija" else "Permitir ajuste automático") },
                                onClick = {
                                    dishAmounts = dishAmounts + (dishId to draft.withAdjustable(
                                            !draft.adjustable,
                                            adjustmentRange.first,
                                            adjustmentRange.second
                                        ))
                                    expandedDishMenuId = null
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("Quitar") },
                                onClick = {
                                    dishAmounts = dishAmounts - dishId
                                    expandedDishMenuId = null
                                }
                            )
                        }
                    }
                }
                if (itemAmounts.isNotEmpty() || dishId != dishAmounts.keys.lastOrNull()) {
                    HorizontalDivider()
                }
            }
        }
        itemAmounts.forEach { (foodId, draft) ->
            val food = foodsById[foodId] ?: return@forEach
            Column {
                Row(
                    Modifier.fillMaxWidth().padding(start = 12.dp, top = 6.dp, bottom = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Column(
                        Modifier.weight(1f).clickable { onOpenFood(foodId) },
                        verticalArrangement = Arrangement.spacedBy(3.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            SmallFoodCategoryBadge(food.category)
                            if (!draft.adjustable) {
                                Icon(
                                    Icons.Default.Lock,
                                    contentDescription = "Cantidad fija",
                                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                            Text(
                                food.name,
                                modifier = Modifier.weight(1f),
                                style = MaterialTheme.typography.bodyLarge,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                            if (foodId in selectedForDish) {
                                Icon(
                                    Icons.Default.Check,
                                    contentDescription = "Seleccionado para crear plato",
                                    tint = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                        }
                        val grams = parseDecimal(draft.grams)
                        val calories = grams?.let { amount -> food.calories?.times(amount)?.div(100.0) }
                        Text(
                            calories?.let { "${formatDecimal(it)} kcal en esta cantidad" }
                                ?: "Introduce una cantidad",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                    CompactGramField(draft.grams) {
                        itemAmounts = itemAmounts + (foodId to draft.copy(grams = it))
                    }
                    Box {
                        IconButton(onClick = { expandedFoodMenuId = foodId }) {
                            Icon(Icons.Default.MoreVert, contentDescription = "Opciones de ${food.name}")
                        }
                        DropdownMenu(
                            expanded = expandedFoodMenuId == foodId,
                            onDismissRequest = { expandedFoodMenuId = null }
                        ) {
                            DropdownMenuItem(
                                text = { Text(if (draft.adjustable) "Dejar cantidad fija" else "Permitir ajuste automático") },
                                onClick = {
                                    itemAmounts = itemAmounts + (foodId to draft.withAdjustable(
                                            !draft.adjustable,
                                            adjustmentRange.first,
                                            adjustmentRange.second
                                        ))
                                    expandedFoodMenuId = null
                                }
                            )
                            DropdownMenuItem(
                                text = {
                                    Text(
                                        if (foodId in selectedForDish) "No usar para crear plato"
                                        else "Seleccionar para crear plato"
                                    )
                                },
                                onClick = {
                                    selectedForDish = if (foodId in selectedForDish) {
                                        selectedForDish - foodId
                                    } else selectedForDish + foodId
                                    expandedFoodMenuId = null
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("Sustituir por uno similar") },
                                onClick = {
                                    replacingFoodId = foodId
                                    expandedFoodMenuId = null
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("Quitar") },
                                onClick = {
                                    itemAmounts = itemAmounts - foodId
                                    selectedForDish = selectedForDish - foodId
                                    expandedFoodMenuId = null
                                }
                            )
                        }
                    }
                }
                if (foodId != itemAmounts.keys.lastOrNull()) {
                    HorizontalDivider()
                }
            }
        }
        OutlinedButton(onClick = { choosingElement = true }, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Default.Add, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("Añadir")
        }
            }
        }
        if (selectedForDish.size >= 2) {
            FilledTonalButton(
                onClick = {
                    newDishName = ""
                    namingDish = true
                },
                modifier = Modifier.fillMaxWidth()
            ) { Text("Crear plato con ${selectedForDish.size} alimentos") }
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        OutlinedButton(
            onClick = {
                val parsedItems = itemAmounts.mapNotNull { (foodId, draft) -> draft.toPlannedFood(foodId) }
                val parsedDishes = dishAmounts.mapNotNull { (dishId, draft) -> draft.toPlannedDish(dishId) }
                error = when {
                    selectedDays.isEmpty() -> "Selecciona al menos un día."
                    itemAmounts.isEmpty() && dishAmounts.isEmpty() -> "Añade al menos un alimento o un plato."
                    parsedItems.size != itemAmounts.size ->
                        "Revisa gramos, mínimo y máximo de los ingredientes ajustables."
                    parsedDishes.size != dishAmounts.size ->
                        "Revisa gramos, mínimo y máximo de los platos ajustables."
                    selectedDays.any(occupiedDays::contains) ->
                        "Ya existe otra comida del mismo tipo en alguno de esos días."
                    else -> null
                }
                if (error == null) {
                    onSave(
                        PlannedMeal(
                            id = initial?.id ?: System.currentTimeMillis(),
                            type = type,
                            planWeek = planWeek,
                            days = selectedDays,
                            items = parsedItems,
                            dishes = parsedDishes,
                            dayAmounts = initial?.dayAmounts.orEmpty()
                        ).sanitizedDayAmounts()
                    )
                }
            },
            modifier = Modifier.weight(1f)
        ) { Text("Guardar") }
        if (onDelete != null) {
            OutlinedButton(onClick = { confirmDelete = true }, modifier = Modifier.weight(1f)) {
                Text("Eliminar")
            }
        }
        }
    }
}

@Composable
private fun SimilarFoodReplacementDialog(
    source: Food,
    foods: List<Food>,
    excludedFoodIds: Set<Long>,
    onChoose: (Long) -> Unit,
    onDismiss: () -> Unit
) {
    val similar = remember(source, foods, excludedFoodIds) {
        FoodSimilarityEngine.findSimilar(source, foods, limit = 20)
            .filterNot { it.id in excludedFoodIds }
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Sustituir ${source.name}") },
        text = {
            if (similar.isEmpty()) {
                Text("No se ha encontrado ningún alimento suficientemente similar.")
            } else {
                LazyColumn(Modifier.fillMaxWidth().heightIn(max = 420.dp)) {
                    items(similar, key = { it.id }) { food ->
                        Row(
                            Modifier.fillMaxWidth().clickable { onChoose(food.id) }.padding(vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(food.name, modifier = Modifier.weight(1f))
                        }
                        HorizontalDivider()
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } }
    )
}

@Composable
private fun FoodPickerDialog(
    foods: List<Food>,
    excludedFoodIds: Set<Long>,
    preferredFoodIds: Set<Long>,
    onChoose: (Long) -> Unit,
    onDismiss: () -> Unit
) {
    var query by remember { mutableStateOf("") }
    val normalized = normalizeSearch(query)
    val index = remember(foods) { foods.map { IndexedFood(it, normalizeSearch(it.name)) } }
    val results = remember(index, excludedFoodIds, preferredFoodIds, normalized) {
        index.asSequence()
            .filterNot { it.food.id in excludedFoodIds }
            .filter { indexed ->
                when {
                    normalized.isBlank() -> indexed.food.id in preferredFoodIds
                    normalized.length < 2 -> indexed.food.id in preferredFoodIds &&
                        indexed.searchText.contains(normalized)
                    else -> indexed.searchText.contains(normalized)
                }
            }
            .sortedWith(
                compareBy<IndexedFood> { it.food.id !in preferredFoodIds }
                    .thenBy { it.food.name.lowercase() }
            )
            .map { it.food }
            .take(50)
            .toList()
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Añadir ingrediente") },
        text = {
            Column(Modifier.fillMaxWidth().heightIn(max = 520.dp)) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Buscar alimento") },
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                    singleLine = true
                )
                Spacer(Modifier.height(8.dp))
                if (normalized.length < 2) {
                    Text(
                        "Usados anteriormente; escribe dos caracteres para buscar en todo el catálogo.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                LazyColumn(Modifier.heightIn(max = 400.dp)) {
                    items(results, key = { it.id }) { food ->
                        Row(
                            Modifier.fillMaxWidth().clickable { onChoose(food.id) }.padding(vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            FoodCategoryBadge(food.category)
                            Text(food.name, modifier = Modifier.weight(1f))
                        }
                        HorizontalDivider()
                    }
                    if (results.isEmpty() && normalized.length >= 2) {
                        item { Text("No hay resultados.", modifier = Modifier.padding(vertical = 16.dp)) }
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Cerrar") } }
    )
}

private data class MealPickerResult(
    val id: Long,
    val name: String,
    val category: FoodCategory? = null,
    val isDish: Boolean = false,
    val preferred: Boolean = false
)

@Composable
private fun MealItemPickerDialog(
    foods: List<Food>,
    dishes: List<Dish>,
    excludedFoodIds: Set<Long>,
    excludedDishIds: Set<Long>,
    preferredFoodIds: Set<Long>,
    preferredDishIds: Set<Long>,
    onChooseFood: (Long) -> Unit,
    onChooseDish: (Long) -> Unit,
    onDismiss: () -> Unit
) {
    var query by remember { mutableStateOf("") }
    val normalized = normalizeSearch(query)
    val foodsById = remember(foods) { foods.associateBy { it.id } }
    val foodIndex = remember(foods) { foods.map { IndexedFood(it, normalizeSearch(it.name)) } }
    val results = remember(
        foodIndex, dishes, excludedFoodIds, excludedDishIds,
        preferredFoodIds, preferredDishIds, normalized, foodsById
    ) {
        val dishResults = dishes.asSequence()
            .filterNot { it.id in excludedDishIds }
            .filter { normalized.isBlank() || normalizeSearch(it.name).contains(normalized) }
            .map {
                MealPickerResult(
                    it.id, it.name, category = it.dominantCategory(foodsById),
                    isDish = true, preferred = it.id in preferredDishIds
                )
            }
        val foodResults = foodIndex.asSequence()
            .filterNot { it.food.id in excludedFoodIds }
            .filter {
                when {
                    normalized.isBlank() -> it.food.id in preferredFoodIds
                    normalized.length < 2 -> it.food.id in preferredFoodIds &&
                        it.searchText.contains(normalized)
                    else -> it.searchText.contains(normalized)
                }
            }
            .map {
                MealPickerResult(
                    it.food.id, it.food.name, category = it.food.category,
                    preferred = it.food.id in preferredFoodIds
                )
            }
        (dishResults + foodResults)
            .sortedWith(compareBy<MealPickerResult> { !it.preferred }.thenBy { it.name.lowercase() })
            .take(50).toList()
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Añadir a la comida") },
        text = {
            Column(Modifier.fillMaxWidth().heightIn(max = 520.dp)) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Buscar platos o alimentos") },
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                    singleLine = true
                )
                Spacer(Modifier.height(8.dp))
                if (normalized.length < 2) {
                    Text(
                        "Usados anteriormente primero; escribe dos caracteres para buscar en todo el catálogo.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                LazyColumn(Modifier.heightIn(max = 400.dp)) {
                        items(results, key = { "meal_picker_${it.isDish}_${it.id}" }) { result ->
                            Row(
                                Modifier.fillMaxWidth().clickable {
                                    if (result.isDish) onChooseDish(result.id) else onChooseFood(result.id)
                                }.padding(vertical = 10.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(10.dp)
                            ) {
                                result.category?.let { SmallFoodCategoryBadge(it) }
                                Column(Modifier.weight(1f)) {
                                    Text(result.name)
                                    Text(
                                        if (result.isDish) "Plato" else "Alimento",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                            HorizontalDivider()
                        }
                        if (results.isEmpty() && normalized.length >= 2) {
                            item { Text("No hay resultados.", modifier = Modifier.padding(vertical = 16.dp)) }
                        }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Cerrar") } }
    )
}

private enum class CatalogFilter { ALL, FOODS, DISHES }

private data class CatalogEntry(
    val id: Long,
    val name: String,
    val isDish: Boolean
)

@Composable
private fun FoodDishCatalogScreen(
    foods: List<Food>,
    dishes: List<Dish>,
    onOpenFood: (Long) -> Unit,
    onOpenDish: (Long) -> Unit,
    onAddFood: () -> Unit,
    onAddDish: () -> Unit
) {
    var query by rememberSaveable { mutableStateOf("") }
    var normalizedQuery by remember { mutableStateOf("") }
    var filter by rememberSaveable { mutableStateOf(CatalogFilter.ALL) }
    var addMenuExpanded by remember { mutableStateOf(false) }
    val foodsById = remember(foods) { foods.associateBy { it.id } }

    LaunchedEffect(query) {
        if (query.isNotBlank()) delay(200)
        normalizedQuery = normalizeSearch(query)
    }

    val entries = remember(foods, dishes, normalizedQuery, filter) {
        buildList {
            if (filter != CatalogFilter.DISHES) {
                foods.forEach { food ->
                    val searchable = normalizeSearch(
                        listOfNotNull(
                            food.name, food.category.label, food.brand, food.family,
                            food.subcategory, food.retailer, food.barcode
                        ).joinToString(" ")
                    )
                    if (normalizedQuery.isBlank() || searchable.contains(normalizedQuery)) {
                        add(CatalogEntry(food.id, food.name, false))
                    }
                }
            }
            if (filter != CatalogFilter.FOODS) {
                dishes.forEach { dish ->
                    val ingredientNames = dish.ingredients.mapNotNull { foodsById[it.foodId]?.name }
                    val searchable = normalizeSearch(
                        (listOf(dish.name) + ingredientNames).joinToString(" ")
                    )
                    if (normalizedQuery.isBlank() || searchable.contains(normalizedQuery)) {
                        add(CatalogEntry(dish.id, dish.name, true))
                    }
                }
            }
        }.sortedWith(compareBy<CatalogEntry> { it.name.lowercase() }.thenBy { it.isDish })
    }

    LazyColumn(
        contentPadding = PaddingValues(start = 20.dp, top = 16.dp, end = 20.dp, bottom = 32.dp)
    ) {
        item {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("Buscar alimentos y platos") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                singleLine = true
            )
            Spacer(Modifier.height(8.dp))
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                listOf(
                    CatalogFilter.ALL to "Todos",
                    CatalogFilter.FOODS to "Alimentos",
                    CatalogFilter.DISHES to "Platos"
                ).forEach { (option, label) ->
                    FilterChip(
                        selected = filter == option,
                        onClick = { filter = option },
                        label = { Text(label) }
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            Box {
                FilledTonalButton(
                    onClick = { addMenuExpanded = true },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Icon(Icons.Default.Add, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Añadir")
                }
                DropdownMenu(
                    expanded = addMenuExpanded,
                    onDismissRequest = { addMenuExpanded = false }
                ) {
                    DropdownMenuItem(
                        text = { Text("Añadir alimento") },
                        onClick = {
                            addMenuExpanded = false
                            onAddFood()
                        }
                    )
                    DropdownMenuItem(
                        text = { Text("Crear plato") },
                        onClick = {
                            addMenuExpanded = false
                            onAddDish()
                        }
                    )
                }
            }
            Spacer(Modifier.height(12.dp))
        }

        items(entries, key = { "${if (it.isDish) "dish" else "food"}_${it.id}" }) { entry ->
            if (entry.isDish) {
                val dish = dishes.firstOrNull { it.id == entry.id } ?: return@items
                val totals = dish.nutrition(foodsById)
                Row(
                    Modifier
                        .fillMaxWidth()
                        .clickable { onOpenDish(dish.id) }
                        .padding(vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    SmallFoodCategoryBadge(dish.dominantCategory(foodsById))
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                        Text(dish.name, style = MaterialTheme.typography.bodyLarge)
                        Text(
                            "${dish.ingredients.size} ingredientes · Plato",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    Text(
                        if (totals.isComplete) "${formatDecimal(totals.calories)}\nkcal"
                        else "datos\nincompletos",
                        textAlign = TextAlign.End,
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            } else {
                val food = foodsById[entry.id] ?: return@items
                FoodListEntry(food = food, onClick = { onOpenFood(food.id) })
            }
            if (entry != entries.lastOrNull()) HorizontalDivider()
        }

        if (entries.isEmpty()) {
            item {
                Text(
                    if (foods.isEmpty() && dishes.isEmpty()) {
                        "Todavía no hay alimentos ni platos."
                    } else {
                        "No hay resultados con estos criterios."
                    },
                    modifier = Modifier.padding(vertical = 24.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun DishesScreen(
    dishes: List<Dish>,
    foods: List<Food>,
    onOpenDish: (Long) -> Unit
) {
    val foodsById = remember(foods) { foods.associateBy { it.id } }
    LazyColumn(
        contentPadding = PaddingValues(start = 20.dp, top = 16.dp, end = 20.dp, bottom = 96.dp)
    ) {
        item {
            Text("Platos", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(6.dp))
            Text(
                "Combinaciones reutilizables por gramos, disponibles para todos los perfiles.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium
            )
            Spacer(Modifier.height(12.dp))
        }
        items(dishes.sortedBy { it.name.lowercase() }, key = { it.id }) { dish ->
            val totals = dish.nutrition(foodsById)
            Row(
                Modifier.fillMaxWidth().clickable { onOpenDish(dish.id) }.padding(vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                SmallFoodCategoryBadge(dish.dominantCategory(foodsById))
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(dish.name, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyLarge)
                    Text(
                        "${dish.ingredients.size} ingredientes · P ${formatDecimal(totals.proteinGrams)} · " +
                            "H ${formatDecimal(totals.carbohydrateGrams)} · G ${formatDecimal(totals.fatGrams)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Text(
                    if (totals.isComplete) "${formatDecimal(totals.calories)}\nkcal" else "datos\nincompletos",
                    textAlign = TextAlign.End,
                    fontWeight = FontWeight.SemiBold
                )
            }
            HorizontalDivider()
        }
        if (dishes.isEmpty()) {
            item {
                Text(
                    "Todavía no hay platos. Pulsa + para crear el primero.",
                    modifier = Modifier.padding(vertical = 24.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun DishDetailScreen(
    dish: Dish,
    foods: List<Food>,
    plannedMeals: List<PlannedMeal>,
    onOpenFood: (Long) -> Unit,
    onOpenMeal: (Long) -> Unit,
    onAddToMeal: (Long) -> Unit,
    onAddNewMeal: () -> Unit,
    planningRule: PlanningRule?,
    onSavePlanningRule: (PlanningRule) -> Unit,
    onDeletePlanningRule: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    var confirmDelete by remember { mutableStateOf(false) }
    val foodsById = remember(foods) { foods.associateBy { it.id } }
    val totals = dish.nutrition(foodsById)
    val totalWeight = dish.totalWeightGrams()
    val per100Factor = if (totalWeight > 0.0) 100.0 / totalWeight else 0.0
    val category = dish.dominantCategory(foodsById)
    val menuUsages = remember(dish.id, plannedMeals) {
        plannedMeals.filter { it.planWeek == PlanWeek.CURRENT }.mapNotNull { meal ->
            val amounts = meal.days.map { day ->
                meal.dishes.filter { it.dishId == dish.id }.sumOf { meal.resolvedGrams(it, day) }
            }
            if (amounts.any { it > 0.0 }) {
                Triple(
                    meal.id,
                    "${meal.type.label} · ${meal.days.joinToString { it.shortLabel }}",
                    amountRangeLabel(amounts)
                )
            } else null
        }
    }
    val nextMenuUsages = remember(dish.id, plannedMeals) {
        plannedMeals.filter { it.planWeek == PlanWeek.NEXT }.mapNotNull { meal ->
            val amounts = meal.days.map { day ->
                meal.dishes.filter { it.dishId == dish.id }.sumOf { meal.resolvedGrams(it, day) }
            }
            if (amounts.any { it > 0.0 }) {
                Triple(
                    meal.id,
                    "${meal.type.label} · ${meal.days.joinToString { it.shortLabel }}",
                    amountRangeLabel(amounts)
                )
            } else null
        }
    }

    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("¿Eliminar ${dish.name}?") },
            text = { Text("También se quitará de las comidas planificadas que lo utilicen.") },
            confirmButton = {
                TextButton(onClick = onDelete) { Text("Eliminar", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { confirmDelete = false }) { Text("Cancelar") }
            }
        )
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    FoodCategoryBadge(category)
                    Column(Modifier.weight(1f)) {
                        Text(dish.name, style = MaterialTheme.typography.headlineSmall)
                        Text(
                            "${dish.ingredients.size} ingredientes · ${formatDecimal(totalWeight)} g en total",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
                HorizontalDivider()
                Text("Plato completo", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(
                    "${formatDecimal(totals.calories)} kcal",
                    style = MaterialTheme.typography.headlineLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                    fontWeight = FontWeight.SemiBold
                )
                NutritionLine("Proteínas", totals.proteinGrams, Color(0xFFC62828))
                NutritionLine("Carbohidratos", totals.carbohydrateGrams, Color(0xFF2563A6))
                NutritionLine("Grasas", totals.fatGrams, Color(0xFF9A6700))
                NutritionLine("Fibra", totals.fiberGrams)
                if (!totals.isComplete) {
                    Text(
                        "Algún ingrediente no tiene todos sus datos nutricionales.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                HorizontalDivider()
                Text(
                    "Por 100 g: ${formatDecimal(totals.calories * per100Factor)} kcal · " +
                        "P ${formatDecimal(totals.proteinGrams * per100Factor)} g · " +
                        "H ${formatDecimal(totals.carbohydrateGrams * per100Factor)} g · " +
                        "G ${formatDecimal(totals.fatGrams * per100Factor)} g",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        PlanningRuleCards(
            itemKind = PlannedItemKind.DISH,
            itemId = dish.id,
            defaultGrams = totalWeight.coerceAtLeast(100.0),
            rule = planningRule,
            onSave = onSavePlanningRule,
            onDelete = onDeletePlanningRule
        )

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Ingredientes", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                HorizontalDivider()
                dish.ingredients.forEachIndexed { index, ingredient ->
                    val food = foodsById[ingredient.foodId]
                    Row(
                        Modifier.fillMaxWidth()
                            .then(if (food != null) Modifier.clickable { onOpenFood(food.id) } else Modifier)
                            .padding(vertical = 6.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        if (food != null) SmallFoodCategoryBadge(food.category) else Spacer(Modifier.size(24.dp))
                        Text(food?.name ?: "Alimento eliminado", modifier = Modifier.weight(1f), maxLines = 2, overflow = TextOverflow.Ellipsis)
                        Icon(
                            Icons.Default.Lock,
                            contentDescription = "Proporción bloqueada",
                            modifier = Modifier.size(17.dp),
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text("${formatDecimal(ingredient.grams)} g")
                    }
                    if (index < dish.ingredients.lastIndex) HorizontalDivider()
                }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("En el menú de esta semana", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                HorizontalDivider()
                if (menuUsages.isEmpty()) {
                    Text("Este plato no está incluido en el menú de esta semana.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    menuUsages.forEachIndexed { index, (_, label, amount) ->
                        Row(
                            Modifier.fillMaxWidth().padding(vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(label, modifier = Modifier.weight(1f), maxLines = 2)
                            Text(amount)
                        }
                        if (index < menuUsages.lastIndex) HorizontalDivider()
                    }
                }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("En el menú de la semana que viene", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                HorizontalDivider()
                if (nextMenuUsages.isEmpty()) {
                    Text("Este plato no está incluido en el menú de la semana que viene.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    nextMenuUsages.forEachIndexed { index, (_, label, amount) ->
                        Row(
                            Modifier.fillMaxWidth().padding(vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(label, modifier = Modifier.weight(1f), maxLines = 2)
                            Text(amount)
                        }
                        if (index < nextMenuUsages.lastIndex) HorizontalDivider()
                    }
                }
            }
        }

    }
}

@Composable
private fun AddToMealDialog(
    meals: List<PlannedMeal>,
    itemName: String,
    onChoose: (Long) -> Unit,
    onCreateNew: () -> Unit,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Añadir a una comida") },
        text = {
            Column(Modifier.fillMaxWidth().heightIn(max = 420.dp).verticalScroll(rememberScrollState())) {
                Text(
                    itemName,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
                Spacer(Modifier.height(8.dp))
                meals.sortedWith(compareBy<PlannedMeal> { it.type.ordinal }.thenBy { it.id }).forEachIndexed { index, meal ->
                    Row(
                        Modifier.fillMaxWidth().clickable { onChoose(meal.id) }.padding(vertical = 12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            "${meal.type.label} · ${meal.days.joinToString { it.shortLabel }}",
                            modifier = Modifier.weight(1f)
                        )
                        Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = null)
                    }
                    if (index < meals.lastIndex) HorizontalDivider()
                }
                if (meals.isNotEmpty()) HorizontalDivider()
                Row(
                    Modifier.fillMaxWidth().clickable(onClick = onCreateNew).padding(vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.Add, contentDescription = null)
                    Spacer(Modifier.width(10.dp))
                    Text("Crear otra comida")
                }
            }
        },
        confirmButton = {},
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } }
    )
}

@Composable
private fun DishEditorScreen(
    foods: List<Food>,
    initial: Dish? = null,
    preferredFoodIds: Set<Long>,
    onSave: (Dish) -> Unit,
    onDelete: (() -> Unit)? = null
) {
    var name by rememberSaveable(initial?.id) { mutableStateOf(initial?.name.orEmpty()) }
    var ingredientAmounts by remember(initial?.id) {
        mutableStateOf(initial?.ingredients?.associate { it.foodId to formatDecimal(it.grams) }.orEmpty())
    }
    var choosingFood by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val foodsById = remember(foods) { foods.associateBy { it.id } }
    val proportionsLocked = initial != null
    val parsedIngredients = ingredientAmounts.mapNotNull { (foodId, amount) ->
        parseDecimal(amount)?.takeIf { it in 0.1..5000.0 }?.let { DishIngredient(foodId, it) }
    }
    val preview = if (parsedIngredients.isNotEmpty() && parsedIngredients.size == ingredientAmounts.size) {
        Dish(initial?.id ?: 1L, name.ifBlank { "Plato" }, parsedIngredients).nutrition(foodsById)
    } else null

    if (choosingFood) {
        FoodPickerDialog(
            foods = foods,
            excludedFoodIds = ingredientAmounts.keys,
            preferredFoodIds = preferredFoodIds,
            onChoose = {
                ingredientAmounts = ingredientAmounts + (it to "100")
                choosingFood = false
            },
            onDismiss = { choosingFood = false }
        )
    }
    if (confirmDelete && onDelete != null) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("¿Eliminar este plato?") },
            text = { Text("También se quitará de las comidas planificadas que lo utilicen.") },
            confirmButton = {
                TextButton(onClick = onDelete) { Text("Eliminar", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancelar") } }
        )
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text(
            if (initial == null) "Nuevo plato" else "Editar plato",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold
        )
        OutlinedTextField(
            value = name,
            onValueChange = { name = it.take(80) },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Nombre del plato") },
            singleLine = true
        )
        Text("Ingredientes del plato", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        if (proportionsLocked) {
            Text(
                "Las proporciones se fijaron al crear el plato. En el menú puede variar la cantidad total, pero todos los ingredientes escalan juntos.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        ingredientAmounts.forEach { (foodId, amount) ->
            val food = foodsById[foodId]
            if (food != null) {
                Row(
                    Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    SmallFoodCategoryBadge(food.category)
                    Text(food.name, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                    if (proportionsLocked) {
                        Text("${amount} g", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Icon(
                            Icons.Default.Lock,
                            contentDescription = "Proporción bloqueada",
                            modifier = Modifier.size(17.dp),
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    } else {
                        NumericField(
                            "Gramos",
                            amount,
                            { ingredientAmounts = ingredientAmounts + (foodId to it) },
                            Modifier.width(105.dp)
                        )
                        TextButton(onClick = { ingredientAmounts = ingredientAmounts - foodId }) { Text("Quitar") }
                    }
                }
            }
        }
        if (!proportionsLocked) {
            OutlinedButton(onClick = { choosingFood = true }, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.Add, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Añadir ingrediente")
            }
        }
        preview?.let { totals ->
            Text(
                "Plato completo · ${formatDecimal(parsedIngredients.sumOf { it.grams })} g · " +
                    "${formatDecimal(totals.calories)} kcal · " +
                    "P ${formatDecimal(totals.proteinGrams)} · H ${formatDecimal(totals.carbohydrateGrams)} · " +
                    "G ${formatDecimal(totals.fatGrams)}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(
            onClick = {
                val ingredients = ingredientAmounts.mapNotNull { (foodId, amount) ->
                    parseDecimal(amount)?.let { DishIngredient(foodId, it) }
                }
                error = when {
                    name.trim().isEmpty() -> "Escribe un nombre para el plato."
                    ingredientAmounts.isEmpty() -> "Añade al menos un ingrediente."
                    ingredients.size != ingredientAmounts.size -> "Revisa las cantidades."
                    ingredients.any { it.grams !in 0.1..5000.0 } ->
                        "Cada cantidad debe estar entre 0,1 y 5000 g."
                    else -> null
                }
                if (error == null) {
                    onSave(Dish(initial?.id ?: System.currentTimeMillis(), name.trim(), ingredients))
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) { Text("Guardar plato") }
        if (onDelete != null) {
            TextButton(onClick = { confirmDelete = true }, modifier = Modifier.fillMaxWidth()) {
                Text("Eliminar plato", color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

private data class IndexedFood(val food: Food, val searchText: String)

@Composable
private fun FoodsScreen(    foods: List<Food>,
    plannedMeals: List<PlannedMeal>,
    dishes: List<Dish>,
    onOpenFood: (Long) -> Unit
) {
    var query by rememberSaveable { mutableStateOf("") }
    var selectedCategories by remember { mutableStateOf(emptySet<FoodCategory>()) }
    var selectedRetailers by remember { mutableStateOf(emptySet<String>()) }
    var showFilters by remember { mutableStateOf(false) }
    var normalizedQuery by remember { mutableStateOf("") }
    LaunchedEffect(query) {
        if (query.isNotBlank()) delay(250)
        normalizedQuery = normalizeSearch(query)
    }
    val retailers = remember(foods) { foods.mapNotNull { it.retailer }.distinct().sorted() }
    val foodIndex = remember(foods) {
        foods.sortedWith(compareBy<Food> { it.category.ordinal }.thenBy { it.name.lowercase() })
            .map { food ->
                IndexedFood(
                    food = food,
                    searchText = normalizeSearch(
                        listOfNotNull(
                            food.name, food.category.label, food.brand, food.family,
                            food.subcategory, food.retailer, food.barcode
                        ).joinToString(" ")
                    )
                )
            }
    }
    val filtered = remember(foodIndex, normalizedQuery, selectedCategories, selectedRetailers) {
        foodIndex.asSequence().filter { indexed ->
            val food = indexed.food
            (selectedCategories.isEmpty() || food.category in selectedCategories) &&
                (selectedRetailers.isEmpty() ||
                    (food.retailer != null && food.retailer in selectedRetailers)) &&
                (normalizedQuery.isBlank() || indexed.searchText.contains(normalizedQuery))
        }.map { it.food }.toList()
    }
    val dishesById = remember(dishes) { dishes.associateBy { it.id } }
    val weeklyAmounts = remember(plannedMeals, dishesById) {
        MealPlanEvaluator.weeklyFoodAmounts(plannedMeals, dishesById)
    }
    val shoppingFoods = remember(filtered, weeklyAmounts) {
        filtered.filter { weeklyAmounts.containsKey(it.id) }.sortedBy { it.name.lowercase() }
    }
    val otherFoods = remember(filtered, weeklyAmounts) { filtered.filterNot { weeklyAmounts.containsKey(it.id) } }
    val grouped = remember(otherFoods) { otherFoods.groupBy { it.category } }
    val activeFilterGroups = listOf(selectedCategories, selectedRetailers).count { it.isNotEmpty() }

    if (showFilters) {
        FoodFilterDialog(
            retailers = retailers,
            selectedCategories = selectedCategories,
            selectedRetailers = selectedRetailers,
            onApply = { categories, commerce ->
                selectedCategories = categories
                selectedRetailers = commerce
                showFilters = false
            },
            onDismiss = { showFilters = false }
        )
    }

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
            OutlinedButton(onClick = { showFilters = true }, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Default.FilterList, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(if (activeFilterGroups == 0) "Filtrar" else "Filtros activos ($activeFilterGroups)")
            }
            Spacer(Modifier.height(8.dp))
            Text(
                "${shoppingFoods.size} en la compra · ${otherFoods.size} restantes · valores por 100 g o 100 ml",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(12.dp))
        }
        item(key = "shopping_header") {
            Text(
                "Lista de la compra",
                modifier = Modifier.padding(top = 6.dp, bottom = 5.dp),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold
            )
        }
        if (shoppingFoods.isEmpty()) {
            item(key = "shopping_empty") {
                Text(
                    if (weeklyAmounts.isEmpty()) {
                        "Todavía no hay alimentos en el plan semanal."
                    } else {
                        "Ningún alimento del plan coincide con la búsqueda o los filtros."
                    },
                    modifier = Modifier.padding(vertical = 12.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                HorizontalDivider()
            }
        } else {
            items(shoppingFoods, key = { "shopping_${it.id}" }) { food ->
                ShoppingListEntry(
                    food = food,
                    totalGrams = weeklyAmounts.getValue(food.id),
                    onClick = { onOpenFood(food.id) }
                )
                HorizontalDivider()
            }
        }
        item(key = "other_foods_header") {
            Text(
                "Otros alimentos",
                modifier = Modifier.padding(top = 22.dp, bottom = 5.dp),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold
            )
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
                    if (foods.isEmpty()) "Todavía no hay alimentos." else "No hay alimentos con estos criterios.",
                    modifier = Modifier.padding(vertical = 24.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun ShoppingListEntry(food: Food, totalGrams: Double, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        FoodCategoryBadge(food.category)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(food.name, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyLarge)
            food.retailer?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Text(
            "${formatDecimal(totalGrams)} g",
            textAlign = TextAlign.End,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary
        )
    }
}

@Composable
private fun FoodFilterDialog(
    retailers: List<String>,
    selectedCategories: Set<FoodCategory>,
    selectedRetailers: Set<String>,
    onApply: (Set<FoodCategory>, Set<String>) -> Unit,
    onDismiss: () -> Unit
) {
    var categories by remember { mutableStateOf(selectedCategories) }
    var commerce by remember { mutableStateOf(selectedRetailers) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Filtrar alimentos") },
        text = {
            Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState())) {
                Text("Tipo nutricional", fontWeight = FontWeight.SemiBold)
                FoodCategory.entries.forEach { category ->
                    FilterChip(
                        selected = category in categories,
                        onClick = {
                            categories = if (category in categories) categories - category else categories + category
                        },
                        label = { Text(category.label) },
                        modifier = Modifier.fillMaxWidth()
                    )
                }
                Spacer(Modifier.height(10.dp))
                Text("Comercio", fontWeight = FontWeight.SemiBold)
                retailers.forEach { retailer ->
                    FilterChip(
                        selected = retailer in commerce,
                        onClick = {
                            commerce = if (retailer in commerce) commerce - retailer else commerce + retailer
                        },
                        label = { Text(retailer) },
                        modifier = Modifier.fillMaxWidth()
                    )
                }
                if (retailers.isEmpty()) {
                    Text("No hay comercios identificados en el catálogo.")
                }
            }
        },
        confirmButton = { TextButton(onClick = { onApply(categories, commerce) }) { Text("Aplicar") } },
        dismissButton = {
            Row {
                TextButton(onClick = { onApply(emptySet(), emptySet()) }) { Text("Limpiar") }
                TextButton(onClick = onDismiss) { Text("Cancelar") }
            }
        }
    )
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

@Composable
private fun SmallFoodCategoryBadge(category: FoodCategory) {
    val color = foodCategoryColor(category)
    Box(
        Modifier.size(24.dp).background(color.copy(alpha = 0.16f), CircleShape),
        contentAlignment = Alignment.Center
    ) {
        Icon(
            foodCategoryIcon(category),
            contentDescription = category.label,
            tint = color,
            modifier = Modifier.size(16.dp)
        )
    }
}

private fun foodCategoryColor(category: FoodCategory): Color = when (category) {
    FoodCategory.CARBOHYDRATE -> Color(0xFF2563A6)
    FoodCategory.FRUIT -> Color(0xFF9C3D78)
    FoodCategory.FAT -> Color(0xFF9A6700)
    FoodCategory.PROTEIN -> Color(0xFFD05A00)
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
private fun NutrientIconValue(
    icon: ImageVector,
    description: String,
    value: Double?,
    suffix: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    Row(
        modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(5.dp)
    ) {
        Icon(icon, contentDescription = description, tint = color, modifier = Modifier.size(19.dp))
        Text(
            value?.let { "${formatDecimal(it)} ${suffix}" } ?: "—",
            style = MaterialTheme.typography.bodySmall,
            color = if (value == null) MaterialTheme.colorScheme.onSurfaceVariant else color,
            maxLines = 1
        )
    }
}

@Composable
private fun FoodPrimaryNutritionStrip(food: Food) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        NutrientIconValue(
            Icons.Default.LocalFireDepartment, "Calorías", food.calories, "kcal",
            MaterialTheme.colorScheme.onSurface, Modifier.weight(1.25f)
        )
        NutrientIconValue(
            Icons.Default.FitnessCenter, "Proteínas", food.proteinGrams, "g",
            Color(0xFFC62828), Modifier.weight(1f)
        )
        NutrientIconValue(
            Icons.Default.Grain, "Carbohidratos", food.carbohydrateGrams, "g",
            Color(0xFF2563A6), Modifier.weight(1f)
        )
        NutrientIconValue(
            Icons.Default.Opacity, "Grasas", food.fatGrams, "g",
            Color(0xFF9A6700), Modifier.weight(1f)
        )
    }
}

@Composable
private fun FoodSecondaryNutritionStrip(food: Food) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        NutrientIconValue(
            Icons.Default.Circle, "Grasas saturadas", food.saturatedFatGrams, "g",
            Color(0xFF8D4E2F), Modifier.weight(1f)
        )
        NutrientIconValue(
            Icons.Default.Cake, "Azúcares", food.sugarGrams, "g",
            Color(0xFF9C3D78), Modifier.weight(1f)
        )
        NutrientIconValue(
            Icons.Default.Eco, "Fibra", food.fiberGrams, "g",
            Color(0xFF287A3D), Modifier.weight(1f)
        )
        NutrientIconValue(
            Icons.Default.AcUnit, "Sal", food.saltGrams, "g",
            Color(0xFF607D8B), Modifier.weight(1f)
        )
    }
}

@Composable
private fun SimilarFoodEntry(food: Food, onClick: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(5.dp)
    ) {
        Text(
            food.name,
            style = MaterialTheme.typography.bodyLarge,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
        FoodPrimaryNutritionStrip(food)
    }
}

@Composable
private fun FoodDetailScreen(
    food: Food,
    foods: List<Food>,
    plannedMeals: List<PlannedMeal>,
    dishes: List<Dish>,
    onOpenFood: (Long) -> Unit,
    onOpenMeal: (Long) -> Unit,
    onAddToMeal: (Long) -> Unit,
    onAddNewMeal: () -> Unit,
    planningRule: PlanningRule?,
    onSavePlanningRule: (PlanningRule) -> Unit,
    onDeletePlanningRule: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    var confirmDelete by remember { mutableStateOf(false) }
    val uriHandler = LocalUriHandler.current
    val similarFoods = FoodSimilarityEngine.findSimilar(food, foods)
    val menuUsages = remember(food.id, plannedMeals, dishes) {
        val dishesById = dishes.associateBy { it.id }
        plannedMeals.filter { it.planWeek == PlanWeek.CURRENT }.mapNotNull { meal ->
            val amounts = meal.days.map { day ->
                val direct = meal.items.filter { it.foodId == food.id }
                    .sumOf { meal.resolvedGrams(it, day) }
                val throughDishes = meal.dishes.sumOf { plannedDish ->
                    val dish = dishesById[plannedDish.dishId] ?: return@sumOf 0.0
                    val recipeWeight = dish.totalWeightGrams()
                    if (recipeWeight <= 0.0) return@sumOf 0.0
                    val ingredientGrams = dish.ingredients.filter { it.foodId == food.id }.sumOf { it.grams }
                    ingredientGrams * meal.resolvedGrams(plannedDish, day) / recipeWeight
                }
                direct + throughDishes
            }
            if (amounts.any { it > 0.0 }) {
                Triple(
                    meal.id,
                    "${meal.type.label} · ${meal.days.joinToString { it.shortLabel }}",
                    amountRangeLabel(amounts)
                )
            } else null
        }
    }
    val nextMenuUsages = remember(food.id, plannedMeals, dishes) {
        val dishesById = dishes.associateBy { it.id }
        plannedMeals.filter { it.planWeek == PlanWeek.NEXT }.mapNotNull { meal ->
            val amounts = meal.days.map { day ->
                val direct = meal.items.filter { it.foodId == food.id }
                    .sumOf { meal.resolvedGrams(it, day) }
                val throughDishes = meal.dishes.sumOf { plannedDish ->
                    val dish = dishesById[plannedDish.dishId] ?: return@sumOf 0.0
                    val recipeWeight = dish.totalWeightGrams()
                    if (recipeWeight <= 0.0) return@sumOf 0.0
                    val ingredientGrams = dish.ingredients.filter { it.foodId == food.id }.sumOf { it.grams }
                    ingredientGrams * meal.resolvedGrams(plannedDish, day) / recipeWeight
                }
                direct + throughDishes
            }
            if (amounts.any { it > 0.0 }) {
                Triple(
                    meal.id,
                    "${meal.type.label} · ${meal.days.joinToString { it.shortLabel }}",
                    amountRangeLabel(amounts)
                )
            } else null
        }
    }

    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("¿Eliminar ${food.name}?") },
            text = { Text("Se eliminará del catálogo de alimentos. Esta acción no se puede deshacer.") },
            confirmButton = {
                TextButton(onClick = onDelete) { Text("Eliminar", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancelar") } }
        )
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    FoodCategoryBadge(food.category)
                    Column(Modifier.weight(1f)) {
                        Text(food.name, style = MaterialTheme.typography.headlineSmall)
                        listOfNotNull(food.brand, food.subcategory ?: food.family)
                            .joinToString(" · ")
                            .takeIf { it.isNotBlank() }
                            ?.let {
                                Text(
                                    it,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    style = MaterialTheme.typography.bodyMedium
                                )
                            }
                        Text(
                            "Predominan: ${food.category.label.lowercase()}",
                            color = foodCategoryColor(food.category),
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
                HorizontalDivider()
                Text("Valores por 100 g o 100 ml", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                FoodPrimaryNutritionStrip(food)
                HorizontalDivider()
                FoodSecondaryNutritionStrip(food)
                food.legalName?.let {
                    HorizontalDivider()
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                food.ingredients?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (food.links.isNotEmpty()) {
                    HorizontalDivider()
                    food.links.forEachIndexed { index, link ->
                        Row(
                            Modifier.fillMaxWidth().clickable { uriHandler.openUri(link) }.padding(vertical = 7.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Text(
                                if (linkLabel(link).contains("mercadona", ignoreCase = true)) "Ver producto en Mercadona"
                                else "Ver fuente: ${linkLabel(link)}",
                                modifier = Modifier.weight(1f),
                                color = MaterialTheme.colorScheme.primary
                            )
                            Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = "Abrir enlace", tint = MaterialTheme.colorScheme.primary)
                        }
                        if (index < food.links.lastIndex) HorizontalDivider()
                    }
                }
            }
        }


        PlanningRuleCards(
            itemKind = PlannedItemKind.FOOD,
            itemId = food.id,
            defaultGrams = 100.0,
            rule = planningRule,
            onSave = onSavePlanningRule,
            onDelete = onDeletePlanningRule
        )

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("En el menú de esta semana", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                HorizontalDivider()
                if (menuUsages.isEmpty()) {
                    Text("Este alimento no está incluido en el menú de esta semana.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    menuUsages.forEachIndexed { index, (_, label, amount) ->
                        Row(
                            Modifier.fillMaxWidth().padding(vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(label, modifier = Modifier.weight(1f), maxLines = 2)
                            Text(amount)
                        }
                        if (index < menuUsages.lastIndex) HorizontalDivider()
                    }
                }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("En el menú de la semana que viene", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                HorizontalDivider()
                if (nextMenuUsages.isEmpty()) {
                    Text("Este alimento no está incluido en el menú de la semana que viene.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    nextMenuUsages.forEachIndexed { index, (_, label, amount) ->
                        Row(
                            Modifier.fillMaxWidth().padding(vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(label, modifier = Modifier.weight(1f), maxLines = 2)
                            Text(amount)
                        }
                        if (index < nextMenuUsages.lastIndex) HorizontalDivider()
                    }
                }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Alimentos similares", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                HorizontalDivider()
                Text(
                    "Puedes sustituirlo por estos alimentos sin alterar demasiado el reparto nutricional.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (similarFoods.isEmpty()) {
                    Text("No hay sustitutos suficientemente próximos.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    similarFoods.forEachIndexed { index, similar ->
                        SimilarFoodEntry(food = similar, onClick = { onOpenFood(similar.id) })
                        if (index < similarFoods.lastIndex) HorizontalDivider()
                    }
                }
            }
        }

    }
}

private fun linkLabel(link: String): String = runCatching {
    java.net.URI(link).host?.removePrefix("www.")
}.getOrNull().orEmpty().ifBlank { link }

@Composable
private fun NutritionLine(label: String, grams: Double?, valueColor: Color = Color.Unspecified) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            grams?.let { "${formatDecimal(it)} g" } ?: "Sin datos",
            color = if (grams == null) MaterialTheme.colorScheme.onSurfaceVariant else valueColor,
            fontWeight = if (grams == null) FontWeight.Normal else FontWeight.SemiBold
        )
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

private val defaultMealShares: Map<MealType, Double> = mapOf(
    MealType.BREAKFAST to 0.25,
    MealType.MORNING_SNACK to 0.10,
    MealType.LUNCH to 0.35,
    MealType.AFTERNOON_SNACK to 0.10,
    MealType.DINNER to 0.20
)

private fun loadMealShares(context: android.content.Context): Map<MealType, Double> {
    val preferences = context.getSharedPreferences("meal_distribution", 0)
    val loaded = MealType.entries.associateWith { type ->
        preferences.getFloat(type.name, defaultMealShares.getValue(type).toFloat()).toDouble()
    }
    return if (kotlin.math.abs(loaded.values.sum() - 1.0) < 0.001) loaded else defaultMealShares
}

private fun saveMealShares(context: android.content.Context, shares: Map<MealType, Double>) {
    context.getSharedPreferences("meal_distribution", 0).edit().apply {
        shares.forEach { (type, share) -> putFloat(type.name, share.toFloat()) }
    }.apply()
}

private fun loadAdjustmentRange(context: android.content.Context): Pair<Double, Double> {
    val preferences = context.getSharedPreferences("quantity_adjustment", 0)
    return preferences.getFloat("divisor", 2.0f).toDouble() to
        preferences.getFloat("multiplier", 1.5f).toDouble()
}

private fun saveAdjustmentRange(context: android.content.Context, range: Pair<Double, Double>) {
    context.getSharedPreferences("quantity_adjustment", 0).edit()
        .putFloat("divisor", range.first.toFloat())
        .putFloat("multiplier", range.second.toFloat())
        .apply()
}

@Composable
private fun SettingsScreen(
    mealShares: Map<MealType, Double>,
    adjustmentRange: Pair<Double, Double>,
    onSaveMealShares: (Map<MealType, Double>) -> Unit,
    onSaveAdjustmentRange: (Pair<Double, Double>) -> Unit,
    onExport: () -> Unit,
    onImport: () -> Unit
) {
    var values by remember(mealShares) {
        mutableStateOf(
            MealType.entries.associateWith {
                ((mealShares[it] ?: defaultMealShares.getValue(it)) * 100.0)
                    .roundToInt().toString()
            }
        )
    }
    var error by remember { mutableStateOf<String?>(null) }
    var adjustmentDivisor by remember(adjustmentRange) {
        mutableStateOf(formatDecimal(adjustmentRange.first))
    }
    var adjustmentMultiplier by remember(adjustmentRange) {
        mutableStateOf(formatDecimal(adjustmentRange.second))
    }
    var adjustmentError by remember { mutableStateOf<String?>(null) }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text("Opciones", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    "Distribución de las calorías",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold
                )
                Text(
                    "Indica qué porcentaje del total diario corresponde a cada comida. La suma debe ser 100 %.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                MealType.entries.forEach { type ->
                    Row(
                        Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Text(type.label, modifier = Modifier.weight(1f))
                        OutlinedTextField(
                            value = values[type].orEmpty(),
                            onValueChange = { raw ->
                                values = values + (type to raw.filter(Char::isDigit).take(2))
                                error = null
                            },
                            modifier = Modifier.width(82.dp),
                            suffix = { Text("%") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true
                        )
                    }
                }
                error?.let {
                    Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
                OutlinedButton(
                    onClick = {
                        val parsed = MealType.entries.associateWith { values[it]?.toIntOrNull() }
                        error = when {
                            parsed.values.any { it == null } -> "Completa todos los porcentajes."
                            parsed.values.any { it!! !in 0..90 } ->
                                "Cada porcentaje debe estar entre 0 y 90."
                            parsed.values.sumOf { it!! } != 100 -> "Los porcentajes deben sumar 100 %."
                            else -> null
                        }
                        if (error == null) {
                            onSaveMealShares(parsed.mapValues { it.value!! / 100.0 })
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Guardar distribución") }
            }
        }
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    "Ajuste automático de cantidades",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold
                )
                Text(
                    "Estos límites se aplican a todos los elementos que permitas ajustar.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                NumericField("Dividir como máximo entre", adjustmentDivisor, {
                    adjustmentDivisor = it
                    adjustmentError = null
                }, Modifier.fillMaxWidth())
                NumericField("Multiplicar como máximo por", adjustmentMultiplier, {
                    adjustmentMultiplier = it
                    adjustmentError = null
                }, Modifier.fillMaxWidth())
                adjustmentError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                OutlinedButton(
                    onClick = {
                        val divisor = parseDecimal(adjustmentDivisor)
                        val multiplier = parseDecimal(adjustmentMultiplier)
                        adjustmentError = if (
                            divisor == null || divisor !in 1.0..10.0 ||
                            multiplier == null || multiplier !in 1.0..10.0
                        ) "Ambos factores deben estar entre 1 y 10."
                        else {
                            onSaveAdjustmentRange(divisor to multiplier)
                            null
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Guardar límites") }
            }
        }
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    "Copia de seguridad",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold
                )
                Text(
                    "La copia incluye todos los perfiles, mediciones y menús.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                OutlinedButton(onClick = onExport, modifier = Modifier.fillMaxWidth()) {
                    Text("Exportar copia")
                }
                OutlinedButton(onClick = onImport, modifier = Modifier.fillMaxWidth()) {
                    Text("Importar copia")
                }
            }
        }
    }
}

@Composable
private fun ProfileScreen(
    profile: UserProfile?,
    profiles: List<UserProfile>,
    isOnboarding: Boolean,
    requiresBaseline: Boolean,
    mealShares: Map<MealType, Double>,
    onCreate: (UserProfile, Measurement, Map<MealType, Double>) -> Unit,
    onSave: (UserProfile) -> Unit,
    onSwitch: (Long) -> Unit,
    onDelete: (Long) -> Unit
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
    var error by rememberSaveable { mutableStateOf<String?>(null) }
    var pendingDelete by remember { mutableStateOf<UserProfile?>(null) }
    var shareValues by remember(editedProfile?.id, creating) {
        mutableStateOf(
            MealType.entries.associateWith {
                ((mealShares[it] ?: defaultMealShares.getValue(it)) * 100).roundToInt().toString()
            }
        )
    }
    val needsBaseline = creating || requiresBaseline

    pendingDelete?.let { selected ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            title = { Text("¿Eliminar el perfil de \${selected.name}?") },
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
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        if (!isOnboarding && profiles.isNotEmpty()) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(vertical = 8.dp)) {
                    Text(
                        "Perfiles",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                    )
                    HorizontalDivider()
                    profiles.forEach { listed ->
                        TextButton(
                            onClick = { onSwitch(listed.id) },
                            modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp)
                        ) {
                            Icon(
                                if (listed.id == profile?.id) Icons.Default.Check else Icons.Default.Person,
                                contentDescription = null
                            )
                            Spacer(Modifier.width(8.dp))
                            Text(listed.name, modifier = Modifier.weight(1f), textAlign = TextAlign.Start)
                            if (listed.id == profile?.id) Text("Activo")
                        }
                    }
                    HorizontalDivider()
                    TextButton(
                        onClick = { creating = true },
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp)
                    ) {
                        Icon(Icons.Default.PersonAdd, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Añadir otro perfil", modifier = Modifier.weight(1f), textAlign = TextAlign.Start)
                    }
                }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(
                Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    if (creating) "Datos personales" else "Datos de \${profile?.name}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
                HorizontalDivider()
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it.take(30) },
                    label = { Text("Nombre del perfil") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    NumericField("Altura (cm)", height, { height = it }, Modifier.weight(1f))
                    OutlinedTextField(
                        value = birthYear,
                        onValueChange = { birthYear = it.filter(Char::isDigit).take(4) },
                        label = { Text("Año de nacimiento") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                }
                SelectorField(
                    label = "Sexo usado para el cálculo",
                    selectedLabel = sex.label,
                    options = Sex.entries,
                    optionLabel = { it.label },
                    onSelect = { sex = it },
                    onClear = null
                )
            }
        }

        if (needsBaseline) {
            Card(Modifier.fillMaxWidth()) {
                Column(
                    Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text(
                        "Primera medición",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    HorizontalDivider()
                    Text(
                        "Introduce el peso, la cintura o ambos. Con los dos indicadores podremos darte una valoración más precisa.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        NumericField("Peso (kg)", initialWeight, { initialWeight = it }, Modifier.weight(1f))
                        NumericField("Cintura (cm)", initialWaist, { initialWaist = it }, Modifier.weight(1f))
                    }
                    WaistMeasurementHelp()
                    Text(
                        "Rumbo propondrá el objetivo que mejor encaje con esta medición. Después podrás cambiarlo desde la pantalla principal.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }

        if (creating) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(
                        "Distribución de las comidas",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                    HorizontalDivider()
                    Text(
                        "Indica qué porcentaje de las calorías diarias quieres reservar para cada comida.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    MealType.entries.forEach { type ->
                        Row(
                            Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Text(type.label, modifier = Modifier.weight(1f))
                            OutlinedTextField(
                                value = shareValues[type].orEmpty(),
                                onValueChange = { raw ->
                                    shareValues = shareValues + (type to raw.filter(Char::isDigit).take(2))
                                    error = null
                                },
                                modifier = Modifier.width(82.dp),
                                suffix = { Text("%") },
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                singleLine = true
                            )
                        }
                    }
                    Text(
                        "La suma debe ser 100 %. Podrás cambiarla después en Opciones.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }

        error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        OutlinedButton(
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
                val parsedShares = MealType.entries.associateWith { shareValues[it]?.toIntOrNull() }
                error = when {
                    !candidate.isValid() -> "Revisa el nombre, la altura y el año de nacimiento. La app está diseñada para personas adultas."
                    needsBaseline && initialWeight.isNotBlank() && (parsedWeight == null || parsedWeight !in 30.0..350.0) ->
                        "El peso debe estar entre 30 y 350 kg."
                    needsBaseline && initialWaist.isNotBlank() && (parsedWaist == null || parsedWaist !in 35.0..250.0) ->
                        "La cintura debe estar entre 35 y 250 cm."
                    needsBaseline && parsedWeight == null && parsedWaist == null ->
                        "Introduce al menos el peso o la cintura."
                    creating && parsedShares.values.any { it == null || it !in 0..90 } ->
                        "Revisa los porcentajes de las comidas."
                    creating && parsedShares.values.sumOf { it ?: 0 } != 100 ->
                        "Los porcentajes de las comidas deben sumar 100 %."
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
                                goal = WeightGoal.AUTOMATIC
                            ),
                            parsedShares.mapValues { (it.value ?: 0) / 100.0 }
                        )
                    } else onSave(candidate)
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
            TextButton(onClick = { creating = false }, modifier = Modifier.fillMaxWidth()) { Text("Cancelar") }
        }
    }
}

@Composable
private fun WaistMeasurementHelp() {
    val uriHandler = LocalUriHandler.current
    TextButton(
        onClick = {
            uriHandler.openUri("https://www.comunidad.madrid/salud/sobrepeso-obesidad")
        },
        contentPadding = PaddingValues(horizontal = 0.dp)
    ) {
        Text("Cómo medir correctamente la cintura")
    }
}

@Composable
private fun CompactGramField(value: String, onValueChange: (String) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = value,
            onValueChange = { raw ->
                onValueChange(raw.filter { it.isDigit() || it == ',' || it == '.' }.take(6))
            },
            modifier = Modifier.width(82.dp),
            suffix = {
                Text("g", color = MaterialTheme.colorScheme.onSurfaceVariant)
            },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            singleLine = true
        )
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
    selectedLabel: String,    options: List<T>,
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
