package es.david.rumbo.logic

import es.david.rumbo.model.ActivityLevel
import es.david.rumbo.model.BodyAssessment
import es.david.rumbo.model.CalculationBreakdown
import es.david.rumbo.model.DietCompliance
import es.david.rumbo.model.EffectiveValues
import es.david.rumbo.model.GoalAssessment
import es.david.rumbo.model.Measurement
import es.david.rumbo.model.Recommendation
import es.david.rumbo.model.RecommendedGoal
import es.david.rumbo.model.Sex
import es.david.rumbo.model.UserProfile
import es.david.rumbo.model.WeightGoal
import java.time.LocalDate
import java.time.temporal.ChronoUnit
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.roundToInt

object RecommendationEngine {
    private const val KCAL_PER_KG = 7700.0
    private const val HISTORY_DAYS = 28L
    private const val MINIMUM_HISTORY_DAYS = 21L
    private const val MAX_STEP_KCAL = 150

    fun weeklyRateFor(goal: WeightGoal, weightKg: Double?): Double? =
        weightKg?.takeIf { goal != WeightGoal.AUTOMATIC }?.let { desiredWeeklyRate(goal, it) }

    fun effectiveValues(
        history: List<Measurement>,
        candidate: Measurement? = null
    ): EffectiveValues {
        val ordered = history.sortedWith(compareBy<Measurement> { it.date }.thenBy { it.id })
        val goalChange = candidate?.takeIf { it.goal != null }
            ?: ordered.asReversed().firstOrNull { it.goal != null }
        return EffectiveValues(
            weightKg = candidate?.weightKg
                ?: ordered.asReversed().firstOrNull { it.weightKg != null }?.weightKg,
            waistCm = candidate?.waistCm
                ?: ordered.asReversed().firstOrNull { it.waistCm != null }?.waistCm,
            activity = candidate?.activity
                ?: ordered.asReversed().firstOrNull { it.activity != null }?.activity
                ?: ActivityLevel.LIGHT,
            goal = goalChange?.goal ?: WeightGoal.AUTOMATIC,
            weeklyRateKg = goalChange?.weeklyRateKg
        )
    }

    fun assessBody(
        profile: UserProfile,
        history: List<Measurement>,
        candidate: Measurement? = null
    ): BodyAssessment? {
        val relevantHistory = candidate?.let { item ->
            history.filter { !it.date.isAfter(item.date) }
        } ?: history
        val values = effectiveValues(relevantHistory, candidate)
        if (values.weightKg == null && values.waistCm == null) return null

        val heightM = profile.heightCm / 100.0
        val bmi = values.weightKg?.div(heightM.pow(2))
        val waistRatio = values.waistCm?.div(profile.heightCm)
        val bmiInterpretation = bmi?.let {
            when {
                it < 18.5 -> "Por debajo del intervalo de referencia"
                it < 25.0 -> "Intervalo de referencia"
                it < 30.0 -> "Sobrepeso"
                it < 35.0 -> "Obesidad, grado I"
                it < 40.0 -> "Obesidad, grado II"
                else -> "Obesidad, grado III"
            }
        }
        val waistInterpretation = waistRatio?.let {
            when {
                it < 0.40 -> "Por debajo del intervalo de referencia"
                it < 0.50 -> "Adiposidad central saludable"
                it < 0.60 -> "Adiposidad central aumentada"
                else -> "Adiposidad central alta"
            }
        }

        return BodyAssessment(
            bmi = bmi,
            bmiInterpretation = bmiInterpretation,
            waistToHeightRatio = waistRatio,
            waistInterpretation = waistInterpretation
        )
    }

    fun assessGoal(
        profile: UserProfile,
        history: List<Measurement>,
        candidate: Measurement? = null
    ): GoalAssessment {
        val relevantHistory = candidate?.let { item ->
            history.filter { !it.date.isAfter(item.date) }
        } ?: history
        val selectedValues = effectiveValues(relevantHistory, candidate)
        val values = if (selectedValues.goal == WeightGoal.AUTOMATIC) {
            selectedValues.copy(goal = recommendGoal(profile, relevantHistory, candidate).goal)
        } else selectedValues
        val weight = values.weightKg
        val heightM = profile.heightCm / 100.0
        val bmi = weight?.div(heightM.pow(2))
        val waistRatio = values.waistCm?.div(profile.heightCm)
        val isLossGoal = values.goal.weeklyRateFactor < 0.0
        val isGainGoal = values.goal.weeklyRateFactor > 0.0
        val gainIsBlocked = isGainGoal && gainBlocked(bmi, waistRatio)
        val lossIsBlocked = isLossGoal && bmi?.let { it <= 18.5 } == true

        if (weight == null && waistRatio == null) {
            return GoalAssessment(
                headline = "Todavía no se puede valorar el objetivo",
                explanation = "Añade al menos el peso o la cintura para comprobar si «${values.goal.label.lowercase()}» encaja con los indicadores corporales.",
                isGoalLimited = false
            )
        }

        val headline = when {
            lossIsBlocked -> "Este objetivo no es coherente con el IMC actual"
            gainIsBlocked -> "Este objetivo no es coherente con los indicadores actuales"
            isLossGoal && (bmi?.let { it >= 25.0 } == true || waistRatio?.let { it >= 0.50 } == true) ->
                "Este objetivo es coherente con los indicadores actuales"
            isLossGoal -> "Este objetivo requiere especial prudencia"
            isGainGoal -> "Este objetivo es compatible con los indicadores actuales"
            bmi?.let { it >= 25.0 } == true || waistRatio?.let { it >= 0.50 } == true ->
                "Mantener es una opción conservadora"
            else -> "Este objetivo es coherente con los indicadores actuales"
        }

        val bodyReason = when {
            lossIsBlocked -> "El IMC está en ${formatForText(bmi)}; por seguridad, la aplicación elimina cualquier déficit."
            gainIsBlocked -> {
                val reason = when {
                    waistRatio?.let { it >= 0.50 } == true -> "la relación cintura/altura es ${formatForText(waistRatio)}"
                    else -> "el IMC es ${formatForText(bmi)}"
                }
                "No aplica un superávit porque $reason y aumentar el peso no es la recomendación automática más prudente."
            }
            isLossGoal && (bmi?.let { it >= 25.0 } == true || waistRatio?.let { it >= 0.50 } == true) -> {
                val indicators = buildList {
                    bmi?.takeIf { it >= 25.0 }?.let { add("un IMC de ${formatForText(it)}") }
                    waistRatio?.takeIf { it >= 0.50 }?.let { add("una relación cintura/altura de ${formatForText(it)}") }
                }.joinToString(" y ")
                "La pérdida gradual está respaldada por $indicators."
            }
            isLossGoal -> "El IMC y la cintura no muestran un exceso claro; la aplicación conserva un déficit pequeño y vigila el límite inferior de IMC."
            isGainGoal -> "Estos indicadores no impiden una ganancia gradual, aunque no pueden determinar si el peso ganado será músculo o grasa."
            bmi?.let { it >= 25.0 } == true || waistRatio?.let { it >= 0.50 } == true ->
                "Mantener evita seguir aumentando, aunque una pérdida gradual también sería compatible con los indicadores corporales."
            else -> "El IMC y la cintura disponibles no justifican modificar el peso automáticamente."
        }

        val paceReason = weight?.let {
            val desiredRate = values.weeklyRateKg ?: desiredWeeklyRate(values.goal, it)
            if (desiredRate == 0.0) {
                "El ritmo buscado es mantener una tendencia estable."
            } else {
                "El ritmo propuesto es de ${formatForText(abs(desiredRate))} kg por semana, dentro de los límites de seguridad de la aplicación."
            }
        }.orEmpty()

        val referenceDate = candidate?.date
            ?: relevantHistory.maxWithOrNull(compareBy<Measurement> { it.date }.thenBy { it.id })?.date
            ?: LocalDate.now()
        val recentHistory = relevantHistory.filter { !it.date.isBefore(referenceDate.minusDays(HISTORY_DAYS)) }
        val recentWeights = recentHistory.filter { it.weightKg != null }
        val span = if (recentWeights.size >= 2) {
            ChronoUnit.DAYS.between(recentWeights.minOf { it.date }, recentWeights.maxOf { it.date })
        } else 0L
        val historyReason = if (recentWeights.size >= 4 && span >= MINIMUM_HISTORY_DAYS) {
            val actualRate = regressionWeeklyRate(recentWeights.map { it.date to it.weightKg!! })
            val compliance = recentHistory.mapNotNull { it.compliance?.score }
            if (compliance.size >= 3 && compliance.average() in 2.75..3.25) {
                "El historial muestra una tendencia de ${formatSignedForText(actualRate)} kg por semana y un cumplimiento suficientemente cercano al plan para interpretarla."
            } else {
                "Hay historial de peso, pero el cumplimiento registrado todavía no permite atribuir su evolución con fiabilidad al objetivo calórico."
            }
        } else {
            "Todavía no hay suficiente historial para comprobar si la evolución real coincide con este objetivo."
        }

        val recentWaists = recentHistory.filter { it.waistCm != null }
        val waistSpan = if (recentWaists.size >= 2) {
            ChronoUnit.DAYS.between(recentWaists.minOf { it.date }, recentWaists.maxOf { it.date })
        } else 0L
        val waistReason = if (recentWaists.size >= 3 && waistSpan >= MINIMUM_HISTORY_DAYS) {
            val waistRate = regressionWeeklyRate(recentWaists.map { it.date to it.waistCm!! })
            when {
                waistRate < -0.05 -> "La cintura está bajando ${formatForText(abs(waistRate))} cm por semana, una señal favorable que se interpreta junto al peso."
                waistRate > 0.05 -> "La cintura está subiendo ${formatForText(waistRate)} cm por semana, una señal que aconseja prudencia aunque el peso evolucione de otra forma."
                else -> "La cintura se mantiene aproximadamente estable durante el periodo disponible."
            }
        } else ""

        return GoalAssessment(
            headline = headline,
            explanation = listOf(bodyReason, paceReason, historyReason, waistReason)
                .filter { it.isNotBlank() }
                .joinToString(" "),
            isGoalLimited = lossIsBlocked || gainIsBlocked
        )
    }

    fun recommendGoal(
        profile: UserProfile,
        history: List<Measurement>,
        candidate: Measurement? = null
    ): RecommendedGoal {
        val relevantHistory = candidate?.let { item ->
            history.filter { !it.date.isAfter(item.date) }
        } ?: history
        val body = assessBody(profile, relevantHistory, candidate)
        val bmi = body?.bmi
        val waistRatio = body?.waistToHeightRatio
        val weight = effectiveValues(relevantHistory, candidate).weightKg

        val goal = when {
            bmi?.let { it < 18.5 } == true -> WeightGoal.GAIN_SLOWLY
            waistRatio?.let { it >= 0.60 } == true ||
                (bmi?.let { it >= 30.0 } == true && waistRatio?.let { it >= 0.50 } == true) ->
                WeightGoal.LOSE_FASTER
            bmi?.let { it >= 25.0 } == true || waistRatio?.let { it >= 0.50 } == true ->
                WeightGoal.LOSE_SLOWLY
            else -> WeightGoal.MAINTAIN
        }

        val rate = weight?.let { abs(desiredWeeklyRate(goal, it)) }
        val rateText = rate?.let(::formatOneDecimalForText) ?: "—"
        val referenceDate = candidate?.date
            ?: relevantHistory.maxWithOrNull(compareBy<Measurement> { it.date }.thenBy { it.id })?.date
            ?: LocalDate.now()
        val recentHistory = relevantHistory.filter { !it.date.isBefore(referenceDate.minusDays(HISTORY_DAYS)) }
        val recentWeights = recentHistory.filter { it.weightKg != null }
        val weightSpan = if (recentWeights.size >= 2) {
            ChronoUnit.DAYS.between(recentWeights.minOf { it.date }, recentWeights.maxOf { it.date })
        } else 0L
        val compliance = recentHistory.mapNotNull { it.compliance?.score }
        val canAdapt = recentWeights.size >= 4 && weightSpan >= MINIMUM_HISTORY_DAYS &&
            compliance.size >= 3 && compliance.average() in 2.75..3.25
        val historyText = if (canAdapt) {
            "Rumbo utiliza tu evolución reciente para ajustar las calorías e intentar mantener este ritmo."
        } else {
            "Es un punto de partida: cuando haya suficientes mediciones, Rumbo ajustará las calorías según tu evolución real."
        }

        val explanation = when (goal) {
            WeightGoal.GAIN_SLOWLY ->
                "Te recomendamos ganar $rateText kg por semana porque tu peso es bajo para tu altura. El objetivo es recuperarlo gradualmente, evitando un superávit innecesariamente grande y favoreciendo que parte de la ganancia sea músculo. $historyText"
            WeightGoal.LOSE_FASTER -> when {
                bmi?.let { it >= 35.0 } == true ->
                    "Te recomendamos perder $rateText kg por semana porque tu IMC muestra un exceso importante de peso. Rumbo limita el ritmo al 0,75 % semanal para evitar objetivos extremos; en esta situación también puede ser conveniente contar con supervisión sanitaria. $historyText"
                bmi?.let { it < 25.0 } == true && waistRatio?.let { it >= 0.60 } == true ->
                    "Te recomendamos perder $rateText kg por semana porque, aunque tu peso total está dentro del intervalo habitual, tu cintura muestra una acumulación abdominal elevada. Rumbo utiliza un ritmo del 0,75 % semanal, más decidido pero todavía gradual. $historyText"
                else ->
                    "Te recomendamos perder $rateText kg por semana porque los indicadores muestran un exceso más claro de grasa corporal o abdominal. Rumbo utiliza el 0,75 % semanal: un ritmo mayor, pero todavía dentro del intervalo gradual utilizado en las referencias. $historyText"
            }
            WeightGoal.LOSE_SLOWLY -> when {
                bmi?.let { it < 25.0 } == true ->
                    "Te recomendamos perder $rateText kg por semana para reducir la grasa abdominal sin provocar una bajada importante de peso. Rumbo utiliza el 0,5 % de tu peso como ritmo inicial prudente; en tu caso será más importante observar la cintura que la báscula. $historyText"
                waistRatio?.let { it < 0.50 } == true ->
                    "Te recomendamos perder $rateText kg por semana porque tu peso está por encima del intervalo habitual, aunque la cintura no muestra una acumulación abdominal elevada. Por esa discrepancia, Rumbo utiliza el ritmo prudente del 0,5 % semanal. $historyText"
                else ->
                    "Te recomendamos perder $rateText kg por semana porque tanto tu peso como tu cintura están ligeramente por encima de sus referencias. Rumbo utiliza el ritmo prudente del 0,5 % semanal, suficiente para reducir grasa sin aplicar un déficit excesivo. $historyText"
            }
            WeightGoal.MAINTAIN ->
                "Te recomendamos mantener el peso porque ninguno de los dos indicadores justifica ganarlo o perderlo. Las variaciones pequeñas son normales; el objetivo es conservar una tendencia estable. $historyText"
            else -> ""
        }

        return RecommendedGoal(goal, explanation)
    }

    fun recommend(
        profile: UserProfile,
        history: List<Measurement>,
        candidate: Measurement
    ): Recommendation? {
        val relevantHistory = history.filter { !it.date.isAfter(candidate.date) }
        val selectedValues = effectiveValues(relevantHistory, candidate)
        val values = if (selectedValues.goal == WeightGoal.AUTOMATIC) {
            selectedValues.copy(goal = recommendGoal(profile, relevantHistory, candidate).goal)
        } else selectedValues
        val weight = values.weightKg ?: return null
        if (weight !in 30.0..350.0 || !profile.isValid(candidate.date.year)) return null

        val age = (candidate.date.year - profile.birthYear).coerceIn(16, 110)
        val heightM = profile.heightCm / 100.0
        val bmi = weight / heightM.pow(2)
        val waistRatio = values.waistCm?.div(profile.heightCm)
        val sexAdjustment = if (profile.sex == Sex.MALE) 5 else -161
        val bmr = 10.0 * weight + 6.25 * profile.heightCm - 5.0 * age + sexAdjustment
        val maintenance = bmr * values.activity.multiplier

        var desiredRate = values.weeklyRateKg ?: desiredWeeklyRate(values.goal, weight)
        var safetyReason: String? = null

        if (desiredRate < 0.0) {
            when {
                bmi <= 18.5 -> {
                    desiredRate = 0.0
                    safetyReason = "no aplica un déficit porque el IMC no permite recomendar una pérdida de peso"
                }
                bmi < 20.0 -> {
                    val maximumFourWeekLoss = max(0.0, weight - 18.5 * heightM.pow(2)) / 4.0
                    val limited = max(desiredRate, -maximumFourWeekLoss)
                    if (limited > desiredRate) {
                        desiredRate = limited
                        safetyReason = "reduce el déficit al acercarse al límite inferior de IMC"
                    }
                }
            }
        } else if (desiredRate > 0.0) {
            if (gainBlocked(bmi, waistRatio)) {
                desiredRate = 0.0
                safetyReason = "no aplica un superávit: los datos actuales aconsejan mantener antes que seguir aumentando peso"
            }
        }

        val goalAdjustment = desiredRate * KCAL_PER_KG / 7.0
        val minimumCalories = max(
            if (profile.sex == Sex.MALE) 1500.0 else 1200.0,
            bmr * 1.05
        )
        val goalBasedTarget = maintenance + goalAdjustment
        var target = goalBasedTarget.coerceIn(
            minimumCalories,
            maintenance + 500.0
        )
        val energyLimitAdjustment = target - goalBasedTarget
        val energyLimitExplanation = when {
            energyLimitAdjustment > 0.0 -> "aplica el mínimo energético de seguridad"
            energyLimitAdjustment < 0.0 -> "limita el superávit máximo a 500 kcal diarias"
            else -> null
        }

        val adaptive = adaptiveAdjustment(history, candidate.date, desiredRate)
        val appliedHistoryAdjustment = if (adaptive.canAdjust) adaptive.kcalAdjustment else 0.0
        target += appliedHistoryAdjustment

        val previous = history
            .filter { !it.date.isAfter(candidate.date) }
            .maxWithOrNull(compareBy<Measurement> { it.date }.thenBy { it.id })
            ?.recommendation
            ?.calories
        var previousLimitAdjustment = 0.0
        var previousLimitExplanation: String? = null
        if (previous != null) {
            val beforeLimit = target
            target = beforeLimit.coerceIn(
                (previous - MAX_STEP_KCAL).toDouble(),
                (previous + MAX_STEP_KCAL).toDouble()
            )
            previousLimitAdjustment = target - beforeLimit
            if (previousLimitAdjustment != 0.0) {
                previousLimitExplanation = "limita el cambio a 150 kcal respecto a la recomendación anterior"
            }
        }

        val calories = roundTo25(target.roundToInt())
        val referenceWeight = min(weight, 30.0 * heightM.pow(2))
        val protein = (referenceWeight * 1.9).roundToInt()
        val fat = (calories / 36.0).roundToInt()
        val carbohydrates = max(0, ((calories - protein * 4 - fat * 9) / 4.0).roundToInt())

        val reason = buildReason(
            values = values,
            hasPrevious = previous != null,
            safetyReason = safetyReason,
            adaptive = adaptive
        )
        return Recommendation(
            calories = calories,
            proteinGrams = protein,
            carbohydrateGrams = carbohydrates,
            fatGrams = fat,
            reason = reason,
            isSafetyLimited = safetyReason != null || energyLimitExplanation != null || previousLimitExplanation != null,
            calculation = CalculationBreakdown(
                weightKg = weight,
                heightCm = profile.heightCm,
                ageYears = age,
                sexAdjustment = sexAdjustment,
                restingCalories = bmr,
                activity = values.activity,
                maintenanceCalories = maintenance,
                appliedWeeklyRateKg = (target - maintenance) * 7.0 / KCAL_PER_KG,
                goalAdjustmentCalories = goalAdjustment,
                goalSafetyExplanation = safetyReason,
                energyLimitAdjustmentCalories = energyLimitAdjustment,
                energyLimitExplanation = energyLimitExplanation,
                historyAdjustmentCalories = appliedHistoryAdjustment,
                historyExplanation = adaptive.explanation,
                previousLimitAdjustmentCalories = previousLimitAdjustment,
                previousLimitExplanation = previousLimitExplanation,
                beforeRoundingCalories = target
            )
        )
    }

    private fun gainBlocked(bmi: Double?, waistRatio: Double?): Boolean =
        bmi?.let { it >= 35.0 } == true || waistRatio?.let { it >= 0.50 } == true ||
            (bmi?.let { it >= 30.0 } == true && waistRatio == null)

    private fun desiredWeeklyRate(goal: WeightGoal, weight: Double): Double {
        if (goal == WeightGoal.MAINTAIN || goal == WeightGoal.AUTOMATIC) return 0.0
        val magnitude = min(abs(weight * goal.weeklyRateFactor), goal.maximumRate)
        return if (goal.weeklyRateFactor < 0) -magnitude else magnitude
    }

    private data class AdaptiveResult(
        val canAdjust: Boolean,
        val kcalAdjustment: Double = 0.0,
        val explanation: String
    )

    private fun adaptiveAdjustment(
        history: List<Measurement>,
        currentDate: LocalDate,
        desiredRate: Double
    ): AdaptiveResult {
        val windowStart = currentDate.minusDays(HISTORY_DAYS)
        val window = history.filter { !it.date.isBefore(windowStart) && it.date.isBefore(currentDate) }
        val weights = window.filter { it.weightKg != null }
        if (weights.size < 4) {
            return AdaptiveResult(false, explanation = "todavía no hay suficientes mediciones de peso para corregir la estimación")
        }
        val span = ChronoUnit.DAYS.between(weights.minOf { it.date }, weights.maxOf { it.date })
        if (span < MINIMUM_HISTORY_DAYS) {
            return AdaptiveResult(false, explanation = "el historial aún no cubre 21 días; de momento conserva la estimación inicial")
        }

        val compliance = window.mapNotNull { it.compliance?.score }
        if (compliance.size < 3) {
            return AdaptiveResult(false, explanation = "faltan valoraciones de cumplimiento para interpretar con fiabilidad el cambio de peso")
        }
        val averageCompliance = compliance.average()
        if (averageCompliance !in 2.75..3.25) {
            val direction = if (averageCompliance < 2.75) "por debajo" else "por encima"
            return AdaptiveResult(false, explanation = "no corrige el objetivo porque el cumplimiento medio ha estado $direction de lo previsto")
        }

        val weightRate = regressionWeeklyRate(weights.map { it.date to it.weightKg!! })
        val waists = window.filter { it.waistCm != null }
        val waistRate = if (waists.size >= 3) {
            regressionWeeklyRate(waists.map { it.date to it.waistCm!! })
        } else null

        if (waistRate != null) {
            val opposingSignals = (weightRate > 0.10 && waistRate < -0.20) ||
                (weightRate < -0.10 && waistRate > 0.20)
            if (opposingSignals) {
                return AdaptiveResult(
                    false,
                    explanation = "peso y cintura evolucionan en sentidos opuestos; mantiene y observa antes de cambiar calorías"
                )
            }
        }

        val rawCorrection = (desiredRate - weightRate) * KCAL_PER_KG / 7.0 * 0.35
        val correction = rawCorrection.coerceIn(-MAX_STEP_KCAL.toDouble(), MAX_STEP_KCAL.toDouble())
        val explanation = when {
            abs(correction) < 25.0 -> "la tendencia de peso está cerca del ritmo buscado y no requiere corrección"
            correction > 0 -> "la tendencia ha sido más rápida a la baja de lo buscado y aumenta ligeramente la energía"
            else -> "la tendencia ha sido más alta de lo buscado y reduce ligeramente la energía"
        }
        return AdaptiveResult(true, correction, explanation)
    }

    internal fun regressionWeeklyRate(points: List<Pair<LocalDate, Double>>): Double {
        if (points.size < 2) return 0.0
        val origin = points.minOf { it.first }
        val xs = points.map { ChronoUnit.DAYS.between(origin, it.first).toDouble() }
        val ys = points.map { it.second }
        val xMean = xs.average()
        val yMean = ys.average()
        val denominator = xs.sumOf { (it - xMean).pow(2) }
        if (denominator == 0.0) return 0.0
        val numerator = xs.indices.sumOf { (xs[it] - xMean) * (ys[it] - yMean) }
        return numerator / denominator * 7.0
    }

    private fun buildReason(
        values: EffectiveValues,
        hasPrevious: Boolean,
        safetyReason: String?,
        adaptive: AdaptiveResult
    ): String {
        val start = if (hasPrevious) {
            "Calculadas con el último peso disponible, la actividad ${values.activity.label.lowercase()} y el objetivo «${values.goal.label.lowercase()}»"
        } else {
            "Estimación inicial según el peso disponible y los datos personales"
        }
        val details = when {
            safetyReason != null -> safetyReason
            else -> adaptive.explanation
        }
        return "$start; $details."
    }

    private fun roundTo25(value: Int): Int = ((value + 12) / 25) * 25

    private fun formatOneDecimalForText(value: Double): String =
        String.format(java.util.Locale.forLanguageTag("es-ES"), "%.1f", value)

    private fun formatForText(value: Double?): String = value?.let {
        String.format(java.util.Locale.forLanguageTag("es-ES"), "%.2f", it)
    } ?: "—"

    private fun formatSignedForText(value: Double): String = when {
        value > 0.0 -> "+${formatForText(value)}"
        value < 0.0 -> "−${formatForText(abs(value))}"
        else -> "0,00"
    }
}
