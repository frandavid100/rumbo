from pathlib import Path
p=Path('app/src/main/java/es/david/rumbo/logic/CulinarilySatisfactoryWitnessRepair.kt')
t=p.read_text()
old='''                        sourceIndex?.let { index ->
                            val sourceId = originalMeal.items[index].foodId
                            if (!isMandatory(sourceId, originalMeal.type, activeRules)) {
                                val items = originalMeal.items.toMutableList().also { it.removeAt(index) }
                                if (items.isNotEmpty() || originalMeal.dishes.isNotEmpty()) {
                                    add(replaceMeal(witness, mealIndex, originalMeal.copy(items = items)))
                                }
                            }
                        }

                        val existingIds = originalMeal.items.mapTo(mutableSetOf()) { it.foodId }
'''
new='''                        sourceIndex?.let { index ->
                            val sourceId = originalMeal.items[index].foodId
                            if (!isMandatory(sourceId, originalMeal.type, activeRules)) {
                                val items = originalMeal.items.toMutableList().also { it.removeAt(index) }
                                if (items.isNotEmpty() || originalMeal.dishes.isNotEmpty()) {
                                    add(replaceMeal(witness, mealIndex, originalMeal.copy(items = items)))
                                }

                                // Preserve nutritional contribution when possible by
                                // relocating an optional modifier to a meal where its
                                // preferred vehicle already exists. This is especially
                                // useful for oil inherited in a fruit snack.
                                val sourceItem = originalMeal.items[index]
                                val sourceAllowedMeals = activeRules
                                    .filter { it.itemId == sourceId }
                                    .flatMapTo(mutableSetOf()) { it.allowedMealTypes }
                                witness.meals.indices
                                    .filter { it != mealIndex }
                                    .forEach destinationLoop@ { destinationIndex ->
                                        val destination = materialize(
                                            witness.meals[destinationIndex], witness.day
                                        )
                                        if (destination.type !in sourceAllowedMeals) return@destinationLoop
                                        if (destination.items.any { it.foodId == sourceId }) return@destinationLoop
                                        val hasPreferredVehicle = destination.items.any { planned ->
                                            foodsById[planned.foodId]?.let(CulinaryPolicy::roles)
                                                ?.any(targetRoles::contains) == true
                                        } || destination.dishes.any { plannedDish ->
                                            dishesById[plannedDish.dishId]?.ingredients.orEmpty().any { ingredient ->
                                                foodsById[ingredient.foodId]?.let(CulinaryPolicy::roles)
                                                    ?.any(targetRoles::contains) == true
                                            }
                                        }
                                        if (!hasPreferredVehicle) return@destinationLoop

                                        val sourceWithout = originalMeal.copy(
                                            items = originalMeal.items.toMutableList().also {
                                                it.removeAt(index)
                                            }
                                        )
                                        val maximum = maximumItems(destination.type)
                                        if (destination.items.size + destination.dishes.size < maximum) {
                                            val meals = witness.meals.toMutableList()
                                            meals[mealIndex] = sourceWithout
                                            meals[destinationIndex] = destination.copy(
                                                items = destination.items + sourceItem
                                            )
                                            add(witness.copy(meals = meals, fingerprint = meals.hashCode()))
                                        } else {
                                            destination.items.indices.forEach replacementLoop@ { replaceIndex ->
                                                val replacedId = destination.items[replaceIndex].foodId
                                                if (isMandatory(
                                                        replacedId, destination.type, activeRules
                                                    )
                                                ) return@replacementLoop
                                                val destinationItems = destination.items.toMutableList().also {
                                                    it[replaceIndex] = sourceItem
                                                }
                                                val meals = witness.meals.toMutableList()
                                                meals[mealIndex] = sourceWithout
                                                meals[destinationIndex] = destination.copy(items = destinationItems)
                                                add(witness.copy(meals = meals, fingerprint = meals.hashCode()))
                                            }
                                        }
                                    }
                            }
                        }

                        val existingIds = originalMeal.items.mapTo(mutableSetOf()) { it.foodId }
'''
if t.count(old)!=1: raise SystemExit(f'block count {t.count(old)}')
p.write_text(t.replace(old,new,1))
print('Reubicación de auxiliares añadida')
