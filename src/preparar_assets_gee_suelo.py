"""Prepara los paquetes Shapefile (.zip) limpios para ingesta como Assets en Google Earth Engine.

Unifica las capas locales de valor de suelo del AMSS:
  1. upd_consolidado.shp (registros de permisos OPAMSS 2007-2019 y 2020-2026)
  2. LISA_PRECIOS_2025.shp (oferta inmobiliaria web scraping 2025, campo promedio_2)
  3. amss_perimetro.geojson y amss_14_distritos.geojson (marco metropolitano continuo)

Genera en C:/web_copernicus_urbano/datos/amss/gee_assets/:
  - amss_upd_suelo_entrenamiento.zip  (Asset obligatorio unificado, 425 UPDs con geometría válida)
  - amss_perimetro_oficial.zip        (Asset opcional del contorno oficial continuo del AMSS)
  - amss_malla_hex_250m.zip           (Asset opcional de malla continua hexagonal de 250 m)
"""

from __future__ import annotations

import math
import shutil
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

NODATA = -9999.0

WORKSPACE_ROOT = Path(r"C:\web_copernicus_urbano")
RAW_AMSS_DIR = WORKSPACE_ROOT / "datos" / "amss"
OUT_ASSETS_DIR = RAW_AMSS_DIR / "gee_assets"
REPO_CAPAS_DIR = WORKSPACE_ROOT / "salida" / "urbano-sv-amss" / "geovisor" / "capas"


def export_zipped_shapefile(gdf: gpd.GeoDataFrame, zip_path: Path, layer_name: str) -> float:
    """Escribe un GeoDataFrame como Shapefile UTF-8 y empaqueta sus componentes en un .zip para GEE."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        shp_path = tmp_path / f"{layer_name}.shp"
        gdf.to_file(shp_path, driver="ESRI Shapefile", encoding="utf-8")
        # Asegurar archivo .cpg explícito para codificación UTF-8 en GEE
        (tmp_path / f"{layer_name}.cpg").write_text("UTF-8", encoding="utf-8")

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for item in sorted(tmp_path.glob(f"{layer_name}.*")):
                zf.write(item, arcname=item.name)

    return zip_path.stat().st_size / (1024.0 * 1024.0)


def clean_str(series: pd.Series, default: str = "ND", max_len: int = 80) -> pd.Series:
    return (
        series.fillna(default)
        .astype(str)
        .str.strip()
        .replace({"": default, "None": default, "nan": default})
        .str.slice(0, max_len)
    )


def build_training_upd_asset() -> tuple[gpd.GeoDataFrame, dict[str, float]]:
    """Une upd_consolidado + LISA_PRECIOS_2025, repara geometrías y calibra VAL_FUS25."""
    upd_path = RAW_AMSS_DIR / "upd_consolidado" / "upd_consolidado.shp"
    lisa_path = RAW_AMSS_DIR / "LISA_PRECIOS_2025" / "LISA_PRECIOS_2025.shp"

    upd = gpd.read_file(upd_path)
    lisa = gpd.read_file(lisa_path)

    # Eliminar registros con geometría nula o vacía (evita fallo de ingesta en GEE)
    n_raw = len(upd)
    upd = upd[upd.geometry.notna() & (~upd.geometry.is_empty)].copy()
    upd["geometry"] = upd.geometry.make_valid()
    upd = upd.to_crs(epsg=4326)
    n_valid = len(upd)

    lisa_cols = [
        "OBJECTID",
        "promedio_2",
        "log_precio",
        "moran_loca",
        "p_perm_loc",
        "cluster_LI",
        "cuadrante_",
    ]
    merged = upd.merge(lisa[lisa_cols], on="OBJECTID", how="left")

    # Área geodésica / proyectada exacta en hectáreas (UTM Zona 16N, EPSG:32616)
    utm_geom = merged.to_crs(epsg=32616).geometry
    area_ha = np.round(utm_geom.area / 10000.0, 3)

    val_mkt25 = pd.to_numeric(merged["promedio_2"], errors="coerce")
    p2_prom = pd.to_numeric(merged["P2_PROM"], errors="coerce")
    p2_med = pd.to_numeric(merged["P2_MED"], errors="coerce")
    p2_n = pd.to_numeric(merged["P2_N"], errors="coerce").fillna(0).astype(int)

    p1_prom = pd.to_numeric(merged["P1_PROM"], errors="coerce")
    p1_med = pd.to_numeric(merged["P1_MED"], errors="coerce")
    p1_n = pd.to_numeric(merged["P1_N"], errors="coerce").fillna(0).astype(int)

    has_mkt25 = val_mkt25.notna() & (val_mkt25 > 0)
    has_p2 = p2_prom.notna() & (p2_prom > 0)
    has_p1 = p1_prom.notna() & (p1_prom > 0) & p1_med.notna() & (p1_med > 0)

    # Winsorización al percentil 98 de P1_PROM para mitigar valores extremos aislados (>7,000 USD/m2)
    p1_cap = float(np.nanpercentile(p1_prom[has_p1], 98))
    p1_prom_w = np.where(has_p1, np.minimum(p1_prom, p1_cap), NODATA)

    # Calibración log-lineal OLS entre P2_PROM (permisos 2020-26) y VAL_MKT25 (mercado 2025)
    # sobre las UPDs que cuentan con ambas observaciones simultáneamente (n=129)
    overlap = has_mkt25 & has_p2
    x_log = np.log(p2_prom[overlap].to_numpy(dtype=float))
    y_log = np.log(val_mkt25[overlap].to_numpy(dtype=float))
    slope_b1, intercept_b0 = np.polyfit(x_log, y_log, 1)
    resid = y_log - (intercept_b0 + slope_b1 * x_log)
    # Estimador smearing de Duan para retransformación insesgada exp(y_hat)
    duan_smearing = float(np.mean(np.exp(resid)))
    r_log = float(np.corrcoef(x_log, y_log)[0, 1])

    # Construcción de VAL_FUS25:
    # - Prioridad 1: Valor de oferta inmobiliaria 2025 observado (VAL_MKT25, 265 UPDs)
    # - Prioridad 2: Valor OPAMSS 2020-2026 calibrado a escala de mercado 2025 (16 UPDs adicionales)
    only_p2 = (~has_mkt25) & has_p2
    p2_calibrated = np.exp(intercept_b0 + slope_b1 * np.log(np.where(only_p2, p2_prom, 1.0))) * duan_smearing

    val_fus25 = np.where(
        has_mkt25,
        val_mkt25,
        np.where(only_p2, p2_calibrated, NODATA),
    )
    has_fus25 = has_mkt25 | only_p2
    fuente_v = np.where(
        has_mkt25,
        "MKT_2025",
        np.where(only_p2, "P2_CALIB", "SIN_DATO"),
    )

    out = gpd.GeoDataFrame(
        {
            "OBJECTID": pd.to_numeric(merged["OBJECTID"], errors="coerce").fillna(0).astype(int),
            "NAME_UPD": clean_str(merged["NAME_UPD"], "SIN_NOMBRE", 80),
            "TIPO": clean_str(merged["TYPE"], "ND", 40),
            "DISTRITO": clean_str(merged["nomb_distr"], "ND", 50),
            "MUNICIPIO": clean_str(merged["nomb_mun"], "ND", 50),
            "AREA_HA": area_ha,
            "VAL_FUS25": np.round(np.where(has_fus25, val_fus25, NODATA), 2),
            "HAS_FUS25": has_fus25.astype(int),
            "FUENTE_V": fuente_v,
            "VAL_MKT25": np.round(np.where(has_mkt25, val_mkt25, NODATA), 2),
            "HAS_MKT25": has_mkt25.astype(int),
            "CLUS_LISA": clean_str(merged["cluster_LI"], "SIN_DATO", 30),
            "CUAD_LISA": clean_str(merged["cuadrante_"], "SIN_DATO", 20),
            "P2_PROM": np.round(np.where(has_p2, p2_prom, NODATA), 2),
            "P2_MED": np.round(np.where(has_p2 & (p2_med > 0), p2_med, NODATA), 2),
            "P2_N": p2_n,
            "HAS_P2": has_p2.astype(int),
            "P1_MED": np.round(np.where(has_p1, p1_med, NODATA), 2),
            "P1_PROM_W": np.round(p1_prom_w, 2),
            "P1_N": p1_n,
            "HAS_P1": has_p1.astype(int),
            "HAB_TOT": np.round(pd.to_numeric(merged["HAB_TOTAL"], errors="coerce").fillna(0.0), 1),
            "UVIP": np.round(pd.to_numeric(merged["UVIP"], errors="coerce").fillna(0.0), 1),
            "PC_TOT": pd.to_numeric(merged["PC_TOT"], errors="coerce").fillna(0).astype(int),
        },
        geometry=merged.geometry,
        crs="EPSG:4326",
    )

    stats = {
        "n_raw": n_raw,
        "n_valid": n_valid,
        "n_mkt25": int(has_mkt25.sum()),
        "n_p2": int(has_p2.sum()),
        "n_p1": int(has_p1.sum()),
        "n_overlap": int(overlap.sum()),
        "n_only_p2": int(only_p2.sum()),
        "n_fus25": int(has_fus25.sum()),
        "b0": float(intercept_b0),
        "b1": float(slope_b1),
        "duan": duan_smearing,
        "r_log": r_log,
        "p1_cap": p1_cap,
    }
    return out, stats


def build_perimeter_asset() -> gpd.GeoDataFrame:
    """Disuelve el contorno metropolitano oficial del AMSS en un único polígono limpio."""
    perim = gpd.read_file(REPO_CAPAS_DIR / "amss_perimetro.geojson").to_crs(epsg=32616)
    perim["geometry"] = perim.geometry.make_valid()
    dissolved_geom = perim.geometry.union_all().buffer(0)
    area_km2 = round(float(dissolved_geom.area) / 1e6, 3)

    gdf = gpd.GeoDataFrame(
        {
            "ID_AMSS": [1],
            "NOMBRE": ["Area Metropolitana de San Salvador (AMSS)"],
            "AREA_KM2": [area_km2],
        },
        geometry=[dissolved_geom],
        crs="EPSG:32616",
    ).to_crs(epsg=4326)
    return gdf


def build_hex_mesh_asset(perim_4326: gpd.GeoDataFrame, spacing_m: float = 250.0) -> gpd.GeoDataFrame:
    """Construye una malla continua hexagonal (teselación regular) sobre todo el AMSS en EPSG:32616.

    spacing_m define la distancia entre centros adyacentes (ancho cara-a-cara del hexágono).
    Para spacing_m = 250 m, cada hexágono completo mide ~5.41 ha.
    """
    perim_utm = perim_4326.to_crs(epsg=32616)
    amss_poly = perim_utm.geometry.iloc[0]
    minx, miny, maxx, maxy = amss_poly.bounds

    # Geometría de hexágono con orientación pointy-top y distancia entre centros = spacing_m
    radius = spacing_m / math.sqrt(3.0)
    dx = spacing_m
    dy = 1.5 * radius

    angles = [math.radians(30 + 60 * k) for k in range(6)]
    unit_offsets = [(radius * math.cos(a), radius * math.sin(a)) for a in angles]

    pad = spacing_m
    y = miny - pad
    row_idx = 0
    hex_polys: list[Polygon] = []

    while y <= maxy + pad:
        x_offset = 0.5 * dx if (row_idx % 2 == 1) else 0.0
        x = minx - pad + x_offset
        while x <= maxx + pad:
            verts = [(x + ox, y + oy) for ox, oy in unit_offsets]
            hex_polys.append(Polygon(verts))
            x += dx
        y += dy
        row_idx += 1

    grid_utm = gpd.GeoDataFrame({"geometry": hex_polys}, crs="EPSG:32616")
    # Filtrado espacial rápido con índice R-tree y recorte exacto al perímetro del AMSS
    idx_cand = list(grid_utm.sindex.query(amss_poly, predicate="intersects"))
    grid_sub = grid_utm.iloc[idx_cand].copy()
    grid_clip = gpd.clip(grid_sub, perim_utm).copy()
    grid_clip = grid_clip[grid_clip.geometry.notna() & (~grid_clip.geometry.is_empty)].copy()
    grid_clip["geometry"] = grid_clip.geometry.make_valid()
    # Conservar únicamente polígonos/multipolígonos con área >= 0.05 ha (evita astillas de borde)
    grid_clip["AREA_HA"] = np.round(grid_clip.geometry.area / 10000.0, 3)
    grid_clip = grid_clip[grid_clip["AREA_HA"] >= 0.05].reset_index(drop=True)

    # Asignar Distrito y Municipio por centroide representativo
    dist = gpd.read_file(REPO_CAPAS_DIR / "amss_14_distritos.geojson").to_crs(epsg=32616)
    dist_sub = dist[["NOM_MUN", "NUEVO_MUN", "geometry"]].copy()
    rep_pts = gpd.GeoDataFrame(
        {"idx_hex": grid_clip.index},
        geometry=grid_clip.geometry.representative_point(),
        crs="EPSG:32616",
    )
    joined = gpd.sjoin(rep_pts, dist_sub, how="left", predicate="within")
    joined = joined.drop_duplicates(subset=["idx_hex"]).set_index("idx_hex")

    grid_clip["HEX_ID"] = np.arange(1, len(grid_clip) + 1, dtype=int)
    grid_clip["DISTRITO"] = clean_str(joined.reindex(grid_clip.index)["NOM_MUN"], "AMSS_BORDE", 50).to_numpy()
    grid_clip["MUNICIPIO"] = clean_str(joined.reindex(grid_clip.index)["NUEVO_MUN"], "AMSS", 50).to_numpy()

    cols = ["HEX_ID", "DISTRITO", "MUNICIPIO", "AREA_HA", "geometry"]
    return grid_clip[cols].to_crs(epsg=4326)


def main() -> None:
    if OUT_ASSETS_DIR.exists():
        shutil.rmtree(OUT_ASSETS_DIR)
    OUT_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    print("1/3 Generando Asset unificado de entrenamiento UPD...")
    upd_gdf, stats = build_training_upd_asset()
    z1 = OUT_ASSETS_DIR / "amss_upd_suelo_entrenamiento.zip"
    mb1 = export_zipped_shapefile(upd_gdf, z1, "amss_upd_suelo_entrenamiento")

    print("2/3 Generando Asset de perímetro oficial continuo del AMSS...")
    perim_gdf = build_perimeter_asset()
    z2 = OUT_ASSETS_DIR / "amss_perimetro_oficial.zip"
    mb2 = export_zipped_shapefile(perim_gdf, z2, "amss_perimetro_oficial")

    print("3/3 Generando Asset opcional de malla continua hexagonal (250 m)...")
    hex_gdf = build_hex_mesh_asset(perim_gdf, spacing_m=250.0)
    z3 = OUT_ASSETS_DIR / "amss_malla_hex_250m.zip"
    mb3 = export_zipped_shapefile(hex_gdf, z3, "amss_malla_hex_250m")

    print("\n=== RESUMEN DE ASSETS GENERADOS PARA GOOGLE EARTH ENGINE ===")
    print(f"Carpeta destino: {OUT_ASSETS_DIR}")
    print(
        f"  [1] {z1.name}: {len(upd_gdf)} polígonos válidos "
        f"(descartados por geometría vacía: {stats['n_raw'] - stats['n_valid']}) | {mb1:.2f} MB"
    )
    print(
        f"      - VAL_MKT25 (Web scraping 2025): {stats['n_mkt25']} UPDs\n"
        f"      - P2_PROM / P2_MED (OPAMSS 2020-2026): {stats['n_p2']} UPDs\n"
        f"      - P1_MED / P1_PROM_W (OPAMSS 2007-2019, tope P98={stats['p1_cap']:.1f}): {stats['n_p1']} UPDs\n"
        f"      - VAL_FUS25 (Fusión calibrada 2025): {stats['n_fus25']} UPDs "
        f"({stats['n_mkt25']} mercado + {stats['n_only_p2']} calibradas desde OPAMSS P2)\n"
        f"      - Calibración log-OLS (n={stats['n_overlap']}): "
        f"ln(MKT25) = {stats['b0']:.4f} + {stats['b1']:.4f}*ln(P2_PROM), "
        f"r_log = {stats['r_log']:.3f}, Duan smearing = {stats['duan']:.4f}"
    )
    print(f"  [2] {z2.name}: {len(perim_gdf)} polígono continuo ({perim_gdf['AREA_KM2'].iloc[0]:.2f} km2) | {mb2:.2f} MB")
    print(f"  [3] {z3.name}: {len(hex_gdf)} hexágonos continuos de 250 m | {mb3:.2f} MB")


if __name__ == "__main__":
    main()
