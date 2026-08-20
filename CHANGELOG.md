# Historial de cambios

## 0.42.0

- Interpreta calorías y macronutrientes mediante tolerancias propias y evita perseguir el 100 % exacto.
- Comparte la misma valoración entre el optimizador y la interfaz, con zonas óptimas sin penalización.
- Muestra cantidades reales y explicaciones semánticas en lugar de porcentajes como juicio principal.
- Programa únicamente alimentos y deriva automáticamente los platos que pueden satisfacer esas preferencias.
- Reparte el peso de cada alimento entre su uso directo y las recetas compatibles sin inflar su frecuencia.
- Permite que un plato satisfaga varias reglas fijas sin duplicar después sus ingredientes.

## 0.41.0

- Elimina las cantidades bloqueadas y los candados de alimentos: una presencia fija ya no fija sus gramos.
- Permite omitir almuerzo y merienda asignándoles un 0 % de las calorías.
- Hace reproducible la compilación con una copia local verificable del catálogo nutricional de Mercadona.

## 0.40.0

- Construye cada comida desde sus cantidades fijas y comprueba el margen restante antes de añadir otros elementos.
- Permite comidas de un solo elemento cuando cualquier añadido empeoraría el ajuste.
- Descarta alimentos cuya cantidad mínima rebase el límite calórico de la comida.
- Rechaza semanas que superen gravemente los objetivos diarios en vez de presentar la combinación menos mala.

## 0.39.0

- Bloquea definitivamente las proporciones de los ingredientes de cada plato una vez creado; al variar su cantidad, todos escalan juntos.
- Retira de la interfaz el editor manual de comidas y las acciones para añadir o modificar elementos directamente en ellas.
- Señala con un candado todas las cantidades fijadas por el usuario en el menú diario y semanal.
- Evita que eliminar un alimento modifique silenciosamente la receta de un plato.

## 0.38.0

- Sustituye el catálogo general de unos 29.000 productos por un subconjunto compacto de Mercadona con información nutricional completa.
- Pregunta durante la creación del perfil cómo se distribuirán las calorías entre las cinco comidas.
- Mueve el selector de perfil al lado izquierdo de la barra superior y lo representa mediante color e inicial.
- Corrige el título y la posición de la valoración nutricional de «Menú de hoy».

## 0.18.0

- Situación corporal, objetivo y recomendación nutricional reunidos en una sola tarjeta.
- Texto contextual distinto para el objetivo automático recomendado y para una elección manual.
- Acciones «Añadir medición» y «Cambiar objetivo» alineadas al pie de la tarjeta.
- Acceso a la explicación del cálculo nutricional desde la pantalla detallada conjunta.

## 0.17.0

- Separadores sutiles y jerarquía tipográfica Material 3 en todas las tarjetas de Inicio.
- Objetivo diario presentado como explicación breve y cuatro métricas con iconos y colores propios.
- Selector de objetivo trasladado a un botón explícito dentro de su tarjeta.
- Menú de hoy resumido en dos filas de porcentajes, sin barras de progreso.
- Acceso directo para completar comidas ausentes y valoración textual del ajuste nutricional diario.
- Ajuste de cantidades del día iniciado directamente desde Inicio.

## 0.16.0

- Cantidades fijas o ajustables en cada alimento y plato, con límites mínimo y máximo.
- Ajuste explícito de cantidades a partir del total nutricional de cada día, con vista previa antes de aplicar.
- Cantidades ajustables independientes por día aunque la comida se reutilice; las fijas permanecen idénticas.
- Lista de la compra y vistas diarias actualizadas con los gramos realmente resueltos para cada día.
- Inicio más claro: botón «Añadir medición» dentro de la primera tarjeta, barras compactas y compra resumida.

## 0.15.0

- Inicio reorganizado en cuatro tarjetas pulsables: situación corporal, objetivos, menú de hoy y compra.
- Escala corporal con cinco franjas de la misma anchura y recomendación resumida en una frase.
- Nuevo objetivo automático que sigue la recomendación corporal vigente en cada medición.
- Barras diarias de calorías, proteína, hidratos y grasa en el menú de hoy.

## 0.14.0

- Buscadores contextuales que priorizan alimentos y platos ya utilizados.
- Ficha de cada plato con información nutricional total y por 100 g.
- Iconos de proteína, carbohidrato o grasa según el macro predominante del plato.
- Cantidades de los platos expresadas y almacenadas en gramos, con migración automática de las raciones anteriores.

## 0.13.0

- Inicio reorganizado con una única escala conjunta de IMC y cintura/altura.
- Objetivo recomendado con variación semanal, recomendación energética, plan de hoy y compra semanal.
- Gráficas corporales e historial trasladados a la explicación detallada.
- Selector único de platos y alimentos en las comidas.
- Creación directa de platos a partir de varios alimentos seleccionados.
- Corrección del gesto Atrás y optimización del buscador de alimentos.

## 0.12.0

- Botón para añadir directamente las comidas ausentes de un día.
- Biblioteca común de platos con ingredientes y cantidades por ración.
- Platos reutilizables en cualquier perfil y visibles como un solo elemento del plan.
- Raciones configurables por persona y expansión automática en nutrición y lista de la compra.

## 0.11.0

- Vistas del plan semanal, de hoy y de un día elegido.
- Comprobación de calorías y macros por comida y por día completo.
- Indicadores por nutriente con márgenes explícitos respecto al objetivo.
- Ingredientes del plan en filas separadas con iconos de categoría.
- Lista de la compra semanal con cantidades totales.

## 0.10.0

- Planificador semanal independiente para cada perfil.
- Comidas reutilizables en varios días, con ingredientes y cantidades.
- Cálculo nutricional por comida y control de solapamientos.
- Filtros del catálogo por tipo nutricional y comercio.
- Compilación y pruebas automáticas en GitHub.

## 0.9.0

- Importación del catálogo público AESAN 2022.
- Búsqueda por nombre, marca, categoría, comercio y EAN.
- Sugerencias de alimentos con composición similar.
# 0.77.0

- Añade importación, listado y eliminación de catálogos `.rumbocatalog` desde Ajustes.
- Permite combinar varios catálogos genéricos o comerciales sin exigir publicaciones de supermercado.
- Incorpora el pipeline reproducible de BEDCA y sus validaciones, sin empaquetar sus datos en el APK.
- Retira del proceso de compilación los catálogos provisionales de Carrefour y AESAN/Mercadona.
