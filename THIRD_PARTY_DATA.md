# Datos de terceros

## Catálogo nutricional de Mercadona (AESAN 2022)

Rumbo incorpora una transformación de la «Base de datos de alimentos y bebidas
comercializados en España en 2022», publicada por la Agencia Española de
Seguridad Alimentaria y Nutrición (AESAN):

https://www.aesan.gob.es/AECOSAN/web/seguridad_alimentaria/subseccion/alimentosBebidas.htm

La aplicación conserva únicamente productos atribuidos a Mercadona mediante la
marca o el fabricante y cuya declaración de calorías, grasas, carbohidratos y
proteínas está completa. Se normalizan espacios, se compacta el archivo y se
asigna automáticamente un icono nutricional; no se alteran los valores declarados.

Los endpoints usados por la tienda web de Mercadona no constituyen una API
oficialmente soportada y no ofrecen los macronutrientes como campos estructurados.
Por ello Rumbo no los consulta desde el móvil ni depende de ellos para planificar.

Los datos fueron recogidos por terceros durante 2022 y pueden no reflejar
reformulaciones, retiradas ni disponibilidad comercial posteriores. La mención
de una marca o comercio no constituye recomendación ni garantía de existencias.

El catálogo se puede regenerar ejecutando:

```bash
python3 tools/import_aesan.py
```

# BEDCA development catalogue

The optional BEDCA catalogue produced by `tools/build_bedca_catalog.py` is for
internal development and validation only. BEDCA's public site currently states
"all rights reserved" and no redistribution permission has been established.
The generated database must not be committed, bundled in a release APK, or
published until its reuse terms are clarified. Every nutrition row is marked
`GENERIC` and retains source-level evidence in the development SQLite.
