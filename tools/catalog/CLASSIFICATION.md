# Clasificación canónica del catálogo

Estado: decisiones de implementación de la fase 1, 17 de agosto de 2026.

## Regla de aceptación

`CLASSIFIED` no significa «se ha asignado una categoría». Solo es verdadero cuando el producto tiene un tipo culinario reconocido, sus roles culinarios pertinentes, los roles nutricionales pertinentes (que pueden ser ninguno cuando el aporte sea incidental), nutrición básica completa, relaciones e invariantes coherentes y ninguna causa abierta de revisión. `MENU_ELIGIBLE` exige además que la nutrición sea utilizable.

Cada asignación almacena confianza, `rule_id`, evidencia y versión del clasificador. Un cambio de versión reclasifica el catálogo completo.

## Roles nutricionales

Se usan los ocho roles autorizados: `PRIMARY_PROTEIN`, `COMPLEMENTARY_PROTEIN`, `PRIMARY_CARBOHYDRATE`, `COMPLEMENTARY_CARBOHYDRATE`, `CONCENTRATED_FAT`, `COMPLEMENTARY_FAT`, `VEGETABLE` y `FRUIT`.

Los roles primarios o semánticos se asignan por tipo cuando ese tipo define la función nutricional del alimento. Los roles complementarios se evalúan sobre la ración de política, nunca únicamente por 100 g.

Umbrales calibrados de fase 1 por ración de política:

- proteína complementaria: al menos 5 g;
- hidratos complementarios: al menos 10 g;
- grasa complementaria: al menos 5 g.

No se asigna el rol complementario de un nutriente cuando el alimento ya tiene el rol primario de ese mismo nutriente. Un alimento correctamente clasificado puede tener cero roles nutricionales si sus aportes son incidentales para su función culinaria (por ejemplo, una salsa ligera o cacao usado como ingrediente).

## Tipos y roles culinarios

El tipo es una familia operativa estable que selecciona ración y política; no sustituye a los roles múltiples. La taxonomía de fase 1 incluye bases líquidas y cremosas, cereales de desayuno, proteína y cacao en polvo, arroz/pasta/almidones, pan, legumbres, queso, proteínas principales, verdura, fruta, aceite, complementos grasos, salsas e ingredientes de cocina.

Los roles culinarios son independientes y múltiples. Las relaciones `REQUIRE` y `FORBID` son duras cuando expresan imposibilidad culinaria, por ejemplo:

- `CEREAL_MIX_IN` requiere `CEREAL_BASE`;
- `POWDER_MIX_IN` requiere `POWDER_BASE`;
- `SANDWICH_FILLING` requiere `SANDWICH_BASE`;
- `TOPPING`, `SAUCE_DRESSING`, `COOKING_MEDIUM`, `BINDER`, `COATING` y `SEASONING` no pueden aparecer solos.

## Conjunto dorado

Debe bloquear regresiones en, como mínimo: queso, frutos secos, legumbres, yogur y multipack, pan, cereal, cacao, proteína en polvo, aceite, salsa, alimentos frescos y preparados ambiguos. También contiene pruebas de frontera de los umbrales y de las relaciones duras.

Los preparados cuyo tipo no pueda inferirse con alta confianza no se fuerzan a una categoría: entran en `review_queue` y no son `MENU_ELIGIBLE` hasta resolverse.

## Principio de calibración

Los umbrales son parámetros de Rumbo, no hechos extraídos de una fuente externa. Cualquier cambio debe:

1. incrementar la versión del clasificador;
2. justificar qué casos corrige;
3. mantener o ampliar el conjunto dorado;
4. ejecutar una reclasificación completa;
5. enviar a revisión cualquier conflicto nuevo en vez de resolverlo silenciosamente.
