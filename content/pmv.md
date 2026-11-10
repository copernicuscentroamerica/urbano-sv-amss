## Evidencias documentales y planificación inicial

- S11 contiene 18 tareas: tres Completada, una En Progreso y 14 No Iniciada, con 108 horas estimadas y 91 restantes almacenadas.
- Se declaran terminadas la normalización de la base histórica, la estructura PostgreSQL/PostGIS y la vinculación de trámites; sus resultados ejecutables no se adjuntan al paquete de perfiles.

### Tareas originales de S11

Fuente documental: archivo de planificación `S11` (ver inventario en Metodología). Cada fila conserva su código de trazabilidad original para vincular las tareas con los Issues y el tablero de seguimiento.

| Clave de importación | ID original | HU | Tarea | Prioridad | Rol | Horas estimadas | Estado declarado | Criterio original |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S11-r13 | TS-101.1 | US-GIS-01 | Procesamiento y descarga de mosaicos Sentinel-2, con delimitación del AMSS en GEE/JavaScript. | Must | Líder Técnico SIG | 10 | En Progreso | Mosaico 2020-2026 descargado y recortado con el perímetro oficial AMSS (14 distritos); metadatos ISO 19115. |
| S11-r14 | TS-101.2 | US-GIS-01 | Descarga y vectorización de capa ráster de huella urbana. | Must | Líder Técnico SIG | 1 | No Iniciada | Capa vectorial poligonizada limpia, proyectada en EPSG:32616 y almacenada en GeoPackage/PostGIS. |
| S11-r15 | TS-101.3 | US-GIS-01 | Limpieza y validación topológica de capas vectoriales urbanas. | Should | Líder Técnico SIG | 8 | No Iniciada | Topología validada sin solapes (overlaps), huecos (gaps) ni geometrías duplicadas. |
| S11-r16 | TS-101.4 | US-GIS-01 | Recorte de capas vectoriales de año base (2015/2020) y año de análisis (2026) al perímetro AMSS. | Must | Líder Técnico SIG | 1 | No Iniciada | Capas vectoriales recortadas ajustadas al límite oficial de los 14 distritos del AMSS sin pérdida de atributos. |
| S11-r17 | TS-102.1 | US-GIS-02 | Consulta, filtrado por año y normalización de la base de trámites de permisos de construcción. | Must | Analista ETL SIG | 1 | Completada | Base histórica de trámites (1990-2026) estructurada, clasificada por rangos temporales y sin registros nulos. |
| S11-r18 | TS-102.2 | US-GIS-02 | Estructuración de base de datos relacional y espacial en PostgreSQL/PostGIS. | Must | Analista ETL SIG | 8 | Completada | Modelo de datos relacional implementado con tablas espaciales, claves primarias y permisos de lectura asignados. |
| S11-r19 | TS-102.3 | US-GIS-02 | Vinculación de base de datos de trámites con la capa de puntos de permisos de construcción georreferenciados. | Must | Analista ETL SIG | 1 | Completada | Puntos de trámites 100 % geocodificados dentro de la delimitación metropolitana y vinculados a UPD 2025. |
| S11-r20 | TS-102.4 | US-GIS-02 | Análisis exploratorio de tendencias espaciales (ESDA) y dispersión del valor de suelo. | Should | Líder Técnico SIG | 8 | No Iniciada | Histogramas, semivariogramas y mapas de dispersión generados para validar normalidad y autocorrelación espacial. |
| S11-r21 | TS-102.5 | US-GIS-02 | Generación de modelos de superficie continua a partir de interpolación espacial (Kriging / IDW). | Must | Líder Técnico SIG | 8 | No Iniciada | 3 rásteres continuos de valor de suelo ($/m² y $/v²) generados con error cuadrático medio (RMSE) documentado. |
| S11-r22 | TS-102.6 | US-GIS-02 | Vectorización y reclasificación de capa ráster de valor de suelo en rangos territoriales. | Should | Líder Técnico SIG | 2 | No Iniciada | Capas poligonales de isovalores de suelo generadas, etiquetadas y listas para su consulta ágil. |
| S11-r23 | TS-103.1 | US-GIS-03 | Análisis de la variación de valor de suelo en zonas de expansión urbana y bordes metropolitanos. | Must | Líder Técnico SIG | 8 | No Iniciada | Tabla y capa de correlación entre crecimiento de huella urbana y plusvalías/desvalorizaciones por distrito. |
| S11-r24 | TS-103.2 | US-GIS-03 | Consistencia topológica, completitud y verificación de límites distritales de capas de expansión. | Must | QA Geoespacial | 8 | No Iniciada | Informe de QA emitido: 0 errores topológicos, cobertura 100 % de los 14 distritos y metadatos validados. |
| S11-r25 | TS-103.3 | US-GIS-03 | Revisión técnica y validación institucional de la integración y cruce de geodatos por el PO. | Must | Product Owner | 2 | No Iniciada | Acta de validación institucional de geodatos firmada por el PO para autorizar pase a publicación. |
| S11-r26 | TS-104.1 | US-GIS-04 | Publicación de capas en GeoServer / ArcGIS Server bajo estándares OGC (WMS/WFS) con estilos SLD metropolitanos. | Must | Dev Frontend GIS | 8 | No Iniciada | Servicios WMS/WFS respondiendo en menos de 2 segundos con simbología institucional de OPAMSS. |
| S11-r27 | TS-104.2 | US-GIS-04 | Diseño e implementación de mockup/visor web interactivo en Leaflet/OpenLayers con selector de capas temporales. | Must | Dev Frontend GIS | 14 | No Iniciada | Visor interactivo funcional con selector bitemporal (swipe/deslizador) y consulta de atributos por distrito. |
| S11-r28 | TS-104.3 | US-GIS-04 | Configuración de dashboard con métricas clave (metros cuadrados de expansión, valor promedio de suelo y varianza). | Should | Dev Frontend GIS | 10 | No Iniciada | Dashboard con gráficos dinámicos sincronizados con la extensión del mapa metropolitano y filtros distritales. |
| S11-r29 | TS-104.4 | US-GIS-04 | Prueba de funcionalidad, verificación de experiencia de usuario (UX) y aprobación del visor de consulta por el PO. | Must | Product Owner | 2 | No Iniciada | Aprobación formal del visor web y dashboard en sesión de Sprint Review con usuarios finales de OPAMSS. |
| S11-r30 | TS-105.1 | US-GIS-05 | Documentación técnica de flujos de trabajo, repositorio de scripts (GitHub/GitLab) y manual de actualización anual. | Should | Scrum Master | 8 | No Iniciada | README detallado con pasos de ejecución del pipeline, diccionario de geodatos y versionado en Git. |

## Especificación de módulos de aplicación

Estos componentes describen el diseño funcional previsto para el visor y el tablero de la iniciativa. Los módulos e indicadores se habilitan de forma progresiva a medida que el equipo incorpora y valida cada conjunto de datos en el repositorio.

- Mapa con selector temporal de huella urbana y rangos de valor del suelo.
- Filtro por distrito y, cuando la capa esté disponible, unidad de planificación detallada UPD 2025.
- Comparador bitemporal y panel de datos que distingue expansión, precios observados e interpolaciones.
- Sección de metodología con periodos, unidades, fuentes y error de interpolación.
- Enlace al sistema institucional NIX como referencia, sin presentarlo como la nueva aplicación del proyecto.

### Estados vacíos y navegación

Para garantizar la transparencia técnica, las capas e indicadores en preparación se identifican explícitamente como pendientes hasta contar con datos verificados, evitando sustituir mediciones faltantes con valores simulados. Todos los enlaces de colaboración de esta página conectan directamente con el repositorio oficial de la iniciativa.
