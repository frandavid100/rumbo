# Política de porciones `GENERAL_ADULT` v1

Estado: calibración inicial conservadora para el nivel 3. No es una prescripción clínica ni sustituye al modelo nutricional.

## Principio

Rumbo separa tres capas:

1. el modelo nutricional calcula objetivos diarios y por comida a partir del perfil y del contexto nutricional;
2. la política culinaria fija qué cantidades son utilizables y qué cantidades resultan culinariamente satisfactorias para el rol desempeñado;
3. el optimizador escoge, dentro de esos dominios, la cantidad que mejor satisface el objetivo nutricional.

Sexo, edad, altura y peso no entran directamente en `PortionPolicyResolver`. Si afectan a la energía o a los macronutrientes objetivo, su efecto ya llega a través de `Recommendation` y `mealShares`.

## Evidencia utilizada

### AESAN, población española

Las recomendaciones dietéticas de AESAN para población general usan frecuencias/raciones por grupos y hacen depender expresamente el número de raciones de cereales de las necesidades energéticas: 3–6 raciones, con un máximo menor cuando se necesita restringir la ingesta. Esto apoya tratar el aumento de energía principalmente como mayor disponibilidad de raciones/composición y solo secundariamente como escalado de una porción concreta.

Fuente: https://www.aesan.gob.es/AECOSAN/web/noticias_y_actualizaciones/noticias/2022/recomendaciones_dieteticas.htm

AESAN también distribuye la energía diaria entre comidas como porcentajes del total, lo que justifica usar el objetivo energético de la comida como contexto y no el peso corporal directamente.

Fuente: https://www.aesan.gob.es/AECOSAN/web/nutricion/campanyas/NoTeLoPuedesSaltar.htm

### Australian Dietary Guidelines / Eat for Health

La guía oficial australiana define `standard serves` estables y concretos, entre ellos:

- 40 g de pan;
- 75–120 g de arroz/pasta/cereal cocido;
- 65 g de carne roja magra cocida;
- 80 g de ave cocida;
- 100 g de pescado cocido.

Las tablas de necesidades diarias varían el número de serves por sexo/edad y permiten serves adicionales para personas más altas o activas. Es una señal fuerte contra multiplicar linealmente cada porción por peso o talla.

Fuente: https://www.eatforhealth.gov.au/food-essentials/how-much-do-we-need-each-day/serve-sizes

## Decisiones de ingeniería v1

Los límites duros existentes de `CulinaryPolicy` no se estrechan en esta fase. El nivel 3 añade una zona satisfactoria interior para roles donde la evidencia culinaria permite distinguir una cantidad central razonable sin asumir precisión clínica.

La contextualización utiliza:

`scale = clamp((mealEnergy / referenceMealEnergy)^elasticity, minScale, maxScale)`

con `referenceDailyCalories = 2000 kcal` y la distribución de comidas por defecto. A 2000 kcal con la distribución de referencia, `scale = 1` y `effectivePreferred = basePreferred`.

Los límites duros `minimum..maximum` nunca escalan. Escalan únicamente el intervalo satisfactorio base y la preferencia efectiva, siempre recortados dentro del dominio duro.

### Elasticidad

- alta/moderada: bases de plato y otros componentes que pueden absorber una parte material de una mayor necesidad energética;
- baja: centro de plato, acompañamientos, bebidas y postres;
- casi nula o nula: aceite/medio de cocción, condimentos, toppings, untables y otros componentes cuya cantidad no debe crecer proporcionalmente con la energía total.

### Rol `STANDALONE`

`STANDALONE` incluye alimentos demasiado heterogéneos en densidad y forma —por ejemplo fruta, yogur, frutos secos y otros snacks— para imponer un único intervalo satisfactorio en gramos sin crear falsos negativos. En v1 su intervalo satisfactorio coincide deliberadamente con su dominio duro. Si la experiencia real demuestra que esto es demasiado permisivo, la solución correcta será introducir una propiedad de porción más específica o una excepción de producto, no forzar un gramaje universal para el rol.

## Tabla de calibración v1

| Rol | Zona satisfactoria base (g) | Elasticidad | Escala min–max |
|---|---:|---:|---:|
| PLATE_CENTER | 75–225 | 0.35 | 0.75–1.35 |
| PLATE_BASE | 75–220 | 0.50 | 0.70–1.50 |
| SIDE | 75–250 | 0.15 | 0.85–1.25 |
| TOPPING | 5–40 | 0.00 | 1.00–1.00 |
| SAUCE_DRESSING | 10–60 | 0.10 | 0.85–1.15 |
| CEREAL_BASE | 150–300 | 0.15 | 0.85–1.20 |
| CEREAL_MIX_IN | 25–70 | 0.35 | 0.75–1.35 |
| POWDER_BASE | 180–350 | 0.10 | 0.90–1.15 |
| POWDER_MIX_IN | 20–40 | 0.10 | 0.90–1.15 |
| SANDWICH_BASE | 40–120 | 0.35 | 0.75–1.35 |
| SANDWICH_FILLING | 30–100 | 0.25 | 0.80–1.25 |
| SPREAD | 5–40 | 0.05 | 0.90–1.10 |
| COOKING_MEDIUM | 5–15 | 0.00 | 1.00–1.00 |
| BINDER | 10–40 | 0.00 | 1.00–1.00 |
| COATING | 15–50 | 0.10 | 0.90–1.15 |
| SEASONING | 0.5–10 | 0.00 | 1.00–1.00 |
| STANDALONE | 20–300 | 0.00 | 1.00–1.00 |
| BEVERAGE | 150–400 | 0.10 | 0.90–1.15 |
| DESSERT | 80–200 | 0.10 | 0.90–1.15 |

Estos intervalos son parámetros de producto versionados. Deben validarse con un conjunto dorado de comidas y con casos reales antes de considerarlos estables.

## Criterio de revisión

Una calibración v1 se considera aceptable si:

- no cambia la validez de niveles 1–2;
- no obliga a una cantidad única dentro de una comida razonable;
- detecta como no satisfactoria una cantidad deliberadamente extrema en roles homogéneos;
- no penaliza `STANDALONE` por una diversidad de gramajes que el rol no puede representar por sí solo;
- aumentar la energía mueve la preferencia solo en roles con elasticidad positiva;
- ninguna personalización modifica los límites duros.
