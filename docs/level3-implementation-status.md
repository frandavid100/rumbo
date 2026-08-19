# Estado de implementación del nivel 3

Fase actual: integración funcional en borrador.

Implementado:

- política de porciones `GENERAL_ADULT` con base física por producto y elasticidad energética acotada;
- migración compatible de `portionBasisGrams` y copias de seguridad esquema 25;
- asignación del rol realmente desempeñado por cada ocurrencia;
- relaciones estructurales `PREFER` centralizadas;
- evaluación `CULINARILY_SATISFACTORY` sobre un día `COMPLETE`;
- conjunto dorado de comidas;
- reparación determinista incremental `COMPLETE → CULINARILY_SATISFACTORY`;
- exploración de fallback que conserva `SEARCH_INCONCLUSIVE` como estado no probatorio;
- persistencia/revalidación del testigo de nivel 3 en la pantalla principal;
- estado explícito de búsqueda para los niveles 2 y 3, sin CTA prescriptivo mientras la búsqueda está en curso;
- eliminación del fallback genérico «Añadir otra verdura» cuando la búsqueda de nivel 2 solo es inconclusa.

Pendiente antes de cerrar el PR:

- CI completa de la integración de interfaz;
- regresión con los perfiles reales Ara y 3 sobre el catálogo Carrefour empaquetado;
- revisar los diagnósticos resultantes y recalibrar únicamente donde los casos reales aporten evidencia;
- generar APK de prueba y validar el comportamiento visible.
