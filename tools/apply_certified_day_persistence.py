from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one occurrence, got {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))

# Models
p='app/src/main/java/es/david/rumbo/model/Models.kt'
replace_once(p,
'''data class ProfileData(\n    val profile: UserProfile,''',
'''enum class CertifiedDayLevel {\n    VIABLE,\n    COMPLETE,\n    CULINARILY_SATISFACTORY\n}\n\ndata class CertifiedDayWitness(\n    val level: CertifiedDayLevel,\n    val seed: Long,\n    val day: WeekDay,\n    val meals: List<PlannedMeal>,\n    val fingerprint: Int = meals.hashCode()\n) {\n    fun isStructurallyValid(): Boolean =\n        meals.isNotEmpty() &&\n            meals.all { meal -> meal.isValid() && meal.days == setOf(day) } &&\n            meals.map { it.type }.distinct().size == meals.size\n}\n\ndata class ProfileData(\n    val profile: UserProfile,''')
replace_once(p,
'''    val nutritionToleranceSettings: NutritionToleranceSettings = NutritionToleranceSettings(),\n    val mealShares: Map<MealType, Double>? = null\n)''',
'''    val nutritionToleranceSettings: NutritionToleranceSettings = NutritionToleranceSettings(),\n    val mealShares: Map<MealType, Double>? = null,\n    val certifiedDayWitnesses: List<CertifiedDayWitness> = emptyList()\n)''')

# New validator/converter in logic
Path('app/src/main/java/es/david/rumbo/logic/CertifiedDayWitnessEvaluator.kt').write_text(r'''package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Dish
import es.david.rumbo.model.Food
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation

object CertifiedDayWitnessEvaluator {
    fun fromMenuWitness(
        witness: MenuWitness,
        level: CertifiedDayLevel = CertifiedDayLevel.VIABLE
    ): CertifiedDayWitness? {
        val days = witness.meals.flatMap { it.days }.distinct()
        if (days.size != 1) return null
        return CertifiedDayWitness(
            level = level,
            seed = witness.seed,
            day = days.single(),
            meals = witness.meals,
            fingerprint = witness.fingerprint
        ).takeIf { it.isStructurallyValid() }
    }

    fun isViable(
        witness: CertifiedDayWitness,
        rules: List<PlanningRule>,
        foodsById: Map<Long, Food>,
        dishesById: Map<Long, Dish>,
        recommendation: Recommendation,
        mealShares: Map<MealType, Double>
    ): Boolean {
        if (witness.level != CertifiedDayLevel.VIABLE || !witness.isStructurallyValid()) return false
        val constraints = MenuConstraintModel.fromLegacyData(rules, foodsById, mealShares)
        if (constraints.structuralViolations.isNotEmpty()) return false
        val activeRules = constraints.activeRules
        val activeByFood = activeRules.groupBy { it.itemId }
        val activeMealTypes = constraints.activeMealTypes
        val meals = witness.meals

        if (meals.map { it.type }.toSet() != activeMealTypes) return false
        if (meals.any { it.type !in activeMealTypes }) return false

        meals.forEach { meal ->
            meal.items.forEach { item ->
                val compatible = activeByFood[item.foodId].orEmpty().any { rule ->
                    meal.type in rule.allowedMealTypes && rule.frequency != PlanningFrequency.NEVER
                }
                if (!compatible) return false
            }
            meal.dishes.forEach { plannedDish ->
                val dish = dishesById[plannedDish.dishId] ?: return false
                if (meal.type !in dish.allowedMealTypes) return false
                if (dish.ingredients.any { ingredient ->
                        activeByFood[ingredient.foodId].orEmpty().none { rule ->
                            meal.type in rule.allowedMealTypes && rule.frequency != PlanningFrequency.NEVER
                        }
                    }
                ) return false
            }
        }

        activeRules.filter { it.frequency == PlanningFrequency.ALWAYS }.forEach { rule ->
            rule.allowedMealTypes.intersect(activeMealTypes).forEach { mealType ->
                val meal = meals.singleOrNull { it.type == mealType } ?: return false
                val direct = meal.items.any { it.foodId == rule.itemId }
                val inDish = meal.dishes.any { plannedDish ->
                    dishesById[plannedDish.dishId]?.ingredients?.any { it.foodId == rule.itemId } == true
                }
                if (!direct && !inDish) return false
            }
        }

        if (!WeeklyMenuGenerator.isCulinarilyValid(meals, foodsById, dishesById)) return false
        val assessment = MealPlanEvaluator.assessDay(
            witness.day, meals, foodsById, dishesById, recommendation
        )
        return WeeklyMenuAcceptancePolicy.isDayAcceptable(assessment, activeMealTypes)
    }
}
''')

# AppRepository imports and persistence
p='app/src/main/java/es/david/rumbo/data/AppRepository.kt'
replace_once(p,
'''import es.david.rumbo.model.AppData\nimport es.david.rumbo.model.DietCompliance''',
'''import es.david.rumbo.model.AppData\nimport es.david.rumbo.model.CertifiedDayLevel\nimport es.david.rumbo.model.CertifiedDayWitness\nimport es.david.rumbo.model.DietCompliance''')
# Preserve witnesses in both explicit ProfileData constructors.
old='''            nutritionToleranceSettings = existing?.nutritionToleranceSettings\n                ?: NutritionToleranceSettings(),\n            mealShares = existing?.mealShares\n        )'''
new='''            nutritionToleranceSettings = existing?.nutritionToleranceSettings\n                ?: NutritionToleranceSettings(),\n            mealShares = existing?.mealShares,\n            certifiedDayWitnesses = existing?.certifiedDayWitnesses.orEmpty()\n        )'''
text=Path(p).read_text()
if text.count(old) != 2:
    raise SystemExit(f'expected two ProfileData constructor tails, got {text.count(old)}')
Path(p).write_text(text.replace(old,new))
# Add save/clear API after saveMealShares.
replace_once(p,
'''    fun saveProfileWithBaseline(profile: UserProfile, baseline: Measurement): AppData {''',
'''    fun saveCertifiedDayWitness(witness: CertifiedDayWitness): AppData {\n        require(witness.isStructurallyValid()) { "El día testigo no es válido" }\n        val current = load()\n        val active = current.activeProfileData ?: return current\n        val updated = active.certifiedDayWitnesses\n            .filterNot { it.level == witness.level } + witness\n        return updateActive(current, active.copy(certifiedDayWitnesses = updated))\n    }\n\n    fun clearCertifiedDayWitness(level: CertifiedDayLevel): AppData {\n        val current = load()\n        val active = current.activeProfileData ?: return current\n        return updateActive(\n            current,\n            active.copy(\n                certifiedDayWitnesses = active.certifiedDayWitnesses.filterNot { it.level == level }\n            )\n        )\n    }\n\n    fun saveProfileWithBaseline(profile: UserProfile, baseline: Measurement): AppData {''')
replace_once(p, 'put("schemaVersion", 23)', 'put("schemaVersion", 24)')
replace_once(p,
'''                    put("menuHistory", encodeMenuHistory(profileData.menuHistory))''',
'''                    put("menuHistory", encodeMenuHistory(profileData.menuHistory))\n                    put(\n                        "certifiedDayWitnesses",\n                        encodeCertifiedDayWitnesses(profileData.certifiedDayWitnesses)\n                    )''')
# Encoding helper before menu history.
replace_once(p,
'''    private fun encodeMenuHistory(history: List<MenuHistoryEntry>): JSONArray = JSONArray().apply {''',
'''    private fun encodeCertifiedDayWitnesses(\n        witnesses: List<CertifiedDayWitness>\n    ): JSONArray = JSONArray().apply {\n        witnesses.forEach { witness ->\n            put(JSONObject().apply {\n                put("level", witness.level.name)\n                put("seed", witness.seed)\n                put("day", witness.day.name)\n                put("fingerprint", witness.fingerprint)\n                put("meals", encodePlannedMeals(witness.meals))\n            })\n        }\n    }\n\n    private fun encodeMenuHistory(history: List<MenuHistoryEntry>): JSONArray = JSONArray().apply {''')
# Decode field in ProfileData.
replace_once(p,
'''                            menuHistory = decodeMenuHistory(item.optJSONArray("menuHistory") ?: JSONArray()),\n                            culinaryPolicyOverrides = decodeCulinaryPolicyOverrides(''',
'''                            menuHistory = decodeMenuHistory(item.optJSONArray("menuHistory") ?: JSONArray()),\n                            certifiedDayWitnesses = decodeCertifiedDayWitnesses(\n                                item.optJSONArray("certifiedDayWitnesses") ?: JSONArray(),\n                                dishesById,\n                                schemaVersion\n                            ),\n                            culinaryPolicyOverrides = decodeCulinaryPolicyOverrides(''')
# Decode helper before decodeMenuHistory.
needle='''    private fun decodeMenuHistory(array: JSONArray): List<MenuHistoryEntry> = buildList {'''
helper='''    private fun decodeCertifiedDayWitnesses(\n        array: JSONArray,\n        dishesById: Map<Long, Dish>,\n        schemaVersion: Int\n    ): List<CertifiedDayWitness> = buildList {\n        for (index in 0 until array.length()) {\n            val item = array.optJSONObject(index) ?: continue\n            val level = runCatching {\n                CertifiedDayLevel.valueOf(item.getString("level"))\n            }.getOrNull() ?: continue\n            val day = runCatching { WeekDay.valueOf(item.getString("day")) }.getOrNull() ?: continue\n            val meals = decodePlannedMeals(\n                item.optJSONArray("meals") ?: JSONArray(), dishesById, schemaVersion\n            )\n            val witness = CertifiedDayWitness(\n                level = level,\n                seed = item.optLong("seed", 11L),\n                day = day,\n                meals = meals,\n                fingerprint = item.optInt("fingerprint", meals.hashCode())\n            )\n            if (witness.isStructurallyValid()) add(witness)\n        }\n    }\n\n'''+needle
replace_once(p, needle, helper)

# Validate witness references in validate(data).
replace_once(p,
'''            require(profileData.repertoireFoodIds.all { it in foodIds }) {\n                "Hay alimentos inexistentes en el repertorio"\n            }''',
'''            require(profileData.repertoireFoodIds.all { it in foodIds }) {\n                "Hay alimentos inexistentes en el repertorio"\n            }\n            require(profileData.certifiedDayWitnesses.all { it.isStructurallyValid() }) {\n                "Hay días testigo no válidos"\n            }\n            require(profileData.certifiedDayWitnesses.flatMap { it.meals }.flatMap { it.items }\n                .all { it.foodId in foodIds }) {\n                "Hay días testigo con alimentos inexistentes"\n            }\n            require(profileData.certifiedDayWitnesses.flatMap { it.meals }.flatMap { it.dishes }\n                .all { it.dishId in dishIds }) {\n                "Hay días testigo con platos inexistentes"\n            }''')

# UI imports
p='app/src/main/java/es/david/rumbo/ui/App.kt'
replace_once(p,
'''import es.david.rumbo.logic.CulinaryRolePolicy\nimport es.david.rumbo.model.ActivityLevel''',
'''import es.david.rumbo.logic.CulinaryRolePolicy\nimport es.david.rumbo.logic.CertifiedDayWitnessEvaluator\nimport es.david.rumbo.model.ActivityLevel\nimport es.david.rumbo.model.CertifiedDayLevel\nimport es.david.rumbo.model.CertifiedDayWitness''')
# HomeScreen call callbacks.
replace_once(p,
'''                    onOpenProgressSearch = { nutritionalRole, culinaryRole, mealType ->''',
'''                    onSaveCertifiedDayWitness = {\n                        data = repository.saveCertifiedDayWitness(it)\n                    },\n                    onClearCertifiedDayWitness = {\n                        data = repository.clearCertifiedDayWitness(it)\n                    },\n                    onOpenProgressSearch = { nutritionalRole, culinaryRole, mealType ->''')
# HomeScreen signature.
replace_once(p,
'''    onOpenFoods: () -> Unit,\n    onOpenProgressSearch: (String?, String?, MealType?) -> Unit,''',
'''    onOpenFoods: () -> Unit,\n    onSaveCertifiedDayWitness: (CertifiedDayWitness) -> Unit,\n    onClearCertifiedDayWitness: (CertifiedDayLevel) -> Unit,\n    onOpenProgressSearch: (String?, String?, MealType?) -> Unit,''')
# Insert saved witness validation after repertoire assessment.
replace_once(p,
'''    val menuReady = currentMenuAcceptable ||\n        repertoireAssessment?.status == RepertoireStatus.SUFFICIENT ||''',
'''    val savedViableWitness = data.activeProfileData?.certifiedDayWitnesses\n        ?.firstOrNull { it.level == CertifiedDayLevel.VIABLE }\n    val savedViableWitnessValid = remember(\n        savedViableWitness,\n        data.activeProfileData?.planningRules,\n        foodsById,\n        dishesById,\n        recommendation,\n        mealShares,\n        data.activeProfileData?.culinaryPolicyOverrides,\n        data.activeProfileData?.nutritionToleranceSettings\n    ) {\n        recommendation != null && savedViableWitness != null &&\n            CertifiedDayWitnessEvaluator.isViable(\n                witness = savedViableWitness,\n                rules = data.activeProfileData?.planningRules.orEmpty(),\n                foodsById = foodsById,\n                dishesById = dishesById,\n                recommendation = recommendation,\n                mealShares = mealShares\n            )\n    }\n    val freshViableWitness = remember(repertoireAssessment) {\n        repertoireAssessment?.witness?.let(CertifiedDayWitnessEvaluator::fromMenuWitness)\n    }\n    LaunchedEffect(\n        savedViableWitness, savedViableWitnessValid, freshViableWitness,\n        repertoireAssessment?.searchStatus\n    ) {\n        when {\n            savedViableWitnessValid -> Unit\n            freshViableWitness != null &&\n                repertoireAssessment?.searchStatus == ConstraintSearchStatus.FEASIBLE ->\n                onSaveCertifiedDayWitness(freshViableWitness)\n            savedViableWitness != null -> onClearCertifiedDayWitness(CertifiedDayLevel.VIABLE)\n        }\n    }\n    val hasCertifiedViableDay = savedViableWitnessValid ||\n        (freshViableWitness != null && repertoireAssessment?.searchStatus == ConstraintSearchStatus.FEASIBLE)\n\n    val menuReady = currentMenuAcceptable || hasCertifiedViableDay ||\n        repertoireAssessment?.status == RepertoireStatus.SUFFICIENT ||''')
# Progress card call
replace_once(p,
'''                RepertoireProgressCard(\n                    assessment = repertoireAssessment,''',
'''                RepertoireProgressCard(\n                    assessment = repertoireAssessment,\n                    hasCertifiedViableDay = hasCertifiedViableDay,''')
# target signature and gate
replace_once(p,
'''private fun repertoireProgressTarget(\n    assessment: RepertoireAssessment?,\n    foods: List<Food>,''',
'''private fun repertoireProgressTarget(\n    assessment: RepertoireAssessment?,\n    hasCertifiedViableDay: Boolean,\n    foods: List<Food>,''')
replace_once(p,
'''    if (assessment.searchStatus == ConstraintSearchStatus.FEASIBLE) {''',
'''    if (hasCertifiedViableDay || assessment.searchStatus == ConstraintSearchStatus.FEASIBLE) {''')
# card signature and remember call
replace_once(p,
'''private fun RepertoireProgressCard(\n    assessment: RepertoireAssessment?,\n    foods: List<Food>,''',
'''private fun RepertoireProgressCard(\n    assessment: RepertoireAssessment?,\n    hasCertifiedViableDay: Boolean,\n    foods: List<Food>,''')
replace_once(p,
'''    val (level, target) = remember(assessment, foods, repertoireFoodIds, planningRules) {\n        repertoireProgressTarget(assessment, foods, repertoireFoodIds, planningRules)\n    }''',
'''    val (level, target) = remember(\n        assessment, hasCertifiedViableDay, foods, repertoireFoodIds, planningRules\n    ) {\n        repertoireProgressTarget(\n            assessment, hasCertifiedViableDay, foods, repertoireFoodIds, planningRules\n        )\n    }''')

# Regression test for monotonicity of saved witness under added optional foods.
Path('app/src/test/java/es/david/rumbo/logic/CertifiedDayWitnessPersistenceTest.kt').write_text(r'''package es.david.rumbo.logic

import es.david.rumbo.model.CertifiedDayLevel
import es.david.rumbo.model.CertifiedDayWitness
import es.david.rumbo.model.Food
import es.david.rumbo.model.FoodCategory
import es.david.rumbo.model.MealDistributionPolicy
import es.david.rumbo.model.MealType
import es.david.rumbo.model.PlannedFood
import es.david.rumbo.model.PlannedItemKind
import es.david.rumbo.model.PlannedMeal
import es.david.rumbo.model.PlanningFrequency
import es.david.rumbo.model.PlanningRule
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.WeekDay
import kotlin.test.Test
import kotlin.test.assertTrue

class CertifiedDayWitnessPersistenceTest {
    private val target = Recommendation(2000, 100, 250, 67, "test")

    private fun food(id: Long, kcal: Double, protein: Double, carbs: Double, fat: Double) = Food(
        id, "F$id", FoodCategory.OTHER, kcal, fat, carbs, protein, 2.0,
        culinaryRoles = setOf("STANDALONE")
    )

    @Test
    fun `adding optional foods cannot invalidate an already valid viable witness`() {
        val baseFoods = listOf(
            food(1, 500.0, 25.0, 62.5, 16.75),
            food(2, 500.0, 25.0, 62.5, 16.75),
            food(3, 500.0, 25.0, 62.5, 16.75),
            food(4, 500.0, 25.0, 62.5, 16.75),
            food(5, 500.0, 25.0, 62.5, 16.75)
        )
        val mealTypes = MealType.entries
        val meals = mealTypes.mapIndexed { index, type ->
            PlannedMeal(
                id = (index + 1).toLong(),
                type = type,
                days = setOf(WeekDay.MONDAY),
                items = listOf(PlannedFood(baseFoods[index].id, 80.0, false))
            )
        }
        val baseRules = baseFoods.mapIndexed { index, f ->
            PlanningRule(
                itemKind = PlannedItemKind.FOOD,
                itemId = f.id,
                allowedMealTypes = setOf(mealTypes[index]),
                frequency = PlanningFrequency.NORMAL,
                preferredGrams = 80.0,
                minimumFactor = 0.5,
                maximumFactor = 1.5
            )
        }
        val witness = CertifiedDayWitness(
            CertifiedDayLevel.VIABLE, 11L, WeekDay.MONDAY, meals
        )
        val foodsBefore = baseFoods.associateBy { it.id }
        assertTrue(CertifiedDayWitnessEvaluator.isViable(
            witness, baseRules, foodsBefore, emptyMap(), target, MealDistributionPolicy.defaults
        ))

        val added = listOf(
            food(101, 30.0, 2.0, 5.0, 0.2),
            food(102, 35.0, 2.0, 6.0, 0.2)
        )
        val addedRules = added.map { f ->
            PlanningRule(
                itemKind = PlannedItemKind.FOOD,
                itemId = f.id,
                allowedMealTypes = setOf(MealType.LUNCH, MealType.DINNER),
                frequency = PlanningFrequency.NORMAL,
                preferredGrams = 100.0
            )
        }
        assertTrue(CertifiedDayWitnessEvaluator.isViable(
            witness,
            baseRules + addedRules,
            (baseFoods + added).associateBy { it.id },
            emptyMap(),
            target,
            MealDistributionPolicy.defaults
        ))
    }
}
''')

print('certified day persistence applied')
