package es.david.rumbo.data

import android.content.Context
import androidx.core.content.edit
import es.david.rumbo.logic.RecommendationEngine
import es.david.rumbo.model.ActivityLevel
import es.david.rumbo.model.AesanFoodCatalog
import es.david.rumbo.model.AppData
import es.david.rumbo.model.DietCompliance
import es.david.rumbo.model.Dish
import es.david.rumbo.model.DishIngredient
import es.david.rumbo.model.DefaultFoodCatalog
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.Measurement
import es.david.rumbo.model.MealType
import es.david.rumbo.model.MealDayAmounts
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedDish
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.ProfileData
import es.david.rumbo.model.Sex
import es.david.rumbo.model.UserProfile
import es.david.rumbo.model.WeightGoal
import es.david.rumbo.model.WeekDay
import es.david.rumbo.model.sanitizedDayAmounts
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate

class AppRepository(context: Context) {
    private val preferences = context.getSharedPreferences("rumbo_data", Context.MODE_PRIVATE)
    private val baseFoods: List<Food> by lazy {
        (DefaultFoodCatalog.items + AesanFoodCatalog.load(context))
            .distinctBy { it.id }
            .sortedWith(foodComparator)
    }
    private val baseFoodsById: Map<Long, Food> by lazy { baseFoods.associateBy { it.id } }

    fun load(): AppData {
        val raw = preferences.getString(KEY_DATA, null)
            ?: return AppData(foods = baseFoods)
        return runCatching { normalize(decode(raw)) }
            .getOrElse { AppData(foods = baseFoods) }
    }

    fun saveProfile(profile: UserProfile): AppData {
        val current = load()
        val existing = current.profiles.firstOrNull { it.profile.id == profile.id }
        val updatedProfile = ProfileData(
            profile = profile,
            measurements = recalculate(profile, existing?.measurements.orEmpty()),
            plannedMeals = existing?.plannedMeals.orEmpty()
        )
        val profiles = if (existing == null) {
            current.profiles + updatedProfile
        } else {
            current.profiles.map { if (it.profile.id == profile.id) updatedProfile else it }
        }
        return persistAndReturn(AppData(profiles, profile.id, current.foods, current.dishes))
    }

    fun saveProfileWithBaseline(profile: UserProfile, baseline: Measurement): AppData {
        require(baseline.weightKg != null && baseline.waistCm != null && baseline.goal != null) {
            "El perfil inicial necesita peso, cintura y objetivo"
        }
        val current = load()
        val existing = current.profiles.firstOrNull { it.profile.id == profile.id }
        val source = existing?.measurements.orEmpty().filterNot { it.id == baseline.id } +
            baseline.copy(recommendation = null)
        val updatedProfile = ProfileData(
            profile = profile,
            measurements = recalculate(profile, source),
            plannedMeals = existing?.plannedMeals.orEmpty()
        )
        val profiles = if (existing == null) {
            current.profiles + updatedProfile
        } else {
            current.profiles.map { if (it.profile.id == profile.id) updatedProfile else it }
        }
        return persistAndReturn(AppData(profiles, profile.id, current.foods, current.dishes))
    }

    fun switchProfile(profileId: Long): AppData {
        val current = load()
        if (current.profiles.none { it.profile.id == profileId }) return current
        return persistAndReturn(current.copy(activeProfileId = profileId))
    }

    fun deleteProfile(profileId: Long): AppData {
        val current = load()
        if (current.profiles.size <= 1) return current
        val remaining = current.profiles.filterNot { it.profile.id == profileId }
        val activeId = if (current.activeProfileId == profileId) remaining.first().profile.id
            else current.activeProfileId
        return persistAndReturn(AppData(remaining, activeId, current.foods, current.dishes))
    }

    fun addMeasurement(draft: Measurement): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        val source = active.measurements.filterNot { it.id == draft.id } + draft.copy(recommendation = null)
        return updateActive(current, active.copy(measurements = recalculate(active.profile, source)))
    }

    fun setGoal(goal: WeightGoal): AppData = setWeeklyRate(
        if (goal == WeightGoal.AUTOMATIC) null
        else RecommendationEngine.weeklyRateFor(goal, load().activeProfileData
            ?.let { RecommendationEngine.effectiveValues(it.measurements).weightKg })
    )

    fun setWeeklyRate(weeklyRateKg: Double?): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        val effective = RecommendationEngine.effectiveValues(active.measurements)
        if (weeklyRateKg == null && effective.goal == WeightGoal.AUTOMATIC) return current
        if (weeklyRateKg != null && effective.weeklyRateKg == weeklyRateKg) return current
        val goal = when {
            weeklyRateKg == null -> WeightGoal.AUTOMATIC
            weeklyRateKg < 0.0 -> WeightGoal.LOSE_SLOWLY
            weeklyRateKg > 0.0 -> WeightGoal.GAIN_SLOWLY
            else -> WeightGoal.MAINTAIN
        }
        return addMeasurement(
            Measurement(
                id = System.currentTimeMillis(),
                date = LocalDate.now(),
                goal = goal,
                weeklyRateKg = weeklyRateKg
            )
        )
    }

    fun deleteMeasurement(id: Long): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        val remaining = active.measurements.filterNot { it.id == id }
        return updateActive(current, active.copy(measurements = recalculate(active.profile, remaining)))
    }

    fun saveFood(food: Food): AppData {
        require(food.isValid()) { "El alimento no es válido" }
        val current = load()
        val foods = (current.foods.filterNot { it.id == food.id } + food)
            .sortedWith(foodComparator)
        return persistAndReturn(current.copy(foods = foods))
    }

    fun deleteFood(id: Long): AppData {
        val current = load()
        val dishes = current.dishes.mapNotNull { dish ->
            val ingredients = dish.ingredients.filterNot { it.foodId == id }
            dish.copy(ingredients = ingredients).takeIf { ingredients.isNotEmpty() }
        }
        val dishIds = dishes.mapTo(mutableSetOf()) { it.id }
        val profiles = current.profiles.map { profileData ->
            profileData.copy(
                plannedMeals = profileData.plannedMeals.mapNotNull { meal ->
                    val remaining = meal.items.filterNot { it.foodId == id }
                    val plannedDishes = meal.dishes.filter { it.dishId in dishIds }
                    meal.copy(items = remaining, dishes = plannedDishes).sanitizedDayAmounts()
                        .takeIf { remaining.isNotEmpty() || plannedDishes.isNotEmpty() }
                }
            )
        }
        return persistAndReturn(
            current.copy(
                profiles = profiles,
                foods = current.foods.filterNot { it.id == id },
                dishes = dishes
            )
        )
    }

    fun saveDish(dish: Dish): AppData {
        require(dish.isValid()) { "El plato no es válido" }
        val current = load()
        require(dish.ingredients.all { ingredient -> current.foods.any { it.id == ingredient.foodId } }) {
            "El plato contiene alimentos inexistentes"
        }
        val dishes = (current.dishes.filterNot { it.id == dish.id } + dish)
            .sortedWith(dishComparator)
        return persistAndReturn(current.copy(dishes = dishes))
    }

    fun deleteDish(id: Long): AppData {
        val current = load()
        val profiles = current.profiles.map { profileData ->
            profileData.copy(
                plannedMeals = profileData.plannedMeals.mapNotNull { meal ->
                    val dishes = meal.dishes.filterNot { it.dishId == id }
                    meal.copy(dishes = dishes).sanitizedDayAmounts()
                        .takeIf { meal.items.isNotEmpty() || dishes.isNotEmpty() }
                }
            )
        }
        return persistAndReturn(
            current.copy(profiles = profiles, dishes = current.dishes.filterNot { it.id == id })
        )
    }

    fun savePlannedMeal(meal: PlannedMeal): AppData {
        val sanitized = meal.sanitizedDayAmounts()
        require(sanitized.isValid()) { "La comida planificada no es válida" }
        val current = load()
        val active = current.activeProfileData ?: return current
        require(sanitized.items.all { item -> current.foods.any { it.id == item.foodId } }) {
            "La comida contiene alimentos inexistentes"
        }
        require(sanitized.dishes.all { item -> current.dishes.any { it.id == item.dishId } }) {
            "La comida contiene platos inexistentes"
        }
        val otherMeals = active.plannedMeals.filterNot { it.id == sanitized.id }
        require(otherMeals.none { it.type == sanitized.type && it.days.any(sanitized.days::contains) }) {
            "Ya hay otra comida de este tipo en alguno de los días seleccionados"
        }
        val updated = active.copy(
            plannedMeals = (otherMeals + sanitized).sortedWith(plannedMealComparator)
        )
        return updateActive(current, updated)
    }

    fun savePlannedMeals(meals: List<PlannedMeal>): AppData {
        val sanitized = meals.map { it.sanitizedDayAmounts() }
        val current = load()
        val active = current.activeProfileData ?: return current
        require(sanitized.all { it.isValid() }) { "Hay alguna comida planificada no válida" }
        val foodIds = current.foods.mapTo(mutableSetOf()) { it.id }
        val dishIds = current.dishes.mapTo(mutableSetOf()) { it.id }
        require(sanitized.flatMap { it.items }.all { it.foodId in foodIds }) {
            "Hay comidas con alimentos inexistentes"
        }
        require(sanitized.flatMap { it.dishes }.all { it.dishId in dishIds }) {
            "Hay comidas con platos inexistentes"
        }
        require(MealType.entries.all { type ->
            val days = sanitized.filter { it.type == type }.flatMap { it.days }
            days.distinct().size == days.size
        }) { "Hay comidas del mismo tipo que se solapan" }
        return updateActive(
            current,
            active.copy(plannedMeals = sanitized.sortedWith(plannedMealComparator))
        )
    }

    fun deletePlannedMeal(id: Long): AppData {
        val current = load()
        val active = current.activeProfileData ?: return current
        return updateActive(
            current,
            active.copy(plannedMeals = active.plannedMeals.filterNot { it.id == id })
        )
    }

    fun exportJson(): String = encode(load()).toString(2)

    fun importJson(raw: String): AppData {
        val decoded = decode(raw)
        validate(decoded)
        return persistAndReturn(normalize(decoded))
    }

    private fun updateActive(current: AppData, updated: ProfileData): AppData = persistAndReturn(
        current.copy(profiles = current.profiles.map {
            if (it.profile.id == updated.profile.id) updated else it
        })
    )

    private fun persistAndReturn(data: AppData): AppData {
        preferences.edit { putString(KEY_DATA, encode(data).toString()) }
        return data
    }

    private fun normalize(data: AppData): AppData {
        val foods = data.foods.ifEmpty { baseFoods }
        val foodIds = foods.mapTo(mutableSetOf()) { it.id }
        val dishes = data.dishes.mapNotNull { dish ->
            val ingredients = dish.ingredients.filter { it.foodId in foodIds }
            dish.copy(ingredients = ingredients).takeIf { ingredients.isNotEmpty() }
        }.sortedWith(dishComparator)
        val dishIds = dishes.mapTo(mutableSetOf()) { it.id }
        val profiles = data.profiles.map { profileData ->
            profileData.copy(
                measurements = recalculate(profileData.profile, profileData.measurements),
                plannedMeals = profileData.plannedMeals.mapNotNull { meal ->
                    val items = meal.items.filter { it.foodId in foodIds }
                    val plannedDishes = meal.dishes.filter { it.dishId in dishIds }
                    meal.copy(items = items, dishes = plannedDishes).sanitizedDayAmounts()
                        .takeIf { items.isNotEmpty() || plannedDishes.isNotEmpty() }
                }.sortedWith(plannedMealComparator)
            )
        }
        val activeId = data.activeProfileId?.takeIf { id -> profiles.any { it.profile.id == id } }
            ?: profiles.firstOrNull()?.profile?.id
        return AppData(profiles, activeId, foods, dishes)
    }

    private fun validate(data: AppData) {
        require(data.profiles.isNotEmpty()) { "La copia no contiene perfiles" }
        require(data.profiles.map { it.profile.id }.distinct().size == data.profiles.size) {
            "Hay perfiles duplicados"
        }
        require(data.profiles.all { it.profile.isValid() }) { "Hay datos personales no válidos" }
        val measurements = data.profiles.flatMap { it.measurements }
        require(measurements.all { it.weightKg == null || it.weightKg in 30.0..350.0 }) {
            "Hay algún peso fuera de rango"
        }
        require(measurements.all { it.waistCm == null || it.waistCm in 35.0..250.0 }) {
            "Hay alguna cintura fuera de rango"
        }
        require(measurements.all { it.weeklyRateKg == null || it.weeklyRateKg in -5.0..5.0 }) {
            "Hay algún objetivo semanal fuera de rango"
        }
        require(data.foods.all { it.isValid() }) { "Hay algún alimento no válido" }
        require(data.foods.map { it.id }.distinct().size == data.foods.size) {
            "Hay alimentos duplicados"
        }
        val foodIds = data.foods.mapTo(mutableSetOf()) { it.id }
        require(data.dishes.all { it.isValid() }) { "Hay algún plato no válido" }
        require(data.dishes.map { it.id }.distinct().size == data.dishes.size) {
            "Hay platos duplicados"
        }
        require(data.dishes.flatMap { it.ingredients }.all { it.foodId in foodIds }) {
            "Hay platos con alimentos inexistentes"
        }
        val dishIds = data.dishes.mapTo(mutableSetOf()) { it.id }
        data.profiles.forEach { profileData ->
            val meals = profileData.plannedMeals
            require(meals.all { it.isValid() }) { "Hay alguna comida planificada no válida" }
            require(meals.map { it.id }.distinct().size == meals.size) {
                "Hay comidas planificadas duplicadas"
            }
            require(meals.flatMap { it.items }.all { it.foodId in foodIds }) {
                "Hay comidas con alimentos inexistentes"
            }
            require(meals.flatMap { it.dishes }.all { it.dishId in dishIds }) {
                "Hay comidas con platos inexistentes"
            }
            require(MealType.entries.all { type ->
                val days = meals.filter { it.type == type }.flatMap { it.days }
                days.distinct().size == days.size
            }) { "Hay comidas del mismo tipo que se solapan" }
        }
    }

    private fun recalculate(profile: UserProfile, source: List<Measurement>): List<Measurement> {
        val ordered = source.sortedWith(compareBy<Measurement> { it.date }.thenBy { it.id })
        return buildList {
            ordered.forEach { item ->
                val draft = item.copy(recommendation = null)
                add(draft.copy(recommendation = RecommendationEngine.recommend(profile, this, draft)))
            }
        }
    }

    private fun encode(data: AppData): JSONObject = JSONObject().apply {
        put("schemaVersion", 11)
        putNullable("activeProfileId", data.activeProfileId)
        put("profiles", JSONArray().apply {
            data.profiles.forEach { profileData ->
                put(JSONObject().apply {
                    put("profile", encodeProfile(profileData.profile))
                    put("measurements", encodeMeasurements(profileData.measurements))
                    put("plannedMeals", encodePlannedMeals(profileData.plannedMeals))
                })
            }
        })
        val currentFoodsById = data.foods.associateBy { it.id }
        val overrides = data.foods.filter { food -> baseFoodsById[food.id] != food }
        val deletedIds = baseFoods.asSequence().map { it.id }
            .filterNot(currentFoodsById::containsKey).toList()
        put("foodOverrides", encodeFoods(overrides))
        put("deletedFoodIds", JSONArray().apply { deletedIds.forEach(::put) })
        put("dishes", encodeDishes(data.dishes))
    }

    private fun encodeProfile(profile: UserProfile): JSONObject = JSONObject().apply {
        put("id", profile.id)
        put("name", profile.name)
        put("heightCm", profile.heightCm)
        put("birthYear", profile.birthYear)
        put("sex", profile.sex.name)
    }

    private fun encodeMeasurements(measurements: List<Measurement>): JSONArray = JSONArray().apply {
        measurements.forEach { measurement ->
            put(JSONObject().apply {
                put("id", measurement.id)
                put("date", measurement.date.toString())
                putNullable("weightKg", measurement.weightKg)
                putNullable("waistCm", measurement.waistCm)
                putNullable("activity", measurement.activity?.name)
                putNullable("compliance", measurement.compliance?.name)
                putNullable("goal", measurement.goal?.name)
                putNullable("weeklyRateKg", measurement.weeklyRateKg)
            })
        }
    }

    private fun encodeFoods(foods: List<Food>): JSONArray = JSONArray().apply {
        foods.forEach { food ->
            put(JSONObject().apply {
                put("id", food.id)
                put("name", food.name)
                put("category", food.category.name)
                putNullable("calories", food.calories)
                putNullable("fatGrams", food.fatGrams)
                putNullable("carbohydrateGrams", food.carbohydrateGrams)
                putNullable("proteinGrams", food.proteinGrams)
                putNullable("fiberGrams", food.fiberGrams)
                put("links", JSONArray().apply { food.links.forEach(::put) })
                putNullable("barcode", food.barcode)
                putNullable("brand", food.brand)
                putNullable("family", food.family)
                putNullable("subcategory", food.subcategory)
                putNullable("legalName", food.legalName)
                putNullable("ingredients", food.ingredients)
                putNullable("saturatedFatGrams", food.saturatedFatGrams)
                putNullable("sugarGrams", food.sugarGrams)
                putNullable("saltGrams", food.saltGrams)
                putNullable("retailer", food.retailer)
                putNullable("source", food.source)
            })
        }
    }

    private fun encodePlannedMeals(meals: List<PlannedMeal>): JSONArray = JSONArray().apply {
        meals.forEach { meal ->
            put(JSONObject().apply {
                put("id", meal.id)
                put("type", meal.type.name)
                put("days", JSONArray().apply {
                    WeekDay.entries.filter(meal.days::contains).forEach { put(it.name) }
                })
                put("items", JSONArray().apply {
                    meal.items.forEach { item ->
                        put(JSONObject().apply {
                            put("foodId", item.foodId)
                            put("grams", item.grams)
                            put("adjustable", item.adjustable)
                            put("minimumGrams", item.minimumGrams)
                            put("maximumGrams", item.maximumGrams)
                        })
                    }
                })
                put("dishes", JSONArray().apply {
                    meal.dishes.forEach { plannedDish ->
                        put(JSONObject().apply {
                            put("dishId", plannedDish.dishId)
                            put("grams", plannedDish.grams)
                            put("adjustable", plannedDish.adjustable)
                            put("minimumGrams", plannedDish.minimumGrams)
                            put("maximumGrams", plannedDish.maximumGrams)
                        })
                    }
                })
                put("dayAmounts", JSONArray().apply {
                    meal.dayAmounts.forEach { amounts ->
                        put(JSONObject().apply {
                            put("day", amounts.day.name)
                            put("items", JSONArray().apply {
                                amounts.foodGrams.forEach { (foodId, grams) ->
                                    put(JSONObject().apply {
                                        put("foodId", foodId)
                                        put("grams", grams)
                                    })
                                }
                            })
                            put("dishes", JSONArray().apply {
                                amounts.dishGrams.forEach { (dishId, grams) ->
                                    put(JSONObject().apply {
                                        put("dishId", dishId)
                                        put("grams", grams)
                                    })
                                }
                            })
                        })
                    }
                })
            })
        }
    }

    private fun encodeDishes(dishes: List<Dish>): JSONArray = JSONArray().apply {
        dishes.forEach { dish ->
            put(JSONObject().apply {
                put("id", dish.id)
                put("name", dish.name)
                put("ingredients", JSONArray().apply {
                    dish.ingredients.forEach { ingredient ->
                        put(JSONObject().apply {
                            put("foodId", ingredient.foodId)
                            put("grams", ingredient.grams)
                        })
                    }
                })
            })
        }
    }

    private fun decode(raw: String): AppData {
        val root = JSONObject(raw)
        val schemaVersion = root.optInt("schemaVersion", 1)
        val profilesJson = root.optJSONArray("profiles")
        if (profilesJson != null) {
            val dishes = root.optJSONArray("dishes")?.let(::decodeDishes).orEmpty()
            val dishesById = dishes.associateBy { it.id }
            val profiles = buildList {
                for (index in 0 until profilesJson.length()) {
                    val item = profilesJson.getJSONObject(index)
                    add(
                        ProfileData(
                            profile = decodeProfile(item.getJSONObject("profile")),
                            measurements = decodeMeasurements(item.optJSONArray("measurements") ?: JSONArray()),
                            plannedMeals = decodePlannedMeals(
                                item.optJSONArray("plannedMeals") ?: JSONArray(),
                                dishesById,
                                schemaVersion
                            )
                        )
                    )
                }
            }
            val foods = if (schemaVersion >= 6) {
                val overrides = root.optJSONArray("foodOverrides")?.let(::decodeFoods).orEmpty()
                val deletedIds = root.optJSONArray("deletedFoodIds")?.let(::decodeIds).orEmpty()
                mergeFoodChanges(overrides, deletedIds)
            } else {
                migrateLegacyFoods(root.optJSONArray("foods")?.let(::decodeFoods), schemaVersion)
            }
            return AppData(profiles, root.optionalLong("activeProfileId"), foods, dishes)
        }

        val legacyProfile = root.optJSONObject("profile") ?: return AppData()
        val migrated = UserProfile(
            id = 1L,
            name = "Mi perfil",
            heightCm = legacyProfile.getDouble("heightCm"),
            birthYear = legacyProfile.getInt("birthYear"),
            sex = Sex.valueOf(legacyProfile.getString("sex"))
        )
        val measurements = decodeMeasurements(root.optJSONArray("measurements") ?: JSONArray())
        return AppData(listOf(ProfileData(migrated, measurements)), migrated.id, baseFoods)
    }

    private fun decodeProfile(json: JSONObject): UserProfile = UserProfile(
        id = json.getLong("id"),
        name = json.getString("name"),
        heightCm = json.getDouble("heightCm"),
        birthYear = json.getInt("birthYear"),
        sex = Sex.valueOf(json.getString("sex"))
    )

    private fun decodeMeasurements(array: JSONArray): List<Measurement> = buildList {
        for (index in 0 until array.length()) {
            val item = array.getJSONObject(index)
            add(
                Measurement(
                    id = item.getLong("id"),
                    date = LocalDate.parse(item.getString("date")),
                    weightKg = item.optionalDouble("weightKg"),
                    waistCm = item.optionalDouble("waistCm"),
                    activity = item.optionalEnum("activity", ActivityLevel::valueOf),
                    compliance = item.optionalEnum("compliance", DietCompliance::valueOf),
                    goal = item.optionalEnum("goal", WeightGoal::valueOf),
                    weeklyRateKg = item.optionalDouble("weeklyRateKg")
                )
            )
        }
    }.sortedWith(compareBy<Measurement> { it.date }.thenBy { it.id })

    private fun decodeFoods(array: JSONArray): List<Food> = buildList {
        for (index in 0 until array.length()) {
            val item = array.getJSONObject(index)
            add(
                Food(
                    id = item.getLong("id"),
                    name = item.getString("name"),
                    category = FoodCategory.valueOf(item.getString("category")),
                    calories = item.optionalDouble("calories"),
                    fatGrams = item.optionalDouble("fatGrams"),
                    carbohydrateGrams = item.optionalDouble("carbohydrateGrams"),
                    proteinGrams = item.optionalDouble("proteinGrams"),
                    fiberGrams = item.optionalDouble("fiberGrams"),
                    links = item.optJSONArray("links")?.let { links ->
                        buildList {
                            for (linkIndex in 0 until links.length()) add(links.getString(linkIndex))
                        }
                    }.orEmpty(),
                    barcode = item.optionalString("barcode"),
                    brand = item.optionalString("brand"),
                    family = item.optionalString("family"),
                    subcategory = item.optionalString("subcategory"),
                    legalName = item.optionalString("legalName"),
                    ingredients = item.optionalString("ingredients"),
                    saturatedFatGrams = item.optionalDouble("saturatedFatGrams"),
                    sugarGrams = item.optionalDouble("sugarGrams"),
                    saltGrams = item.optionalDouble("saltGrams"),
                    retailer = item.optionalString("retailer"),
                    source = item.optionalString("source")
                )
            )
        }
    }.sortedWith(foodComparator)

    private fun decodePlannedMeals(
        array: JSONArray,
        dishesById: Map<Long, Dish>,
        schemaVersion: Int
    ): List<PlannedMeal> = buildList {
        for (index in 0 until array.length()) {
            val item = array.getJSONObject(index)
            val daysJson = item.optJSONArray("days") ?: JSONArray()
            val itemsJson = item.optJSONArray("items") ?: JSONArray()
            val dishesJson = item.optJSONArray("dishes") ?: JSONArray()
            val dayAmountsJson = item.optJSONArray("dayAmounts") ?: JSONArray()
            add(
                PlannedMeal(
                    id = item.getLong("id"),
                    type = MealType.valueOf(item.getString("type")),
                    days = buildSet {
                        for (dayIndex in 0 until daysJson.length()) {
                            add(WeekDay.valueOf(daysJson.getString(dayIndex)))
                        }
                    },
                    items = buildList {
                        for (itemIndex in 0 until itemsJson.length()) {
                            val planned = itemsJson.getJSONObject(itemIndex)
                            val grams = planned.getDouble("grams")
                            add(
                                PlannedFood(
                                    foodId = planned.getLong("foodId"),
                                    grams = grams,
                                    adjustable = schemaVersion >= 10 && planned.optBoolean("adjustable", false),
                                    minimumGrams = if (schemaVersion >= 10) planned.optDouble("minimumGrams", grams * 0.5) else grams * 0.5,
                                    maximumGrams = if (schemaVersion >= 10) planned.optDouble("maximumGrams", grams * 1.5) else grams * 1.5
                                )
                            )
                        }
                    },
                    dishes = buildList {
                        for (dishIndex in 0 until dishesJson.length()) {
                            val planned = dishesJson.getJSONObject(dishIndex)
                            val dishId = planned.getLong("dishId")
                            val grams = if (schemaVersion >= 9) {
                                planned.getDouble("grams")
                            } else {
                                val servings = planned.getDouble("servings")
                                dishesById[dishId]?.ingredients?.sumOf { it.grams }?.times(servings)
                                    ?: 0.0
                            }
                            add(
                                PlannedDish(
                                    dishId = dishId,
                                    grams = grams,
                                    adjustable = schemaVersion >= 10 && planned.optBoolean("adjustable", false),
                                    minimumGrams = if (schemaVersion >= 10) planned.optDouble("minimumGrams", grams * 0.5) else grams * 0.5,
                                    maximumGrams = if (schemaVersion >= 10) planned.optDouble("maximumGrams", grams * 1.5) else grams * 1.5
                                )
                            )
                        }
                    },
                    dayAmounts = buildList {
                        if (schemaVersion >= 10) for (amountIndex in 0 until dayAmountsJson.length()) {
                            val amounts = dayAmountsJson.getJSONObject(amountIndex)
                            val foodAmountsJson = amounts.optJSONArray("items") ?: JSONArray()
                            val dishAmountsJson = amounts.optJSONArray("dishes") ?: JSONArray()
                            add(
                                MealDayAmounts(
                                    day = WeekDay.valueOf(amounts.getString("day")),
                                    foodGrams = buildMap {
                                        for (i in 0 until foodAmountsJson.length()) {
                                            val entry = foodAmountsJson.getJSONObject(i)
                                            put(entry.getLong("foodId"), entry.getDouble("grams"))
                                        }
                                    },
                                    dishGrams = buildMap {
                                        for (i in 0 until dishAmountsJson.length()) {
                                            val entry = dishAmountsJson.getJSONObject(i)
                                            put(entry.getLong("dishId"), entry.getDouble("grams"))
                                        }
                                    }
                                )
                            )
                        }
                    }
                ).sanitizedDayAmounts()
            )
        }
    }.sortedWith(plannedMealComparator)

    private fun decodeDishes(array: JSONArray): List<Dish> = buildList {
        for (index in 0 until array.length()) {
            val item = array.getJSONObject(index)
            val ingredientsJson = item.optJSONArray("ingredients") ?: JSONArray()
            add(
                Dish(
                    id = item.getLong("id"),
                    name = item.getString("name"),
                    ingredients = buildList {
                        for (ingredientIndex in 0 until ingredientsJson.length()) {
                            val ingredient = ingredientsJson.getJSONObject(ingredientIndex)
                            add(
                                DishIngredient(
                                    ingredient.getLong("foodId"),
                                    ingredient.getDouble("grams")
                                )
                            )
                        }
                    }
                )
            )
        }
    }.sortedWith(dishComparator)

    private fun decodeIds(array: JSONArray): Set<Long> = buildSet {
        for (index in 0 until array.length()) add(array.getLong(index))
    }

    private fun mergeFoodChanges(overrides: List<Food>, deletedIds: Set<Long>): List<Food> {
        val overrideById = overrides.associateBy { it.id }
        return (baseFoods.asSequence()
            .filterNot { it.id in deletedIds }
            .map { overrideById[it.id] ?: it } +
            overrides.asSequence().filterNot { baseFoodsById.containsKey(it.id) })
            .distinctBy { it.id }
            .sortedWith(foodComparator)
            .toList()
    }

    private fun migrateLegacyFoods(decoded: List<Food>?, schemaVersion: Int): List<Food> {
        if (decoded == null) return baseFoods
        val legacyFoods = if (schemaVersion < 5) addDefaultLinks(decoded) else decoded
        val legacyById = legacyFoods.associateBy { it.id }
        val defaultById = DefaultFoodCatalog.items.associateBy { it.id }
        val deletedDefaultIds = defaultById.keys - legacyById.keys
        val overrides = legacyFoods.filter { food -> defaultById[food.id] != food }
        return mergeFoodChanges(overrides, deletedDefaultIds)
    }

    private fun addDefaultLinks(foods: List<Food>): List<Food> {
        val defaults = DefaultFoodCatalog.items.associateBy { it.id }
        return foods.map { food ->
            val default = defaults[food.id]
            if (food.links.isEmpty() && default?.name == food.name) food.copy(links = default.links) else food
        }
    }

    private fun JSONObject.putNullable(name: String, value: Any?) {
        if (value == null) put(name, JSONObject.NULL) else put(name, value)
    }

    private fun JSONObject.optionalDouble(name: String): Double? =
        if (isNull(name) || !has(name)) null else getDouble(name)

    private fun JSONObject.optionalLong(name: String): Long? =
        if (isNull(name) || !has(name)) null else getLong(name)

    private fun JSONObject.optionalString(name: String): String? =
        if (isNull(name) || !has(name)) null else getString(name)

    private fun <T> JSONObject.optionalEnum(name: String, parser: (String) -> T): T? =
        if (isNull(name) || !has(name)) null else parser(getString(name))

    companion object {
        private const val KEY_DATA = "app_data_v1"
        private val foodComparator = compareBy<Food> { it.category.ordinal }
            .thenBy { it.name.lowercase() }
        private val dishComparator = compareBy<Dish> { it.name.lowercase() }
        private val plannedMealComparator = compareBy<PlannedMeal> { it.type.ordinal }
            .thenBy { meal -> WeekDay.entries.indexOfFirst(meal.days::contains) }
    }
}
