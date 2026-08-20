package es.david.rumbo.logic

import es.david.rumbo.model.*
import org.junit.Assert.assertNotNull
import org.junit.Before
import org.junit.Test

class ExportedProfileLevel3RegressionTest {
    @Before fun reset() {
        CulinaryPolicy.configure(emptyList())
        WeeklyMenuAcceptancePolicy.configure(NutritionToleranceSettings())
    }

    @Test fun exportedProfileFindsCulinarilySatisfactoryDay() {
        val foods = listOf(
            food(5877912053805521076L, "Volador, crudo", FoodCategory.PROTEIN, 87.97801147227534, 21.0, 0.0, 0.3, 0.0, 150.0, "", setOf("PLATE_CENTER")),
            food(4908616859504657730L, "Bacalao, salado, remojado, crudo", FoodCategory.PROTEIN, 109.17782026768643, 26.0, 0.0, 0.4, 0.0, 150.0, "bacalao", setOf("PLATE_CENTER")),
            food(4883618187182678371L, "Huevo de gallina, clara, cruda", FoodCategory.PROTEIN, 44.765774378585085, 10.5, 0.3, 0.1, 0.0, 60.0, "huevo", setOf("BINDER","PLATE_CENTER")),
            food(5040197807541378941L, "Berberechos en conserva", FoodCategory.PROTEIN, 47.896749521988525, 10.7, 0.14918738049713198, 0.5, 0.0, 100.0, "", setOf("PLATE_CENTER","SANDWICH_FILLING")),
            food(4533143235677122585L, "Jamón cocido, categoría s/e", FoodCategory.PROTEIN, 113.47992351816444, 21.0, 0.4, 3.0, 0.0, 50.0, "cerdo", setOf("PLATE_CENTER","SANDWICH_FILLING")),
            food(4365814837990144418L, "Leche de vaca, desnatada, pasteurizada", FoodCategory.PROTEIN, 36.971999999999994, 3.893, 4.9, 0.2, 0.0, 200.0, "leche", setOf("BEVERAGE","CEREAL_BASE","POWDER_BASE","STANDALONE")),
            food(5113321827553490261L, "Arroz", FoodCategory.CARBOHYDRATE, 385.8269598470363, 7.0, 86.0, 0.9, 0.2, 80.0, "arroz", setOf("PLATE_BASE")),
            food(5759078436861737485L, "Pan blanco, tostado", FoodCategory.CARBOHYDRATE, 303.68068833652006, 10.1, 59.2, 2.5, 4.5, 60.0, "trigo", setOf("PLATE_BASE","SANDWICH_BASE","STANDALONE")),
            food(5688008557442937568L, "Judías blancas, cocidas", FoodCategory.PROTEIN, 322.8728489483748, 21.4, 54.8, 1.5, 21.3, 180.0, "", setOf("PLATE_BASE","PLATE_CENTER","SIDE")),
            food(4078594988320490919L, "Lenteja, hervida", FoodCategory.PROTEIN, 331.142447418738, 23.0, 54.8, 1.7, 11.2, 180.0, "lenteja", setOf("PLATE_BASE","PLATE_CENTER","SIDE")),
            food(5916984186410301698L, "Pera", FoodCategory.FRUIT, 44.69407265774378, 0.4, 10.6, 0.07711918419375349, 2.3, 150.0, "pera", setOf("DESSERT","STANDALONE")),
            food(5485709273594849150L, "Piña", FoodCategory.FRUIT, 48.75717017208413, 0.5, 11.5, 0.08413001912045893, 1.2, 150.0, "", setOf("DESSERT","STANDALONE")),
            food(4667602396619332474L, "Melocotón", FoodCategory.FRUIT, 39.0057361376673, 0.6, 9.0, 0.06730401529636668, 1.4, 150.0, "melocoton", setOf("DESSERT","STANDALONE")),
            food(5961251453330686429L, "Plátano", FoodCategory.FRUIT, 88.7906309751434, 1.2, 20.0, 0.3, 3.4, 150.0, "platano", setOf("DESSERT","STANDALONE")),
            food(5194589425113431274L, "Aceite de oliva virgen extra", FoodCategory.FAT, 884.321223709369, 0.0, 0.0, 100.0, 0.0, 10.0, "aceituna", setOf("COOKING_MEDIUM","SAUCE_DRESSING")),
            food(5203449563016489509L, "Nuez", FoodCategory.FAT, 592.0411089866157, 14.0, 3.3, 63.28, 5.2, 30.0, "nuez", setOf("STANDALONE","TOPPING")),
            food(5859693614946220060L, "Foie gras", FoodCategory.PROTEIN, 441.92160611854683, 10.0, 3.0, 44.0, 0.0, 150.0, "", setOf("PLATE_CENTER")),
            food(5140518523843252124L, "Salami", FoodCategory.PROTEIN, 433.1022944550669, 17.8, 1.3, 40.2, 0.1, 50.0, "", setOf("PLATE_CENTER","SANDWICH_FILLING")),
            food(4415633190118516354L, "Lechuga", FoodCategory.VEGETABLE, 15.565248565965582, 1.125, 1.4, 0.6, 1.5, 100.0, "lechuga", setOf("SALAD_BASE")),
            food(4256230435931326165L, "Pimiento verde, crudo", FoodCategory.VEGETABLE, 22.0, 0.6, 2.6, 0.6, 1.9, 100.0, "pimiento", setOf("SIDE","STANDALONE")),
            food(4597281240235899950L, "Membrillo, crudo", FoodCategory.FRUIT, 28.806166347992352, 0.3, 6.3, 0.225, 6.4, 150.0, "", setOf("DESSERT","STANDALONE")),
            food(5551334170044859604L, "Fuet", FoodCategory.PROTEIN, 472.9923518164436, 19.5, 5.5, 42.0, 0.0, 150.0, "", setOf("PLATE_CENTER","SANDWICH_FILLING")),
            food(5053420851366914800L, "Pan blanco, de barra, sin sal", FoodCategory.CARBOHYDRATE, 261.6682600382409, 8.0, 53.9, 1.14925, 3.5, 60.0, "trigo", setOf("PLATE_BASE","SANDWICH_BASE","STANDALONE")),
        )
        val rules = listOf(
            rule(5877912053805521076L, setOf(MealType.DINNER,MealType.LUNCH), 100.0, 0.5, 1.5),
            rule(4908616859504657730L, setOf(MealType.DINNER,MealType.LUNCH), 100.0, 0.5, 1.5),
            rule(4883618187182678371L, setOf(MealType.DINNER,MealType.LUNCH), 100.0, 0.5, 1.5),
            rule(5040197807541378941L, setOf(MealType.BREAKFAST,MealType.MORNING_SNACK,MealType.LUNCH,MealType.AFTERNOON_SNACK,MealType.DINNER), 100.0, 0.5, 1.5),
            rule(4533143235677122585L, setOf(MealType.MORNING_SNACK,MealType.AFTERNOON_SNACK), 100.0, 0.5, 1.5),
            rule(4365814837990144418L, setOf(MealType.BREAKFAST), 100.0, 0.5, 1.5),
            rule(5113321827553490261L, setOf(MealType.LUNCH), 100.0, 0.5, 1.5),
            rule(5759078436861737485L, setOf(MealType.BREAKFAST,MealType.LUNCH,MealType.DINNER), 100.0, 0.5, 1.5),
            rule(5688008557442937568L, setOf(MealType.LUNCH), 100.0, 0.5, 1.5),
            rule(4078594988320490919L, setOf(MealType.LUNCH), 100.0, 0.5, 1.5),
            rule(5916984186410301698L, setOf(MealType.LUNCH,MealType.DINNER), 100.0, 0.5, 1.5),
            rule(5485709273594849150L, setOf(MealType.LUNCH,MealType.DINNER), 100.0, 0.5, 1.5),
            rule(4667602396619332474L, setOf(MealType.LUNCH,MealType.DINNER), 100.0, 0.5, 1.5),
            rule(5961251453330686429L, setOf(MealType.BREAKFAST,MealType.LUNCH,MealType.DINNER), 100.0, 0.5, 1.5),
            rule(5194589425113431274L, setOf(MealType.DINNER,MealType.LUNCH), 100.0, 0.5, 1.5),
            rule(5203449563016489509L, setOf(MealType.MORNING_SNACK,MealType.DINNER,MealType.AFTERNOON_SNACK,MealType.LUNCH,MealType.BREAKFAST), 100.0, 0.5, 1.5),
            rule(5859693614946220060L, setOf(MealType.MORNING_SNACK,MealType.AFTERNOON_SNACK), 100.0, 0.5, 1.5),
            rule(5140518523843252124L, setOf(MealType.MORNING_SNACK,MealType.AFTERNOON_SNACK), 100.0, 0.5, 1.5),
            rule(4415633190118516354L, setOf(MealType.DINNER,MealType.LUNCH), 100.0, 0.5, 1.5),
            rule(4256230435931326165L, setOf(MealType.LUNCH,MealType.DINNER), 100.0, 0.5, 1.5),
            rule(4597281240235899950L, setOf(MealType.BREAKFAST), 100.0, 0.5, 1.5),
            rule(5551334170044859604L, setOf(MealType.MORNING_SNACK,MealType.AFTERNOON_SNACK), 100.0, 0.5, 1.5),
            rule(5053420851366914800L, setOf(MealType.MORNING_SNACK,MealType.AFTERNOON_SNACK), 100.0, 0.5, 1.5),
        )
        val meals = listOf(
            meal(1001L, MealType.BREAKFAST, listOf(PlannedFood(5759078436861737485L, 50.0, true, 40.0, 300.0),PlannedFood(4365814837990144418L, 130.0, true, 100.0, 500.0),PlannedFood(5961251453330686429L, 40.0, true, 40.0, 250.0),PlannedFood(5203449563016489509L, 45.0, true, 5.0, 60.0))),
            meal(1002L, MealType.MORNING_SNACK, listOf(PlannedFood(4533143235677122585L, 130.0, true, 20.0, 150.0),PlannedFood(5203449563016489509L, 6.0, true, 5.0, 60.0))),
            meal(1003L, MealType.LUNCH, listOf(PlannedFood(5916984186410301698L, 160.0, true, 40.0, 250.0),PlannedFood(5688008557442937568L, 40.0, true, 40.0, 300.0),PlannedFood(4078594988320490919L, 90.0, true, 40.0, 300.0),PlannedFood(4256230435931326165L, 170.0, true, 50.0, 300.0))),
            meal(1004L, MealType.AFTERNOON_SNACK, listOf(PlannedFood(4533143235677122585L, 130.0, true, 20.0, 150.0),PlannedFood(5203449563016489509L, 6.0, true, 5.0, 60.0))),
            meal(1005L, MealType.DINNER, listOf(PlannedFood(4256230435931326165L, 110.0, true, 50.0, 300.0),PlannedFood(5759078436861737485L, 65.0, true, 40.0, 300.0),PlannedFood(4908616859504657730L, 160.0, true, 75.0, 300.0),PlannedFood(5961251453330686429L, 85.0, true, 40.0, 250.0))),
        )
        val baseline = CertifiedDayWitness(CertifiedDayLevel.COMPLETE, 11L, WeekDay.MONDAY, meals, meals.hashCode())
        val byId = foods.associateBy { it.id }
        val target = Recommendation(1875, 154, 198, 52, "export")
        fun planned(id: Long, role: CulinaryRole, mealType: MealType): PlannedFood {
            val policy = PortionPolicyResolver.resolve(
                byId.getValue(id), role, mealType, target, MealDistributionPolicy.defaults
            )
            return PlannedFood(
                id, policy.effectivePreferred, true,
                policy.satisfactoryMinimum, policy.satisfactoryMaximum
            )
        }
        val designedMeals = listOf(
            meal(2001L, MealType.BREAKFAST, listOf(
                planned(4365814837990144418L, CulinaryRole.BEVERAGE, MealType.BREAKFAST),
                planned(5961251453330686429L, CulinaryRole.DESSERT, MealType.BREAKFAST),
                planned(5203449563016489509L, CulinaryRole.TOPPING, MealType.BREAKFAST),
                planned(4597281240235899950L, CulinaryRole.DESSERT, MealType.BREAKFAST)
            )),
            meal(2002L, MealType.MORNING_SNACK, listOf(
                planned(5053420851366914800L, CulinaryRole.SANDWICH_BASE, MealType.MORNING_SNACK),
                planned(4533143235677122585L, CulinaryRole.SANDWICH_FILLING, MealType.MORNING_SNACK)
            )),
            meal(2003L, MealType.LUNCH, listOf(
                planned(5877912053805521076L, CulinaryRole.PLATE_CENTER, MealType.LUNCH),
                planned(4078594988320490919L, CulinaryRole.PLATE_BASE, MealType.LUNCH),
                planned(4415633190118516354L, CulinaryRole.SALAD_BASE, MealType.LUNCH),
                planned(5194589425113431274L, CulinaryRole.SAUCE_DRESSING, MealType.LUNCH)
            )),
            meal(2004L, MealType.AFTERNOON_SNACK, listOf(
                planned(5053420851366914800L, CulinaryRole.SANDWICH_BASE, MealType.AFTERNOON_SNACK),
                planned(5140518523843252124L, CulinaryRole.SANDWICH_FILLING, MealType.AFTERNOON_SNACK)
            )),
            meal(2005L, MealType.DINNER, listOf(
                planned(4908616859504657730L, CulinaryRole.PLATE_CENTER, MealType.DINNER),
                planned(4256230435931326165L, CulinaryRole.SIDE, MealType.DINNER),
                planned(5916984186410301698L, CulinaryRole.DESSERT, MealType.DINNER)
            ))
        )
        val designed = MealQuantityOptimizer.optimize(
            designedMeals, byId, emptyMap(), target,
            setOf(WeekDay.MONDAY), MealDistributionPolicy.defaults
        ).meals
        val designedWitness = CertifiedDayWitness(
            CertifiedDayLevel.COMPLETE, 99L, WeekDay.MONDAY, designed, designed.hashCode()
        )
        val designedComplete = CertifiedDayWitnessEvaluator.isComplete(
            designedWitness, rules, byId, emptyMap(), target, MealDistributionPolicy.defaults
        )
        val designedCulinary = CulinarySatisfactionEvaluator.evaluateDay(
            WeekDay.MONDAY, designed, byId, emptyMap(), target, MealDistributionPolicy.defaults
        )
        val result = CulinarilySatisfactoryDaySearch.find(
            rules, byId, emptyMap(), target, MealDistributionPolicy.defaults, baseline
        )
        assertNotNull(
            "No level 3 witness. designedComplete=$designedComplete; " +
                "designedCulinary=$designedCulinary; designed=$designed; " +
                "diagnostic=${result.diagnostic}; progress=${result.progressWitness}",
            result.witness
        )
    }

    private fun meal(id: Long, type: MealType, items: List<PlannedFood>) = PlannedMeal(
        id = id, type = type, days = setOf(WeekDay.MONDAY), items = items
    )

    private fun rule(id: Long, meals: Set<MealType>, preferred: Double, min: Double, max: Double) =
        PlanningRule(
            itemKind = PlannedItemKind.FOOD, itemId = id, allowedMealTypes = meals,
            frequency = PlanningFrequency.NORMAL, preferredGrams = preferred,
            minimumFactor = min, maximumFactor = max
        )

    private fun food(
        id: Long, name: String, category: FoodCategory, calories: Double, protein: Double,
        carbohydrates: Double, fat: Double, fiber: Double, portion: Double, family: String,
        roles: Set<String>
    ) = Food(
        id = id, name = name, category = category, calories = calories, proteinGrams = protein,
        carbohydrateGrams = carbohydrates, fatGrams = fat, fiberGrams = fiber,
        portionBasisGrams = portion, family = family.ifBlank { null }, culinaryRoles = roles
    )
}
