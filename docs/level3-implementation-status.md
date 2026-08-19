# Estado de implementación del nivel 3

Fase actual: integración funcional validada por CI; pendiente validación visible en móvil antes de fusionar.

Implementado:

- política de porciones `GENERAL_ADULT` con base física por producto y elasticidad energética acotada;
- migración compatible de `portionBasisGrams` y copias de seguridad esquema 25;
- asignación del rol realmente desempeñado por cada ocurrencia;
- relaciones estructurales `PREFER` centralizadas;
- evaluación `CULINARILY_SATISFACTORY` sobre un día `COMPLETE`;
- conjunto dorado de comidas y testigo constructivo independiente de Ara;
- reparación determinista incremental `COMPLETE → CULINARILY_SATISFACTORY`;
- reubicación de auxiliares opcionales —por ejemplo aceite heredado en una merienda— hacia comidas donde exista un vehículo culinario compatible, conservando su contribución nutricional cuando sea posible;
- búsqueda determinista de composiciones con intervalos satisfactorios y optimización final de cantidades;
- búsqueda previa en shortlists deterministas para que repertorios grandes no oculten soluciones válidas entre alternativas equivalentes; cualquier solución se revalida contra todas las reglas antes de certificarla;
- selección de shortlists tanto por capacidad nutricional como por diversidad de funciones culinarias;
- `SEARCH_INCONCLUSIVE` se conserva como estado no probatorio;
- persistencia/revalidación del testigo de nivel 3 en la pantalla principal;
- estado explícito de búsqueda para los niveles 2 y 3, sin CTA prescriptivo mientras la búsqueda está en curso;
- eliminación del fallback genérico «Añadir otra verdura» cuando la búsqueda de nivel 2 solo es inconclusa;
- diagnósticos culinarios causales: las dependencias duras conservan el alimento que las origina y un alimento multirrol no provoca una petición falsa de acompañante;
- una carencia `PREFER` solo se expone como accionable si la ocurrencia que la causa es obligatoria y no existe una reasignación funcional que la evite;
- el resultado de una búsqueda acotada de nivel 2 no se interpreta como prueba de falta de fibra;
- recuperación interna de un testigo `VIABLE` fresco cuando no existe un testigo persistido válido, para que la corrección del nivel 2 no dependa del orden de recomposición de la interfaz;
- regresión real de Ara con 24 reglas: encuentra y certifica nivel 3;
- regresión real del perfil 3 con 27 reglas y su testigo `COMPLETE`: mantiene el contrato y encuentra nivel 3;
- CI Android y CI con catálogo Carrefour superadas para ambos casos reales.

Pendiente antes de cerrar el PR:

- ejecutar la CI final de Rumbo 0.76.0 tras la limpieza de diagnósticos;
- generar el APK firmado de prueba;
- validar en móvil que los estados de búsqueda, nivel 3 y explicaciones causales se muestran correctamente;
- mantener el PR en borrador hasta esa validación visible.
