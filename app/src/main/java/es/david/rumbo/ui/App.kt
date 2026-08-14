@file:OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)

package es.david.rumbo.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.BackHandler
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.input.TextFieldState
import androidx.compose.foundation.text.input.rememberTextFieldState
import androidx.compose.foundation.text.input.setTextAndPlaceCursorAtEnd
import androidx.compose.foundation.verticalScroll
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.togetherWith
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
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Eco
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.FitnessCenter
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.Grain
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.LocalFlorist
import androidx.compose.material.icons.filled.LocalFireDepartment
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Opacity
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material.icons.filled.Restaurant
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.ShoppingCart
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AppBarWithSearch
import androidx.compose.material3.ExpandedFullScreenSearchBar
import androidx.compose.material3.SearchBarScrollBehavior
import androidx.compose.material3.SearchBarState
import androidx.compose.material3.SearchBarValue
import androidx.compose.material3.rememberSearchBarState
import androidx.compose.material3.Button
import androidx.compose.material3.Card as MaterialCard
import androidx.compose.material3.CardColors
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CardElevation
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.LargeTopAppBar
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ScaffoldDefaults
import androidx.compose.material3.SearchBar
import androidx.compose.material3.SearchBarDefaults
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberTopAppBarState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.listSaver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.foundation.Image
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
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
import es.david.rumbo.logic.FoodSuggestion
import es.david.rumbo.logic.FoodSuggestionEngine
import es.david.rumbo.logic.EfficientNutrient
import es.david.rumbo.logic.MealPlanEvaluator
import es.david.rumbo.logic.MealQuantityOptimizer
import es.david.rumbo.logic.NutrientKind
import es.david.rumbo.logic.NutritionTolerancePolicy
import es.david.rumbo.logic.PlanNutritionAssessment
import es.david.rumbo.logic.QuantityOptimizationResult
import es.david.rumbo.logic.RepertoireAssessment
import es.david.rumbo.logic.RepertoireEvaluator
import es.david.rumbo.logic.RepertoireStatus
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.abs
import kotlin.math.pow
import kotlin.math.roundToInt

@Composable
private fun Card(
    modifier: Modifier = Modifier,
    shape: Shape = CardDefaults.shape,
    colors: CardColors = CardDefaults.cardColors(
        containerColor = MaterialTheme.colorScheme.surfaceContainerHigh
    ),
    elevation: CardElevation = CardDefaults.cardElevation(),
    border: BorderStroke? = null,
    content: @Composable ColumnScope.() -> Unit
) {
    MaterialCard(
        modifier = modifier,
        shape = shape,
        colors = colors,
        elevation = elevation,
        border = border,
        content = content
    )
}

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
    SHOPPING_LIST("Lista de la compra", Icons.Default.ShoppingCart, false),
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
    var foodNavigationStack by rememberSaveable { mutableStateOf(emptyList<Long>()) }
    var selectedPlannedMealId by rememberSaveable { mutableStateOf<Long?>(null) }
    var selectedDishId by rememberSaveable { mutableStateOf<Long?>(null) }
    var draftMealTypeName by rememberSaveable { mutableStateOf<String?>(null) }
    var plannerWeekName by rememberSaveable { mutableStateOf(PlanWeek.CURRENT.name) }
    var shoppingWeekName by rememberSaveable { mutableStateOf(PlanWeek.CURRENT.name) }
    var shoppingCurrentOnly by rememberSaveable { mutableStateOf(false) }
    var draftMealDayName by rememberSaveable { mutableStateOf<String?>(null) }
    var draftFoodId by rememberSaveable { mutableStateOf<Long?>(null) }
    var draftDishId by rememberSaveable { mutableStateOf<Long?>(null) }
    var draftDishFoodId by rememberSaveable { mutableStateOf<Long?>(null) }
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
    var addingMeasurement by rememberSaveable { mutableStateOf(false) }
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
            screen == Screen.ADD_DISH && dishReturnScreenName != null -> {
                draftDishFoodId = null
                val destination = dishReturnScreenName!!
                dishReturnScreenName = null
                destination
            }
            screen in setOf(Screen.ADD_DISH, Screen.DISH_DETAIL) -> Screen.FOODS.name
            screen == Screen.FOOD_DETAIL && foodNavigationStack.isNotEmpty() -> {
                selectedFoodId = foodNavigationStack.last()
                foodNavigationStack = foodNavigationStack.dropLast(1)
                Screen.FOOD_DETAIL.name
            }
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

    val plannerTopAppBarState = rememberTopAppBarState()
    val plannerScrollBehavior = TopAppBarDefaults.enterAlwaysScrollBehavior(plannerTopAppBarState)

    Scaffold(
        modifier = if (screen == Screen.PLANNER) {
            Modifier.nestedScroll(plannerScrollBehavior.nestedScrollConnection)
        } else {
            Modifier
        },
        contentWindowInsets = if (screen in setOf(Screen.HOME, Screen.SHOPPING_LIST, Screen.PLANNER, Screen.FOOD_DETAIL)) {
            WindowInsets(0, 0, 0, 0)
        } else {
            ScaffoldDefaults.contentWindowInsets
        },
        topBar = {
            if (screen != Screen.HOME && screen !in setOf(Screen.ADD, Screen.EDIT_MEASUREMENT, Screen.SHOPPING_LIST, Screen.FOOD_DETAIL)) TopAppBar(
                navigationIcon = {
                    if (!screen.inNavigation) {
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
                            Text(
                                if (plannerWeekName == PlanWeek.NEXT.name) "Menú de la semana que viene"
                                else "Menú de esta semana",
                                fontWeight = FontWeight.SemiBold
                            )
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
                                        text = { Text("Crear plato con este alimento") },
                                        onClick = {
                                            detailMenuExpanded = false
                                            draftDishFoodId = selectedFoodId
                                            dishReturnScreenName = Screen.FOOD_DETAIL.name
                                            screenName = Screen.ADD_DISH.name
                                        }
                                    )
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
                },
                scrollBehavior = if (screen == Screen.PLANNER) plannerScrollBehavior else null
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) }
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            AnimatedContent(
                targetState = if (screenName == Screen.FOOD_DETAIL.name) {
                    "$screenName:${selectedFoodId ?: 0L}"
                } else {
                    screenName
                },
                transitionSpec = { fadeIn() togetherWith fadeOut() },
                label = "Navegación"
            ) { animatedScreenKey ->
            val animatedScreenName = animatedScreenKey.substringBefore(":")
            val screen = Screen.valueOf(animatedScreenName)
            screenStateHolder.SaveableStateProvider(animatedScreenKey) {
            when {
                !profileReady -> ProfileScreen(
                    profile = data.profile,
                    profiles = data.profiles.map { it.profile },
                    isOnboarding = data.profile == null,
                    mealShares = mealShares,
                    onCreate = { profile, shares ->
                        data = repository.saveProfile(profile)
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
                    mealShares = mealShares,
                    onSwitchProfile = {
                        data = repository.switchProfile(it)
                        screenName = if (data.isActiveProfileReady) Screen.HOME.name else Screen.PROFILE.name
                    },
                    onManageProfiles = { screenName = Screen.PROFILE.name },
                    onOpenShoppingList = {
                        shoppingCurrentOnly = false
                        shoppingWeekName = PlanWeek.CURRENT.name
                        screenName = Screen.SHOPPING_LIST.name
                    },
                    onOpenCurrentShoppingList = {
                        shoppingCurrentOnly = false
                        shoppingWeekName = PlanWeek.CURRENT.name
                        screenName = Screen.SHOPPING_LIST.name
                    },
                    onOpenSettings = { screenName = Screen.SETTINGS.name },
                    onGoalChange = { data = repository.setWeeklyRate(it) },
                    onAddMeasurement = { addingMeasurement = true },
                    onExplainBody = { screenName = Screen.BODY_EXPLANATION.name },
                    onOpenNextWeek = {
                        plannerWeekName = PlanWeek.NEXT.name
                        screenName = Screen.PLANNER.name
                    },
                    onRegenerateWeek = {
                        if (currentRecommendation == null) {
                            "Necesitas una recomendación nutricional antes de generar el menú."
                        } else {
                            runCatching {
                                WeeklyMenuGenerator.generate(
                                    currentMeals = data.activeProfileData?.plannedMeals.orEmpty().filter { it.planWeek == PlanWeek.CURRENT },
                                    rules = data.activeProfileData?.planningRules.orEmpty(),
                                    history = data.activeProfileData?.menuHistory.orEmpty(),
                                    foodsById = data.foods.associateBy { it.id },
                                    dishesById = data.dishes.associateBy { it.id },
                                    recommendation = currentRecommendation,
                                    mealShares = mealShares
                                )
                            }.fold(
                                onSuccess = { result ->
                                    data = repository.applyGeneratedMenu(result, PlanWeek.CURRENT)
                                    null
                                },
                                onFailure = { it.message ?: "No se pudo generar una semana válida." }
                            )
                        }
                    },
                    onOpenMeal = {
                        plannerWeekName = PlanWeek.CURRENT.name
                        selectedPlannedMealId = it
                        screenName = Screen.EDIT_PLANNED_MEAL.name
                    },
                    onOpenFoods = { screenName = Screen.FOODS.name },
                    onOpenFood = {
                        selectedFoodId = it
                        foodNavigationStack = emptyList()
                        foodReturnScreenName = Screen.HOME.name
                        screenName = Screen.FOOD_DETAIL.name
                    },
                    onDismissFoodSuggestion = {
                        data = repository.dismissFoodSuggestion(it)
                    },
                    onOpenDish = {
                        selectedDishId = it
                        dishReturnScreenName = Screen.HOME.name
                        screenName = Screen.DISH_DETAIL.name
                    },
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
                    onDismiss = { screenName = Screen.HOME.name },
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
                            onDismiss = { screenName = Screen.MEASUREMENT_DETAIL.name },
                            onSave = {
                                data = repository.addMeasurement(it)
                                screenName = Screen.MEASUREMENT_DETAIL.name
                            }
                        )
                    }
                }
                screen == Screen.PLANNER -> {
                    val selectedWeek = PlanWeek.valueOf(plannerWeekName)
                    WeeklyMenuReplicaScreen(
                        meals = data.activeProfileData?.plannedMeals.orEmpty()
                            .filter { it.planWeek == selectedWeek },
                        foodsById = data.foods.associateBy { it.id },
                        dishesById = data.dishes.associateBy { it.id },
                        recommendation = currentRecommendation,
                        sectionTitle = "",
                        onOpenShoppingList = {
                            shoppingCurrentOnly = false
                            shoppingWeekName = selectedWeek.name
                            screenName = Screen.SHOPPING_LIST.name
                        },
                        onRegenerateWeek = {
                            if (currentRecommendation == null) {
                                "Necesitas una recomendación nutricional antes de generar el menú."
                            } else {
                                runCatching {
                                    WeeklyMenuGenerator.generate(
                                        currentMeals = data.activeProfileData?.plannedMeals.orEmpty()
                                            .filter { it.planWeek == selectedWeek },
                                        rules = data.activeProfileData?.planningRules.orEmpty(),
                                        history = data.activeProfileData?.menuHistory.orEmpty(),
                                        foodsById = data.foods.associateBy { it.id },
                                        dishesById = data.dishes.associateBy { it.id },
                                        recommendation = currentRecommendation,
                                        mealShares = mealShares
                                    )
                                }.fold(
                                    onSuccess = { result ->
                                        data = repository.applyGeneratedMenu(result, selectedWeek)
                                        null
                                    },
                                    onFailure = { it.message ?: "No se pudo generar una semana válida." }
                                )
                            }
                        },
                        onOpenMeal = { mealId ->
                            plannerWeekName = selectedWeek.name
                            selectedPlannedMealId = mealId
                            screenName = Screen.EDIT_PLANNED_MEAL.name
                        },
                        onOpenFood = {
                            selectedFoodId = it
                        foodNavigationStack = emptyList()
                            foodReturnScreenName = Screen.PLANNER.name
                            screenName = Screen.FOOD_DETAIL.name
                        },
                        onOpenDish = {
                            selectedDishId = it
                            dishReturnScreenName = Screen.PLANNER.name
                            screenName = Screen.DISH_DETAIL.name
                        },
                        onApplyAdjustedMeals = { adjustedMeals ->
                            data = repository.savePlannedMeals(adjustedMeals, selectedWeek)
                        }
                    )
                }
                screen == Screen.AUTO_PLANNING -> AutomaticPlanningScreen(
                    rules = data.activeProfileData?.planningRules.orEmpty(),
                    repertoireFoodIds = data.activeProfileData?.repertoireFoodIds.orEmpty(),
                    foods = data.foods,
                    dishes = data.dishes,
                    recommendation = currentRecommendation,
                    mealShares = mealShares,
                    onSaveRule = { data = repository.savePlanningRule(it) },
                    onDeleteRule = { ruleId -> data = repository.deletePlanningRule(ruleId) },
                    onAddToRepertoire = { data = repository.addToRepertoire(it) },
                    onRemoveFromRepertoire = { data = repository.removeFromRepertoire(it) },
                    onSetActive = { id, active -> data = repository.setRepertoireFoodActive(id, active) },
                    onReplace = { oldId, newId -> data = repository.replaceRepertoireFood(oldId, newId) }
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
                        foodNavigationStack = emptyList()
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
                        foodNavigationStack = emptyList()
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
                    initialFoodId = draftDishFoodId,
                    preferredFoodIds = preferredFoodIds,
                    onSave = {
                        data = repository.saveDish(it)
                        draftDishFoodId = null
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
                        foodNavigationStack = emptyList()
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
                            onSaveDish = { data = repository.saveDish(it) },
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
                    planningRules = data.activeProfileData?.planningRules.orEmpty(),
                    repertoireFoodIds = data.activeProfileData?.repertoireFoodIds.orEmpty(),
                    onOpenFood = {
                        selectedFoodId = it
                        foodNavigationStack = emptyList()
                        foodReturnScreenName = null
                        screenName = Screen.FOOD_DETAIL.name
                    },
                    onOpenDish = {
                        selectedDishId = it
                        dishReturnScreenName = null
                        screenName = Screen.DISH_DETAIL.name
                    },
                    onAddFood = { screenName = Screen.ADD_FOOD.name },
                    onAddDish = {
                        draftDishFoodId = null
                        dishReturnScreenName = null
                        screenName = Screen.ADD_DISH.name
                    }
                )
                screen == Screen.ADD_FOOD -> FoodEditorScreen(
                    foods = data.foods,
                    onSave = {
                        data = repository.saveFood(it)
                        selectedFoodId = it.id
                        foodNavigationStack = emptyList()
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
                            activeMealTypes = mealShares.filterValues { it > 0.0 }.keys,
                            onBack = navigateBack,
                            plannedMeals = data.activeProfileData?.plannedMeals.orEmpty(),
                            dishes = data.dishes,
                            onOpenFood = {
                                selectedFoodId?.let { current ->
                                    foodNavigationStack = foodNavigationStack + current
                                }
                                selectedFoodId = it
                            },
                            onOpenDish = {
                                selectedDishId = it
                                dishReturnScreenName = Screen.FOOD_DETAIL.name
                                screenName = Screen.DISH_DETAIL.name
                            },
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
                            onAddDish = {
                                draftDishFoodId = food.id
                                dishReturnScreenName = Screen.FOOD_DETAIL.name
                                screenName = Screen.ADD_DISH.name
                            },
                            planningRules = data.activeProfileData?.planningRules?.filter {
                                it.itemKind == PlannedItemKind.FOOD && it.itemId == food.id
                            }.orEmpty(),
                            onSavePlanningRule = { data = repository.savePlanningRule(it) },
                            onDeletePlanningRule = { data = repository.deletePlanningRule(it) },
                            onSaveFood = { data = repository.saveFood(it) },
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
                    mealShares = mealShares,
                    onCreate = { profile, shares ->
                        data = repository.saveProfile(profile)
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
                screen == Screen.SHOPPING_LIST -> ShoppingListScreen(
                    data = data,
                    week = PlanWeek.valueOf(shoppingWeekName),
                    onWeekChange = { shoppingWeekName = it.name },
                    showWeekSelector = true,
                    onBack = { shoppingCurrentOnly = false; screenName = Screen.HOME.name }
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

    if (addingMeasurement) {
        AddMeasurementScreen(
            data = data,
            onDismiss = { addingMeasurement = false },
            onSave = {
                data = repository.addMeasurement(it)
                addingMeasurement = false
            }
        )
    }
}

@Composable
private fun ProfileSwitcher(
    profiles: List<UserProfile>,
    activeProfile: UserProfile?,
    onSelect: (Long) -> Unit,
    onManage: () -> Unit,
    onShoppingList: () -> Unit,
    onSettings: () -> Unit,
    avatarSize: Int = 36
) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        IconButton(onClick = { expanded = true }) {
            ProfileAvatar(activeProfile, avatarSize.dp)
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
                leadingIcon = { Icon(Icons.Default.ShoppingCart, contentDescription = null) },
                text = { Text("Lista de la compra") },
                onClick = {
                    expanded = false
                    onShoppingList()
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

@Composable
private fun ProfileAvatar(profile: UserProfile?, size: androidx.compose.ui.unit.Dp) {
    val context = LocalContext.current
    val bitmap = remember(profile?.photoUri) {
        profile?.photoUri?.let { uri -> runCatching {
            context.contentResolver.openInputStream(android.net.Uri.parse(uri))?.use {
                android.graphics.BitmapFactory.decodeStream(it)
            }
        }.getOrNull() }
    }
    if (bitmap != null) {
        Image(
            bitmap = bitmap!!.asImageBitmap(),
            contentDescription = profile?.name,
            contentScale = ContentScale.Crop,
            modifier = Modifier.size(size).clip(CircleShape)
        )
    } else Box(
        Modifier.size(size).background(profileColor(profile?.id), CircleShape),
        contentAlignment = Alignment.Center
    ) {
        Text(
            profile?.name?.trim()?.firstOrNull()?.uppercase() ?: "?",
            color = Color.White,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold
        )
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
    mealShares: Map<MealType, Double>,
    onSwitchProfile: (Long) -> Unit,
    onManageProfiles: () -> Unit,
    onOpenShoppingList: () -> Unit,
    onOpenCurrentShoppingList: () -> Unit,
    onOpenSettings: () -> Unit,
    onGoalChange: (Double?) -> Unit,
    onAddMeasurement: () -> Unit,
    onExplainBody: () -> Unit,
    onOpenNextWeek: () -> Unit,
    onRegenerateWeek: () -> String?,
    onOpenMeal: (Long) -> Unit,
    onOpenFood: (Long) -> Unit,
    onDismissFoodSuggestion: (Long) -> Unit,
    onOpenDish: (Long) -> Unit,
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
    val repertoireAssessment by produceState<RepertoireAssessment?>(
        initialValue = null,
        data.activeProfileData?.planningRules,
        data.foods,
        data.dishes,
        recommendation,
        mealShares
    ) {
        value = recommendation?.let { target ->
            withContext(Dispatchers.Default) {
                RepertoireEvaluator.evaluate(
                    rules = data.activeProfileData?.planningRules.orEmpty(),
                    foodsById = foodsById,
                    dishesById = dishesById,
                    recommendation = target,
                    mealShares = mealShares
                )
            }
        }
    }
    val candidateAssessments by produceState<Map<Long, RepertoireAssessment>?>(
        initialValue = null,
        repertoireAssessment,
        data.foods,
        data.activeProfileData?.repertoireFoodIds,
        data.activeProfileData?.dismissedSuggestionFoodIds,
        data.activeProfileData?.planningRules,
        recommendation,
        mealShares
    ) {
        val baseline = repertoireAssessment
        val target = recommendation
        value = if (baseline == null || target == null) {
            emptyMap()
        } else {
            withContext(Dispatchers.Default) {
                val shortlist = FoodSuggestionEngine.suggest(
                    foods = data.foods,
                    repertoireFoodIds = data.activeProfileData?.repertoireFoodIds.orEmpty(),
                    planningRules = data.activeProfileData?.planningRules.orEmpty(),
                    plannedMeals = emptyList(),
                    dishesById = dishesById,
                    recommendation = target,
                    excludedFoodIds = data.activeProfileData
                        ?.dismissedSuggestionFoodIds.orEmpty(),
                    repertoireAssessment = baseline,
                    limit = 12
                ).map { it.food }
                RepertoireEvaluator.evaluateCandidates(
                    rules = data.activeProfileData?.planningRules.orEmpty(),
                    candidates = shortlist,
                    foodsById = foodsById,
                    dishesById = dishesById,
                    recommendation = target,
                    mealShares = mealShares
                )
            }
        }
    }
    val foodSuggestions = remember(
        data.foods,
        data.activeProfileData?.repertoireFoodIds,
        data.activeProfileData?.dismissedSuggestionFoodIds,
        data.activeProfileData?.planningRules,
        data.dishes,
        recommendation,
        repertoireAssessment,
        candidateAssessments
    ) {
        FoodSuggestionEngine.suggest(
            foods = data.foods,
            repertoireFoodIds = data.activeProfileData?.repertoireFoodIds.orEmpty(),
            planningRules = data.activeProfileData?.planningRules.orEmpty(),
            plannedMeals = emptyList(),
            dishesById = dishesById,
            recommendation = recommendation,
            excludedFoodIds = data.activeProfileData?.dismissedSuggestionFoodIds.orEmpty(),
            repertoireAssessment = repertoireAssessment,
            candidateAssessments = candidateAssessments,
            limit = 100
        )
    }
    val searchTextState = rememberTextFieldState()
    var searchFilter by rememberSaveable { mutableStateOf(CatalogFilter.ALL) }
    var searchMessage by remember { mutableStateOf<String?>(null) }
    val searchBarState = rememberSearchBarState()
    val searchListState = rememberLazyListState()
    var suppressRestoredSearchKeyboard by rememberSaveable { mutableStateOf(false) }
    val searchScrollBehavior = SearchBarDefaults.enterAlwaysSearchBarScrollBehavior()
    val searchScope = rememberCoroutineScope()
    val closeSearch = {
        searchTextState.setTextAndPlaceCursorAtEnd("")
        searchMessage = null
        searchScrollBehavior.scrollOffset = 0f
        searchScrollBehavior.contentOffset = 0f
        searchScope.launch { searchBarState.animateToCollapsed() }
        Unit
    }

    Scaffold(
        modifier = Modifier.fillMaxSize().nestedScroll(searchScrollBehavior.nestedScrollConnection),
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            HomeCatalogSearch(
                foods = data.foods,
                dishes = data.dishes,
                repertoireFoodIds = data.activeProfileData?.repertoireFoodIds.orEmpty(),
                foodSuggestions = foodSuggestions,
                textFieldState = searchTextState,
                filter = searchFilter,
                onFilterChange = { searchFilter = it },
                scanMessage = searchMessage,
                onScanMessageChange = { searchMessage = it },
                state = searchBarState,
                listState = searchListState,
                suppressRestoredKeyboard = suppressRestoredSearchKeyboard,
                onRestoredKeyboardSuppressed = { suppressRestoredSearchKeyboard = false },
                scrollBehavior = searchScrollBehavior,
                onCloseSearch = closeSearch,
                onOpenFood = {
                    suppressRestoredSearchKeyboard = true
                    onOpenFood(it)
                },
                onOpenDish = {
                    suppressRestoredSearchKeyboard = true
                    onOpenDish(it)
                },
                trailingContent = {
                    ProfileSwitcher(
                        profiles = data.profiles.map { it.profile },
                        activeProfile = data.profile,
                        onSelect = onSwitchProfile,
                        onManage = onManageProfiles,
                        onShoppingList = onOpenShoppingList,
                        onSettings = onOpenSettings,
                        avatarSize = 36
                    )
                }
            )
        }
    ) { innerPadding ->
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(innerPadding),
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
        if (foodSuggestions.isNotEmpty()) {
            item {
                FoodSuggestionsCard(
                    suggestions = foodSuggestions.take(3),
                    onOpenFood = onOpenFood,
                    onDismiss = onDismissFoodSuggestion
                )
            }
        }
        item {
            WeeklyHomeMenuSection(
                meals = meals,
                foodsById = foodsById,
                dishesById = dishesById,
                recommendation = recommendation,
                sectionTitle = "Tu menú de esta semana",
                repertoireWarning = repertoireCoverageWarning(
                    repertoireAssessment,
                    data.activeProfileData?.planningRules.orEmpty(),
                    foodsById
                ),
                onOpenNextWeek = onOpenNextWeek,
                onOpenCurrentShoppingList = onOpenCurrentShoppingList,
                onRegenerateWeek = onRegenerateWeek,
                onOpenMeal = onOpenMeal,
                onOpenFood = onOpenFood,
                onOpenDish = onOpenDish,
                onApplyAdjustedMeals = onApplyAdjustedMeals
            )
        }
        }
    }
}

@Composable
private fun FoodSuggestionsCard(
    suggestions: List<FoodSuggestion>,
    onOpenFood: (Long) -> Unit,
    onDismiss: (Long) -> Unit
) {
    Column(
        Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text("Tus alimentos recomendados", style = MaterialTheme.typography.titleLarge)
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp)) {
                repeat(3) { index ->
                    val suggestion = suggestions.getOrNull(index)
                    var displayedSuggestion by remember(index) {
                        mutableStateOf(suggestion)
                    }
                    if (suggestion != null) displayedSuggestion = suggestion
                    AnimatedVisibility(
                        visible = suggestion != null,
                        enter = fadeIn() + expandVertically(),
                        exit = fadeOut() + shrinkVertically()
                    ) {
                        displayedSuggestion?.let { currentSuggestion ->
                            Column {
                                if (index > 0) {
                                    HorizontalDivider(
                                        color = MaterialTheme.colorScheme.outlineVariant
                                    )
                                }
                            AnimatedContent(
                                targetState = currentSuggestion,
                                transitionSpec = { fadeIn() togetherWith fadeOut() },
                                label = "Texto de recomendación"
                            ) { animatedSuggestion ->
                                Row(
                                    Modifier
                                        .fillMaxWidth()
                                        .clickable { onOpenFood(animatedSuggestion.food.id) }
                                        .padding(vertical = 12.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                                ) {
                                    Column(
                                        Modifier.weight(1f),
                                        verticalArrangement = Arrangement.spacedBy(2.dp)
                                    ) {
                                        Text(
                                            animatedSuggestion.food.name,
                                            style = MaterialTheme.typography.bodyLarge,
                                            fontWeight = FontWeight.SemiBold,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis
                                        )
                                        Text(
                                            animatedSuggestion.reason,
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis
                                        )
                                    }
                                    IconButton(
                                        onClick = { onDismiss(animatedSuggestion.food.id) }
                                    ) {
                                        Icon(
                                            Icons.Default.Close,
                                            contentDescription = "No me interesa",
                                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }
                                }
                            }
                            }
                        }
                    }
                }
            }
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
                "Añade una medición",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            HorizontalDivider()
            Text(
                when {
                    missingWeight && missingWaist ->
                        "Añade tu peso o tu cintura para que Rumbo pueda empezar a funcionar. Lo ideal es introducir ambos datos, porque así la valoración es más fiable."
                    missingWeight ->
                        "La cintura ya permite orientar el objetivo, pero con el peso también podremos calcular el IMC y las calorías que necesitas."
                    else ->
                        "El peso ya permite calcular las calorías, pero la cintura hará más precisa la valoración de la distribución abdominal."
                },
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            WaistMeasurementHelp()
            OutlinedButton(onClick = onAddMeasurement, modifier = Modifier.fillMaxWidth()) {
                Text("Añadir medición")
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
        ModalBottomSheet(onDismissRequest = { choosingGoal = false }) {
                Column(
                    Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(24.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    Text("Cambiar objetivo semanal", style = MaterialTheme.typography.headlineSmall)
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
                    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                        listOf(-1.0 to "Perder", 1.0 to "Ganar").forEachIndexed { index, (value, label) ->
                            SegmentedButton(
                                selected = manualDirection == value,
                                onClick = { manualDirection = value },
                                shape = SegmentedButtonDefaults.itemShape(index, 2)
                            ) { Text(label) }
                        }
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
                    Button(onClick = {
                    val magnitude = parseDecimal(manualMagnitude)
                    if (magnitude == null || !magnitude.isFinite() || magnitude < 0.0) {
                        manualError = "Introduce una cifra numérica válida."
                    } else {
                        onGoalChange(if (magnitude == 0.0) 0.0 else magnitude * manualDirection)
                        choosingGoal = false
                    }
                    }, Modifier.fillMaxWidth()) { Text("Usar esta cifra") }
                    TextButton(onClick = { choosingGoal = false }, Modifier.fillMaxWidth()) { Text("Cancelar") }
                    Spacer(Modifier.height(16.dp))
                }
        }
    }
    Text("Tu objetivo", style = MaterialTheme.typography.titleLarge)
    Spacer(Modifier.height(12.dp))
    Card(Modifier.fillMaxWidth().clickable(onClick = onExplain)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
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
                Column(
                    Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Row(Modifier.fillMaxWidth()) {
                        HomeNutritionLegendMetric(
                            label = "Calorías",
                            value = "${recommendation.calories} kcal",
                            icon = Icons.Default.LocalFireDepartment,
                            modifier = Modifier.weight(1f)
                        )
                        HomeNutritionLegendMetric(
                            label = "Proteínas",
                            value = "${recommendation.proteinGrams} g",
                            icon = foodCategoryIcon(FoodCategory.PROTEIN),
                            reverse = true,
                            modifier = Modifier.weight(1f)
                        )
                    }
                    Row(Modifier.fillMaxWidth()) {
                        HomeNutritionLegendMetric(
                            label = "Carbohidratos",
                            value = "${recommendation.carbohydrateGrams} g",
                            icon = foodCategoryIcon(FoodCategory.CARBOHYDRATE),
                            modifier = Modifier.weight(1f)
                        )
                        HomeNutritionLegendMetric(
                            label = "Grasas",
                            value = "${recommendation.fatGrams} g",
                            icon = foodCategoryIcon(FoodCategory.FAT),
                            reverse = true,
                            modifier = Modifier.weight(1f)
                        )
                    }
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
private fun HomeNutritionLegendMetric(
    label: String,
    value: String,
    icon: ImageVector,
    reverse: Boolean = false,
    modifier: Modifier = Modifier
) {
    val color = MaterialTheme.colorScheme.onSurfaceVariant
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = if (reverse) Arrangement.End else Arrangement.Start
    ) {
        if (!reverse) {
            Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(6.dp))
        }
        Text(
            if (reverse) "$value  $label" else "$label  $value",
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.SemiBold,
            color = color,
            maxLines = 1
        )
        if (reverse) {
            Spacer(Modifier.width(6.dp))
            Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(20.dp))
        }
    }
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
private fun WeeklyHomeMenuSection(
    meals: List<PlannedMeal>,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    recommendation: es.david.rumbo.model.Recommendation?,
    sectionTitle: String,
    onOpenNextWeek: (() -> Unit)?,
    onOpenCurrentShoppingList: () -> Unit,
    onRegenerateWeek: () -> String?,
    onOpenMeal: (Long) -> Unit,
    onOpenFood: (Long) -> Unit,
    onOpenDish: (Long) -> Unit,
    onApplyAdjustedMeals: (List<PlannedMeal>) -> Unit,
    repertoireWarning: String? = null
) {
    val today = WeekDay.entries[LocalDate.now().dayOfWeek.value - 1]
    val visibleDays = if (onOpenNextWeek != null) {
        WeekDay.entries.dropWhile { it != today }
    } else {
        WeekDay.entries
    }
    val summaryKey = "WEEKLY_SUMMARY"
    val hasMenu = meals.isNotEmpty()
    var expandedSection by rememberSaveable(today.name, hasMenu) {
        mutableStateOf(if (hasMenu) today.name else summaryKey)
    }
    var rebuildSheet by remember { mutableStateOf(false) }
    var optimizationPreview by remember { mutableStateOf<QuantityOptimizationResult?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    val weeklyAssessment = recommendation?.let {
        MealPlanEvaluator.assessWeek(meals, foodsById, dishesById, it)
    }

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
    message?.let { value ->
        AlertDialog(
            onDismissRequest = { message = null },
            title = { Text("Menú semanal") },
            text = { Text(value) },
            confirmButton = { TextButton(onClick = { message = null }) { Text("Entendido") } }
        )
    }
    if (rebuildSheet) {
        ModalBottomSheet(onDismissRequest = { rebuildSheet = false }) {
            Column(
                Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text("Rehacer menú semanal", style = MaterialTheme.typography.headlineSmall)
                Text("Elige cuánto quieres cambiar.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                FilledTonalButton(
                    onClick = {
                        rebuildSheet = false
                        if (recommendation == null) {
                            message = "Necesitas una recomendación nutricional antes de ajustar el menú."
                        } else {
                            val result = MealQuantityOptimizer.optimize(meals, foodsById, dishesById, recommendation)
                            if (result.changes.isNotEmpty()) optimizationPreview = result
                            else message = "Las cantidades actuales ya son la mejor combinación encontrada dentro de los límites indicados."
                        }
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Cambiar solo las cantidades") }
                OutlinedButton(
                    onClick = {
                        rebuildSheet = false
                        message = onRegenerateWeek()
                    },
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Cambiar también los platos") }
                TextButton(onClick = { rebuildSheet = false }, Modifier.fillMaxWidth()) { Text("Cancelar") }
                Spacer(Modifier.height(12.dp))
            }
        }
    }

    fun toggleSection(key: String) {
        expandedSection = if (expandedSection == key) "" else key
    }

    @Composable
    fun SectionHeader(
        title: String,
        subtitle: String?
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .padding(start = 16.dp, top = 16.dp, end = 16.dp, bottom = 8.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            subtitle?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }

    fun compactNutritionNumber(value: Double): String =
        if (abs(value) < 10.0) formatOneDecimal(value) else value.roundToInt().toString()

    fun nutrientAmount(valuePer100: Double?, grams: Double): String =
        valuePer100?.let { compactNutritionNumber(it * grams / 100.0) } ?: "—"

    @Composable
    fun CompactNutritionGridValues(
        calories: Double?,
        protein: Double?,
        carbohydrates: Double?,
        fat: Double?,
        modifier: Modifier = Modifier
    ) {
        val color = MaterialTheme.colorScheme.onSurfaceVariant

        @Composable
        fun LeftMetric(icon: ImageVector, label: String, value: String, modifier: Modifier) {
            Row(
                modifier,
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Start
            ) {
                Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(17.dp))
                Spacer(Modifier.width(2.dp))
                Text(value, style = MaterialTheme.typography.bodyLarge, color = color, maxLines = 1)
            }
        }

        @Composable
        fun RightMetric(icon: ImageVector, label: String, value: String, modifier: Modifier) {
            Row(
                modifier,
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.End
            ) {
                Text(value, style = MaterialTheme.typography.bodyLarge, color = color, maxLines = 1)
                Spacer(Modifier.width(2.dp))
                Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(17.dp))
            }
        }

        fun display(value: Double?): String = value?.let(::compactNutritionNumber) ?: "—"

        Column(modifier, verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                LeftMetric(
                    Icons.Default.LocalFireDepartment,
                    "Calorías",
                    display(calories),
                    Modifier.width(46.dp)
                )
                Spacer(Modifier.width(6.dp))
                RightMetric(
                    foodCategoryIcon(FoodCategory.PROTEIN),
                    "Proteínas",
                    display(protein),
                    Modifier.width(46.dp)
                )
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                LeftMetric(
                    foodCategoryIcon(FoodCategory.CARBOHYDRATE),
                    "Carbohidratos",
                    display(carbohydrates),
                    Modifier.width(46.dp)
                )
                Spacer(Modifier.width(6.dp))
                RightMetric(
                    foodCategoryIcon(FoodCategory.FAT),
                    "Grasas",
                    display(fat),
                    Modifier.width(46.dp)
                )
            }
        }
    }

    @Composable
    fun CompactNutritionGrid(food: Food, grams: Double, modifier: Modifier = Modifier) {
        val factor = grams / 100.0
        CompactNutritionGridValues(
            calories = food.calories?.times(factor),
            protein = food.proteinGrams?.times(factor),
            carbohydrates = food.carbohydrateGrams?.times(factor),
            fat = food.fatGrams?.times(factor),
            modifier = modifier
        )
    }

    @Composable
    fun FoodNutritionLine(food: Food, grams: Double, modifier: Modifier = Modifier) {
        Row(
            modifier
                .fillMaxWidth()
                .clickable { onOpenFood(food.id) }
                .padding(vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(
                    food.name,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    foodAmountLabel(food, grams),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1
                )
            }
            CompactNutritionGrid(food, grams, Modifier.width(98.dp))
        }
    }

    fun dishAmountLabelForHome(dish: Dish, grams: Double): String {
        val unitAmount = dish.unitAmount?.takeIf { it > 0.0 }
        val singular = dish.unitName?.trim()?.takeIf { it.isNotEmpty() }
        if (unitAmount != null && singular != null) {
            val count = grams / unitAmount
            val countLabel = if (abs(count - count.roundToInt()) < 0.01) {
                count.roundToInt().toString()
            } else compactNutritionNumber(count)
            val name = if (abs(count - 1.0) < 0.01) singular
            else dish.unitPlural?.trim()?.takeIf { it.isNotEmpty() } ?: singular
            return "$countLabel $name · ${formatDecimal(grams)} g"
        }
        return "${formatDecimal(grams)} g"
    }

    fun foodCategoryPriority(category: FoodCategory?): Int = when (category) {
        FoodCategory.PROTEIN -> 0
        FoodCategory.CARBOHYDRATE -> 1
        FoodCategory.FAT -> 2
        FoodCategory.VEGETABLE -> 3
        FoodCategory.FRUIT -> 4
        FoodCategory.OTHER, null -> 5
    }

    @Composable
    fun DishNutritionCard(dish: Dish, grams: Double) {
        val totalWeight = dish.totalWeightGrams().takeIf { it > 0.0 } ?: 1.0
        val totals = dish.nutritionForGrams(foodsById, grams)
        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .clickable { onOpenDish(dish.id) }
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        dish.name,
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                    Text(
                        dishAmountLabelForHome(dish, grams),
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1
                    )
                }
                CompactNutritionGridValues(
                    calories = totals.calories,
                    protein = totals.proteinGrams,
                    carbohydrates = totals.carbohydrateGrams,
                    fat = totals.fatGrams,
                    modifier = Modifier.width(98.dp)
                )
            }
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = MaterialTheme.colorScheme.surfaceContainer
            ) {
                Column(
                    Modifier.fillMaxWidth().padding(vertical = 6.dp),
                    verticalArrangement = Arrangement.spacedBy(2.dp)
                ) {
                    dish.ingredients
                        .sortedWith(
                            compareBy<DishIngredient> { foodCategoryPriority(foodsById[it.foodId]?.category) }
                                .thenBy { foodsById[it.foodId]?.name.orEmpty().lowercase() }
                        )
                        .forEach ingredientLoop@ { ingredient ->
                            val food = foodsById[ingredient.foodId] ?: return@ingredientLoop
                            val ingredientGrams = ingredient.grams * grams / totalWeight
                            FoodNutritionLine(
                                food,
                                ingredientGrams,
                                Modifier.padding(horizontal = 16.dp)
                            )
                        }
                }
            }
        }
    }

    @Composable
    fun AbsoluteNutritionSummary(assessment: PlanNutritionAssessment?) {
        val color = MaterialTheme.colorScheme.onSurfaceVariant
        val actual = assessment?.actual

        @Composable
        fun Metric(
            icon: ImageVector,
            label: String,
            text: String,
            arrangement: Arrangement.Horizontal,
            modifier: Modifier
        ) {
            Row(
                modifier,
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = arrangement
            ) {
                Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(4.dp))
                Text(
                    text,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = color,
                    maxLines = 1
                )
            }
        }

        Row(Modifier.fillMaxWidth()) {
            Metric(
                Icons.Default.LocalFireDepartment,
                "Calorías",
                actual?.calories?.let { "${compactNutritionNumber(it)} kcal" } ?: "—",
                Arrangement.Start,
                Modifier.weight(1.18f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.PROTEIN),
                "Proteínas",
                actual?.proteinGrams?.let { "${compactNutritionNumber(it)} g" } ?: "—",
                Arrangement.Center,
                Modifier.weight(0.94f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.CARBOHYDRATE),
                "Carbohidratos",
                actual?.carbohydrateGrams?.let { "${compactNutritionNumber(it)} g" } ?: "—",
                Arrangement.Center,
                Modifier.weight(0.94f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.FAT),
                "Grasas",
                actual?.fatGrams?.let { "${compactNutritionNumber(it)} g" } ?: "—",
                Arrangement.End,
                Modifier.weight(0.94f)
            )
        }
    }

    @Composable
    fun WeeklyPercentSummary(assessment: PlanNutritionAssessment) {
        val color = MaterialTheme.colorScheme.onSurfaceVariant
        fun percentage(actual: Double, target: Double): String =
            if (target <= 0.0) "—" else "${(actual / target * 100.0).roundToInt()} %"

        @Composable
        fun Metric(
            icon: ImageVector,
            label: String,
            value: String,
            arrangement: Arrangement.Horizontal,
            modifier: Modifier
        ) {
            Row(
                modifier,
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = arrangement
            ) {
                Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(4.dp))
                Text(
                    value,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = color,
                    maxLines = 1
                )
            }
        }

        Row(Modifier.fillMaxWidth()) {
            Metric(
                Icons.Default.LocalFireDepartment,
                "Calorías",
                percentage(assessment.actual.calories, assessment.target.calories),
                Arrangement.Start,
                Modifier.weight(1.18f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.PROTEIN),
                "Proteínas",
                percentage(assessment.actual.proteinGrams, assessment.target.proteinGrams),
                Arrangement.Center,
                Modifier.weight(0.94f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.CARBOHYDRATE),
                "Carbohidratos",
                percentage(assessment.actual.carbohydrateGrams, assessment.target.carbohydrateGrams),
                Arrangement.Center,
                Modifier.weight(0.94f)
            )
            Metric(
                foodCategoryIcon(FoodCategory.FAT),
                "Grasas",
                percentage(assessment.actual.fatGrams, assessment.target.fatGrams),
                Arrangement.End,
                Modifier.weight(0.94f)
            )
        }
    }

    @Composable
    fun SummarySection(expanded: Boolean) {
        Column(Modifier.fillMaxWidth()) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .clickable { toggleSection(summaryKey) }
            ) {
                SectionHeader(
                    title = "Valoración nutricional",
                    subtitle = null
                )
                weeklyAssessment?.let {
                    Box(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 14.dp)) {
                        WeeklyPercentSummary(it)
                    }
                }
            }
            AnimatedVisibility(
                visible = expanded,
                enter = expandVertically(expandFrom = Alignment.Top) + fadeIn(),
                exit = shrinkVertically(shrinkTowards = Alignment.Top) + fadeOut()
            ) {
                Column(
                    Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text(
                        weeklyAssessmentText(weeklyAssessment),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    repertoireWarning?.let {
                        Text(
                            it,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                    }
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        OutlinedButton(
                            onClick = {
                                if (hasMenu) rebuildSheet = true
                                else message = onRegenerateWeek()
                            },
                            modifier = Modifier.weight(1f)
                        ) { Text(if (hasMenu) "Cambiar menú" else "Crear menú") }
                        OutlinedButton(
                            onClick = onOpenCurrentShoppingList,
                            modifier = Modifier.weight(1f)
                        ) { Text("Lista de la compra") }
                    }
                }
            }
        }
    }

    @Composable
    fun DaySection(day: WeekDay, expanded: Boolean) {
        val dayMeals = meals.filter { day in it.days }.associateBy { it.type }
        val assessment = recommendation?.let {
            MealPlanEvaluator.assessDay(day, meals, foodsById, dishesById, it)
        }

        Column(Modifier.fillMaxWidth()) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .clickable { toggleSection(day.name) }
            ) {
                SectionHeader(
                    title = day.label,
                    subtitle = null
                )
                Box(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 14.dp)) {
                    AbsoluteNutritionSummary(assessment)
                }
            }
            AnimatedVisibility(
                visible = expanded,
                enter = expandVertically(expandFrom = Alignment.Top) + fadeIn(),
                exit = shrinkVertically(shrinkTowards = Alignment.Top) + fadeOut()
            ) {
                Column(
                    Modifier.fillMaxWidth().padding(bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    HorizontalDivider(
                        modifier = Modifier.padding(horizontal = 16.dp),
                        color = MaterialTheme.colorScheme.outlineVariant
                    )
                    if (dayMeals.isEmpty()) {
                        Text(
                            "No hay comidas planificadas.",
                            modifier = Modifier.padding(horizontal = 16.dp),
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    val visibleTypes = MealType.entries.filter { dayMeals[it] != null }
                    visibleTypes.forEachIndexed { index, type ->
                        val meal = dayMeals[type] ?: return@forEachIndexed
                        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(
                                type.label,
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier
                                    .padding(horizontal = 16.dp)
                                    .clickable { onOpenMeal(meal.id) }
                            )
                            meal.dishes.forEach dishLoop@ { planned ->
                                val dish = dishesById[planned.dishId] ?: return@dishLoop
                                DishNutritionCard(dish, meal.resolvedGrams(planned, day))
                            }
                            meal.items
                                .sortedWith(
                                    compareBy<PlannedFood> { foodCategoryPriority(foodsById[it.foodId]?.category) }
                                        .thenBy { foodsById[it.foodId]?.name.orEmpty().lowercase() }
                                )
                                .forEach foodLoop@ { planned ->
                                    val food = foodsById[planned.foodId] ?: return@foodLoop
                                    FoodNutritionLine(
                                        food,
                                        meal.resolvedGrams(planned, day),
                                        Modifier.padding(horizontal = 16.dp)
                                    )
                                }
                        }
                        if (index < visibleTypes.lastIndex) {
                            HorizontalDivider(
                                modifier = Modifier.padding(horizontal = 16.dp),
                                color = MaterialTheme.colorScheme.outlineVariant
                            )
                        }
                    }
                }
            }
        }
    }

    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(sectionTitle, style = MaterialTheme.typography.titleLarge)
        Column(
            Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Card(
                Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(
                    topStart = 12.dp,
                    topEnd = 12.dp,
                    bottomStart = 4.dp,
                    bottomEnd = 4.dp
                )
            ) {
                SummarySection(expandedSection == summaryKey)
            }
            visibleDays.forEachIndexed { index, day ->
                val isLast = index == visibleDays.lastIndex
                Card(
                    Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(
                        topStart = 4.dp,
                        topEnd = 4.dp,
                        bottomStart = if (isLast) 12.dp else 4.dp,
                        bottomEnd = if (isLast) 12.dp else 4.dp
                    )
                ) {
                    DaySection(day, expandedSection == day.name)
                }
            }
        }
        onOpenNextWeek?.let { openNextWeek ->
            FilledTonalButton(
                onClick = openNextWeek,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Ver el menú de la semana que viene")
            }
        }
    }
}

@Composable
private fun WeeklyMenuReplicaScreen(
    meals: List<PlannedMeal>,
    foodsById: Map<Long, Food>,
    dishesById: Map<Long, Dish>,
    recommendation: es.david.rumbo.model.Recommendation?,
    sectionTitle: String,
    onOpenShoppingList: () -> Unit,
    onRegenerateWeek: () -> String?,
    onOpenMeal: (Long) -> Unit,
    onOpenFood: (Long) -> Unit,
    onOpenDish: (Long) -> Unit,
    onApplyAdjustedMeals: (List<PlannedMeal>) -> Unit
) {
    LazyColumn(
        contentPadding = PaddingValues(start = 16.dp, top = 12.dp, end = 16.dp, bottom = 96.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            WeeklyHomeMenuSection(
                meals = meals,
                foodsById = foodsById,
                dishesById = dishesById,
                recommendation = recommendation,
                sectionTitle = sectionTitle,
                onOpenNextWeek = null,
                onOpenCurrentShoppingList = onOpenShoppingList,
                onRegenerateWeek = onRegenerateWeek,
                onOpenMeal = onOpenMeal,
                onOpenFood = onOpenFood,
                onOpenDish = onOpenDish,
                onApplyAdjustedMeals = onApplyAdjustedMeals
            )
        }
    }
}

private data class MenuItemLine(
    val id: Long,
    val isDish: Boolean,
    val name: String,
    val grams: Double,
    val category: FoodCategory
)

@Composable
private fun TodayNutritionSummary(assessment: PlanNutritionAssessment) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        NutritionAmountMetric(
            "Calorías", assessment.actual.calories, assessment.target.calories,
            Icons.Default.LocalFireDepartment, MaterialTheme.colorScheme.onSurfaceVariant, Modifier.weight(1f)
        )
        NutritionAmountMetric(
            "Proteína", assessment.actual.proteinGrams, assessment.target.proteinGrams,
            foodCategoryIcon(FoodCategory.PROTEIN), foodCategoryColor(FoodCategory.PROTEIN), Modifier.weight(1f)
        )
        NutritionAmountMetric(
            "Hidratos", assessment.actual.carbohydrateGrams, assessment.target.carbohydrateGrams,
            foodCategoryIcon(FoodCategory.CARBOHYDRATE), foodCategoryColor(FoodCategory.CARBOHYDRATE), Modifier.weight(1f)
        )
        NutritionAmountMetric(
            "Grasa", assessment.actual.fatGrams, assessment.target.fatGrams,
            foodCategoryIcon(FoodCategory.FAT), foodCategoryColor(FoodCategory.FAT), Modifier.weight(1f)
        )
    }
}

@Composable
private fun NutritionAmountMetric(
    label: String,
    actual: Double,
    target: Double,
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
            "${if (target > 0.0) (actual / target * 100.0).roundToInt() else 0} %",
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
    val names = listOf("calorías", "proteína", "hidratos", "grasa")
    val outside = assessment.evaluations.withIndex().filter { it.value.fit == TargetFit.OUTSIDE }
    val below = outside.filter { it.value.difference < 0.0 }.map { names[it.index] }
    val above = outside.filter { it.value.difference > 0.0 }.map { names[it.index] }
    if (below.isEmpty() && above.isEmpty()) return "El menú del día está bien ajustado a tus objetivos."
    return buildList {
        if (below.isNotEmpty()) add("Por debajo del objetivo: ${below.joinToString()}.")
        if (above.isNotEmpty()) add("Por encima del objetivo: ${above.joinToString()}.")
    }.joinToString(" ")
}


private fun repertoireCoverageWarning(
    assessment: RepertoireAssessment?,
    rules: List<PlanningRule>,
    foodsById: Map<Long, Food>
): String? {
    assessment ?: return null
    val missingNutrients = listOf(
        NutrientKind.PROTEIN to EfficientNutrient.PROTEIN,
        NutrientKind.CARBOHYDRATES to EfficientNutrient.CARBOHYDRATES,
        NutrientKind.FAT to EfficientNutrient.FAT
    ).filter { (kind, _) ->
        assessment.nutrition[kind]?.let {
            it.deviation < 0.0 && it.fit != TargetFit.ON_TARGET
        } == true
    }
    if (missingNutrients.isEmpty()) return null

    val activeRules = rules.filter {
        it.isActive && it.itemKind == PlannedItemKind.FOOD &&
            foodsById[it.itemId] != null
    }
    val problem = missingNutrients.firstNotNullOfOrNull { (kind, efficientNutrient) ->
        assessment.coverage.firstOrNull { coverage ->
            activeRules.none { rule ->
                val allowed = coverage.mealType in rule.allowedMealTypes ||
                    rule.requiredSlots().any { it.mealType == coverage.mealType }
                allowed && efficientNutrient in
                    FoodSuggestionEngine.efficientNutrients(foodsById.getValue(rule.itemId))
            }
        }?.let { kind to it.mealType }
    } ?: return null

    val nutrient = when (problem.first) {
        NutrientKind.PROTEIN -> "proteína"
        NutrientKind.CARBOHYDRATES -> "hidratos"
        NutrientKind.FAT -> "grasas"
        NutrientKind.CALORIES -> return null
    }
    val meal = problem.second.label.lowercase()
    val cannotBuild = assessment.status == RepertoireStatus.INSUFFICIENT ||
        assessment.acceptableSolutions == 0
    return if (cannotBuild) {
        "No podemos crear un menú adecuado porque faltan fuentes de $nutrient para $meal."
    } else {
        "Será más fácil crear menús variados si añades fuentes de $nutrient para $meal."
    }
}

private fun weeklyAssessmentText(assessment: PlanNutritionAssessment?): String {
    if (assessment == null) return "Añade una medición para poder valorar este menú."
    if (!assessment.actual.isComplete) return "Faltan datos nutricionales para valorar el menú completo."
    val names = listOf("calorías", "proteína", "hidratos", "grasa")
    val outside = assessment.evaluations.withIndex().filter { it.value.fit == TargetFit.OUTSIDE }
    val below = outside.filter { it.value.difference < 0.0 }.map { names[it.index] }
    val above = outside.filter { it.value.difference > 0.0 }.map { names[it.index] }
    if (below.isEmpty() && above.isEmpty()) return "El menú semanal está bien ajustado a tus objetivos."
    return buildList {
        if (below.isNotEmpty()) add("Por debajo del objetivo semanal: ${below.joinToString()}.")
        if (above.isNotEmpty()) add("Por encima del objetivo semanal: ${above.joinToString()}.")
    }.joinToString(" ")
}

@Composable
private fun ShoppingListScreen(
    data: AppData,
    week: PlanWeek,
    onWeekChange: (PlanWeek) -> Unit,
    showWeekSelector: Boolean = true,
    onBack: () -> Unit
) {
    val foodsById = remember(data.foods) { data.foods.associateBy { it.id } }
    val dishesById = remember(data.dishes) { data.dishes.associateBy { it.id } }
    val meals = data.activeProfileData?.plannedMeals.orEmpty().filter { it.planWeek == week }
    val topAppBarState = rememberTopAppBarState()
    val scrollBehavior = TopAppBarDefaults.enterAlwaysScrollBehavior(topAppBarState)

    Scaffold(
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            TopAppBar(
                title = { Text("Lista de la compra") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Volver")
                    }
                },
                scrollBehavior = scrollBehavior
            )
        }
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(top = innerPadding.calculateTopPadding()),
            contentPadding = PaddingValues(start = 16.dp, top = 12.dp, end = 16.dp, bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            if (showWeekSelector) {
                item {
                    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                        listOf(PlanWeek.CURRENT to "Esta semana", PlanWeek.NEXT to "La que viene").forEachIndexed { index, (value, label) ->
                            SegmentedButton(
                                selected = week == value,
                                onClick = { onWeekChange(value) },
                                shape = SegmentedButtonDefaults.itemShape(index, 2)
                            ) { Text(label) }
                        }
                    }
                }
            }
            item {
                HomeShoppingSection(
                    meals = meals,
                    foodsById = foodsById,
                    dishesById = dishesById,
                    profileId = data.profile?.id,
                    onOpenFoods = {}
                )
            }
        }
    }
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
    val purchasedEntries = entries.filter { (food, _) -> food.id in availableFoodIds }

    Column(
        Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        if (neededEntries.isEmpty() && entries.isEmpty()) {
            Text(
                "El plan todavía no contiene alimentos.",
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        } else {
            neededEntries.forEachIndexed { index, (food, grams) ->
                HomeShoppingEntry(
                    food = food,
                    grams = grams,
                    checked = false,
                    onCheckedChange = { isChecked ->
                        if (isChecked) saveAvailableFoods(availableFoodIds + food.id)
                    }
                )
                if (index < neededEntries.lastIndex) {
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                }
            }
        }
        if (purchasedEntries.isNotEmpty()) {
            Text(
                "Ya comprado",
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.padding(top = 4.dp)
            )
            purchasedEntries.forEachIndexed { index, (food, grams) ->
                HomeShoppingEntry(
                    food = food,
                    grams = grams,
                    checked = true,
                    onCheckedChange = { isChecked ->
                        if (!isChecked) saveAvailableFoods(availableFoodIds - food.id)
                    }
                )
                if (index < purchasedEntries.lastIndex) {
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
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
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onCheckedChange(!checked) }
            .padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Checkbox(
            checked = checked,
            onCheckedChange = onCheckedChange
        )
        Column(
            Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            Text(
                food.name,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            Text(
                foodAmountLabel(food, grams),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1
            )
        }
    }
}

private fun foodAmountLabel(food: Food, grams: Double): String {
    val unitAmount = food.unitAmount
    val unitName = food.unitName
    if (unitAmount == null || unitAmount <= 0.0 || unitName.isNullOrBlank()) {
        return "${formatDecimal(grams)} g"
    }
    val units = grams / unitAmount
    val plural = food.unitPlural?.takeIf { it.isNotBlank() } ?: "${unitName}s"
    val halves = (units * 2).roundToInt()
    val natural = when {
        abs(units - 0.5) < 0.01 -> if (food.unitGender == "FEMININE") "media $unitName" else "medio $unitName"
        abs(units - 1.0) < 0.01 -> "1 $unitName"
        halves > 2 && halves % 2 == 1 -> "${halves / 2} $unitName y ${if (food.unitGender == "FEMININE") "media" else "medio"}"
        abs(units - units.roundToInt()) < 0.01 -> "${units.roundToInt()} $plural"
        else -> "${formatDecimal(units)} $plural"
    }
    return "$natural · ${formatDecimal(grams)} g"
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
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow)) {
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
    onDismiss: () -> Unit,
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

    ModalBottomSheet(onDismissRequest = onDismiss) {
    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text(if (isEditing) "Editar medición" else "Nueva medición", style = MaterialTheme.typography.headlineSmall)
                OutlinedButton(onClick = { showDatePicker = true }, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Default.CalendarMonth, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(date.format(DateTimeFormatter.ofPattern("dd/MM/yyyy")))
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    NumericField("Peso (kg)", weight, { weight = it }, Modifier.weight(1f))
                    NumericField("Cintura (cm)", waist, { waist = it }, Modifier.weight(1f))
                }
                WaistMeasurementHelp()
                SelectorField(
                    label = "Actividad habitual",
                    selectedLabel = activity?.label ?: "Mantener la anterior · ${inherited.activity.label}",
                    options = ActivityLevel.entries,
                    optionLabel = { "${it.label} · ${it.description}" },
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
        TextButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) { Text("Cancelar") }
        Spacer(Modifier.height(24.dp))
    }
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
    rules: List<PlanningRule>,
    activeMealTypes: Set<MealType>,
    onSave: (PlanningRule) -> Unit,
    onDelete: (Long) -> Unit
) {
    var editingRule by remember(itemKind, itemId) { mutableStateOf<PlanningRule?>(null) }
    var addingRule by remember(itemKind, itemId) { mutableStateOf(false) }
    val shownRule = editingRule
    if (shownRule != null || addingRule) {
        PlanningRuleDialog(
            name = "Regla de planificación",
            initial = shownRule ?: PlanningRule(
                itemKind,
                itemId,
                activeMealTypes,
                frequency = PlanningFrequency.OCCASIONAL,
                preferredGrams = defaultGrams,
                ruleId = System.currentTimeMillis()
            ),
            activeMealTypes = activeMealTypes,
            onSave = {
                onSave(it)
                editingRule = null
                addingRule = false
            },
            onDelete = shownRule?.let { rule ->
                {
                    onDelete(rule.ruleId)
                    editingRule = null
                }
            },
            onDismiss = {
                editingRule = null
                addingRule = false
            }
        )
    }
    Card(Modifier.fillMaxWidth()) {
        Column(
            Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text("Cuándo quieres comerlo", style = MaterialTheme.typography.titleLarge)
            HorizontalDivider()
            if (rules.isEmpty()) {
                Text(
                    "Sin reglas. Rumbo no utilizará este alimento automáticamente.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            } else {
                rules.forEachIndexed { index, rule ->
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .clickable { editingRule = rule }
                            .padding(vertical = 10.dp),
                        verticalArrangement = Arrangement.spacedBy(3.dp)
                    ) {
                        Text(
                            "${rule.frequency.label} · ${rule.allowedMealTypes.joinToString { it.label }}",
                            style = MaterialTheme.typography.bodyLarge,
                            fontWeight = FontWeight.SemiBold
                        )
                        Text(
                            if (rule.allowedDays.size == WeekDay.entries.size) {
                                "Cualquier día"
                            } else {
                                rule.allowedDays.joinToString { it.shortLabel }
                            },
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    if (index < rules.lastIndex) HorizontalDivider()
                }
            }
            TextButton(onClick = { addingRule = true }) {
                Icon(Icons.Default.Add, contentDescription = null)
                Spacer(Modifier.width(6.dp))
                Text("Añadir regla")
            }
        }
    }
}

@Composable
private fun AutomaticPlanningScreen(
    rules: List<PlanningRule>,
    repertoireFoodIds: Set<Long>,
    foods: List<Food>,
    dishes: List<Dish>,
    recommendation: es.david.rumbo.model.Recommendation?,
    mealShares: Map<MealType, Double>,
    onSaveRule: (PlanningRule) -> Unit,
    onDeleteRule: (Long) -> Unit,
    onAddToRepertoire: (Long) -> Unit,
    onRemoveFromRepertoire: (Long) -> Unit,
    onSetActive: (Long, Boolean) -> Unit,
    onReplace: (Long, Long) -> Unit
) {
    val foodsById = remember(foods) { foods.associateBy { it.id } }
    val foodRules = remember(rules) { rules.filter { it.itemKind == PlannedItemKind.FOOD } }
    val rulesByFoodId = remember(foodRules) { foodRules.groupBy { it.itemId } }
    val candidates = remember(foods) {
        foods.filter { it.hasComparableNutrition() }.map { food ->
            PlanningCandidate(PlannedItemKind.FOOD, food.id, food.name, 100.0)
        }
    }
    val assessment by produceState<RepertoireAssessment?>(
        initialValue = null,
        rules, foods, dishes, recommendation, mealShares
    ) {
        value = recommendation?.let { target ->
            withContext(Dispatchers.Default) {
                RepertoireEvaluator.evaluate(
                    rules = rules,
                    foodsById = foods.associateBy { it.id },
                    dishesById = dishes.associateBy { it.id },
                    recommendation = target,
                    mealShares = mealShares
                )
            }
        }
    }
    var query by rememberSaveable { mutableStateOf("") }
    var repertoireFilter by rememberSaveable { mutableStateOf(RepertoireFilter.ALL) }
    var editing by remember { mutableStateOf<PlanningRule?>(null) }
    var removingFood by remember { mutableStateOf<Food?>(null) }
    var replacingFood by remember { mutableStateOf<Food?>(null) }
    var replacementQuery by rememberSaveable { mutableStateOf("") }

    removingFood?.let { food ->
        val relatedDishes = dishes.count { dish -> dish.ingredients.any { it.foodId == food.id } }
        AlertDialog(
            onDismissRequest = { removingFood = null },
            title = { Text("¿Eliminar ${food.name} del repertorio?") },
            text = { Text(if (relatedDishes == 0) "Perderás su configuración personal. El producto seguirá en el catálogo." else "Se usa en $relatedDishes plato(s). Perderás su configuración y esos platos dejarán de poder generarse.") },
            confirmButton = { TextButton(onClick = { onRemoveFromRepertoire(food.id); removingFood = null }) { Text("Eliminar", color = MaterialTheme.colorScheme.error) } },
            dismissButton = { TextButton(onClick = { removingFood = null }) { Text("Cancelar") } }
        )
    }
    replacingFood?.let { oldFood ->
        AlertDialog(
            onDismissRequest = { replacingFood = null; replacementQuery = "" },
            title = { Text("Sustituir ${oldFood.name}") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Se conservarán sus reglas y estado. Revisa después las unidades del nuevo formato.")
                    OutlinedTextField(replacementQuery, { replacementQuery = it.take(80) }, label = { Text("Buscar sustituto") }, singleLine = true)
                    foods.asSequence().filter { it.id != oldFood.id && replacementQuery.isNotBlank() && it.name.contains(replacementQuery, true) }.take(6).forEach { candidate ->
                        TextButton(onClick = { onReplace(oldFood.id, candidate.id); replacingFood = null; replacementQuery = "" }) { Text(candidate.name) }
                    }
                }
            },
            confirmButton = {},
            dismissButton = { TextButton(onClick = { replacingFood = null; replacementQuery = "" }) { Text("Cancelar") } }
        )
    }

    editing?.let { rule ->
        val name = candidates.firstOrNull { it.kind == rule.itemKind && it.id == rule.itemId }?.name
            ?: "Elemento"
        PlanningRuleDialog(
            name = name,
            initial = rule,
            activeMealTypes = mealShares.filterValues { it > 0.0 }.keys,
            onSave = {
                onSaveRule(it)
                editing = null
            },
            onDelete = foodRules.any { it.ruleId == rule.ruleId }
                .takeIf { it }
                ?.let {
                    {
                        onDeleteRule(rule.ruleId)
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
                        "Elige qué sueles comer y establece cuándo puede usarlo Rumbo.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    if (recommendation == null) {
                        Text(
                            "Añade una medición para que Rumbo pueda valorar este repertorio según tus necesidades.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    } else if (assessment == null) {
                        Text("Analizando el repertorio…", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    } else {
                        RepertoireAssessmentSummary(
                            assessment = assessment!!,
                            foodsById = foodsById,
                            rules = foodRules,
                            onEditRule = { editing = it }
                        )
                    }
                }
            }
        }

        item {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it.take(80) },
                label = { Text("Buscar en mi repertorio") },
                leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(Modifier.height(8.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                RepertoireFilter.entries.forEach { option ->
                    FilterChip(
                        selected = repertoireFilter == option,
                        onClick = { repertoireFilter = option },
                        label = { Text(option.label) }
                    )
                }
            }
        }

        val repertoireFoods = foods.asSequence()
            .filter { it.id in repertoireFoodIds }
            .filter { query.isBlank() || it.name.contains(query, ignoreCase = true) }
            .filter { food ->
                val foodRulesForItem = rulesByFoodId[food.id].orEmpty()
                when (repertoireFilter) {
                    RepertoireFilter.ALL -> true
                    RepertoireFilter.ACTIVE -> foodRulesForItem.any { it.isActive }
                    RepertoireFilter.INACTIVE -> foodRulesForItem.isNotEmpty() && foodRulesForItem.none { it.isActive }
                    RepertoireFilter.PENDING -> foodRulesForItem.isEmpty()
                }
            }.sortedBy { it.name.lowercase() }.toList()

        if (repertoireFoods.isEmpty()) {
            item {
                Text(
                    if (repertoireFoodIds.isEmpty()) "Tu repertorio todavía está vacío."
                    else "No hay alimentos con estos criterios.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        } else {
            items(repertoireFoods, key = { "repertoire_${it.id}" }) { food ->
                val itemRules = rulesByFoodId[food.id].orEmpty()
                val rule = itemRules.firstOrNull()
                var actionsExpanded by remember { mutableStateOf(false) }
                Card(
                    Modifier.fillMaxWidth().clickable {
                        editing = rule ?: PlanningRule(
                            PlannedItemKind.FOOD, food.id,
                            setOf(MealType.LUNCH, MealType.DINNER),
                            preferredGrams = 100.0
                        )
                    }
                ) {
                    Row(
                        Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Icon(
                            foodCategoryIcon(food.category),
                            contentDescription = null
                        )
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                            Text(food.name, style = MaterialTheme.typography.bodyLarge)
                            Text(
                                if (rule == null) "Pendiente de configurar" else if (!rule.isActive) {
                                    "Inactivo · conserva su configuración"
                                } else "${itemRules.size} regla(s) · " + itemRules.joinToString { it.frequency.label },
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        if (rule == null) {
                            TextButton(onClick = {
                                editing = PlanningRule(
                                    PlannedItemKind.FOOD, food.id,
                                    setOf(MealType.LUNCH, MealType.DINNER),
                                    preferredGrams = 100.0
                                )
                            }) { Text("Configurar") }
                        } else {
                            TextButton(onClick = { onSetActive(food.id, !rule.isActive) }) {
                                Text(if (rule.isActive) "Desactivar" else "Activar")
                            }
                        }
                        Box {
                            IconButton(onClick = { actionsExpanded = true }) {
                                Icon(Icons.Default.MoreVert, contentDescription = "Más acciones")
                            }
                            DropdownMenu(expanded = actionsExpanded, onDismissRequest = { actionsExpanded = false }) {
                                DropdownMenuItem(
                                    text = { Text("Añadir regla") },
                                    onClick = {
                                        actionsExpanded = false
                                        editing = PlanningRule(
                                            PlannedItemKind.FOOD, food.id,
                                            setOf(MealType.LUNCH, MealType.DINNER),
                                            preferredGrams = 100.0,
                                            ruleId = System.currentTimeMillis()
                                        )
                                    }
                                )
                                itemRules.forEachIndexed { index, existingRule ->
                                    DropdownMenuItem(
                                        text = { Text("Editar regla ${index + 1}: ${existingRule.frequency.label}") },
                                        onClick = { actionsExpanded = false; editing = existingRule }
                                    )
                                }
                                DropdownMenuItem(
                                    text = { Text("Sustituir producto") },
                                    onClick = { actionsExpanded = false; replacingFood = food }
                                )
                                DropdownMenuItem(
                                    text = { Text("Eliminar del repertorio") },
                                    onClick = { actionsExpanded = false; removingFood = food }
                                )
                            }
                        }
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
            Text("Elige un producto para guardarlo como pendiente y configurarlo después.",
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        val visible = candidates.asSequence()
            .filterNot { it.id in repertoireFoodIds }
            .take(12)
            .toList()
        items(visible, key = { "candidate_${it.kind}_${it.id}" }) { candidate ->
            Row(
                Modifier
                    .fillMaxWidth()
                    .clickable {
                        onAddToRepertoire(candidate.id)
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
private fun RepertoireAssessmentSummary(
    assessment: RepertoireAssessment,
    foodsById: Map<Long, Food>,
    rules: List<PlanningRule>,
    onEditRule: (PlanningRule) -> Unit
) {
    val (title, icon, color) = when (assessment.status) {
        RepertoireStatus.ROBUST -> Triple("Repertorio robusto", Icons.Default.Check, MaterialTheme.colorScheme.primary)
        RepertoireStatus.SUFFICIENT -> Triple("Repertorio suficiente", Icons.Default.Check, MaterialTheme.colorScheme.primary)
        RepertoireStatus.LIMITED -> Triple("Repertorio limitado", Icons.Default.Info, MaterialTheme.colorScheme.tertiary)
        RepertoireStatus.INSUFFICIENT -> Triple("Repertorio insuficiente", Icons.Default.Warning, MaterialTheme.colorScheme.error)
    }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Icon(icon, contentDescription = null, tint = color)
        Text(title, style = MaterialTheme.typography.titleMedium, color = color)
    }
    Text(
        when (assessment.status) {
            RepertoireStatus.ROBUST -> "Rumbo dispone de varias combinaciones bien ajustadas y margen para variar."
            RepertoireStatus.SUFFICIENT -> "Rumbo puede construir menús bien ajustados con las opciones actuales."
            RepertoireStatus.LIMITED -> "Rumbo puede generar menús, pero dependerá de pocas combinaciones o comidas con escasas alternativas."
            RepertoireStatus.INSUFFICIENT -> "Con la programación actual Rumbo no puede construir un menú razonablemente ajustado."
        },
        color = MaterialTheme.colorScheme.onSurfaceVariant
    )
    assessment.limitingFactors.take(4).forEach { factor ->
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {
            Icon(Icons.Default.Warning, contentDescription = null, modifier = Modifier.size(18.dp), tint = color)
            Text(factor, style = MaterialTheme.typography.bodyMedium)
        }
    }
    val inactiveRules = assessment.reactivationFoodIds.mapNotNull { id ->
        rules.firstOrNull { it.itemId == id }?.let { it to foodsById[id] }
    }
    if (inactiveRules.isNotEmpty()) {
        Text("Puedes reactivar", style = MaterialTheme.typography.labelLarge)
        inactiveRules.take(4).forEach { (rule, food) ->
            TextButton(onClick = { onEditRule(rule) }, contentPadding = PaddingValues(0.dp)) {
                Text(food?.name ?: "Alimento inactivo")
                Spacer(Modifier.width(4.dp))
                Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = "Revisar")
            }
        }
    } else if (assessment.suggestions.isNotEmpty()) {
        Text(
            "Sería útil añadir: ${assessment.suggestions.joinToString { it.label.lowercase() }}.",
            style = MaterialTheme.typography.bodyMedium
        )
    }
}

@Composable
private fun PlanningRuleDialog(
    name: String,
    initial: PlanningRule,
    activeMealTypes: Set<MealType>,
    onSave: (PlanningRule) -> Unit,
    onDelete: (() -> Unit)?,
    onDismiss: () -> Unit
) {
    var meals by remember(initial, activeMealTypes) {
        mutableStateOf(initial.allowedMealTypes.intersect(activeMealTypes))
    }
    var days by remember(initial) { mutableStateOf(initial.allowedDays) }
    var frequency by remember(initial) {
        mutableStateOf(when (initial.frequency) {
            PlanningFrequency.ALWAYS -> PlanningFrequency.ALWAYS
            PlanningFrequency.OCCASIONAL -> PlanningFrequency.OCCASIONAL
            else -> PlanningFrequency.NORMAL
        })
    }
    var error by remember { mutableStateOf<String?>(null) }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text(name, style = MaterialTheme.typography.headlineSmall)
            SelectorField(
                label = "Frecuencia",
                selectedLabel = frequency.label,
                options = listOf(PlanningFrequency.OCCASIONAL, PlanningFrequency.NORMAL, PlanningFrequency.ALWAYS),
                optionLabel = { it.label }, onSelect = { frequency = it }, onClear = null
            )
            MultiSelectField(
                label = "Comidas",
                options = MealType.entries.filter { it in activeMealTypes },
                selected = meals,
                optionLabel = { it.label },
                onSelectedChange = { meals = it }
            )
            MultiSelectField(
                label = "Días",
                options = WeekDay.entries,
                selected = days,
                optionLabel = { it.label },
                allLabel = "Cualquier día",
                onSelectedChange = { days = it }
            )
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(onClick = {
                val draft = initial.copy(
                    allowedMealTypes = meals,
                    allowedDays = days,
                    fixedSlots = emptySet(),
                    frequency = frequency,
                    preferredGrams = 100.0,
                    minimumFactor = 0.1,
                    maximumFactor = 5.0
                )
                if (draft.isValid()) onSave(draft)
                else error = "Selecciona al menos una comida y un día."
            }, Modifier.fillMaxWidth()) { Text("Guardar") }
            onDelete?.let { delete ->
                TextButton(onClick = delete, Modifier.fillMaxWidth()) {
                    Text("Eliminar regla", color = MaterialTheme.colorScheme.error)
                }
            }
            TextButton(onClick = onDismiss, Modifier.fillMaxWidth()) { Text("Cancelar") }
            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun <T> MultiSelectField(
    label: String,
    options: List<T>,
    selected: Set<T>,
    optionLabel: (T) -> String,
    allLabel: String? = null,
    onSelectedChange: (Set<T>) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = if (selected.size == options.size && allLabel != null) allLabel else selected.joinToString { optionLabel(it) },
            onValueChange = {}, readOnly = true, label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth()
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(option in selected, null)
                            Text(optionLabel(option))
                        }
                    },
                    onClick = { onSelectedChange(if (option in selected) selected - option else selected + option) }
                )
            }
        }
    }
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
    onOpenFood: (Long) -> Unit,
    onOpenDish: (Long) -> Unit,
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
                onOpenFood = onOpenFood,
                onOpenDish = onOpenDish,
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
        NutritionAmountMetric(
            "Calorías", actualCalories, targetCalories,
            Icons.Default.LocalFireDepartment, MaterialTheme.colorScheme.onSurfaceVariant, Modifier.weight(1f)
        )
        NutritionAmountMetric(
            "Proteína", actualProtein, targetProtein,
            foodCategoryIcon(FoodCategory.PROTEIN), foodCategoryColor(FoodCategory.PROTEIN), Modifier.weight(1f)
        )
        NutritionAmountMetric(
            "Hidratos", actualCarbohydrates, targetCarbohydrates,
            foodCategoryIcon(FoodCategory.CARBOHYDRATE),
            foodCategoryColor(FoodCategory.CARBOHYDRATE),
            Modifier.weight(1f)
        )
        NutritionAmountMetric(
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
    val days = assessments.size.toDouble()
    val nutrients = listOf(
        Triple("calorías", NutrientKind.CALORIES, assessments.map { it.actual.calories to it.target.calories }),
        Triple("proteína", NutrientKind.PROTEIN, assessments.map { it.actual.proteinGrams to it.target.proteinGrams }),
        Triple("hidratos", NutrientKind.CARBOHYDRATES, assessments.map { it.actual.carbohydrateGrams to it.target.carbohydrateGrams }),
        Triple("grasa", NutrientKind.FAT, assessments.map { it.actual.fatGrams to it.target.fatGrams })
    )
    val weeklyEvaluations = nutrients.map { (name, kind, values) ->
        name to NutritionTolerancePolicy.evaluate(
            kind,
            values.sumOf { it.first } / days,
            values.sumOf { it.second } / days
        )
    }
    val below = weeklyEvaluations.filter { it.second.fit == TargetFit.OUTSIDE && it.second.difference < 0.0 }
        .map { it.first }
    val above = weeklyEvaluations.filter { it.second.fit == TargetFit.OUTSIDE && it.second.difference > 0.0 }
        .map { it.first }
    val extremeDays = assessments.count { it.overall == TargetFit.OUTSIDE }
    if (below.isEmpty() && above.isEmpty()) {
        return if (extremeDays == 0) {
            "El menú semanal está bien ajustado a tus objetivos."
        } else {
            "El promedio semanal está bien ajustado, pero conviene revisar ${if (extremeDays == 1) "un día" else "$extremeDays días"}."
        }
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
    onOpenFood: (Long) -> Unit,
    onOpenDish: (Long) -> Unit,
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
                                dish.id, true,
                                dish.name,
                                it.resolvedGrams(planned, day),
                                dish.dominantCategory(foodsById)
                            )
                        }
                    } + it.items.mapNotNull { planned ->
                        foodsById[planned.foodId]?.let { food ->
                            MenuItemLine(
                                food.id, false,
                                food.name,
                                it.resolvedGrams(planned, day),
                                food.category
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
                                Modifier.fillMaxWidth().clickable {
                                    if (entry.isDish) onOpenDish(entry.id) else onOpenFood(entry.id)
                                },
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                SmallFoodCategoryBadge(entry.category)
                                Text(entry.name, modifier = Modifier.weight(1f))
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
private enum class CatalogMode { SEARCH, REPERTOIRE }
private enum class RepertoireFilter(val label: String) {
    ALL("Todos"), ACTIVE("Activos"), INACTIVE("Inactivos"), PENDING("Pendientes")
}

private data class CatalogEntry(
    val id: Long,
    val name: String,
    val isDish: Boolean
)

@Composable
private fun HomeCatalogSearch(
    foods: List<Food>, dishes: List<Dish>, repertoireFoodIds: Set<Long>,
    foodSuggestions: List<FoodSuggestion>,
    textFieldState: TextFieldState,
    filter: CatalogFilter, onFilterChange: (CatalogFilter) -> Unit,
    scanMessage: String?, onScanMessageChange: (String?) -> Unit,
    state: SearchBarState,
    listState: LazyListState,
    suppressRestoredKeyboard: Boolean,
    onRestoredKeyboardSuppressed: () -> Unit,
    scrollBehavior: SearchBarScrollBehavior,
    onCloseSearch: () -> Unit,
    onOpenFood: (Long) -> Unit, onOpenDish: (Long) -> Unit,
    trailingContent: @Composable () -> Unit
) {
    val context = LocalContext.current
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    val scope = rememberCoroutineScope()
    val query = textFieldState.text.toString()
    val normalized = normalizeSearch(query)
    val searchContainerColor = MaterialTheme.colorScheme.surfaceContainerHighest
    val searchInputColors = SearchBarDefaults.inputFieldColors(
        focusedContainerColor = searchContainerColor,
        unfocusedContainerColor = searchContainerColor,
        disabledContainerColor = searchContainerColor
    )
    val searchBarColors = SearchBarDefaults.colors(
        containerColor = searchContainerColor,
        dividerColor = Color.Transparent,
        inputFieldColors = searchInputColors
    )
    val appBarColors = SearchBarDefaults.appBarWithSearchColors(
        searchBarColors = searchBarColors,
        appBarContainerColor = MaterialTheme.colorScheme.surface,
        scrolledAppBarContainerColor = MaterialTheme.colorScheme.surface,
        scrolledSearchBarContainerColor = searchContainerColor
    )
    val foodsById = remember(foods) { foods.associateBy { it.id } }
    val suggestionsByFoodId = remember(foodSuggestions) {
        foodSuggestions.associateBy { it.food.id }
    }
    val topSuggestionIds = remember(foodSuggestions) {
        foodSuggestions.take(3).mapTo(mutableSetOf()) { it.food.id }
    }
    val entries = remember(
        foods, dishes, normalized, filter, repertoireFoodIds, suggestionsByFoodId,
        topSuggestionIds
    ) {
        buildList {
            if (filter != CatalogFilter.DISHES) foods.forEach { food ->
                val searchText = normalizeSearch(
                    listOfNotNull(food.name, food.brand, food.barcode).joinToString(" ")
                )
                val suggested = food.id in topSuggestionIds
                if (normalized.isBlank() && (suggested || food.id in repertoireFoodIds) ||
                    normalized.isNotBlank() && searchText.contains(normalized)
                ) {
                    add(CatalogEntry(food.id, food.name, false))
                }
            }
            if (filter != CatalogFilter.FOODS) dishes.forEach { dish ->
                val favorite = dish.ingredients.any { it.foodId in repertoireFoodIds }
                if (normalized.isBlank() && favorite ||
                    normalized.isNotBlank() && normalizeSearch(dish.name).contains(normalized)
                ) {
                    add(CatalogEntry(dish.id, dish.name, true))
                }
            }
        }.sortedWith(
            compareBy<CatalogEntry> {
                if (it.isDish) Int.MAX_VALUE
                else foodSuggestions.indexOfFirst { suggestion -> suggestion.food.id == it.id }
                    .takeIf { index -> index >= 0 } ?: Int.MAX_VALUE
            }.thenBy { !normalizeSearch(it.name).startsWith(normalized) }
                .thenByDescending {
                    if (it.isDish) Double.NEGATIVE_INFINITY
                    else suggestionsByFoodId[it.id]?.score ?: Double.NEGATIVE_INFINITY
                }
                .thenBy { it.name.lowercase() }
        )
    }

    val leaveForDetail = {
        focusManager.clearFocus(force = true)
        keyboard?.hide()
    }
    val close = {
        leaveForDetail()
        onCloseSearch()
    }

    LaunchedEffect(suppressRestoredKeyboard, state.targetValue) {
        if (suppressRestoredKeyboard && state.targetValue == SearchBarValue.Expanded) {
            focusManager.clearFocus(force = true)
            keyboard?.hide()
            delay(500)
            focusManager.clearFocus(force = true)
            keyboard?.hide()
            onRestoredKeyboardSuppressed()
        }
    }

    LaunchedEffect(state.targetValue) {
        if (state.targetValue == SearchBarValue.Collapsed) {
            focusManager.clearFocus(force = true)
            keyboard?.hide()
            if (textFieldState.text.isNotEmpty()) textFieldState.setTextAndPlaceCursorAtEnd("")
            onScanMessageChange(null)
            scrollBehavior.scrollOffset = 0f
            scrollBehavior.contentOffset = 0f
        }
    }

    val scan = {
        onScanMessageChange(null)
        GmsBarcodeScanning.getClient(context).startScan().addOnSuccessListener { barcode ->
            val value = barcode.rawValue.orEmpty()
            foods.firstOrNull { it.barcode == value }?.let { food ->
                leaveForDetail()
                onOpenFood(food.id)
            } ?: run {
                textFieldState.setTextAndPlaceCursorAtEnd(value)
                onScanMessageChange("No encuentro este producto en tus supermercados.")
                scope.launch { state.animateToExpanded() }
            }
        }
        Unit
    }

    val inputField: @Composable () -> Unit = {
        SearchBarDefaults.InputField(
            textFieldState = textFieldState,
            searchBarState = state,
            enabled = !suppressRestoredKeyboard,
            colors = appBarColors.searchBarColors.inputFieldColors,
            onSearch = {},
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("Buscar alimentos y platos") },
            leadingIcon = {
                if (state.targetValue == SearchBarValue.Expanded) {
                    IconButton(onClick = close) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Cerrar búsqueda")
                    }
                } else {
                    Icon(Icons.Default.Search, contentDescription = null)
                }
            },
            trailingIcon = {
                if (state.targetValue == SearchBarValue.Expanded) {
                    IconButton(onClick = scan) {
                        Icon(Icons.Default.QrCodeScanner, "Escanear código de barras")
                    }
                }
            }
        )
    }

    AppBarWithSearch(
        state = state,
        inputField = inputField,
        scrollBehavior = scrollBehavior,
        colors = appBarColors,
        actions = { trailingContent() },
        modifier = Modifier.fillMaxWidth(),
        contentPadding = PaddingValues(horizontal = 16.dp),
        tonalElevation = 0.dp
    )

    ExpandedFullScreenSearchBar(
        state = state,
        inputField = {
            Box(Modifier.fillMaxWidth()) {
                inputField()
            }
        },
        colors = searchBarColors,
        tonalElevation = 0.dp,
        shadowElevation = 0.dp,
        windowInsets = {
            WindowInsets.safeDrawing.only(
                WindowInsetsSides.Top + WindowInsetsSides.Horizontal
            )
        }
    ) {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.surface
        ) {
            CatalogEntries(
                entries = entries,
                foods = foods,
                foodsById = foodsById,
                dishes = dishes,
                repertoireFoodIds = repertoireFoodIds,
                foodSuggestions = suggestionsByFoodId,
                mode = if (query.isBlank()) CatalogMode.REPERTOIRE else CatalogMode.SEARCH,
                normalizedQuery = normalized,
                onOpenFood = { id -> leaveForDetail(); onOpenFood(id) },
                onOpenDish = { id -> leaveForDetail(); onOpenDish(id) },
                onAddFood = {},
                onAddDish = {},
                compactPresentation = true,
                listState = listState,
                modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
                header = {
                    Column(Modifier.fillMaxWidth()) {
                        Spacer(Modifier.height(8.dp))
                        CatalogFilterMenu(filter, onFilterChange)
                        if (query.isBlank()) {
                            Text(
                                "Escribe el nombre de un alimento o plato, escanea su código de barras o elígelo de tu repertorio.",
                                Modifier.padding(vertical = 12.dp),
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        scanMessage?.let { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    }
                }
            )
        }
    }

    BackHandler(enabled = state.targetValue == SearchBarValue.Expanded) { close() }
}

@Composable
private fun FoodDishCatalogScreen(
    foods: List<Food>,
    dishes: List<Dish>,
    planningRules: List<PlanningRule>,
    repertoireFoodIds: Set<Long>,
    onOpenFood: (Long) -> Unit,
    onOpenDish: (Long) -> Unit,
    onAddFood: () -> Unit,
    onAddDish: () -> Unit
) {
    var query by rememberSaveable { mutableStateOf("") }
    var normalizedQuery by remember { mutableStateOf("") }
    var filter by rememberSaveable { mutableStateOf(CatalogFilter.ALL) }
    var mode by rememberSaveable { mutableStateOf(CatalogMode.SEARCH) }
    var searchExpanded by rememberSaveable { mutableStateOf(false) }
    var scanMessage by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current
    val foodsById = remember(foods) { foods.associateBy { it.id } }

    LaunchedEffect(query) {
        if (query.isNotBlank()) delay(200)
        normalizedQuery = normalizeSearch(query)
    }

    val entries = remember(foods, dishes, normalizedQuery, filter, mode, repertoireFoodIds) {
        buildList {
            if (filter != CatalogFilter.DISHES) {
                foods.forEach { food ->
                    val searchable = normalizeSearch(
                        listOfNotNull(
                            food.name, food.category.label, food.brand, food.family,
                            food.subcategory, food.retailer, food.barcode
                        ).joinToString(" ")
                    )
                    val belongs = food.id in repertoireFoodIds
                    if ((mode == CatalogMode.SEARCH && normalizedQuery.isNotBlank() ||
                            mode == CatalogMode.REPERTOIRE && belongs) &&
                        (normalizedQuery.isBlank() || searchable.contains(normalizedQuery))) {
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
                    val belongs = dish.ingredients.any { it.foodId in repertoireFoodIds }
                    if ((mode == CatalogMode.SEARCH && normalizedQuery.isNotBlank() ||
                            mode == CatalogMode.REPERTOIRE && belongs) &&
                        (normalizedQuery.isBlank() || searchable.contains(normalizedQuery))) {
                        add(CatalogEntry(dish.id, dish.name, true))
                    }
                }
            }
        }.sortedWith(
            compareBy<CatalogEntry> { !normalizeSearch(it.name).startsWith(normalizedQuery) }
                .thenBy { it.name.length }
                .thenBy { it.name.lowercase() }
                .thenBy { it.isDish }
        )
    }

    BackHandler(enabled = searchExpanded) { searchExpanded = false }

    Box(Modifier.fillMaxSize()) {
        Column(
            Modifier.fillMaxSize().padding(start = 20.dp, top = 16.dp, end = 20.dp)
        ) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = mode == CatalogMode.SEARCH,
                    onClick = {
                        mode = CatalogMode.SEARCH
                        searchExpanded = true
                    },
                    label = { Text("Buscar") }
                )
                FilterChip(
                    selected = mode == CatalogMode.REPERTOIRE,
                    onClick = { mode = CatalogMode.REPERTOIRE },
                    label = { Text("Mi repertorio") }
                )
            }
            Spacer(Modifier.height(8.dp))
            SearchBar(
                inputField = {
                    SearchBarDefaults.InputField(
                        query = query,
                        onQueryChange = { query = it },
                        onSearch = { },
                        expanded = searchExpanded,
                        onExpandedChange = {
                            searchExpanded = it
                            if (it) mode = CatalogMode.SEARCH
                        },
                        placeholder = { Text("Buscar alimentos y platos") },
                        leadingIcon = {
                            if (searchExpanded) {
                                IconButton(onClick = { searchExpanded = false }) {
                                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Salir de la búsqueda")
                                }
                            } else {
                                Icon(Icons.Default.Search, contentDescription = null)
                            }
                        },
                        trailingIcon = {
                            IconButton(onClick = {
                                scanMessage = null
                                GmsBarcodeScanning.getClient(context).startScan()
                                    .addOnSuccessListener { barcode ->
                                        val value = barcode.rawValue.orEmpty()
                                        val food = foods.firstOrNull { it.barcode == value }
                                        if (food != null) onOpenFood(food.id) else {
                                            query = value
                                            scanMessage = "No encuentro este producto en tus supermercados. Puedes buscarlo por nombre o añadirlo manualmente."
                                        }
                                    }
                            }) {
                                Icon(Icons.Default.QrCodeScanner, contentDescription = "Escanear código de barras")
                            }
                        }
                    )
                },
                expanded = searchExpanded,
                onExpandedChange = {
                    searchExpanded = it
                    if (it) mode = CatalogMode.SEARCH
                },
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
                    CatalogFilterChips(filter = filter, onFilterChange = { filter = it })
                    scanMessage?.let {
                        Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(8.dp))
                    }
                    CatalogEntries(
                        entries = entries,
                        foods = foods,
                        foodsById = foodsById,
                        dishes = dishes,
                        repertoireFoodIds = repertoireFoodIds,
                        mode = CatalogMode.SEARCH,
                        normalizedQuery = normalizedQuery,
                        onOpenFood = onOpenFood,
                        onOpenDish = onOpenDish,
                        onAddFood = onAddFood,
                        onAddDish = onAddDish,
                        modifier = Modifier.weight(1f)
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            if (mode == CatalogMode.REPERTOIRE) {
                CatalogFilterChips(filter = filter, onFilterChange = { filter = it })
                CatalogEntries(
                    entries = entries,
                    foods = foods,
                    foodsById = foodsById,
                    dishes = dishes,
                    repertoireFoodIds = repertoireFoodIds,
                    mode = mode,
                    normalizedQuery = normalizedQuery,
                    onOpenFood = onOpenFood,
                    onOpenDish = onOpenDish,
                    onAddFood = onAddFood,
                    onAddDish = onAddDish,
                    modifier = Modifier.weight(1f)
                )
            } else {
                Text(
                    "Toca la barra para buscar por nombre o escanear un código.",
                    modifier = Modifier.padding(vertical = 16.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun CatalogFilterChips(
    filter: CatalogFilter,
    onFilterChange: (CatalogFilter) -> Unit
) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        listOf(
            CatalogFilter.ALL to "Todos",
            CatalogFilter.FOODS to "Alimentos",
            CatalogFilter.DISHES to "Platos"
        ).forEach { (option, label) ->
            FilterChip(
                selected = filter == option,
                onClick = { onFilterChange(option) },
                label = { Text(label) }
            )
        }
    }
    Spacer(Modifier.height(8.dp))
}

@Composable
private fun CatalogFilterMenu(
    filter: CatalogFilter,
    onFilterChange: (CatalogFilter) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    val options = listOf(
        CatalogFilter.ALL to "Todos",
        CatalogFilter.FOODS to "Alimentos",
        CatalogFilter.DISHES to "Platos"
    )
    Box {
        FilterChip(
            selected = true,
            onClick = { expanded = true },
            label = { Text(options.first { it.first == filter }.second) },
            trailingIcon = { Icon(Icons.Default.ArrowDropDown, contentDescription = null) }
        )
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { (option, label) ->
                DropdownMenuItem(
                    leadingIcon = {
                        if (filter == option) Icon(Icons.Default.Check, contentDescription = null)
                    },
                    text = { Text(label) },
                    onClick = { onFilterChange(option); expanded = false }
                )
            }
        }
    }
}

@Composable
private fun CatalogEntries(
    entries: List<CatalogEntry>,
    foods: List<Food>,
    foodsById: Map<Long, Food>,
    dishes: List<Dish>,
    repertoireFoodIds: Set<Long>,
    foodSuggestions: Map<Long, FoodSuggestion> = emptyMap(),
    mode: CatalogMode,
    normalizedQuery: String,
    onOpenFood: (Long) -> Unit,
    onOpenDish: (Long) -> Unit,
    onAddFood: () -> Unit,
    onAddDish: () -> Unit,
    modifier: Modifier = Modifier,
    header: (@Composable () -> Unit)? = null,
    compactPresentation: Boolean = false,
    listState: LazyListState? = null
) {
    var addMenuExpanded by remember { mutableStateOf(false) }
    val resolvedListState = listState ?: rememberLazyListState()
    LazyColumn(
        modifier = modifier,
        state = resolvedListState,
        contentPadding = PaddingValues(bottom = 32.dp)
    ) {
        if (header != null) item { header() }
        items(entries, key = { "${if (it.isDish) "dish" else "food"}_${it.id}" }) { entry ->
            if (compactPresentation && normalizedQuery.isBlank()) {
                val entryIndex = entries.indexOf(entry)
                val previous = entries.getOrNull(entryIndex - 1)
                val isRecommended = !entry.isDish && entry.id in foodSuggestions
                val previousWasRecommended = previous != null && !previous.isDish &&
                    previous.id in foodSuggestions
                val sectionTitle = when {
                    isRecommended && !previousWasRecommended -> "Recomendados"
                    !isRecommended && (previous == null || previousWasRecommended) -> "Tu repertorio"
                    else -> null
                }
                sectionTitle?.let {
                    Text(
                        it,
                        modifier = Modifier.padding(top = 16.dp, bottom = 6.dp),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
            if (compactPresentation) {
                val food = if (entry.isDish) null else foodsById[entry.id]
                val dish = if (entry.isDish) dishes.firstOrNull { it.id == entry.id } else null
                if (food == null && dish == null) return@items
                val category = food?.category ?: dish!!.dominantCategory(foodsById)
                val dishNutrition = dish?.nutrition(foodsById)
                Row(
                    Modifier
                        .fillMaxWidth()
                        .clickable {
                            if (entry.isDish) onOpenDish(entry.id) else onOpenFood(entry.id)
                        }
                        .padding(vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    FoodCategoryBadge(category)
                    Column(
                        Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(2.dp)
                    ) {
                        Text(
                            entry.name,
                            style = MaterialTheme.typography.bodyLarge,
                            fontWeight = FontWeight.SemiBold,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Text(
                            if (entry.isDish) "Plato"
                            else foodSuggestions[entry.id]?.reason ?: category.label,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1
                        )
                    }
                    SearchNutritionGrid(
                        calories = food?.calories ?: dishNutrition?.calories,
                        protein = food?.proteinGrams ?: dishNutrition?.proteinGrams,
                        carbohydrates = food?.carbohydrateGrams ?: dishNutrition?.carbohydrateGrams,
                        fat = food?.fatGrams ?: dishNutrition?.fatGrams,
                        modifier = Modifier.width(98.dp)
                    )
                }
            } else if (entry.isDish) {
                val dish = dishes.firstOrNull { it.id == entry.id } ?: return@items
                val totals = dish.nutrition(foodsById)
                Row(
                    Modifier.fillMaxWidth().clickable { onOpenDish(dish.id) }.padding(vertical = 10.dp),
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
                        if (totals.isComplete) "${formatDecimal(totals.calories)}\nkcal" else "datos\nincompletos",
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

        if (mode == CatalogMode.SEARCH && normalizedQuery.isBlank()) {
            item {
                Text(
                    "Escribe el nombre de un alimento o plato, o escanea su código de barras.",
                    modifier = Modifier.padding(vertical = 24.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        } else if (entries.isEmpty()) {
            item {
                Text(
                    if (mode == CatalogMode.REPERTOIRE && repertoireFoodIds.isEmpty()) {
                        "Tu repertorio todavía está vacío. Configura alimentos desde la generación automática."
                    } else if (foods.isEmpty() && dishes.isEmpty()) {
                        "Todavía no hay alimentos ni platos."
                    } else {
                        "No hay resultados con estos criterios."
                    },
                    modifier = Modifier.padding(top = 24.dp, bottom = 12.dp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (mode == CatalogMode.SEARCH) {
                    Box {
                        FilledTonalButton(onClick = { addMenuExpanded = true }) {
                            Icon(Icons.Default.Add, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                                Text("Añadir manualmente")
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
                }
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
    onSaveDish: (Dish) -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    var confirmDelete by remember { mutableStateOf(false) }
    var creatingUnit by remember { mutableStateOf(false) }
    var unitDraft by remember(dish.id, dish.unitName) {
        mutableStateOf(dish.unitName?.let { FoodUnitDefinition(it, dish.unitPlural ?: it, dish.unitGender) })
    }
    var selectedUnitAmount by remember(dish.id, dish.unitAmount) {
        mutableStateOf(dish.unitAmount?.let(::formatDecimal).orEmpty())
    }
    var allowDividing by remember(dish.id, dish.wholeUnitsOnly) {
        mutableStateOf(!dish.unitName.isNullOrBlank() && !dish.wholeUnitsOnly)
    }
    var unitDivisions by remember(dish.id, dish.unitDivisions) {
        mutableStateOf(dish.unitDivisions.takeIf { it > 1 }?.toString() ?: "2")
    }
    var unitError by remember { mutableStateOf<String?>(null) }
    var ingredientAmounts by remember(dish.id, dish.ingredients) {
        mutableStateOf(dish.ingredients.associate { it.foodId to formatDecimal(it.grams) })
    }
    var addingIngredient by remember { mutableStateOf(false) }
    var ingredientError by remember { mutableStateOf<String?>(null) }
    val availableUnits = remember(foods) {
        foods.mapNotNull { candidate ->
            val singular = candidate.unitName ?: return@mapNotNull null
            FoodUnitDefinition(singular, candidate.unitPlural ?: singular, candidate.unitGender)
        }.plus(defaultUnitDefinitions).distinctBy { listOf(it.singular, it.plural, it.gender) }
            .sortedBy { it.singular.lowercase() }
    }
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
    if (creatingUnit) {
        NewFoodUnitDialog(
            foodName = dish.name,
            onCreate = { definition ->
                unitDraft = definition
                creatingUnit = false
                onSaveDish(dish.copy(
                    unitName = definition.singular, unitPlural = definition.plural,
                    unitGender = definition.gender, unitAmount = parseDecimal(selectedUnitAmount),
                    wholeUnitsOnly = !allowDividing,
                    unitDivisions = if (allowDividing) unitDivisions.toIntOrNull()?.coerceIn(2, 100) ?: 2 else 1
                ))
            },
            onDismiss = { creatingUnit = false }
        )
    }

    if (addingIngredient) {
        ModalBottomSheet(onDismissRequest = { addingIngredient = false }) {
            Column(
                Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text("Añadir ingrediente", style = MaterialTheme.typography.headlineSmall)
                val availableFoods = foods.filter { candidate -> dish.ingredients.none { it.foodId == candidate.id } }
                if (availableFoods.isEmpty()) {
                    Text("No quedan alimentos del catálogo por añadir.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    LazyColumn(Modifier.fillMaxWidth().heightIn(max = 420.dp)) {
                        items(availableFoods, key = { it.id }) { food ->
                            Row(
                                Modifier.fillMaxWidth().clickable {
                                    val updated = dish.ingredients + DishIngredient(food.id, 100.0)
                                    ingredientAmounts = ingredientAmounts + (food.id to "100")
                                    onSaveDish(dish.copy(ingredients = updated))
                                    addingIngredient = false
                                }.padding(vertical = 12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(10.dp)
                            ) {
                                SmallFoodCategoryBadge(food.category)
                                Text(food.name, Modifier.weight(1f), maxLines = 2, overflow = TextOverflow.Ellipsis)
                                Icon(Icons.Default.Add, contentDescription = null)
                            }
                            HorizontalDivider()
                        }
                    }
                }
                TextButton(onClick = { addingIngredient = false }, Modifier.fillMaxWidth()) { Text("Cancelar") }
                Spacer(Modifier.height(16.dp))
            }
        }
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
                NutritionLine("Proteínas", totals.proteinGrams, MaterialTheme.colorScheme.onSurface)
                NutritionLine("Carbohidratos", totals.carbohydrateGrams, MaterialTheme.colorScheme.onSurface)
                NutritionLine("Grasas", totals.fatGrams, MaterialTheme.colorScheme.onSurface)
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

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Unidades", style = MaterialTheme.typography.titleLarge)
                HorizontalDivider()
                UnitDefinitionField(
                    selected = unitDraft,
                    options = availableUnits,
                    onSelect = { definition ->
                        unitDraft = definition
                        unitError = null
                        onSaveDish(dish.copy(
                            unitName = definition.singular, unitPlural = definition.plural,
                            unitGender = definition.gender, unitAmount = parseDecimal(selectedUnitAmount),
                            wholeUnitsOnly = !allowDividing,
                            unitDivisions = if (allowDividing) unitDivisions.toIntOrNull()?.coerceIn(2, 100) ?: 2 else 1
                        ))
                    },
                    onCreateNew = { creatingUnit = true }
                )
                unitDraft?.let { definition ->
                    NumericField("Gramos o ml por unidad", selectedUnitAmount, { value ->
                        selectedUnitAmount = value
                        val amount = parseDecimal(value)
                        unitError = if (value.isNotBlank() && (amount == null || amount !in 0.1..5000.0))
                            "Indica entre 0,1 y 5.000 g o ml." else null
                        if (amount != null && amount in 0.1..5000.0) onSaveDish(dish.copy(
                            unitName = definition.singular, unitPlural = definition.plural,
                            unitGender = definition.gender, unitAmount = amount,
                            wholeUnitsOnly = !allowDividing,
                            unitDivisions = if (allowDividing) unitDivisions.toIntOrNull()?.coerceIn(2, 100) ?: 2 else 1
                        ))
                    }, Modifier.fillMaxWidth())
                    Row(
                        Modifier.fillMaxWidth().clickable {
                            allowDividing = !allowDividing
                            onSaveDish(dish.copy(
                                unitName = definition.singular, unitPlural = definition.plural,
                                unitGender = definition.gender, unitAmount = parseDecimal(selectedUnitAmount),
                                wholeUnitsOnly = !allowDividing,
                                unitDivisions = if (allowDividing) unitDivisions.toIntOrNull()?.coerceIn(2, 100) ?: 2 else 1
                            ))
                        },
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Checkbox(allowDividing, null)
                        Text("Permitir dividirlo")
                    }
                    if (allowDividing) NumericField("¿En cuántas partes?", unitDivisions, { value ->
                        unitDivisions = value
                        val divisions = value.toIntOrNull()
                        unitError = if (divisions == null || divisions !in 2..100) "Indica entre 2 y 100 partes." else null
                        if (divisions != null && divisions in 2..100) onSaveDish(dish.copy(
                            unitName = definition.singular, unitPlural = definition.plural,
                            unitGender = definition.gender, unitAmount = parseDecimal(selectedUnitAmount),
                            wholeUnitsOnly = false, unitDivisions = divisions
                        ))
                    }, Modifier.fillMaxWidth())
                    unitError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Este plato es adecuado para…", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                HorizontalDivider()
                MultiSelectDishField(
                    label = "Comidas",
                    selectedLabels = MealType.entries.filter { it in dish.allowedMealTypes }.map { it.label },
                    options = MealType.entries.map { it.name to it.label },
                    selectedKeys = dish.allowedMealTypes.mapTo(mutableSetOf()) { it.name },
                    onSelectionChange = { keys ->
                        onSaveDish(dish.copy(allowedMealTypes = keys.mapNotNull { key -> runCatching { MealType.valueOf(key) }.getOrNull() }.toSet()))
                    }
                )
                MultiSelectDishField(
                    label = "Días",
                    selectedLabels = WeekDay.entries.filter { it in dish.allowedDays }.map { it.label },
                    options = WeekDay.entries.map { it.name to it.label },
                    selectedKeys = dish.allowedDays.mapTo(mutableSetOf()) { it.name },
                    onSelectionChange = { keys ->
                        onSaveDish(dish.copy(allowedDays = keys.mapNotNull { key -> runCatching { WeekDay.valueOf(key) }.getOrNull() }.toSet()))
                    }
                )
                Text(
                    "Las comidas y días que desmarques quedan excluidos del generador semanal.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Ingredientes", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                HorizontalDivider()
                dish.ingredients.forEachIndexed { index, ingredient ->
                    val food = foodsById[ingredient.foodId]
                    Row(
                        Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        if (food != null) {
                            SmallFoodCategoryBadge(food.category)
                            Text(
                                food.name,
                                Modifier.weight(1f).clickable { onOpenFood(food.id) },
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis
                            )
                        } else {
                            Spacer(Modifier.size(24.dp))
                            Text("Alimento eliminado", Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        OutlinedTextField(
                            value = ingredientAmounts[ingredient.foodId] ?: formatDecimal(ingredient.grams),
                            onValueChange = { raw ->
                                val filtered = raw.filter { it.isDigit() || it == ',' || it == '.' }.take(8)
                                ingredientAmounts = ingredientAmounts + (ingredient.foodId to filtered)
                                val grams = parseDecimal(filtered)
                                if (grams != null && grams in 0.1..5000.0) {
                                    ingredientError = null
                                    onSaveDish(dish.copy(ingredients = dish.ingredients.map {
                                        if (it.foodId == ingredient.foodId) it.copy(grams = grams) else it
                                    }))
                                } else if (filtered.isNotBlank()) {
                                    ingredientError = "Los gramos deben estar entre 0,1 y 5.000."
                                }
                            },
                            modifier = Modifier.width(104.dp),
                            suffix = { Text("g") },
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            singleLine = true
                        )
                        IconButton(
                            onClick = {
                                if (dish.ingredients.size > 1) {
                                    ingredientAmounts = ingredientAmounts - ingredient.foodId
                                    onSaveDish(dish.copy(ingredients = dish.ingredients.filterNot { it.foodId == ingredient.foodId }))
                                } else {
                                    ingredientError = "Un plato debe tener al menos un ingrediente."
                                }
                            }
                        ) {
                            Icon(Icons.Default.Delete, "Quitar ingrediente")
                        }
                    }
                    if (index < dish.ingredients.lastIndex) HorizontalDivider()
                }
                ingredientError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                OutlinedButton(onClick = { addingIngredient = true }, Modifier.fillMaxWidth()) {
                    Icon(Icons.Default.Add, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Añadir ingrediente")
                }
            }
        }




    }
}


@Composable
private fun MultiSelectDishField(
    label: String,
    selectedLabels: List<String>,
    options: List<Pair<String, String>>,
    selectedKeys: Set<String>,
    onSelectionChange: (Set<String>) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    val displayValue = when {
        selectedLabels.size == options.size -> "Todos"
        selectedLabels.isEmpty() -> "Ninguno"
        else -> selectedLabels.joinToString()
    }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = displayValue,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth(),
            maxLines = 2
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { (key, optionLabel) ->
                DropdownMenuItem(
                    leadingIcon = { Checkbox(checked = key in selectedKeys, onCheckedChange = null) },
                    text = { Text(optionLabel) },
                    onClick = {
                        onSelectionChange(if (key in selectedKeys) selectedKeys - key else selectedKeys + key)
                    }
                )
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
    initialFoodId: Long? = null,
    preferredFoodIds: Set<Long>,
    onSave: (Dish) -> Unit,
    onDelete: (() -> Unit)? = null
) {
    var name by rememberSaveable(initial?.id) { mutableStateOf(initial?.name.orEmpty()) }
    var ingredientAmounts by remember(initial?.id, initialFoodId) {
        mutableStateOf(
            initial?.ingredients?.associate { it.foodId to formatDecimal(it.grams) }
                ?: initialFoodId?.let { mapOf(it to "100") }
                ?: emptyMap<Long, String>()
        )
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
                    onSave(
                        initial?.copy(name = name.trim(), ingredients = ingredients)
                            ?: Dish(System.currentTimeMillis(), name.trim(), ingredients)
                    )
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
private fun SearchNutritionGrid(
    calories: Double?,
    protein: Double?,
    carbohydrates: Double?,
    fat: Double?,
    modifier: Modifier = Modifier
) {
    val color = MaterialTheme.colorScheme.onSurfaceVariant
    fun display(value: Double?): String = value?.let {
        if (abs(it) < 10.0) formatOneDecimal(it) else it.roundToInt().toString()
    } ?: "—"

    @Composable
    fun Metric(
        icon: ImageVector,
        label: String,
        value: String,
        alignEnd: Boolean,
        modifier: Modifier
    ) {
        Row(
            modifier,
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = if (alignEnd) Arrangement.End else Arrangement.Start
        ) {
            if (alignEnd) {
                Text(value, style = MaterialTheme.typography.bodyLarge, color = color, maxLines = 1)
                Spacer(Modifier.width(2.dp))
                Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(17.dp))
            } else {
                Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(17.dp))
                Spacer(Modifier.width(2.dp))
                Text(value, style = MaterialTheme.typography.bodyLarge, color = color, maxLines = 1)
            }
        }
    }

    Column(modifier, verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            Metric(
                Icons.Default.LocalFireDepartment, "Calorías", display(calories), false,
                Modifier.width(46.dp)
            )
            Spacer(Modifier.width(6.dp))
            Metric(
                foodCategoryIcon(FoodCategory.PROTEIN), "Proteínas", display(protein), true,
                Modifier.width(46.dp)
            )
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            Metric(
                foodCategoryIcon(FoodCategory.CARBOHYDRATE), "Carbohidratos",
                display(carbohydrates), false, Modifier.width(46.dp)
            )
            Spacer(Modifier.width(6.dp))
            Metric(
                foodCategoryIcon(FoodCategory.FAT), "Grasas", display(fat), true,
                Modifier.width(46.dp)
            )
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

@Composable
private fun foodCategoryColor(category: FoodCategory): Color =
    MaterialTheme.colorScheme.onSurfaceVariant

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
            MaterialTheme.colorScheme.onSurfaceVariant, Modifier.weight(1.25f)
        )
        NutrientIconValue(
            Icons.Default.FitnessCenter, "Proteínas", food.proteinGrams, "g",
            MaterialTheme.colorScheme.onSurface, Modifier.weight(1f)
        )
        NutrientIconValue(
            Icons.Default.Grain, "Carbohidratos", food.carbohydrateGrams, "g",
            MaterialTheme.colorScheme.onSurface, Modifier.weight(1f)
        )
        NutrientIconValue(
            Icons.Default.Opacity, "Grasas", food.fatGrams, "g",
            MaterialTheme.colorScheme.onSurface, Modifier.weight(1f)
        )
    }
}

@Composable
private fun FoodSecondaryNutritionStrip(food: Food) {
    val nutrients = listOf(
        Triple(Icons.Default.Circle, "Grasas saturadas", food.saturatedFatGrams),
        Triple(Icons.Default.Cake, "Azúcares", food.sugarGrams),
        Triple(Icons.Default.Eco, "Fibra", food.fiberGrams),
        Triple(Icons.Default.AcUnit, "Sal", food.saltGrams)
    ).filter { it.third != null }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        nutrients.forEach { (icon, label, value) ->
            NutrientIconValue(
                icon, label, value, "g",
                MaterialTheme.colorScheme.onSurfaceVariant, Modifier.weight(1f)
            )
        }
    }
}

@Composable
private fun SimilarFoodEntry(food: Food, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        FoodCategoryBadge(food.category)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(
                food.name,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            Text(
                food.category.label,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1
            )
        }
        SearchNutritionGrid(
            calories = food.calories,
            protein = food.proteinGrams,
            carbohydrates = food.carbohydrateGrams,
            fat = food.fatGrams,
            modifier = Modifier.width(98.dp)
        )
    }
}

private data class FoodUnitDefinition(
    val singular: String,
    val plural: String,
    val gender: String
) {
    val label: String get() = singular
}

private val defaultUnitDefinitions = listOf(
    FoodUnitDefinition("unidad", "unidades", "FEMININE"),
    FoodUnitDefinition("pieza", "piezas", "FEMININE"),
    FoodUnitDefinition("porción", "porciones", "FEMININE"),
    FoodUnitDefinition("vaso", "vasos", "MASCULINE"),
    FoodUnitDefinition("taza", "tazas", "FEMININE"),
    FoodUnitDefinition("cucharada", "cucharadas", "FEMININE"),
    FoodUnitDefinition("cucharadita", "cucharaditas", "FEMININE"),
    FoodUnitDefinition("lata", "latas", "FEMININE"),
    FoodUnitDefinition("bote", "botes", "MASCULINE"),
    FoodUnitDefinition("paquete", "paquetes", "MASCULINE"),
    FoodUnitDefinition("loncha", "lonchas", "FEMININE"),
    FoodUnitDefinition("rebanada", "rebanadas", "FEMININE")
)

@Composable
private fun FoodDetailScreen(
    food: Food,
    foods: List<Food>,
    activeMealTypes: Set<MealType>,
    onBack: () -> Unit,
    plannedMeals: List<PlannedMeal>,
    dishes: List<Dish>,
    onOpenFood: (Long) -> Unit,
    onOpenDish: (Long) -> Unit,
    onOpenMeal: (Long) -> Unit,
    onAddToMeal: (Long) -> Unit,
    onAddNewMeal: () -> Unit,
    onAddDish: () -> Unit,
    planningRules: List<PlanningRule>,
    onSavePlanningRule: (PlanningRule) -> Unit,
    onDeletePlanningRule: (Long) -> Unit,
    onSaveFood: (Food) -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    var confirmDelete by remember { mutableStateOf(false) }
    var menuExpanded by remember { mutableStateOf(false) }
    val uriHandler = LocalUriHandler.current
    val similarFoods = remember(food, foods) { FoodSimilarityEngine.findMoreEfficient(food, foods) }
    val containingDishes = remember(food.id, dishes) {
        dishes.filter { dish -> dish.ingredients.any { it.foodId == food.id } }
    }
    val scrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior(
        rememberTopAppBarState()
    )
    val secondaryNutrition = listOfNotNull(
        food.saturatedFatGrams?.let { "Grasas saturadas: ${formatDecimal(it)} g" },
        food.sugarGrams?.let { "Azúcares: ${formatDecimal(it)} g" },
        food.fiberGrams?.let { "Fibra: ${formatDecimal(it)} g" },
        food.saltGrams?.let { "Sal: ${formatDecimal(it)} g" }
    )
    val unitDescription = when {
        food.unitName.isNullOrBlank() -> "Unidad habitual: no definida"
        food.unitAmount == null -> "Unidad habitual: 1 ${food.unitName}"
        else -> "Unidad habitual: 1 ${food.unitName} = ${formatDecimal(food.unitAmount)} g o ml · " +
            if (food.wholeUnitsOnly) "Unidad completa"
            else "Divisible en ${food.unitDivisions.coerceAtLeast(2)} partes"
    }

    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("¿Eliminar ${food.name}?") },
            text = { Text("Se eliminará del catálogo de alimentos. Esta acción no se puede deshacer.") },
            confirmButton = {
                TextButton(onClick = onDelete) {
                    Text("Eliminar", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmDelete = false }) { Text("Cancelar") }
            }
        )
    }

    Scaffold(
        modifier = Modifier
            .fillMaxSize()
            .nestedScroll(scrollBehavior.nestedScrollConnection),
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            LargeTopAppBar(
                title = {
                    Text(
                        food.name,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
                actions = {
                    Box {
                        IconButton(onClick = { menuExpanded = true }) {
                            Icon(Icons.Default.MoreVert, contentDescription = "Opciones")
                        }
                        DropdownMenu(
                            expanded = menuExpanded,
                            onDismissRequest = { menuExpanded = false }
                        ) {
                            DropdownMenuItem(
                                text = { Text("Crear plato con este alimento") },
                                onClick = {
                                    menuExpanded = false
                                    onAddDish()
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("Editar") },
                                onClick = {
                                    menuExpanded = false
                                    onEdit()
                                }
                            )
                            DropdownMenuItem(
                                text = { Text("Eliminar") },
                                onClick = {
                                    menuExpanded = false
                                    confirmDelete = true
                                }
                            )
                        }
                    }
                },
                scrollBehavior = scrollBehavior
            )
        }
    ) { innerPadding ->
        Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(top = innerPadding.calculateTopPadding())
                .padding(start = 16.dp, end = 16.dp, bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Column(
                Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                listOfNotNull(food.brand, food.subcategory ?: food.family)
                    .joinToString(" · ")
                    .takeIf { it.isNotBlank() }
                    ?.let {
                        Text(
                            it,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.bodyLarge
                        )
                    }
                Text(
                    food.category.label,
                    color = foodCategoryColor(food.category),
                    style = MaterialTheme.typography.bodyMedium
                )
                HorizontalDivider()
                Text(
                    "Valores por 100 g o 100 ml",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                FoodPrimaryNutritionStrip(food)
                if (secondaryNutrition.isNotEmpty()) {
                    Text(
                        secondaryNutrition.joinToString(" · "),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                food.legalName?.let {
                    HorizontalDivider()
                    Text(
                        it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                food.ingredients?.let {
                    Text(
                        it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                HorizontalDivider()
                Text(
                    unitDescription,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (food.links.isNotEmpty()) {
                    HorizontalDivider()
                    food.links.forEachIndexed { index, link ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clickable { uriHandler.openUri(link) }
                                .padding(vertical = 7.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            Text(
                                if (linkLabel(link).contains("mercadona", ignoreCase = true)) {
                                    "Ver producto en Mercadona"
                                } else {
                                    "Ver fuente: ${linkLabel(link)}"
                                },
                                modifier = Modifier.weight(1f),
                                color = MaterialTheme.colorScheme.primary
                            )
                            Icon(
                                Icons.AutoMirrored.Filled.OpenInNew,
                                contentDescription = "Abrir enlace",
                                tint = MaterialTheme.colorScheme.primary
                            )
                        }
                        if (index < food.links.lastIndex) HorizontalDivider()
                    }
                }
            }

            PlanningRuleCards(
                itemKind = PlannedItemKind.FOOD,
                itemId = food.id,
                defaultGrams = 100.0,
                rules = planningRules,
                activeMealTypes = activeMealTypes,
                onSave = onSavePlanningRule,
                onDelete = onDeletePlanningRule
            )

            Card(Modifier.fillMaxWidth()) {
                Column(
                    Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text("En qué platos puedes comerlo", style = MaterialTheme.typography.titleLarge)
                    HorizontalDivider()
                    if (containingDishes.isEmpty()) {
                        Text(
                            "Todavía no hay ningún plato que contenga este alimento.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    } else {
                        containingDishes.forEachIndexed { index, dish ->
                            Row(
                                Modifier
                                    .fillMaxWidth()
                                    .clickable { onOpenDish(dish.id) }
                                    .padding(vertical = 10.dp)
                            ) {
                                Text(dish.name, Modifier.weight(1f))
                                Icon(Icons.AutoMirrored.Filled.ArrowForward, "Abrir plato")
                            }
                            if (index < containingDishes.lastIndex) HorizontalDivider()
                        }
                    }
                    TextButton(onClick = onAddDish) {
                        Icon(Icons.Default.Add, contentDescription = null)
                        Spacer(Modifier.width(6.dp))
                        Text("Crear plato con este alimento")
                    }
                }
            }

            Column(
                Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text("Alternativas más eficientes", style = MaterialTheme.typography.titleLarge)
                HorizontalDivider()
                Text(
                    "Cumplen una función parecida, pero aprovechan mejor sus calorías o su nutriente principal.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (similarFoods.isEmpty()) {
                    Text(
                        "No hay alternativas parecidas que sean claramente más eficientes.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                } else {
                    similarFoods.forEachIndexed { index, similar ->
                        SimilarFoodEntry(
                            food = similar,
                            onClick = { onOpenFood(similar.id) }
                        )
                        if (index < similarFoods.lastIndex) {
                            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun UnitDefinitionField(
    selected: FoodUnitDefinition?,
    options: List<FoodUnitDefinition>,
    onSelect: (FoodUnitDefinition) -> Unit,
    onCreateNew: () -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded, { expanded = it }) {
        OutlinedTextField(
            value = selected?.label.orEmpty(),
            onValueChange = {},
            readOnly = true,
            label = { Text("Elegir una unidad") },
            placeholder = { Text("Elegir una unidad") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth()
        )
        ExposedDropdownMenu(expanded, { expanded = false }) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = { Text(option.label) },
                    onClick = { onSelect(option); expanded = false }
                )
            }
            if (options.isNotEmpty()) HorizontalDivider()
            DropdownMenuItem(
                leadingIcon = { Icon(Icons.Default.Add, contentDescription = null) },
                text = { Text("Crear nueva unidad") },
                onClick = { expanded = false; onCreateNew() }
            )
        }
    }
}

@Composable
private fun NewFoodUnitDialog(
    foodName: String,
    onCreate: (FoodUnitDefinition) -> Unit,
    onDismiss: () -> Unit
) {
    var unitName by rememberSaveable { mutableStateOf("") }
    var unitPlural by rememberSaveable { mutableStateOf("") }
    var gender by rememberSaveable { mutableStateOf("MASCULINE") }
    var error by remember { mutableStateOf<String?>(null) }
    ModalBottomSheet(onDismissRequest = onDismiss) {
            Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Nueva unidad para $foodName", style = MaterialTheme.typography.headlineSmall)
                OutlinedTextField(
                    value = unitName,
                    onValueChange = { unitName = it.take(40) },
                    label = { Text("Singular") },
                    placeholder = { Text("vasito, huevo, lata…") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(unitPlural, { unitPlural = it.take(40) }, Modifier.fillMaxWidth(), label = { Text("Plural") }, placeholder = { Text("vasitos, huevos, latas…") }, singleLine = true)
                SelectorField("Género gramatical", if (gender == "FEMININE") "Femenino" else "Masculino", listOf("MASCULINE", "FEMININE"), { if (it == "FEMININE") "Femenino" else "Masculino" }, { gender = it }, null)
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                Button(onClick = {
                error = when {
                    unitName.isBlank() -> "Indica el singular."
                    unitPlural.isBlank() -> "Indica también el plural."
                    else -> null
                }
                if (error == null) onCreate(FoodUnitDefinition(unitName.trim(), unitPlural.trim(), gender))
            }, Modifier.fillMaxWidth()) { Text("Crear unidad") }
                TextButton(onClick = onDismiss, Modifier.fillMaxWidth()) { Text("Cancelar") }
                Spacer(Modifier.height(16.dp))
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
    var unitName by rememberSaveable(initial?.id) { mutableStateOf(initial?.unitName.orEmpty()) }
    var unitAmount by rememberSaveable(initial?.id) { mutableStateOf(initial?.unitAmount?.let(::formatDecimal).orEmpty()) }
    var wholeUnitsOnly by rememberSaveable(initial?.id) { mutableStateOf(initial?.wholeUnitsOnly == true) }
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
        Text("Unidades", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        OutlinedTextField(
            value = unitName,
            onValueChange = { unitName = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Nombre de la unidad (opcional)") },
            placeholder = { Text("Vasito, huevo, loncha…") },
            singleLine = true
        )
        NumericField("Gramos o ml por unidad", unitAmount, { unitAmount = it }, Modifier.fillMaxWidth())
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Checkbox(
                checked = wholeUnitsOnly,
                onCheckedChange = { wholeUnitsOnly = it }
            )
            Text("Usar solo unidades completas")
        }
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
                val parsedUnitAmount = unitAmount.takeIf { it.isNotBlank() }?.let(::parseDecimal)
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
                    unitName.isBlank() != unitAmount.isBlank() ->
                        "Indica tanto el nombre de la unidad como su equivalencia."
                    unitName.trim().length > 40 -> "El nombre de la unidad no puede superar 40 caracteres."
                    unitAmount.isNotBlank() && (parsedUnitAmount == null || parsedUnitAmount !in 0.1..5000.0) ->
                        "La equivalencia debe estar entre 0,1 y 5000 g o ml."
                    wholeUnitsOnly && unitName.isBlank() ->
                        "Define una unidad antes de exigir unidades completas."
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
                            links = parsedLinks,
                            unitName = unitName.trim().ifBlank { null },
                            unitAmount = parsedUnitAmount,
                            wholeUnitsOnly = wholeUnitsOnly
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
                    "Indica qué porcentaje del total diario corresponde a cada comida. Usa 0 % para saltarte el almuerzo o la merienda. La suma debe ser 100 %.",
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
    mealShares: Map<MealType, Double>,
    onCreate: (UserProfile, Map<MealType, Double>) -> Unit,
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
    var photoUri by rememberSaveable(editedProfile?.id, creating) { mutableStateOf(editedProfile?.photoUri) }
    var error by rememberSaveable { mutableStateOf<String?>(null) }
    var pendingDelete by remember { mutableStateOf<UserProfile?>(null) }
    var mealSizes by remember(editedProfile?.id, creating) {
        mutableStateOf(MealType.entries.associateWith { type ->
            when {
                (mealShares[type] ?: 0.0) <= 0.0 -> "NONE"
                (mealShares[type] ?: 0.0) >= 0.28 -> "LARGE"
                (mealShares[type] ?: 0.0) >= 0.15 -> "NORMAL"
                else -> "SMALL"
            }
        })
    }
    val context = LocalContext.current
    val photoPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        uri ?: return@rememberLauncherForActivityResult
        runCatching {
            context.contentResolver.takePersistableUriPermission(
                uri, android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION
            )
        }
        photoUri = uri.toString()
    }

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
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    ProfileAvatar(
                        UserProfile(1, name.ifBlank { "Perfil" }, 170.0, 1990, sex, photoUri),
                        64.dp
                    )
                    Column {
                        TextButton(onClick = { photoPicker.launch(arrayOf("image/*")) }) { Text("Elegir foto") }
                        if (photoUri != null) TextButton(onClick = { photoUri = null }) { Text("Quitar foto") }
                    }
                }
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
                        "Indica cómo de grande suele ser cada comida. Las que no hagas se eliminarán del menú.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    MealType.entries.forEach { type ->
                        SelectorField(
                            label = type.label,
                            selectedLabel = when (mealSizes[type]) { "LARGE" -> "Grande"; "NORMAL" -> "Normal"; "NONE" -> "No la hago"; else -> "Pequeña" },
                            options = listOf("NONE", "SMALL", "NORMAL", "LARGE"),
                            optionLabel = { when (it) { "LARGE" -> "Grande"; "NORMAL" -> "Normal"; "NONE" -> "No la hago"; else -> "Pequeña" } },
                            onSelect = { mealSizes = mealSizes + (type to it) },
                            onClear = null
                        )
                    }
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
                    sex = sex,
                    photoUri = photoUri
                )
                val weights = MealType.entries.associateWith { type -> when (mealSizes[type]) { "LARGE" -> 3.0; "NORMAL" -> 2.0; "NONE" -> 0.0; else -> 1.0 } }
                val weightTotal = weights.values.sum()
                val parsedShares = weights.mapValues { if (weightTotal > 0.0) it.value / weightTotal else 0.0 }
                error = when {
                    !candidate.isValid() -> "Revisa el nombre, la altura y el año de nacimiento. La app está diseñada para personas adultas."
                    creating && weightTotal <= 0.0 -> "Selecciona al menos una comida que sí hagas."
                    else -> null
                }
                if (error == null) {
                    if (creating) onCreate(candidate, parsedShares) else onSave(candidate)
                    creating = false
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(
                when {
                    creating -> "Crear perfil"
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
    selectedLabel: String,
    options: List<T>,
    optionLabel: (T) -> String,
    onSelect: (T) -> Unit,
    onClear: (() -> Unit)?
) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = selectedLabel,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth()
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
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
