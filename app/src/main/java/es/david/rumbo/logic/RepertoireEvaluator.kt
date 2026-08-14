package es.david.rumbo.logic

import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
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

data class RepertoireAssessment(
    val status: RepertoireStatus,
    val nutrition: Map<NutrientKind, NutrientCapacity>,
    val coverage: List<MealCoverage>,
    val fruitConcepts: Int,
    val vegetableConcepts: Int,
    val acceptableSolutions: Int,
    val limitingFactors: List<String>,
    val suggestions: List<FoodCategory>,
    val reactivationFoodIds: List<Long>,
    val metrics: RepertoireMetrics
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
 * It deliberately delegates construction, practical units, fixed slots and
 * dish derivation to [WeeklyMenuGenerator], preventing a second, contradictory
 * nutrition solver from developing beside the real one.
 */
object RepertoireEvaluator {
    private val seeds = listOf(11L, 97L, 313L, 997L)
    private val defaultShares = mapOf(
        MealType.BREAKFAST to .20,
        MealType.MORNING_SNACK to .10,
        MealType.LUNCH to .35,
        MealType.AFTERNOON_SNACK to .10,
        MealType.DINNER to .25
    )

    fun evaluate(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double> = defaultShares,
        thresholds: RepertoireThresholds = RepertoireThresholds()
    ): RepertoireAssessment {
        val activeRules = rules.filter {
            it.itemKind == PlannedItemKind.FOOD &&
                it.isActive && it.frequency != PlanningFrequency.NEVER && it.isValid() &&
                foodsById[it.itemId]?.hasComparableNutrition() == true
        }
        val activeFoods = activeRules.mapNotNull { foodsById[it.itemId] }.distinctBy { it.id }
        val inactiveFoods = rules.filter {
            it.itemKind == PlannedItemKind.FOOD && !it.isActive
        }.mapNotNull { foodsById[it.itemId] }.distinctBy { it.id }
        val coverage = MealType.entries.filter { (mealShares[it] ?: defaultShares.getValue(it)) > 0.0 }
            .map { type ->
                MealCoverage(type, activeRules.count { rule ->
                    type in rule.allowedMealTypes || rule.requiredSlots().any { it.mealType == type }
                })
            }
        val vegetableGroups = activeFoods.filter { it.category == FoodCategory.VEGETABLE }
            .map(::conceptKey).distinct().size
        val fruitGroups = activeFoods.filter { it.category == FoodCategory.FRUIT }
            .map(::conceptKey).distinct().size

        if (activeRules.isEmpty() || coverage.any { it.alternatives == 0 }) {
            val factors = buildList {
                if (activeRules.isEmpty()) add("No hay alimentos activos y correctamente programados.")
                coverage.filter { it.alternatives == 0 }.forEach {
                    add("No hay opciones para ${it.mealType.label.lowercase()}.")
                }
            }
            return emptyAssessment(
                recommendation, coverage, fruitGroups, vegetableGroups, activeFoods,
                factors, thresholds, inactiveFoods
            )
        }

        val attempts = seeds.mapNotNull { seed ->
            runCatching {
                WeeklyMenuGenerator.generate(
                    currentMeals = emptyList(), rules = activeRules, history = emptyList(),
                    foodsById = foodsById, dishesById = dishesById,
                    recommendation = recommendation, mealShares = mealShares, seed = seed
                )
            }.getOrNull()
        }
        if (attempts.isEmpty()) {
            return emptyAssessment(
                recommendation, coverage, fruitGroups, vegetableGroups, activeFoods,
                listOf("Las reglas obligatorias no permiten construir todas las comidas."),
                thresholds, inactiveFoods
            )
        }

        val ranked = attempts.map { generated ->
            val assessments = WeekDay.entries.map { day ->
                MealPlanEvaluator.assessDay(day, generated.meals, foodsById, dishesById, recommendation)
            }
            val evaluations = assessments.flatMap { it.evaluations }
            Candidate(
                assessments = assessments,
                worstPenalty = evaluations.maxOf { it.penalty },
                totalPenalty = evaluations.sumOf { it.penalty },
                fingerprint = generated.meals.flatMap { meal ->
                    meal.items.map { "f${it.foodId}" } + meal.dishes.map { "d${it.dishId}" }
                }.toSet()
            )
        }.sortedWith(compareBy<Candidate> { it.worstPenalty }.thenBy { it.totalPenalty })
        val best = ranked.first()
        val acceptable = ranked.filter { it.worstPenalty <= thresholds.acceptableWorstPenalty }
        val distinctAcceptable = acceptable.distinctBy { it.fingerprint }
        // Menu generation is heuristic: failure to find a good week is not proof
        // that the repertoire lacks a nutrient. Capacity is therefore evaluated
        // deterministically from the amounts and slots the rules actually permit.
        val nutrition = capacityNutrition(
            activeRules, foodsById, recommendation, mealShares
        )
        val limitedMeals = coverage.count { it.alternatives <= thresholds.limitedMealAlternatives }
        val profiles = activeFoods.map(::nutritionProfile).distinct().size
        val factors = limitingFactors(nutrition, coverage, fruitGroups, vegetableGroups, thresholds)
        val suggestions = suggestionsFor(nutrition, fruitGroups, vegetableGroups)
        val reactivations = matchingInactiveFoods(inactiveFoods, suggestions)
        val capacityPenalty = nutrition.maxOf { (kind, capacity) ->
            NutritionTolerancePolicy.evaluate(
                kind, capacity.bestAchievable, capacity.target
            ).penalty
        }
        val status = when {
            capacityPenalty > thresholds.acceptableWorstPenalty ->
                RepertoireStatus.INSUFFICIENT
            distinctAcceptable.size >= thresholds.robustSolutionCount && limitedMeals == 0 &&
                profiles >= thresholds.robustSolutionCount -> RepertoireStatus.ROBUST
            limitedMeals == 0 -> RepertoireStatus.SUFFICIENT
            else -> RepertoireStatus.LIMITED
        }
        return RepertoireAssessment(
            status, nutrition, coverage, fruitGroups, vegetableGroups,
            distinctAcceptable.size, factors, suggestions, reactivations,
            RepertoireMetrics(
                best.worstPenalty, best.totalPenalty, activeFoods.size, profiles,
                limitedMeals, ranked.size
            )
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

    /**
     * Computes whether every nutrient target lies inside the daily interval that
     * the configured rules permit. Optional foods have a zero lower bound;
     * «Siempre» and fixed slots contribute their real compulsory minimum.
     *
     * This is intentionally independent from the stochastic menu generator:
     * not finding a combination is a generator limitation, not evidence that
     * another food is required.
     */
    private fun capacityNutrition(
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): Map<NutrientKind, NutrientCapacity> {
        val targets = mapOf(
            NutrientKind.CALORIES to recommendation.calories.toDouble(),
            NutrientKind.PROTEIN to recommendation.proteinGrams.toDouble(),
            NutrientKind.CARBOHYDRATES to recommendation.carbohydrateGrams.toDouble(),
            NutrientKind.FAT to recommendation.fatGrams.toDouble()
        )
        fun Food.value(kind: NutrientKind): Double = when (kind) {
            NutrientKind.CALORIES -> calories ?: 0.0
            NutrientKind.PROTEIN -> proteinGrams ?: 0.0
            NutrientKind.CARBOHYDRATES -> carbohydrateGrams ?: 0.0
            NutrientKind.FAT -> fatGrams ?: 0.0
        }
        fun usable(rule: PlanningRule, day: WeekDay): Boolean =
            day in rule.allowedDays && rule.allowedMealTypes.any {
                (mealShares[it] ?: defaultShares.getValue(it)) > 0.0
            }

        return targets.mapValues { (kind, target) ->
            val dailyBest = WeekDay.entries.map { day ->
                var minimum = 0.0
                var maximum = 0.0
                rules.filter { usable(it, day) }.forEach { rule ->
                    val food = foodsById[rule.itemId] ?: return@forEach
                    val perGram = food.value(kind) / 100.0
                    val requiredCount = rule.requiredSlots().count { slot ->
                        slot.day == day &&
                            (mealShares[slot.mealType]
                                ?: defaultShares.getValue(slot.mealType)) > 0.0
                    }
                    if (requiredCount > 0) {
                        minimum += perGram * rule.preferredGrams *
                            rule.minimumFactor * requiredCount
                        maximum += perGram * rule.preferredGrams *
                            rule.maximumFactor * requiredCount
                    } else {
                        maximum += perGram * rule.preferredGrams * rule.maximumFactor
                    }
                }
                target.coerceIn(minimum, maximum)
            }
            val worst = dailyBest.maxByOrNull { achieved ->
                NutritionTolerancePolicy.evaluate(kind, achieved, target).penalty
            } ?: 0.0
            val evaluation = NutritionTolerancePolicy.evaluate(kind, worst, target)
            NutrientCapacity(target, worst, evaluation.difference, evaluation.fit)
        }
    }

    private fun emptyAssessment(
        recommendation: Recommendation,
        coverage: List<MealCoverage>,
        fruit: Int,
        vegetables: Int,
        foods: List<Food>,
        factors: List<String>,
        thresholds: RepertoireThresholds,
        inactiveFoods: List<Food>
    ): RepertoireAssessment {
        val target = MealPlanEvaluator.dailyTarget(recommendation)
        val nutrition = mapOf(
            NutrientKind.CALORIES to NutrientCapacity(target.calories, 0.0, -target.calories, TargetFit.OUTSIDE),
            NutrientKind.PROTEIN to NutrientCapacity(target.proteinGrams, 0.0, -target.proteinGrams, TargetFit.OUTSIDE),
            NutrientKind.CARBOHYDRATES to NutrientCapacity(target.carbohydrateGrams, 0.0, -target.carbohydrateGrams, TargetFit.OUTSIDE),
            NutrientKind.FAT to NutrientCapacity(target.fatGrams, 0.0, -target.fatGrams, TargetFit.OUTSIDE)
        )
        val suggestions = suggestionsFor(nutrition, fruit, vegetables)
        return RepertoireAssessment(
            RepertoireStatus.INSUFFICIENT, nutrition, coverage, fruit, vegetables, 0,
            factors, suggestions, matchingInactiveFoods(inactiveFoods, suggestions),
            RepertoireMetrics(Double.POSITIVE_INFINITY, Double.POSITIVE_INFINITY, foods.size,
                foods.map(::nutritionProfile).distinct().size,
                coverage.count { it.alternatives <= thresholds.limitedMealAlternatives }, 0)
        )
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
