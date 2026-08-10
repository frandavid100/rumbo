package es.david.rumbo.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

class AppDataTest {
    private val david = UserProfile(1, "David", 177.0, 1979, Sex.MALE)
    private val araceli = UserProfile(2, "Araceli", 165.0, 1982, Sex.FEMALE)

    @Test
    fun activeProfileExposesOnlyItsOwnMeasurements() {
        val davidMeasurement = Measurement(10, LocalDate.of(2026, 8, 8), weightKg = 83.4)
        val araceliMeasurement = Measurement(20, LocalDate.of(2026, 8, 8), weightKg = 60.0)
        val data = AppData(
            profiles = listOf(
                ProfileData(david, listOf(davidMeasurement)),
                ProfileData(araceli, listOf(araceliMeasurement))
            ),
            activeProfileId = araceli.id
        )

        assertEquals("Araceli", data.profile?.name)
        assertEquals(listOf(araceliMeasurement), data.measurements)
    }

    @Test
    fun missingActiveIdFallsBackToFirstProfileWithoutMixingHistories() {
        val davidMeasurement = Measurement(10, LocalDate.of(2026, 8, 8), weightKg = 83.4)
        val data = AppData(
            profiles = listOf(ProfileData(david, listOf(davidMeasurement)), ProfileData(araceli)),
            activeProfileId = 999
        )

        assertEquals("David", data.profile?.name)
        assertEquals(listOf(davidMeasurement), data.measurements)
    }

    @Test
    fun profileIsReadyWithEitherBodyMeasurementAndAutomaticGoal() {
        val empty = AppData(
            profiles = listOf(ProfileData(david)),
            activeProfileId = david.id
        )
        val weightOnly = empty.copy(
            profiles = listOf(
                ProfileData(
                    david,
                    listOf(Measurement(10, LocalDate.of(2026, 8, 8), weightKg = 83.4))
                )
            )
        )
        val waistOnly = empty.copy(
            profiles = listOf(
                ProfileData(
                    david,
                    listOf(Measurement(11, LocalDate.of(2026, 8, 8), waistCm = 91.0))
                )
            )
        )

        assertFalse(empty.isActiveProfileReady)
        assertTrue(weightOnly.isActiveProfileReady)
        assertTrue(waistOnly.isActiveProfileReady)
    }

    @Test
    fun weeklyPlansBelongToTheirProfile() {
        val davidMeal = PlannedMeal(
            id = 100,
            type = MealType.BREAKFAST,
            days = WeekDay.entries.toSet(),
            items = listOf(PlannedFood(1, 100.0))
        )
        val data = AppData(
            profiles = listOf(
                ProfileData(david, plannedMeals = listOf(davidMeal)),
                ProfileData(araceli)
            ),
            activeProfileId = araceli.id
        )

        assertTrue(data.activeProfileData?.plannedMeals.isNullOrEmpty())
        assertEquals(listOf(davidMeal), data.profiles.first().plannedMeals)
    }

    @Test
    fun dishesAreSharedBetweenProfiles() {
        val dish = Dish(30, "Batido", listOf(DishIngredient(1, 250.0)))
        val data = AppData(
            profiles = listOf(ProfileData(david), ProfileData(araceli)),
            activeProfileId = david.id,
            dishes = listOf(dish)
        )

        assertEquals(listOf(dish), data.dishes)
        assertEquals(2, data.profiles.size)
    }
}
