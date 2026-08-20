# Rumbo

Aplicación Android nativa y local para registrar peso, cintura y contexto dietético, y obtener una recomendación energética explicada.

## Qué hace esta versión

- Exige nombre, altura, año de nacimiento, sexo, peso, cintura y objetivo al crear cada perfil.
- Admite mediciones irregulares y registros con solo peso o solo cintura.
- Hereda la última actividad y el último objetivo cuando se dejan vacíos.
- Calcula una estimación inicial mediante Mifflin–St Jeor y un factor de actividad.
- Interpreta el IMC y la relación cintura/altura y los relaciona con el objetivo elegido.
- Representa la evolución del IMC y de cintura/altura en gráficas con franjas clínicas de color y fechas reales.
- Propone automáticamente un objetivo coherente con los últimos indicadores y explica el criterio aplicado.
- Permite varios perfiles con historiales completamente separados.
- Ordena Inicio como una secuencia: evolución corporal, objetivo recomendado, objetivo elegido, calorías/macros e historial.
- Organiza Inicio en tres tarjetas pulsables: situación corporal con objetivo y nutrición, menú de hoy y lista de la compra.
- Resume IMC y cintura/altura en una única escala de cinco franjas iguales; las gráficas y el historial quedan en la explicación detallada.
- Permite elegir «Automático» para que el objetivo aplicado siga siempre la recomendación corporal vigente.
- Muestra el cumplimiento diario de calorías y macros en una cuadrícula compacta de porcentajes con iconos y colores propios.
- Permite completar comidas ausentes y ajustar las cantidades del día directamente desde Inicio.
- Evita tarjetas y encabezados redundantes en Inicio; usa espacio y divisores para separar la información.
- Muestra un historial compacto; al tocar una entrada abre todos sus detalles y permite editarla o eliminarla.
- Añade una pestaña «Alimentos» con búsqueda por nombre, categoría, marca, comercio o EAN.
- Permite filtrar el catálogo por tipo nutricional y por comercio identificado.
- Añade un planificador semanal por perfil: cada comida se crea una vez y se asigna a varios días.
- Permite alternar entre el plan semanal, el de hoy y el de cualquier día concreto.
- Permite crear directamente cualquier comida ausente con su tipo y día ya seleccionados.
- Guarda ingredientes y cantidades, calcula los macros de cada comida e impide solapamientos del mismo tipo y día.
- Permite marcar cada alimento o plato como fijo o ajustable y definir para estos últimos un intervalo de gramos.
- Ajusta de forma explícita las cantidades variables para aproximar calorías y macros del día completo, mostrando una vista previa antes de guardar.
- Una comida puede reutilizarse durante la semana sin bloquear el ajuste: los elementos fijos conservan exactamente sus gramos y los ajustables se resuelven por día.
- Añade una pestaña «Platos» con combinaciones de ingredientes compartidas por todos los perfiles.
- Cada plato tiene una ficha con su composición nutricional total y por 100 g, y un icono según el macro que aporta más energía.
- Los platos se incorporan al plan y se reparten por gramos, no mediante raciones abstractas.
- Unifica la búsqueda de platos y alimentos al editar una comida.
- En los selectores aparecen primero los platos y alimentos que ya se utilizan en alguna comida o receta.
- Permite seleccionar varios alimentos de una comida y convertirlos inmediatamente en un plato reutilizable.
- Descompone los platos en sus ingredientes al calcular calorías, macros y lista de la compra.
- Compara calorías y macros de cada toma con el 20 % de la recomendación diaria y los totales de cada día con el 100 %.
- Distingue entre objetivo alcanzado, próximo, fuera de rango y plan incompleto, mostrando cada nutriente por separado.
- Calcula una lista de la compra semanal con los gramos acumulados de cada alimento planificado.
- Incluye los 52 alimentos iniciales y un catálogo compacto de productos de Mercadona con EAN y datos nutricionales completos.
- Excluye productos de otros comercios y fichas sin los cuatro valores necesarios para planificar menús.
- Muestra marca, familia, subcategoría, denominación legal, ingredientes, grasas saturadas, azúcares, sal, EAN y procedencia cuando figuran en la fuente.
- Identifica las referencias de Mercadona a partir de la marca o del fabricante declarados en AESAN.
- Permite consultar, crear, editar y eliminar alimentos; el catálogo es común a todos los perfiles.
- Conserva en las copias de seguridad las altas, ediciones y eliminaciones del usuario; el catálogo público ya viaja dentro de la aplicación y no se duplica en cada copia.
- Identifica cada categoría mediante un icono y un color estables.
- Admite hasta diez enlaces por alimento; todos los alimentos iniciales incluyen al menos un acceso a Mercadona.
- Propone hasta cinco sustitutos de la misma subcategoría culinaria cuando calorías y macros por 100 g son suficientemente próximos.
- Mantiene las explicaciones detalladas en pantallas separadas para simplificar la vista principal.
- Incluye un botón «Añadir medición» inequívoco en la tarjeta corporal y registra con fecha los cambios de objetivo.
- Explica el cálculo energético en lenguaje natural y con los límites realmente aplicados.
- Ajusta gradualmente la estimación cuando existen al menos 21 días de historial fiable.
- Usa peso y cintura como señales distintas; si se contradicen, mantiene y observa.
- Limita cada corrección a 150 kcal y aplica protecciones por IMC y cintura/altura.
- Calcula proteína, hidratos y grasa a partir de la recomendación actual.
- Exporta e importa todos los datos en JSON.
- No usa Internet, cuentas, anuncios ni analítica.
- Respeta el gesto Atrás en las pantallas secundarias y mantiene fluida la búsqueda del catálogo mediante un índice precalculado y consulta diferida.

## Compilar

Requisitos: Android Studio compatible con AGP 8.13, JDK 17 y Android SDK 36.

1. Abre esta carpeta en Android Studio.
2. Deja que Android Studio sincronice Gradle e instale el SDK solicitado.
3. Ejecuta la configuración `app` o usa `./gradlew assembleDebug`.

El APK de depuración se genera en `app/build/outputs/apk/debug/app-debug.apk`.

## Regenerar el catálogo de Mercadona

El APK publicado incluye un subconjunto nutricional de Mercadona. El repositorio
no versiona esa copia generada: para crearla desde el libro oficial de AESAN:

1. Instala Python 3 y ejecuta `python3 -m pip install -r tools/requirements.txt`.
2. Ejecuta `python3 tools/import_aesan.py` desde la raíz del proyecto.

El importador descarga el libro oficial, conserva un registro completo por EAN
solo cuando la marca o el fabricante permiten atribuirlo a Mercadona y no modifica
los valores nutricionales publicados. Debe ejecutarse antes de compilar una copia
recién clonada del repositorio.

## Construir el catálogo genérico de BEDCA

El catálogo de desarrollo se construye fuera de la aplicación y no se versiona:

```bash
python3 tools/build_bedca_catalog.py \
  --output build/catalog/bedca/rumbo-bedca-development.rumbocatalog \
  --report build/catalog/bedca/report.json
python3 tools/validate_catalog.py \
  build/catalog/bedca/rumbo-bedca-development.rumbocatalog \
  --json build/catalog/bedca/validation.json
```

La descarga es reanudable. El SQLite conserva las observaciones de nutrientes,
normaliza los campos necesarios para Rumbo y separa clasificación, familia
alimentaria, base física de porción y elegibilidad. No debe incorporarse a un
APK público mientras no se aclaren los derechos de redistribución de BEDCA.

Los archivos `.rumbocatalog` declaran `catalog_format`, `catalog_format_version`,
`schema_version`, un `catalog_id` estable, una `catalog_version` y un
`product_id_namespace`. Catálogos con identidades distintas se combinan; al
importar otra versión con el mismo `catalog_id`, Rumbo reemplaza la anterior de
forma atómica. Cada espacio de productos solo puede pertenecer a un catálogo
instalado, evitando colisiones silenciosas entre fuentes.
El contrato completo está en [`docs/CATALOG_FORMAT.md`](docs/CATALOG_FORMAT.md).

## Criterio de cálculo

La estimación base usa Mifflin–St Jeor y el nivel de actividad. Los objetivos representan ritmos relativos y prudentes, no un número libre de kilos por semana. La app bloquea un déficit con IMC ≤ 18,5 y un superávit cuando el IMC o la relación cintura/altura indican que no es razonable recomendarlo automáticamente.

El ajuste histórico requiere cuatro pesos, 21 días de intervalo y al menos tres valoraciones de cumplimiento cercanas a «aproximadamente lo previsto». La pendiente se obtiene mediante regresión lineal usando las fechas reales. Si peso y cintura dan señales relevantes en sentidos opuestos, no cambia la recomendación.

Esta aplicación ofrece una estimación orientativa, no sustituye una valoración sanitaria individual.

En el planificador, el ajuste por comida es un objetivo práctico: cada una de las cinco tomas recibe el 20 % de la recomendación diaria. Verde significa una desviación máxima del 10 %, amarillo hasta el 20 % y rojo una desviación superior. Esta comparación solo evalúa energía y macronutrientes; no certifica por sí sola la calidad nutricional completa de una comida.

El ajuste automático de gramos se inicia únicamente al pulsar «Ajustar cantidades». Optimiza cada día completo dando prioridad a energía y proteína, mantiene la grasa dentro de un margen razonable y utiliza los hidratos como componente más flexible. Nunca modifica elementos fijos ni rebasa los mínimos y máximos indicados; si no existe una solución exacta, presenta la combinación más próxima para que el usuario decida si la aplica.

## Licencia

GPL-3.0-only. El código puede estudiarse, modificarse y redistribuirse conforme a esa licencia.
