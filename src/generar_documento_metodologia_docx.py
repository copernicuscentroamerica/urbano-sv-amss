"""Genera el documento Word (.docx) institucional con la metodología completa del modelo
espacial de valor del suelo a nivel de píxel y malla continua en el AMSS (sv-amss).

Construye gráficos analíticos de alta resolución (300 DPI) a partir de los datos reales
del proyecto utilizando GeoPandas + Pillow, y empaqueta un archivo OpenXML (.docx)
estrictamente conforme al estándar ECMA-376 con la identidad visual institucional de
Copernicus Centroamérica (Calibri Light / Calibri, paleta #000A62, #0C1659, #FFC800).
"""

from __future__ import annotations

import datetime as dt
import io
import math
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

import geopandas as gpd
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

WORKSPACE_ROOT = Path(r"C:\web_copernicus_urbano")
REPO_ROOT = WORKSPACE_ROOT / "salida" / "urbano-sv-amss"
ASSETS_DIR = WORKSPACE_ROOT / "datos" / "amss" / "gee_assets"
RESULTADOS_DIR = WORKSPACE_ROOT / "datos" / "amss" / "resultados"
WEB_FIGURAS_DIR = REPO_ROOT / "web" / "assets" / "img" / "figuras"
OUT_DOCX_REPO = REPO_ROOT / "docs" / "Metodologia_Modelo_Valor_Suelo_AMSS_GEE.docx"
OUT_DOCX_WEB = REPO_ROOT / "web" / "assets" / "descargas" / "Metodologia_Modelo_Valor_Suelo_AMSS_GEE.docx"
OUT_DOCX_DATOS = WORKSPACE_ROOT / "datos" / "amss" / "Metodologia_Modelo_Valor_Suelo_AMSS_GEE.docx"

# Paleta institucional (docs/identidad-visual.md)
HEX_BRAND_BLUE = "000A62"
HEX_COVER_BLUE = "0C1659"
HEX_MESH_BLUE = "172070"
HEX_ACCENT_YELLOW = "FFC800"
HEX_TEAL = "0F766E"
HEX_SLATE_DARK = "1E293B"
HEX_SLATE_MUTED = "475569"
HEX_BG_LIGHT = "F1F5F9"
HEX_BG_CALLOUT = "EEF2FF"
HEX_BG_WARN = "FFFBEB"
HEX_BORDER = "CBD5E1"


def load_font(size: int, bold: bool = False, light: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    fonts_dir = Path(r"C:\Windows\Fonts")
    candidates = []
    if mono:
        candidates = ["consolab.ttf" if bold else "consola.ttf", "cour.ttf"]
    elif bold:
        candidates = ["calibrib.ttf", "segoeuib.ttf", "arialbd.ttf"]
    elif light:
        candidates = ["calibril.ttf", "segoeuil.ttf", "calibri.ttf"]
    else:
        candidates = ["calibri.ttf", "segoeui.ttf", "arial.ttf"]

    for name in candidates:
        fp = fonts_dir / name
        if fp.exists():
            try:
                return ImageFont.truetype(str(fp), size=size)
            except Exception:
                pass
    return ImageFont.load_default()


# ==============================================================================
# 1. GENERACIÓN DE FIGURAS DE ALTA RESOLUCIÓN (300 DPI)
# ==============================================================================

def create_fig1_workflow() -> bytes:
    """Diagrama de arquitectura metodológica en 4 fases (1800 x 1020 px)."""
    W, H = 1800, 1020
    img = Image.new("RGB", (W, H), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    # Encabezado del diagrama
    draw.rounded_rectangle([30, 24, W - 30, 112], radius=14, fill="#0C1659")
    draw.rectangle([30, 102, W - 30, 112], fill="#FFC800")
    f_title = load_font(32, bold=True)
    f_sub = load_font(20)
    draw.text((60, 38), "Arquitectura Metodológica del Modelo Espacial de Valor del Suelo — AMSS", fill="#FFFFFF", font=f_title)
    draw.text((60, 74), "Fusión de registros locales OPAMSS + Web Scraping 2025 + Google Satellite Embeddings V1 en Google Earth Engine", fill="#E2E8F0", font=f_sub)

    phases = [
        {
            "num": "FASE I",
            "title": "Armonización y Calibración Local (Python)",
            "color": "#000A62",
            "bg": "#EEF2FF",
            "items": [
                "• Auditoría topológica de 426 UPDs (eliminación de 1 geometría vacía -> 425 válidas).",
                "• Unión exacta por llave OBJECTID entre upd_consolidado (OPAMSS) y LISA_PRECIOS_2025.",
                "• Winsorización al P98 ($6,561.4/m²) en permisos históricos 2007–2019 (P1_PROM_W).",
                "• Regresión log-OLS (n=129, r=0.614) + factor Duan (1.2141) -> VAL_FUS25 (281 UPDs).",
                "• Empaquetado de Assets GEE: amss_upd_suelo_entrenamiento y amss_perimetro_oficial."
            ],
        },
        {
            "num": "FASE II",
            "title": "Cubo Satelital Ligero Sin Halos en GEE (71 Bandas)",
            "color": "#0F766E",
            "bg": "#F0FDFA",
            "items": [
                "• Google Satellite Embeddings V1 (A00..A63, 64 bandas a 10 m, AlphaEarth Foundations).",
                "• Morfología edilicia 2.5D: Open Buildings Temporal V1 (presencia y altura en metros).",
                "• Cobertura del suelo a 10 m: ESA WorldCover v200 (huella construida, árboles, agua).",
                "• Intensidad económica nocturna: NOAA VIIRS DNB Annual V2.2 (radiancia anual limpia).",
                "• Geomorfometría: Copernicus DEM GLO-30 (altitud m s.n.m. y pendiente en grados)."
            ],
        },
        {
            "num": "FASE III",
            "title": "Control de Sesgo MAUP y Regresión Píxel (Random Forest)",
            "color": "#1D4ED8",
            "bg": "#EFF6FF",
            "items": [
                "• Máscara intra-UPD de huella urbana/desarrollable (excluye quebradas >32° y bosque).",
                "• Muestreo raster directo (.paint + .sample, 1,800 píxeles urbanos, tileScale = 8).",
                "• Entrenamiento Random Forest (80 árboles) sobre ln(Valor) con arquitectura halo=0.",
                "• Retransformación exponencial ajustada por sesgo log-normal -> USD/m² a 20 m.",
                "• Generación dual: valor_urbano_usd_m2 (suelo desarrollable) y valor_potencial_usd_m2."
            ],
        },
        {
            "num": "FASE IV",
            "title": "Malla Continua de Polígonos e Imputación Metropolitana",
            "color": "#B45309",
            "bg": "#FFFBEB",
            "items": [
                "• Generación nativa coveringGrid en UTM Zona 16N (EPSG:32616) con celdas de 250 m.",
                "• Cobertura continua de 1,484.21 km² (~24,200 polígonos con recorte limpio de borde).",
                "• Reducción zonal: media, mediana, desviación estándar, fracción y altura construida.",
                "• Tipologías: URBANO_CONSOLIDADO, PERIURBANO_TRANSICION y RURAL_RESERVA.",
                "• Imputación de las 144 UPDs sin muestra + exportación Batch (GeoJSON, SHP, COG, CSV)."
            ],
        },
    ]

    f_badge = load_font(20, bold=True)
    f_box_title = load_font(24, bold=True)
    f_item = load_font(19)

    box_w = 820
    box_h = 370
    positions = [
        (50, 155),
        (930, 155),
        (50, 585),
        (930, 585),
    ]

    for idx, (ph, (x0, y0)) in enumerate(zip(phases, positions)):
        x1, y1 = x0 + box_w, y0 + box_h
        draw.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=ph["bg"], outline=ph["color"], width=3)
        draw.rounded_rectangle([x0, y0, x1, y0 + 62], radius=16, fill=ph["color"])
        draw.rectangle([x0, y0 + 42, x1, y0 + 62], fill=ph["color"])

        # Badge amarillo
        draw.rounded_rectangle([x0 + 18, y0 + 13, x0 + 125, y0 + 49], radius=8, fill="#FFC800")
        draw.text((x0 + 32, y0 + 19), ph["num"], fill="#000A62", font=f_badge)
        draw.text((x0 + 142, y0 + 17), ph["title"], fill="#FFFFFF", font=f_box_title)

        yy = y0 + 82
        for line in ph["items"]:
            draw.text((x0 + 24, yy), line, fill="#1E293B", font=f_item)
            yy += 54

    # Flechas conectoras entre fases
    arrow_color = "#0C1659"
    # Fase I -> Fase II
    draw.line([(872, 340), (926, 340)], fill=arrow_color, width=6)
    draw.polygon([(928, 340), (908, 327), (908, 353)], fill=arrow_color)
    # Fase II -> Fase III (diagonal central)
    draw.line([(1340, 528), (1340, 555), (460, 555), (460, 582)], fill=arrow_color, width=5)
    draw.polygon([(460, 584), (448, 566), (472, 566)], fill=arrow_color)
    # Fase III -> Fase IV
    draw.line([(872, 770), (926, 770)], fill=arrow_color, width=6)
    draw.polygon([(928, 770), (908, 757), (908, 783)], fill=arrow_color)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()




def create_fig2_spatial_coverage(upd_gdf: gpd.GeoDataFrame, perim_gdf: gpd.GeoDataFrame) -> bytes:
    """Mapa real de cobertura de las 425 UPDs y perímetro oficial del AMSS (1700 x 1100 px)."""
    W, H = 1700, 1100
    img = Image.new("RGB", (W, H), "#F8FAFC")
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([25, 20, W - 25, 102], radius=12, fill="#0C1659")
    draw.rectangle([25, 94, W - 25, 102], fill="#FFC800")
    f_title = load_font(30, bold=True)
    f_sub = load_font(19)
    draw.text((52, 32), "Cobertura Territorial del Modelo sobre el AMSS (425 UPDs y Perímetro Oficial)", fill="#FFFFFF", font=f_title)
    draw.text((52, 66), "Distribución espacial de observaciones en VAL_FUS25 (n = 281 UPDs con dato) y zonas imputadas por Google Earth Engine (144 UPDs)", fill="#E2E8F0", font=f_sub)

    upd_utm = upd_gdf.to_crs(epsg=32616)
    perim_utm = perim_gdf.to_crs(epsg=32616)

    minx, miny, maxx, maxy = perim_utm.total_bounds
    map_x0, map_y0, map_x1, map_y1 = 55, 130, 1180, 1050
    avail_w = map_x1 - map_x0
    avail_h = map_y1 - map_y0
    scale = min(avail_w / (maxx - minx), avail_h / (maxy - miny)) * 0.94
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    px_center = (map_x0 + map_x1) / 2.0
    py_center = (map_y0 + map_y1) / 2.0

    def to_px(x: float, y: float) -> tuple[float, float]:
        return (px_center + (x - cx) * scale, py_center - (y - cy) * scale)

    draw.rounded_rectangle([map_x0 - 15, map_y0 - 10, map_x1 + 15, map_y1 + 15], radius=12, fill="#FFFFFF", outline="#CBD5E1", width=2)

    def draw_geom(geom, fill_col: str | None, outline_col: str, width: int = 1) -> None:
        if geom is None or geom.is_empty:
            return
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms) if geom.geom_type == "MultiPolygon" else []
        for poly in polys:
            ext_pts = [to_px(x, y) for x, y in poly.exterior.coords]
            if len(ext_pts) >= 3:
                if fill_col:
                    draw.polygon(ext_pts, fill=fill_col, outline=outline_col)
                if width > 1:
                    draw.line(ext_pts + [ext_pts[0]], fill=outline_col, width=width)

    # Fondo del perímetro oficial AMSS (muestra también los ~36 km2 fuera de UPDs)
    for g in perim_utm.geometry:
        draw_geom(g, "#E2E8F0", "#0C1659", width=2)

    color_map = {
        "MKT_2025": "#0F766E",   # Verde azulado: Oferta mercado 2025 (265)
        "P2_CALIB": "#F59E0B",   # Ámbar: Permisos OPAMSS 2020-26 calibrados (16)
        "SIN_DATO": "#94A3B8",   # Gris azulado: Imputadas por modelo GEE (144)
    }

    for _, row in upd_utm.iterrows():
        fuente = str(row.get("FUENTE_V", "SIN_DATO"))
        col = color_map.get(fuente, "#94A3B8")
        draw_geom(row.geometry, col, "#FFFFFF", width=1)

    # Re-trazar contorno oficial AMSS encima
    for g in perim_utm.geometry:
        draw_geom(g, None, "#000A62", width=3)

    # Panel lateral de leyenda y síntesis estadística
    lx0, ly0, lx1, ly1 = 1215, 130, 1665, 1050
    draw.rounded_rectangle([lx0, ly0, lx1, ly1], radius=12, fill="#FFFFFF", outline="#CBD5E1", width=2)

    f_sec = load_font(24, bold=True)
    f_lbl = load_font(20, bold=True)
    f_txt = load_font(18)

    draw.text((lx0 + 24, ly0 + 24), "Leyenda de Fuentes (UPDs)", fill="#000A62", font=f_sec)

    legend_items = [
        ("#0F766E", "Oferta Mercado 2025 (MKT_2025)", "265 UPDs con precio web scraping"),
        ("#F59E0B", "OPAMSS 2020–26 Calibrado", "16 UPDs adicionales (log-OLS + Duan)"),
        ("#94A3B8", "UPDs sin muestra reciente", "144 UPDs estimadas por modelo GEE"),
        ("#E2E8F0", "Franja periférica oficial AMSS", "~35.9 km² cubiertos por malla 250 m"),
    ]

    yy = ly0 + 75
    for col, title, desc in legend_items:
        draw.rounded_rectangle([lx0 + 24, yy, lx0 + 64, yy + 34], radius=6, fill=col, outline="#334155", width=1)
        draw.text((lx0 + 78, yy - 2), title, fill="#0F172A", font=f_lbl)
        draw.text((lx0 + 78, yy + 24), desc, fill="#475569", font=f_txt)
        yy += 78

    draw.line([(lx0 + 24, yy + 10), (lx1 - 24, yy + 10)], fill="#CBD5E1", width=2)
    yy += 32
    draw.text((lx0 + 24, yy), "Indicadores Clave del Territorio", fill="#000A62", font=f_sec)
    yy += 45

    kpis = [
        ("Superficie oficial AMSS:", "1,484.21 km² (148,421 ha)"),
        ("Superficie 425 UPDs:", "1,448.30 km²"),
        ("Mediana tamaño de UPD:", "164.8 ha (P95 = 1,230.1 ha)"),
        ("Muestra fusionada 2025:", "281 UPDs (66.1% del total)"),
        ("Resolución modelo píxel:", "20 m (71 bandas GEE)"),
        ("Malla continua generada:", "Cuadrícula UTM 250 m"),
        ("Polígonos malla AMSS:", "~24,200 celdas (6.25 ha)"),
    ]
    for k, v in kpis:
        draw.text((lx0 + 24, yy), k, fill="#334155", font=f_lbl)
        draw.text((lx0 + 24, yy + 24), v, fill="#0F766E", font=f_txt)
        yy += 62

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()




def create_fig3_calibration(upd_gdf: gpd.GeoDataFrame) -> bytes:
    """Gráfico empírico de calibración log-lineal entre OPAMSS P2_PROM y Oferta 2025 (1600 x 980 px)."""
    W, H = 1600, 980
    img = Image.new("RGB", (W, H), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([25, 20, W - 25, 100], radius=12, fill="#0C1659")
    draw.rectangle([25, 92, W - 25, 100], fill="#FFC800")
    f_title = load_font(28, bold=True)
    f_sub = load_font(19)
    draw.text((50, 31), "Calibración Empírica entre Permisos OPAMSS (2020–2026) y Oferta de Mercado (2025)", fill="#FFFFFF", font=f_title)
    draw.text((50, 64), "Ajuste OLS en escala logarítmica natural sobre las n = 129 UPDs con observación simultánea", fill="#E2E8F0", font=f_sub)

    sub = upd_gdf[(upd_gdf["HAS_MKT25"] == 1) & (upd_gdf["HAS_P2"] == 1)].copy()
    x = np.log(sub["P2_PROM"].to_numpy(dtype=float))
    y = np.log(sub["VAL_MKT25"].to_numpy(dtype=float))
    b1, b0 = np.polyfit(x, y, 1)
    r_val = float(np.corrcoef(x, y)[0, 1])
    duan = float(np.mean(np.exp(y - (b0 + b1 * x))))

    px0, py0, px1, py1 = 150, 150, 1120, 865
    draw.rectangle([px0, py0, px1, py1], fill="#F8FAFC", outline="#94A3B8", width=2)

    xmin, xmax = float(np.min(x)) - 0.25, float(np.max(x)) + 0.25
    ymin, ymax = float(np.min(y)) - 0.25, float(np.max(y)) + 0.25

    def to_pt(xv: float, yv: float) -> tuple[float, float]:
        ux = px0 + (xv - xmin) / (xmax - xmin) * (px1 - px0)
        uy = py1 - (yv - ymin) / (ymax - ymin) * (py1 - py0)
        return (ux, uy)

    f_tick = load_font(17)
    f_axis = load_font(21, bold=True)

    # Líneas de cuadrícula
    for xv in np.arange(math.ceil(xmin), math.floor(xmax) + 0.5, 1.0):
        gx, _ = to_pt(xv, ymin)
        if px0 <= gx <= px1:
            draw.line([(gx, py0), (gx, py1)], fill="#E2E8F0", width=1)
            lbl = f"{xv:.1f} (${math.exp(xv):.0f})"
            draw.text((gx - 38, py1 + 10), lbl, fill="#475569", font=f_tick)

    for yv in np.arange(math.ceil(ymin * 2) / 2, math.floor(ymax * 2) / 2 + 0.25, 0.5):
        _, gy = to_pt(xmin, yv)
        if py0 <= gy <= py1:
            draw.line([(px0, gy), (px1, gy)], fill="#E2E8F0", width=1)
            lbl = f"{yv:.1f} (${math.exp(yv):.0f})"
            draw.text((32, gy - 10), lbl, fill="#475569", font=f_tick)

    # Línea identidad 1:1 referencial
    id_min = max(xmin, ymin)
    id_max = min(xmax, ymax)
    draw.line([to_pt(id_min, id_min), to_pt(id_max, id_max)], fill="#94A3B8", width=2)

    # Puntos observados
    for xv, yv in zip(x, y):
        ux, uy = to_pt(float(xv), float(yv))
        draw.ellipse([ux - 6, uy - 6, ux + 6, uy + 6], fill="#2563EB", outline="#1E3A8A", width=1)

    # Recta de regresión OLS
    rx0, ry0 = xmin + 0.1, b0 + b1 * (xmin + 0.1)
    rx1, ry1 = xmax - 0.1, b0 + b1 * (xmax - 0.1)
    draw.line([to_pt(rx0, ry0), to_pt(rx1, ry1)], fill="#DC2626", width=4)

    draw.text((px0 + 210, py1 + 48), "ln(P2_PROM) — Valor en Permisos OPAMSS 2020–2026 [ln(USD/m²)]", fill="#0F172A", font=f_axis)
    draw.text((px0, py0 - 34), "ln(VAL_MKT25) — Oferta Inmobiliaria 2025 [ln(USD/m²)]", fill="#0F172A", font=f_axis)

    # Tarjeta derecha con ecuación y parámetros
    cx0, cy0, cx1, cy1 = 1155, 150, 1570, 865
    draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=12, fill="#EEF2FF", outline="#000A62", width=2)
    f_card_h = load_font(23, bold=True)
    f_card_b = load_font(18, bold=True)
    f_card_t = load_font(17)
    f_mono = load_font(18, bold=True, mono=True)

    draw.text((cx0 + 22, cy0 + 22), "Parámetros de Armonización", fill="#000A62", font=f_card_h)
    draw.text((cx0 + 22, cy0 + 62), "Ecuación estructural log-OLS:", fill="#1E293B", font=f_card_b)
    draw.rounded_rectangle([cx0 + 20, cy0 + 92, cx1 - 20, cy0 + 168], radius=8, fill="#FFFFFF", outline="#CBD5E1")
    draw.text((cx0 + 32, cy0 + 104), "ln(MKT25) = 2.8070", fill="#DC2626", font=f_mono)
    draw.text((cx0 + 32, cy0 + 134), "          + 0.4943 * ln(P2_PROM)", fill="#DC2626", font=f_mono)

    stats_lines = [
        ("UPDs traslapadas (n):", f"{len(sub)} polígonos"),
        ("Correlación r (log):", f"{r_val:.3f} (p < 0.0001)"),
        ("Factor Duan smearing:", f"{duan:.4f}"),
        ("Razón mediana MKT/P2:", "1.527x sobre P2_PROM"),
        ("UPDs rescatadas:", "+16 UPDs sin scraping"),
        ("Total VAL_FUS25:", "281 UPDs entrenables"),
    ]
    yy = cy0 + 188
    for k, v in stats_lines:
        draw.text((cx0 + 22, yy), k, fill="#334155", font=f_card_b)
        draw.text((cx0 + 22, yy + 22), v, fill="#0F766E", font=f_card_t)
        yy += 54

    draw.rounded_rectangle([cx0 + 20, cy1 - 158, cx1 - 20, cy1 - 20], radius=8, fill="#FFFBEB", outline="#F59E0B")
    draw.text((cx0 + 32, cy1 - 146), "Interpretación económica:", fill="#92400E", font=f_card_b)
    note_lines = [
        "La oferta comercial 2025 supera",
        "sistemáticamente al valor declarado",
        "en trámites; la calibración alinea",
        "ambas fuentes sin salto de escala.",
    ]
    ny = cy1 - 118
    for nl in note_lines:
        draw.text((cx0 + 32, ny), nl, fill="#78350F", font=load_font(17))
        ny += 24

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def create_fig4_mesh_results(malla_gdf: gpd.GeoDataFrame, perim_gdf: gpd.GeoDataFrame) -> bytes:
    """Mapa de resultados empíricos de la Malla Continua de 250 m (24,292 celdas, 1700 x 1100 px)."""
    W, H = 1700, 1100
    img = Image.new("RGB", (W, H), "#F8FAFC")
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([25, 20, W - 25, 102], radius=12, fill="#0C1659")
    draw.rectangle([25, 94, W - 25, 102], fill="#FFC800")
    f_title = load_font(30, bold=True)
    f_sub = load_font(19)
    draw.text((52, 32), "Resultados del Modelo GEE: Malla Continua de Valor del Suelo a 250 m (USD/m²)", fill="#FFFFFF", font=f_title)
    draw.text((52, 66), "24,292 polígonos continuos (148,875 ha) estimados mediante Google Satellite Embeddings V1 + Capas Físicas EO", fill="#E2E8F0", font=f_sub)

    malla_utm = malla_gdf.to_crs(epsg=32616)
    perim_utm = perim_gdf.to_crs(epsg=32616)

    minx, miny, maxx, maxy = perim_utm.total_bounds
    map_x0, map_y0, map_x1, map_y1 = 55, 130, 1175, 1050
    avail_w = map_x1 - map_x0
    avail_h = map_y1 - map_y0
    scale = min(avail_w / (maxx - minx), avail_h / (maxy - miny)) * 0.94
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    px_center = (map_x0 + map_x1) / 2.0
    py_center = (map_y0 + map_y1) / 2.0

    def to_px(x: float, y: float) -> tuple[float, float]:
        return (px_center + (x - cx) * scale, py_center - (y - cy) * scale)

    draw.rounded_rectangle([map_x0 - 15, map_y0 - 10, map_x1 + 15, map_y1 + 15], radius=12, fill="#FFFFFF", outline="#CBD5E1", width=2)

    def val_to_hex(v: float) -> str:
        if v <= 30.0:
            return "#FEF0D9"
        if v <= 50.0:
            return "#FDD49E"
        if v <= 100.0:
            return "#FDBB84"
        if v <= 175.0:
            return "#FC8D59"
        if v <= 300.0:
            return "#E34A33"
        return "#990000"

    for geom, val in zip(malla_utm.geometry, malla_utm["VAL_EST_M2"].to_numpy(dtype=float)):
        if geom is None or geom.is_empty:
            continue
        col = val_to_hex(float(val))
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms) if geom.geom_type == "MultiPolygon" else []
        for poly in polys:
            pts = [to_px(x, y) for x, y in poly.exterior.coords]
            if len(pts) >= 3:
                draw.polygon(pts, fill=col)

    for g in perim_utm.geometry:
        polys = [g] if g.geom_type == "Polygon" else list(g.geoms) if g.geom_type == "MultiPolygon" else []
        for poly in polys:
            pts = [to_px(x, y) for x, y in poly.exterior.coords]
            if len(pts) >= 3:
                draw.line(pts + [pts[0]], fill="#000A62", width=3)

    lx0, ly0, lx1, ly1 = 1210, 130, 1665, 1050
    draw.rounded_rectangle([lx0, ly0, lx1, ly1], radius=12, fill="#FFFFFF", outline="#CBD5E1", width=2)

    f_sec = load_font(23, bold=True)
    f_lbl = load_font(18, bold=True)
    f_txt = load_font(17)

    draw.text((lx0 + 22, ly0 + 22), "Escala Homologada (VAL_EST_M2)", fill="#000A62", font=f_sec)
    ranges = [
        ("#FEF0D9", "≤ $30 / m²", "8,557 celdas (35.2% · rural/reserva)"),
        ("#FDD49E", "$30 – $50 / m²", "11,225 celdas (46.2% · periferia)"),
        ("#FDBB84", "$50 – $100 / m²", "2,215 celdas (9.1% · transición)"),
        ("#FC8D59", "$100 – $175 / m²", "1,218 celdas (5.0% · pericentral)"),
        ("#E34A33", "$175 – $300 / m²", "836 celdas (3.4% · alta renta)"),
        ("#990000", "> $300 / m²", "241 celdas (1.0% · nodos prime)"),
    ]
    yy = ly0 + 66
    for col, r_lbl, r_desc in ranges:
        draw.rounded_rectangle([lx0 + 22, yy, lx0 + 58, yy + 30], radius=5, fill=col, outline="#334155", width=1)
        draw.text((lx0 + 70, yy - 3), r_lbl, fill="#0F172A", font=f_lbl)
        draw.text((lx0 + 70, yy + 19), r_desc, fill="#475569", font=f_txt)
        yy += 58

    draw.line([(lx0 + 22, yy + 8), (lx1 - 22, yy + 8)], fill="#CBD5E1", width=2)
    yy += 26
    draw.text((lx0 + 22, yy), "Síntesis Estadística Obtenida", fill="#000A62", font=f_sec)
    yy += 40

    kpis = [
        ("Cobertura sin vacíos:", "24,292 celdas (100% AMSS)"),
        ("Mediana metropolitana:", "$32.47/m² (Media: $50.04/m²)"),
        ("Urbano consolidado:", "2,215 celdas · Media $187.27/m²"),
        ("Periurbano transición:", "1,571 celdas · Media $74.35/m²"),
        ("Rural / reserva volcánica:", "20,506 celdas · Media $33.35/m²"),
        ("Máximo malla (6.25 ha):", "$375.90/m² (San Benito / Escalón)"),
        ("Máximo píxel puro (20 m):", "$471.13/m² (3.85 M píxeles)"),
    ]
    for k, v in kpis:
        draw.text((lx0 + 22, yy), k, fill="#334155", font=f_lbl)
        draw.text((lx0 + 22, yy + 21), v, fill="#0F766E", font=f_txt)
        yy += 56

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def create_fig5_correlations(corr_df: pd.DataFrame) -> bytes:
    """Gráfico de barras divergentes de las 22 bandas con mayor correlación |r| de Pearson (1650 x 1020 px)."""
    W, H = 1650, 1020
    img = Image.new("RGB", (W, H), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([25, 20, W - 25, 100], radius=12, fill="#0C1659")
    draw.rectangle([25, 92, W - 25, 100], fill="#FFC800")
    f_title = load_font(28, bold=True)
    f_sub = load_font(19)
    draw.text((50, 31), "Poder Explicativo Satelital: Top 22 Predictores frente a ln(Valor del Suelo)", fill="#FFFFFF", font=f_title)
    draw.text((50, 64), "Correlación r de Pearson sobre muestra urbana intra-UPD (64 de las 71 bandas son significativas con p < 0.05)", fill="#E2E8F0", font=f_sub)

    # Seleccionar top 16 embeddings + todas las 6 físicas significativas para visión integral (22 barras)
    top_emb = corr_df[corr_df["grupo"] == "Google_Embedding"].nlargest(16, "abs_r")
    phys_all = corr_df[corr_df["grupo"] == "Fisica_EO"]
    plot_df = pd.concat([top_emb, phys_all], ignore_index=True).drop_duplicates(subset=["banda"]).sort_values("abs_r", ascending=False).head(22)

    px0, py0, px1, py1 = 240, 145, 1130, 955
    draw.rectangle([px0, py0, px1, py1], fill="#F8FAFC", outline="#CBD5E1", width=2)

    zero_x = (px0 + px1) / 2.0
    max_r = 0.80
    half_w = (px1 - px0) / 2.0

    f_tick = load_font(16)
    f_lbl = load_font(17, bold=True, mono=True)
    f_val = load_font(16, bold=True)

    for tick in (-0.7, -0.5, -0.3, 0.0, 0.3, 0.5, 0.7):
        tx = zero_x + (tick / max_r) * half_w
        col_l = "#64748B" if tick == 0.0 else "#E2E8F0"
        w_l = 2 if tick == 0.0 else 1
        draw.line([(tx, py0), (tx, py1)], fill=col_l, width=w_l)
        draw.text((tx - 18, py1 + 10), f"{tick:+.1f}", fill="#475569", font=f_tick)

    n_bars = len(plot_df)
    row_h = (py1 - py0 - 24) / float(n_bars)

    label_aliases = {
        "wc_trees": "wc_trees (Árboles)",
        "wc_built": "wc_built (Edif.)",
        "viirs_rad": "viirs_rad (VIIRS)",
        "dem_slope": "dem_slope (Pend.)",
        "ob_pres": "ob_pres (2.5D)",
        "ob_height": "ob_height (Altura)",
        "dem_elev": "dem_elev (Altitud)",
    }

    for idx, (_, row) in enumerate(plot_df.iterrows()):
        cy = py0 + 14 + idx * row_h + row_h / 2.0
        r_v = float(row["r_pearson"])
        b_name = str(row["banda"])
        is_phys = str(row["grupo"]) == "Fisica_EO"

        disp_name = label_aliases.get(b_name, f"Emb {b_name}")
        draw.text((38, cy - 10), disp_name, fill="#000A62" if is_phys else "#1E293B", font=f_lbl)

        bx = zero_x + (r_v / max_r) * half_w
        x_left, x_right = (zero_x, bx) if r_v >= 0 else (bx, zero_x)
        if is_phys:
            fill_c = "#D97706" if r_v >= 0 else "#0D9488"
        else:
            fill_c = "#1D4ED8" if r_v >= 0 else "#6366F1"

        draw.rounded_rectangle([x_left, cy - row_h * 0.34, x_right, cy + row_h * 0.34], radius=4, fill=fill_c)
        val_txt = f"{r_v:+.3f}"
        if r_v >= 0:
            draw.text((x_right + 8, cy - 9), val_txt, fill="#0F172A", font=f_val)
        else:
            draw.text((x_left - 62, cy - 9), val_txt, fill="#0F172A", font=f_val)

    # Panel lateral interpretativo
    cx0, cy0, cx1, cy1 = 1165, 145, 1620, 955
    draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=12, fill="#EEF2FF", outline="#000A62", width=2)
    f_ch = load_font(22, bold=True)
    f_cb = load_font(18, bold=True)
    f_ct = load_font(17)

    draw.text((cx0 + 22, cy0 + 22), "Lectura de Correlaciones", fill="#000A62", font=f_ch)

    leg_chips = [
        ("#1D4ED8", "Google Embedding (+r con valor)"),
        ("#6366F1", "Google Embedding (-r con valor)"),
        ("#D97706", "Capa Física EO (+r urbanización)"),
        ("#0D9488", "Capa Física EO (-r pendiente/bosque)"),
    ]
    yy = cy0 + 66
    for c_hex, c_txt in leg_chips:
        draw.rounded_rectangle([cx0 + 22, yy, cx0 + 50, yy + 22], radius=4, fill=c_hex)
        draw.text((cx0 + 62, yy + 1), c_txt, fill="#1E293B", font=f_ct)
        yy += 36

    draw.line([(cx0 + 22, yy + 8), (cx1 - 22, yy + 8)], fill="#CBD5E1", width=2)
    yy += 26
    findings = [
        ("1. Dominio de Embeddings V1:", [
            "Las dimensiones A13 (r = -0.694),",
            "A32 (r = -0.660) y A34 (r = +0.650)",
            "superan a cualquier índice aislado,",
            "capturando morfología y grano vial.",
        ]),
        ("2. Consistencia biofísica:", [
            "La huella construida (wc_built +0.621)",
            "y la luz nocturna VIIRS (+0.578)",
            "capitalizan centralidad; la pendiente",
            "(dem_slope -0.472) penaliza laderas.",
        ]),
        ("3. Altitud no lineal (dem_elev):", [
            "Correlación lineal nula (r = +0.075,",
            "p = 0.21) pues coexisten polos caros",
            "en meseta alta (Escalón/Sta. Elena)",
            "con laderas volcánicas rurales.",
        ]),
    ]
    for head_t, lines_t in findings:
        draw.text((cx0 + 22, yy), head_t, fill="#000A62", font=f_cb)
        yy += 26
        for lt in lines_t:
            draw.text((cx0 + 22, yy), lt, fill="#334155", font=f_ct)
            yy += 23
        yy += 18

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def create_fig6_evaluation_and_typologies(upd_res_gdf: gpd.GeoDataFrame, malla_gdf: gpd.GeoDataFrame) -> bytes:
    """Panel dual: (Izq) Desempeño Observado vs Modelo en 281 UPDs; (Der) Gradiente por Tipología Urbana (1680 x 920 px)."""
    W, H = 1680, 920
    img = Image.new("RGB", (W, H), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([25, 20, W - 25, 100], radius=12, fill="#0C1659")
    draw.rectangle([25, 92, W - 25, 100], fill="#FFC800")
    f_title = load_font(28, bold=True)
    f_sub = load_font(19)
    draw.text((50, 31), "Evaluación Empírica del Modelo y Gradiente Estructural por Tipología Territorial", fill="#FFFFFF", font=f_title)
    draw.text((50, 64), "Concordancia en las 281 UPDs observadas (mediana $102.84 vs. $103.66/m²) y diferenciación en las 24,292 celdas de la malla", fill="#E2E8F0", font=f_sub)

    # --- PANEL IZQUIERDO: Observado vs Modelo en UPDs ---
    obs = upd_res_gdf[(upd_res_gdf["ORIGEN_FIN"] == "OBSERVADO") & (upd_res_gdf["VAL_FIN_M2"] > 0) & (upd_res_gdf["VAL_MOD_M2"] > 0)].copy()
    x = np.log(obs["VAL_FIN_M2"].to_numpy(dtype=float))
    y = np.log(obs["VAL_MOD_M2"].to_numpy(dtype=float))
    r_lin = float(np.corrcoef(obs["VAL_FIN_M2"], obs["VAL_MOD_M2"])[0, 1])
    r_log = float(np.corrcoef(x, y)[0, 1])

    lx0, ly0, lx1, ly1 = 115, 165, 815, 815
    draw.rectangle([lx0, ly0, lx1, ly1], fill="#F8FAFC", outline="#94A3B8", width=2)
    f_phead = load_font(22, bold=True)
    f_tick = load_font(16)
    f_axis = load_font(19, bold=True)
    draw.text((lx0, ly0 - 36), "A. Ajuste Zonal en UPDs Observadas (n = 281 · escala ln)", fill="#000A62", font=f_phead)

    vmin, vmax = 1.5, 6.7
    def to_lpt(xv: float, yv: float) -> tuple[float, float]:
        ux = lx0 + (xv - vmin) / (vmax - vmin) * (lx1 - lx0)
        uy = ly1 - (yv - vmin) / (vmax - vmin) * (ly1 - ly0)
        return (ux, uy)

    for tv in (2.0, 3.0, 4.0, 5.0, 6.0):
        gx, _ = to_lpt(tv, vmin)
        _, gy = to_lpt(vmin, tv)
        draw.line([(gx, ly0), (gx, ly1)], fill="#E2E8F0", width=1)
        draw.line([(lx0, gy), (lx1, gy)], fill="#E2E8F0", width=1)
        lbl = f"{tv:.0f} (${math.exp(tv):.0f})"
        draw.text((gx - 30, ly1 + 8), lbl, fill="#475569", font=f_tick)
        draw.text((28, gy - 9), lbl, fill="#475569", font=f_tick)

    # Identidad 1:1
    draw.line([to_lpt(vmin, vmin), to_lpt(vmax, vmax)], fill="#DC2626", width=3)

    for xv, yv in zip(x, y):
        ux, uy = to_lpt(max(vmin + 0.05, float(xv)), max(vmin + 0.05, float(yv)))
        draw.ellipse([ux - 5, uy - 5, ux + 5, uy + 5], fill="#0F766E", outline="#115E59", width=1)

    draw.text((lx0 + 115, ly1 + 42), "ln(VAL_FIN_M2) — Valor Observado [USD/m²]", fill="#0F172A", font=f_axis)
    draw.rounded_rectangle([lx0 + 18, ly0 + 18, lx0 + 355, ly0 + 132], radius=8, fill="#FFFFFF", outline="#CBD5E1")
    draw.text((lx0 + 30, ly0 + 28), f"Correlación lineal r = {r_lin:.3f}", fill="#000A62", font=load_font(17, bold=True))
    draw.text((lx0 + 30, ly0 + 54), f"Correlación log r = {r_log:.3f}", fill="#0F766E", font=load_font(17, bold=True))
    draw.text((lx0 + 30, ly0 + 80), "Mediana Obs: $103.66 vs Mod: $102.84", fill="#334155", font=load_font(16))
    draw.text((lx0 + 30, ly0 + 103), "Línea roja: Identidad exacta 1:1", fill="#DC2626", font=load_font(15))

    # --- PANEL DERECHO: Gradiente por Tipología de Suelo ---
    rx0, ry0, rx1, ry1 = 900, 165, 1630, 815
    draw.rounded_rectangle([rx0, ry0, rx1, ry1], radius=12, fill="#F8FAFC", outline="#94A3B8", width=2)
    draw.text((rx0, ry0 - 36), "B. Gradiente de Valor por Tipología en Malla 250 m", fill="#000A62", font=f_phead)

    typologies = [
        ("URBANO_CONSOLIDADO", "Urbano Consolidado (≥45% edif.)", "#B91C1C", "#FEE2E2"),
        ("PERIURBANO_TRANSICION", "Periurbano en Transición (10–45%)", "#D97706", "#FEF3C7"),
        ("RURAL_RESERVA", "Rural y Reserva Ambiental (<10%)", "#0F766E", "#CCFBF1"),
    ]

    cy_card = ry0 + 28
    max_bar_usd = 330.0
    bar_area_w = 640

    for t_key, t_title, c_main, c_bg in typologies:
        sub_t = malla_gdf[malla_gdf["TIPO_SUELO"] == t_key]
        n_c = len(sub_t)
        area_h = float(sub_t["AREA_HA"].sum())
        v_med = float(sub_t["VAL_EST_M2"].median())
        v_mean = float(sub_t["VAL_EST_M2"].mean())
        v_p90 = float(sub_t["VAL_EST_M2"].quantile(0.90))
        edif_m = float(sub_t["FRAC_EDIF"].mean()) * 100.0
        alt_m = float(sub_t["ALT_EDIF_M"].mean())
        pend_m = float(sub_t["PEND_DEG"].mean())

        draw.rounded_rectangle([rx0 + 24, cy_card, rx1 - 24, cy_card + 188], radius=10, fill="#FFFFFF", outline=c_main, width=2)
        draw.rounded_rectangle([rx0 + 24, cy_card, rx1 - 24, cy_card + 44], radius=10, fill=c_bg)
        draw.text((rx0 + 40, cy_card + 10), f"{t_title}  ·  {n_c:,} celdas ({area_h:,.0f} ha)", fill="#0F172A", font=load_font(18, bold=True))

        # Barras comparativas de Mediana, Media y P90
        bars_spec = [
            ("Mediana:", v_med, c_main),
            ("Promedio:", v_mean, "#1E3A8A"),
            ("Percentil 90:", v_p90, "#475569"),
        ]
        by = cy_card + 56
        for b_lbl, b_val, b_col in bars_spec:
            draw.text((rx0 + 40, by), b_lbl, fill="#334155", font=load_font(16, bold=True))
            bw = max(8, int((min(b_val, max_bar_usd) / max_bar_usd) * 410))
            draw.rounded_rectangle([rx0 + 155, by + 2, rx0 + 155 + bw, by + 20], radius=4, fill=b_col)
            draw.text((rx0 + 165 + bw, by), f"${b_val:.2f}/m²", fill="#0F172A", font=load_font(16, bold=True))
            by += 30

        draw.text(
            (rx0 + 40, cy_card + 154),
            f"Morfología media: Edificado {edif_m:.1f}%  |  Altura 2.5D: {alt_m:.2f} m  |  Pendiente: {pend_m:.1f}°",
            fill="#475569",
            font=load_font(16),
        )
        cy_card += 205

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ==============================================================================
# 2. CONSTRUCTOR OPENXML (.DOCX) ESTRICTO Y ESTILIZADO
# ==============================================================================

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"


class DocxBuilder:
    def __init__(self) -> None:
        self.body_parts: list[str] = []
        self.media: list[tuple[str, bytes]] = []
        self.rels: list[tuple[str, str, str]] = [
            ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", "styles.xml"),
            ("rId2", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings", "settings.xml"),
            ("rId3", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header", "header1.xml"),
            ("rId4", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer", "footer1.xml"),
        ]
        self.next_rid = 5
        self.next_docpr_id = 1

    def _run_xml(
        self,
        text: str,
        bold: bool = False,
        italic: bool = False,
        color: str | None = None,
        size_pt: float | None = None,
        mono: bool = False,
    ) -> str:
        rpr: list[str] = []
        if mono:
            rpr.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>')
        if bold:
            rpr.append("<w:b/>")
        if italic:
            rpr.append("<w:i/>")
        if color:
            rpr.append(f'<w:color w:val="{color}"/>')
        if size_pt is not None:
            half_pt = int(round(size_pt * 2))
            rpr.append(f'<w:sz w:val="{half_pt}"/><w:szCs w:val="{half_pt}"/>')
        rpr_str = f"<w:rPr>{''.join(rpr)}</w:rPr>" if rpr else ""
        return f'<w:r>{rpr_str}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'

    def add_p(
        self,
        runs: str | list[tuple],
        style: str = "Normal",
        align: str = "both",
        space_before: int = 0,
        space_after: int = 140,
        line: int = 276,
        keep_next: bool = False,
        page_break_before: bool = False,
        indent_left: int = 0,
        indent_hanging: int = 0,
    ) -> None:
        ppr: list[str] = [f'<w:pStyle w:val="{style}"/>']
        if keep_next:
            ppr.append("<w:keepNext/>")
        if page_break_before:
            ppr.append("<w:pageBreakBefore/>")
        ppr.append(f'<w:spacing w:before="{space_before}" w:after="{space_after}" w:line="{line}" w:lineRule="auto"/>')
        if indent_left or indent_hanging:
            h_attr = f' w:hanging="{indent_hanging}"' if indent_hanging else ""
            ppr.append(f'<w:ind w:left="{indent_left}"{h_attr}/>')
        if align:
            ppr.append(f'<w:jc w:val="{align}"/>')

        if isinstance(runs, str):
            runs_xml = self._run_xml(runs)
        else:
            chunks = []
            for item in runs:
                txt = item[0]
                kw = item[1] if len(item) > 1 else {}
                chunks.append(self._run_xml(txt, **kw))
            runs_xml = "".join(chunks)

        self.body_parts.append(f"<w:p><w:pPr>{''.join(ppr)}</w:pPr>{runs_xml}</w:p>")

    def add_h1(self, num_str: str, title: str, page_break: bool = False) -> None:
        # Barra de acento institucional bajo el encabezado principal
        ppr = [
            '<w:pStyle w:val="Heading1"/>',
            "<w:keepNext/>",
        ]
        if page_break:
            ppr.append("<w:pageBreakBefore/>")
        ppr.append(
            f'<w:pBdr><w:bottom w:val="single" w:sz="12" w:space="4" w:color="{HEX_ACCENT_YELLOW}"/></w:pBdr>'
        )
        ppr.append('<w:spacing w:before="320" w:after="160" w:line="260" w:lineRule="auto"/>')
        r1 = self._run_xml(f"{num_str}  ", bold=True, color=HEX_TEAL, size_pt=16)
        r2 = self._run_xml(title, bold=True, color=HEX_BRAND_BLUE, size_pt=16)
        self.body_parts.append(f"<w:p><w:pPr>{''.join(ppr)}</w:pPr>{r1}{r2}</w:p>")

    def add_h2(self, title: str) -> None:
        self.add_p(
            [(title, {"bold": True, "color": HEX_COVER_BLUE, "size_pt": 13})],
            style="Heading2",
            align="left",
            space_before=240,
            space_after=100,
            keep_next=True,
        )

    def add_h3(self, title: str) -> None:
        self.add_p(
            [(title, {"bold": True, "color": HEX_TEAL, "size_pt": 11.5})],
            style="Heading3",
            align="left",
            space_before=180,
            space_after=80,
            keep_next=True,
        )

    def add_bullet(self, lead_bold: str, text: str) -> None:
        runs = [
            ("▪  ", {"bold": True, "color": HEX_TEAL}),
        ]
        if lead_bold:
            runs.append((lead_bold + " ", {"bold": True, "color": HEX_SLATE_DARK}))
        runs.append((text, {"color": HEX_SLATE_DARK}))
        self.add_p(runs, align="both", space_before=20, space_after=90, indent_left=420, indent_hanging=240)

    def add_formula_box(self, formula_lines: list[str], caption: str | None = None) -> None:
        rows_p = []
        for fl in formula_lines:
            r = self._run_xml(fl, bold=True, color=HEX_BRAND_BLUE, size_pt=10.5, mono=True)
            rows_p.append(
                f'<w:p><w:pPr><w:spacing w:before="40" w:after="40" w:line="260" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>{r}</w:p>'
            )
        if caption:
            rc = self._run_xml(caption, italic=True, color=HEX_SLATE_MUTED, size_pt=9.5)
            rows_p.append(
                f'<w:p><w:pPr><w:spacing w:before="60" w:after="20" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr>{rc}</w:p>'
            )

        tbl = f"""
        <w:tbl>
          <w:tblPr>
            <w:tblW w:w="9360" w:type="dxa"/>
            <w:jc w:val="center"/>
            <w:tblBorders>
              <w:top w:val="single" w:sz="6" w:space="0" w:color="{HEX_BORDER}"/>
              <w:left w:val="single" w:sz="24" w:space="0" w:color="{HEX_BRAND_BLUE}"/>
              <w:bottom w:val="single" w:sz="6" w:space="0" w:color="{HEX_BORDER}"/>
              <w:right w:val="single" w:sz="6" w:space="0" w:color="{HEX_BORDER}"/>
            </w:tblBorders>
            <w:tblCellMar>
              <w:top w:w="140" w:type="dxa"/>
              <w:left w:w="220" w:type="dxa"/>
              <w:bottom w:w="140" w:type="dxa"/>
              <w:right w:w="220" w:type="dxa"/>
            </w:tblCellMar>
          </w:tblPr>
          <w:tblGrid><w:gridCol w:w="9360"/></w:tblGrid>
          <w:tr>
            <w:tc>
              <w:tcPr>
                <w:tcW w:w="9360" w:type="dxa"/>
                <w:shd w:val="clear" w:color="auto" w:fill="{HEX_BG_LIGHT}"/>
              </w:tcPr>
              {''.join(rows_p)}
            </w:tc>
          </w:tr>
        </w:tbl>
        """
        self.body_parts.append(tbl)
        self.add_p("", space_before=0, space_after=100)

    def add_callout(self, title: str, body_text: str, accent_hex: str = HEX_TEAL, bg_hex: str = HEX_BG_CALLOUT) -> None:
        p1 = (
            f'<w:p><w:pPr><w:spacing w:before="20" w:after="60" w:line="250" w:lineRule="auto"/></w:pPr>'
            f'{self._run_xml(title, bold=True, color=HEX_BRAND_BLUE, size_pt=10.5)}</w:p>'
        )
        p2 = (
            f'<w:p><w:pPr><w:spacing w:before="0" w:after="20" w:line="255" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>'
            f'{self._run_xml(body_text, color=HEX_SLATE_DARK, size_pt=10)}</w:p>'
        )
        tbl = f"""
        <w:tbl>
          <w:tblPr>
            <w:tblW w:w="9360" w:type="dxa"/>
            <w:jc w:val="center"/>
            <w:tblBorders>
              <w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>
              <w:left w:val="single" w:sz="28" w:space="0" w:color="{accent_hex}"/>
              <w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto"/>
              <w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>
            </w:tblBorders>
            <w:tblCellMar>
              <w:top w:w="130" w:type="dxa"/>
              <w:left w:w="200" w:type="dxa"/>
              <w:bottom w:w="130" w:type="dxa"/>
              <w:right w:w="180" w:type="dxa"/>
            </w:tblCellMar>
          </w:tblPr>
          <w:tblGrid><w:gridCol w:w="9360"/></w:tblGrid>
          <w:tr>
            <w:tc>
              <w:tcPr>
                <w:tcW w:w="9360" w:type="dxa"/>
                <w:shd w:val="clear" w:color="auto" w:fill="{bg_hex}"/>
              </w:tcPr>
              {p1}{p2}
            </w:tc>
          </w:tr>
        </w:tbl>
        """
        self.body_parts.append(tbl)
        self.add_p("", space_before=0, space_after=100)

    def add_table(self, headers: list[str], rows: list[list[str]], col_widths_pct: list[int], mono_cols: set[int] | None = None) -> None:
        mono_cols = mono_cols or set()
        total_dxa = 9360
        col_dxa = [int(round(total_dxa * p / 100.0)) for p in col_widths_pct]
        col_dxa[-1] = total_dxa - sum(col_dxa[:-1])

        grid_xml = "".join(f'<w:gridCol w:w="{w}"/>' for w in col_dxa)

        # Fila de encabezado
        h_cells = []
        for h_txt, w in zip(headers, col_dxa):
            p = (
                f'<w:p><w:pPr><w:spacing w:before="20" w:after="20" w:line="240" w:lineRule="auto"/><w:jc w:val="left"/></w:pPr>'
                f'{self._run_xml(h_txt, bold=True, color="FFFFFF", size_pt=9.5)}</w:p>'
            )
            h_cells.append(
                f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>'
                f'<w:shd w:val="clear" w:color="auto" w:fill="{HEX_COVER_BLUE}"/>'
                f'<w:vAlign w:val="center"/></w:tcPr>{p}</w:tc>'
            )
        tr_list = [f"<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>{''.join(h_cells)}</w:tr>"]

        # Filas de datos con cebreado suave
        for r_idx, row in enumerate(rows):
            fill = "FFFFFF" if r_idx % 2 == 0 else "F8FAFC"
            d_cells = []
            for c_idx, (cell_txt, w) in enumerate(zip(row, col_dxa)):
                is_mono = c_idx in mono_cols
                is_first = c_idx == 0
                p = (
                    f'<w:p><w:pPr><w:spacing w:before="20" w:after="20" w:line="240" w:lineRule="auto"/><w:jc w:val="left"/></w:pPr>'
                    f'{self._run_xml(cell_txt, bold=is_first, color=HEX_SLATE_DARK, size_pt=9.0 if is_mono else 9.5, mono=is_mono)}</w:p>'
                )
                d_cells.append(
                    f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>'
                    f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/>'
                    f'<w:vAlign w:val="top"/></w:tcPr>{p}</w:tc>'
                )
            tr_list.append(f"<w:tr><w:trPr><w:cantSplit/></w:trPr>{''.join(d_cells)}</w:tr>")

        tbl_xml = f"""
        <w:tbl>
          <w:tblPr>
            <w:tblW w:w="{total_dxa}" w:type="dxa"/>
            <w:jc w:val="center"/>
            <w:tblBorders>
              <w:top w:val="single" w:sz="8" w:space="0" w:color="{HEX_COVER_BLUE}"/>
              <w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>
              <w:bottom w:val="single" w:sz="10" w:space="0" w:color="{HEX_COVER_BLUE}"/>
              <w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>
              <w:insideH w:val="single" w:sz="4" w:space="0" w:color="{HEX_BORDER}"/>
              <w:insideV w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
            </w:tblBorders>
            <w:tblCellMar>
              <w:top w:w="90" w:type="dxa"/>
              <w:left w:w="120" w:type="dxa"/>
              <w:bottom w:w="90" w:type="dxa"/>
              <w:right w:w="120" w:type="dxa"/>
            </w:tblCellMar>
          </w:tblPr>
          <w:tblGrid>{grid_xml}</w:tblGrid>
          {''.join(tr_list)}
        </w:tbl>
        """
        self.body_parts.append(tbl_xml)
        self.add_p("", space_before=0, space_after=110)

    def add_image(self, png_bytes: bytes, filename: str, width_inches: float, caption: str) -> None:
        with Image.open(io.BytesIO(png_bytes)) as im:
            px_w, px_h = im.size
        aspect = px_h / float(px_w)
        cx = int(round(width_inches * 914400))
        cy = int(round(cx * aspect))

        rid = f"rId{self.next_rid}"
        self.next_rid += 1
        docpr_id = self.next_docpr_id
        self.next_docpr_id += 1

        self.media.append((filename, png_bytes))
        self.rels.append(
            (rid, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image", f"media/{filename}")
        )

        drawing_xml = f"""
        <w:p>
          <w:pPr>
            <w:keepNext/>
            <w:spacing w:before="140" w:after="60"/>
            <w:jc w:val="center"/>
          </w:pPr>
          <w:r>
            <w:drawing>
              <wp:inline distT="0" distB="0" distL="0" distR="0">
                <wp:extent cx="{cx}" cy="{cy}"/>
                <wp:effectExtent l="0" t="0" r="0" b="0"/>
                <wp:docPr id="{docpr_id}" name="Figura_{docpr_id}" descr="{escape(caption)}"/>
                <wp:cNvGraphicFramePr>
                  <a:graphicFrameLocks noChangeAspect="1"/>
                </wp:cNvGraphicFramePr>
                <a:graphic>
                  <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                    <pic:pic>
                      <pic:nvPicPr>
                        <pic:cNvPr id="{docpr_id}" name="{escape(filename)}"/>
                        <pic:cNvPicPr/>
                      </pic:nvPicPr>
                      <pic:blipFill>
                        <a:blip r:embed="{rid}"/>
                        <a:stretch><a:fillRect/></a:stretch>
                      </pic:blipFill>
                      <pic:spPr>
                        <a:xfrm>
                          <a:off x="0" y="0"/>
                          <a:ext cx="{cx}" cy="{cy}"/>
                        </a:xfrm>
                        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                      </pic:spPr>
                    </pic:pic>
                  </a:graphicData>
                </a:graphic>
              </wp:inline>
            </w:drawing>
          </w:r>
        </w:p>
        """
        self.body_parts.append(drawing_xml)
        self.add_p(
            [(caption, {"italic": True, "color": HEX_SLATE_MUTED, "size_pt": 9.5})],
            align="center",
            space_before=0,
            space_after=180,
        )

    def add_cover_banner(self) -> None:
        banner_tbl = f"""
        <w:tbl>
          <w:tblPr>
            <w:tblW w:w="9360" w:type="dxa"/>
            <w:jc w:val="center"/>
            <w:tblBorders>
              <w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>
              <w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>
              <w:bottom w:val="single" w:sz="36" w:space="0" w:color="{HEX_ACCENT_YELLOW}"/>
              <w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>
            </w:tblBorders>
            <w:tblCellMar>
              <w:top w:w="340" w:type="dxa"/>
              <w:left w:w="320" w:type="dxa"/>
              <w:bottom w:w="340" w:type="dxa"/>
              <w:right w:w="320" w:type="dxa"/>
            </w:tblCellMar>
          </w:tblPr>
          <w:tblGrid><w:gridCol w:w="9360"/></w:tblGrid>
          <w:tr>
            <w:tc>
              <w:tcPr>
                <w:tcW w:w="9360" w:type="dxa"/>
                <w:shd w:val="clear" w:color="auto" w:fill="{HEX_COVER_BLUE}"/>
              </w:tcPr>
              <w:p>
                <w:pPr><w:spacing w:before="0" w:after="100"/></w:pPr>
                {self._run_xml("COMUNIDAD URBANA COPERNICUS CENTROAMÉRICA · INICIATIVA SV-AMSS", bold=True, color=HEX_ACCENT_YELLOW, size_pt=10)}
              </w:p>
              <w:p>
                <w:pPr><w:spacing w:before="40" w:after="140" w:line="280" w:lineRule="auto"/></w:pPr>
                {self._run_xml("Metodología del Modelo Espacial de Valor del Suelo a Nivel de Píxel y Asociación a Malla Continua de Polígonos en el AMSS", bold=True, color="FFFFFF", size_pt=20)}
              </w:p>
              <w:p>
                <w:pPr><w:spacing w:before="0" w:after="60" w:line="260" w:lineRule="auto"/></w:pPr>
                {self._run_xml("Integración geoestadística de registros de permisos OPAMSS (2007–2026), oferta inmobiliaria por web scraping (2025), Google Satellite Embeddings V1 y Observación de la Tierra en Google Earth Engine", italic=True, color="E2E8F0", size_pt=11.5)}
              </w:p>
            </w:tc>
          </w:tr>
        </w:tbl>
        """
        self.body_parts.append(banner_tbl)
        self.add_p("", space_before=0, space_after=180)

    def save(self, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)

        sect_pr = """
        <w:sectPr>
          <w:headerReference w:type="default" r:id="rId3"/>
          <w:footerReference w:type="default" r:id="rId4"/>
          <w:pgSz w:w="12240" w:h="15840"/>
          <w:pgMar w:top="1360" w:right="1440" w:bottom="1360" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
          <w:titlePg/>
        </w:sectPr>
        """

        document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W_NS}" xmlns:r="{R_NS}" xmlns:wp="{WP_NS}" xmlns:a="{A_NS}" xmlns:pic="{PIC_NS}">
  <w:body>
    {''.join(self.body_parts)}
    {sect_pr}
  </w:body>
</w:document>"""

        styles_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W_NS}">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
        <w:color w:val="{HEX_SLATE_DARK}"/>
        <w:sz w:val="21"/>
        <w:szCs w:val="21"/>
        <w:lang w:val="es-SV" w:eastAsia="en-US" w:bidi="ar-SA"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="120" w:line="276" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:keepNext/><w:outlineLvl w:val="0"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Calibri Light" w:hAnsi="Calibri Light" w:cs="Calibri Light"/>
      <w:b/>
      <w:color w:val="{HEX_BRAND_BLUE}"/>
      <w:sz w:val="32"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:keepNext/><w:outlineLvl w:val="1"/></w:pPr>
    <w:rPr>
      <w:rFonts w:ascii="Calibri Light" w:hAnsi="Calibri Light" w:cs="Calibri Light"/>
      <w:b/>
      <w:color w:val="{HEX_COVER_BLUE}"/>
      <w:sz w:val="26"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:keepNext/><w:outlineLvl w:val="2"/></w:pPr>
    <w:rPr>
      <w:b/>
      <w:color w:val="{HEX_TEAL}"/>
      <w:sz w:val="23"/>
    </w:rPr>
  </w:style>
</w:styles>"""

        settings_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="{W_NS}">
  <w:zoom w:percent="100"/>
  <w:defaultTabStop w:val="720"/>
  <w:characterSpacingControl w:val="doNotCompress"/>
</w:settings>"""

        header_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="{W_NS}">
  <w:p>
    <w:pPr>
      <w:pBdr><w:bottom w:val="single" w:sz="6" w:space="4" w:color="{HEX_BORDER}"/></w:pBdr>
      <w:spacing w:after="60"/>
      <w:jc w:val="right"/>
    </w:pPr>
    <w:r>
      <w:rPr><w:color w:val="{HEX_SLATE_MUTED}"/><w:sz w:val="17"/></w:rPr>
      <w:t>AMSS (sv-amss) · Metodología del Modelo Espacial de Valor del Suelo en Google Earth Engine</w:t>
    </w:r>
  </w:p>
</w:hdr>"""

        footer_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="{W_NS}">
  <w:p>
    <w:pPr>
      <w:pBdr><w:top w:val="single" w:sz="6" w:space="4" w:color="{HEX_BORDER}"/></w:pBdr>
      <w:spacing w:before="60" w:after="0"/>
      <w:jc w:val="center"/>
    </w:pPr>
    <w:r>
      <w:rPr><w:color w:val="{HEX_SLATE_MUTED}"/><w:sz w:val="17"/></w:rPr>
      <w:t xml:space="preserve">Clúster Urbano Copernicus Centroamérica · OPAMSS · Página </w:t>
    </w:r>
    <w:fldSimple w:instr="PAGE">
      <w:r><w:rPr><w:b/><w:color w:val="{HEX_BRAND_BLUE}"/><w:sz w:val="17"/></w:rPr><w:t>1</w:t></w:r>
    </w:fldSimple>
    <w:r>
      <w:rPr><w:color w:val="{HEX_SLATE_MUTED}"/><w:sz w:val="17"/></w:rPr>
      <w:t xml:space="preserve"> de </w:t>
    </w:r>
    <w:fldSimple w:instr="NUMPAGES">
      <w:r><w:rPr><w:b/><w:color w:val="{HEX_BRAND_BLUE}"/><w:sz w:val="17"/></w:rPr><w:t>1</w:t></w:r>
    </w:fldSimple>
  </w:p>
</w:ftr>"""

        rels_items = "".join(
            f'<Relationship Id="{rid}" Type="{rtype}" Target="{target}"/>'
            for rid, rtype, target in self.rels
        )
        doc_rels_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {rels_items}
</Relationships>"""

        root_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

        content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

        now_iso = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        core_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Metodología del Modelo Espacial de Valor del Suelo en el AMSS (Google Earth Engine)</dc:title>
  <dc:subject>Modelación geoestadística de valor de suelo, Google Satellite Embeddings, OPAMSS, AMSS</dc:subject>
  <dc:creator>Proyecto Urbano SV-AMSS · Comunidad Urbana Copernicus Centroamérica</dc:creator>
  <cp:keywords>AMSS, OPAMSS, Valor del Suelo, Google Satellite Embeddings, Random Forest, Google Earth Engine</cp:keywords>
  <dc:description>Documento metodológico reproducible para la estimación continua de valores de suelo a nivel de píxel y malla de polígonos en el Área Metropolitana de San Salvador.</dc:description>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:modified>
</cp:coreProperties>"""

        app_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>Copernicus Urbano SV-AMSS Document Generator</Application>
  <Company>Clúster de Asentamientos Humanos · Copernicus Centroamérica</Company>
</Properties>"""

        xml_files = {
            "[Content_Types].xml": content_types_xml,
            "_rels/.rels": root_rels_xml,
            "word/document.xml": document_xml,
            "word/styles.xml": styles_xml,
            "word/settings.xml": settings_xml,
            "word/header1.xml": header_xml,
            "word/footer1.xml": footer_xml,
            "word/_rels/document.xml.rels": doc_rels_xml,
            "docProps/core.xml": core_xml,
            "docProps/app.xml": app_xml,
        }

        # Validación sintáctica estricta de todos los XML antes de escribir el .docx
        for name, content in xml_files.items():
            ET.fromstring(content.encode("utf-8"))

        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for name, content in xml_files.items():
                zf.writestr(name, content.encode("utf-8"))
            for fname, img_bytes in self.media:
                zf.writestr(f"word/media/{fname}", img_bytes)


# ==============================================================================
# 3. REDACCIÓN INTEGRAL DEL CONTENIDO METODOLÓGICO
# ==============================================================================

def build_methodology_document() -> None:
    upd_gdf = gpd.read_file(f"zip://{ASSETS_DIR / 'amss_upd_suelo_entrenamiento.zip'}")
    perim_gdf = gpd.read_file(f"zip://{ASSETS_DIR / 'amss_perimetro_oficial.zip'}")
    malla_res_gdf = gpd.read_file(REPO_ROOT / "geovisor" / "capas" / "amss_malla_continua_250m.geojson")
    upd_res_gdf = gpd.read_file(REPO_ROOT / "geovisor" / "capas" / "amss_upd_425_imputadas.geojson")
    corr_df = pd.read_csv(RESULTADOS_DIR / "amss_correlaciones_embeddings_suelo.csv")

    fig1_bytes = create_fig1_workflow()
    fig2_bytes = create_fig2_spatial_coverage(upd_gdf, perim_gdf)
    fig3_bytes = create_fig3_calibration(upd_gdf)
    fig4_bytes = create_fig4_mesh_results(malla_res_gdf, perim_gdf)
    fig5_bytes = create_fig5_correlations(corr_df)
    fig6_bytes = create_fig6_evaluation_and_typologies(upd_res_gdf, malla_res_gdf)

    # Exportar también las 6 figuras a web/assets/img/figuras/ para las páginas del portal web
    WEB_FIGURAS_DIR.mkdir(parents=True, exist_ok=True)
    web_figs = [
        ("01_arquitectura_metodologica_gee.png", fig1_bytes),
        ("02_cobertura_territorial_upds_amss.png", fig2_bytes),
        ("03_calibracion_log_ols_opamss_mercado.png", fig3_bytes),
        ("04_mapa_resultados_malla_continua_250m.png", fig4_bytes),
        ("05_correlaciones_google_embeddings_eo.png", fig5_bytes),
        ("06_evaluacion_modelo_y_tipologias_urbanas.png", fig6_bytes),
    ]
    for fname, fbytes in web_figs:
        (WEB_FIGURAS_DIR / fname).write_bytes(fbytes)

    doc = DocxBuilder()

    # --- PORTADA / FICHA EJECUTIVA ---
    doc.add_cover_banner()

    doc.add_table(
        ["Atributo del Proyecto", "Detalle Técnico Oficial"],
        [
            ["Iniciativa y código", "Monitoreo de las dinámicas de expansión urbana y transformación del suelo del AMSS (sv-amss)"],
            ["Ámbito geográfico", "Área Metropolitana de San Salvador (AMSS) — 14 distritos tradicionales (1,484.21 km²)"],
            ["Instituciones vinculadas", "OPAMSS, Ministerio de Gobernación y Desarrollo Territorial, NIMD · Clúster Urbano Copernicus"],
            ["Unidad y moneda estándar", "Dólares estadounidenses por metro cuadrado de suelo (USD/m²), trazable por fuente"],
            ["Plataformas de procesamiento", "Python 3 (GeoPandas / Shapely / NumPy) + Google Earth Engine (JavaScript API)"],
            ["Modelo de representación EO", "Google Satellite Embeddings V1 (AlphaEarth Foundations, 64 bandas a 10 m) + 7 capas físicas"],
            ["Resolución espacial", "Estimación continua a nivel de píxel (20 m) y malla continua de polígonos UTM 16N (250 m)"],
            ["Scripts reproducibles", "src/preparar_assets_gee_suelo.py  |  src/gee_modelo_valor_suelo_amss.js"],
        ],
        [30, 70],
    )

    doc.add_callout(
        "Propósito ejecutivo del documento",
        "Este documento describe de manera rigurosa y reproducible la metodología aplicada para construir una superficie continua de valor del suelo a nivel de píxel (USD/m²) y su agregación sobre una malla continua de polígonos en todo el territorio del AMSS. El flujo supera la fragmentación espacial de los registros puntuales y poligonales disponibles combinando econometría espacial de armonización de fuentes con aprendizaje automático no paramétrico (Random Forest logarítmico) alimentado por los vectores profundos de Google Satellite Embeddings y variables biofísicas en Google Earth Engine.",
    )

    # --- SECCIÓN 1 ---
    doc.add_h1("1.", "Introducción y Planteamiento del Problema Territorial")
    doc.add_p(
        "El Área Metropolitana de San Salvador (AMSS) experimenta procesos simultáneos de densificación vertical en sus corredores centrales y pericentrales (San Benito, Colonia Escalón, Santa Elena, Antiguo Cuscatlán) y de expansión horizontal discontinua hacia las periferias norte, oriente y sur (Apopa, Tonacatepeque, Ilopango, San Martín, Zaragoza y Santo Tomás). Para orientar los instrumentos de planificación urbana, zonificación, captura de plusvalías e inversión pública gestionados por la Oficina de Planificación del Área Metropolitana de San Salvador (OPAMSS) y el Ministerio de Gobernación y Desarrollo Territorial, resulta indispensable contar con una estimación territorialmente continua y actualizada del valor del suelo."
    )
    doc.add_p(
        "Sin embargo, la información empírica disponible en gabinete presenta tres limitaciones estructurales características de los mercados de suelo latinoamericanos:"
    )
    doc.add_bullet(
        "Cobertura espacial incompleta:",
        "De las 425 Unidades de Planificación Detallada (UPD) con geometría válida en el AMSS, 265 cuentan con precios de oferta inmobiliaria capturados mediante web scraping en 2025 y 145 registran valores declarados en trámites de permisos OPAMSS del periodo reciente 2020–2026. Incluso integrando ambas fuentes, 144 UPDs (33.9% de las unidades) y aproximadamente 35.9 km² de franjas periféricas dentro del límite metropolitano oficial carecen de observaciones recientes.",
    )
    doc.add_bullet(
        "Diferencial sistemático de escala entre fuentes administrativas y mercado:",
        "Los valores asociados a expedientes de permisos reflejan costos o avalúos declarados en trámite, mientras que los anuncios inmobiliarios reflejan precios de oferta comercial (asking prices), los cuales superan en mediana por un factor de 1.53 veces al promedio reciente de permisos.",
    )
    doc.add_bullet(
        "Problema de la Unidad Espacial Modificable (MAUP) intra-UPD:",
        "Las UPDs presentan tamaños altamente heterogéneos (mediana de 164.8 ha y percentil 95 de 1,230.1 ha), integrando dentro de un mismo polígono tejido urbano consolidado junto con barrancas volcánicas, quebradas de alta pendiente y áreas boscosas de reserva donde el precio urbano observado no es físicamente representativo.",
    )

    doc.add_image(
        fig1_bytes,
        "fig1_flujo_metodologico.png",
        6.4,
        "Figura 1. Arquitectura metodológica en cuatro fases para la estimación del valor del suelo a nivel de píxel y malla continua en el AMSS.",
    )

    # --- SECCIÓN 2 ---
    doc.add_h1("2.", "Fuentes Locales, Depuración Topológica y Armonización Econométrica", page_break=True)
    doc.add_h2("2.1. Auditoría y saneamiento geométrico de las capas base")
    doc.add_p(
        "En la Fase I, ejecutada localmente mediante el script reproducible src/preparar_assets_gee_suelo.py, se auditaron y armonizaron tres insumos vectoriales en el sistema de referencia geodésico WGS84 (EPSG:4326) junto con cálculos métricos exactos en proyección UTM Zona 16N (EPSG:32616):"
    )
    doc.add_bullet(
        "Consolidado de permisos OPAMSS (upd_consolidado.shp):",
        "Contiene 426 registros poligonales de Unidades de Planificación Detallada con estadísticas agregadas de valor del suelo para dos cortes temporales: Periodo 1 (2007–2019: P1_PROM, P1_MED, P1_N en 157 UPDs) y Periodo 2 (2020–2026: P2_PROM, P2_MED, P2_N en 145 UPDs), además de indicadores socio-urbanos (HAB_TOTAL, UVIP, PC_TOT). Durante la auditoría se detectó y descartó 1 registro con geometría nula/vacía y se aplicó reparación topológica (.make_valid()), consolidando 425 polígonos válidos (1,448.30 km²) aptos para ingesta sin fallos en Google Earth Engine.",
    )
    doc.add_bullet(
        "Oferta inmobiliaria 2025 por web scraping (LISA_PRECIOS_2025.shp):",
        "Integra 265 polígonos UPD con precios promedio de oferta comercial del año 2025 en USD/m² (campo promedio_2, renombrado a VAL_MKT25) y tipologías de autocorrelación espacial local de Moran (cluster_LI y cuadrante_). El cruce relacional verificó una correspondencia exacta del 100% (265 de 265 polígonos) mediante el identificador único OBJECTID.",
    )
    doc.add_bullet(
        "Perímetro metropolitano oficial (amss_perimetro.geojson):",
        "Disuelto topológicamente en un único polígono continuo de 1,484.21 km² (amss_perimetro_oficial.zip) para garantizar que tanto la inferencia raster como la malla continua cubran la totalidad de los 14 distritos del AMSS sin vacíos intersticiales.",
    )

    doc.add_h2("2.2. Control de valores atípicos y calibración log-lineal (VAL_FUS25)")
    doc.add_p(
        "En la serie histórica 2007–2019 (P1_PROM) se identificaron cuatro registros extremos aislados superiores a $7,000 USD/m² originados por distorsiones puntuales de expediente, mientras que las medianas (P1_MED) permanecían estables. Para preservar la utilidad analítica de la media histórica sin sesgar ajustes paramétricos, se generó la variable winsorizada al percentil 98 (P1_PROM_W, con tope en $6,561.40 USD/m²)."
    )
    doc.add_p(
        "Para maximizar la muestra de entrenamiento contemporánea (horizonte 2025) sin mezclar directamente precios de oferta con valores administrativos de permisos (cumpliendo el criterio de trazabilidad sv-amss-AC-02), se estimó un modelo de calibración log-lineal por Mínimos Cuadrados Ordinarios (OLS) sobre las n = 129 UPDs que cuentan simultáneamente con oferta inmobiliaria 2025 (VAL_MKT25) y permisos recientes 2020–2026 (P2_PROM):"
    )

    doc.add_formula_box(
        [
            "ln(VAL_MKT25_i) = 2.8070 + 0.4943 * ln(P2_PROM_i) + e_i     (n = 129,  r = 0.614)",
            "S_Duan = (1 / n) * SUM[ exp(e_i) ] = 1.2141",
            "VAL_CALIB_i = exp( 2.8070 + 0.4943 * ln(P2_PROM_i) ) * 1.2141",
        ],
        "Ecuación 1. Calibración log-OLS y corrección no paramétrica de sesgo exponencial de Duan para armonizar permisos 2020–2026 a escala de mercado 2025.",
    )

    doc.add_p(
        "La variable objetivo recomendada VAL_FUS25 conserva el valor observado de mercado (VAL_MKT25) en las 265 UPDs donde existe levantamiento directo e incorpora el valor calibrado (VAL_CALIB) únicamente en las 16 UPDs adicionales que disponían de permisos OPAMSS 2020–2026 pero carecían de anuncios web, alcanzando 281 UPDs de entrenamiento y documentando el origen exacto de cada polígono en el atributo categórico FUENTE_V (MKT_2025, P2_CALIB o SIN_DATO). Los valores faltantes se codifican explícitamente como -9999.0 acompañados de banderas binarias (HAS_FUS25, HAS_MKT25, HAS_P2, HAS_P1) para evitar coerciones ambiguas a cero en formato Shapefile DBF."
    )

    doc.add_image(
        fig2_bytes,
        "fig2_mapa_cobertura.png",
        6.3,
        "Figura 2. Distribución espacial de las 425 UPDs según fuente de valor disponible en el Asset de entrenamiento y contorno oficial del AMSS.",
    )

    doc.add_image(
        fig3_bytes,
        "fig3_calibracion_ols.png",
        6.1,
        "Figura 3. Relación log-lineal empírica entre los registros de permisos OPAMSS 2020–2026 y los precios de oferta inmobiliaria 2025 (n = 129 UPDs).",
    )

    # --- SECCIÓN 3 ---
    doc.add_h1("3.", "Cubo de Predictores: Google Satellite Embeddings y Observación de la Tierra", page_break=True)
    doc.add_p(
        "La hipótesis central del modelo espacial es que el valor del suelo urbano capitaliza atributos multidimensionales del entorno construido, la accesibilidad funcional, el nivel de consolidación de infraestructuras, la calidad ambiental barrial y las restricciones topográficas, todos los cuales dejan una huella física medible desde sensores orbitales. En lugar de depender únicamente de índices espectrales simples (como NDVI o NDBI aislados), el modelo integra representaciones profundas de última generación junto con variables geofísicas explícitas, conformando un cubo de 71 bandas predictoras continuas en Google Earth Engine."
    )

    doc.add_h2("3.1. Google Satellite Embeddings V1 (AlphaEarth Foundations)")
    doc.add_p(
        "El núcleo explicativo está constituido por la colección anual GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL a 10 metros de resolución espacial (64 bandas continuas A00 a A63). Generados por el modelo fundacional geoespacial AlphaEarth Foundations, estos vectores de longitud unitaria sintetizan en un espacio latente común observaciones multimodales a lo largo de todo el ciclo anual: reflectancia superficial óptica multiespectral (Sentinel-2 y Landsat 8/9), retrodispersión de radar de apertura sintética en banda C (Sentinel-1 GRD VV/VH sensible al doble rebote diedro de estructuras urbanas), estructura tridimensional LiDAR (GEDI), elevación y fenología estacional."
    )
    doc.add_p(
        "Para el contexto del AMSS, estas 64 dimensiones capturan de forma nativa distinciones morfológicas sutiles estrechamente ligadas al mercado inmobiliario: diferencian tejidos residenciales de alta plusvalía con abundante arbolado intersticial y techos amplios frente a tejidos industriales/logísticos de gran nave metálica, centros comerciales con superficies de estacionamiento, lotificaciones periurbanas en terracería y asentamientos densos de grano fino."
    )

    doc.add_h2("3.2. Covariables explícitas morfológicas 2.5D, económicas y topográficas")
    doc.add_p(
        "Para reforzar la capacidad del modelo en gradientes verticales de renta y restricciones fisiográficas locales, las 64 dimensiones latentes se complementan con 7 bandas físicas directas provenientes de colecciones precomputadas globales:"
    )

    doc.add_table(
        ["Grupo Temático", "Colección Oficial en GEE", "Bandas en el Modelo", "Res.", "Rol Explicativo en el Valor del Suelo"],
        [
            [
                "Embeddings multimodales",
                "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL",
                "A00 .. A63 (64 bandas)",
                "10 m",
                "Morfología urbana integral, materiales de techo, grano vial, textura radar y contexto espacial barrial.",
            ],
            [
                "Morfología edilicia 2.5D",
                "GOOGLE/Research/open-buildings-temporal/v1",
                "ob_pres, ob_height",
                "4 m ef.",
                "Presencia de edificaciones y altura neta en metros; discrimina polos corporativos y torres residenciales.",
            ],
            [
                "Cobertura consolidada",
                "ESA/WorldCover/v200",
                "wc_built, wc_trees (+ máscara agua)",
                "10 m",
                "Delimitación nítida de superficie construida consolidada, amenidad arbórea urbana y exclusión de cuerpos de agua.",
            ],
            [
                "Centralidad económica",
                "NOAA/VIIRS/DNB/ANNUAL_V22",
                "viirs_rad (average_masked)",
                "~460 m",
                "Radiancia nocturna anual libre de nubes y fuegos efímeros; proxy de aglomeración comercial, servicios y conectividad.",
            ],
            [
                "Geomorfometría",
                "COPERNICUS/DEM/GLO30",
                "dem_elev, dem_slope",
                "30 m",
                "Gradiente altitudinal climático del AMSS y penalización por laderas escarpadas y taludes de quebradas.",
            ],
        ],
        [18, 28, 17, 8, 29],
        mono_cols={1, 2},
    )

    # --- SECCIÓN 4 ---
    doc.add_h1("4.", "Modelado a Nivel de Píxel y Optimización Computacional en GEE")
    doc.add_h2("4.1. Mitigación del sesgo MAUP mediante enmascaramiento de huella desarrollable")
    doc.add_p(
        "Si se extrajeran píxeles de entrenamiento de manera uniforme dentro de cada polígono UPD, una UPD periférica extensa compuesta en un 85% por cafetales o laderas del volcán de San Salvador transferiría erróneamente el precio de sus urbanizaciones formales a píxeles forestales o barrancas inaccesibles. Para resolver este problema de asignación ecológica (MAUP intra-polígono), el muestreo de entrenamiento se restringe estrictamente a los píxeles que cumplen simultáneamente la condición de huella construida y aptitud topográfica:"
    )

    doc.add_formula_box(
        [
            "Mascara_Entrenamiento(x) = [ wc_built(x) == 1  OR  ob_pres(x) > 0.12 ]",
            "                           AND [ dem_slope(x) < 32 grados ] AND [ wc_water(x) == 0 ]",
        ],
        "Ecuación 2. Condición espacial intra-UPD para extracción limpia de píxeles urbanos de entrenamiento.",
    )

    doc.add_p(
        "Esta regla aporta una ventaja estadística adicional: equilibra de forma natural el peso muestral entre polígonos centrales compactos 100% urbanizados (30–60 ha) y polígonos periféricos gigantes (>800 ha) cuya mancha efectivamente edificada tiene una extensión comparable, evitando sobrerrepresentar la periferia rural."
    )

    doc.add_h2("4.2. Regresión Random Forest en escala logarítmica y superficie dual")
    doc.add_p(
        "Dado que los precios del suelo urbano exhiben fuerte asimetría positiva (distribución aproximadamente log-normal) e interacciones no lineales complejas entre verticalidad, centralidad y entorno ambiental, se entrena un ensamble Random Forest en modo regresión (ee.Classifier.smileRandomForest) sobre el logaritmo natural del valor del suelo, y_ln = ln(Valor):"
    )
    doc.add_bullet("Muestreo directo:", "Pintado vectorial a raster (.paint()) seguido de muestreo aleatorio estratificado implícito (.sample()) de 1,800 píxeles urbanos a escala de 30 m con tileScale = 8.")
    doc.add_bullet("Configuración del bosque:", "80 árboles de regresión, 18 predictores candidatos por nodo de partición (aprox. p/4 sobre 71 variables), población mínima de hoja igual a 5 observaciones para prevenir sobreajuste local y fracción de submuestreo bagging de 0.70.")
    doc.add_bullet("Retransformación a USD/m²:", "Por la desigualdad de Jensen, exp(E[ln V]) subestima E[V]; por ello la predicción logarítmica de cada píxel se retransforma multiplicando exp(y_hat_ln) por el factor de corrección log-normal de sesgo (1.06, consistente con un RMSE logarítmico Out-Of-Bag del orden de ~0.34).")
    doc.add_bullet(
        "Doble banda de salida a nivel de píxel (20 m):",
        "El modelo genera 1) valor_potencial_usd_m2 (superficie continua sobre el 100% del perímetro del AMSS, útil para evaluar presión inmobiliaria y continuidad territorial) y 2) valor_urbano_usd_m2 (superficie restringida a terrenos con pendiente < 35° y libres de cuerpos de agua permanentes).",
    )

    doc.add_h2("4.3. Ingeniería de memoria en Google Earth Engine (Arquitectura Halo Cero)")
    doc.add_p(
        "En la plataforma interactiva de Google Earth Engine, las capas visualizadas en pantalla disponen de una cuota estricta de memoria por nodo y tiempo límite por tesela (tile timeout). Para impedir errores de saturación ('Layer error' o 'User memory limit exceeded'), el script aplica cuatro principios de ingeniería computacional:"
    )
    doc.add_bullet("Cero consultas computeValue en Consola al inicio:", "Se suprimieron impresiones de tablas masivas, gráficos interactivos y conteos de colecciones al arrancar, dedicando el 100% de la concurrencia al renderizado cartográfico.")
    doc.add_bullet("Cero convoluciones focales y cero compuestos crudos (Halo = 0):", "Se eliminó el promediado en vivo de cientos de escenas Sentinel-1/2 y los kernels focalMean de gran radio, aprovechando que Google Satellite Embeddings V1 ya integra el contexto espacial vecinal precomputado.")
    doc.add_bullet("Un único entrenamiento en memoria:", "Se prescinde de entrenar bosques duplicados simultáneos y se sustituyen los bucles de puntos por polígono por una única lectura rasterizada.")
    doc.add_bullet("Desacoplamiento entre vista rápida y vectorización masiva:", "En el visor interactivo solo se activa por defecto el raster ligero de píxeles y un inspector puntual por clic (que reduce únicamente la celda de 250 m seleccionada), mientras que la reducción zonal sobre los ~24,200 polígonos de la malla se ejecuta íntegramente en los servidores Batch mediante Export.table.toDrive.")

    # --- SECCIÓN 5 ---
    doc.add_h1("5.", "Asociación a Malla Continua de Polígonos e Imputación de UPDs", page_break=True)
    doc.add_p(
        "Para traducir la superficie continua de píxeles en unidades operativas homogéneas comparables en todo el territorio metropolitano, el script genera dinámicamente dentro de Google Earth Engine una malla continua de polígonos regulares sin necesidad de cargar insumos externos de grilla:"
    )
    doc.add_bullet(
        "Teselación métrica continua (EPSG:32616):",
        "Se emplea el motor nativo coveringGrid sobre la proyección UTM Zona 16N con tamaño de celda configurable (por defecto 250 m x 250 m, equivalente a 6.25 ha por celda, generando ~24,200 polígonos continuos sobre los 1,484.21 km² del AMSS).",
    )
    doc.add_bullet(
        "Recorte topológico inteligente de borde:",
        "Se define un anillo interior negativo (-1.5 veces el tamaño de celda); el ~95% de las celdas estrictamente interiores conservan su geometría cuadrada exacta de 4 vértices sin costo geométrico, aplicando intersección contra el perímetro simplificado únicamente en las celdas limítrofes y filtrando astillas residuales (< 0.05 ha).",
    )
    doc.add_bullet(
        "Estadística zonal multivariada y respaldo continuo:",
        "Mediante reduceRegions (escala 30 m, tileScale = 8), cada polígono de la malla agrega media, mediana y desviación estándar del valor del suelo, fracción edificada, altura media 2.5D y pendiente. En celdas periurbanas escarpadas donde la máscara urbanizable no tuviese píxeles válidos, VAL_EST_M2 adopta automáticamente VAL_POT_M2 para garantizar continuidad al 100% sin huecos nulos, y todos los campos numéricos aseguran tipado estricto no nulo compatible con Shapefile y GeoJSON.",
    )

    doc.add_h2("5.1. Diccionario de atributos de la Malla Continua exportada")
    doc.add_table(
        ["Campo", "Tipo", "Unidad / Dominio", "Definición Técnica en la Malla Continua (250 m)"],
        [
            ["ID_CELDA", "Texto", "C_<col>_<fila>", "Identificador único determinístico basado en coordenadas de grilla UTM 16N."],
            ["AREA_HA", "Decimal", "Hectáreas (ha)", "Superficie exacta del polígono (6.25 ha en celdas interiores completas)."],
            ["VAL_EST_M2", "Decimal", "USD/m²", "Valor estimado principal del suelo (promedio en píxeles desarrollables de la celda)."],
            ["VAL_MED_M2", "Decimal", "USD/m²", "Mediana intra-celda del valor estimado (robusta ante bordes de transición)."],
            ["VAL_POT_M2", "Decimal", "USD/m²", "Valor potencial continuo promedio de todos los píxeles de la celda sin máscara."],
            ["VAL_STD_M2", "Decimal", "USD/m²", "Desviación estándar intra-celda (indicador de heterogeneidad interna)."],
            ["FRAC_EDIF", "Decimal", "Proporción [0–1]", "Fracción de superficie construida dentro de la celda según ESA WorldCover 10 m."],
            ["ALT_EDIF_M", "Decimal", "Metros (m)", "Altura media de edificaciones 2.5D según Google Open Buildings Temporal."],
            ["PEND_DEG", "Decimal", "Grados (°)", "Pendiente topográfica media derivada de Copernicus DEM GLO-30."],
            [
                "TIPO_SUELO",
                "Texto",
                "3 categorías",
                "URBANO_CONSOLIDADO (>=45% edif.), PERIURBANO_TRANSICION (10–45%) o RURAL_RESERVA (<10%).",
            ],
        ],
        [16, 12, 20, 52],
        mono_cols={0},
    )

    doc.add_p(
        "De manera complementaria, el flujo genera la capa upd425Imputadas, la cual conserva el dato observado (ORIGEN_FIN = 'OBSERVADO') en las UPDs con muestra válida e imputa la media zonal estimada sobre huella urbana en las 144 UPDs sin información previa (ORIGEN_FIN = 'IMPUTADO_MODELO_GEE'), cumpliendo íntegramente el criterio sv-amss-AC-03 de transparencia entre datos observados y estimados."
    )

    # --- SECCIÓN 6: RESULTADOS EMPÍRICOS, ANÁLISIS E INTERPRETACIÓN ---
    doc.add_h1("6.", "Resultados Obtenidos: Análisis Estadístico e Interpretación Territorial", page_break=True)
    doc.add_p(
        "La ejecución completa del flujo en Google Earth Engine sobre los Assets oficiales produjo cuatro salidas verificadas: 1) la tabla estadística de correlaciones de las 71 bandas frente al logaritmo del valor del suelo, 2) el raster continuo multibanda a 20 metros de resolución (3,845,824 píxeles válidos dentro del perímetro del AMSS), 3) la malla continua de 24,292 polígonos de 250 m (148,875.1 ha sin un solo vacío espacial) y 4) el consolidado completo de las 425 UPDs con imputación explícita de las 144 unidades faltantes."
    )

    doc.add_h2("6.1. Análisis de correlaciones: Google Satellite Embeddings frente a variables físicas EO")
    doc.add_p(
        "El análisis bivariado de Pearson sobre la muestra urbana intra-UPD confirma de manera contundente la pertinencia de combinar representaciones profundas con indicadores biofísicos directos: 64 de las 71 bandas evaluadas resultan estadísticamente significativas al 95% de confianza (p < 0.05) y 24 predictores superan el umbral de correlación fuerte (|r| >= 0.50)."
    )
    doc.add_bullet(
        "Liderazgo predictivo de Google Satellite Embeddings V1:",
        "Las tres variables con mayor poder explicativo individual en todo el AMSS corresponden a dimensiones latentes de AlphaEarth Foundations: A13 (r = -0.694, p = 1.12e-41), A32 (r = -0.660, p = 1.62e-36) y A34 (r = +0.650, p = 4.66e-35), acompañadas por A51 (+0.620), A08 (-0.616), A41 (+0.602), A28 (+0.600), A22 (-0.590), A18 (+0.588) y A53 (+0.585). Esto demuestra que las texturas multiespectrales, de radar SAR y de grano urbano codificadas a 10 m capturan señales inmobiliarias más ricas que cualquier índice espectral tradicional por separado.",
    )
    doc.add_bullet(
        "Coherencia económica de las covariables físicas explícitas:",
        "La fracción arbórea periurbana/rural (wc_trees, r = -0.625) y la huella impermeabilizada edificada (wc_built, r = +0.621) ocupan las posiciones 4 y 5 del ranking general, seguidas por la radiancia nocturna anual VIIRS (viirs_rad, r = +0.578, proxy de aglomeración comercial y conectividad luminosa), la penalización topográfica por pendiente (dem_slope, r = -0.472), la densidad de presencia de edificaciones 2.5D (ob_pres, r = +0.471) y la altura media construida (ob_height, r = +0.311, p = 9.74e-8).",
    )
    doc.add_bullet(
        "No linealidad altitudinal (dem_elev):",
        "La elevación absoluta presentó una correlación lineal marginal no significativa (r = +0.075, p = 0.212). Desde la geografía económica del AMSS este hallazgo es plenamente consistente: los mayores precios se ubican en mesetas intermedias-altas del poniente (Colonia Escalón, San Benito, Santa Elena y Antiguo Cuscatlán, entre 750 y 1,050 m s.n.m.), mientras que tanto las cotas más altas (>1,300 m en el edificio volcánico del Boquerón y cordillera del Bálsamo) como las cotas bajas orientales (Ilopango, San Martín, Tonacatepeque, 450–650 m) registran menores valores relativos. El modelo Random Forest aprovecha esta relación no monótona mediante particiones jerárquicas.",
    )

    doc.add_image(
        fig5_bytes,
        "fig5_correlaciones_embeddings.png",
        6.3,
        "Figura 4. Ranking de correlaciones r de Pearson de los principales vectores de Google Satellite Embeddings V1 y capas físicas de Observación de la Tierra frente a ln(Valor del Suelo).",
    )

    doc.add_h2("6.2. Distribución espacial en Píxel (20 m) y Malla Continua (250 m)")
    doc.add_p(
        "En la superficie raster continua de 20 metros, la banda de suelo urbano/desarrollable abarca 3,631,473 píxeles válidos (excluyendo láminas de agua permanente como el lago de Ilopango y escarpes extremos >= 35°), con valores que oscilan entre $8.66 USD/m² en bordes rurales quebrados y $471.13 USD/m² en los nodos corporativos y comerciales prime del eje San Benito – Escalón – La Gran Vía, situándose la mediana general del territorio metropolitano en $32.34 USD/m² (percentil 90 = $100.22/m²; percentil 95 = $176.17/m²; percentil 99 = $317.72/m²)."
    )
    doc.add_p(
        "Al agregar estos píxeles sobre los 24,292 polígonos de la malla continua de 250 m (148,875.1 ha totales), emerge con nitidez la estructura policéntrica y el gradiente centro-periferia del AMSS:"
    )

    doc.add_table(
        ["Tipología en Malla 250 m", "Celdas (n)", "Superficie (ha)", "Media (USD/m²)", "Mediana", "P90 (USD/m²)", "Máximo", "Morfología Media"],
        [
            [
                "URBANO_CONSOLIDADO",
                "2,215 (9.1%)",
                "13,824.6",
                "$187.27",
                "$169.24",
                "$302.70",
                "$375.90",
                "77.6% edif. | 2.85 m alt. | 5.5°",
            ],
            [
                "PERIURBANO_TRANSICION",
                "1,571 (6.5%)",
                "9,578.1",
                "$74.35",
                "$67.49",
                "$117.38",
                "$250.00",
                "23.9% edif. | 1.01 m alt. | 9.6°",
            ],
            [
                "RURAL_RESERVA",
                "20,506 (84.4%)",
                "125,472.4",
                "$33.35",
                "$31.11",
                "$41.93",
                "$223.31",
                "0.4% edif. | 0.07 m alt. | 15.8°",
            ],
            [
                "TOTAL MALLA AMSS",
                "24,292 (100%)",
                "148,875.1",
                "$50.04",
                "$32.47",
                "$93.83",
                "$375.90",
                "9.0% edif. | 0.38 m alt. | 14.4°",
            ],
        ],
        [21, 11, 11, 12, 9, 11, 9, 16],
    )

    doc.add_p(
        "La tabla evidencia una diferenciación estructural contundente: el suelo urbano consolidado alcanza un valor mediano 5.4 veces superior al suelo rural/reserva ($169.24 frente a $31.11 USD/m²) y 2.5 veces superior a la franja periurbana en transición ($67.49 USD/m²), reflejando cómo la capitalización inmobiliaria sigue estrechamente la consolidación de infraestructura, la altura edificada (2.85 m promedio sobre toda la celda de 6.25 ha) y las pendientes suaves (5.5° en promedio)."
    )

    doc.add_image(
        fig4_bytes,
        "fig4_mapa_malla_resultados.png",
        6.3,
        "Figura 5. Mapa continuo del valor del suelo estimado (VAL_EST_M2) sobre las 24,292 celdas de 250 m en todo el ámbito metropolitano.",
    )

    doc.add_h2("6.3. Evaluación en UPDs observadas, jerarquía distrital e imputación de vacíos")
    doc.add_p(
        "Al contrastar las predicciones zonales puras del modelo satelital (VAL_MOD_M2) frente a los valores de referencia en las n = 281 UPDs observadas, se obtiene una correlación lineal r = 0.782 y una correlación logarítmica r_log = 0.724, con una convergencia casi exacta en la tendencia central metropolitana: la mediana predicha por el modelo es de $102.84 USD/m² frente a $103.66 USD/m² observados (diferencia menor al 0.8%)."
    )
    doc.add_p(
        "En las 144 UPDs que carecían por completo de registros de mercado 2025 o permisos recientes (57,647.5 ha, equivalentes al 39.8% de la superficie total de UPDs), el modelo imputó valores coherentes con su localización y morfología física: mediana de $35.14 USD/m² y media de $50.69 USD/m² (rango de $17.75 a $267.21 USD/m²), distinguiendo con precisión enclaves residenciales consolidados sin oferta activa en Antiguo Cuscatlán y Santa Tecla (> $200/m²) frente a unidades rurales periféricas en Tonacatepeque, Nejapa, Panchimalco y Rosario de Mora ($24–$50/m²)."
    )

    doc.add_image(
        fig6_bytes,
        "fig6_evaluacion_y_tipologias.png",
        6.3,
        "Figura 6. Evaluación empírica en las 281 UPDs con muestra observada (panel A) y gradiente estructural de precios y morfología según tipología urbana en la malla de 250 m (panel B).",
    )

    doc.add_table(
        ["Distrito / Municipio Relevante", "UPDs Totales", "Observadas / Imputadas", "Mediana Integrada (USD/m²)", "Media Integrada", "Máximo UPD"],
        [
            ["Antiguo Cuscatlán", "13", "8 obs. / 5 imp.", "$288.55", "$309.22", "$577.13"],
            ["San Salvador (núcleo capital)", "41", "39 obs. / 2 imp.", "$272.85", "$271.34", "$677.30"],
            ["Nuevo Cuscatlán", "7", "7 obs. / 0 imp.", "$253.63", "$227.73", "$413.89"],
            ["Santa Tecla", "29", "22 obs. / 7 imp.", "$219.14", "$215.82", "$461.23"],
            ["Mejicanos", "14", "13 obs. / 1 imp.", "$191.66", "$173.35", "$330.97"],
            ["Soyapango", "17", "15 obs. / 2 imp.", "$117.67", "$110.99", "$231.96"],
            ["Cuscatancingo", "6", "6 obs. / 0 imp.", "$101.48", "$113.69", "$224.66"],
            ["San Marcos", "10", "9 obs. / 1 imp.", "$84.13", "$100.77", "$229.20"],
            ["Ilopango", "12", "11 obs. / 1 imp.", "$80.43", "$80.17", "$131.78"],
            ["Apopa", "15", "11 obs. / 4 imp.", "$76.00", "$77.45", "$171.50"],
            ["San Martín", "17", "7 obs. / 10 imp.", "$72.60", "$78.15", "$206.60"],
            ["Delgado", "15", "13 obs. / 2 imp.", "$66.81", "$98.17", "$271.07"],
            ["Santo Tomás", "14", "4 obs. / 10 imp.", "$52.46", "$60.96", "$143.01"],
            ["Ayutuxtepeque", "5", "5 obs. / 0 imp.", "$50.81", "$86.02", "$182.50"],
            ["Tonacatepeque", "13", "8 obs. / 5 imp.", "$47.72", "$48.82", "$128.54"],
            ["Nejapa", "16", "7 obs. / 9 imp.", "$47.17", "$62.36", "$195.92"],
        ],
        [26, 12, 18, 16, 14, 14],
    )

    # --- SECCIÓN 7: HOJA DE RUTA DE MEJORA Y AFINAMIENTO ---
    doc.add_h1("7.", "Diagnóstico Crítico y Cómo Mejorar y Afinar la Metodología", page_break=True)
    doc.add_p(
        "El análisis empírico de los primeros resultados permite identificar dos comportamientos estadísticos susceptibles de refinamiento en una segunda iteración del modelo: 1) compresión de extremos superiores e inferiores propia del promediado en árboles de regresión (el percentil 95 zonal del modelo se sitúa en $303.74 USD/m² frente a $407.84 USD/m² observados, suavizando micro-corredores corporativos > $500/m²), y 2) ruido muestral en UPDs periféricas donde el dato observado proviene de un único anuncio aislado ($0.64 a $6.00 USD/m²), lo cual eleva el error porcentual mediano (MedAPE = 40.97% y MAE = $58.42 USD/m²). Para afinar la precisión predictiva e institucionalizar el modelo en OPAMSS, se proponen siete mejoras concretas:"
    )

    doc.add_bullet(
        "1. Entrenamiento con puntos georreferenciados individuales (parcela/oferta) en lugar de polígonos UPD:",
        "Migrar la variable dependiente desde promedios agregados por UPD hacia las coordenadas exactas de cada trámite OPAMSS y cada anuncio depurado de web scraping (extrayendo embeddings en un buffer local de 50–100 m). Esto eliminará de raíz el residuo de falacia ecológica intra-UPD y reducirá sustancialmente la dispersión del error.",
    )
    doc.add_bullet(
        "2. Ponderación por tamaño muestral y filtro de confiabilidad mínima:",
        "Incorporar pesos estadísticos proporcionales a sqrt(N_observaciones) por unidad o descartar del entrenamiento aquellas UPDs con menos de 3 registros independientes cuando presenten desviaciones extremas respecto a su vecindario LISA, evitando que lotes rústicos aislados distorsionen la cola baja.",
    )
    doc.add_bullet(
        "3. Corrección de compresión en colas prime mediante Gradient Boosting e intervalos cuantílicos:",
        "Complementar Random Forest con ensambles secuenciales (ee.Classifier.smileGradientTreeBoost con pérdida Huber/Mínimos Cuadrados) o Regresión Cuantílica (P10, P50, P90) más calibración post-hoc isotónica, permitiendo reproducir picos comerciales de $500–$700 USD/m² y entregar bandas explícitas de incertidumbre por celda.",
    )
    doc.add_bullet(
        "4. Integración de variables normativas del Esquema Director OPAMSS y riesgo físico:",
        "Incorporar como predictores explícitos la zonificación normativa vigente (usos permitidos, coeficientes de edificabilidad COS/CUS, alturas máximas reguladas y zonas de máxima protección ambiental o amenaza por deslizamiento/inundación), dado que dos parcelas físicamente similares tienen distinto valor potencial según su edificabilidad legal.",
    )
    doc.add_bullet(
        "5. Accesibilidad vial por tiempos reales en red (isócronas) y centralidades:",
        "Sustituir proxies isotrópicos por matrices de tiempo de viaje sobre la red vial jerarquizada (OpenStreetMap / OPAMSS) hacia subcentros de empleo, corredores logísticos e inversiones viales estratégicas.",
    )
    doc.add_bullet(
        "6. Validación cruzada espacial por bloques (Spatial Block Cross-Validation):",
        "Implementar particiones espaciales en bloques de 2 a 3 km (k-fold espacial) fuera de Google Earth Engine (en Python con scikit-learn / LightGBM / XGBoost exportando la matriz muestral) para medir el error predictivo libre de autocorrelación espacial de corto alcance y optimizar hiperparámetros sistemáticamente.",
    )
    doc.add_bullet(
        "7. Descomposición suelo desnudo vs. inmueble construido y panel multianual 2017–2025:",
        "Estratificar las ofertas inmobiliarias según tipología (lote urbano sin construir frente a vivienda/local edificado aplicando método residual para aislar el valor puro de la tierra) y replicar la inferencia sobre la serie anual completa de Google Satellite Embeddings (2017–2025) para medir plusvalías interanuales y apoyar instrumentos de financiamiento urbano.",
    )

    # --- SECCIÓN 8: FLUJO OPERATIVO Y PUBLICACIÓN EN GEOVISOR ---
    doc.add_h1("8.", "Flujo Operativo Reproducible e Integración en el Geovisor Web")
    doc.add_table(
        ["Componente / Producto", "Ruta en el Repositorio sv-amss", "Formato", "Rol en el Ecosistema Técnico"],
        [
            ["1. Preparación de Assets", "src/preparar_assets_gee_suelo.py", "Python (.py)", "Audita geometrías, calibra VAL_FUS25 y empaqueta los Shapefiles para GEE."],
            ["2. Modelo satelital GEE", "src/gee_modelo_valor_suelo_amss.js", "GEE JS (.js)", "Entrena el Random Forest sobre 71 bandas y exporta malla 250 m, raster 20 m y UPDs."],
            ["3. Integración Geovisor", "src/integrar_resultados_gee_geovisor.py", "Python (.py)", "Sanea geometrías, cruza distritos, genera overlays PNG 20 m y comprime COG."],
            ["4. Malla Continua 250 m", "geovisor/capas/amss_malla_continua_250m.geojson", "GeoJSON", "24,292 celdas con 6 modos de leyenda interactiva en el geovisor MapLibre."],
            ["5. UPDs 425 Completas", "geovisor/capas/amss_upd_425_imputadas.geojson", "GeoJSON", "425 UPDs sin vacíos (281 observadas + 144 imputadas por GEE)."],
            ["6. Superficie Píxel 20 m", "geovisor/capas/amss_valor_suelo_pixel_20m.tif", "COG GeoTIFF", "Raster multibanda a 20 m (con vista directa PNG en el visor integrado)."],
            ["7. Subpágina Analítica", "site/modelo-suelo/index.html", "HTML5 / JS", "Subpágina dedicada con metodología, resultados, mejoras y visor del script GEE."],
        ],
        [20, 36, 13, 31],
        mono_cols={1},
    )

    doc.save(OUT_DOCX_REPO)
    OUT_DOCX_WEB.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT_DOCX_REPO, OUT_DOCX_WEB)
    OUT_DOCX_DATOS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT_DOCX_REPO, OUT_DOCX_DATOS)

    sz_kb = OUT_DOCX_REPO.stat().st_size / 1024.0
    print(f"[OK] Documento Word actualizado exitosamente ({sz_kb:.1f} KB):")
    print(f"  - En repositorio (docs/): {OUT_DOCX_REPO}")
    print(f"  - En descargas web:       {OUT_DOCX_WEB}")
    print(f"  - En carpeta de datos:    {OUT_DOCX_DATOS}")


if __name__ == "__main__":
    build_methodology_document()
