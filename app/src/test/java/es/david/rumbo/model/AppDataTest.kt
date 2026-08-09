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
    fun profileIsReadyOnlyWithWeightWaistAndExplicitGoal() {
        val incomplete = AppData(
            profiles = listOf(
                ProfileData(
                    david,
                    listOf(Measurement(10, LocalDate.of(2026, 8, 8), weightKg = 83.4, waistCm = 91.0))
                )
            ),
            activeProfileId = david.id
        )
        val complete = incomplete.copy(
            profiles = listOf(
                ProfileData(
                    david,
                    incomplete.measurements + Measurement(
                        11,
                        LocalDate.of(2026, 8, 8),
                        goal = WeightGoal.LOSE_SLOWLY
                    )
                )
            )
        )

        assertFalse(incomplete.isActiveProfileReady)
        assertTrue(complete.isActiveProfileReady)
    }
}
