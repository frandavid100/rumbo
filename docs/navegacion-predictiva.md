# Navegación predictiva

Rumbo usa una pila real de Navigation Compose. No se debe simular el retroceso
predictivo cambiando la pantalla actual desde `PredictiveBackHandler` ni
conservando manualmente composiciones salientes con temporizadores.

## Implementación

- Dependencia mínima: `androidx.navigation:navigation-compose:2.8.0`.
- Cada pantalla es un destino del `NavHost`.
- `popEnterTransition` dibuja el destino anterior durante el gesto.
- `popExitTransition` desvanece y reduce el destino actual.
- Navigation Compose controla el progreso, la cancelación y la confirmación
  mediante sus transiciones seekable.
- El retorno desde la búsqueda no añade otra transición, porque su propio
  componente ya anima el cierre.

## Referencias oficiales

- https://developer.android.com/develop/ui/compose/system/predictive-back-setup
- https://developer.android.com/guide/navigation/custom-back/support-animations
- https://developer.android.com/jetpack/androidx/releases/navigation

Si se añade un nuevo destino, debe incorporarse a la pila y utilizar las
transiciones del `NavHost`; no debe crearse otro manejador global del gesto.
