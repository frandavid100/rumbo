# Política de porciones `GENERAL_ADULT` v2

Estado: calibración inicial conservadora para el nivel 3. No es una prescripción clínica ni sustituye al modelo nutricional.

## Principio

Rumbo separa cuatro piezas:

1. el modelo nutricional calcula objetivos diarios y por comida;
2. el producto aporta una **base física de porción** (`portionBasisGrams`) independiente del usuario;
3. el rol culinario indica cómo transformar esa base —o una referencia funcional propia del rol— en una cantidad para el uso concreto;
4. el optimizador escoge la cantidad final dentro del espacio permitido.

Sexo, edad, altura y peso no entran directamente en `PortionPolicyResolver`. Su efecto llega a través de los objetivos nutricionales y de `mealShares`.

## Por qué no basta un gramaje universal por rol

El catálogo Carrefour provisional muestra productos con el mismo rol y escalas físicas legítimamente diferentes. Entre los `PLATE_BASE` actuales aparecen, por ejemplo:

- arroz y pasta secos: referencia provisional 80 g;
- pan: 70 g;
- legumbres y cereales ya cocidos: 180 g;
- almidones frescos: 250 g.

Por tanto, `PLATE_BASE = 50–120 g` no puede ser una verdad del rol: funcionaría para arroz seco pero convertiría una ración normal de patata en un falso defecto culinario. Lo mismo ocurre con `STANDALONE`, que puede representar desde queso o frutos secos hasta fruta, yogur o una bebida.

La antigua columna `preferred_grams` del SQLite se usa temporalmente como puente para poblar `portionBasisGrams`. El formato canónico futuro debe publicar `portion_basis_grams` de forma explícita y con evidencia propia. `culinary_type` no reaparece como taxonomía.

## Modos de referencia

### `PRODUCT_BASIS`

Se usa cuando la escala normal depende de la forma física del producto. La referencia preferida parte de `portionBasisGrams`; si falta en un alimento legado, se usa el valor histórico del rol como fallback explícito.

Roles v2: `PLATE_CENTER`, `PLATE_BASE`, `SIDE`, `CEREAL_BASE`, `POWDER_BASE`, `SANDWICH_BASE`, `STANDALONE`, `BEVERAGE`, `DESSERT`.

### `ROLE_DEFAULT`

Se usa cuando la función culinaria define por sí misma una cantidad bastante estable y la porción habitual del producto no debe dominarla.

Roles v2: `TOPPING`, `SAUCE_DRESSING`, `CEREAL_MIX_IN`, `POWDER_MIX_IN`, `SANDWICH_FILLING`, `SPREAD`, `COOKING_MEDIUM`, `BINDER`, `COATING`, `SEASONING`.

## Contextualización energética

`scale = clamp((mealEnergy / referenceMealEnergy)^elasticity, minScale, maxScale)`

`effectivePreferred = referenceGrams × scale`

La zona satisfactoria se expresa mediante factores alrededor de `referenceGrams` y se desplaza con el mismo `scale`. En esta migración se recorta a los límites duros históricos de `CulinaryPolicy`; dichos límites no se cambian todavía para no invalidar niveles 1–2 ya certificados.

A 2000 kcal y con la distribución de comidas de referencia, `scale = 1`.

## Calibración v2

| Rol | Referencia | Factor satisfactorio min–max | Elasticidad | Escala contextual |
|---|---|---:|---:|---:|
| PLATE_CENTER | producto | 0.50–1.50 | 0.35 | 0.75–1.35 |
| PLATE_BASE | producto | 0.625–1.50 | 0.50 | 0.70–1.50 |
| SIDE | producto | 0.50–1.25 | 0.15 | 0.85–1.25 |
| TOPPING | rol (20 g) | 0.25–2.00 | 0.00 | 1.00–1.00 |
| SAUCE_DRESSING | rol (30 g) | 0.33–2.00 | 0.10 | 0.85–1.15 |
| CEREAL_BASE | producto | 0.75–1.50 | 0.15 | 0.85–1.20 |
| CEREAL_MIX_IN | rol (50 g) | 0.50–1.40 | 0.35 | 0.75–1.35 |
| POWDER_BASE | producto | 0.72–1.40 | 0.10 | 0.90–1.15 |
| POWDER_MIX_IN | rol (30 g) | 0.67–1.33 | 0.10 | 0.90–1.15 |
| SANDWICH_BASE | producto | 0.60–1.50 | 0.35 | 0.75–1.35 |
| SANDWICH_FILLING | rol (60 g) | 0.50–1.67 | 0.25 | 0.80–1.25 |
| SPREAD | rol (25 g) | 0.20–1.60 | 0.05 | 0.90–1.10 |
| COOKING_MEDIUM | rol (10 g) | 0.50–1.50 | 0.00 | 1.00–1.00 |
| BINDER | rol (20 g) | 0.50–2.00 | 0.00 | 1.00–1.00 |
| COATING | rol (30 g) | 0.50–1.67 | 0.10 | 0.90–1.15 |
| SEASONING | rol (3 g) | 0.17–3.33 | 0.00 | 1.00–1.00 |
| STANDALONE | producto | 0.50–1.50 | 0.10 | 0.85–1.20 |
| BEVERAGE | producto | 0.60–1.60 | 0.10 | 0.90–1.15 |
| DESSERT | producto | 0.50–1.50 | 0.10 | 0.90–1.15 |

Estos factores son parámetros versionados de ingeniería y deberán recalibrarse con el conjunto dorado y casos reales.

## Relaciones estructurales de nivel 3 añadidas

Además de las relaciones ya definidas, v2 incluye:

`COOKING_MEDIUM → PREFER ANY_OF {PLATE_CENTER, PLATE_BASE, SIDE}`

Así, aceite junto a fruta y zumo puede seguir siendo una composición dura utilizable en niveles inferiores, pero no se certifica como culinariamente satisfactoria por el mero hecho de contener varios alimentos.

## Evidencia externa utilizada

AESAN varía el número de raciones de grupos como cereales según necesidades energéticas y distribuye la energía diaria por comidas. Las guías australianas usan `standard serves` relativamente estables y ajustan el número de serves por persona. Ambas ideas apoyan que las características físicas actúen primero sobre objetivos nutricionales y que la porción individual solo tenga una elasticidad acotada.

- AESAN: https://www.aesan.gob.es/AECOSAN/web/noticias_y_actualizaciones/noticias/2022/recomendaciones_dieteticas.htm
- AESAN, distribución por comidas: https://www.aesan.gob.es/AECOSAN/web/nutricion/campanyas/NoTeLoPuedesSaltar.htm
- Australian Eat for Health: https://www.eatforhealth.gov.au/food-essentials/how-much-do-we-need-each-day/serve-sizes

Para peso seco, documentación sanitaria británica sitúa una ración práctica de arroz/pasta secos alrededor de 75 g, coherente con la base provisional de 80 g del catálogo actual:

- https://www.whittington.nhs.uk/default.asp?c=35962&print=1

## Pendientes explícitos

- Los límites duros siguen siendo los históricos del rol durante esta migración; normalizarlos también por base física requiere una migración separada.
- Productos de infusión/filtrado o dilución en los que no se ingiere toda la masa vendida no deben tratarse como una bebida ordinaria hasta modelar la conversión de preparación; el importador debe enviarlos a revisión cuando corresponda.
- Una excepción producto+rol solo se justifica si la combinación base física + política común no representa el uso real.
