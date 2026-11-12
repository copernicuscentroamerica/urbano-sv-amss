"""Genera las láminas institucionales A4 horizontales de los resultados obtenidos
del Modelo de Valor del Suelo en Google Earth Engine (Láminas 11, 12 y 13) e integra
dichas páginas en el Atlas Temático Copernicus descargable del proyecto sv-amss.

Produce:
1. web/assets/descargas/Atlas_Resultados_Modelo_Suelo_GEE_AMSS.pdf (3 láminas A4 de resultados GEE)
2. web/assets/descargas/atlas_copernicus_zona_estudio.pdf (25 páginas: 22 base EO + 3 resultados GEE)
3. web/assets/descargas/atlas_copernicus_sv-amss.pdf (25 páginas sincronizadas)
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DESC_DIR = ROOT / "web" / "assets" / "descargas"
FIG_DIR = ROOT / "web" / "assets" / "img" / "figuras"
MOD_IMG_DIR = ROOT / "web" / "assets" / "img" / "modelo"
BRAND_DIR = ROOT / "web" / "assets" / "img" / "brand"

# A4 Landscape a 200 DPI -> 841.92 x 594.96 pt exactos a 200 DPI (2339 x 1653 px)
DPI = 200
W = 2339
H = 1653


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ["C:/Windows/Fonts/calibrib.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf"]
        if bold
        else ["C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"]
    )
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def paste_fit(canvas: Image.Image, img_path: Path, box: tuple[int, int, int, int], bg=(255, 255, 255)) -> None:
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(box, radius=14, fill=bg, outline=(205, 216, 238), width=3)
    if not img_path.exists():
        return
    src = Image.open(img_path).convert("RGBA")
    pad = 14
    tw, th = bw - 2 * pad, bh - 2 * pad
    scale = min(tw / src.width, th / src.height)
    nw, nh = max(1, int(src.width * scale)), max(1, int(src.height * scale))
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    px = x0 + (bw - nw) // 2
    py = y0 + (bh - nh) // 2
    canvas.paste(resized, (px, py), resized)


def draw_wrapped(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, max_w: int, font, fill=(30, 41, 59), line_gap: int = 7) -> int:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    cy = y
    for ln in lines:
        draw.text((x, cy), ln, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), ln, font=font)
        cy += (bbox[3] - bbox[1]) + line_gap
    return cy


def make_base_sheet(plate_badge: str, title: str, subtitle: str, page_num: int, total_pages: int = 25) -> Image.Image:
    im = Image.new("RGB", (W, H), (244, 247, 253))
    draw = ImageDraw.Draw(im)

    # Header institucional azul marino #000A62 con franja dorada #FFC800
    hdr_h = 152
    draw.rectangle((0, 0, W, hdr_h), fill=(8, 18, 94))
    draw.rectangle((0, hdr_h, W, hdr_h + 9), fill=(255, 200, 0))

    f_badge = load_font(25, bold=True)
    f_title = load_font(36, bold=True)
    f_sub = load_font(22, bold=False)
    f_right_b = load_font(24, bold=True)
    f_right = load_font(20, bold=False)

    # Insignia amarilla
    bb = draw.textbbox((0, 0), plate_badge, font=f_badge)
    bw = (bb[2] - bb[0]) + 42
    draw.rounded_rectangle((56, 26, 56 + bw, 70), radius=8, fill=(255, 200, 0))
    draw.text((77, 34), plate_badge, font=f_badge, fill=(0, 10, 98))

    draw.text((56 + bw + 24, 24), title, font=f_title, fill=(255, 255, 255))
    draw.text((56, 88), subtitle, font=f_sub, fill=(203, 216, 248))

    r1 = "Atlas Temático Copernicus · Resultados GEE"
    r2 = f"Iniciativa sv-amss (OPAMSS) · Pág. {page_num} / {total_pages}"
    w1 = draw.textbbox((0, 0), r1, font=f_right_b)[2]
    w2 = draw.textbbox((0, 0), r2, font=f_right)[2]
    draw.text((W - 56 - w1, 34), r1, font=f_right_b, fill=(255, 200, 0))
    draw.text((W - 56 - w2, 68), r2, font=f_right, fill=(226, 232, 248))

    # Footer institucional blanco con logos oficiales
    ftr_y = H - 104
    draw.rectangle((0, ftr_y - 6, W, ftr_y), fill=(255, 200, 0))
    draw.rectangle((0, ftr_y, W, H), fill=(255, 255, 255))

    logos = [
        ("logo-union-europea.png", False),
        ("logo-ccvah.png", False),
        ("logo-sisca.png", False),
        ("logo-sica.png", False),
        ("logo-cooperacion-alemana.png", False),
        ("logo-giz.png", False),
        ("logo-copernicus-lac-chile.png", False),
    ]
    lx = 56
    for lname, dark_bg in logos:
        lp = BRAND_DIR / lname
        if lp.exists():
            lg = Image.open(lp).convert("RGBA")
            th = 52
            tw = max(1, int(lg.width * (th / lg.height)))
            lg_r = lg.resize((tw, th), Image.Resampling.LANCZOS)
            if dark_bg:
                draw.rounded_rectangle((lx - 6, ftr_y + 20, lx + tw + 6, ftr_y + 26 + th), radius=6, fill=(12, 22, 89))
            im.paste(lg_r, (lx, ftr_y + 24), lg_r)
            lx += tw + 28

    f_foot = load_font(20, bold=True)
    ftxt = "Clúster de Asentamientos Humanos · Modelo Espacial de Valor del Suelo (Google Earth Engine + Embeddings V1)"
    fw = draw.textbbox((0, 0), ftxt, font=f_foot)[2]
    draw.text((W - 56 - fw, ftr_y + 38), ftxt, font=f_foot, fill=(12, 22, 89))

    return im


def build_plate_11() -> Image.Image:
    im = make_base_sheet(
        "LÁMINA 11 · PÍXEL 20 M",
        "Superficie Continua a Nivel de Píxel (20 m) — Valor Estimado del Suelo AMSS",
        "Google Satellite Embeddings V1 (64 bandas) + Open Buildings 2.5D + WorldCover 10 m + VIIRS DNB + Copernicus DEM GLO-30",
        page_num=23,
    )
    draw = ImageDraw.Draw(im)
    # Izquierda arriba: Suelo Urbano y Desarrollable 20 m; Izquierda abajo: Potencial Continuo Completo 20 m
    paste_fit(im, MOD_IMG_DIR / "amss_pixel_20m_urbano.png", (52, 188, 780, 1518), bg=(15, 23, 42))
    paste_fit(im, MOD_IMG_DIR / "amss_pixel_20m_potencial.png", (798, 188, 1525, 1518), bg=(15, 23, 42))
    f_cap = load_font(21, bold=True)
    draw.rounded_rectangle((70, 204, 520, 246), radius=6, fill=(8, 18, 94), outline=(255, 200, 0), width=2)
    draw.text((84, 212), "A. Píxel 20 m · Urbano y Desarrollable", font=f_cap, fill=(255, 200, 0))
    draw.rounded_rectangle((816, 204, 1255, 246), radius=6, fill=(8, 18, 94), outline=(255, 200, 0), width=2)
    draw.text((830, 212), "B. Píxel 20 m · Potencial Completo", font=f_cap, fill=(255, 200, 0))

    # Panel derecho de KPIs, parámetros y leyenda
    rx0, ry0, rx1, ry1 = 1555, 188, W - 52, 1518
    draw.rounded_rectangle((rx0, ry0, rx1, ry1), radius=14, fill=(255, 255, 255), outline=(205, 216, 238), width=3)
    draw.rectangle((rx0, ry0, rx1, ry0 + 10), fill=(8, 18, 94))

    f_h = load_font(26, bold=True)
    f_b = load_font(21, bold=True)
    f_p = load_font(20, bold=False)
    f_kpi_v = load_font(32, bold=True)
    f_kpi_l = load_font(18, bold=False)

    cx = rx0 + 26
    mw = (rx1 - rx0) - 52
    cy = ry0 + 28
    draw.text((cx, cy), "Métricas Empíricas de la Superficie a 20 m", font=f_h, fill=(8, 18, 94))
    cy += 42

    kpis = [
        ("3.85 M", "Píxeles válidos 20 m (3.63 M aptos)"),
        ("$8.66–$471", "Rango continuo estimado (USD/m²)"),
        ("$176.17", "Percentil P95 urbano (P99: $317.72/m²)"),
        ("71 Bandas", "64 Embeddings V1 + 7 físicas EO"),
    ]
    kw = (mw - 18) // 2
    kh = 100
    for idx, (kv, kl) in enumerate(kpis):
        col = idx % 2
        row = idx // 2
        bx0 = cx + col * (kw + 18)
        by0 = cy + row * (kh + 14)
        draw.rounded_rectangle((bx0, by0, bx0 + kw, by0 + kh), radius=10, fill=(241, 245, 254), outline=(190, 205, 238), width=2)
        draw.text((bx0 + 14, by0 + 12), kv, font=f_kpi_v, fill=(185, 28, 28) if idx in (1, 2) else (8, 18, 94))
        draw_wrapped(draw, kl, bx0 + 14, by0 + 54, kw - 24, f_kpi_l, fill=(51, 65, 85), line_gap=2)

    cy += 2 * (kh + 14) + 18
    draw.rounded_rectangle((cx, cy, cx + mw, cy + 178), radius=10, fill=(248, 250, 255), outline=(203, 213, 225), width=2)
    cy_in = draw_wrapped(
        draw,
        "Lectura territorial: La inferencia píxel a píxel (Halo = 0, Random Forest 200 árboles en espacio logarítmico) captura con nitidez el núcleo policéntrico de alta capitalización en San Benito, Escalón, Antiguo Cuscatlán y Santa Tecla (> $300/m²), separando automáticamente laderas escarpadas (> 35°) y cuerpos de agua.",
        cx + 16,
        cy + 14,
        mw - 32,
        f_p,
        fill=(30, 41, 59),
    )
    cy += 198

    draw.text((cx, cy), "Leyenda Homologada de Valor del Suelo (USD/m²)", font=f_h, fill=(8, 18, 94))
    cy += 40
    swatches = [
        ((103, 0, 31), "> $420 / m²", "Nodos corporativos prime (máx. $471.13/m²)"),
        ((179, 0, 0), "$300 – $420 / m²", "Ejes comerciales primarios y desarrollos verticales"),
        ((227, 74, 51), "$175 – $300 / m²", "Residencial consolidado medio-alto y servicios"),
        ((252, 141, 89), "$100 – $175 / m²", "Tejido urbano medio y corredores logísticos"),
        ((253, 187, 132), "$50 – $100 / m²", "Frentes de expansión periurbana activa"),
        ((253, 212, 158), "$30 – $50 / m²", "Transición rururbana de baja densidad"),
        ((254, 240, 217), "≤ $30 / m²", "Suelo rural, cafetal y reserva volcánica"),
    ]
    for rgb, lbl, desc in swatches:
        draw.rounded_rectangle((cx, cy + 4, cx + 46, cy + 34), radius=6, fill=rgb, outline=(30, 41, 59), width=2)
        draw.text((cx + 60, cy + 5), lbl, font=f_b, fill=(15, 23, 42))
        draw.text((cx + 245, cy + 6), desc, font=f_p, fill=(71, 85, 105))
        cy += 48

    return im


def build_plate_12() -> Image.Image:
    im = make_base_sheet(
        "LÁMINA 12 · MALLA 250 M",
        "Malla Continua Metropolitana (24,292 Celdas de 250 m) y Regímenes Morfológicos",
        "Teselación continua de 6.25 ha (148,875.1 ha en 28 distritos · 0 vacíos) con media, mediana, dispersión y morfología urbana",
        page_num=24,
    )
    draw = ImageDraw.Draw(im)
    paste_fit(im, FIG_DIR / "04_mapa_resultados_malla_continua_250m.png", (52, 188, 1495, 1518), bg=(255, 255, 255))

    rx0, ry0, rx1, ry1 = 1525, 188, W - 52, 1518
    draw.rounded_rectangle((rx0, ry0, rx1, ry1), radius=14, fill=(255, 255, 255), outline=(205, 216, 238), width=3)
    draw.rectangle((rx0, ry0, rx1, ry0 + 10), fill=(15, 118, 110))

    f_h = load_font(26, bold=True)
    f_b = load_font(20, bold=True)
    f_p = load_font(19, bold=False)

    cx = rx0 + 26
    mw = (rx1 - rx0) - 52
    cy = ry0 + 28
    draw.text((cx, cy), "Síntesis por Régimen Morfológico (24,292 Celdas)", font=f_h, fill=(8, 18, 94))
    cy += 44

    regimes = [
        ((185, 28, 28), "URBANO CONSOLIDADO (2,215 celdas · 13,825 ha)", "Media: $187.27/m² · Mediana: $169.24/m² · P90: $302.70/m² · Máx: $375.90/m²"),
        ((245, 158, 11), "PERIURBANO EN TRANSICIÓN (1,571 celdas · 9,578 ha)", "Media: $74.35/m² · Mediana: $67.49/m² · P90: $122.40/m² · Expansión activa"),
        ((15, 118, 110), "RURAL / RESERVA AMBIENTAL (20,506 celdas · 125,472 ha)", "Media: $33.35/m² · Mediana: $31.11/m² · Matriz agroforestal y relieve volcánico"),
    ]
    for rgb, rtitle, rstats in regimes:
        draw.rounded_rectangle((cx, cy, cx + mw, cy + 104), radius=10, fill=(248, 250, 252), outline=rgb, width=3)
        draw.rectangle((cx, cy, cx + 12, cy + 104), fill=rgb)
        draw.text((cx + 24, cy + 14), rtitle, font=f_b, fill=rgb)
        draw_wrapped(draw, rstats, cx + 24, cy + 48, mw - 36, f_p, fill=(30, 41, 59), line_gap=3)
        cy += 120

    cy += 12
    draw.text((cx, cy), "Jerarquía Distrital en Tejido Urbano Consolidado", font=f_h, fill=(8, 18, 94))
    cy += 40

    top_dist = [
        ("1. Antiguo Cuscatlán", "195 celdas urb.", "Mediana urb. $288.4/m²", "Máx. $375.9/m²"),
        ("2. San Salvador", "639 celdas urb.", "Mediana urb. $236.8/m²", "Máx. $373.4/m²"),
        ("3. Santa Tecla", "225 celdas urb.", "Mediana urb. $224.5/m²", "Máx. $352.1/m²"),
        ("4. Mejicanos", "205 celdas urb.", "Mediana urb. $156.4/m²", "Máx. $289.7/m²"),
        ("5. Cuscatancingo", "92 celdas urb.", "Mediana urb. $138.9/m²", "Máx. $231.0/m²"),
        ("6. Soyapango", "312 celdas urb.", "Mediana urb. $132.6/m²", "Máx. $254.8/m²"),
        ("7. San Marcos", "84 celdas urb.", "Mediana urb. $118.5/m²", "Máx. $198.4/m²"),
        ("8. Ilopango", "134 celdas urb.", "Mediana urb. $109.2/m²", "Máx. $214.6/m²"),
        ("9. Apopa", "146 celdas urb.", "Mediana urb. $94.8/m²", "Máx. $176.3/m²"),
    ]
    for idx, (dn, dc, dm, dx) in enumerate(top_dist):
        bg_row = (241, 245, 254) if idx % 2 == 0 else (255, 255, 255)
        draw.rectangle((cx, cy, cx + mw, cy + 42), fill=bg_row)
        draw.text((cx + 10, cy + 9), dn, font=f_b, fill=(15, 23, 42))
        draw.text((cx + 260, cy + 9), dc, font=f_p, fill=(71, 85, 105))
        draw.text((cx + 420, cy + 9), dm, font=f_b, fill=(185, 28, 28))
        draw.text((cx + 625, cy + 9), dx, font=f_p, fill=(30, 41, 59))
        cy += 44

    cy += 16
    draw_wrapped(
        draw,
        "Nota técnica: Cada polígono conserva VAL_EST_M2 (media), VAL_MED_M2 (mediana resistente a bordes de barranco), VAL_STD_M2 (dispersión intra-celda), PCT_EDIF, ALT_EDIF_M y PEND_DEG.",
        cx,
        cy,
        mw,
        f_p,
        fill=(71, 85, 105),
    )
    return im


def build_plate_13() -> Image.Image:
    im = make_base_sheet(
        "LÁMINA 13 · 425 UPDS Y VALIDACIÓN",
        "Imputación sin Vacíos de las 425 UPDs y Poder Predictivo de Google Embeddings V1",
        "281 UPDs observadas (OPAMSS / Oferta 2025) + 144 UPDs imputadas por GEE (57,648 ha) · Correlación empírica r = 0.7816",
        page_num=25,
    )
    draw = ImageDraw.Draw(im)

    # Izquierda: Mapa comparativo 425 UPDs
    paste_fit(im, FIG_DIR / "02_cobertura_territorial_upds_amss.png", (52, 188, 1210, 1020), bg=(255, 255, 255))
    # Abajo izquierda: Evaluación y tipologías
    paste_fit(im, FIG_DIR / "06_evaluacion_modelo_y_tipologias_urbanas.png", (52, 1044, 1210, 1518), bg=(255, 255, 255))
    # Derecha arriba: Correlaciones 71 bandas
    paste_fit(im, FIG_DIR / "05_correlaciones_google_embeddings_eo.png", (1238, 188, W - 52, 1020), bg=(255, 255, 255))

    # Derecha abajo: Síntesis ejecutiva de validación
    rx0, ry0, rx1, ry1 = 1238, 1044, W - 52, 1518
    draw.rounded_rectangle((rx0, ry0, rx1, ry1), radius=14, fill=(255, 255, 255), outline=(205, 216, 238), width=3)
    draw.rectangle((rx0, ry0, rx1, ry0 + 10), fill=(255, 200, 0))

    f_h = load_font(25, bold=True)
    f_b = load_font(20, bold=True)
    f_p = load_font(19, bold=False)

    cx = rx0 + 26
    mw = (rx1 - rx0) - 52
    cy = ry0 + 24
    draw.text((cx, cy), "Desempeño Estadístico y Predictores Clave (71 Bandas)", font=f_h, fill=(8, 18, 94))
    cy += 40

    bullets = [
        ("Ajuste empírico (281 UPDs):", "Pearson r = 0.7816 (r_log = 0.7238); mediana modelo $102.84 vs. observada $103.66 USD/m² (sesgo -0.79%)."),
        ("Cierre de vacíos (144 UPDs):", "57,647.5 ha completadas sin extrapolaciones erráticas (mediana imputada $35.14/m², media $50.69/m²)."),
        ("Significancia satelital:", "64 de las 71 bandas son significativas (p < 0.05) y 24 superan |r| ≥ 0.50 frente al log-valor del suelo."),
        ("Top predictores latentes y EO:", "A13 (r = -0.694), A32 (r = -0.660), A34 (r = +0.650), wc_trees (-0.625), wc_built (+0.621) y VIIRS (+0.578)."),
    ]
    for b_lbl, b_txt in bullets:
        draw.text((cx, cy), "• " + b_lbl, font=f_b, fill=(15, 23, 42))
        cy = draw_wrapped(draw, b_txt, cx + 22, cy + 26, mw - 24, f_p, fill=(51, 65, 85), line_gap=3) + 8

    return im


def main() -> None:
    DESC_DIR.mkdir(parents=True, exist_ok=True)
    pages = [build_plate_11(), build_plate_12(), build_plate_13()]

    standalone_pdf = DESC_DIR / "Atlas_Resultados_Modelo_Suelo_GEE_AMSS.pdf"
    pages[0].save(
        standalone_pdf,
        "PDF",
        resolution=float(DPI),
        save_all=True,
        append_images=pages[1:],
    )
    print(f"[OK] Generado PDF autónomo de resultados GEE: {standalone_pdf.name} ({standalone_pdf.stat().st_size / 1e6:.2f} MB)")

    base_pdf_path = DESC_DIR / "atlas_copernicus_zona_estudio.pdf"
    proj_pdf_path = DESC_DIR / "atlas_copernicus_sv-amss.pdf"

    if base_pdf_path.exists():
        doc = pdfium.PdfDocument(str(base_pdf_path))
        # Mantener únicamente las 22 páginas originales de observación terrestre antes de anexar las 3 láminas GEE
        while len(doc) > 22:
            doc.del_page(len(doc) - 1)
        addon = pdfium.PdfDocument(str(standalone_pdf))
        doc.import_pages(addon)
        tmp_out = DESC_DIR / "_tmp_atlas_merged.pdf"
        doc.save(str(tmp_out))
        doc.close()
        addon.close()

        shutil.move(str(tmp_out), str(base_pdf_path))
        shutil.copy2(str(base_pdf_path), str(proj_pdf_path))
        verify = pdfium.PdfDocument(str(base_pdf_path))
        n_final = len(verify)
        verify.close()
        print(
            f"[OK] Actualizados {base_pdf_path.name} y {proj_pdf_path.name}: "
            f"{n_final} páginas totales ({base_pdf_path.stat().st_size / 1e6:.2f} MB)"
        )


if __name__ == "__main__":
    main()
