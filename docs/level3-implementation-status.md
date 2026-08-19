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
- reubicación de auxiliares opcionales —por ejemplo aceite heredado en una merienda— hacia comidas donde exista un vehículo culinario compatible, conservando su contribución nutricional cuando sea posible;
- exploración de fallback acotada: se repara el testigo persistido, se exploran candidatos y solo se repara en profundidad el mejor candidato adicional;
- `SEARCH_INCONCLUSIVE` se conserva como estado no probatorio;
- persistencia/revalidación del testigo de nivel 3 en la pantalla principal;
- estado explícito de búsqueda para los niveles 2 y 3, sin CTA prescriptivo mientras la búsqueda está en curso;
- eliminación del fallback genérico «Añadir otra verdura» cuando la búsqueda de nivel 2 solo es inconclusa;
- regresión de Ara ampliada con las bases físicas del catálogo Carrefour provisional y búsqueda de nivel 3.

Pendiente antes de cerrar el PR:

- CI completa de la integración de interfaz y de la regresión de Ara tras la reubicación de auxiliares;
- añadir/validar la regresión del perfil 3 si Ara supera el contrato;
- revisar los diagnósticos resultantes y recalibrar únicamente donde los casos reales aporten evidencia;
- generar APK de prueba y validar el comportamiento visible.
