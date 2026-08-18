# Validación sistemática del motor de menús

Este documento define las comprobaciones que deben repetirse al modificar el
generador, el evaluador, el recomendador o la taxonomía culinaria.

## Capas de validación

1. **Política culinaria**: cada tipo culinario conserva sus funciones,
   dependencias, exclusiones y límites de cantidad. Los alimentos ambiguos son
   `UNKNOWN`; nunca se infiere una restricción dura a partir de una coincidencia
   dudosa del nombre.
2. **Composición**: ninguna comida contiene dos bases de almidón, dos cereales
   o dos proteínas principales. Los alimentos dependientes llevan una base
   compatible y los ingredientes de cocina no aparecen solos.
3. **Cantidades**: todas las cantidades finales respetan mínimos, máximos y
   unidades indivisibles.
4. **Nutrición**: el evaluador solo declara apto un menú que cumple la política
   semanal. La elección inicial considera calorías, proteína, hidratos y grasa;
   el ajuste de cantidades no debe intentar reparar una composición imposible.
5. **Recomendaciones**: un diagnóstico del repertorio siempre prevalece sobre
   un menú antiguo mostrado. Un estado apto no puede reabrir un déficit de
   macros usando datos obsoletos.

## Matriz obligatoria

Las pruebas deben combinar varios objetivos energéticos y de macros, semillas
deterministas, repertorios mínimos y amplios, frecuencias, comidas activas,
dependencias y tipos excluyentes. Cada defecto real comunicado por un usuario
se conserva como prueba de regresión con sus reglas y valores nutricionales,
pero sin excepciones de producción para perfiles o productos concretos.

La matriz generativa debe comprobar, como mínimo:

- validez culinaria de todas las comidas generadas;
- cantidades dentro de los límites en todos los días;
- determinismo para una misma entrada y semilla;
- suficiencia solo cuando existe al menos una solución aceptable;
- ausencia de recomendaciones bloqueantes cuando el repertorio ya es apto;
- que añadir una alternativa válida no convierta un repertorio apto en no apto.

## Incorporación de un catálogo nuevo

1. Importar los datos originales sin modificar y registrar su procedencia.
2. Aplicar una versión explícita del clasificador determinista.
3. Generar un informe con recuentos por tipo, cambios respecto a la versión
   anterior y muestras de cada clasificación.
4. Revisar manualmente todos los tipos que activan restricciones duras:
   dependencias, bases, proteínas principales, aceites e ingredientes de cocina.
5. Registrar correcciones por identificador estable; no por nombre comercial.
6. Ejecutar las pruebas del importador y toda la matriz del motor.
7. Rechazar la importación si aparece una clasificación ambigua como tipo duro,
   cambia un producto sin corrección explícita o falla cualquier invariante.

## Criterio de publicación

No se publica una APK si falla una prueba, si un caso real no está reproducido
o si no se ha verificado que conserva el identificador y la firma de Rumbo.
