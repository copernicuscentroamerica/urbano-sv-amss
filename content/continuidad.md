## Avances consolidados, consideraciones metodológicas y hoja de ruta de continuidad

### Hitos técnicos completados e integrados al Atlas

- **Perímetro metropolitano, distritos y unidades de planificación (UPD):** Se integraron en `EPSG:4326` el perímetro del AMSS ampliado (`1,488.8 km²`), los límites distritales y de nuevos municipios, y las **425 Unidades de Planificación Detallada (UPD)** libres de información nominal.
- **Armonización multitemporal y mercado inmobiliario:** Se estandarizaron los registros agregados de trámites OPAMSS (`2007–2019` y `2020–2026`) junto con la oferta inmobiliaria `2025` y el análisis de autocorrelación espacial Local Moran's I (**LISA**), reuniendo evidencia empírica directa en **281 UPDs** (`66.1%`).
- **Modelo espacial continuo en Google Earth Engine (Embeddings V1 + Copernicus EO):** Se implementó un flujo reproducible de cero sobrecarga de memoria (`src/gee_modelo_valor_suelo_amss.js`) basado en **71 predictores espaciales** (`64` dimensiones latentes de *Google Satellite Embeddings V1* + `7` covariables biofísicas de *Open Buildings 2.5D*, *ESA WorldCover 10 m*, *VIIRS DNB* y *Copernicus DEM GLO-30*), alcanzando una correlación empírica de `r = 0.7816` (`r_log = 0.7238`) y un sesgo relativo de mediana de `-0.79%` en las UPDs observadas.
- **Tres productos publicados en el Atlas Urbano Regional y el Geovisor:**
  1. **Superficie continua a nivel de píxel (20 m):** `3.85 millones` de píxeles válidos (`3.63 millones` en suelo urbano/desarrollable con pendiente `< 35°` sin agua; rango `$8.66` a `$471.13 USD/m²`).
  2. **Malla continua metropolitana de 250 × 250 m:** `24,292` celdas (`0` vacíos) enriquecidas por distrito y régimen morfológico (`2,215` urbanas consolidadas con media `$187.27/m²`; `1,571` periurbanas `$74.35/m²`; `20,506` rurales/reserva `$33.35/m²`).
  3. **Cobertura completa de las 425 UPDs:** Cierre del `100%` de vacíos cartográficos mediante la imputación satelital de las **144 UPDs** previamente sin muestra (`57,647.5 ha`, mediana imputada `$35.14 USD/m²`).

### Limitaciones y resguardos de interpretación

- Los valores de calibración provienen de expedientes administrativos agregados y levantamiento de precios de oferta inmobiliaria 2025; representan **valores de referencia y oferta de mercado** para análisis territorial y no sustituyen avalúos periciales individuales ni escrituras de compraventa.
- El ensamble *Random Forest* suaviza por construcción las colas extremas superiores (`> $420 USD/m²`) en nodos corporativos verticales puntuales (San Benito, Santa Elena, Paseo General Escalón).
- En celdas de `250 m` atravesadas por cañones o barrancos colindantes con tejido residencial consolidado, se recomienda priorizar la **mediana intra-celda (`VAL_MED_M2`)** e inspeccionar la desviación estándar (`VAL_STD_M2`).

### Siguientes pasos para la Fase II y validación institucional

- **Calibración con microdatos puntuales anonimizados:** Sustituir gradualmente el etiquetado zonal por UPD con puntos o manzanas anonimizadas diferenciando terreno puro frente a propiedad horizontal.
- **Accesibilidad vial y normativa urbanística:** Incorporar al apilamiento de GEE isócronas de red vial hacia subcentros de empleo y coeficientes normativos del Esquema Director de OPAMSS (`COS`, `CUS` y zonificación ambiental).
- **Modelado híbrido y validación espacial por bloques:** Implementar *Regression-Kriging* sobre residuales observados, validación cruzada espacial bloqueada (*Spatial Block CV*) e intervalos de predicción `P10–P90`.
- **Revisión institucional formal:** Documentar la sesión de revisión técnica con las subdirecciones de Planificación, Control del Desarrollo Urbano e Inteligencia Territorial de OPAMSS para actualizar el estado de validación oficial en el manifiesto del proyecto.
