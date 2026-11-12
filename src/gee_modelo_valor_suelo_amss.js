/**
 * ============================================================================
 * MODELO ULTRA-LIGERO DE VALOR DEL SUELO A NIVEL DE PÍXEL Y MALLA CONTINUA — AMSS
 * Proyecto: AMSS: expansión urbana y transformación del suelo (sv-amss)
 * Plataforma: Google Earth Engine (Optimizado contra errores de memoria/capa)
 * ============================================================================
 *
 * ARQUITECTURA DE BAJA MEMORIA (CERO SATURACIÓN EN CONSOLA Y MAPA):
 * 1. Cero cálculos del servidor en Consola (0 llamadas computeValue al inicio):
 *    toda la cuota interactiva de GEE se dedica exclusivamente a dibujar el mapa.
 * 2. Cero kernels focales (halo = 0 píxeles) y cero compuestos de cientos de
 *    escenas: usa las 64 bandas precomputadas de Google Satellite Embeddings V1
 *    (que ya codifican el contexto espacial óptico, radar, térmico y estructural)
 *    + 7 bandas estáticas/anuales directas (71 predictores punto a punto).
 * 3. Muestreo directo con .paint() + .sample() (1,800 píxeles urbanos, tileScale 8)
 *    y 1 solo Random Forest compacto (80 árboles).
 * 4. La agregación pesada sobre los ~24,200 polígonos de la malla continua se
 *    ejecuta únicamente en modo Batch desde la pestaña "Tasks" (Export a Drive),
 *    donde GEE dispone de mucha más memoria y tiempo que en el visor interactivo.
 */

// ============================================================================
// 0. PARÁMETROS DE CONFIGURACIÓN
// ============================================================================

var ASSET_UPD = 'projects/ee-abnerjjimenez/assets/amss_upd_suelo_entrenamiento';
var ASSET_PERIMETRO = 'projects/ee-abnerjjimenez/assets/amss_perimetro_oficial';

// Tamaño de cada polígono de la malla continua generada por GEE en UTM 16N (metros)
var TAMANO_CELDA_M = 250;          // Ej.: 250 m (~24,200 celdas) o 500 m (~6,100 celdas)
var RECORTAR_BORDE_EXPORT = true;  // Recorta celdas de borde al perímetro en el GeoJSON/SHP

// Variable objetivo de valor de suelo en USD/m2 dentro de amss_upd_suelo_entrenamiento:
//   'VAL_FUS25' (recomendado, 281 UPDs) | 'VAL_MKT25' | 'P2_PROM' | 'P2_MED' | 'P1_MED' | 'P1_PROM_W'
var CAMPO_OBJETIVO = 'VAL_FUS25';

// Parámetros ligeros de entrenamiento e inferencia
var ESCALA_MUESTREO_M = 30;        // Escala de muestreo de entrenamiento (m)
var ESCALA_EXPORT_PX_M = 20;       // Escala de exportación del raster GeoTIFF (10 o 20 m)
var NUM_PIX_MUESTRA = 1800;        // Muestra ligera sobre huella urbana
var NUM_ARBOLES_RF = 80;           // Número de árboles del Random Forest
var FACTOR_SESGO_LOG = 1.06;       // Factor Duan/log-normal ligero sin re-escaneo de tabla
var SEMILLA = 42;
var CARPETA_DRIVE = 'GEE_AMSS_Valor_Suelo';

// Dejar en false para NO consumir memoria en Consola (recomendado)
var VER_METRICA_CONSOLA = false;


// ============================================================================
// 1. CARGA DE ASSETS DEL AMSS
// ============================================================================

var updTodas = ee.FeatureCollection(ASSET_UPD);
var perimetroOficial = ee.FeatureCollection(ASSET_PERIMETRO);

var aoiGeom = perimetroOficial.geometry();
var aoiSimple = aoiGeom.simplify({maxError: 25});

var mapaBanderas = {
  'VAL_FUS25': 'HAS_FUS25',
  'VAL_MKT25': 'HAS_MKT25',
  'P2_PROM': 'HAS_P2',
  'P2_MED': 'HAS_P2',
  'P1_MED': 'HAS_P1',
  'P1_PROM_W': 'HAS_P1'
};
var campoBandera = mapaBanderas[CAMPO_OBJETIVO] || null;

var filtroValidas = campoBandera
  ? ee.Filter.and(ee.Filter.eq(campoBandera, 1), ee.Filter.gt(CAMPO_OBJETIVO, 0))
  : ee.Filter.gt(CAMPO_OBJETIVO, 0);

var updValidas = updTodas.filter(filtroValidas).map(function(f) {
  var val = ee.Number(f.get(CAMPO_OBJETIVO));
  return f.set({
    'val_obs': val,
    'ln_val': val.log()
  });
});

Map.centerObject(aoiSimple, 11);
Map.setOptions('HYBRID');


// ============================================================================
// 2. STACK DE 71 BANDAS PUNTO A PUNTO (CERO HALOS / CERO ESCENAS CRUDAS)
// ============================================================================

// 2.1 Google Satellite Embeddings V1 (64 dimensiones A00..A63 a 10 m)
var EMB_BANDS = [];
for (var i = 0; i < 64; i++) {
  EMB_BANDS.push('A' + (i < 10 ? '0' + i : '' + i));
}

var embImg = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL')
  .filterBounds(aoiSimple)
  .filterDate('2023-01-01', '2026-01-01')
  .sort('system:time_start', true)
  .mosaic()
  .select(EMB_BANDS);

// 2.2 Morfología Edilicia 2.5D: Google Open Buildings Temporal V1 (época anual reciente)
var ob23 = ee.ImageCollection('GOOGLE/Research/open-buildings-temporal/v1')
  .filterBounds(aoiSimple)
  .filterDate('2022-06-01', '2024-01-01')
  .sort('system:time_start', true)
  .mosaic()
  .select(['building_presence', 'building_height'])
  .unmask(0);

var obPres = ob23.select('building_presence').rename('ob_pres');
var obHeight = ob23.select('building_height').rename('ob_height');

// 2.3 Cobertura a 10 m: ESA WorldCover v200 (1 sola imagen global precomputada)
var wcMap = ee.ImageCollection('ESA/WorldCover/v200').first().select('Map');
var wcBuilt = wcMap.eq(50).rename('wc_built');
var wcTrees = wcMap.eq(10).rename('wc_trees');
var wcWater = wcMap.eq(80);

// 2.4 Actividad Económica Nocturna: NOAA VIIRS Anual V2.2 (1 sola imagen anual)
var viirsRad = ee.ImageCollection('NOAA/VIIRS/DNB/ANNUAL_V22')
  .sort('system:time_start', false)
  .first()
  .select('average_masked')
  .unmask(0)
  .rename('viirs_rad');

// 2.5 Geomorfometría: Copernicus DEM GLO-30 (elevación y pendiente directa)
var glo30 = ee.ImageCollection('COPERNICUS/DEM/GLO30')
  .filterBounds(aoiSimple)
  .map(function(tile) {
    var elev = tile.select('DEM');
    var slp = ee.Terrain.slope(elev);
    return elev.rename('dem_elev').addBands(slp.rename('dem_slope'));
  })
  .mosaic();

var demElev = glo30.select('dem_elev');
var demSlope = glo30.select('dem_slope');

var PHYS_BANDS = [
  'ob_pres', 'ob_height',
  'wc_built', 'wc_trees',
  'viirs_rad',
  'dem_elev', 'dem_slope'
];

var ALL_BANDS = EMB_BANDS.concat(PHYS_BANDS);

var predictorStack = ee.Image.cat([
  embImg,
  obPres, obHeight,
  wcBuilt, wcTrees,
  viirsRad,
  demElev, demSlope
]).float();


// ============================================================================
// 3. MUESTREO EN HUELLA URBANA Y REGRESIÓN RANDOM FOREST A NIVEL DE PÍXEL
// ============================================================================

var mascaraMuestreoUrb = wcBuilt.eq(1)
  .or(obPres.gt(0.12))
  .and(demSlope.lt(32))
  .and(wcWater.eq(0));

var imgTargetLn = ee.Image().float().paint(updValidas, 'ln_val').rename('ln_val');

var muestras = predictorStack.addBands(imgTargetLn)
  .updateMask(mascaraMuestreoUrb)
  .sample({
    region: aoiSimple,
    scale: ESCALA_MUESTREO_M,
    numPixels: NUM_PIX_MUESTRA,
    seed: SEMILLA,
    tileScale: 8,
    geometries: false
  });

var modeloRF = ee.Classifier.smileRandomForest({
  numberOfTrees: NUM_ARBOLES_RF,
  variablesPerSplit: 18,
  minLeafPopulation: 5,
  bagFraction: 0.70,
  seed: SEMILLA
}).setOutputMode('REGRESSION').train({
  features: muestras,
  classProperty: 'ln_val',
  inputProperties: ALL_BANDS
});

// Superficie continua estimada a nivel de píxel sobre todo el AMSS
var lnValorPx = predictorStack.classify(modeloRF, 'ln_valor_suelo').clip(aoiGeom);

var valorPotencialPx = lnValorPx.exp()
  .multiply(FACTOR_SESGO_LOG)
  .rename('valor_potencial_usd_m2');

var mascaraDesarrollable = demSlope.lt(35).and(wcWater.eq(0));
var valorUrbanoPx = valorPotencialPx.updateMask(mascaraDesarrollable)
  .rename('valor_urbano_usd_m2');

var imagenModeloExport = ee.Image.cat([
  valorPotencialPx,
  valorUrbanoPx,
  lnValorPx
]).float().clip(aoiGeom);

// Solo mensajes de texto locales (0 consumo de memoria del servidor en Consola)
print('Script cargado sin cálculos pesados en Consola.');
print('Variable objetivo: ' + CAMPO_OBJETIVO + ' | Malla continua: ' + TAMANO_CELDA_M + ' m');
print('Abre la pestaña "Tasks" (arriba a la derecha) para descargar la Malla Continua (GeoJSON/SHP) y el GeoTIFF.');

if (VER_METRICA_CONSOLA) {
  print('RMSE log Out-Of-Bag (RF):', modeloRF.explain().getNumber('outOfBagErrorEstimate'));
}


// ============================================================================
// 4. DEFINICIÓN DE LA MALLA CONTINUA DE POLÍGONOS (EJECUTADA EN BATCH EXPORT)
// ============================================================================

var projUtm16 = ee.Projection('EPSG:32616');
var mallaCuadradaRaw = aoiSimple.coveringGrid(projUtm16, TAMANO_CELDA_M);
var aoiInterior = aoiSimple.buffer(-TAMANO_CELDA_M * 1.5, 25);

var mallaContinuaBase = RECORTAR_BORDE_EXPORT
  ? mallaCuadradaRaw.map(function(celda) {
      var g = celda.geometry();
      var esInt = aoiInterior.contains(g, 25);
      var gFin = ee.Geometry(
        ee.Algorithms.If(esInt, g.transform('EPSG:4326', 1), g.intersection(aoiSimple, 1).transform('EPSG:4326', 1))
      );
      var areaHa = gFin.area(1).divide(10000);
      var idCelda = ee.String('C_').cat(ee.String(celda.id()).replace(',', '_'));
      return ee.Feature(gFin, {'ID_CELDA': idCelda, 'AREA_HA': areaHa});
    }).filter(ee.Filter.gte('AREA_HA', 0.05))
  : mallaCuadradaRaw.map(function(celda) {
      var idCelda = ee.String('C_').cat(ee.String(celda.id()).replace(',', '_'));
      return ee.Feature(celda.geometry().transform('EPSG:4326', 1), {
        'ID_CELDA': idCelda,
        'AREA_HA': (TAMANO_CELDA_M * TAMANO_CELDA_M) / 10000
      });
    });

var stackResumenMalla = ee.Image.cat([
  valorUrbanoPx.rename('val_urb'),
  valorPotencialPx.rename('val_pot'),
  wcBuilt.rename('edif_frac'),
  obHeight.rename('edif_h_m'),
  demSlope.rename('pend_deg')
]);

var reductorMalla = ee.Reducer.mean().combine({
  reducer2: ee.Reducer.median(),
  sharedInputs: true
}).combine({
  reducer2: ee.Reducer.stdDev(),
  sharedInputs: true
});

function numSeguro(val, porDefecto) {
  return ee.Number(ee.Algorithms.If(ee.Algorithms.IsEqual(val, null), porDefecto, val));
}

var mallaConValores = stackResumenMalla.reduceRegions({
  collection: mallaContinuaBase,
  reducer: reductorMalla,
  scale: 30,
  tileScale: 8
}).map(function(celda) {
  var valPotMean = numSeguro(celda.get('val_pot_mean'), -9999);
  var valPotMed = numSeguro(celda.get('val_pot_median'), valPotMean);
  var valUrbMean = numSeguro(celda.get('val_urb_mean'), valPotMean);
  var valUrbMed = numSeguro(celda.get('val_urb_median'), valPotMed);
  var valStd = numSeguro(celda.get('val_pot_stdDev'), 0);
  var fracEdif = numSeguro(celda.get('edif_frac_mean'), 0);
  var altEdif = numSeguro(celda.get('edif_h_m_mean'), 0);
  var pendDeg = numSeguro(celda.get('pend_deg_mean'), 0);
  var areaHa = numSeguro(celda.get('AREA_HA'), 0);

  var tipoSuelo = ee.Algorithms.If(
    fracEdif.gte(0.45), 'URBANO_CONSOLIDADO',
    ee.Algorithms.If(fracEdif.gte(0.10), 'PERIURBANO_TRANSICION', 'RURAL_RESERVA')
  );

  return ee.Feature(celda.geometry(), {
    'ID_CELDA': celda.get('ID_CELDA'),
    'AREA_HA': areaHa,
    'VAL_EST_M2': valUrbMean,
    'VAL_MED_M2': valUrbMed,
    'VAL_POT_M2': valPotMean,
    'VAL_STD_M2': valStd,
    'FRAC_EDIF': fracEdif,
    'ALT_EDIF_M': altEdif,
    'PEND_DEG': pendDeg,
    'TIPO_SUELO': tipoSuelo
  });
});

var upd425Imputadas = ee.Image.cat([
  valorUrbanoPx.updateMask(mascaraMuestreoUrb).rename('val_mod_urb'),
  valorPotencialPx.rename('val_mod_pot')
]).reduceRegions({
  collection: updTodas,
  reducer: ee.Reducer.mean(),
  scale: 30,
  tileScale: 8
}).map(function(f) {
  var modPot = numSeguro(f.get('val_mod_pot'), -9999);
  var modEst = numSeguro(f.get('val_mod_urb'), modPot);
  var obsVal = numSeguro(f.get(CAMPO_OBJETIVO), -9999);
  var tieneObs = obsVal.gt(0);
  var valFinal = ee.Number(ee.Algorithms.If(tieneObs, obsVal, modEst));
  return f.select(
    ['OBJECTID', 'NAME_UPD', 'TIPO', 'DISTRITO', 'MUNICIPIO', 'AREA_HA', CAMPO_OBJETIVO],
    null,
    true
  ).set({
    'VAL_MOD_M2': modEst,
    'VAL_FIN_M2': valFinal,
    'ORIGEN_FIN': ee.Algorithms.If(tieneObs, 'OBSERVADO', 'IMPUTADO_MODELO_GEE')
  });
});

var updMediasExport = predictorStack.updateMask(mascaraMuestreoUrb).reduceRegions({
  collection: updValidas.select(['OBJECTID', 'ln_val']),
  reducer: ee.Reducer.mean(),
  scale: 30,
  tileScale: 8
}).filter(ee.Filter.notNull(['A00', 'ln_val']));

var tablaCorrelaciones = ee.FeatureCollection(ALL_BANDS.map(function(b) {
  var corrDict = updMediasExport.reduceColumns({
    reducer: ee.Reducer.pearsonsCorrelation(),
    selectors: [b, 'ln_val']
  });
  var r = ee.Number(corrDict.get('correlation'));
  var grupo = (b.charAt(0) === 'A') ? 'Google_Embedding' : 'Fisica_EO';
  return ee.Feature(null, {
    banda: b,
    grupo: grupo,
    r_pearson: r,
    abs_r: r.abs(),
    p_valor: corrDict.get('p-value')
  });
}));


// ============================================================================
// 5. VISUALIZACIÓN LIGERA EN EL MAPA E INSPECTOR RÁPIDO POR CLIC
// ============================================================================

var PALETA_VALOR = [
  '#1e1b4b', '#312e81', '#1d4ed8', '#0ea5e9',
  '#10b981', '#84cc16', '#facc15', '#f97316',
  '#dc2626', '#7f1d1d'
];

var VIS_VALOR = {
  min: 40,
  max: 950,
  palette: PALETA_VALOR
};

// Capa 1 (apagada): Google Satellite Embeddings RGB
Map.addLayer(
  embImg.select(['A00', 'A01', 'A02']).clip(aoiGeom),
  {min: -0.25, max: 0.25},
  '1. Google Satellite Embeddings (RGB: A00, A01, A02)',
  false
);

// Capa 2 (apagada): Valor observado en UPDs
Map.addLayer(
  ee.Image().float().paint(updValidas, 'val_obs'),
  VIS_VALOR,
  '2. Valor Observado UPDs (' + CAMPO_OBJETIVO + ', USD/m2)',
  false
);

// Capa 3 (apagada): Superficie continua potencial a nivel de píxel
Map.addLayer(
  valorPotencialPx,
  VIS_VALOR,
  '3. Modelo Píxel — Valor Potencial Continuo (USD/m2)',
  false
);

// Capa 4 (ACTIVA — única inferencia encendida al inicio para carga rápida sin error)
Map.addLayer(
  valorUrbanoPx,
  VIS_VALOR,
  '4. Modelo Píxel — Suelo Urbano/Desarrollable (USD/m2)',
  true
);

// Capa 5 (apagada — activar al acercar zoom): Retícula geométrica de la malla de 250 m
Map.addLayer(
  ee.Image().byte().paint(mallaCuadradaRaw, 1, 1).clip(aoiGeom),
  {palette: ['#e2e8f0']},
  '5. Retícula Malla Continua (' + TAMANO_CELDA_M + 'm)',
  false,
  0.45
);

// Capa 6 (ACTIVA): Contorno del Perímetro Oficial del AMSS
Map.addLayer(
  ee.Image().byte().paint(perimetroOficial, 1, 2),
  {palette: ['#38bdf8']},
  '6. Perímetro Oficial AMSS',
  true,
  0.90
);

// --- Leyenda flotante ---
var panelLeyenda = ui.Panel({
  style: {
    position: 'bottom-left',
    padding: '10px 12px',
    backgroundColor: 'rgba(15, 23, 42, 0.90)'
  }
});
panelLeyenda.add(ui.Label({
  value: 'Valor de Suelo Estimado — AMSS (USD/m²)',
  style: {fontWeight: 'bold', fontSize: '13px', color: '#f8fafc', margin: '0 0 6px 0', backgroundColor: 'rgba(0,0,0,0)'}
}));
panelLeyenda.add(ui.Thumbnail({
  image: ee.Image.pixelLonLat().select(0),
  params: {
    bbox: [0, 0, 1, 0.1],
    dimensions: '230x14',
    format: 'png',
    min: 0,
    max: 1,
    palette: PALETA_VALOR
  },
  style: {stretch: 'horizontal', margin: '0 0 4px 0'}
}));
panelLeyenda.add(ui.Label({
  value: '$40/m²                  $350/m²                  $950+/m²',
  style: {fontSize: '11px', color: '#cbd5e1', margin: '0', backgroundColor: 'rgba(0,0,0,0)'}
}));
Map.add(panelLeyenda);

// --- Inspector puntual al hacer clic (evalúa solo 1 celda de 250 m bajo el cursor) ---
var panelInspector = ui.Panel({
  style: {
    position: 'top-right',
    width: '285px',
    padding: '10px 12px',
    backgroundColor: 'rgba(15, 23, 42, 0.90)'
  }
});
var lblInspector = ui.Label({
  value: 'Haz clic en el mapa para consultar el valor del píxel y de su celda de ' + TAMANO_CELDA_M + 'm.',
  style: {fontSize: '12px', color: '#e2e8f0', whiteSpace: 'pre-line', backgroundColor: 'rgba(0,0,0,0)'}
});
panelInspector.add(lblInspector);
Map.add(panelInspector);

Map.onClick(function(coords) {
  lblInspector.setValue('Consultando (' + coords.lon.toFixed(4) + ', ' + coords.lat.toFixed(4) + ')...');
  var pt = ee.Geometry.Point([coords.lon, coords.lat]);

  var muestraPx = ee.Image.cat([valorUrbanoPx, valorPotencialPx]).reduceRegion({
    reducer: ee.Reducer.first(),
    geometry: pt,
    scale: 20
  });

  var subMalla = mallaCuadradaRaw.filterBounds(pt);
  var resumenCelda = ee.Algorithms.If(
    subMalla.size().gt(0),
    stackResumenMalla.reduceRegion({
      reducer: ee.Reducer.mean(),
      geometry: ee.Feature(subMalla.first()).geometry(),
      scale: 30
    }).set('ID_CELDA', ee.String('C_').cat(ee.String(ee.Feature(subMalla.first()).id()).replace(',', '_'))),
    ee.Dictionary({})
  );

  ee.Dictionary({
    px: muestraPx,
    celda: resumenCelda
  }).evaluate(function(res) {
    if (!res) {
      lblInspector.setValue('Sin datos en la ubicación seleccionada.');
      return;
    }
    var pxPot = (res.px && res.px.valor_potencial_usd_m2 != null)
      ? '$' + res.px.valor_potencial_usd_m2.toFixed(1) + ' USD/m²'
      : 'Fuera de AMSS';
    var pxUrb = (res.px && res.px.valor_urbano_usd_m2 != null)
      ? '$' + res.px.valor_urbano_usd_m2.toFixed(1) + ' USD/m²'
      : 'Restricción topográfica/agua';

    var txt = 'Coordenadas: ' + coords.lat.toFixed(5) + ', ' + coords.lon.toFixed(5) +
      '\nPíxel desarrollable: ' + pxUrb +
      '\nPíxel potencial: ' + pxPot;

    if (res.celda && res.celda.val_pot != null) {
      var valCelda = (res.celda.val_urb != null) ? res.celda.val_urb : res.celda.val_pot;
      txt += '\n──────────────────────────' +
        '\nCelda (' + TAMANO_CELDA_M + 'm): ' + res.celda.ID_CELDA +
        '\nValor medio celda: $' + Number(valCelda).toFixed(1) + ' USD/m²' +
        '\nFracción construida: ' + (Number(res.celda.edif_frac || 0) * 100).toFixed(1) + '%' +
        '\nAltura media 2.5D: ' + Number(res.celda.edif_h_m || 0) .toFixed(1) + ' m';
    }
    lblInspector.setValue(txt);
  });
});


// ============================================================================
// 6. TAREAS DE EXPORTACIÓN BATCH A GOOGLE DRIVE (PESTAÑA TASKS)
// ============================================================================

var sufijoMalla = 'cuadrada_' + TAMANO_CELDA_M + 'm';

// 1. Malla continua de polígonos sobre todo el AMSS en GeoJSON (para el Geovisor)
Export.table.toDrive({
  collection: mallaConValores,
  description: 'AMSS_Malla_Continua_' + sufijoMalla + '_GeoJSON',
  folder: CARPETA_DRIVE,
  fileNamePrefix: 'amss_malla_continua_valor_suelo_' + sufijoMalla,
  fileFormat: 'GeoJSON'
});

// 2. Malla continua de polígonos sobre todo el AMSS en Shapefile (para QGIS/ArcGIS)
Export.table.toDrive({
  collection: mallaConValores,
  description: 'AMSS_Malla_Continua_' + sufijoMalla + '_SHP',
  folder: CARPETA_DRIVE,
  fileNamePrefix: 'amss_malla_continua_valor_suelo_' + sufijoMalla + '_shp',
  fileFormat: 'SHP'
});

// 3. Raster Cloud-Optimized GeoTIFF (COG) a nivel de píxel (20 m)
Export.image.toDrive({
  image: imagenModeloExport,
  description: 'AMSS_Valor_Suelo_Pixel_' + ESCALA_EXPORT_PX_M + 'm_COG',
  folder: CARPETA_DRIVE,
  fileNamePrefix: 'amss_valor_suelo_pixel_' + ESCALA_EXPORT_PX_M + 'm',
  region: aoiSimple.bounds(),
  scale: ESCALA_EXPORT_PX_M,
  crs: 'EPSG:4326',
  maxPixels: 1e10,
  formatOptions: {cloudOptimized: true}
});

// 4. Las 425 UPDs del AMSS completas (observadas + 144 imputadas por el modelo)
Export.table.toDrive({
  collection: upd425Imputadas,
  description: 'AMSS_UPD_425_Completas_Imputadas_GeoJSON',
  folder: CARPETA_DRIVE,
  fileNamePrefix: 'amss_upd_425_imputadas_modelo',
  fileFormat: 'GeoJSON'
});

// 5. Tabla CSV de correlaciones de las 71 bandas (Embeddings + EO) con ln(Valor)
Export.table.toDrive({
  collection: tablaCorrelaciones.sort('abs_r', false),
  description: 'AMSS_Correlaciones_Embeddings_Valor_Suelo_CSV',
  folder: CARPETA_DRIVE,
  fileNamePrefix: 'amss_correlaciones_embeddings_suelo',
  fileFormat: 'CSV'
});
