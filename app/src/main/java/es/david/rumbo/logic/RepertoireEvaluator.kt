package es.david.rumbo.logic

import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.MealDistributionPolicy
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import kotlin.math.roundToInt

enum class RepertoireStatus { INSUFFICIENT, LIMITED, SUFFICIENT, ROBUST }

data class RepertoireThresholds(
    val acceptableWorstPenalty: Double = 1.0,
    val goodWorstPenalty: Double = 0.25,
    val robustSolutionCount: Int = 3,
    val limitedMealAlternatives: Int = 1,
    val adequateFruitConcepts: Int = 2,
    val adequateVegetableConcepts: Int = 3
)

data class NutrientCapacity(
    val target: Double,
    val bestAchievable: Double,
    val deviation: Double,
    val fit: TargetFit
)

data class MealCoverage(val mealType: MealType, val alternatives: Int)

enum class CulinaryNeedKind { COMPANION_BASE, STARCH_BASE, PRIMARY_PROTEIN, FAT_COMPLEMENT }

data class CulinaryNeed(
    val kind: CulinaryNeedKind,
    val mealType: MealType,
    val acceptedRoles: Set<CulinaryRole>,
    val message: String,
    val sourceFoodId: Long? = null,
    val sourceFoodName: String? = null,
    val sourceRole: CulinaryRole? = null
)

data class RepertoireAssessment(
    val status: RepertoireStatus,
    val nutrition: Map<NutrientKind, NutrientCapacity>,
    val coverage: List<MealCoverage>,
    /**
     * Compatibility values for the legacy progress card. Since COMPLETE no
     * longer requires N distinct concepts, non-structural evaluations expose at
     * least the old UI threshold so those obsolete gates cannot become hidden
     * certification rules. Use raw*Concepts for the actual repertoire counts.
     */
    val fruitConcepts: Int,
    val vegetableConcepts: Int,
    val acceptableSolutions: Int,
    val limitingFactors: List<String>,
    val suggestions: List<FoodCategory>,
    val reactivationFoodIds: List<Long>,
    val metrics: RepertoireMetrics,
    val culinaryNeeds: List<CulinaryNeed> = emptyList(),
    val searchStatus: ConstraintSearchStatus = ConstraintSearchStatus.SEARCH_INCONCLUSIVE,
    val witness: MenuWitness? = null,
    val constraintViolations: List<ConstraintViolation> = emptyList(),
    val rawFruitConcepts: Int = fruitConcepts,
    val rawVegetableConcepts: Int = vegetableConcepts
)

data class RepertoireMetrics(
    val worstPenalty: Double,
    val totalPenalty: Double,
    val availableFoods: Int,
    val distinctNutritionProfiles: Int,
    val mealsWithLimitedCoverage: Int,
    val evaluatedSolutions: Int
)

/** Evaluates exactly the repertoire that the menu generator can use.
 *
 * The compatibility [RepertoireStatus] remains for the current UI. The
 * independent [ConstraintSearchStatus] is the authoritative statement about
 * feasibility: bounded heuristic failure is SEARCH_INCONCLUSIVE, never a proof
 * of insufficiency.
 */
object RepertoireEvaluator {
    private val seeds = listOf(11L, 37L, 89L)
    private val defaultShares = MealDistributionPolicy.defaults

    fun evaluate(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double> = defaultShares,
        thresholds: RepertoireThresholds = RepertoireThresholds()
    ): RepertoireAssessment {
        val constraints = MenuConstraintModel.fromLegacyData(rules, foodsById, mealShares)
        val activeRules = constraints.activeRules
        val activeFoods = activeRules.mapNotNull { foodsById[it.itemId] }.distinctBy { it.id }
        val dependencyNeeds = dependencyNeeds(activeRules, foodsById)
        val inactiveFoods = rules.filter {
            it.itemKind == PlannedItemKind.FOOD && !it.isActive
        }.mapNotNull { foodsById[it.itemId] }.distinctBy { it.id }
        val coverage = constraints.activeMealTypes.map { type ->
            MealCoverage(type, activeRules.count { rule ->
                type in rule.allowedMealTypes || rule.requiredSlots().any { it.mealType == type }
            })
        }
        val vegetableGroups = activeFoods.filter { it.category == FoodCategory.VEGETABLE }
            .map(::conceptKey).distinct().size
        val fruitGroups = activeFoods.filter { it.category == FoodCategory.FRUIT }
            .map(::conceptKey).distinct().size

        if (constraints.structuralViolations.isNotEmpty()) {
            return emptyAssessment(
                recommendation = recommendation,
                coverage = coverage,
                fruit = fruitGroups,
                vegetables = vegetableGroups,
                foods = activeFoods,
                factors = constraints.structuralViolations.map { it.message },
                thresholds = thresholds,
                inactiveFoods = inactiveFoods,
                culinaryNeeds = dependencyNeeds,
                searchStatus = ConstraintSearchStatus.INSUFFICIENT,
                constraintViolations = constraints.structuralViolations
            )
        }

        // COMPLETE is based on fruit/vegetable presence in distinct meals, not
        // on a count of different concepts. The old card still reads these two
        // fields, so neutralise that compatibility-only gate once structural
        // validity is established. Actual counts remain in raw*Concepts.
        val compatibilityFruitGroups = maxOf(fruitGroups, thresholds.adequateFruitConcepts)
        val compatibilityVegetableGroups = maxOf(
            vegetableGroups, thresholds.adequateVegetableConcepts
        )

        val attempts = seeds.mapNotNull { seed ->
            runCatching {
                seed to WeeklyMenuGenerator.generate(
                    constraints = constraints,
                    currentMeals = emptyList(),
                    history = emptyList(),
                    foodsById = foodsById,
                    dishesById = dishesById,
                    recommendation = recommendation,
                    seed = seed,
                    days = setOf(WeekDay.MONDAY)
                )
            }.getOrNull()
        }
        if (attempts.isEmpty()) {
            return emptyAssessment(
                recommendation = recommendation,
                coverage = coverage,
                fruit = compatibilityFruitGroups,
                vegetables = compatibilityVegetableGroups,
                rawFruit = fruitGroups,
                rawVegetables = vegetableGroups,
                foods = activeFoods,
                factors = listOf(
                    "La búsqueda no encontró un menú testigo; no se ha demostrado que el repertorio sea insuficiente."
                ),
                thresholds = thresholds,
                inactiveFoods = inactiveFoods,
                culinaryNeeds = dependencyNeeds,
                searchStatus = ConstraintSearchStatus.SEARCH_INCONCLUSIVE
            )
        }

        val ranked = attempts.map { (seed, generated) ->
            val assessments = listOf(
                MealPlanEvaluator.assessDay(
                    WeekDay.MONDAY, generated.meals, foodsById, dishesById, recommendation
                )
            )
            val evaluations = assessments.flatMap { it.evaluations }
            Candidate(
                seed = seed,
                meals = generated.meals,
                assessments = assessments,
                worstPenalty = evaluations.maxOf { it.penalty },
                totalPenalty = evaluations.sumOf { it.penalty },
                fingerprint = generated.meals.flatMap { meal ->
                    meal.items.map { "f${it.foodId}" } + meal.dishes.map { "d${it.dishId}" }
                }.toSet()
            )
        }.sortedWith(compareBy<Candidate> { it.worstPenalty }.thenBy { it.totalPenalty })
        val best = ranked.first()
        val activeMealTypes = coverage.mapTo(mutableSetOf()) { it.mealType }
        val acceptable = ranked.filter {
            WeeklyMenuAcceptancePolicy.isDayAcceptable(
                it.assessments.single(), activeMealTypes
            )
        }
        val distinctAcceptable = acceptable.distinctBy { it.fingerprint }
        val average = averageNutrition(best.assessments)
        val target = MealPlanEvaluator.dailyTarget(recommendation)
        val nutrition = listOf(
            NutrientKind.CALORIES to (average.calories to target.calories),
            NutrientKind.PROTEIN to (average.proteinGrams to target.proteinGrams),
            NutrientKind.CARBOHYDRATES to (average.carbohydrateGrams to target.carbohydrateGrams),
            NutrientKind.FAT to (average.fatGrams to target.fatGrams)
        ).associate { (kind, values) ->
            val evaluation = NutritionTolerancePolicy.evaluate(kind, values.first, values.second)
            kind to NutrientCapacity(values.second, values.first, evaluation.difference, evaluation.fit)
        }
        val limitedMeals = coverage.count { it.alternatives <= thresholds.limitedMealAlternatives }
        val profiles = activeFoods.map(::nutritionProfile).distinct().size
        val factors = limitingFactors(nutrition, coverage, fruitGroups, vegetableGroups, thresholds)
        val suggestions = suggestionsFor(nutrition, fruitGroups, vegetableGroups)
        val culinaryNeeds = dependencyNeeds + macroCulinaryNeeds(activeRules, foodsById, nutrition)
        val reactivations = matchingInactiveFoods(inactiveFoods, suggestions)
        val status = when {
            acceptable.isEmpty() -> RepertoireStatus.INSUFFICIENT
            distinctAcceptable.size >= thresholds.robustSolutionCount && limitedMeals == 0 &&
                profiles >= thresholds.robustSolutionCount -> RepertoireStatus.ROBUST
            else -> RepertoireStatus.SUFFICIENT
        }
        val witnessCandidate = acceptable.firstOrNull()
        return RepertoireAssessment(
            status = status,
            nutrition = nutrition,
            coverage = coverage,
            fruitConcepts = compatibilityFruitGroups,
            vegetableConcepts = compatibilityVegetableGroups,
            acceptableSolutions = distinctAcceptable.size,
            limitingFactors = factors,
            suggestions = suggestions,
            reactivationFoodIds = reactivations,
            metrics = RepertoireMetrics(
                best.worstPenalty, best.totalPenalty, activeFoods.size, profiles,
                limitedMeals, ranked.size
            ),
            culinaryNeeds = culinaryNeeds.distinctBy { it.kind to it.mealType },
            searchStatus = if (witnessCandidate == null) {
                ConstraintSearchStatus.SEARCH_INCONCLUSIVE
            } else {
                ConstraintSearchStatus.FEASIBLE
            },
            witness = witnessCandidate?.let { MenuWitness(it.seed, it.meals) },
            rawFruitConcepts = fruitGroups,
            rawVegetableConcepts = vegetableGroups
        )
    }

    fun evaluateCandidates(
        rules: List<PlanningRule>,
        candidates: List<Food>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double> = defaultShares,
        thresholds: RepertoireThresholds = RepertoireThresholds()
    ): Map<Long, RepertoireAssessment> = candidates.associate { candidate ->
        val hypotheticalRule = PlanningRule(
            itemKind = PlannedItemKind.FOOD,
            itemId = candidate.id,
            allowedMealTypes = MealType.entries.toSet(),
            frequency = PlanningFrequency.FREQUENT,
            preferredGrams = (candidate.unitAmount ?: 100.0).coerceIn(30.0, 250.0)
        )
        candidate.id to evaluate(
            rules = rules + hypotheticalRule,
            foodsById = foodsById,
            dishesById = dishesById,
            recommendation = recommendation,
            mealShares = mealShares,
            thresholds = thresholds
        )
    }

    private data class Candidate(
        val seed: Long,
        val meals: List<PlannedMeal>,
        val assessments: List<PlanNutritionAssessment>,
        val worstPenalty: Double,
        val totalPenalty: Double,
        val fingerprint: Set<String>
    )

    private fun averageNutrition(values: List<PlanNutritionAssessment>) =
        es.david.rumbo.model.NutritionTotals(
            calories = values.map { it.actual.calories }.average(),
            proteinGrams = values.map { it.actual.proteinGrams }.average(),
            carbohydrateGrams = values.map { it.actual.carbohydrateGrams }.average(),
            fatGrams = values.map { it.actual.fatGrams }.average(),
            fiberGrams = values.map { it.actual.fiberGrams }.average(),
            isComplete = values.all { it.actual.isComplete }
        )

    private fun emptyAssessment(
        recommendation: Recommendation,
        coverage: List<MealCoverage>,
        fruit: Int,
        vegetables: Int,
        foods: List<Food>,
        factors: List<String>,
        thresholds: RepertoireThresholds,
        inactiveFoods: List<Food>,
        culinaryNeeds: List<CulinaryNeed> = emptyList(),
        searchStatus: ConstraintSearchStatus = ConstraintSearchStatus.INSUFFICIENT,
        constraintViolations: List<ConstraintViolation> = emptyList(),
        rawFruit: Int = fruit,
        rawVegetables: Int = vegetables
    ): RepertoireAssessment {
        val target = MealPlanEvaluator.dailyTarget(recommendation)
        val nutrition = mapOf(
            NutrientKind.CALORIES to NutrientCapacity(target.calories, 0.0, -target.calories, TargetFit.OUTSIDE),
            NutrientKind.PROTEIN to NutrientCapacity(target.proteinGrams, 0.0, -target.proteinGrams, TargetFit.OUTSIDE),
            NutrientKind.CARBOHYDRATES to NutrientCapacity(target.carbohydrateGrams, 0.0, -target.carbohydrateGrams, TargetFit.OUTSIDE),
            NutrientKind.FAT to NutrientCapacity(target.fatGrams, 0.0, -target.fatGrams, TargetFit.OUTSIDE)
        )
        val suggestions = suggestionsFor(nutrition, rawFruit, rawVegetables)
        return RepertoireAssessment(
            status = RepertoireStatus.INSUFFICIENT,
            nutrition = nutrition,
            coverage = coverage,
            fruitConcepts = fruit,
            vegetableConcepts = vegetables,
            acceptableSolutions = 0,
            limitingFactors = factors,
            suggestions = suggestions,
            reactivationFoodIds = matchingInactiveFoods(inactiveFoods, suggestions),
            metrics = RepertoireMetrics(
                Double.POSITIVE_INFINITY, Double.POSITIVE_INFINITY, foods.size,
                foods.map(::nutritionProfile).distinct().size,
                coverage.count { it.alternatives <= thresholds.limitedMealAlternatives }, 0
            ),
            culinaryNeeds = culinaryNeeds,
            searchStatus = searchStatus,
            witness = null,
            constraintViolations = constraintViolations,
            rawFruitConcepts = rawFruit,
            rawVegetableConcepts = rawVegetables
        )
    }

    /**
     * Reports a hard companion dependency only when it is unavoidable for one
     * concrete food in that meal. A multi-role food must not trigger a request
     * just because one of its possible roles has a dependency if another role
     * can be used without it.
     */
    private fun dependencyNeeds(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>
    ): List<CulinaryNeed> = MealType.entries.mapNotNull { mealType ->
        val entries = rules.filter {
            mealType in it.allowedMealTypes || it.requiredSlots().any { slot -> slot.mealType == mealType }
        }.mapNotNull { rule ->
            val food = foodsById[rule.itemId] ?: return@mapNotNull null
            val roles = CulinaryPolicy.roles(food)
            if (roles.isEmpty()) null else Triple(rule, food, roles)
        }
        val availableRoles = entries.flatMapTo(linkedSetOf()) { it.third }

        entries.asSequence().mapNotNull { (_, food, roles) ->
            val missingByRole = roles.associateWith { role ->
                CulinaryPolicy.policy(role).requiredRoles - availableRoles
            }
            // At least one role can be performed without a missing hard
            // companion, so no dependency is proven for this food.
            if (missingByRole.values.any { it.isEmpty() }) return@mapNotNull null

            val cause = missingByRole.entries.minWithOrNull(
                compareBy<Map.Entry<CulinaryRole, Set<CulinaryRole>>> { it.value.size }
                    .thenBy { it.key.ordinal }
            ) ?: return@mapNotNull null
            val missing = cause.value
            if (missing.isEmpty()) return@mapNotNull null
            val role = cause.key
            val missingLabel = missing.joinToString(" o ") { it.label.lowercase() }
            CulinaryNeed(
                kind = CulinaryNeedKind.COMPANION_BASE,
                mealType = mealType,
                acceptedRoles = missing,
                message = "${food.name} está disponible para ${mealType.label.lowercase()} como " +
                    "${role.label.lowercase()}, pero necesita $missingLabel para formar una combinación válida.",
                sourceFoodId = food.id,
                sourceFoodName = food.name,
                sourceRole = role
            )
        }.firstOrNull()
    }

    private fun macroCulinaryNeeds(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        nutrition: Map<NutrientKind, NutrientCapacity>
    ): List<CulinaryNeed> = buildList {
        fun lacksRole(meal: MealType, role: CulinaryRole) = rules.none {
            meal in it.allowedMealTypes && role in
                foodsById[it.itemId]?.let(CulinaryPolicy::roles).orEmpty()
        }
        val isLow: (NutrientKind) -> Boolean = { kind ->
            nutrition[kind]?.let { it.deviation < 0.0 && it.fit != TargetFit.ON_TARGET } == true
        }
        if (isLow(NutrientKind.CARBOHYDRATES)) {
            listOf(MealType.LUNCH, MealType.DINNER).firstOrNull {
                lacksRole(it, CulinaryRole.PLATE_BASE)
            }?.let { meal ->
                add(CulinaryNeed(
                    CulinaryNeedKind.STARCH_BASE, meal,
                    setOf(CulinaryRole.PLATE_BASE),
                    "Añade una base de hidratos para ${meal.label.lowercase()}."
                ))
            }
        }
        if (isLow(NutrientKind.PROTEIN)) {
            listOf(MealType.LUNCH, MealType.DINNER).firstOrNull {
                lacksRole(it, CulinaryRole.PLATE_CENTER)
            }?.let { meal ->
                add(CulinaryNeed(
                    CulinaryNeedKind.PRIMARY_PROTEIN, meal,
                    setOf(CulinaryRole.PLATE_CENTER),
                    "Añade un alimento principal con proteína para ${meal.label.lowercase()}."
                ))
            }
        }
        // Do not derive a missing fat food from a low-fat result. Unlike a
        // mandatory companion, that result only proves that this bounded
        // search did not find suitable foods and quantities. The initial
        // repertoire milestones already verify the presence of concentrated
        // and complementary fat sources.
    }

    private fun limitingFactors(
        nutrition: Map<NutrientKind, NutrientCapacity>,
        coverage: List<MealCoverage>,
        fruit: Int,
        vegetables: Int,
        thresholds: RepertoireThresholds
    ) = buildList {
        nutrition.filterValues { it.fit == TargetFit.OUTSIDE }.forEach { (kind, capacity) ->
            val direction = if (capacity.deviation < 0) "alcanzar" else "no superar"
            add("Cuesta $direction el objetivo de ${capacity.target.roundToInt()} de ${kind.label()}.")
        }
        coverage.filter { it.alternatives <= thresholds.limitedMealAlternatives }.forEach {
            add("${it.mealType.label} tiene ${it.alternatives} alternativa(s) programada(s).")
        }
        if (fruit == 0) add("No hay fruta activa y programada.")
        if (vegetables == 0) add("No hay verdura activa y programada.")
    }

    private fun suggestionsFor(
        nutrition: Map<NutrientKind, NutrientCapacity>, fruit: Int, vegetables: Int
    ) = buildSet {
        nutrition[NutrientKind.PROTEIN]?.takeIf { it.deviation < 0 && it.fit == TargetFit.OUTSIDE }
            ?.let { add(FoodCategory.PROTEIN) }
        nutrition[NutrientKind.CARBOHYDRATES]?.takeIf { it.deviation < 0 && it.fit == TargetFit.OUTSIDE }
            ?.let { add(FoodCategory.CARBOHYDRATE) }
        nutrition[NutrientKind.FAT]?.takeIf { it.deviation < 0 && it.fit == TargetFit.OUTSIDE }
            ?.let { add(FoodCategory.FAT) }
        if (fruit == 0) add(FoodCategory.FRUIT)
        if (vegetables == 0) add(FoodCategory.VEGETABLE)
    }.toList()

    private fun matchingInactiveFoods(
        inactiveFoods: List<Food>, suggestions: List<FoodCategory>
    ): List<Long> = inactiveFoods.filter { it.category in suggestions }.map { it.id }

    private fun NutrientKind.label() = when (this) {
        NutrientKind.CALORIES -> "calorías"
        NutrientKind.PROTEIN -> "proteína"
        NutrientKind.CARBOHYDRATES -> "carbohidratos"
        NutrientKind.FAT -> "grasas"
    }

    private fun conceptKey(food: Food) = (food.family ?: food.subcategory ?: food.name)
        .lowercase().replace(Regex("[^a-záéíóúüñ]+"), " ").trim()

    private fun nutritionProfile(food: Food): String {
        fun bucket(value: Double?) = ((value ?: 0.0) / 5.0).roundToInt()
        return listOf(bucket(food.proteinGrams), bucket(food.carbohydrateGrams), bucket(food.fatGrams)).joinToString(":")
    }
}
