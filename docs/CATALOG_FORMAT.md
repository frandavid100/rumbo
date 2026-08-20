# Formato importable de catálogos de Rumbo

Un catálogo es una base SQLite completa con extensión `.rumbocatalog`. La
versión inicial del contenedor usa `catalog_format=es.rumbo.catalog.sqlite`,
`catalog_format_version=1` y `schema_version=rumbo-catalog-1`.

## Identidad y actualización

La tabla `metadata` debe declarar como mínimo:

| Clave | Contrato |
| --- | --- |
| `catalog_id` | Identidad estable del catálogo. Importarla de nuevo reemplaza la versión instalada. |
| `catalog_name` | Nombre visible. |
| `catalog_version` | Versión no vacía de la instantánea. |
| `product_id_namespace` | Espacio estable y exclusivo de sus `product_id`. |
| `product_count` | Número exacto de filas de `products`. |
| `catalog_format` | `es.rumbo.catalog.sqlite`. |
| `catalog_format_version` | `1`. |
| `schema_version` | `rumbo-catalog-1`. |

`catalog_id` y `product_id_namespace` solo admiten minúsculas ASCII, dígitos,
punto, guion y guion bajo. Todo `product_id` comienza por
`<product_id_namespace>:`. Los identificadores no deben depender del orden de
extracción ni cambiar al actualizar nutrientes, precio o clasificación.

La importación se valida antes de activarse y la sustitución se realiza de
forma atómica. Un archivo con `catalog_id` nuevo se añade; uno con el mismo
`catalog_id` actualiza; dos catálogos distintos no pueden reclamar el mismo
espacio de productos.

## Composición

Rumbo consulta conjuntamente todos los catálogos instalados. Los espacios de
productos exclusivos evitan que una coincidencia textual o numérica elimine
silenciosamente un producto de otra fuente. La resolución global entre fuentes
—por ejemplo mediante GTIN— debe hacerse antes de publicar el catálogo o en una
capa explícita de fusión; el nombre visible nunca funciona como identificador
global de productos comerciales.

Dentro de un catálogo genérico, varias observaciones de la misma identidad se
publican como un solo producto. Las observaciones originales pueden conservarse
en tablas de evidencia, como `source_records`, sin aparecer como alimentos
duplicados.

## Tablas mínimas

El esquema `rumbo-catalog-1` requiere `metadata`, `products`,
`retailer_listings`, `nutrition`, `classifications` y
`classification_roles`. Un catálogo puede añadir tablas de evidencia; los
lectores deben ignorar las extensiones que no necesiten.
