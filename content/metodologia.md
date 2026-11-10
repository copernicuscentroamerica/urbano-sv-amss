## Alcance técnico y metodológico declarado en el perfil

Los siguientes campos reproducen la información de `S10`. Son declaraciones del perfil y no una comprobación de disponibilidad o vigencia.

### Territorio y escala

**Ciudad, sector o territorio.** Área Metropolitana de San Salvador – Zona núcleo/urbana (AMSS) - 14 DISTRITOS

**Escala principal de análisis.** Área urbana metropolitana / conurbación

**Superficie aproximada.** 165.107 ha (≈ 1651 km²), calculada a partir del polígono del formulario

**Centroide (lat, lon).** 13.61892, -89.31432

**¿Cuenta con archivos geoespaciales?.** Sí

**Archivo cargado.** Perimetro_AMSS-14_26_13.zip

**Descripción de los archivos.** Se comparte el límite del Área Metropolitana de San Salvador

### Instrumentos y productos

**Instrumento de planificación o gestión al que aportaría.** Plan de ordenamiento territorial / plan de desarrollo urbano

Reglamento o plan de zonificación / uso del suelo

Plan parcial / plan maestro de sector

Permisos de construcción / licencias

Plan de inversión municipal / presupuesto

**Tipo de producto o entregable.** Mapa

Capa geoespacial

Script reproducible

Flujo de trabajo / metodología

Dashboard / tablero

Visor web

Base de datos

**Descripción del producto.** Un usuario final tendría que poder visualizar el mapa y consultar el dashboard para la toma de decisiones. Técnicos SIG utilizarán el script y consultarán el flujo de trabajo y metodología para poder replicar el trabajo y llevar un monitoreo de la información territorial.

**Avance mínimo esperado en la jornada presencial.** Primer script, capa demostrativa, flujo de análisis y mockup de tablero.

### Datos

**Datos satelitales o productos geoespaciales útiles.** Sentinel-2 / óptico multiespectral

Sentinel-1 / radar SAR

GHSL / huella urbana global

OpenStreetMap (vías, edificaciones, equipamientos)

Luces nocturnas (VIIRS)

Catastro / parcelario

Límites institucionales o administrativos

Limites de unidades de planificación detallada (UPD 2025)

Puntos de permisos de construcción de 1990 al 2026

**Datos locales, institucionales o de campo disponibles.** Base de datos de sistema de trámites

Esquema director,

Base de datos de precio de venta obtenidos de webscraping de páginas de ventas inmobiliarias

**Datos que hacen falta.** Actualizar y ampliar los datos obtenidos de webscraping, porque tenemos pocos datos y son del 2025

**Enlaces relacionados.** https://nix.opamss.org.sv/

### Método y herramientas

**Métodos o pasos previstos.** Detección de cambios / expansión urbana entre fechas

Clasificación de coberturas y usos urbanos

Extracción de edificaciones (segmentación / deep learning)

Series temporales

Análisis multicriterio / aptitud del suelo

Modelación de crecimiento urbano / escenarios

Análisis de exposición, vulnerabilidad y riesgo

Visualización en dashboard, visor o app

**Flujo de trabajo preliminar.** Revisión de datos existentes, integración al análisis de la base de datos de trámites, completar la información faltante referente al valor de suelo, estandarizar datos, desarrollo de script, generar mapa, implementación de aplicativo web map.

Revisión de los datos existentes de la base de datos de tramites relacionados al valor del suelo y permisos de construcción históricos.

Completar vacíos de información faltante mediante web srcapping de valor de suelo

Estandarización de datos y normalización en el territorio

Elaboración del mapa de expansión urbana mediante imágenes satelitales y scripts

Identificar los cambios en la mancha urbana

Interpolar los precios de valor de suelo (USD/V2 o M2) con base a la data histórica obtenida de los permisos de construcción y el web scrapping.

Generar periodos de tiempo de análisis

Generar rangos de valor de suelo

Elaborar un mapa de consulta con dashboard

Cruce de información con las variables temporales y rangos de valores de suelo definidos anteriormente.

Identificación general de las diferentes tipologías de expansión urbana identificadas en el territorio AMSS

**Índices, algoritmos o herramientas.** NDVI, NDBI, LST, clasificación supervisada, análisis multicriterio, Google Earth Engine, QGIS, R, Python, JavaScript, ArcGIS Pro y Server, Agentes de IA

### Operación y acompañamiento

**Frecuencia de actualización o análisis.** Anual

**Nivel(es) de acceso.** Uso interno

Uso institucional

**Componentes para usar o desplegar.** GeoServer / servicio geoespacial

**Uso previsto por otras personas.** Aplicativo web consultado en línea

**¿Requiere actualización periódica?.** Sí

**Actualización requerida.** Actualización anual, con la actualización de datos del sistema de trámites y nueva información de valor de suelo.

**Pregunta principal.** ¿Cómo estructurar el proceso de trabajo, desde la definición del problema, la metodología de análisis hasta la visualización y despliegue web, para desarrollar una solución de monitoreo de las dinámicas de expansión urbana y transformación del suelo en el AMSS?

**Áreas en las que necesita asesoría.** Problema, alcance y producto mínimo viable

Metodología y análisis geoespacial

Producto esperado y visualización

Despliegue digital

## Referencias documentales del expediente

- `S09` — `0. Perfiles de Proyectos/Grupo 2_ El Salvador_AMSS/Ficha_02_El_Salvador_OPAMSS_Expansion_Urbana_AMSS.docx`.

- `S10` — `0. Perfiles de Proyectos/Grupo 2_ El Salvador_AMSS/Ficha_02_El_Salvador_OPAMSS_Expansion_Urbana_AMSS_AV_02.docx`.

- `S11` — `0. Perfiles de Proyectos/Grupo 2_ El Salvador_AMSS/Sprint_Backlog_Marco_Scrum_ProyectoSIG_OPAMSS_FINAL.xlsx`.
