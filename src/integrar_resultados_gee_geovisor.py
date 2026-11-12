"""Procesa, optimiza e integra los resultados exportados desde Google Earth Engine
(C:\\web_copernicus_urbano\\datos\\amss\\resultados) hacia el geovisor web y activos
descargables del repositorio sv-amss.

Genera:
1. geovisor/capas/amss_malla_continua_250m.geojson
   - 24,292 celdas continuas de 250 m saneadas a Polygon/MultiPolygon puros (sin
     GeometryCollection en bordes), enriquecidas espacialmente con DISTRITO y MUNICIPIO,
     y optimizadas a 5 decimales (~1.1 m) para carga instantánea en MapLibre GL JS.
2. geovisor/capas/amss_upd_425_imputadas.geojson
   - Las 425 UPDs del AMSS completas (281 observadas + 144 imputadas por GEE), con
     métricas comparativas y residuales documentadas.
3. geovisor/capas/amss_valor_suelo_pixel_20m.tif
   - Raster GeoTIFF multibanda a 20 m comprimido con DEFLATE + bloques internos (256x256)
     compatible con GeoLibre Studio y sistemas SIG de escritorio (< 19 MB).
4. web/assets/img/modelo/amss_pixel_20m_urbano.png y amss_pixel_20m_potencial.png
   - Overlays raster RGBA georreferenciados en proyección Web Mercator / EPSG:4326
     para visualización interactiva inmediata a 20 m dentro de MapLibre GL JS.
5. geovisor/data/amss_correlaciones_embeddings_suelo.csv y copias descargables en
   web/assets/descargas/ (incluyendo el script GEE gee_modelo_valor_suelo_amss.js).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.warp import Resampling, calculate_default_transform, reproject
from shapely.geometry import MultiPolygon, Polygon, mapping
from shapely.ops import transform as shp_transform

UTM16_TO_WGS84 = Transformer.from_crs("EPSG:32616", "EPSG:4326", always_xy=True).transform

WORKSPACE_ROOT = Path(r"C:\web_copernicus_urbano")
RESULTADOS_DIR = WORKSPACE_ROOT / "datos" / "amss" / "resultados"
REPO_ROOT = WORKSPACE_ROOT / "salida" / "urbano-sv-amss"

CAPAS_DIR = REPO_ROOT / "geovisor" / "capas"
GV_DATA_DIR = REPO_ROOT / "geovisor" / "data"
WEB_MODELO_IMG_DIR = REPO_ROOT / "web" / "assets" / "img" / "modelo"
WEB_DESCARGAS_DIR = REPO_ROOT / "web" / "assets" / "descargas"


def extract_polygonal(geom):
    """Convierte cualquier GeometryCollection residual en Polygon/MultiPolygon puro y homologa CRS a EPSG:4326."""
    if geom is None or geom.is_empty:
        return None
    minx, miny, maxx, maxy = geom.bounds
    if max(abs(minx), abs(maxx)) > 180.0 or max(abs(miny), abs(maxy)) > 90.0:
        geom = shp_transform(UTM16_TO_WGS84, geom)
    if not geom.is_valid:
        geom = geom.make_valid()
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    if hasattr(geom, "geoms"):
        polys = []
        for sub in geom.geoms:
            cleaned = extract_polygonal(sub)
            if cleaned is not None:
                if cleaned.geom_type == "Polygon":
                    polys.append(cleaned)
                elif cleaned.geom_type == "MultiPolygon":
                    polys.extend(list(cleaned.geoms))
        if not polys:
            return None
        return polys[0] if len(polys) == 1 else MultiPolygon(polys)
    return None


def round_coords(coords, precision: int = 5):
    if not coords:
        return coords
    if isinstance(coords[0], (int, float)):
        return [round(float(coords[0]), precision), round(float(coords[1]), precision)]
    return [round_coords(c, precision) for c in coords]


def gdf_to_compact_geojson(gdf: gpd.GeoDataFrame, out_path: Path, coord_prec: int = 5) -> float:
    features = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        geom_dict = mapping(geom)
        geom_dict["coordinates"] = round_coords(geom_dict["coordinates"], coord_prec)
        props = {}
        for col in gdf.columns:
            if col == "geometry":
                continue
            val = row[col]
            if pd.isna(val):
                props[col] = None
            elif isinstance(val, (np.integer, int)):
                props[col] = int(val)
            elif isinstance(val, (np.floating, float)):
                props[col] = round(float(val), 2)
            else:
                props[col] = str(val)
        features.append({"type": "Feature", "properties": props, "geometry": geom_dict})

    fc = {"type": "FeatureCollection", "features": features}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out_path.stat().st_size / (1024 * 1024)


def colorize_land_value(arr: np.ndarray) -> np.ndarray:
    """Aplica rampa continua homologada (USD/m2) con canal alfa transparente fuera del AMSS."""
    h, w = arr.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    valid = np.isfinite(arr) & (arr > 0)
    if not np.any(valid):
        return rgba

    # Puntos de corte continuos alineados con la leyenda homologada del geovisor
    stops_v = np.array([15.0, 30.0, 50.0, 100.0, 175.0, 300.0, 420.0], dtype=np.float32)
    stops_rgb = np.array(
        [
            [254, 240, 217],  # #FEF0D9 (<= $30: rural / reserva)
            [253, 212, 158],  # #FDD49E ($30)
            [253, 187, 132],  # #FDBB84 ($50)
            [252, 141, 89],   # #FC8D59 ($100)
            [227, 74, 51],    # #E34A33 ($175)
            [179, 0, 0],      # #B30000 ($300)
            [103, 0, 31],     # #67001F (>= $420: nodos prime)
        ],
        dtype=np.float32,
    )

    vals = np.clip(arr[valid], stops_v[0], stops_v[-1])
    r = np.interp(vals, stops_v, stops_rgb[:, 0]).astype(np.uint8)
    g = np.interp(vals, stops_v, stops_rgb[:, 1]).astype(np.uint8)
    b = np.interp(vals, stops_v, stops_rgb[:, 2]).astype(np.uint8)

    rgba[valid, 0] = r
    rgba[valid, 1] = g
    rgba[valid, 2] = b
    rgba[valid, 3] = 232
    return rgba


def main() -> None:
    CAPAS_DIR.mkdir(parents=True, exist_ok=True)
    GV_DATA_DIR.mkdir(parents=True, exist_ok=True)
    WEB_MODELO_IMG_DIR.mkdir(parents=True, exist_ok=True)
    WEB_DESCARGAS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Tabla de correlaciones limpia (.csv)
    corr_in = RESULTADOS_DIR / "amss_correlaciones_embeddings_suelo.csv"
    corr_df = pd.read_csv(corr_in)
    keep_cols = [c for c in ("banda", "grupo", "r_pearson", "abs_r", "p_valor") if c in corr_df.columns]
    corr_clean = corr_df[keep_cols].copy()
    corr_clean.insert(0, "ranking", np.arange(1, len(corr_clean) + 1))
    corr_clean.to_csv(GV_DATA_DIR / "amss_correlaciones_embeddings_suelo.csv", index=False, encoding="utf-8")
    corr_clean.to_csv(WEB_DESCARGAS_DIR / "amss_correlaciones_embeddings_suelo.csv", index=False, encoding="utf-8")
    print(f"[1/5] CSV de correlaciones limpio guardado ({len(corr_clean)} predictores).")

    # 2. Malla continua de 250 m enriquecida con Distrito y saneada
    malla_in = RESULTADOS_DIR / "amss_malla_continua_valor_suelo_cuadrada_250m.geojson"
    malla = gpd.read_file(malla_in)
    if "id" in malla.columns:
        malla = malla.drop(columns=["id"])
    malla["geometry"] = malla["geometry"].apply(extract_polygonal)
    malla = malla[malla["geometry"].notna() & ~malla["geometry"].is_empty].copy()

    dist_path = CAPAS_DIR / "amss_14_distritos.geojson"
    if dist_path.exists():
        dist_gdf = gpd.read_file(dist_path).to_crs(epsg=4326)
        d_cols = [c for c in dist_gdf.columns if c != "geometry"]
        name_col = next(
            (c for c in ("NOM_MUN", "DISTRITO", "nomb_distr", "NAM", "NOMBRE", "nombre") if c in d_cols),
            d_cols[0] if d_cols else None,
        )
        mun_col = next((c for c in ("NUEVO_MUN", "MUNICIPIO", "nomb_mun", "MUN") if c in d_cols), None)
        if name_col:
            pts = malla.copy()
            pts_utm = pts.to_crs(epsg=32616)
            pts["geometry"] = pts_utm.geometry.representative_point().to_crs(epsg=4326)
            sub_cols = [name_col] + ([mun_col] if mun_col and mun_col != name_col else []) + ["geometry"]
            joined = gpd.sjoin(pts[["ID_CELDA", "geometry"]], dist_gdf[sub_cols], how="left", predicate="intersects")
            joined = joined.drop_duplicates(subset=["ID_CELDA"])
            malla = malla.merge(
                joined[["ID_CELDA", name_col] + ([mun_col] if mun_col and mun_col != name_col else [])],
                on="ID_CELDA",
                how="left",
            )
            malla = malla.rename(columns={name_col: "DISTRITO"})
            if mun_col and mun_col != name_col:
                malla = malla.rename(columns={mun_col: "MUNICIPIO"})
            malla["DISTRITO"] = malla["DISTRITO"].fillna("Periferia Metropolitana")

    # Porcentaje edificado legible para popups y leyenda
    malla["PCT_EDIF"] = (malla["FRAC_EDIF"].astype(float) * 100.0).round(1)
    ordered_malla_cols = [
        c
        for c in (
            "ID_CELDA",
            "DISTRITO",
            "MUNICIPIO",
            "TIPO_SUELO",
            "VAL_EST_M2",
            "VAL_MED_M2",
            "VAL_POT_M2",
            "VAL_STD_M2",
            "PCT_EDIF",
            "FRAC_EDIF",
            "ALT_EDIF_M",
            "PEND_DEG",
            "AREA_HA",
            "geometry",
        )
        if c in malla.columns
    ]
    malla = malla[ordered_malla_cols]
    sz_malla = gdf_to_compact_geojson(malla, CAPAS_DIR / "amss_malla_continua_250m.geojson", coord_prec=5)
    print(f"[2/5] Malla continua 250 m guardada: {len(malla)} polígonos ({sz_malla:.2f} MB).")
    print("      Quintiles VAL_EST_M2:", np.quantile(malla["VAL_EST_M2"], [0.2, 0.4, 0.6, 0.8]).round(2).tolist())
    print("      Conteo rangos homologados (<=30, 30-50, 50-100, 100-175, 175-300, >300):",
          np.histogram(malla["VAL_EST_M2"], bins=[0, 30, 50, 100, 175, 300, 10000])[0].tolist())

    # 3. UPDs 425 completas imputadas
    upd_in = RESULTADOS_DIR / "amss_upd_425_imputadas_modelo.geojson"
    upd = gpd.read_file(upd_in)
    if "id" in upd.columns:
        upd = upd.drop(columns=["id"])
    upd["geometry"] = upd["geometry"].apply(extract_polygonal)
    upd = upd[upd["geometry"].notna() & ~upd["geometry"].is_empty].copy()
    upd["DIF_MOD_M2"] = np.where(
        upd["ORIGEN_FIN"] == "OBSERVADO",
        (upd["VAL_MOD_M2"].astype(float) - upd["VAL_FIN_M2"].astype(float)).round(2),
        np.nan,
    )
    ordered_upd_cols = [
        c
        for c in (
            "OBJECTID",
            "NAME_UPD",
            "DISTRITO",
            "MUNICIPIO",
            "TIPO",
            "AREA_HA",
            "ORIGEN_FIN",
            "VAL_FIN_M2",
            "VAL_MOD_M2",
            "VAL_FUS25",
            "DIF_MOD_M2",
            "geometry",
        )
        if c in upd.columns
    ]
    upd = upd[ordered_upd_cols]
    sz_upd = gdf_to_compact_geojson(upd, CAPAS_DIR / "amss_upd_425_imputadas.geojson", coord_prec=5)
    print(f"[3/5] UPDs 425 imputadas guardadas: {len(upd)} polígonos ({sz_upd:.2f} MB).")
    print("      Quintiles VAL_FIN_M2 (425 UPDs):", np.quantile(upd["VAL_FIN_M2"], [0.2, 0.4, 0.6, 0.8]).round(2).tolist())
    print("      Conteo rangos homologados UPD (<=50, 50-100, 100-175, 175-300, >300):",
          np.histogram(upd["VAL_FIN_M2"], bins=[0, 50, 100, 175, 300, 10000])[0].tolist())

    # 4. Raster GeoTIFF 20 m optimizado + Overlays PNG georreferenciados en EPSG:3857 para MapLibre
    tif_in = RESULTADOS_DIR / "amss_valor_suelo_pixel_20m.tif"
    tif_out = CAPAS_DIR / "amss_valor_suelo_pixel_20m.tif"
    with rasterio.open(tif_in) as src:
        profile = src.profile.copy()
        profile.update(
            driver="GTiff",
            dtype="float32",
            nodata=-9999.0,
            compress="deflate",
            predictor=2,
            zlevel=9,
            tiled=True,
            blockxsize=256,
            blockysize=256,
        )
        with rasterio.open(tif_out, "w", **profile) as dst:
            for b in range(1, src.count + 1):
                arr = src.read(b)
                arr_clean = np.where(np.isfinite(arr) & (arr > 0), np.round(arr, 2), -9999.0).astype("float32")
                dst.write(arr_clean, b)
                dst.set_band_description(b, src.descriptions[b - 1] or f"band_{b}")
            dst.build_overviews([2, 4, 8], Resampling.average)
            dst.update_tags(ns="rio_overview", resampling="average")

        # Reproyectar bandas 1 (potencial) y 2 (urbano) a EPSG:3857 para alineación exacta en MapLibre image source
        dst_crs = "EPSG:3857"
        transform_3857, w_3857, h_3857 = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )
        # Escalar a ancho máx 2400 px para nitidez visual y peso < 600 KB
        max_w = 2400
        if w_3857 > max_w:
            factor = w_3857 / float(max_w)
            w_3857 = max_w
            h_3857 = int(round(h_3857 / factor))
            transform_3857, w_3857, h_3857 = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds, dst_width=w_3857, dst_height=h_3857
            )

        for b_idx, out_name in ((2, "amss_pixel_20m_urbano.png"), (1, "amss_pixel_20m_potencial.png")):
            src_band = src.read(b_idx)
            dst_band = np.full((h_3857, w_3857), np.nan, dtype=np.float32)
            reproject(
                source=src_band,
                destination=dst_band,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform_3857,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear,
                src_nodata=0.0,
                dst_nodata=np.nan,
            )
            rgba = colorize_land_value(dst_band)
            img = Image.fromarray(rgba, mode="RGBA").quantize(colors=256, method=Image.Quantize.FASTOCTREE)
            png_path = WEB_MODELO_IMG_DIR / out_name
            img.save(png_path, format="PNG", optimize=True)
            shutil.copy2(png_path, GV_DATA_DIR / out_name)
            print(f"      Overlay PNG {out_name}: {w_3857}x{h_3857} px ({png_path.stat().st_size / 1024:.1f} KB)")

        bounds_wgs84 = [
            round(float(src.bounds.left), 6),
            round(float(src.bounds.bottom), 6),
            round(float(src.bounds.right), 6),
            round(float(src.bounds.top), 6),
        ]

    sz_tif = tif_out.stat().st_size / (1024 * 1024)
    print(f"[4/5] GeoTIFF 20 m optimizado con pirámides guardado ({sz_tif:.2f} MB). Bounds WGS84: {bounds_wgs84}")

    # 5. Copiar script GEE y documento Word a web/assets/descargas/ para acceso directo desde la web
    gee_js_src = REPO_ROOT / "src" / "gee_modelo_valor_suelo_amss.js"
    if gee_js_src.exists():
        shutil.copy2(gee_js_src, WEB_DESCARGAS_DIR / "gee_modelo_valor_suelo_amss.js")
    docx_src = REPO_ROOT / "docs" / "Metodologia_Modelo_Valor_Suelo_AMSS_GEE.docx"
    if docx_src.exists():
        shutil.copy2(docx_src, WEB_DESCARGAS_DIR / "Metodologia_Modelo_Valor_Suelo_AMSS_GEE.docx")
    print("[5/5] Activos descargables sincronizados en web/assets/descargas/.")


if __name__ == "__main__":
    main()
