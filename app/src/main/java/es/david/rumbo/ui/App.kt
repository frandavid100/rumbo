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
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Eco
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.Grain
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.LocalFlorist
import androidx.compose.material.icons.filled.LocalFireDepartment
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
import androidx.compose.runtime.saveable.rememberSaveable
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
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
import es.david.rumbo.model.ActivityLevel
import es.david.rumbo.model.AppData
import es.david.rumbo.model.BodyAssessment
import es.david.rumbo.model.DietCompliance
import es.david.rumbo.model.Dish
import es.david.rumbo.model.DishIngredient
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.Measurement
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedDish
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.RecommendedGoal
import es.david.rumbo.model.Sex
import es.david.rumbo.model.UserProfile
import es.david.rumbo.model.WeightGoal
import es.david.rumbo.model.WeekDay
import es.david.rumbo.model.dominantCategory
import es.david.rumbo.model.nutrition
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
    PLANNER("Plan", Icons.Default.CalendarMonth),
    ADD_PLANNED_MEAL("Añadir comida", Icons.Default.CalendarMonth, false),
    EDIT_PLANNED_MEAL("Editar comida", Icons.Default.CalendarMonth, false),
    DISHES("Platos", Icons.Default.Restaurant),
    ADD_DISH("Añadir plato", Icons.Default.Restaurant, false),
    DISH_DETAIL("Plato", Icons.Default.Restaurant, false),
    EDIT_DISH("Editar plato", Icons.Default.Restaurant, false),
    FOODS("Alimentos", Icons.Default.Restaurant),
    ADD_FOOD("Añadir alimento", Icons.Default.Restaurant, false),
    FOOD_DETAIL("Alimento", Icons.Default.Restaurant, false),
    EDIT_FOOD("Editar alimento", Icons.Default.Restaurant, false),
    PROFILE("Perfiles", Icons.Default.Person),
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
    var draftMealDayName by rememberSaveable { mutableStateOf<String?>(null) }
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
    val navigateBack = {
        screenName = when {
            screen == Screen.EDIT_MEASUREMENT && selectedMeasurementId != null ->
                Screen.MEASUREMENT_DETAIL.name
            screen == Screen.EDIT_FOOD && selectedFoodId != null ->
                Screen.FOOD_DETAIL.name
            screen in setOf(Screen.ADD_PLANNED_MEAL, Screen.EDIT_PLANNED_MEAL) ->
                Screen.PLANNER.name
            screen == Screen.EDIT_DISH && selectedDishId != null -> Screen.DISH_DETAIL.name
            screen in setOf(Screen.ADD_DISH, Screen.DISH_DETAIL) -> Screen.DISHES.name
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

    Scaffold(
        topBar = {
            TopAppBar(
                navigationIcon = {
                    if (!screen.inNavigation) {
                        IconButton(onClick = navigateBack) {
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
            if (profileReady && screen in setOf(Screen.PLANNER, Screen.DISHES, Screen.FOODS)) {
                FloatingActionButton(onClick = {
                    if (screen == Screen.PLANNER) {
                        draftMealTypeName = null
                        draftMealDayName = null
                    }
                    screenName = when (screen) {
                        Screen.PLANNER -> Screen.ADD_PLANNED_MEAL.name
                        Screen.DISHES -> Screen.ADD_DISH.name
                        Screen.FOODS -> Screen.ADD_FOOD.name
                        else -> Screen.ADD.name
                    }
                }) {
                    Icon(
                        Icons.Default.Add,
                        contentDescription = when (screen) {
                            Screen.PLANNER -> "Añadir una comida"
                            Screen.DISHES -> "Añadir un plato"
                            Screen.FOODS -> "Añadir un alimento"
                            else -> "Añadir una medición"
                        }
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
                    onGoalChange = { data = repository.setWeeklyRate(it) },
                    onAddMeasurement = { screenName = Screen.ADD.name },
                    onExplainBody = { screenName = Screen.BODY_EXPLANATION.name },
                    onOpenPlanner = { screenName = Screen.PLANNER.name },
                    onOpenMeal = {
                        selectedPlannedMealId = it
                        screenName = Screen.EDIT_PLANNED_MEAL.name
                    },
                    onOpenFoods = { screenName = Screen.FOODS.name },
                    onAddMissingMeal = { type, day ->
                        draftMealTypeName = type.name
                        draftMealDayName = day.name
                        screenName = Screen.ADD_PLANNED_MEAL.name
                    },
                    onApplyAdjustedMeals = { data = repository.savePlannedMeals(it) }
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
                    foods = data.foods,
                    dishes = data.dishes,
                    recommendation = currentRecommendation,
                    onOpenMeal = {
                        selectedPlannedMealId = it
                        screenName = Screen.EDIT_PLANNED_MEAL.name
                    },
                    onAddMissing = { type, day ->
                        draftMealTypeName = type.name
                        draftMealDayName = day.name
                        screenName = Screen.ADD_PLANNED_MEAL.name
                    },
                    onApplyAdjustedMeals = { data = repository.savePlannedMeals(it) }
                )
                screen == Screen.ADD_PLANNED_MEAL -> PlannedMealEditorScreen(
                    foods = data.foods,
                    dishes = data.dishes,
                    existingMeals = data.activeProfileData?.plannedMeals.orEmpty(),
                    recommendation = currentRecommendation,
                    initialType = draftMealTypeName?.let { MealType.valueOf(it) },
                    initialDays = draftMealDayName?.let { setOf(WeekDay.valueOf(it)) }.orEmpty(),
                    preferredFoodIds = preferredFoodIds,
                    preferredDishIds = preferredDishIds,
                    onCreateDish = { data = repository.saveDish(it) },
                    onSave = {
                        data = repository.savePlannedMeal(it)
                        draftMealTypeName = null
                        draftMealDayName = null
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
                            initial = meal,
                            preferredFoodIds = preferredFoodIds,
                            preferredDishIds = preferredDishIds,
                            onCreateDish = { data = repository.saveDish(it) },
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
                screen == Screen.DISHES -> DishesScreen(
                    dishes = data.dishes,
                    foods = data.foods,
                    onOpenDish = {
                        selectedDishId = it
                        screenName = Screen.DISH_DETAIL.name
                    }
                )
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
                        screenName = Screen.DISHES.name
                    } else {
                        DishDetailScreen(
                            dish = dish,
                            foods = data.foods,
                            onEdit = { screenName = Screen.EDIT_DISH.name },
                            onDelete = {
                                data = repository.deleteDish(dish.id)
                                selectedDishId = null
                                screenName = Screen.DISHES.name
                            }
                        )
                    }
                }
                screen == Screen.EDIT_DISH -> {
                    val dish = data.dishes.firstOrNull { it.id == selectedDishId }
                    if (dish == null) {
                        screenName = Screen.DISHES.name
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
                                screenName = Screen.DISHES.name
                            }
                        )
                    }
                }
                screen == Screen.FOODS -> FoodsScreen(
                    foods = data.foods,
                    plannedMeals = data.activeProfileData?.plannedMeals.orEmpty(),
                    dishes = data.dishes,
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
                onOpenFoods = onOpenFoods
            )
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
private fun HomeCardHeader(title: String) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(title, modifier = Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
            Icon(
                Icons.AutoMirrored.Filled.ArrowForward,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(20.dp)
            )
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
            HomeCardHeader("Menú de hoy · ${today.label}")
            MealType.entries.forEachIndexed { index, type ->
                val meal = todayMeals[type]
                val entries = meal?.let {
                    it.dishes.mapNotNull { planned ->
                        dishesById[planned.dishId]?.let { dish ->
                            Triple(
                                dish.name,
                                it.resolvedGrams(planned, today),
                                dish.dominantCategory(foodsById)
                            )
                        }
                    } + it.items.mapNotNull { planned ->
                        foodsById[planned.foodId]?.let { food ->
                            Triple(
                                food.name,
                                it.resolvedGrams(planned, today),
                                food.category
                            )
                        }
                    }
                }.orEmpty()
                val mealModifier = if (meal == null) {
                    Modifier.fillMaxWidth()
                } else {
                    Modifier.fillMaxWidth().clickable { onOpenMeal(meal.id) }
                }
                Column(
                    mealModifier.padding(vertical = 2.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Row(
                        Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            type.label,
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.SemiBold
                        )
                        if (entries.isEmpty()) {
                            TextButton(onClick = { onAddMissing(type, today) }) {
                                Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(18.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("Añadir")
                            }
                        }
                    }
                    if (entries.isEmpty()) {
                        Text(
                            "Sin planificar",
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodyMedium
                        )
                    } else {
                        entries.forEach { (name, grams, category) ->
                            Row(
                                Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                SmallFoodCategoryBadge(category)
                                Text(name, modifier = Modifier.weight(1f))
                                Text(
                                    "${formatDecimal(grams)} g",
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
            OutlinedButton(
                onClick = {
                    if (recommendation == null) {
                        optimizationMessage = "Necesitas una recomendación nutricional antes de ajustar el menú."
                    } else {
                        val result = MealQuantityOptimizer.optimize(
                            meals, foodsById, dishesById, recommendation, setOf(today)
                        )
                        if (result.changes.isNotEmpty()) optimizationPreview = result
                        else optimizationMessage = if (result.days.isEmpty()) {
                            "Completa el día y marca uno o varios elementos como ajustables. Las cantidades fijas nunca se modifican."
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
        )
    }
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
    onOpenFoods: () -> Unit
) {
    val amounts = remember(meals, dishesById) {
        MealPlanEvaluator.weeklyFoodAmounts(meals, dishesById)
    }
    val entries = remember(amounts, foodsById) {
        amounts.mapNotNull { (foodId, grams) -> foodsById[foodId]?.let { it to grams } }
            .sortedBy { it.first.name.lowercase() }
    }
    Card(Modifier.fillMaxWidth().clickable(onClick = onOpenFoods)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            HomeCardHeader("Lista de la compra")
            if (entries.isEmpty()) {
                Text("El plan todavía no contiene alimentos.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                entries.take(6).forEach { (food, grams) ->
                    Row(
                        Modifier.fillMaxWidth().padding(vertical = 2.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        SmallFoodCategoryBadge(food.category)
                        Text(food.name, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                        Text("${formatDecimal(grams)} g", fontWeight = FontWeight.SemiBold)
                    }
                }
                if (entries.size > 6) Text(
                    "Y ${entries.size - 6} productos más",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
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
            Text(
                label,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold
            )
            Text(interpretation, style = MaterialTheme.typography.bodyLarge)
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
private const val WEIGHT_LOSS_RATE_STUDY_URL =
    "https://pubmed.ncbi.nlm.nih.gov/21558571/"
private const val MIFFLIN_ST_JEOR_URL =
    "https://pubmed.ncbi.nlm.nih.gov/2305711/"
private const val ENERGY_BALANCE_MODEL_URL =
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC3859816/"
private const val PROTEIN_META_ANALYSIS_URL =
    "https://pubmed.ncbi.nlm.nih.gov/28698222/"
private const val EFSA_FAT_REFERENCE_URL =
    "https://www.efsa.europa.eu/en/press/news/nda100326"

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
                    value = formatOneDecimal(bmi),
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
                    value = formatTwoDecimals(ratio),
                    interpretation = assessment.waistInterpretation.orEmpty()
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
                        TextButton(
                            onClick = { uriHandler.openUri(WEIGHT_LOSS_RATE_STUDY_URL) },
                            contentPadding = PaddingValues(0.dp)
                        ) { Text("Estudio: ritmo de pérdida y conservación muscular") }
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
                        "Según tu peso, altura, edad y sexo, Mifflin–St Jeor estima un gasto de ${formatOneDecimal(calculation.restingCalories)} kcal al día en reposo. Al incorporar tu actividad «${calculation.activity.label.lowercase()}», estimamos un mantenimiento de ${formatOneDecimal(calculation.maintenanceCalories)} kcal. $goalCalculation $adjustments Tras los ajustes obtenemos ${formatOneDecimal(calculation.beforeRoundingCalories)} kcal y redondeamos al múltiplo de 25 más cercano: ${recommendation.calories} kcal al día.",
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
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
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
                    Spacer(Modifier.height(8.dp))
                    Text(
                        proteinContext + referenceWeightText +
                            " Reservamos aproximadamente el 25 % de las calorías para ${recommendation.fatGrams} g de grasa, dentro del intervalo recomendado, y completamos las calorías restantes con ${recommendation.carbohydrateGrams} g de hidratos para aportar energía. Este no es el único reparto saludable posible, pero ofrece un equilibrio razonable entre composición corporal, energía y facilidad para mantener la dieta.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    TextButton(
                        onClick = { uriHandler.openUri(PROTEIN_META_ANALYSIS_URL) },
                        contentPadding = PaddingValues(0.dp)
                    ) { Text("Referencia: proteína y conservación muscular") }
                    TextButton(
                        onClick = { uriHandler.openUri(EFSA_FAT_REFERENCE_URL) },
                        contentPadding = PaddingValues(0.dp)
                    ) { Text("Referencia: intervalo de grasas de la EFSA") }
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
private fun WeeklyPlannerScreen(
    meals: List<PlannedMeal>,
    foods: List<Food>,
    dishes: List<Dish>,
    recommendation: es.david.rumbo.model.Recommendation?,
    onOpenMeal: (Long) -> Unit,
    onAddMissing: (MealType, WeekDay) -> Unit,
    onApplyAdjustedMeals: (List<PlannedMeal>) -> Unit
) {
    var viewName by rememberSaveable { mutableStateOf(PlannerView.WEEK.name) }
    var selectedDayName by rememberSaveable { mutableStateOf(WeekDay.MONDAY.name) }
    val view = PlannerView.valueOf(viewName)
    val today = WeekDay.entries[LocalDate.now().dayOfWeek.value - 1]
    val selectedDay = if (view == PlannerView.TODAY) today else WeekDay.valueOf(selectedDayName)
    val foodsById = remember(foods) { foods.associateBy { it.id } }
    val dishesById = remember(dishes) { dishes.associateBy { it.id } }
    val grouped = remember(meals) { meals.groupBy { it.type } }
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
            confirmButton = { TextButton(onClick = { optimizationMessage = null }) { Text("Entendido") } }
        )
    }
    LazyColumn(
        contentPadding = PaddingValues(start = 20.dp, top = 16.dp, end = 20.dp, bottom = 96.dp)
    ) {
        item {
            Text("Plan de comidas", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(6.dp))
            Text(
                "Compara cada comida y cada día con tu recomendación actual.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium
            )
            Text(
                "Real/objetivo · verde ≤10 % · amarillo ≤20 % · rojo >20 %",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodySmall
            )
            Spacer(Modifier.height(14.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                PlannerView.entries.forEach { option ->
                    FilterChip(
                        selected = view == option,
                        onClick = { viewName = option.name },
                        label = { Text(option.label) },
                        modifier = Modifier.weight(1f)
                    )
                }
            }
            if (view == PlannerView.DAY) {
                Spacer(Modifier.height(10.dp))
                WeekDay.entries.chunked(4).forEach { rowDays ->
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        rowDays.forEach { day ->
                            FilterChip(
                                selected = day == selectedDay,
                                onClick = { selectedDayName = day.name },
                                label = { Text(day.shortLabel) },
                                modifier = Modifier.weight(1f)
                            )
                        }
                        repeat(4 - rowDays.size) { Spacer(Modifier.weight(1f)) }
                    }
                }
            }
            Spacer(Modifier.height(10.dp))
            FilledTonalButton(
                onClick = {
                    if (recommendation == null) {
                        optimizationMessage = "Necesitas una recomendación nutricional antes de ajustar el plan."
                    } else {
                        val result = MealQuantityOptimizer.optimize(
                            meals, foodsById, dishesById, recommendation
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
            ) {
                Text("Ajustar cantidades")
            }
            Spacer(Modifier.height(8.dp))
        }

        if (view == PlannerView.WEEK) {
            item {
                Text(
                    "Totales por día",
                    modifier = Modifier.padding(top = 6.dp, bottom = 4.dp),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold
                )
            }
            items(WeekDay.entries, key = { "day_${it.name}" }) { day ->
                DayNutritionEntry(
                    day = day,
                    meals = meals,
                    foodsById = foodsById,
                    dishesById = dishesById,
                    recommendation = recommendation,
                    onClick = {
                        selectedDayName = day.name
                        viewName = PlannerView.DAY.name
                    }
                )
                HorizontalDivider()
            }
            item {
                Text(
                    "Comidas reutilizables",
                    modifier = Modifier.padding(top = 22.dp, bottom = 4.dp),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold
                )
            }
            MealType.entries.forEach { type ->
                val typeMeals = grouped[type].orEmpty()
                if (typeMeals.isNotEmpty()) {
                    item(key = "meal_header_${type.name}") {
                        Text(
                            type.label,
                            modifier = Modifier.padding(top = 10.dp, bottom = 4.dp),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                    items(typeMeals, key = { it.id }) { meal ->
                        PlannedMealListEntry(
                            meal = meal,
                            foodsById = foodsById,
                            dishesById = dishesById,
                            recommendation = recommendation,
                            showDays = true,
                            day = null,
                            onClick = { onOpenMeal(meal.id) }
                        )
                        HorizontalDivider()
                    }
                }
            }
        } else {
            item {
                Text(
                    if (view == PlannerView.TODAY) "Hoy · ${selectedDay.label}" else selectedDay.label,
                    modifier = Modifier.padding(top = 6.dp, bottom = 4.dp),
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold
                )
                DayNutritionEntry(
                    day = selectedDay,
                    meals = meals,
                    foodsById = foodsById,
                    dishesById = dishesById,
                    recommendation = recommendation,
                    onClick = null
                )
                HorizontalDivider()
            }
            MealType.entries.forEach { type ->
                val meal = grouped[type].orEmpty().firstOrNull { selectedDay in it.days }
                item(key = "selected_${selectedDay.name}_${type.name}") {
                    Text(
                        type.label,
                        modifier = Modifier.padding(top = 10.dp, bottom = 4.dp),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary
                    )
                    if (meal == null) {
                        Row(
                            Modifier.fillMaxWidth().padding(vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                "Sin planificar",
                                modifier = Modifier.weight(1f),
                                color = MaterialTheme.colorScheme.error,
                                style = MaterialTheme.typography.bodyMedium
                            )
                            TextButton(onClick = { onAddMissing(type, selectedDay) }) {
                                Icon(Icons.Default.Add, contentDescription = null)
                                Spacer(Modifier.width(4.dp))
                                Text("Añadir")
                            }
                        }
                    } else {
                        PlannedMealListEntry(
                            meal = meal,
                            foodsById = foodsById,
                            dishesById = dishesById,
                            recommendation = recommendation,
                            showDays = false,
                            day = selectedDay,
                            onClick = { onOpenMeal(meal.id) }
                        )
                    }
                    HorizontalDivider()
                }
            }
        }

        if (meals.isEmpty()) {
            item {
                Text(
                    "Todavía no hay comidas. Pulsa + para crear la primera.",
                    modifier = Modifier.padding(vertical = 24.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
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

private fun AmountDraft.withAdjustable(enabled: Boolean): AmountDraft {
    if (!enabled) return copy(adjustable = false)
    val amount = parseDecimal(grams) ?: 100.0
    return copy(
        adjustable = true,
        minimum = minimum.ifBlank { formatDecimal((amount * 0.5).coerceAtLeast(0.1)) },
        maximum = maximum.ifBlank { formatDecimal((amount * 1.5).coerceAtMost(5000.0)) }
    )
}

@Composable
private fun PlannedMealEditorScreen(
    foods: List<Food>,
    dishes: List<Dish>,
    existingMeals: List<PlannedMeal>,
    recommendation: es.david.rumbo.model.Recommendation?,
    initial: PlannedMeal? = null,
    initialType: MealType? = null,
    initialDays: Set<WeekDay> = emptySet(),
    preferredFoodIds: Set<Long>,
    preferredDishIds: Set<Long>,
    onCreateDish: (Dish) -> Unit,
    onSave: (PlannedMeal) -> Unit,
    onDelete: (() -> Unit)? = null
) {
    var type by remember(initial?.id, initialType) {
        mutableStateOf(initial?.type ?: initialType ?: MealType.BREAKFAST)
    }
    var selectedDays by remember(initial?.id, initialDays) {
        mutableStateOf(initial?.days ?: initialDays)
    }
    var itemAmounts by remember(initial?.id) {
        mutableStateOf(initial?.items?.associate {
            it.foodId to AmountDraft(
                formatDecimal(it.grams), it.adjustable,
                formatDecimal(it.minimumGrams), formatDecimal(it.maximumGrams)
            )
        }.orEmpty())
    }
    var dishAmounts by remember(initial?.id) {
        mutableStateOf(initial?.dishes?.associate {
            it.dishId to AmountDraft(
                formatDecimal(it.grams), it.adjustable,
                formatDecimal(it.minimumGrams), formatDecimal(it.maximumGrams)
            )
        }.orEmpty())
    }
    var choosingElement by remember { mutableStateOf(false) }
    var selectedForDish by remember { mutableStateOf(emptySet<Long>()) }
    var namingDish by remember { mutableStateOf(false) }
    var newDishName by remember { mutableStateOf("") }
    var confirmDelete by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val foodsById = remember(foods) { foods.associateBy { it.id } }
    val dishesById = remember(dishes) { dishes.associateBy { it.id } }
    val occupiedDays = existingMeals.asSequence()
        .filter { it.id != initial?.id && it.type == type }
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
                days = selectedDays.ifEmpty { setOf(WeekDay.MONDAY) },
                items = previewItems,
                dishes = previewDishes
            ),
            foodsById,
            dishesById,
            recommendation
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
        Text(
            if (initial == null) "Nueva comida" else "Editar comida",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold
        )
        SelectorField(
            label = "Tipo de comida",
            selectedLabel = type.label,
            options = MealType.entries,
            optionLabel = { it.label },
            onSelect = { newType ->
                type = newType
                val unavailable = existingMeals.asSequence()
                    .filter { it.id != initial?.id && it.type == newType }
                    .flatMap { it.days.asSequence() }
                    .toSet()
                selectedDays = selectedDays - unavailable
            },
            onClear = null
        )
        Text("Días", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        WeekDay.entries.chunked(4).forEach { rowDays ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                rowDays.forEach { day ->
                    FilterChip(
                        selected = day in selectedDays,
                        onClick = {
                            selectedDays = if (day in selectedDays) selectedDays - day else selectedDays + day
                        },
                        enabled = day !in occupiedDays,
                        label = { Text(day.shortLabel) },
                        modifier = Modifier.weight(1f)
                    )
                }
                repeat(4 - rowDays.size) { Spacer(Modifier.weight(1f)) }
            }
        }
        if (occupiedDays.isNotEmpty()) {
            Text(
                "Los días desactivados ya tienen ${type.label.lowercase()}.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        HorizontalDivider()
        Text("Elementos de la comida", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        dishAmounts.forEach { (dishId, draft) ->
            val dish = dishesById[dishId]
            if (dish != null) {
                Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        SmallFoodCategoryBadge(dish.dominantCategory(foodsById))
                        Text(dish.name, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                        TextButton(onClick = { dishAmounts = dishAmounts - dishId }) { Text("Quitar") }
                    }
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        NumericField(
                            "Gramos", draft.grams,
                            { dishAmounts = dishAmounts + (dishId to draft.copy(grams = it)) },
                            Modifier.weight(1f)
                        )
                        FilterChip(
                            selected = draft.adjustable,
                            onClick = {
                                dishAmounts = dishAmounts +
                                    (dishId to draft.withAdjustable(!draft.adjustable))
                            },
                            label = { Text(if (draft.adjustable) "Ajustable" else "Fijo") }
                        )
                    }
                    if (draft.adjustable) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            NumericField(
                                "Mínimo", draft.minimum,
                                { dishAmounts = dishAmounts + (dishId to draft.copy(minimum = it)) },
                                Modifier.weight(1f)
                            )
                            NumericField(
                                "Máximo", draft.maximum,
                                { dishAmounts = dishAmounts + (dishId to draft.copy(maximum = it)) },
                                Modifier.weight(1f)
                            )
                        }
                    }
                }
            }
        }
        itemAmounts.forEach { (foodId, draft) ->
            val food = foodsById[foodId]
            if (food != null) {
                Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Checkbox(
                            checked = foodId in selectedForDish,
                            onCheckedChange = { checked ->
                                selectedForDish = if (checked) selectedForDish + foodId else selectedForDish - foodId
                            }
                        )
                        SmallFoodCategoryBadge(food.category)
                        Text(food.name, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                        TextButton(onClick = {
                            itemAmounts = itemAmounts - foodId
                            selectedForDish = selectedForDish - foodId
                        }) { Text("Quitar") }
                    }
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        NumericField(
                            "Gramos", draft.grams,
                            { itemAmounts = itemAmounts + (foodId to draft.copy(grams = it)) },
                            Modifier.weight(1f)
                        )
                        FilterChip(
                            selected = draft.adjustable,
                            onClick = {
                                itemAmounts = itemAmounts +
                                    (foodId to draft.withAdjustable(!draft.adjustable))
                            },
                            label = { Text(if (draft.adjustable) "Ajustable" else "Fijo") }
                        )
                    }
                    if (draft.adjustable) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            NumericField(
                                "Mínimo", draft.minimum,
                                { itemAmounts = itemAmounts + (foodId to draft.copy(minimum = it)) },
                                Modifier.weight(1f)
                            )
                            NumericField(
                                "Máximo", draft.maximum,
                                { itemAmounts = itemAmounts + (foodId to draft.copy(maximum = it)) },
                                Modifier.weight(1f)
                            )
                        }
                    }
                }
            }
        }
        OutlinedButton(onClick = { choosingElement = true }, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Default.Add, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("Añadir")
        }
        if (selectedForDish.size >= 2) {
            FilledTonalButton(
                onClick = {
                    newDishName = ""
                    namingDish = true
                },
                modifier = Modifier.fillMaxWidth()
            ) { Text("Crear plato con ${selectedForDish.size} alimentos") }
        } else if (itemAmounts.size >= 2) {
            Text(
                "Marca dos o más alimentos para convertirlos en un plato.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        if (itemAmounts.values.any { it.adjustable } || dishAmounts.values.any { it.adjustable }) {
            Text(
                "Las cantidades fijas serán iguales todos los días. Las ajustables podrán variar entre el mínimo y el máximo cuando pulses «Ajustar cantidades» en el plan.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        previewAssessment?.let { assessment ->
            HorizontalDivider()
            Text("Ajuste de esta comida", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                "Referencia orientativa de esta toma; el ajuste automático se decide con el total del día.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            NutritionTargetLine(assessment)
            Text(
                assessment.overall.fitLabel(),
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                color = assessment.overall.fitColor()
            )
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(
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
                            days = selectedDays,
                            items = parsedItems,
                            dishes = parsedDishes,
                            dayAmounts = initial?.dayAmounts.orEmpty()
                        ).sanitizedDayAmounts()
                    )
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) { Text("Guardar comida") }
        if (onDelete != null) {
            TextButton(onClick = { confirmDelete = true }, modifier = Modifier.fillMaxWidth()) {
                Text("Eliminar comida", color = MaterialTheme.colorScheme.error)
            }
        }
    }
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
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    var confirmDelete by remember { mutableStateOf(false) }
    val foodsById = remember(foods) { foods.associateBy { it.id } }
    val totals = dish.nutrition(foodsById)
    val totalWeight = dish.totalWeightGrams()
    val per100Factor = if (totalWeight > 0.0) 100.0 / totalWeight else 0.0
    val category = dish.dominantCategory(foodsById)

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
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            FoodCategoryBadge(category)
            Column(Modifier.weight(1f)) {
                Text(dish.name, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text(
                    "Predomina ${category.label.lowercase()} · ${formatDecimal(totalWeight)} g en total",
                    color = foodCategoryColor(category),
                    fontWeight = FontWeight.SemiBold
                )
            }
        }
        HorizontalDivider()
        Text("Plato completo", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(
            "${formatDecimal(totals.calories)} kcal",
            style = MaterialTheme.typography.headlineLarge,
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.Bold
        )
        NutritionLine("Grasas", totals.fatGrams)
        NutritionLine("Carbohidratos", totals.carbohydrateGrams)
        NutritionLine("Proteínas", totals.proteinGrams)
        NutritionLine("Fibra", totals.fiberGrams)
        if (!totals.isComplete) {
            Text(
                "El resultado es parcial porque algún ingrediente no tiene todos sus datos nutricionales.",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall
            )
        }
        HorizontalDivider()
        Text("Valores por 100 g", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        Text(
            "${formatDecimal(totals.calories * per100Factor)} kcal",
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.Bold
        )
        NutritionLine("Grasas", totals.fatGrams * per100Factor)
        NutritionLine("Carbohidratos", totals.carbohydrateGrams * per100Factor)
        NutritionLine("Proteínas", totals.proteinGrams * per100Factor)
        NutritionLine("Fibra", totals.fiberGrams * per100Factor)
        HorizontalDivider()
        Text("Ingredientes", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        dish.ingredients.forEach { ingredient ->
            val food = foodsById[ingredient.foodId]
            Row(
                Modifier.fillMaxWidth().padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                if (food != null) SmallFoodCategoryBadge(food.category) else Spacer(Modifier.size(24.dp))
                Text(food?.name ?: "Alimento eliminado", modifier = Modifier.weight(1f))
                Text("${formatDecimal(ingredient.grams)} g", fontWeight = FontWeight.SemiBold)
            }
        }
        Button(onClick = onEdit, modifier = Modifier.fillMaxWidth()) { Text("Editar plato") }
        TextButton(onClick = { confirmDelete = true }, modifier = Modifier.fillMaxWidth()) {
            Text("Eliminar plato", color = MaterialTheme.colorScheme.error)
        }
    }
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
        OutlinedButton(onClick = { choosingFood = true }, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Default.Add, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("Añadir ingrediente")
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
private fun FoodsScreen(
    foods: List<Food>,
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
