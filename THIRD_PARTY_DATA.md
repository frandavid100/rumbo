# Datos de terceros

## Catálogo AESAN 2022

Rumbo incorpora una transformación de la «Base de datos de alimentos y bebidas
comercializados en España en 2022», publicada por la Agencia Española de
Seguridad Alimentaria y Nutrición (AESAN):

https://www.aesan.gob.es/AECOSAN/web/seguridad_alimentaria/subseccion/alimentosBebidas.htm

La aplicación conserva los productos con EAN de la hoja `Tabla1`, incluidos los
registros cuya declaración nutricional es incompleta. Se normalizan espacios,
se compacta el archivo y se asigna automáticamente un icono nutricional; no se
alteran los valores declarados por la fuente.

Los datos fueron recogidos por terceros durante 2022 y pueden no reflejar
reformulaciones, retiradas ni disponibilidad comercial posteriores. La mención
de una marca o comercio no constituye recomendación ni garantía de existencias.

El catálogo se puede regenerar ejecutando:

```bash
python3 tools/import_aesan.py
```
