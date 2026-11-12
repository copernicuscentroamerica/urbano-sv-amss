#!/usr/bin/env python3
"""
Generador estático determinista (scripts/build_site.py) para cada repositorio de iniciativa
(urbano-{id}) y para la plantilla común (clusterurbano-proyecto-template).
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import shutil
import statistics
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from markdown_lite import render_markdown
from site_common import (
    TEMPLATE_VERSION,
    THEME_VERSION,
    SiteContext,
    badge_html,
    compute_site_context,
    esc,
    format_spanish_date,
    render_hero_team,
    render_project_institutions_band,
    render_regional_institutional_band,
    render_team_section_html,
    render_upper_institutional_bar,
)

ROOT = Path(__file__).resolve().parent.parent


def render_link_or_pending(url: str | None, active_label: str, pending_label: str, btn_class: str = "btn btn-outline", declared_only: bool = False) -> str:
    if url and url.startswith("https://"):
        suffix = " (referencia declarada)" if declared_only else " ↗"
        return (
            f'<a class="{btn_class}" href="{html.escape(url, quote=True)}" '
            f'target="_blank" rel="noopener noreferrer">{html.escape(active_label + suffix)}</a>'
        )
    return f'<span class="btn-disabled" role="status">{html.escape(pending_label)}</span>'


def render_status_strip(manifest: dict[str, Any]) -> str:
    st = manifest["status"]
    pmv = manifest["pmv"]
    tr = st["technical_review"]
    iv = st["institutional_validation"]
    ad = st["adoption"]
    return f"""
    <section class="status-strip" aria-label="Estados independientes de la iniciativa">
      <div class="status-cell">
        <div class="status-cell-label">Alcance del PMV</div>
        <div>{badge_html(pmv.get("scope_status"))}</div>
      </div>
      <div class="status-cell">
        <div class="status-cell-label">Desarrollo</div>
        <div>{badge_html(st.get("development"))}</div>
      </div>
      <div class="status-cell">
        <div class="status-cell-label">Demostración</div>
        <div>{badge_html(st.get("demo"))}</div>
      </div>
      <div class="status-cell">
        <div class="status-cell-label">Revisión técnica</div>
        <div>{badge_html(tr.get("state"))}</div>
      </div>
      <div class="status-cell">
        <div class="status-cell-label">Validación institucional</div>
        <div>{badge_html(iv.get("state"))}</div>
      </div>
      <div class="status-cell">
        <div class="status-cell-label">Adopción</div>
        <div>{badge_html(ad.get("state"))}</div>
      </div>
    </section>
    """


def render_shell(
    *,
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    page_title: str,
    active_nav: str,
    hero_html: str,
    body_html: str,
    include_maplibre: bool = False,
) -> str:
    pid = manifest["id"]
    short_title = repo_cfg.get("short_title") or manifest["title"]
    country_name = manifest["country"]["name"]
    country_code = manifest["country"]["code"]

    robots_meta = (
        '<meta name="robots" content="noindex, nofollow">'
        if ctx.effective_mode != "canonical"
        else '<meta name="robots" content="index, follow">'
    )

    canonical_link_note = ""
    if manifest["links"].get("website"):
        w = html.escape(manifest["links"]["website"], quote=True)
        canonical_link_note = f' · <a href="{w}">Ir a la versión canónica publicada</a>'
    elif manifest["links"].get("repository"):
        r = html.escape(manifest["links"]["repository"], quote=True)
        canonical_link_note = f' · <a href="{r}" target="_blank" rel="noopener noreferrer">Repositorio canónico</a>'

    work_banner_html = ""
    if ctx.effective_mode != "canonical":
        mode_reason = (
            f" Vista generada desde {html.escape(ctx.github_repository)}."
            if ctx.github_repository
            else " Previsualización local o repositorio canónico pendiente de verificación."
        )
        work_banner_html = f"""
        <div class="work-banner" role="region" aria-label="Aviso de versión de trabajo">
          <div class="container">
            <span>Vista de trabajo (versión no canónica) · ID estable: <code>{esc(pid)}</code>.{mode_reason}</span>
            <span>Solo el repositorio canónico publica la referencia compartida del equipo{canonical_link_note}</span>
          </div>
        </div>
        """

    hub_link_html = (
        f'<a href="{html.escape(ctx.hub_url, quote=True)}">← Volver al Portal de la Comunidad Urbana</a>'
        if ctx.hub_url and ctx.hub_url.startswith("https://")
        else '<span>Portal regional: <code>clusterurbano</code> (enlace activo al publicar el hub)</span>'
    )

    upper_bar_html = render_upper_institutional_bar(
        ctx,
        hub_link_html,
        f"Comunidad Urbana Copernicus Centroamérica · <strong>{esc(country_name)} ({esc(country_code)})</strong> · ID: <code>{esc(pid)}</code>",
    )

    # La banda institucional regional se ubica al final de todas las páginas, justo encima del pie
    bottom_regional_band_html = render_regional_institutional_band(ctx, extra_class="is-footer-band")

    nav_items = [
        ("inicio", "Inicio", ctx.site_url("")),
        ("proyecto", "Proyecto", ctx.site_url("proyecto/")),
        ("aplicacion", "Geovisor (GeoLibre)", ctx.site_url("aplicacion/")),
        ("modelo-suelo", "Modelo Valor Suelo (GEE)", ctx.site_url("modelo-suelo/")),
        ("metodologia", "Metodología", ctx.site_url("metodologia/")),
        ("resultados", "Resultados y Atlas", ctx.site_url("resultados/")),
        ("colaborar", "Colaborar", ctx.site_url("colaborar/")),
    ]
    nav_lis = []
    for key, label, href in nav_items:
        cur = ' aria-current="page"' if key == active_nav else ""
        nav_lis.append(f'<li><a href="{html.escape(href, quote=True)}"{cur}>{html.escape(label)}</a></li>')

    maplibre_head = ""
    maplibre_scripts = ""
    if include_maplibre:
        maplibre_head = (
            '<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" crossorigin="anonymous">'
        )
        maplibre_scripts = (
            '<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js" crossorigin="anonymous"></script>\n'
            f'  <script src="{html.escape(ctx.site_url("assets/js/geovisor.js"), quote=True)}?v=2.1.0"></script>'
        )

    updated_raw = manifest["governance"].get("content_updated_at")
    updated_label = format_spanish_date(updated_raw, "Fecha de actualización no informada")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(page_title)} · {esc(short_title)}</title>
  <meta name="description" content="{esc(manifest['summary'])}">
  {robots_meta}
  <link rel="stylesheet" href="{html.escape(ctx.site_url('assets/css/styles.css'), quote=True)}?v=2.1.0">
  {maplibre_head}
</head>
<body>
  <a class="skip-link" href="#contenido-principal">Saltar al contenido principal</a>
  {work_banner_html}
  {upper_bar_html}
  <header class="site-header">
    <div class="container header-inner">
      <a class="brand" href="{html.escape(ctx.site_url(''), quote=True)}">
        <span class="brand-mark" aria-hidden="true">{esc(country_code)}</span>
        <span class="brand-text">
          <span class="brand-title">{esc(short_title)}</span>
          <span class="brand-subtitle">Clúster de Asentamientos Humanos · Fase II</span>
        </span>
      </a>
      <button class="nav-toggle" type="button" data-nav-toggle aria-expanded="false" aria-controls="menu-proyecto">
        Menú ☰
      </button>
      <nav id="menu-proyecto" class="site-nav" data-site-nav aria-label="Navegación de la iniciativa">
        <ul>
          {"".join(nav_lis)}
        </ul>
      </nav>
    </div>
  </header>

  {hero_html}

  <main id="contenido-principal">
    <div class="container">
      {body_html}
    </div>
  </main>

  {bottom_regional_band_html}
  <footer class="site-footer">
    <div class="container footer-grid">
      <div>
        <p class="footer-title">{esc(manifest['title'])}</p>
        <p>Identificador estable: <code>{esc(pid)}</code> · Grupos de origen: {esc(", ".join(str(g) for g in manifest["source_groups"]))} · Tema común: <code>{esc(THEME_VERSION)}</code>.</p>
        <p>Última actualización del contenido por el equipo: <strong>{esc(updated_label)}</strong>.</p>
      </div>
      <div>
        <p class="footer-title">Navegación rápida</p>
        <p>
          <a href="{html.escape(ctx.site_url('proyecto/'), quote=True)}">Ficha completa</a> ·
          <a href="{html.escape(ctx.site_url('aplicacion/'), quote=True)}">Geovisor GeoLibre</a> ·
          <a href="{html.escape(ctx.site_url('modelo-suelo/'), quote=True)}">Modelo Valor Suelo (GEE)</a> ·
          <a href="{html.escape(ctx.site_url('metodologia/'), quote=True)}">Metodología</a> ·
          <a href="{html.escape(ctx.site_url('resultados/'), quote=True)}">Resultados y Atlas</a> ·
          <a href="{html.escape(ctx.site_url('colaborar/'), quote=True)}">Colaborar y Logos</a>
        </p>
      </div>
      <div>
        <p class="footer-title">Transparencia documental</p>
        <p>Este sitio distingue afirmaciones declaradas en el perfil, propuestas técnicas de trabajo y datos pendientes de confirmar. Una página publicada no equivale por sí sola a validación institucional.</p>
      </div>
    </div>
  </footer>

  <script src="{html.escape(ctx.site_url('assets/js/ui.js'), quote=True)}?v=2.1.0"></script>
  {maplibre_scripts}
</body>
</html>
"""


def make_geolibre_layer_style(raw_style: dict[str, Any] | None) -> dict[str, Any]:
    s = raw_style or {}
    raw_fc = str(s.get("fillColor") or s.get("fill_color") or "#0d9488")
    fill_color = "#e34a33" if raw_fc.startswith("auto_") else raw_fc
    stroke_color = str(s.get("lineColor") or s.get("strokeColor") or s.get("stroke_color") or "#115e59")
    stroke_width = float(s.get("lineWidth") or s.get("strokeWidth") or s.get("stroke_width") or 2)
    fill_opacity = float(
        s.get("fillOpacity")
        if s.get("fillOpacity") is not None
        else (s.get("fill_opacity") if s.get("fill_opacity") is not None else 0.35)
    )
    circle_radius = float(s.get("circleRadius") or 6)
    circle_color = str(s.get("circleColor") or fill_color)
    thematic_prop = str(s.get("thematic_field") or "")
    vec_mode = "graduated" if raw_fc in ("auto_gee_malla_250m", "auto_gee_upd_425", "auto_lisa_2025", "auto_upd_2020_2026", "auto_upd_2007_2019") else "single"
    vec_stops = (
        [
            {"value": 0, "color": "#FEF0D9"},
            {"value": 50, "color": "#FDCC8A"},
            {"value": 100, "color": "#FC8D59"},
            {"value": 175, "color": "#E34A33"},
            {"value": 300, "color": "#B30000"},
        ]
        if vec_mode == "graduated"
        else [
            {"value": 0, "color": "#dbeafe"},
            {"value": 1, "color": fill_color},
        ]
    )
    return {
        "minZoom": 0,
        "maxZoom": 24,
        "fillColor": fill_color,
        "strokeColor": stroke_color,
        "strokeWidth": stroke_width,
        "strokeWidthUnit": "pixels",
        "strokeOpacity": 1,
        "strokeDash": [],
        "strokeBlur": 0,
        "fillOpacity": fill_opacity,
        "circleRadius": circle_radius,
        "textColor": "#111827",
        "textHaloColor": "#ffffff",
        "textHaloWidth": 2,
        "textSize": 14,
        "labels": {
            "enabled": False,
            "field": "",
            "expression": "",
            "placement": "point",
            "size": 12,
            "color": "#111827",
            "haloColor": "#ffffff",
            "haloWidth": 1.5,
            "minZoom": 0,
            "maxZoom": 24,
            "allowOverlap": False,
            "anchor": "center",
            "offsetX": 0,
            "offsetY": 0,
            "rotation": 0,
            "maxWidth": 10,
            "transform": "none",
            "numberFormatEnabled": False,
            "numberDecimals": 0,
            "numberLocale": "",
            "dedupe": "off",
            "sizeExpression": "",
            "colorExpression": "",
            "opacityExpression": "",
            "visibilityExpression": "",
            "priorityExpression": "",
        },
        "extrusionEnabled": False,
        "extrusionColor": fill_color,
        "extrusionOpacity": 0.8,
        "extrusionHeightProperty": "height",
        "extrusionHeightScale": 1,
        "extrusionBase": 0,
        "extrusionBaseProperty": "",
        "extrusionBaseScale": 1,
        "extrusionFloorHeight": 0,
        "extrusionAdvancedStyleEnabled": False,
        "extrusionColorExpression": "",
        "extrusionHeightExpression": "",
        "extrusionBaseExpression": "",
        "elevation3dEnabled": False,
        "elevation3dVerticalScale": 1,
        "elevation3dOffset": 0,
        "vectorStyleMode": vec_mode,
        "vectorStyleProperty": thematic_prop,
        "vectorStyleClassCount": 5,
        "vectorStyleColorRamp": "orrd" if vec_mode == "graduated" else "viridis",
        "vectorStyleClassificationScheme": "manual" if vec_mode == "graduated" else "equal-interval",
        "vectorStyleStops": vec_stops,
        "vectorStyleExpression": "",
        "vectorRules": [],
        "proportionalSizeEnabled": False,
        "proportionalSizeProperty": "",
        "proportionalSizeMinValue": 0,
        "proportionalSizeMaxValue": 100,
        "proportionalSizeMinRadius": 4,
        "proportionalSizeMaxRadius": 24,
        "fillPattern": "none",
        "fillPatternColor": stroke_color,
        "fillPatternSvg": "",
        "markerEnabled": False,
        "markerShape": "circle",
        "markerColor": circle_color,
        "markerSize": 18,
        "markerSvg": "",
        "simpleStyleEnabled": False,
        "diagramType": "none",
        "diagramFields": [],
        "diagramSizeMode": "fixed",
        "diagramSize": 30,
        "diagramSizeProperty": "",
        "diagramMinZoom": 0,
        "diagramDeclutter": False,
        "pointRenderer": "single",
        "heatmapRadius": 30,
        "heatmapIntensity": 1,
        "heatmapColorRamp": "turbo",
        "heatmapWeightProperty": "",
        "clusterRadius": 50,
        "clusterMaxZoom": 14,
        "invertedFillEnabled": False,
        "lineDecoration": "none",
        "lineDecorationColor": "",
        "lineDecorationSize": 12,
        "lineDecorationSpacing": 80,
        "geometryGenerator": "none",
        "geometryGeneratorBufferDistance": 1000,
        "geometryGeneratorBufferProperty": "",
        "geometryGeneratorFillColor": "#f59e0b",
        "geometryGeneratorStrokeColor": "#b45309",
        "geometryGeneratorStrokeWidth": 2,
        "geometryGeneratorOpacity": 0.4,
        "geometryGeneratorCircleRadius": 5,
        "geometryGeneratorSizeProperty": "",
        "geometryGeneratorSizeMinValue": 0,
        "geometryGeneratorSizeMaxValue": 100,
        "geometryGeneratorSizeMinRadius": 4,
        "geometryGeneratorSizeMaxRadius": 24,
        "rasterBrightnessMin": 0,
        "rasterBrightnessMax": 1,
        "rasterSaturation": 0,
        "rasterContrast": 0,
        "rasterHueRotate": 0,
        "blendMode": "normal",
    }


def build_geolibre_project_json(
    layers_cfg: dict[str, Any],
    manifest: dict[str, Any],
    ctx: SiteContext,
) -> dict[str, Any]:
    pid = manifest["id"]
    active_layers: list[dict[str, Any]] = []
    styles_map: dict[str, Any] = {}
    legend_order: list[str] = []

    for lyr in layers_cfg.get("layers", []):
        sp = lyr.get("source_path")
        st = lyr.get("status")
        if not sp or st not in ("publicado", "en_revision"):
            continue
        lid = lyr["id"]
        resolved = sp if str(sp).startswith("https://") else ctx.full_url(str(sp))
        fmt = str(lyr.get("format") or "geojson").lower()
        layer_type = "geojson" if fmt in ("geojson", "json", "kml") else ("cog" if fmt in ("tif", "tiff", "cog") else ("pmtiles" if fmt == "pmtiles" else "raster"))
        full_style = make_geolibre_layer_style(lyr.get("style"))
        styles_map[lid] = full_style
        legend_order.append(lid)

        embedded_geojson = None
        if not str(sp).startswith("https://") and fmt in ("geojson", "json"):
            local_file = ROOT / str(sp)
            if local_file.exists() and local_file.stat().st_size <= 512 * 1024:
                try:
                    parsed_gj = json.loads(local_file.read_text(encoding="utf-8"))
                    if isinstance(parsed_gj, dict) and parsed_gj.get("type") == "FeatureCollection":
                        embedded_geojson = parsed_gj
                except Exception:
                    embedded_geojson = None

        layer_entry: dict[str, Any] = {
            "id": lid,
            "name": lyr["title"],
            "type": layer_type,
            "source": {
                "type": "geojson" if layer_type == "geojson" else "raster",
                "url": resolved,
                "data": resolved if layer_type == "geojson" else None,
            },
            "visible": True,
            "opacity": 1,
            "style": full_style,
            "metadata": {
                "sourceUrl": resolved,
                "status": st,
                "resolution": lyr.get("resolution"),
                "caveat": lyr.get("caveat"),
            },
        }
        if embedded_geojson is not None:
            layer_entry["geojson"] = embedded_geojson
        active_layers.append(layer_entry)

    mv = layers_cfg.get("map_view", {})
    center = mv.get("center", [-84.0, 13.5])
    zoom = float(mv.get("zoom", 10))
    map_view_obj: dict[str, Any] = {
        "center": [float(center[0]), float(center[1])],
        "zoom": zoom,
        "bearing": 0,
        "pitch": 0,
    }
    if mv.get("bbox") and isinstance(mv["bbox"], list) and len(mv["bbox"]) == 4:
        map_view_obj["bbox"] = [float(x) for x in mv["bbox"]]

    return {
        "id": f"geolibre-{pid}",
        "version": "0.2.0",
        "name": f"{manifest['country']['name']} · {layers_cfg.get('title', manifest['title'])}",
        "mapView": map_view_obj,
        "basemapStyleUrl": "https://tiles.openfreemap.org/styles/positron",
        "basemapVisible": True,
        "basemapOpacity": 1,
        "blankBackgroundColor": None,
        "primaryRenderer": "maplibre",
        "layers": active_layers,
        "selectedLayerId": active_layers[0]["id"] if active_layers else None,
        "layerGroups": [],
        "styles": styles_map,
        "preferences": {
            "map": {
                "restrictBounds": False,
                "bounds": [-180, -85, 180, 85],
                "minZoom": 0,
                "maxZoom": 24,
                "maxPitch": 85,
                "renderWorldCopies": True,
                "projection": "mercator",
                "ellipsoidId": "earth",
                "scaleUnit": "metric",
                "showPointerElevation": False,
                "terrainEnabled": False,
                "coordinateFormat": "dd",
                "zoomToNewLayers": True,
            },
            "environmentVariables": [],
            "geocoding": {
                "providerId": "nominatim",
                "apiKeys": {},
            },
        },
        "legend": {
            "title": "Capas del proyecto",
            "groupByLayer": True,
            "order": legend_order,
            "overrides": {},
        },
        "comments": [],
        "metadata": {
            "project_id": pid,
            "description": manifest["summary"],
            "schema_version": manifest["schema_version"],
            "community": "Comunidad Urbana Copernicus Centroamérica",
            "referential_frame_only": len(active_layers) == 0,
            "note": mv.get("reference_note"),
            "planned_layers": [
                {
                    "id": lyr["id"],
                    "title": lyr["title"],
                    "status": lyr["status"],
                    "expected_file_hint": lyr.get("expected_file_hint"),
                    "caveat": lyr.get("caveat"),
                }
                for lyr in layers_cfg.get("layers", [])
            ],
        },
    }


def has_declared_demo_statement(manifest: dict[str, Any]) -> bool:
    for st in manifest.get("provenance", {}).get("statements", []):
        if st.get("pointer") == "/links/demo" and st.get("status") == "declarado":
            return True
    return False


def build_home_page(
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    layers_cfg: dict[str, Any],
    branding: dict[str, Any],
) -> str:
    iu = manifest["institutional_use"]
    institutions_li = "".join(f"<li>{esc(inst)}</li>" for inst in iu.get("institutions", [])) or "<li>Institución por confirmar</li>"
    limitations_li = "".join(f"<li>{esc(lim)}</li>" for lim in manifest.get("limitations", [])[:5])
    tags_spans = "".join(f'<span class="tag">{esc(t)}</span>' for t in manifest.get("tags", []))

    demo_declared_only = has_declared_demo_statement(manifest) and manifest["status"].get("demo") != "disponible"
    repo_btn = render_link_or_pending(
        manifest["links"].get("repository"),
        "Ver repositorio canónico",
        "Repositorio canónico en preparación",
        "btn btn-outline-light",
    )
    demo_btn = ""
    if manifest["links"].get("demo"):
        demo_btn = render_link_or_pending(
            manifest["links"].get("demo"),
            "Ver demostrador externo",
            "",
            "btn btn-outline-light",
            declared_only=demo_declared_only,
        )

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">{esc(manifest['country']['name'])} · {esc(manifest['territory']['label'])}</span>
          <span class="badge badge-country">Grupos de origen: {esc(', '.join(str(g) for g in manifest['source_groups']))}</span>
          {badge_html(manifest['pmv']['scope_status'], 'Alcance PMV')}
        </div>
        <h1>{esc(manifest['title'])}</h1>
        {render_hero_team(manifest)}
        <p class="hero-lead">{esc(manifest['summary'])}</p>
        <div class="hero-actions">
          <a class="btn btn-primary" href="{html.escape(ctx.site_url('aplicacion/'), quote=True)}">Abrir Geovisor (GeoLibre)</a>
          <a class="btn btn-teal" href="{html.escape(ctx.site_url('modelo-suelo/'), quote=True)}">📊 Modelo Valor del Suelo (GEE): Metodología, Resultados y Script →</a>
          <a class="btn btn-outline-light" href="{html.escape(ctx.site_url('proyecto/'), quote=True)}">Leer ficha completa</a>
          <a class="btn btn-outline-light" href="{html.escape(ctx.site_url('colaborar/'), quote=True)}">Colaborar (Fork / PR)</a>
          {repo_btn}
          {demo_btn}
        </div>
      </div>
    </section>
    """

    mv = layers_cfg.get("map_view", {})
    repo_url = (manifest["links"].get("repository") or "").rstrip("/")
    hub_base = (ctx.hub_url or "https://copernicuscentroamerica.github.io/clusterurbano/").rstrip("/")
    ejercicio_url = f"{hub_base}/ejercicio/"
    new_task_url = f"{repo_url}/issues/new?template=01-tarea-pmv.yml" if repo_url else ctx.site_url("colaborar/")
    support_url = f"{repo_url}/issues/new?template=02-bloqueo-apoyo.yml" if repo_url else ctx.site_url("colaborar/")
    pulls_url = f"{repo_url}/pulls" if repo_url else ctx.site_url("colaborar/")
    colaborar_logos_href = ctx.site_url("colaborar/") + "#anadir-actualizar-logos"

    body = f"""
    {render_status_strip(manifest)}

    <section class="section">
      <div class="card" style="border-left:4px solid var(--c-brand-blue);">
        <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:0.75rem;">
          <div>
            <span class="badge badge-ok">Trabajar en este proyecto</span>
            <h2 style="margin:0.35rem 0 0.25rem;font-size:1.2rem;">Accesos directos para participantes e instituciones</h2>
            <p style="margin:0;font-size:0.9rem;color:var(--c-text-muted);">Usa estos enlaces para incorporar avances, actualizar logos institucionales, ejecutar el ejercicio práctico (Google Colab o Google Earth Engine con la misma cuenta de Google que uses en Antigravity), registrar tareas o solicitar apoyo técnico.</p>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:0.5rem;">
            {f'<a class="btn btn-outline btn-xs" href="{html.escape(repo_url, quote=True)}" target="_blank" rel="noopener noreferrer">Repositorio oficial ↗</a>' if repo_url else ''}
            <a class="btn btn-teal btn-xs" href="{html.escape(ctx.site_url('colaborar/'), quote=True)}">Guía de incorporación</a>
            <a class="btn btn-outline btn-xs" href="{html.escape(colaborar_logos_href, quote=True)}">Añadir o actualizar logos</a>
            <a class="btn btn-primary btn-xs" href="{html.escape(ejercicio_url, quote=True)}">Ejercicio Colab / GEE ↗</a>
            <a class="btn btn-outline btn-xs" href="{html.escape(new_task_url, quote=True)}" target="_blank" rel="noopener noreferrer">Crear tarea ↗</a>
            <a class="btn btn-outline btn-xs" href="{html.escape(support_url, quote=True)}" target="_blank" rel="noopener noreferrer">Solicitar apoyo ↗</a>
            <a class="btn btn-outline btn-xs" href="{html.escape(pulls_url, quote=True)}" target="_blank" rel="noopener noreferrer">Enviar o revisar PR ↗</a>
          </div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-header">
        <h2>Contexto institucional y territorial</h2>
        <div class="tag-list">{tags_spans}</div>
      </div>
      <div class="grid-3">
        <article class="card">
          <span class="badge badge-declarado">Según el perfil</span>
          <h3>Problema que aborda</h3>
          <p>{esc(iu.get('problem'))}</p>
          <p><strong>Territorio:</strong> {esc(manifest['territory']['label'])}</p>
        </article>
        <article class="card">
          <span class="badge badge-declarado">Según el perfil</span>
          <h3>Instituciones y usuario principal</h3>
          <ul>{institutions_li}</ul>
          <p><strong>Usuario directo:</strong> {esc(iu.get('primary_user'), 'No indicado en el perfil')}</p>
        </article>
        <article class="card">
          <span class="badge badge-declarado">Según el perfil</span>
          <h3>Decisión pública que apoya</h3>
          <p>{esc(iu.get('decision_supported'), 'No indicado en el perfil')}</p>
          <p><strong>Beneficio esperado:</strong> {esc(iu.get('expected_benefit'), 'No indicado en el perfil')}</p>
        </article>
      </div>
    </section>

    {render_team_section_html(manifest)}

    <section class="section">
      <div class="grid-2">
        <article class="card">
          <span class="badge badge-propuesta">Alcance de trabajo</span>
          <h3>Producto Mínimo Viable (PMV) previsto</h3>
          <p>{esc(manifest['pmv'].get('description'), 'Alcance pendiente de confirmar con el equipo.')}</p>
          <div class="callout callout-muted">
            <strong>Ámbito espacial documentado</strong>
            <span>{esc(mv.get('area_declared', manifest['territory']['label']))}</span>
          </div>
          <div class="card-footer">
            <a class="btn btn-teal" href="{html.escape(ctx.site_url('proyecto/'), quote=True)}">Ver criterios de aceptación ({len(manifest['pmv'].get('acceptance_criteria', []))})</a>
            <a class="btn btn-outline" href="{html.escape(ctx.site_url('metodologia/'), quote=True)}">Ver datos y método</a>
          </div>
        </article>

        <article class="card">
          <span class="badge badge-warn">Geovisor basado en GeoLibre</span>
          <h3>Espacio de visualización geoespacial</h3>
          <p>Este repositorio incorpora un visor integrado basado en <strong>MapLibre GL JS</strong> y exporta un proyecto estándar <code>geovisor/proyecto.geolibre.json</code> (v0.2.0) compatible con <strong>GeoLibre Studio</strong> para desplegar las capas en <code>geovisor/capas/</code>.</p>
          <p><strong>Capas preconfiguradas en catálogo:</strong> {len(layers_cfg.get('layers', []))} capas previstas ({sum(1 for l in layers_cfg.get('layers', []) if l.get('status') in ('publicado', 'en_revision'))} publicadas/en revisión actualmente).</p>
          <div class="card-footer">
            <a class="btn btn-primary" href="{html.escape(ctx.site_url('aplicacion/'), quote=True)}">Explorar Geovisor →</a>
            <a class="btn btn-outline" href="{html.escape(ctx.site_url('resultados/'), quote=True)}">Contribución al Atlas</a>
          </div>
        </article>
      </div>
    </section>

    <section class="section">
      <div class="callout callout-warn">
        <strong>Limitaciones, discrepancias y cautelas documentadas</strong>
        <ul>{limitations_li}</ul>
      </div>
    </section>

    {render_project_institutions_band(ctx, branding, manifest, colaborar_href=colaborar_logos_href)}
    """

    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="Inicio",
        active_nav="inicio",
        hero_html=hero,
        body_html=body,
    )


def build_proyecto_page(
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    project_md: str,
    pmv_md: str,
    branding: dict[str, Any],
) -> str:
    ac_rows = []
    for ac in manifest["pmv"].get("acceptance_criteria", []):
        ac_rows.append(
            f"<tr><td><code>{esc(ac['id'])}</code></td>"
            f"<td>{esc(ac['description'])}</td>"
            f"<td>{badge_html(ac['status'])}</td>"
            f"<td>{esc(ac.get('evidence_required'))}</td></tr>"
        )
    ac_table = (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>ID</th><th>Criterio de aceptación</th><th>Procedencia</th><th>Evidencia requerida</th>"
        "</tr></thead><tbody>" + "".join(ac_rows) + "</tbody></table></div>"
        if ac_rows
        else "<p>Criterios de aceptación pendientes de definir.</p>"
    )

    src_map = {s["id"]: s["label"] for s in manifest["provenance"]["sources"]}
    src_rows = []
    for s in manifest["provenance"]["sources"]:
        url_cell = (
            f'<a href="{html.escape(s["url"], quote=True)}" target="_blank" rel="noopener noreferrer">Abrir referencia externa ↗</a>'
            if s.get("url")
            else "Documento del expediente técnico de la cartera"
        )
        src_rows.append(
            f"<tr><td><strong>{esc(s['label'])}</strong><br><small style='color:var(--c-text-muted);'>Código interno de trazabilidad: <code>{esc(s['id'])}</code></small></td><td>{url_cell}</td></tr>"
        )

    stmt_rows = []
    for st in manifest["provenance"]["statements"]:
        ptr = st["pointer"] or "/ (raíz)"
        sids = ", ".join(f"{sid} ({src_map.get(sid, sid)})" for sid in st.get("source_ids", [])) or "—"
        stmt_rows.append(
            f"<tr><td><code>{esc(ptr)}</code></td><td>{badge_html(st['status'])}</td>"
            f"<td>{esc(sids)}</td><td>{esc(st.get('note'), '—')}</td></tr>"
        )

    gov = manifest.get("governance", {})
    updated_label = format_spanish_date(gov.get("content_updated_at"), "Pendiente de informar")
    repo_url = (manifest["links"].get("repository") or "").rstrip("/")
    support_url = f"{repo_url}/issues/new?template=02-bloqueo-apoyo.yml" if repo_url else ctx.site_url("colaborar/")
    colaborar_logos_href = ctx.site_url("colaborar/") + "#anadir-actualizar-logos"

    figuras_dir = ROOT / "web" / "assets" / "img" / "figuras"
    figuras_html = ""
    if figuras_dir.is_dir():
        fig_files = sorted(
            f for f in figuras_dir.iterdir()
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".webp")
        )
        if fig_files:
            fig_cards = []
            for ff in fig_files:
                f_url = html.escape(ctx.site_url(f"assets/img/figuras/{ff.name}"), quote=True)
                f_label = esc(ff.stem.replace("_", " ").capitalize())
                fig_cards.append(
                    f"""
                    <article class="card">
                      <span class="badge badge-ok">Evidencia gráfica del repositorio</span>
                      <h3 style="margin:0.35rem 0 0.5rem;font-size:1rem;">{f_label}</h3>
                      <a href="{f_url}" target="_blank" rel="noopener noreferrer" style="display:block;border:1px solid var(--c-border);border-radius:8px;overflow:hidden;background:#070A14;">
                        <img src="{f_url}" alt="{f_label}" style="width:100%;height:auto;display:block;" loading="lazy">
                      </a>
                    </article>
                    """
                )
            figuras_html = f"""
            <section class="section">
              <h2>Figuras y visualizaciones analíticas incorporadas por el equipo</h2>
              <p>Gráficos y salidas analíticas generadas a partir de los scripts del proyecto en <code>src/</code> y almacenadas en <code>web/assets/img/figuras/</code>:</p>
              <div class="grid-2">{"".join(fig_cards)}</div>
            </section>
            """

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Ficha completa del proyecto</span>
          <span class="badge badge-country">{esc(manifest['id'])}</span>
        </div>
        <h1>{esc(manifest['title'])}</h1>
        {render_hero_team(manifest)}
        <p class="hero-lead">Alcance territorial en {esc(manifest['territory']['label'])}, criterios del PMV, instituciones participantes y trazabilidad documental desde <code>project.json</code>.</p>
      </div>
    </section>
    """

    team_names_str = ", ".join(m.get("name", "") for m in (manifest.get("team") or []) if isinstance(m, dict) and m.get("name")) or "Por confirmar"

    body = f"""
    {render_status_strip(manifest)}

    <section class="section">
      <div class="card">
        <h3>Gobernanza, coordinación operativa y fechas clave</h3>
        <div class="grid-3">
          <div>
            <p><strong>Instituciones participantes:</strong><br>{esc(", ".join(manifest["institutional_use"].get("institutions", [])), "Por confirmar")}</p>
            <p><strong>Integrantes del equipo:</strong><br>{esc(team_names_str)}</p>
            <p><strong>Responsabilidad funcional:</strong><br>Equipo técnico de la iniciativa ({esc(manifest['country']['name'])}) · Coordinación regional del Clúster Urbano.</p>
          </div>
          <div>
            <p><strong>Próximo entregable previsto:</strong><br>Capas de salida del PMV en <code>geovisor/capas/</code> y validación de criterios de aceptación.</p>
            <p><strong>Última actualización del contenido por el equipo:</strong><br><code>governance.content_updated_at</code>: <strong>{esc(updated_label)}</strong></p>
          </div>
          <div>
            <p><strong>Canal de soporte y atención técnica:</strong><br>Formulario estructurado de bloqueos e incidencias del repositorio con atención de la facilitación del clúster.</p>
            <p><a class="btn btn-teal btn-xs" href="{html.escape(support_url, quote=True)}" target="_blank" rel="noopener noreferrer">Solicitar apoyo técnico ↗</a></p>
          </div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="prose">
        {render_markdown(project_md)}
      </div>
    </section>

    <section class="section">
      <h2>Criterios de aceptación propuestos para el PMV</h2>
      <p>Estos criterios convierten el perfil en resultados verificables durante y después de la jornada; requieren acuerdo del equipo y evidencia para darse por validados.</p>
      {ac_table}
    </section>

    <section class="section">
      <div class="prose">
        {render_markdown(pmv_md)}
      </div>
    </section>

    <section class="section">
      <h2>Fuentes documentales de referencia</h2>
      <p>Documentos e insumos a partir de los cuales se estructuró el perfil inicial de la iniciativa:</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Documento o insumo de origen</th><th>Referencia / disponibilidad</th></tr></thead>
          <tbody>{"".join(src_rows)}</tbody>
        </table>
      </div>
      <details class="card" style="margin-top:1rem;">
        <summary style="cursor:pointer;font-weight:700;color:var(--c-brand-blue);">Ver registro técnico de procedencia por campo (JSON Pointer y códigos internos de auditoría)</summary>
        <div class="table-wrap" style="margin-top:0.85rem;">
          <table>
            <thead><tr><th>Campo (JSON Pointer)</th><th>Estado</th><th>Fuentes asociadas</th><th>Nota metodológica</th></tr></thead>
            <tbody>{"".join(stmt_rows)}</tbody>
          </table>
        </div>
      </details>
    </section>

    {render_project_institutions_band(ctx, branding, manifest, colaborar_href=colaborar_logos_href)}
    """

    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="Ficha del proyecto",
        active_nav="proyecto",
        hero_html=hero,
        body_html=body,
    )


def build_aplicacion_page(
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    layers_cfg: dict[str, Any],
    branding: dict[str, Any],
) -> str:
    pid = manifest["id"]
    mv = layers_cfg.get("map_view", {})
    grouped: dict[str, list[dict[str, Any]]] = {}
    for lyr in layers_cfg.get("layers", []):
        grp = lyr.get("group", "Capas del proyecto")
        grouped.setdefault(grp, []).append(lyr)

    groups_html: list[str] = []
    for grp_name, items in grouped.items():
        items_html: list[str] = []
        for lyr in items:
            lid = lyr["id"]
            is_ready = bool(lyr.get("source_path")) and lyr.get("status") in ("publicado", "en_revision")
            vis_default = not (isinstance(lyr.get("style"), dict) and lyr["style"].get("visible_by_default") is False)
            disabled_attr = "" if is_ready else " disabled"
            checked_attr = " checked" if (is_ready and vis_default) else ""
            hint_html = (
                f'<div class="layer-item-meta">Ruta esperada para activar: <code>{esc(lyr.get("expected_file_hint"))}</code></div>'
                if not is_ready and lyr.get("expected_file_hint")
                else ""
            )
            caveat_html = (
                f'<div class="layer-item-caveat">{esc(lyr.get("caveat"))}</div>'
                if lyr.get("caveat")
                else ""
            )
            fc_spec = str((lyr.get("style") or {}).get("fill_color") or "")
            scheme_selector_html = ""
            if fc_spec == "auto_gee_malla_250m":
                scheme_selector_html = f"""
                <div style="margin-top:0.45rem;padding:0.45rem 0.55rem;background:#F8FAFC;border:1px solid var(--c-border);border-radius:6px;">
                  <label for="sch-{esc(lid)}" style="display:block;font-size:0.74rem;font-weight:700;color:var(--c-brand-blue);margin-bottom:0.25rem;">🎨 Opciones de visualización Malla GEE 250 m (24,292 celdas):</label>
                  <select id="sch-{esc(lid)}" data-layer-scheme="{esc(lid)}" style="width:100%;font-size:0.75rem;padding:0.25rem 0.35rem;border:1px solid var(--c-border);border-radius:4px;margin-bottom:0.35rem;">
                    <option value="homologated">Opción 1 · Escala Homologada de Valor del Suelo (USD/m² · VAL_EST_M2)</option>
                    <option value="quantiles">Opción 2 · Quintiles Metropolitanos 250 m (P20, P40, P60, P80)</option>
                    <option value="median">Opción 3 · Mediana Intra-Celda a 20 m (VAL_MED_M2)</option>
                    <option value="tipologia">Opción 4 · Régimen Morfológico Territorial (Consolidado / Periurbano / Rural)</option>
                    <option value="edificacion">Opción 5 · Fracción Construida a 10 m (PCT_EDIF %)</option>
                    <option value="incertidumbre">Opción 6 · Heterogeneidad Intra-Celda (DE VAL_STD_M2)</option>
                  </select>
                  <div class="gv-scheme-pills" data-pill-layer="{esc(lid)}">
                    <button type="button" class="gv-scheme-pill is-active" data-scheme-val="homologated" title="Escala Homologada USD/m²">Homologada (USD/m²)</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="quantiles" title="5 Quintiles Metropolitanos">Quintiles</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="median" title="Mediana Intra-Celda">Mediana</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="tipologia" title="Régimen Morfológico Territorial">Tipología Urbana</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="edificacion" title="Porcentaje Construido 10 m">% Edificado</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="incertidumbre" title="Desviación Estándar Intra-Celda">Dispersión (DE)</button>
                  </div>
                  <div data-layer-swatches="{esc(lid)}" style="display:flex;flex-wrap:wrap;gap:0.25rem;margin-top:0.35rem;"></div>
                </div>
                """
            elif fc_spec == "auto_gee_upd_425":
                scheme_selector_html = f"""
                <div style="margin-top:0.45rem;padding:0.45rem 0.55rem;background:#F8FAFC;border:1px solid var(--c-border);border-radius:6px;">
                  <label for="sch-{esc(lid)}" style="display:block;font-size:0.74rem;font-weight:700;color:var(--c-brand-blue);margin-bottom:0.25rem;">🎨 Opciones de visualización 425 UPDs Completas (0 vacíos):</label>
                  <select id="sch-{esc(lid)}" data-layer-scheme="{esc(lid)}" style="width:100%;font-size:0.75rem;padding:0.25rem 0.35rem;border:1px solid var(--c-border);border-radius:4px;margin-bottom:0.35rem;">
                    <option value="homologated">Opción 1 · Valor Integrado 2025 sin Vacíos (VAL_FIN_M2)</option>
                    <option value="origen">Opción 2 · Cobertura Observada (281) vs. Imputada por GEE (144)</option>
                    <option value="modelo_puro">Opción 3 · Predicción Satelital Pura GEE (VAL_MOD_M2)</option>
                    <option value="quantiles">Opción 4 · Quintiles de las 425 UPDs (P20, P40, P60, P80)</option>
                  </select>
                  <div class="gv-scheme-pills" data-pill-layer="{esc(lid)}">
                    <button type="button" class="gv-scheme-pill is-active" data-scheme-val="homologated" title="Valor Integrado 2025 USD/m²">Valor Integrado</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="origen" title="Observado vs Imputado GEE">Origen (Obs/Imp)</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="modelo_puro" title="Predicción Satelital Pura GEE">Modelo Puro GEE</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="quantiles" title="Quintiles 425 UPDs">Quintiles</button>
                  </div>
                  <div data-layer-swatches="{esc(lid)}" style="display:flex;flex-wrap:wrap;gap:0.25rem;margin-top:0.35rem;"></div>
                </div>
                """
            elif fc_spec == "auto_gee_pixel_20m":
                scheme_selector_html = f"""
                <div style="margin-top:0.45rem;padding:0.45rem 0.55rem;background:#F8FAFC;border:1px solid var(--c-border);border-radius:6px;">
                  <label for="sch-{esc(lid)}" style="display:block;font-size:0.74rem;font-weight:700;color:var(--c-brand-blue);margin-bottom:0.25rem;">🎨 Modalidad de superficie raster a 20 m (3.85 M píxeles):</label>
                  <select id="sch-{esc(lid)}" data-layer-scheme="{esc(lid)}" style="width:100%;font-size:0.75rem;padding:0.25rem 0.35rem;border:1px solid var(--c-border);border-radius:4px;margin-bottom:0.35rem;">
                    <option value="urbano_desarrollable">Opción 1 · Suelo Urbano y Desarrollable (Pendiente &lt; 35° sin agua)</option>
                    <option value="potencial_continuo">Opción 2 · Potencial Continuo Completo (Todo el perímetro AMSS)</option>
                  </select>
                  <div class="gv-scheme-pills" data-pill-layer="{esc(lid)}">
                    <button type="button" class="gv-scheme-pill is-active" data-scheme-val="urbano_desarrollable" title="Suelo Urbano y Desarrollable a 20 m">Urbano / Desarrollable</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="potencial_continuo" title="Potencial Continuo Completo a 20 m">Potencial Continuo</button>
                  </div>
                  <div data-layer-swatches="{esc(lid)}" style="display:flex;flex-wrap:wrap;gap:0.25rem;margin-top:0.35rem;"></div>
                </div>
                """
            elif fc_spec == "auto_lisa_2025":
                scheme_selector_html = f"""
                <div style="margin-top:0.45rem;padding:0.45rem 0.55rem;background:#F8FAFC;border:1px solid var(--c-border);border-radius:6px;">
                  <label for="sch-{esc(lid)}" style="display:block;font-size:0.74rem;font-weight:700;color:var(--c-brand-blue);margin-bottom:0.25rem;">🎨 Opciones de visualización (promedio_2025 / LISA):</label>
                  <select id="sch-{esc(lid)}" data-layer-scheme="{esc(lid)}" style="width:100%;font-size:0.75rem;padding:0.25rem 0.35rem;border:1px solid var(--c-border);border-radius:4px;margin-bottom:0.35rem;">
                    <option value="homologated">Opción 1 · Escala Homologada Comparable (5 rangos USD: ≤$50 a &gt;$300)</option>
                    <option value="quantiles">Opción 2 · Quintiles de Mercado 2025 (P20, P40, P60, P80 · 53 UPD/clase)</option>
                    <option value="jenks">Opción 3 · Rupturas Naturales (Jenks 5 clases)</option>
                    <option value="lisa_quadrants">Opción 4 · Cuadrantes LISA de Moran (Alto-Alto, Bajo-Bajo, etc.)</option>
                    <option value="lisa_sig">Opción 5 · Clusters Significativos LISA (p_perm_loc ≤ 0.05)</option>
                  </select>
                  <div class="gv-scheme-pills" data-pill-layer="{esc(lid)}">
                    <button type="button" class="gv-scheme-pill is-active" data-scheme-val="homologated" title="Escala Homologada (≤$50 a >$300 USD)">Homologada (USD)</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="quantiles" title="5 Quintiles de igual frecuencia">Quintiles</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="jenks" title="Rupturas Naturales Jenks">Jenks</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="lisa_quadrants" title="Cuadrantes Espaciales LISA">Cuadrantes LISA</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="lisa_sig" title="Clusters Significativos p ≤ 0.05">Clusters p≤0.05</button>
                  </div>
                  <div data-layer-swatches="{esc(lid)}" style="display:flex;flex-wrap:wrap;gap:0.25rem;margin-top:0.35rem;"></div>
                </div>
                """
            elif fc_spec == "auto_upd_2020_2026":
                scheme_selector_html = f"""
                <div style="margin-top:0.45rem;padding:0.45rem 0.55rem;background:#F8FAFC;border:1px solid var(--c-border);border-radius:6px;">
                  <label for="sch-{esc(lid)}" style="display:block;font-size:0.74rem;font-weight:700;color:var(--c-brand-blue);margin-bottom:0.25rem;">🎨 Opciones de visualización 2020–2026 (P2_PROM / P2_MED):</label>
                  <select id="sch-{esc(lid)}" data-layer-scheme="{esc(lid)}" style="width:100%;font-size:0.75rem;padding:0.25rem 0.35rem;border:1px solid var(--c-border);border-radius:4px;margin-bottom:0.35rem;">
                    <option value="homologated">Opción 1 · Escala Homologada Comparable (5 rangos USD: ≤$50 a &gt;$300)</option>
                    <option value="quantiles">Opción 2 · Quintiles 2020–2026 (P20, P40, P60, P80 · P2_PROM)</option>
                    <option value="jenks">Opción 3 · Rupturas Naturales (Jenks 5 clases · P2_PROM)</option>
                    <option value="median">Opción 4 · Mediana Robusta 2020–2026 (P2_MED)</option>
                  </select>
                  <div class="gv-scheme-pills" data-pill-layer="{esc(lid)}">
                    <button type="button" class="gv-scheme-pill is-active" data-scheme-val="homologated" title="Escala Homologada (≤$50 a >$300 USD)">Homologada (USD)</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="quantiles" title="5 Quintiles 2020–2026">Quintiles</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="jenks" title="Rupturas Naturales Jenks">Jenks</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="median" title="Mediana Robusta P2_MED">Mediana Robusta</button>
                  </div>
                  <div data-layer-swatches="{esc(lid)}" style="display:flex;flex-wrap:wrap;gap:0.25rem;margin-top:0.35rem;"></div>
                </div>
                """
            elif fc_spec == "auto_upd_2007_2019":
                scheme_selector_html = f"""
                <div style="margin-top:0.45rem;padding:0.45rem 0.55rem;background:#F8FAFC;border:1px solid var(--c-border);border-radius:6px;">
                  <label for="sch-{esc(lid)}" style="display:block;font-size:0.74rem;font-weight:700;color:var(--c-brand-blue);margin-bottom:0.25rem;">🎨 Opciones de visualización 2007–2019 (P1_PROM / P1_MED):</label>
                  <select id="sch-{esc(lid)}" data-layer-scheme="{esc(lid)}" style="width:100%;font-size:0.75rem;padding:0.25rem 0.35rem;border:1px solid var(--c-border);border-radius:4px;margin-bottom:0.35rem;">
                    <option value="homologated">Opción 1 · Escala Homologada Comparable (5 rangos USD: ≤$50 a &gt;$300)</option>
                    <option value="quantiles">Opción 2 · Quintiles 2007–2019 (P20, P40, P60, P80 · P1_PROM)</option>
                    <option value="jenks">Opción 3 · Rupturas Naturales (Jenks con control de outliers)</option>
                    <option value="median">Opción 4 · Mediana Robusta 2007–2019 (P1_MED · sin sesgo atípico)</option>
                  </select>
                  <div class="gv-scheme-pills" data-pill-layer="{esc(lid)}">
                    <button type="button" class="gv-scheme-pill is-active" data-scheme-val="homologated" title="Escala Homologada (≤$50 a >$300 USD)">Homologada (USD)</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="quantiles" title="5 Quintiles 2007–2019">Quintiles</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="jenks" title="Rupturas Naturales Jenks con control de outliers">Jenks (Outliers)</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="median" title="Mediana Robusta P1_MED">Mediana Robusta</button>
                  </div>
                  <div data-layer-swatches="{esc(lid)}" style="display:flex;flex-wrap:wrap;gap:0.25rem;margin-top:0.35rem;"></div>
                </div>
                """
            elif fc_spec == "auto_upd_tendencia":
                scheme_selector_html = f"""
                <div style="margin-top:0.45rem;padding:0.45rem 0.55rem;background:#F8FAFC;border:1px solid var(--c-border);border-radius:6px;">
                  <label for="sch-{esc(lid)}" style="display:block;font-size:0.74rem;font-weight:700;color:var(--c-brand-blue);margin-bottom:0.25rem;">🎨 Opciones de visualización de cambio (TENDENCIA / PCT_VAR):</label>
                  <select id="sch-{esc(lid)}" data-layer-scheme="{esc(lid)}" style="width:100%;font-size:0.75rem;padding:0.25rem 0.35rem;border:1px solid var(--c-border);border-radius:4px;margin-bottom:0.35rem;">
                    <option value="diverging">Opción 1 · Categorías de Tendencia (Aumento / Disminución / Cobertura)</option>
                    <option value="pct_var">Opción 2 · Variación Porcentual Divergente (PCT_VAR %)</option>
                  </select>
                  <div class="gv-scheme-pills" data-pill-layer="{esc(lid)}">
                    <button type="button" class="gv-scheme-pill is-active" data-scheme-val="diverging" title="Categorías de Tendencia: Aumento / Disminución / Cobertura">Categorías (TENDENCIA)</button>
                    <button type="button" class="gv-scheme-pill" data-scheme-val="pct_var" title="Tasa de Variación Porcentual Divergente (PCT_VAR %)">Variación % (PCT_VAR)</button>
                  </div>
                  <div data-layer-swatches="{esc(lid)}" style="display:flex;flex-wrap:wrap;gap:0.25rem;margin-top:0.35rem;"></div>
                </div>
                """
            items_html.append(
                f"""
                <div class="layer-item">
                  <div class="layer-item-head">
                    <label class="layer-item-title">
                      <input type="checkbox" data-layer-toggle="{esc(lid)}"{checked_attr}{disabled_attr}>
                      <span>{esc(lyr['title'])}</span>
                    </label>
                    {badge_html(lyr.get('status', 'en_preparacion'))}
                  </div>
                  <div class="layer-item-meta">Formato: <code>{esc(lyr.get('format'))}</code> · Escala/resolución: {esc(lyr.get('resolution'), 'Por documentar')}</div>
                  {hint_html}
                  <div class="layer-item-meta" style="display:flex;align-items:center;gap:0.5rem;margin-top:0.35rem;">
                    <label for="op-{esc(lid)}">Opacidad:</label>
                    <input id="op-{esc(lid)}" type="range" min="0.1" max="1" step="0.05" value="0.75" data-layer-opacity="{esc(lid)}"{disabled_attr}>
                  </div>
                  {scheme_selector_html}
                  {caveat_html}
                </div>
                """
            )
        groups_html.append(f'<div class="layer-group-title">{esc(grp_name)}</div>' + "".join(items_html))

    controls_li = "".join(f"<li>{esc(c)}</li>" for c in layers_cfg.get("planned_controls", []))
    ext_refs_html = ""
    if layers_cfg.get("external_references"):
        ext_cards = []
        for ref in layers_cfg["external_references"]:
            badge_k = "declarado" if ref.get("kind") == "referencia_declarada" else "propuesta"
            ext_cards.append(
                f"""
                <div class="card">
                  <div>{badge_html(badge_k)}</div>
                  <h3>{esc(ref['label'])}</h3>
                  <p>{esc(ref.get('note', ''))}</p>
                  <div class="card-footer">
                    <a class="btn btn-outline" href="{html.escape(ref['url'], quote=True)}" target="_blank" rel="noopener noreferrer">Abrir enlace externo ↗</a>
                  </div>
                </div>
                """
            )
        ext_refs_html = f"""
        <section class="section">
          <h2>Referencias técnicas y demostradores externos documentados</h2>
          <div class="grid-2">{"".join(ext_cards)}</div>
        </section>
        """

    effective_repo_slug = (
        ctx.github_repository
        if ctx.github_repository
        else (ctx.canonical_repository if ctx.effective_mode == "canonical" else None)
    )
    runtime_cfg = dict(layers_cfg)
    runtime_cfg["site_base_url"] = ctx.site_url("")
    runtime_cfg["repository_slug"] = effective_repo_slug
    runtime_cfg["canonical_repository_slug"] = ctx.canonical_repository
    runtime_cfg["effective_mode"] = ctx.effective_mode
    runtime_cfg["repository_branch"] = "main"
    safe_json_cfg = json.dumps(runtime_cfg, ensure_ascii=False).replace("</", "<\\/")

    repo_capas_gh_btn = ""
    target_gh_slug = effective_repo_slug or ctx.canonical_repository
    if target_gh_slug:
        gh_capas_url = f"https://github.com/{target_gh_slug}/tree/main/geovisor/capas"
        repo_capas_gh_btn = (
            f'<a class="btn btn-outline btn-xs" href="{html.escape(gh_capas_url, quote=True)}" '
            f'target="_blank" rel="noopener noreferrer">Abrir geovisor/capas/ en GitHub ↗</a>'
        )

    modelo_suelo_href = html.escape(ctx.site_url("modelo-suelo/"), quote=True)
    docx_dl_href = html.escape(ctx.site_url("assets/descargas/Metodologia_Modelo_Valor_Suelo_AMSS_GEE.docx"), quote=True)
    gee_js_dl_href = html.escape(ctx.site_url("assets/descargas/gee_modelo_valor_suelo_amss.js"), quote=True)

    hero = f"""
    <section class="hero hero-compact">
      <div class="container">
        <div class="hero-eyebrow" style="margin-bottom:0.45rem;">
          <span class="badge badge-lime">Geovisor basado en GeoLibre</span>
          <span class="badge badge-country">{esc(pid)} · {esc(manifest['territory']['label'])}</span>
          {badge_html(manifest['status']['demo'], 'Estado Demo')}
        </div>
        <h1>Geovisor del proyecto y modelo continuo de valor del suelo (GEE)</h1>
        <p class="hero-lead">Explora la malla continua de 250 m (24,292 celdas), la superficie a nivel de píxel (20 m) y las 425 UPDs completas generadas con Google Satellite Embeddings V1 + EO, junto con los registros históricos de OPAMSS y oferta inmobiliaria 2025.</p>
        <div class="hero-actions" style="margin-top:0.65rem;">
          <a class="btn btn-primary" href="{modelo_suelo_href}">📊 Metodología, Primeros Resultados y Script GEE →</a>
          <a class="btn btn-teal" href="{docx_dl_href}" download="Metodologia_Modelo_Valor_Suelo_AMSS_GEE.docx">📥 Documento Metodológico (.docx)</a>
          <a class="btn btn-outline-light" href="{gee_js_dl_href}" download="gee_modelo_valor_suelo_amss.js">📜 Descargar Script GEE (.js)</a>
        </div>
      </div>
    </section>
    """

    geolibre_json_href = html.escape(ctx.site_url("geovisor/proyecto.geolibre.json"), quote=True)
    geolibre_full_url = ctx.full_url("geovisor/proyecto.geolibre.json")
    studio_open_href = (
        f"https://web.geolibre.app/?url={urllib.parse.quote(geolibre_full_url, safe='')}"
        if geolibre_full_url.startswith("https://")
        else "https://web.geolibre.app/"
    )
    colaborar_logos_href = ctx.site_url("colaborar/") + "#anadir-actualizar-logos"

    body = f"""
    <div class="callout" style="margin-top:0;margin-bottom:1rem;padding:0.75rem 1rem;">
      <strong>Nota de integridad cartográfica ({esc(mv.get('scale_label', 'Escala del perfil'))})</strong>
      <span>{esc(mv.get('reference_note'))} Los límites administrativos procedentes de fuentes abiertas (OpenStreetMap ODbL) se muestran con carácter referencial hasta su homologación institucional.</span>
    </div>

    <section class="section" id="geovisor-app">
      <div class="geovisor-shell">
        <aside class="geovisor-sidebar" aria-label="Controles y capas del geovisor">
          <div class="geovisor-tabs" role="tablist">
            <button type="button" class="geovisor-tab is-active" data-gv-tab="layers">Capas ({len(layers_cfg.get('layers', []))})</button>
            <button type="button" class="geovisor-tab" data-gv-tab="repo-folder">Carpeta repo</button>
            <button type="button" class="geovisor-tab" data-gv-tab="local">Archivo local</button>
            <button type="button" class="geovisor-tab" data-gv-tab="embed">GeoLibre</button>
          </div>

          <div class="geovisor-panel is-active" data-gv-panel="layers">
            <div style="margin-bottom:0.65rem;padding:0.6rem 0.65rem;background:linear-gradient(135deg,#0F172A 0%,#1E3A8A 100%);color:#FFFFFF;border-radius:8px;border:1px solid #334155;">
              <div style="font-size:0.73rem;font-weight:700;color:#FDE047;margin-bottom:0.22rem;">🛰️ NUEVO · MODELO CONTINUO GEE (AMSS)</div>
              <p style="font-size:0.72rem;color:#E2E8F0;margin:0 0 0.45rem 0;line-height:1.35;">
                Consulta la memoria metodológica, el análisis de las 71 bandas (Google Embeddings + EO), cómo afinar el modelo y el script completo de GEE:
              </p>
              <a class="btn btn-primary btn-xs" style="width:100%;justify-content:center;font-weight:700;" href="{modelo_suelo_href}">
                📊 Ver Metodología, Resultados y Script GEE →
              </a>
            </div>

            <div class="gv-scenario-selector" style="margin-bottom:0.75rem;padding:0.6rem;background:#EEF2FF;border:1px solid #C7D2FE;border-radius:8px;">
              <div style="font-size:0.76rem;font-weight:700;color:#1E3A8A;margin-bottom:0.35rem;display:flex;align-items:center;justify-content:space-between;">
                <span>🎯 Escenarios Analíticos de Valor del Suelo</span>
                <span class="badge badge-primary" style="font-size:0.65rem;">1-Clic</span>
              </div>
              <p style="font-size:0.72rem;color:#334155;margin:0 0 0.45rem 0;line-height:1.35;">
                Alterna en un clic entre las predicciones satelitales continuas en GEE y los registros base observados:
              </p>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.35rem;">
                <button type="button" class="btn btn-primary btn-xs gv-scenario-btn is-active" data-gv-scenario="gee-malla-250m" title="Malla Continua GEE de 250 m (24,292 celdas · USD/m²)">
                  🛰️ Malla GEE 250m (USD/m²)
                </button>
                <button type="button" class="btn btn-outline btn-xs gv-scenario-btn" data-gv-scenario="gee-malla-tipologia" title="Régimen Morfológico Territorial GEE (Consolidado / Periurbano / Rural)">
                  🏙️ Tipología Urbana GEE
                </button>
                <button type="button" class="btn btn-outline btn-xs gv-scenario-btn" data-gv-scenario="gee-upd-425" title="425 UPDs Completas (281 observadas + 144 imputadas por GEE)">
                  🧩 425 UPDs (0 Vacíos)
                </button>
                <button type="button" class="btn btn-outline btn-xs gv-scenario-btn" data-gv-scenario="gee-pixel-20m" title="Superficie Raster Continua a Nivel de Píxel 20 m (3.85 M píxeles)">
                  🔬 Superficie Píxel 20m
                </button>
                <button type="button" class="btn btn-outline btn-xs gv-scenario-btn" data-gv-scenario="mercado-2025-homol" title="Web Scraping 2025 en escala comparable (≤$50 a >$300 USD)">
                  🛒 Mercado 2025 (Homol.)
                </button>
                <button type="button" class="btn btn-outline btn-xs gv-scenario-btn" data-gv-scenario="mercado-2025-lisa" title="Clusters Espaciales LISA Moran (p ≤ 0.05)">
                  🔥 Clusters LISA 2025
                </button>
                <button type="button" class="btn btn-outline btn-xs gv-scenario-btn" data-gv-scenario="opamss-p2-homol" title="Permisos OPAMSS 2020-2026 en escala comparable">
                  📑 OPAMSS 2020–2026
                </button>
                <button type="button" class="btn btn-outline btn-xs gv-scenario-btn" data-gv-scenario="opamss-p1-homol" title="Permisos OPAMSS 2007-2019 en escala comparable">
                  🏛️ OPAMSS 2007–2019
                </button>
                <button type="button" class="btn btn-outline btn-xs gv-scenario-btn" data-gv-scenario="opamss-tendencia" title="Tendencia de cambio entre periodos de permisos OPAMSS" style="grid-column: span 2;">
                  📈 Dinámica / Tendencia OPAMSS (2007–19 vs 2020–26)
                </button>
              </div>
            </div>
            <div class="filter-field" style="margin-bottom:0.5rem;">
              <label for="gv-basemap-select">Catálogo de Mapas Base Copernicus y Derivados (23 capas abiertas)</label>
              <select id="gv-basemap-select">
                <optgroup label="1. Modelo Digital de Elevación Oficial Copernicus DEM (GLO-30 · 30 m)">
                  <option value="copernicus-dem-glo30">Copernicus DEM GLO-30 (30 m · Elevación Hipsométrica + Sombreado)</option>
                  <option value="copernicus-dem-hillshade">Copernicus DEM GLO-30 (30 m · Sombreado de Relieve / Hillshade)</option>
                  <option value="copernicus-dem-viridis">Copernicus DEM GLO-30 (30 m · Hipsometría Viridis + Curvas de Nivel)</option>
                </optgroup>
                <optgroup label="2. Cobertura Terrestre y Mancha Urbana 10 m (Sentinel-1 + Sentinel-2)">
                  <option value="esa-worldcover-2021">ESA WorldCover 10 m (2021 v200 · Mancha Urbana y Cobertura)</option>
                  <option value="esa-worldcover-2020">ESA WorldCover 10 m (2020 v100 · Mancha Urbana y Cobertura)</option>
                  <option value="s2-lulc-2023">Uso y Cobertura del Suelo Sentinel-2 10 m (Año 2023 · 9 clases)</option>
                  <option value="s2-lulc-2022">Uso y Cobertura del Suelo Sentinel-2 10 m (Año 2022 · 9 clases)</option>
                  <option value="s2-lulc-2021">Uso y Cobertura del Suelo Sentinel-2 10 m (Año 2021 · 9 clases)</option>
                  <option value="s2-lulc-2020">Uso y Cobertura del Suelo Sentinel-2 10 m (Año 2020 · 9 clases)</option>
                  <option value="s2-lulc-2019">Uso y Cobertura del Suelo Sentinel-2 10 m (Año 2019 · 9 clases)</option>
                  <option value="s2-lulc-2018">Uso y Cobertura del Suelo Sentinel-2 10 m (Año 2018 · 9 clases)</option>
                  <option value="s2-lulc-2017">Uso y Cobertura del Suelo Sentinel-2 10 m (Año 2017 · Línea base)</option>
                </optgroup>
                <optgroup label="3. Índices Espectrales y Bandas Copernicus Sentinel-2 L2A (10 m / 20 m)">
                  <option value="s2-l2a-ndvi">Sentinel-2 L2A · Índice de Vegetación Urbana (NDVI · 10 m)</option>
                  <option value="s2-l2a-ndbi">Sentinel-2 L2A · Índice de Edificación / Área Construida (NDBI · 20 m)</option>
                  <option value="s2-l2a-ndwi">Sentinel-2 L2A · Índice de Humedad Superficial (NDWI · 20 m)</option>
                  <option value="s2-l2a-falsecolor">Sentinel-2 L2A · Falso Color Infrarrojo (B08-B04-B03 · 10 m)</option>
                  <option value="s2-l2a-swir">Sentinel-2 L2A · SWIR Urbano (B12-B8A-B04 · 20 m)</option>
                </optgroup>
                <optgroup label="4. Radar de Apertura Sintética Copernicus Sentinel-1 SAR RTC (10 m · Sin Nubes)">
                  <option value="s1-rtc-falsecolor">Copernicus Sentinel-1 SAR RTC (10 m · Compuesto Urbano VV+VH)</option>
                  <option value="s1-rtc-vv">Copernicus Sentinel-1 SAR RTC (10 m · Polarización VV Escala de Grises)</option>
                </optgroup>
                <optgroup label="5. Agua Superficial e Inundaciones (JRC Comisión Europea / Copernicus)">
                  <option value="jrc-gsw-occurrence">JRC Agua Superficial · Ocurrencia Histórica e Inundación (1984–2021)</option>
                  <option value="jrc-gsw-extent">JRC Agua Superficial · Extensión Máxima de Agua / Inundación</option>
                </optgroup>
                <optgroup label="6. Mosaicos Anuales Ópticos Copernicus Sentinel-2 Cloudless (2018–2024)">
                  <option value="sentinel2-2024">Copernicus Sentinel-2 Cloudless (Mosaico 2024 · EOX)</option>
                  <option value="sentinel2-2023">Copernicus Sentinel-2 Cloudless (Mosaico 2023 · EOX)</option>
                  <option value="sentinel2-2022">Copernicus Sentinel-2 Cloudless (Mosaico 2022 · EOX)</option>
                  <option value="sentinel2-2021">Copernicus Sentinel-2 Cloudless (Mosaico 2021 · EOX)</option>
                  <option value="sentinel2-2020">Copernicus Sentinel-2 Cloudless (Mosaico 2020 · EOX)</option>
                  <option value="sentinel2-2019">Copernicus Sentinel-2 Cloudless (Mosaico 2019 · EOX)</option>
                  <option value="sentinel2-2018">Copernicus Sentinel-2 Cloudless (Mosaico 2018 · EOX)</option>
                </optgroup>
                <optgroup label="7. Mapas Base Vectoriales y Referencia Cartográfica">
                  <option value="carto-positron" selected>Mapa Claro Vectorial (OpenFreeMap)</option>
                  <option value="osm-standard">OpenStreetMap Estándar</option>
                  <option value="carto-dark">Modo Oscuro Vectorial (OpenFreeMap)</option>
                  <option value="esri-imagery">Imagen Satelital de Alta Resolución (Esri)</option>
                </optgroup>
              </select>
            </div>

            <div style="margin-bottom:0.75rem;background:#F3F6FD;border:1px solid var(--c-border);border-radius:6px;padding:0.5rem 0.6rem;">
              <div style="font-size:0.74rem;font-weight:700;color:var(--c-brand-blue);margin-bottom:0.38rem;">🛰️ Acceso directo por familia Copernicus (Sin API Key):</div>
              <div style="display:flex;flex-wrap:wrap;gap:0.3rem;">
                <button type="button" class="btn btn-outline btn-xs" data-basemap-quick="copernicus-dem-glo30" title="Copernicus DEM GLO-30 (30 m · Elevación Hipsométrica + Sombreado)">⛰️ DEM GLO-30</button>
                <button type="button" class="btn btn-outline btn-xs" data-basemap-quick="copernicus-dem-hillshade" title="Copernicus DEM GLO-30 (30 m · Sombreado de Relieve / Hillshade)">⛰️ Hillshade</button>
                <button type="button" class="btn btn-outline btn-xs" data-basemap-quick="esa-worldcover-2021" title="ESA WorldCover 10 m (Mancha urbana y cobertura derivada de Sentinel-1 y Sentinel-2)">🏙️ WorldCover 10m</button>
                <button type="button" class="btn btn-outline btn-xs" data-basemap-quick="s2-lulc-2023" title="Uso y Cobertura del Suelo Sentinel-2 10 m (2023)">🏙️ LULC 2023</button>
                <button type="button" class="btn btn-outline btn-xs" data-basemap-quick="s2-l2a-ndvi" title="Sentinel-2 L2A Índice de Vegetación Urbana (NDVI · 10 m)">🌿 NDVI</button>
                <button type="button" class="btn btn-outline btn-xs" data-basemap-quick="s2-l2a-ndbi" title="Sentinel-2 L2A Índice de Edificación / Área Construida (NDBI · 20 m)">🏗️ NDBI</button>
                <button type="button" class="btn btn-outline btn-xs" data-basemap-quick="s1-rtc-falsecolor" title="Radar de Apertura Sintética Copernicus Sentinel-1 SAR RTC (10 m · VV+VH)">📡 Radar S1</button>
                <button type="button" class="btn btn-outline btn-xs" data-basemap-quick="jrc-gsw-occurrence" title="JRC Agua Superficial e Inundación (Comisión Europea)">🌊 JRC Agua</button>
                <button type="button" class="btn btn-outline btn-xs" data-basemap-quick="sentinel2-2024" title="Mosaico anual abierto Copernicus Sentinel-2 Cloudless 2024">🛰️ S2 2024</button>
                <button type="button" class="btn btn-outline btn-xs" data-basemap-quick="sentinel2-2018" title="Mosaico anual abierto Copernicus Sentinel-2 Cloudless 2018">🛰️ S2 2018</button>
                <button type="button" class="btn btn-teal btn-xs" data-basemap-quick="carto-positron" title="Mapa Claro Vectorial de Referencia">🗺️ Vectorial</button>
              </div>
              <div id="gv-basemap-legend" style="margin-top:0.42rem;padding-top:0.35rem;border-top:1px dashed var(--c-border);font-size:0.73rem;color:var(--c-text-muted);line-height:1.35;">
                🗺️ Mapa base vectorial de referencia cartográfica (OpenFreeMap / OpenStreetMap)
              </div>
            </div>

            <div style="margin-bottom:0.65rem;padding:0.45rem 0.6rem;background:#FFFDF5;border:1px solid #E5D48A;border-radius:6px;">
              <label style="display:flex;align-items:center;gap:0.45rem;font-size:0.8rem;font-weight:700;color:var(--c-brand-blue);">
                <input type="checkbox" id="gv-toggle-mask" checked>
                <span>Enmascarar fuera del límite de zona de estudio</span>
              </label>
              <div style="display:flex;align-items:center;gap:0.45rem;margin-top:0.3rem;font-size:0.74rem;color:var(--c-text-muted);">
                <span>Opacidad máscara:</span>
                <input type="range" id="gv-mask-opacity" min="0" max="1" step="0.05" value="0.88" style="flex:1;" aria-label="Opacidad de máscara exterior">
              </div>
            </div>

            <label style="display:flex;align-items:center;gap:0.45rem;font-size:0.83rem;font-weight:600;margin-bottom:0.6rem;">
              <input type="checkbox" id="gv-toggle-ref-marker" checked>
              <span>Mostrar marcador de centroide referencial</span>
            </label>
            {"".join(groups_html)}
          </div>

          <div class="geovisor-panel" data-gv-panel="repo-folder">
            <h3 style="margin-top:0;font-size:1rem;color:var(--c-brand-blue);">Cargar capa desde carpeta del repositorio</h3>
            <p style="font-size:0.82rem;">Lee los archivos publicados en <code>geovisor/capas/</code> de <strong>esta vista</strong> (en una copia personal o fork lee exclusivamente tu repositorio para no mezclar capas con el repositorio oficial).</p>
            <div style="display:flex;flex-wrap:wrap;gap:0.45rem;margin-bottom:0.75rem;">
              <button type="button" id="gv-refresh-repo-folder" class="btn btn-teal btn-xs">Leer / Refrescar carpeta</button>
              {repo_capas_gh_btn}
            </div>
            <p id="gv-repo-folder-status" style="font-size:0.8rem;color:var(--c-brand-blue);font-weight:600;margin-bottom:0.6rem;">Consultando carpeta geovisor/capas/...</p>
            <div id="gv-repo-folder-list"></div>
          </div>

          <div class="geovisor-panel" data-gv-panel="local">
            <h3 style="margin-top:0;font-size:1rem;color:var(--c-brand-blue);">Inspeccionar archivo desde tu equipo (Archivo local)</h3>
            <p style="font-size:0.84rem;">Arrastra o selecciona un archivo <code>.geojson</code> o <code>.kml</code> desde tu computadora para verificar su geometría y atributos antes de subirlo a <code>geovisor/capas/</code>.</p>
            <div class="dropzone" id="gv-dropzone" tabindex="0" role="button" aria-label="Seleccionar archivo GeoJSON o KML local">
              <strong>Haz clic o arrastra aquí un .geojson / .kml</strong>
              <div style="font-size:0.78rem;margin-top:0.25rem;">WGS84 (EPSG:4326) recomendado</div>
            </div>
            <input type="file" id="gv-local-geojson-input" accept=".geojson,.json,.kml,application/geo+json,application/json" class="hidden">
            <p id="gv-local-status" style="font-size:0.82rem;color:var(--c-brand-blue);font-weight:600;">Ningún archivo temporal cargado.</p>
            <button type="button" id="gv-clear-local" class="btn btn-outline btn-xs hidden">Quitar capa temporal</button>
          </div>

          <div class="geovisor-panel" data-gv-panel="embed">
            <h3 style="margin-top:0;font-size:1rem;color:var(--c-brand-blue);">Integración con GeoLibre Studio</h3>
            <p id="geolibre-embed-notice" style="font-size:0.83rem;">Este sitio combina dos piezas complementarias: el <strong>visor integrado (MapLibre GL JS)</strong> para consulta rápida de vectores y el archivo de proyecto <code>geovisor/proyecto.geolibre.json</code> (esquema oficial v0.2.0 con <code>mapView</code>, <code>layers</code> y <code>styles</code>) para abrir la iniciativa completa en <strong>GeoLibre Studio</strong>.</p>
            <div style="display:flex;flex-direction:column;gap:0.55rem;margin-top:0.85rem;">
              <a class="btn btn-primary" href="{html.escape(studio_open_href, quote=True)}" target="_blank" rel="noopener noreferrer">Abrir proyecto en GeoLibre Studio ↗</a>
              <a class="btn btn-teal" href="{geolibre_json_href}" download="proyecto-{esc(pid)}.geolibre.json">Descargar proyecto.geolibre.json</a>
            </div>
          </div>
        </aside>

        <div class="geovisor-stage">
          <div class="geovisor-toolbar">
            <div><strong>{esc(layers_cfg.get('title', manifest['title']))}</strong> · Motor MapLibre / GeoLibre</div>
            <div class="geovisor-toolbar-actions">
              <a id="btn-open-modelo-suelo" class="btn btn-primary btn-xs" style="background:#D97706;border-color:#B45309;color:#FFFFFF;font-weight:700;" href="{modelo_suelo_href}" title="Abrir subpágina con la metodología aplicada, análisis de primeros resultados, mejoras y script de GEE">📊 Metodología, Resultados y Script GEE →</a>
              <button type="button" id="gv-toggle-fullscreen" class="btn btn-teal btn-xs" title="Ver el geovisor en pantalla completa (Esc para salir)">⛶ Pantalla completa</button>
              <button type="button" id="gv-toggle-sidebar" class="btn btn-outline-light btn-xs" title="Ocultar o mostrar el panel lateral de capas">⇄ Panel lateral</button>
              <button type="button" id="gv-open-folder-tab" class="btn btn-outline-light btn-xs">Cargar desde carpeta</button>
              <button type="button" id="gv-reset-view" class="btn btn-outline-light btn-xs">Encuadre inicial</button>
              <a class="btn btn-outline-light btn-xs" href="{docx_dl_href}" download="Metodologia_Modelo_Valor_Suelo_AMSS_GEE.docx" title="Descargar documento Word actualizado con metodología y análisis de resultados">📥 Metodología Word</a>
              <a class="btn btn-outline-light btn-xs" href="{html.escape(ctx.site_url('assets/descargas/atlas_copernicus_zona_estudio.pdf'), quote=True)}" download="Atlas_Copernicus_{esc(pid)}.pdf" title="Descargar Atlas Temático Copernicus con identidad gráfica institucional en PDF">📥 Atlas PDF</a>
              <a class="btn btn-outline-light btn-xs" href="{geolibre_json_href}">JSON GeoLibre</a>
              <a id="btn-open-geolibre-studio" class="btn btn-primary btn-xs" href="{html.escape(studio_open_href, quote=True)}" target="_blank" rel="noopener noreferrer">Abrir en GeoLibre Studio ↗</a>
            </div>
          </div>
          <div id="geovisor-map-canvas" class="geovisor-canvas" role="region" aria-label="Mapa interactivo del proyecto">
            <div id="gv-floating-legend" class="geovisor-map-legend" aria-live="polite">
              <div class="gv-legend-header">
                <span class="gv-legend-title" id="gv-legend-title">🗺️ Leyenda del mapa</span>
                <button type="button" id="gv-legend-toggle" class="gv-legend-toggle-btn" aria-label="Minimizar leyenda" title="Minimizar o expandir leyenda">−</button>
              </div>
              <div id="gv-legend-body" class="gv-legend-body">
                <div style="font-size:0.72rem;color:var(--c-text-muted);">Cargando simbología...</div>
              </div>
            </div>
          </div>
          <iframe id="geolibre-embed-iframe" class="geovisor-iframe" title="Visor GeoLibre embebido" allowfullscreen loading="lazy"></iframe>
          <div class="geovisor-statusbar">
            <span id="gv-coords-readout">Encuadre referencial inicial: Lat {mv.get('center', [0, 0])[1]:.4f} · Lon {mv.get('center', [0, 0])[0]:.4f}</span>
            <span>Ubicación referencial según perfil · Colores analíticos independientes de la marca</span>
          </div>
        </div>
      </div>
      <script id="geovisor-config-data" type="application/json">{safe_json_cfg}</script>
    </section>

    <section class="section">
      <div class="grid-2">
        <div class="card">
          <span class="badge badge-declarado">Comportamiento por tipo de archivo</span>
          <h2>Formatos admitidos en <code>geovisor/capas/</code></h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>Formato</th><th>Dónde se abre</th><th>Pasos necesarios</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td><code>.geojson</code>, <code>.json</code>, <code>.kml</code></td>
                  <td>Visor integrado del sitio (MapLibre) y GeoLibre Studio</td>
                  <td>Pulsar <strong>Cargar en mapa</strong> en la pestaña <em>Carpeta repo</em> (o arrastrar en <em>Archivo local</em>).</td>
                </tr>
                <tr>
                  <td><code>.geolibre.json</code></td>
                  <td>GeoLibre Studio (<code>web.geolibre.app/?url=...</code>)</td>
                  <td>Pulsar <strong>Abrir en GeoLibre Studio</strong> para restaurar encuadre (<code>mapView</code>), capas y estilos.</td>
                </tr>
                <tr>
                  <td><code>.tif</code> / <code>.tiff</code> (COG), <code>.pmtiles</code>, <code>.fgb</code>, <code>.geoparquet</code></td>
                  <td>GeoLibre Studio (<code>web.geolibre.app/?data=...</code>)</td>
                  <td>Pulsar <strong>Abrir capa en GeoLibre Studio</strong> en la pestaña <em>Carpeta repo</em> (transfiere la URL pública mediante <code>?data=</code>).</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <span class="badge badge-propuesta">Módulos funcionales previstos para el PMV</span>
          <h2>Controles y análisis especificados por el perfil</h2>
          <p>Conforme al expediente de la iniciativa, los siguientes módulos y selectores se habilitan progresivamente conforme el equipo incorpora las salidas verificadas en el repositorio:</p>
          <ul>{controls_li}</ul>
        </div>
      </div>
    </section>

    {ext_refs_html}

    {render_project_institutions_band(ctx, branding, manifest, colaborar_href=colaborar_logos_href)}
    """

    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="Geovisor GeoLibre y Aplicación",
        active_nav="aplicacion",
        hero_html=hero,
        body_html=body,
        include_maplibre=True,
    )


def build_metodologia_page(
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    metodologia_md: str,
    branding: dict[str, Any],
) -> str:
    ds_rows = []
    for ds in manifest.get("data_sources", []):
        url_part = (
            f'<br><a href="{html.escape(ds["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{esc(ds["url"])}</a>'
            if ds.get("url")
            else ""
        )
        ds_rows.append(
            f"<tr><td><strong>{esc(ds['title'])}</strong>{url_part}</td>"
            f"<td>{esc(ds.get('provider'), 'Por confirmar')}</td>"
            f"<td><code>{esc(ds.get('access'))}</code></td>"
            f"<td>{badge_html(ds.get('status'))}</td>"
            f"<td>{esc(ds.get('description'), '—')}</td></tr>"
        )
    ds_table = (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Fuente o producto</th><th>Proveedor</th><th>Acceso</th><th>Procedencia</th><th>Notas</th>"
        "</tr></thead><tbody>" + "".join(ds_rows) + "</tbody></table></div>"
        if ds_rows
        else "<p>Fuentes de datos en proceso de documentación.</p>"
    )

    lim_li = "".join(f"<li>{esc(l)}</li>" for l in manifest.get("limitations", [])) or "<li>Sin limitaciones adicionales registradas.</li>"
    colaborar_logos_href = ctx.site_url("colaborar/") + "#anadir-actualizar-logos"

    figuras_dir = ROOT / "web" / "assets" / "img" / "figuras"
    figuras_html = ""
    if figuras_dir.is_dir():
        fig_files = sorted(
            f for f in figuras_dir.iterdir()
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".webp")
        )
        if fig_files:
            fig_cards = []
            for ff in fig_files:
                f_url = html.escape(ctx.site_url(f"assets/img/figuras/{ff.name}"), quote=True)
                f_label = esc(ff.stem.replace("_", " ").capitalize())
                fig_cards.append(
                    f"""
                    <article class="card">
                      <span class="badge badge-ok">Evidencia gráfica del repositorio</span>
                      <h3 style="margin:0.35rem 0 0.5rem;font-size:1rem;">{f_label}</h3>
                      <a href="{f_url}" target="_blank" rel="noopener noreferrer" style="display:block;border:1px solid var(--c-border);border-radius:8px;overflow:hidden;background:#070A14;">
                        <img src="{f_url}" alt="{f_label}" style="width:100%;height:auto;display:block;" loading="lazy">
                      </a>
                    </article>
                    """
                )
            figuras_html = f"""
            <section class="section">
              <h2>Figuras y visualizaciones analíticas incorporadas por el equipo</h2>
              <p>Gráficos y salidas analíticas generadas a partir de los scripts del proyecto en <code>src/</code> y almacenadas en <code>web/assets/img/figuras/</code>:</p>
              <div class="grid-2">{"".join(fig_cards)}</div>
            </section>
            """

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Datos, flujo técnico y cautelas</span>
          <span class="badge badge-country">{esc(manifest['id'])}</span>
        </div>
        <h1>Metodología, fuentes de datos y limitaciones</h1>
        <p class="hero-lead">Fuentes satelitales Copernicus, registros locales declarados en {esc(manifest['territory']['label'])}, secuencia metodológica y condiciones de interpretación.</p>
      </div>
    </section>
    """

    modelo_suelo_href = html.escape(ctx.site_url("modelo-suelo/"), quote=True)
    docx_dl_href = html.escape(ctx.site_url("assets/descargas/Metodologia_Modelo_Valor_Suelo_AMSS_GEE.docx"), quote=True)

    body = f"""
    <section class="section">
      <div class="card" style="border-left:4px solid var(--c-brand-blue);background:#F8FAFC;">
        <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:0.75rem;">
          <div>
            <span class="badge badge-lime">Memoria Técnica Completa · Google Earth Engine</span>
            <h2 style="margin:0.3rem 0 0.2rem;font-size:1.2rem;">Modelo Espacial de Valor del Suelo a Nivel de Píxel (20 m) y Malla Continua (250 m)</h2>
            <p style="margin:0;font-size:0.9rem;color:var(--c-text-muted);">Consulta la subpágina especializada con la arquitectura metodológica de 4 fases, la matriz empírica de 71 predictores (Google Satellite Embeddings V1 + EO), la evaluación de los primeros resultados, las 7 líneas de refinamiento metodológico y el script completo de GEE.</p>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:0.5rem;">
            <a class="btn btn-primary btn-xs" href="{modelo_suelo_href}">📊 Abrir Subpágina del Modelo GEE →</a>
            <a class="btn btn-teal btn-xs" href="{docx_dl_href}" download="Metodologia_Modelo_Valor_Suelo_AMSS_GEE.docx">📥 Descargar Documento Word (.docx)</a>
          </div>
        </div>
      </div>
    </section>

    <section class="section">
      <h2>Fuentes de datos estructuradas en el manifiesto</h2>
      {ds_table}
    </section>

    <section class="section">
      <div class="prose">
        {render_markdown(metodologia_md)}
      </div>
    </section>

    {figuras_html}

    <section class="section">
      <div class="callout callout-warn">
        <strong>Supuestos, discrepancias y limitaciones documentadas</strong>
        <ul>{lim_li}</ul>
      </div>
    </section>

    {render_project_institutions_band(ctx, branding, manifest, colaborar_href=colaborar_logos_href)}
    """

    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="Metodología y datos",
        active_nav="metodologia",
        hero_html=hero,
        body_html=body,
    )


def build_modelo_suelo_page(
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    branding: dict[str, Any],
) -> str:
    pid = manifest["id"]
    colaborar_logos_href = ctx.site_url("colaborar/") + "#anadir-actualizar-logos"

    # Enlaces internos validados
    gv_href = html.escape(ctx.site_url("aplicacion/"), quote=True)
    docx_href = html.escape(ctx.site_url("assets/descargas/Metodologia_Modelo_Valor_Suelo_AMSS_GEE.docx"), quote=True)
    js_href = html.escape(ctx.site_url("assets/descargas/gee_modelo_valor_suelo_amss.js"), quote=True)
    csv_href = html.escape(ctx.site_url("assets/descargas/amss_correlaciones_embeddings_suelo.csv"), quote=True)
    malla_gj_href = html.escape(ctx.site_url("geovisor/capas/amss_malla_continua_250m.geojson"), quote=True)
    upd_gj_href = html.escape(ctx.site_url("geovisor/capas/amss_upd_425_imputadas.geojson"), quote=True)
    tif_href = html.escape(ctx.site_url("geovisor/capas/amss_valor_suelo_pixel_20m.tif"), quote=True)

    fig1_url = html.escape(ctx.site_url("assets/img/figuras/01_arquitectura_metodologica_gee.png"), quote=True)
    fig2_url = html.escape(ctx.site_url("assets/img/figuras/02_cobertura_territorial_upds_amss.png"), quote=True)
    fig3_url = html.escape(ctx.site_url("assets/img/figuras/03_calibracion_log_ols_opamss_mercado.png"), quote=True)
    fig4_url = html.escape(ctx.site_url("assets/img/figuras/04_mapa_resultados_malla_continua_250m.png"), quote=True)
    fig5_url = html.escape(ctx.site_url("assets/img/figuras/05_correlaciones_google_embeddings_eo.png"), quote=True)
    fig6_url = html.escape(ctx.site_url("assets/img/figuras/06_evaluacion_modelo_y_tipologias_urbanas.png"), quote=True)
    px_urb_url = html.escape(ctx.site_url("assets/img/modelo/amss_pixel_20m_urbano.png"), quote=True)
    px_pot_url = html.escape(ctx.site_url("assets/img/modelo/amss_pixel_20m_potencial.png"), quote=True)

    # 1. Leer script GEE completo
    gee_js_path = ROOT / "src" / "gee_modelo_valor_suelo_amss.js"
    gee_js_code = gee_js_path.read_text(encoding="utf-8") if gee_js_path.exists() else "// Script GEE no encontrado"

    # 2. Leer tabla de correlaciones de las 71 bandas
    corr_csv_path = ROOT / "geovisor" / "data" / "amss_correlaciones_embeddings_suelo.csv"
    phys_notes = {
        "wc_trees": "Cobertura arbórea 10 m (ESA WorldCover clase 10): gradiente inverso bosque/cafetal vs. centralidad urbana.",
        "wc_built": "Superficie edificada 10 m (ESA WorldCover clase 50): consolida el salto entre reserva rural y tejido urbano.",
        "viirs_rad": "Radiancia nocturna anual (NOAA VIIRS DNB V2.2): proxy directo de intensidad comercial, vial y de servicios.",
        "dem_slope": "Pendiente topográfica en grados (Copernicus DEM GLO-30): penalización geotécnica y restricción de urbanización.",
        "ob_pres": "Presencia de edificaciones (Google Open Buildings Temporal V1): compacidad predial y ocupación del suelo.",
        "ob_height": "Altura media 2.5D de edificaciones en metros (Open Buildings V1): captura verticalización y nodos corporativos.",
        "dem_elev": "Elevación ortométrica m s.n.m. (GLO-30): no lineal (existen polos prime tanto en valles como en mesetas altas).",
    }
    corr_rows_html: list[str] = []
    if corr_csv_path.exists():
        with corr_csv_path.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rk = int(row["ranking"])
                banda = row["banda"]
                grupo = row["grupo"]
                r_val = float(row["r_pearson"])
                abs_r = float(row["abs_r"])
                p_val = float(row["p_valor"])

                if abs_r >= 0.50:
                    tier_key = "fuerte"
                    tier_badge = '<span class="badge badge-ok">Fuerte (|r| ≥ 0.50)</span>'
                elif p_val < 0.05:
                    tier_key = "moderada"
                    tier_badge = '<span class="badge badge-declarado">Significativa (p &lt; 0.05)</span>'
                else:
                    tier_key = "no_sig"
                    tier_badge = '<span class="badge badge-pendiente">No lineal / NS</span>'

                grp_label = "Google Embedding V1 (10 m)" if grupo == "Google_Embedding" else "Física / EO Explícita"
                bar_w = min(100, int(round((abs_r / 0.72) * 100)))
                bar_col = "#0284C7" if r_val >= 0 else "#DC2626"
                p_str = f"{p_val:.2e}" if p_val < 0.001 else f"{p_val:.4f}"

                if banda in phys_notes:
                    interp = phys_notes[banda]
                elif abs_r >= 0.58:
                    sign_txt = "positiva con morfología comercial/residencial densa" if r_val > 0 else "inversa (alta activación en dosel agroforestal y baja en centros consolidados)"
                    interp = f"Dimensión latente multimodal de máxima respuesta {sign_txt}."
                elif abs_r >= 0.40:
                    interp = "Vector latente intermedio de textura urbana, red vial y transición periurbana."
                elif p_val < 0.05:
                    interp = "Componente complementaria de micro-estructura espectral y radar (útil en interacciones no lineales RF)."
                else:
                    interp = "Ortogonal al gradiente lineal global de precios; aporta particiones locales secundarias."

                corr_rows_html.append(
                    f'<tr data-filter-item data-grupo="{esc(grupo)}" data-nivel="{esc(tier_key)}" '
                    f'data-search-text="{esc(banda)} {esc(grp_label)} {esc(interp)}">'
                    f"<td><strong>#{rk}</strong></td>"
                    f"<td><code>{esc(banda)}</code></td>"
                    f"<td>{esc(grp_label)}</td>"
                    f'<td style="white-space:nowrap;"><strong style="color:{bar_col};">{r_val:+.4f}</strong>'
                    f'<div style="width:90px;height:6px;background:#E2E8F0;border-radius:3px;margin-top:3px;overflow:hidden;">'
                    f'<div style="width:{bar_w}%;height:100%;background:{bar_col};"></div></div></td>'
                    f"<td>{abs_r:.4f}</td>"
                    f"<td><code>{p_str}</code></td>"
                    f"<td>{tier_badge}</td>"
                    f'<td style="font-size:0.82rem;color:var(--c-text-muted);">{esc(interp)}</td>'
                    f"</tr>"
                )

    # 3. Calcular jerarquía distrital exacta desde geovisor/capas/amss_malla_continua_250m.geojson
    malla_path = ROOT / "geovisor" / "capas" / "amss_malla_continua_250m.geojson"
    dist_rows_html: list[str] = []
    if malla_path.exists():
        malla_fc = json.loads(malla_path.read_text(encoding="utf-8"))
        by_dist: dict[tuple[str, str], dict[str, Any]] = {}
        for feat in malla_fc.get("features", []):
            pr = feat.get("properties") or {}
            d_name = str(pr.get("DISTRITO") or "Sin clasificar")
            m_name = str(pr.get("MUNICIPIO") or "AMSS")
            if d_name == "Periferia Metropolitana":
                continue
            key = (d_name, m_name)
            rec = by_dist.setdefault(key, {"vals_all": [], "vals_urb": [], "ha": 0.0})
            v = float(pr.get("VAL_EST_M2") or 0.0)
            rec["vals_all"].append(v)
            rec["ha"] += float(pr.get("AREA_HA") or 0.0)
            if pr.get("TIPO_SUELO") == "URBANO_CONSOLIDADO":
                rec["vals_urb"].append(v)

        dist_summary = []
        for (d_name, m_name), rec in by_dist.items():
            vals_all = sorted(rec["vals_all"])
            vals_urb = sorted(rec["vals_urb"])
            n_all = len(vals_all)
            n_urb = len(vals_urb)
            med_all = statistics.median(vals_all) if vals_all else 0.0
            p90_idx = min(n_all - 1, max(0, int(round(0.90 * (n_all - 1)))))
            p90_all = vals_all[p90_idx] if vals_all else 0.0
            max_all = vals_all[-1] if vals_all else 0.0
            med_urb = statistics.median(vals_urb) if vals_urb else 0.0
            dist_summary.append((med_urb, p90_all, d_name, m_name, n_all, rec["ha"], n_urb, med_all, max_all))

        dist_summary.sort(key=lambda x: (x[0], x[1]), reverse=True)
        for idx_d, (med_urb, p90_all, d_name, m_name, n_all, ha_tot, n_urb, med_all, max_all) in enumerate(dist_summary, start=1):
            urb_txt = f"${med_urb:,.2f}" if n_urb > 0 else "Sin celda consolidada"
            dist_rows_html.append(
                f"<tr>"
                f"<td>{idx_d}</td>"
                f"<td><strong>{esc(d_name)}</strong></td>"
                f"<td>{esc(m_name)}</td>"
                f"<td>{n_all:,}</td>"
                f"<td>{ha_tot:,.1f} ha</td>"
                f"<td>{n_urb:,}</td>"
                f"<td><strong>{urb_txt}</strong></td>"
                f"<td>${med_all:,.2f}</td>"
                f"<td>${p90_all:,.2f}</td>"
                f"<td>${max_all:,.2f}</td>"
                f"</tr>"
            )

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Modelo GeoAI · Google Satellite Embeddings V1 + Copernicus EO</span>
          <span class="badge badge-country">{esc(pid)} · AMSS</span>
        </div>
        <h1>Metodología, Primeros Resultados y Hoja de Ruta del Modelo Continuo de Valor del Suelo (GEE)</h1>
        {render_hero_team(manifest)}
        <p class="hero-lead">Estimación espacialmente explícita a nivel de píxel (20 m) y agregación sobre una malla continua de 24,292 polígonos (250 m) y 425 UPDs sin vacíos en el Área Metropolitana de San Salvador y distritos incorporados, integrando registros administrativos de OPAMSS, oferta inmobiliaria 2025 y 71 predictores satelitales en Google Earth Engine.</p>
        <div class="hero-actions">
          <a class="btn btn-primary" href="{gv_href}">🗺️ Explorar Capas en el Geovisor Interactivo →</a>
          <a class="btn btn-teal" href="{docx_href}" download="Metodologia_Modelo_Valor_Suelo_AMSS_GEE.docx">📥 Descargar Documento Word Actualizado (.docx)</a>
          <a class="btn btn-outline-light" href="#codigo-gee">📜 Ver y Copiar Script GEE (.js)</a>
          <a class="btn btn-outline-light" href="#mejoras-metodologicas">🔧 Cómo Mejorar y Afinar el Modelo</a>
        </div>
      </div>
    </section>
    """

    body = f"""
    <section class="section" aria-label="Descargas directas de productos del modelo">
      <div class="card" style="border-top:4px solid var(--c-brand-blue);background:#F8FAFC;">
        <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:0.75rem;">
          <div>
            <span class="badge badge-ok">Repositorio Abierto y Reproducible</span>
            <h2 style="margin:0.3rem 0 0.2rem;font-size:1.15rem;">Paquete Completo de Entregables del Modelo de Valor del Suelo</h2>
            <p style="margin:0;font-size:0.88rem;color:var(--c-text-muted);">Descarga directamente la memoria metodológica en Word (actualizada con el análisis de resultados), el script optimizado de Google Earth Engine, la matriz estadística de las 71 bandas y las capas geoespaciales generadas.</p>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:0.45rem;">
            <a class="btn btn-primary btn-xs" href="{docx_href}" download="Metodologia_Modelo_Valor_Suelo_AMSS_GEE.docx">📄 Metodología y Resultados (.docx)</a>
            <a class="btn btn-teal btn-xs" href="{js_href}" download="gee_modelo_valor_suelo_amss.js">📜 Script GEE (.js)</a>
            <a class="btn btn-outline btn-xs" href="{csv_href}" download="amss_correlaciones_embeddings_suelo.csv">📊 Correlaciones 71 Bandas (.csv)</a>
            <a class="btn btn-outline btn-xs" href="{malla_gj_href}" download="amss_malla_continua_250m.geojson">🗺️ Malla 250 m (.geojson)</a>
            <a class="btn btn-outline btn-xs" href="{upd_gj_href}" download="amss_upd_425_imputadas.geojson">🧩 425 UPDs (.geojson)</a>
            <a class="btn btn-outline btn-xs" href="{tif_href}" download="amss_valor_suelo_pixel_20m.tif">🛰️ Raster Píxel 20 m (.tif)</a>
          </div>
        </div>
      </div>
    </section>

    <section class="section" aria-label="Síntesis cuantitativa de los primeros resultados">
      <div class="section-header">
        <div>
          <span class="badge badge-lime">Síntesis Ejecutiva</span>
          <h2>Indicadores Clave de la Primera Corrida Empírica en el AMSS</h2>
        </div>
        <nav aria-label="Índice rápido de la subpágina" style="display:flex;flex-wrap:wrap;gap:0.4rem;">
          <a class="btn btn-outline btn-xs" href="#metodologia-aplicada">1. Metodología</a>
          <a class="btn btn-outline btn-xs" href="#primeros-resultados">2. Primeros Resultados</a>
          <a class="btn btn-outline btn-xs" href="#correlaciones-embeddings">3. Correlaciones (71 bandas)</a>
          <a class="btn btn-outline btn-xs" href="#jerarquia-distrital">4. Distritos AMSS</a>
          <a class="btn btn-outline btn-xs" href="#mejoras-metodologicas">5. Cómo Mejorar el Modelo</a>
          <a class="btn btn-outline btn-xs" href="#codigo-gee">6. Script GEE</a>
        </nav>
      </div>

      <div class="grid-3">
        <article class="card" style="border-top:3px solid #0284C7;">
          <span class="badge badge-ok">Cobertura Territorial 100%</span>
          <h3 style="font-size:1.65rem;margin:0.3rem 0;color:var(--c-brand-blue);">24,292 celdas</h3>
          <p style="margin:0;font-size:0.88rem;"><strong>Malla continua cuadrada de 250 m (6.25 ha)</strong> sobre <strong>148,898.7 ha</strong> (28 distritos del ámbito metropolitano ampliado), con <strong>0 celdas vacías</strong> y mediana urbana consolidada de <strong>$169.24 USD/m²</strong> (media <strong>$187.27/m²</strong>).</p>
        </article>
        <article class="card" style="border-top:3px solid #0F766E;">
          <span class="badge badge-ok">Resolución Sub-hectárea</span>
          <h3 style="font-size:1.65rem;margin:0.3rem 0;color:var(--c-brand-blue);">3.85 M píxeles (20 m)</h3>
          <p style="margin:0;font-size:0.88rem;"><strong>3,845,824 píxeles válidos</strong> estimados a 20 m (<strong>3,631,473</strong> en suelo urbano/desarrollable con pendiente &lt; 35° sin agua), capturando un gradiente continuo entre <strong>$8.66 y $471.13 USD/m²</strong>.</p>
        </article>
        <article class="card" style="border-top:3px solid #D97706;">
          <span class="badge badge-ok">Cierre de Brecha Catastral</span>
          <h3 style="font-size:1.65rem;margin:0.3rem 0;color:var(--c-brand-blue);">425 UPDs (0 vacíos)</h3>
          <p style="margin:0;font-size:0.88rem;">Integra las <strong>281 UPDs observadas/calibradas</strong> e imputa satelitalmente las <strong>144 UPDs sin registros previos</strong> (<strong>57,647.5 ha</strong>, 33.9% del padrón de UPDs) con mediana imputada de <strong>$35.14 USD/m²</strong>.</p>
        </article>
        <article class="card" style="border-top:3px solid #7C3AED;">
          <span class="badge badge-declarado">Señal Espectral-Estructural</span>
          <h3 style="font-size:1.65rem;margin:0.3rem 0;color:var(--c-brand-blue);">r = −0.694 (p &lt; 10⁻⁴⁰)</h3>
          <p style="margin:0;font-size:0.88rem;"><strong>64 de los 71 predictores</strong> presentan correlación estadísticamente significativa (p &lt; 0.05) con <code>ln(Valor)</code> y <strong>24 superan |r| ≥ 0.50</strong>, encabezados por los embeddings <code>A13</code>, <code>A32</code> y <code>A34</code>.</p>
        </article>
        <article class="card" style="border-top:3px solid #16A34A;">
          <span class="badge badge-declarado">Consistencia Central</span>
          <h3 style="font-size:1.65rem;margin:0.3rem 0;color:var(--c-brand-blue);">r = 0.782 · Sesgo −0.8%</h3>
          <p style="margin:0;font-size:0.88rem;">Sobre las 281 UPDs con verdad terreno, la correlación lineal alcanza <strong>r = 0.7816</strong> (<strong>r_log = 0.7238</strong>), reproduciendo con alta fidelidad la mediana observada (<strong>$102.84 vs. $103.66 USD/m²</strong>).</p>
        </article>
        <article class="card" style="border-top:3px solid #B91C1C;">
          <span class="badge badge-propuesta">Eficiencia Computacional GEE</span>
          <h3 style="font-size:1.65rem;margin:0.3rem 0;color:var(--c-brand-blue);">Halo = 0 · 0 Timeouts</h3>
          <p style="margin:0;font-size:0.88rem;">Al aprovechar el contexto espacial ya pre-codificado en <strong>Google Satellite Embeddings V1</strong> y delegar <code>reduceRegions</code> a tareas <em>Batch</em>, el visor GEE carga sin errores de memoria.</p>
        </article>
      </div>
    </section>

    <section class="section" id="metodologia-aplicada">
      <span class="badge badge-lime">Sección 1 · Diseño Metodológico</span>
      <h2>Metodología Aplicada: Del Registro Fragmentado por UPD a la Malla Continua Metropolitana</h2>
      <p>El problema estructural que enfrenta la planificación metropolitana en el AMSS es la <strong>discontinuidad espacial y temporal de las fuentes de precios de suelo</strong>: los expedientes administrativos de permisos de construcción de OPAMSS (2007–2019 y 2020–2026) solo registran actividad donde hubo trámites formales, mientras que el levantamiento de ofertas inmobiliarias de mercado 2025 cubre 265 de las 425 UPDs válidas, dejando vacíos de información en el 33.9% de las unidades y ocultando la heterogeneidad interna dentro de polígonos extensos de borde periurbano.</p>
      <p>Para resolver esta limitación de manera reproducible y escalable, se implementó una arquitectura secuencial en <strong>cuatro fases</strong> acoplando preprocesamiento econométrico local en Python con modelado de aprendizaje automático en la nube mediante <strong>Google Earth Engine (GEE)</strong>:</p>

      <div class="grid-2" style="margin-top:1rem;">
        <article class="card">
          <span class="badge badge-declarado">Fase 1 · Preparación y Armonización Econométrica</span>
          <h3>Fusión jerárquica multi-fuente y calibración Log-OLS a precios 2025</h3>
          <p>Se depuraron topológicamente las 425 UPDs válidas y se construyó la variable objetivo armonizada <code>VAL_FUS25</code> (USD/m² equivalentes a mercado 2025 en <strong>281 UPDs</strong>, 66.1% del padrón) aplicando tres reglas de control estadístico:</p>
          <ul>
            <li><strong>Prioridad 1 — Oferta de mercado 2025 (265 UPDs):</strong> adopción directa del precio unitario medio verificado por <em>web scraping</em> inmobiliario 2025 (<code>promedio_2025</code>).</li>
            <li><strong>Prioridad 2 — Calibración inter-fuente OPAMSS 2020–2026 (+13 UPDs):</strong> ajuste por mínimos cuadrados ordinarios en escala logarítmica sobre las UPDs con traslape simultáneo entre permisos recientes y mercado 2025 (<code>ln(V_mkt25) = 2.6606 + 0.5071 · ln(P2_MED)</code>), corrigiendo el sub-reporte fiscal/administrativo respecto al valor comercial.</li>
            <li><strong>Prioridad 3 — Calibración histórica OPAMSS 2007–2019 con filtro de atípicos (+3 UPDs):</strong> uso exclusivo de la mediana robusta <code>P1_MED</code> y winsorización P99 para neutralizar 4 registros históricos anómalos (&gt; $7,000/m²).</li>
          </ul>
        </article>

        <article class="card">
          <span class="badge badge-declarado">Fase 2 · Cubo Satelital Punto a Punto (71 Bandas)</span>
          <h3>Google Satellite Embeddings V1 + Variables Explícitas EO (Arquitectura Halo = 0)</h3>
          <p>En lugar de calcular costosas texturas focales (GLCM o ventanas móviles) sobre cientos de escenas crudas —lo que provoca errores <code>User memory limit exceeded</code> en la consola interactiva de GEE—, se ensambló un stack punto a punto de <strong>71 bandas precomputadas</strong>:</p>
          <ul>
            <li><strong>64 dimensiones latentes (<code>A00</code>–<code>A63</code> a 10 m) de <code>GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL</code>:</strong> vectores generados por un modelo fundacional multimodal que destila series anuales completas de Sentinel-2 óptico, Sentinel-1 SAR C-band, Landsat térmico, elevación y clima, encapsulando intrínsecamente la morfología del vecindario urbano sin requerir kernels adicionales.</li>
            <li><strong>7 covariables físicas y económicas explícitas:</strong> presencia y altura edilicia 2.5D (<code>GOOGLE/Research/open-buildings-temporal/v1</code>), fracción construida y cobertura arbórea a 10 m (<code>ESA/WorldCover/v200</code>), radiancia nocturna anual (<code>NOAA/VIIRS/DNB/ANNUAL_V22</code>) y elevación + pendiente topográfica a 30 m (<code>COPERNICUS/DEM/GLO30</code>).</li>
          </ul>
        </article>

        <article class="card">
          <span class="badge badge-declarado">Fase 3 · Inferencia No Paramétrica a Nivel de Píxel</span>
          <h3>Muestreo en huella edificable y regresión Random Forest con ajuste log-normal</h3>
          <p>Para evitar el sesgo ecológico de entrenar con píxeles boscosos o barrancos dentro de UPDs periféricas grandes, la etiqueta <code>ln(VAL_FUS25)</code> se muestrea exclusivamente sobre la <strong>máscara de huella urbana desarrollable</strong>:</p>
          <ul>
            <li><strong>Máscara de entrenamiento:</strong> <code>(wc_built == 1 OR ob_pres &gt; 0.12) AND dem_slope &lt; 32° AND wc_water == 0</code> (<code>n = 1,800</code> píxeles estratificados a 30 m con <code>tileScale = 8</code>).</li>
            <li><strong>Modelo <code>smileRandomForest</code> (modo <code>REGRESSION</code>):</strong> 80 árboles de decisión, <code>variablesPerSplit = 18</code>, <code>minLeafPopulation = 5</code> y <code>bagFraction = 0.70</code> entrenados sobre <code>ln(V)</code> para estabilizar la asimetría positiva de los precios inmobiliarios.</li>
            <li><strong>Re-transformación con corrección de sesgo de Duan:</strong> conversión a dólares corrientes mediante <code>V_px = 1.06 · exp(ln_V_pred)</code>, generando tanto la superficie potencial completa como la superficie de suelo urbano/desarrollable (pendiente &lt; 35° sin cuerpos de agua) a <strong>20 m</strong>.</li>
          </ul>
        </article>

        <article class="card">
          <span class="badge badge-declarado">Fase 4 · Agregación Zonal en Malla Continua y UPDs</span>
          <h3>Generación nativa de grilla UTM 16N (250 m) e imputación de vacíos</h3>
          <p>Toda la carga de reducción zonal sobre decenas de miles de polígonos se desacopla del visor interactivo y se ejecuta en el motor paralelo <strong>Batch Export</strong> de GEE:</p>
          <ul>
            <li><strong>Malla continua de 250 m (<code>coveringGrid</code> en <code>EPSG:32616</code> homologada a <code>EPSG:4326</code>):</strong> recorte exacto al perímetro metropolitano oficial generando <strong>24,292 celdas</strong> con media (<code>VAL_EST_M2</code>), mediana (<code>VAL_MED_M2</code>), potencial (<code>VAL_POT_M2</code>), desviación estándar intra-celda (<code>VAL_STD_M2</code>), fracción construida, altura 2.5D, pendiente y tipología territorial (<code>TIPO_SUELO</code>).</li>
            <li><strong>Padrón completo de 425 UPDs:</strong> preserva el dato empírico observado en las 281 UPDs con muestra y asigna la predicción satelital media en huella urbana a las <strong>144 UPDs faltantes</strong> (<code>ORIGEN_FIN = IMPUTADO_MODELO_GEE</code>).</li>
          </ul>
        </article>
      </div>

      <div class="grid-3" style="margin-top:1.15rem;">
        <article class="card">
          <span class="badge badge-ok">Figura Metodológica 1</span>
          <h3 style="font-size:0.98rem;margin:0.3rem 0 0.45rem;">Arquitectura de 4 fases en Google Earth Engine</h3>
          <a href="{fig1_url}" target="_blank" rel="noopener noreferrer" style="display:block;border:1px solid var(--c-border);border-radius:8px;overflow:hidden;">
            <img src="{fig1_url}" alt="Diagrama de arquitectura metodológica en cuatro fases para el modelo de valor del suelo del AMSS en Google Earth Engine" style="width:100%;height:auto;display:block;" loading="lazy">
          </a>
        </article>
        <article class="card">
          <span class="badge badge-ok">Figura Metodológica 2</span>
          <h3 style="font-size:0.98rem;margin:0.3rem 0 0.45rem;">Cobertura empírica inicial vs. vacíos de información</h3>
          <a href="{fig2_url}" target="_blank" rel="noopener noreferrer" style="display:block;border:1px solid var(--c-border);border-radius:8px;overflow:hidden;">
            <img src="{fig2_url}" alt="Mapa de cobertura territorial de las 281 UPDs con muestra observada frente a las 144 UPDs sin datos previos en el AMSS" style="width:100%;height:auto;display:block;" loading="lazy">
          </a>
        </article>
        <article class="card">
          <span class="badge badge-ok">Figura Metodológica 3</span>
          <h3 style="font-size:0.98rem;margin:0.3rem 0 0.45rem;">Calibración econométrica Log-OLS entre fuentes</h3>
          <a href="{fig3_url}" target="_blank" rel="noopener noreferrer" style="display:block;border:1px solid var(--c-border);border-radius:8px;overflow:hidden;">
            <img src="{fig3_url}" alt="Gráfico de regresión log-lineal entre valores administrativos de permisos OPAMSS y precios de oferta inmobiliaria 2025" style="width:100%;height:auto;display:block;" loading="lazy">
          </a>
        </article>
      </div>
    </section>

    <section class="section" id="primeros-resultados">
      <span class="badge badge-lime">Sección 2 · Análisis e Interpretación de Resultados</span>
      <h2>Análisis Estadístico e Interpretación Territorial de los Primeros Resultados</h2>

      <div class="grid-2" style="margin-top:0.85rem;">
        <article class="card">
          <span class="badge badge-ok">Figura de Resultados 4 · Malla 250 m</span>
          <h3 style="font-size:1.05rem;margin:0.3rem 0 0.45rem;">Distribución espacial continua en las 24,292 celdas de 250 m</h3>
          <a href="{fig4_url}" target="_blank" rel="noopener noreferrer" style="display:block;border:1px solid var(--c-border);border-radius:8px;overflow:hidden;">
            <img src="{fig4_url}" alt="Mapa coroplético de resultados del modelo continuo de valor del suelo en malla de 250 metros sobre el AMSS" style="width:100%;height:auto;display:block;" loading="lazy">
          </a>
          <p style="font-size:0.84rem;color:var(--c-text-muted);margin:0.55rem 0 0;">Estructura policéntrica estimada: se distingue con nitidez el núcleo financiero-comercial San Benito – Escalón – Santa Elena – Merliot (&gt; $300/m²), los corredores consolidados de Soyapango, Mejicanos y San Marcos ($130–$220/m²), los ejes de expansión norte/sur/costa ($50–$120/m²) y la matriz agroforestal de reserva (&lt; $35/m²).</p>
        </article>

        <article class="card">
          <span class="badge badge-ok">Figura de Resultados 6 · Validación y Tipologías</span>
          <h3 style="font-size:1.05rem;margin:0.3rem 0 0.45rem;">Ajuste observado vs. predicho y estratificación morfológica</h3>
          <a href="{fig6_url}" target="_blank" rel="noopener noreferrer" style="display:block;border:1px solid var(--c-border);border-radius:8px;overflow:hidden;">
            <img src="{fig6_url}" alt="Gráficos de validación empírica del modelo Random Forest en 281 UPDs observadas y distribución de valores por régimen morfológico" style="width:100%;height:auto;display:block;" loading="lazy">
          </a>
          <p style="font-size:0.84rem;color:var(--c-text-muted);margin:0.55rem 0 0;">El modelo separa nítidamente los tres regímenes territoriales (medianas de <strong>$169.24/m²</strong> en Urbano Consolidado, <strong>$67.49/m²</strong> en Periurbano en Transición y <strong>$31.11/m²</strong> en Rural/Reserva) y cierra sin saltos artificiales las 144 UPDs sin muestra previa.</p>
        </article>
      </div>

      <h3 style="margin-top:1.5rem;color:var(--c-brand-blue);">2.1 Comportamiento por Régimen Morfológico en la Malla Continua de 250 m</h3>
      <p>La clasificación automática de las 24,292 celdas según su fracción edificada a 10 m (<code>FRAC_EDIF</code>) demuestra que el modelo aprende una jerarquía económicamente coherente entre consolidación física, altura edilicia 2.5D y valor unitario de la tierra:</p>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Régimen Morfológico (<code>TIPO_SUELO</code>)</th>
              <th>Criterio Físico (10 m)</th>
              <th>Celdas (250 m)</th>
              <th>Superficie (ha / %)</th>
              <th>Media (USD/m²)</th>
              <th>Mediana (USD/m²)</th>
              <th>Percentil 90 (USD/m²)</th>
              <th>Máximo (USD/m²)</th>
              <th>Altura Media 2.5D</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Urbano Consolidado</strong></td>
              <td><code>FRAC_EDIF ≥ 45%</code></td>
              <td>2,215</td>
              <td>13,824.6 ha (9.3%)</td>
              <td><strong>$187.27</strong></td>
              <td><strong>$169.24</strong></td>
              <td>$302.70</td>
              <td>$375.90</td>
              <td>4.68 m</td>
            </tr>
            <tr>
              <td><strong>Periurbano en Transición</strong></td>
              <td><code>10% ≤ FRAC_EDIF &lt; 45%</code></td>
              <td>1,571</td>
              <td>9,578.1 ha (6.4%)</td>
              <td><strong>$74.35</strong></td>
              <td><strong>$67.49</strong></td>
              <td>$130.64</td>
              <td>$285.10</td>
              <td>1.29 m</td>
            </tr>
            <tr>
              <td><strong>Rural / Reserva Ambiental</strong></td>
              <td><code>FRAC_EDIF &lt; 10%</code></td>
              <td>20,506</td>
              <td>125,472.4 ha (84.3%)</td>
              <td><strong>$33.35</strong></td>
              <td><strong>$31.11</strong></td>
              <td>$42.59</td>
              <td>$245.18</td>
              <td>0.08 m</td>
            </tr>
            <tr style="background:#F1F5F9;font-weight:700;">
              <td>Total Ámbito Metropolitano</td>
              <td>Cobertura continua 100%</td>
              <td>24,292</td>
              <td>148,875.1 ha (100%)</td>
              <td>$50.04</td>
              <td>$32.47</td>
              <td>$93.83</td>
              <td>$375.90</td>
              <td>0.58 m</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="grid-2" style="margin-top:1.15rem;">
        <article class="card">
          <span class="badge badge-declarado">Superficie Raster Píxel 20 m · Suelo Desarrollable</span>
          <h4 style="margin:0.3rem 0 0.4rem;">Máscara de aptitud urbanística (Pendiente &lt; 35° sin cuerpos de agua)</h4>
          <a href="{px_urb_url}" target="_blank" rel="noopener noreferrer" style="display:block;border:1px solid var(--c-border);border-radius:8px;overflow:hidden;background:#0F172A;">
            <img src="{px_urb_url}" alt="Superficie raster continua a 20 metros de valor del suelo urbano y desarrollable en el AMSS" style="width:100%;height:auto;display:block;" loading="lazy">
          </a>
          <p style="font-size:0.83rem;color:var(--c-text-muted);margin:0.45rem 0 0;"><strong>3,631,473 píxeles válidos</strong> (mediana $32.34/m², P90 $100.22/m², P95 $176.17/m², P99 $317.72/m², máximo puntual $471.13/m²). Excluye laderas escarpadas de cañones volcánicos (&ge; 35°) y el espejo de agua del Lago de Ilopango.</p>
        </article>
        <article class="card">
          <span class="badge badge-declarado">Superficie Raster Píxel 20 m · Potencial Continuo</span>
          <h4 style="margin:0.3rem 0 0.4rem;">Superficie teórica sin máscara topográfica</h4>
          <a href="{px_pot_url}" target="_blank" rel="noopener noreferrer" style="display:block;border:1px solid var(--c-border);border-radius:8px;overflow:hidden;background:#0F172A;">
            <img src="{px_pot_url}" alt="Superficie raster continua potencial a 20 metros sobre la totalidad del perímetro del AMSS" style="width:100%;height:auto;display:block;" loading="lazy">
          </a>
          <p style="font-size:0.83rem;color:var(--c-text-muted);margin:0.45rem 0 0;"><strong>3,845,824 píxeles válidos</strong> sobre todo el polígono envolvente oficial. Útil como insumo base para algoritmos de reducción zonal cuando una celda de borde contiene micro-relieve mixto.</p>
        </article>
      </div>

      <h3 style="margin-top:1.5rem;color:var(--c-brand-blue);">2.2 Evaluación de Desempeño en UPDs Observadas e Interpretación de Residuales</h3>
      <p>Al contrastar la predicción agregada del modelo GEE (<code>VAL_MOD_M2</code>) frente al valor observado/calibrado (<code>VAL_FUS25</code>) en las <strong>281 UPDs con muestra empírica</strong>, emergen tres hallazgos fundamentales para la gestión urbana de OPAMSS:</p>
      <ol>
        <li><strong>Ausencia de sesgo sistemático en la tendencia central:</strong> la mediana predicha por el modelo satelital (<strong>$102.84 USD/m²</strong>) coincide prácticamente con la mediana observada (<strong>$103.66 USD/m²</strong>, diferencia de apenas <code>−$0.82/m²</code> o <code>−0.79%</code>), con una correlación lineal de Pearson de <strong>r = 0.7816</strong> (<strong>r = 0.7238</strong> en logaritmos) y un error absoluto mediano relativo (<code>MedAPE</code>) de <strong>40.97%</strong> (<code>MAE = $58.42/m²</code>).</li>
        <li><strong>Atenuación esperada en el percentil extremo superior (&gt; $400/m²):</strong> mientras que el P95 observado alcanza <strong>$407.84/m²</strong> (con picos puntuales de oferta comercial corporativa hasta $677.30/m²), el P95 del modelo en UPDs se sitúa en <strong>$303.74/m²</strong> (y $471.13/m² a nivel de píxel individual). Este comportamiento es propio de los ensamblajes <em>Random Forest</em> (que promedian hojas terminales y no extrapolan fuera del soporte convexo) y refleja además que las plusvalías extraordinarias por encima de $400/m² dependen de <strong>normativa específica de altura/uso comercial y prestigio micro-local</strong> no totalmente distinguibles solo desde el espacio.</li>
        <li><strong>Plausibilidad territorial en las 144 UPDs imputadas (57,647.5 ha):</strong> las 144 UPDs que carecían por completo de registros presentan una mediana imputada de <strong>$35.14 USD/m²</strong> (media <strong>$50.69/m²</strong>, rango <strong>$17.75 a $267.21/m²</strong>), asignando valores altos únicamente a enclaves residenciales/industriales consolidados sin trámites recientes y valores bajos ($20–$40/m²) a cantones rurales periféricos.</li>
      </ol>
    </section>

    <section class="section" id="correlaciones-embeddings">
      <span class="badge badge-lime">Sección 3 · Explicabilidad GeoAI (71 Bandas)</span>
      <h2>Matriz de Correlaciones: ¿Qué Capturan los Google Satellite Embeddings frente a las Capas Físicas?</h2>
      <p>El cálculo en GEE del coeficiente de correlación de Pearson entre el promedio urbano de cada una de las <strong>71 bandas predictoras</strong> y <code>ln(VAL_FUS25)</code> sobre las UPDs de entrenamiento confirma empíricamente el altísimo poder explicativo de las representaciones auto-supervisadas de <strong>Google Satellite Embeddings V1</strong>:</p>

      <div class="card" style="margin-bottom:1.1rem;">
        <a href="{fig5_url}" target="_blank" rel="noopener noreferrer" style="display:block;border:1px solid var(--c-border);border-radius:8px;overflow:hidden;">
          <img src="{fig5_url}" alt="Ranking de correlaciones de Pearson de las bandas de Google Satellite Embeddings V1 y variables físicas de observación de la Tierra con el logaritmo del valor del suelo en el AMSS" style="width:100%;height:auto;display:block;" loading="lazy">
        </a>
      </div>

      <div class="callout">
        <strong>Lectura sustantiva de los predictores dominantes</strong>
        <ul>
          <li><strong>Superioridad de las dimensiones latentes multimodales (Top 3 absoluto):</strong> tres bandas de Google Embeddings —<code>A13</code> (<code>r = −0.6939</code>), <code>A32</code> (<code>r = −0.6600</code>) y <code>A34</code> (<code>r = +0.6495</code>)— superan individualmente a cualquier indicador físico tradicional aislado. Esto ocurre porque cada dimensión de <code>SATELLITE_EMBEDDING/V1/ANNUAL</code> sintetiza simultáneamente reflectancia multiespectral estacional, retrodispersión radar SAR de doble rebote en estructuras edilicias, rugosidad de techos y firma térmica superficial.</li>
          <li><strong>Coherencia física de las variables explícitas de Observación de la Tierra:</strong> la cobertura arbórea <code>wc_trees</code> ocupa el 4.° lugar global con correlación negativa (<code>r = −0.6250</code>), seguida de inmediato por la fracción construida <code>wc_built</code> en 5.° lugar (<code>r = +0.6209</code>), la radiancia económica nocturna <code>viirs_rad</code> en 13.° lugar (<code>r = +0.5779</code>), la pendiente topográfica <code>dem_slope</code> en 30.° lugar (<code>r = −0.4716</code>), la densidad predial <code>ob_pres</code> (<code>r = +0.4707</code>) y la altura media 2.5D <code>ob_height</code> (<code>r = +0.3115</code>).</li>
          <li><strong>No linealidad de la altitud (<code>dem_elev</code>, <code>r = +0.0748, p = 0.2115</code>):</strong> la elevación absoluta no tiene correlación lineal simple porque en el AMSS coexisten submercados de alto valor tanto en terrazas medias (700–950 m s.n.m. en Antiguo Cuscatlán y Santa Tecla) como en desarrollos residenciales de montaña (&gt; 1,100 m s.n.m. en El Espino / Cordillera del Bálsamo) y desarrollos turísticos costeros a nivel del mar en La Libertad Costa; sin embargo, dentro de los árboles de decisión del Random Forest actúa como modulador contextual clave.</li>
        </ul>
      </div>

      <div class="card" data-catalog-correlations style="margin-top:1rem;">
        <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:0.75rem;margin-bottom:0.85rem;">
          <div>
            <h3 style="margin:0 0 0.2rem;">Tabla Interactiva Completa de las 71 Bandas Evaluadas en GEE</h3>
            <p style="margin:0;font-size:0.84rem;color:var(--c-text-muted);" data-filter-count>71 de 71 registros mostrados</p>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:0.5rem;align-items:flex-end;">
            <div class="filter-field" style="min-width:200px;">
              <label for="corr-search">Buscar banda o concepto</label>
              <input id="corr-search" type="search" placeholder="Ej. A13, viirs, altura..." data-filter-search>
            </div>
            <div class="filter-field">
              <label for="corr-grupo">Familia de banda</label>
              <select id="corr-grupo" data-filter-select="grupo">
                <option value="all">Todas las familias (71)</option>
                <option value="Google_Embedding">Google Satellite Embeddings V1 (64)</option>
                <option value="Fisica_EO">Variables Físicas / EO Explícitas (7)</option>
              </select>
            </div>
            <div class="filter-field">
              <label for="corr-nivel">Magnitud estadística</label>
              <select id="corr-nivel" data-filter-select="nivel">
                <option value="all">Todos los niveles</option>
                <option value="fuerte">Fuerte |r| ≥ 0.50 (24)</option>
                <option value="moderada">Significativa p &lt; 0.05 (40)</option>
                <option value="no_sig">No lineal / NS p ≥ 0.05 (7)</option>
              </select>
            </div>
            <button type="button" class="btn btn-outline btn-xs" data-filter-reset>Restablecer</button>
          </div>
        </div>

        <p class="hidden" data-filter-empty style="padding:0.75rem;background:#FEF2F2;color:#991B1B;border-radius:6px;">No hay bandas que coincidan con el filtro aplicado.</p>

        <div class="table-wrap" style="max-height:520px;overflow-y:auto;">
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Banda</th>
                <th>Familia</th>
                <th>Pearson r</th>
                <th>|r|</th>
                <th>Valor p</th>
                <th>Significancia</th>
                <th>Interpretación física / econométrica</th>
              </tr>
            </thead>
            <tbody>
              {"".join(corr_rows_html)}
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="section" id="jerarquia-distrital">
      <span class="badge badge-lime">Sección 4 · Lectura Territorial por Distrito</span>
      <h2>Jerarquía de Valor del Suelo por Distrito en el Ámbito Metropolitano (Malla 250 m)</h2>
      <p>Al cruzar espacialmente las 24,292 celdas de la malla continua con la división político-administrativa de distritos y nuevos municipios del AMSS ampliado, se obtiene una radiografía territorial homogénea y libre de sesgos por ausencia de trámites administrativos:</p>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Distrito</th>
              <th>Municipio Actual</th>
              <th>Celdas Totales</th>
              <th>Superficie Malla</th>
              <th>Celdas Urbanas Consolidadas</th>
              <th>Mediana Urbana Consolidada (USD/m²)</th>
              <th>Mediana Global Distrito (USD/m²)</th>
              <th>P90 Distrito (USD/m²)</th>
              <th>Máximo Celda (USD/m²)</th>
            </tr>
          </thead>
          <tbody>
            {"".join(dist_rows_html)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section" id="mejoras-metodologicas">
      <span class="badge badge-lime">Sección 5 · Hoja de Ruta de Refinamiento (Fase II)</span>
      <h2>Cómo Mejorar y Afinar la Metodología en Siguientes Iteraciones</h2>
      <p>Esta primera versión operativa demuestra la viabilidad técnica de estimar valores continuos del suelo combinando GeoAI satelital y datos locales sin saturar los límites computacionales de Google Earth Engine. Para evolucionar este prototipo hacia un <strong>observatorio fiscal, catastral y de captura de plusvalías de grado institucional</strong> en OPAMSS, se proponen <strong>siete líneas concretas de refinamiento metodológico</strong>:</p>

      <div class="grid-2" style="margin-top:0.9rem;">
        <article class="card" style="border-left:4px solid #0284C7;">
          <span class="badge badge-propuesta">Mejora 1 · Granularidad de Etiquetas</span>
          <h3>Entrenamiento con microdatos puntuales georreferenciados en lugar de polígonos UPD</h3>
          <p>Actualmente la variable objetivo se asigna pintando (<code>.paint()</code>) el promedio/mediana de cada UPD sobre su huella edificada, lo que introduce suavizado intrazonal en UPDs heterogéneas. Pasar a una muestra anonimizada de <strong>puntos exactos o manzanas de permisos OPAMSS, avalúos bancarios y ofertas verificadas</strong> (filtrando terreno puro vs. construcción vertical mediante el cociente área construida / área de lote) reducirá sustancialmente la dispersión intra-UPD y elevará el <code>R²</code> fuera de muestra.</p>
        </article>

        <article class="card" style="border-left:4px solid #DC2626;">
          <span class="badge badge-propuesta">Mejora 2 · Colas Superiores (&gt; $350/m²)</span>
          <h3>Corrección de compresión de extremos con Gradient Boosting y modelos bi-etápicos</h3>
          <p>Los bosques aleatorios promedian predicciones de hojas terminales y tienden a subestimar el top 5% corporativo (San Benito, Santa Elena, Paseo General Escalón). Se recomienda evaluar <code>ee.Classifier.smileGradientTreeBoost</code> con pérdida robusta Huber, o implementar una <strong>arquitectura en dos etapas (Hurdle / Regime-Switching)</strong>: un clasificador probabilístico de centralidad corporativa seguido de un regresor especializado calibrado para nodos de alta densidad vertical.</p>
        </article>

        <article class="card" style="border-left:4px solid #0F766E;">
          <span class="badge badge-propuesta">Mejora 3 · Accesibilidad y Normativa</span>
          <h3>Incorporación explícita de isócronas viales, distancias a corredores y zonificación OPAMSS</h3>
          <p>Dos terrenos con idéntica firma satelital tienen distinto valor si uno goza de frente comercial sobre un eje primario o mayor coeficiente de edificabilidad normativa. Integrar en el stack de GEE capas rasterizadas de <strong>distancia de costo/tiempo en red vial</strong> (OpenStreetMap / grafos viales hacia centros de empleo), proximidad a nuevos proyectos viales y <strong>parámetros normativos del Esquema Director de OPAMSS</strong> (usos permitidos, COS/CUS y zonas de protección ambiental) dotará al modelo de sensibilidad regulatoria directa.</p>
        </article>

        <article class="card" style="border-left:4px solid #7C3AED;">
          <span class="badge badge-propuesta">Mejora 4 · Rigor de Validación e Incertidumbre</span>
          <h3>Validación cruzada espacial por bloques (Spatial Block CV) e intervalos P10–P90</h3>
          <p>Debido a la fuerte autocorrelación espacial del precio del suelo (confirmada por los clusters LISA de Moran), una partición aleatoria estándar sobreestima la precisión real en zonas sin muestra. Implementar <strong>validación cruzada espacial bloqueada por distritos o bloques de 3 × 3 km</strong> permitirá medir con rigor la capacidad de transferencia hacia los 144 sectores imputados, acompañando cada celda de 250 m con un <strong>intervalo de predicción intercuartílico o P10–P90</strong> derivado de la dispersión entre los árboles individuales del ensamble.</p>
        </article>

        <article class="card" style="border-left:4px solid #D97706;">
          <span class="badge badge-propuesta">Mejora 5 · Econometría Espacial Híbrida</span>
          <h3>Regression-Kriging sobre residuales observados (RF + Kriging Ordinario)</h3>
          <p>En las 281 UPDs con datos observados conocemos exactamente el residual del modelo satelital (<code>e_i = ln(V_obs) − ln(V_RF)</code>), el cual captura externalidades intangibles como seguridad percibida, reputación histórica del barrio o micro-amenidades. Interpolar espacialmente estos residuales con un variograma de alcance corto (1.0–1.5 km) y sumarlos a la tendencia de Google Embeddings (<strong>Regression-Kriging</strong>) garantiza exactitud local en zonas muestreadas y convergencia suave al modelo satelital puro en zonas periféricas.</p>
        </article>

        <article class="card" style="border-left:4px solid #16A34A;">
          <span class="badge badge-propuesta">Mejora 6 · Dominio de Aplicabilidad (AOA)</span>
          <h3>Submodelos separados por régimen urbano/rural e Índice de Disimilitud</h3>
          <p>Las lógicas de formación de precios del suelo agrícola/forestal (productividad edáfica, pendiente, acceso a agua) difieren estructuralmente de las del suelo urbano (accesibilidad, densidad y servicios). Entrenar <strong>submodelos específicos para suelo urbano/periurbano frente a suelo rústico</strong> y calcular el <strong>Área de Aplicabilidad (AOA)</strong> de Meyer &amp; Pebesma en el hiperespacio de las 64 bandas de Embeddings permitirá señalizar cartográficamente las celdas de cumbre volcánica o costa donde el modelo opera en extrapolación.</p>
        </article>
      </div>

      <article class="card" style="margin-top:0.9rem;border-left:4px solid var(--c-brand-blue);">
        <span class="badge badge-lime">Mejora 7 · Monitoreo Multitemporal Anual (2018–2026)</span>
        <h3 style="margin:0.3rem 0 0.35rem;">Panel espacio-temporal de plusvalías con series anuales de Google Satellite Embeddings</h3>
        <p style="margin:0;">Dado que tanto <code>GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL</code> como <code>GOOGLE/Research/open-buildings-temporal/v1</code> y <code>NOAA/VIIRS/DNB/ANNUAL_V22</code> disponen de cortes anuales consistentes, el mismo clasificador calibrado (ajustado por deflactor inmobiliario anual) puede proyectarse retrospectivamente y hacia adelante año por año. Esto permitirá a OPAMSS construir un <strong>índice espacial de valorización anual a 250 m</strong> para medir objetivamente el impacto de obras públicas, aperturas viales y cambios de zonificación sobre el valor del suelo metropolitano.</p>
      </article>
    </section>

    <section class="section" id="codigo-gee">
      <span class="badge badge-lime">Sección 6 · Reproducibilidad en Google Earth Engine</span>
      <h2>Script Completo Optimizado de Google Earth Engine (<code>gee_modelo_valor_suelo_amss.js</code>)</h2>
      <p>El siguiente código fuente está diseñado específicamente bajo una arquitectura de <strong>cero sobrecarga de memoria en consola</strong> para evitar bloqueos en el Code Editor de Google Earth Engine y generar mediante exportación <em>Batch</em> los cinco productos oficiales del modelo:</p>

      <div class="callout" style="margin-bottom:0.85rem;">
        <strong>Instrucciones rápidas de ejecución en Google Earth Engine Code Editor</strong>
        <ol style="margin:0.35rem 0 0;padding-left:1.25rem;font-size:0.88rem;">
          <li>Verifica que los dos Assets base estén cargados en tu proyecto de GEE (o reemplaza las rutas en las líneas 26–27): <code>projects/ee-abnerjjimenez/assets/amss_upd_suelo_entrenamiento</code> y <code>projects/ee-abnerjjimenez/assets/amss_perimetro_oficial</code>.</li>
          <li>Haz clic en <strong>Copiar script GEE</strong> aquí abajo, pégalo en <code>https://code.earthengine.google.com/</code> y pulsa <strong>Run</strong>: el visor cargará de inmediato la superficie a nivel de píxel e inspector puntual sin saturar la consola.</li>
          <li>Abre la pestaña <strong>Tasks</strong> (esquina superior derecha) y ejecuta las 5 tareas de exportación hacia Google Drive (Malla Continua 250 m en GeoJSON y Shapefile, GeoTIFF COG a 20 m, 425 UPDs imputadas y CSV de correlaciones de las 71 bandas).</li>
        </ol>
      </div>

      <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:0.5rem;margin-bottom:0.5rem;">
        <div style="font-size:0.85rem;font-weight:700;color:var(--c-brand-blue);">Archivo: <code>src/gee_modelo_valor_suelo_amss.js</code> (570 líneas · Arquitectura Halo = 0)</div>
        <div style="display:flex;flex-wrap:wrap;gap:0.45rem;">
          <button type="button" class="btn btn-primary btn-xs" data-copy-target="gee-script-code">📋 Copiar script GEE al portapapeles</button>
          <a class="btn btn-teal btn-xs" href="{js_href}" download="gee_modelo_valor_suelo_amss.js">📥 Descargar archivo .js</a>
          <a class="btn btn-outline btn-xs" href="{gv_href}">🗺️ Ver salidas en el Geovisor →</a>
        </div>
      </div>

      <pre id="gee-script-code" class="code-block" style="max-height:560px;overflow:auto;font-size:0.78rem;line-height:1.45;"><code>{html.escape(gee_js_code)}</code></pre>
    </section>

    {render_project_institutions_band(ctx, branding, manifest, colaborar_href=colaborar_logos_href)}
    """

    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="Modelo Valor del Suelo (GEE): Metodología, Resultados y Script",
        active_nav="modelo-suelo",
        hero_html=hero,
        body_html=body,
    )


def render_copernicus_study_area_atlas_section(
    territory_label: str,
    initial_center: list[float],
    initial_zoom: float,
    ctx: SiteContext | None = None,
    pid: str = "zona-estudio",
) -> str:
    center_attr = html.escape(json.dumps(initial_center), quote=True)
    pdf_href = html.escape(
        ctx.site_url("assets/descargas/atlas_copernicus_zona_estudio.pdf") if ctx else "../assets/descargas/atlas_copernicus_zona_estudio.pdf",
        quote=True,
    )
    pdf_dl_name = f"Atlas_Copernicus_{pid}.pdf"
    plates_meta = [
        (
            "sentinel2-cloudless",
            "Lámina 1",
            "🛰️ 1. Mosaicos Anuales Sentinel-2 (2018–2024)",
            "Mosaicos Anuales sin Nubes Copernicus Sentinel-2 Cloudless (Serie 2018–2024 · 10 m)",
            "Compuestos ópticos anuales en color verdadero libres de nubes para comparar visualmente la evolución física urbana entre 2018 y 2024.",
            [
                ("sentinel2-2024", "2024"),
                ("sentinel2-2023", "2023"),
                ("sentinel2-2022", "2022"),
                ("sentinel2-2021", "2021"),
                ("sentinel2-2020", "2020"),
                ("sentinel2-2019", "2019"),
                ("sentinel2-2018", "2018 (Base)"),
            ],
            [
                ("#E8ECEF", "Blanco / Gris brillante", "Techos industriales, comerciales, concreto nuevo y cubiertas metálicas."),
                ("#9BA3AE", "Gris medio / Trama urbana", "Tejido residencial consolidado y red vial pavimentada."),
                ("#D29D6A", "Ocre / Terracota / Marrón", "Suelo desnudo en apertura urbana, taludes o techos de teja/lámina."),
                ("#1E5631", "Verde bosque oscuro", "Dosel arbóreo denso, bosques de galería en cañones y manglares."),
                ("#76B041", "Verde claro / Herbáceo", "Parques urbanos, pastizales y cultivos periurbanos."),
                ("#0F3A5D", "Azul marino / Turquesa", "Ríos principales, lagos, embalses y aguas costeras."),
            ],
        ),
        (
            "copernicus-dem-glo30",
            "Lámina 2",
            "⛰️ 2. Geomorfología y Pendientes (DEM 30 m)",
            "Copernicus DEM GLO-30 (30 m · Hipsometría, Hillshade y Curvas de Nivel)",
            "Identifica valles, terrazas aluviales, mesetas y cañones escarpados donde la expansión urbana enfrenta susceptibilidad a deslizamientos o escorrentía concentrada.",
            [
                ("copernicus-dem-glo30", "Hipsometría + Hillshade"),
                ("copernicus-dem-hillshade", "Solo Hillshade 30 m"),
                ("copernicus-dem-viridis", "Viridis + Curvas de Nivel"),
            ],
            [
                ("#336699", "0 – 150 m s. n. m.", "Planicies bajas, zonas costeras y llanuras de inundación."),
                ("#56A862", "150 – 500 m s. n. m.", "Terrazas aluviales y valles intramontanos de pendiente suave."),
                ("#E6C267", "500 – 1200 m s. n. m.", "Piedemonte, mesetas intermedias y laderas moderadas."),
                ("#A66A43", "> 1200 m s. n. m.", "Escarpes pronunciados, cordilleras y divisorias de cuenca."),
                ("#3A3F4B", "Sombreado Hillshade 30 m", "Barrancos, taludes y laderas de fuerte pendiente (>25%)."),
            ],
        ),
        (
            "esa-worldcover-2021",
            "Lámina 3",
            "🏙️ 3. Cobertura y Mancha Urbana 10 m (WorldCover)",
            "ESA WorldCover 10 m (Fusión Sentinel-1 + Sentinel-2 · Ediciones 2021 y 2020)",
            "Separa con resolución de 10 m la huella edificada e impermeable (#FA0000) de los bosques urbanos, pastizales, cultivos, manglares y cuerpos de agua.",
            [
                ("esa-worldcover-2021", "Año 2021 (v200)"),
                ("esa-worldcover-2020", "Año 2020 (v100)"),
            ],
            [
                ("#FA0000", "Edificado / Mancha Urbana", "Techos, pavimento vial, concreto y tejido urbano consolidado."),
                ("#006400", "Cobertura Arbórea", "Bosques urbanos, parques, bosques de galería y arbolado denso."),
                ("#FFBB22", "Arbustos y Matorral", "Vegetación leñosa baja y laderas en regeneración."),
                ("#FFFF4C", "Pastizales y Herbáceas", "Áreas verdes abiertas, lotes baldíos con pasto y praderas."),
                ("#F096FF", "Cultivos Agrícolas", "Borde agrourbano sujeto a presión por expansión residencial."),
                ("#B4B4B4", "Suelo Desnudo / Expuesto", "Terrenos en movimiento de tierra, taludes o trazados en apertura."),
                ("#0064C8", "Agua Permanente y Manglar", "Ríos, lagos, esteros (#0064C8) y manglares costeros (#00CF75)."),
            ],
        ),
        (
            "s2-lulc-2023",
            "Lámina 4",
            "📈 4. Uso del Suelo Anual 10 m (LULC 2017–2023)",
            "Serie Anual de Uso del Suelo y Expansión Urbana Sentinel-2 10 m (2017–2023)",
            "Permite medir año por año (2017 a 2023) el crecimiento del área construida consolidada (#C4281B) sobre suelos agrícolas, pastizales y bosques periurbanos.",
            [
                ("s2-lulc-2023", "2023"),
                ("s2-lulc-2022", "2022"),
                ("s2-lulc-2021", "2021"),
                ("s2-lulc-2020", "2020"),
                ("s2-lulc-2019", "2019"),
                ("s2-lulc-2018", "2018"),
                ("s2-lulc-2017", "2017 (Base)"),
            ],
            [
                ("#C4281B", "Área Construida (Built Area)", "Asentamientos humanos, tejido residencial, comercial e industrial."),
                ("#397D49", "Árboles y Bosque Denso", "Remanentes forestales y reservas ecológicas periurbanas."),
                ("#E49635", "Cultivos", "Superficie agrícola en transición urbano-rural."),
                ("#DFC35A", "Matorral / Rangeland", "Vegetación arbustiva y herbácea abierta."),
                ("#A59B8F", "Suelo Desnudo", "Superficies sin cobertura vegetal o en explanación."),
                ("#419BDF", "Agua y Humedales", "Cuerpos de agua (#419BDF) y vegetación inundable (#88B053)."),
            ],
        ),
        (
            "s2-l2a-ndvi",
            "Lámina 5",
            "🌿 5. Vegetación Urbana e Islas Verdes (NDVI)",
            "Copernicus Sentinel-2 L2A · Índice NDVI 10 m (Serie Multitemporal)",
            "Mide el vigor fotosintético ((B08-B04)/(B08+B04)) para localizar el déficit de áreas verdes intraurbanas y los corredores biológicos que mitigan islas de calor.",
            [
                ("s2-l2a-ndvi", "Reciente"),
                ("s2-l2a-ndvi-2024", "2024"),
                ("s2-l2a-ndvi-2023", "2023"),
                ("s2-l2a-ndvi-2022", "2022"),
                ("s2-l2a-ndvi-2021", "2021"),
                ("s2-l2a-ndvi-2020", "2020"),
                ("s2-l2a-ndvi-2019", "2019"),
                ("s2-l2a-ndvi-2018", "2018"),
            ],
            [
                ("#A50026", "NDVI < 0.05 (Rojo intenso)", "Techos, asfalto, concreto sellado o cuerpos de agua."),
                ("#F46D43", "NDVI 0.05 – 0.20 (Naranja)", "Tejido urbano denso con escaso o nulo arbolado viario."),
                ("#FEE08B", "NDVI 0.20 – 0.38 (Amarillo)", "Zonas residenciales mixtas con jardines dispersos o pasto seco."),
                ("#66BD63", "NDVI 0.38 – 0.60 (Verde claro)", "Parques urbanos, bulevares arbolados y huertos periurbanos."),
                ("#006837", "NDVI > 0.60 (Verde oscuro)", "Dosel forestal denso en cañones, riberas y áreas protegidas."),
            ],
        ),
        (
            "s2-l2a-ndbi",
            "Lámina 6",
            "🏗️ 6. Densidad Edificada e Impermeabilización (NDBI)",
            "Copernicus Sentinel-2 L2A · Índice NDBI 20 m (Serie Multitemporal)",
            "Evalúa la reflectancia en el infrarrojo de onda corta ((B11-B08)/(B11+B08)) para resaltar techos densos, concreto y suelo compactado.",
            [
                ("s2-l2a-ndbi", "Reciente"),
                ("s2-l2a-ndbi-2024", "2024"),
                ("s2-l2a-ndbi-2023", "2023"),
                ("s2-l2a-ndbi-2022", "2022"),
                ("s2-l2a-ndbi-2021", "2021"),
                ("s2-l2a-ndbi-2020", "2020"),
                ("s2-l2a-ndbi-2019", "2019"),
                ("s2-l2a-ndbi-2018", "2018"),
            ],
            [
                ("#FCFFA4", "NDBI > +0.15 (Amarillo claro)", "Alta concentración de techos metálicos/concreto, naves o suelo expuesto."),
                ("#F98E09", "NDBI 0.00 a +0.15 (Naranja)", "Tejido urbano consolidado con alta impermeabilización."),
                ("#AC2F5E", "NDBI -0.15 a 0.00 (Magenta)", "Zonas residenciales de densidad media con patios arborizados."),
                ("#1B0C41", "NDBI < -0.15 (Violeta/Negro)", "Cobertura vegetal densa y cuerpos de agua permeables."),
            ],
        ),
        (
            "s2-l2a-ndwi",
            "Lámina 7",
            "💧 7. Humedad Superficial y Estrés Térmico (NDWI)",
            "Copernicus Sentinel-2 L2A · Índice NDWI 20 m (Serie Multitemporal)",
            "Contrasta las zonas de retención hídrica y enfriamiento evaporativo (azul) frente a las superficies urbanas secas y calientes (rojo).",
            [
                ("s2-l2a-ndwi", "Reciente"),
                ("s2-l2a-ndwi-2024", "2024"),
                ("s2-l2a-ndwi-2023", "2023"),
                ("s2-l2a-ndwi-2022", "2022"),
                ("s2-l2a-ndwi-2021", "2021"),
                ("s2-l2a-ndwi-2020", "2020"),
                ("s2-l2a-ndwi-2019", "2019"),
                ("s2-l2a-ndwi-2018", "2018"),
            ],
            [
                ("#053061", "NDWI > +0.25 (Azul marino)", "Cuerpos de agua, humedales y riberas con alta humedad."),
                ("#4393C3", "NDWI +0.05 a +0.25 (Azul)", "Vegetación hidratada y suelos húmedos."),
                ("#F7F7F7", "NDWI -0.05 a +0.05 (Blanco)", "Humedad superficial intermedia."),
                ("#D6604D", "NDWI -0.20 a -0.05 (Salmón)", "Zonas urbanizadas secas o vegetación con estrés hídrico."),
                ("#67001F", "NDWI < -0.20 (Rojo oscuro)", "Superficies urbanas impermeables y secas con alta carga térmica."),
            ],
        ),
        (
            "s2-l2a-composites",
            "Lámina 8",
            "🔬 8. Falso Color Infrarrojo y SWIR Urbano (S2 L2A)",
            "Compuestos Multiespectrales Infrarrojo (B08-B04-B03) y SWIR Urbano (B12-B8A-B04)",
            "Combina las bandas VNIR y SWIR de Sentinel-2 L2A para discriminar techos, concreto y suelo expuesto frente al vigor vegetal y cuerpos de agua.",
            [
                ("s2-l2a-falsecolor", "IR B08-B04-B03 (Reciente)"),
                ("s2-l2a-falsecolor-2024", "IR 2024"),
                ("s2-l2a-falsecolor-2022", "IR 2022"),
                ("s2-l2a-falsecolor-2020", "IR 2020"),
                ("s2-l2a-swir", "SWIR Urbano (Reciente)"),
                ("s2-l2a-swir-2024", "SWIR 2024"),
                ("s2-l2a-swir-2022", "SWIR 2022"),
                ("s2-l2a-swir-2020", "SWIR 2020"),
            ],
            [
                ("#D32F2F", "Rojo escarlata (En modo IR)", "Vegetación vigorosa y bosques urbanos con alta reflectancia NIR (B08)."),
                ("#90CAF9", "Azul cian / Gris (En modo IR)", "Tejido urbano denso, techos, pavimento vial y concreto."),
                ("#BA68C8", "Magenta / Púrpura (En modo SWIR)", "Huella urbana consolidada y materiales de construcción en onda corta (B12)."),
                ("#2E7D32", "Verde esmeralda (En modo SWIR)", "Cobertura vegetal densa e hidratada."),
            ],
        ),
        (
            "s1-rtc-falsecolor",
            "Lámina 9",
            "📡 9. Morfología Urbana por Radar (Sentinel-1 SAR)",
            "Copernicus Sentinel-1 SAR RTC (10 m · Compuesto VV+VH y Polarización VV)",
            "Observación radar todo-tiempo (sin nubes): detecta construcciones por rebote doble (double-bounce) y distingue vegetación de láminas de agua.",
            [
                ("s1-rtc-falsecolor", "VV+VH Urbano (Reciente)"),
                ("s1-rtc-falsecolor-2024", "VV+VH 2024"),
                ("s1-rtc-falsecolor-2022", "VV+VH 2022"),
                ("s1-rtc-falsecolor-2020", "VV+VH 2020"),
                ("s1-rtc-vv", "Polarización VV (Grises)"),
                ("s1-rtc-vv-2024", "VV Grises 2024"),
                ("s1-rtc-vv-2020", "VV Grises 2020"),
            ],
            [
                ("#FFF59D", "Amarillo / Blanco brillante", "Rebote doble intenso: edificaciones densas, estructuras y taludes."),
                ("#4CAF50", "Verde intenso (Alto VH)", "Dispersión volumétrica en dosel arbóreo y vegetación rugosa."),
                ("#5C6BC0", "Azul / Añil intermedio", "Suelos agrícolas, pastizales bajos o superficies semirrugosas."),
                ("#0D1B2A", "Azul oscuro / Negro", "Espejos de agua calma (ríos, lagos, mar) o zonas urbanas anegadas."),
            ],
        ),
        (
            "jrc-gsw-occurrence",
            "Lámina 10",
            "🌊 10. Agua Superficial e Inundación (JRC)",
            "EC JRC / Copernicus Global Surface Water (Ocurrencia y Extensión Máxima)",
            "Muestra la frecuencia histórica de agua superficial e inundaciones (1984–2021) y la huella máxima de desbordamiento.",
            [
                ("jrc-gsw-occurrence", "Ocurrencia Histórica (0–100%)"),
                ("jrc-gsw-extent", "Extensión Máxima de Inundación"),
            ],
            [
                ("#0000FF", "80% – 100% Ocurrencia (Azul)", "Cauces permanentes de ríos, lagos, embalses y línea de costa."),
                ("#8844CC", "25% – 80% Ocurrencia (Violeta)", "Cuerpos de agua estacionales, esteros y barras fluviales."),
                ("#FF3366", "1% – 25% Ocurrencia (Rosa)", "Llanuras de inundación episódica durante eventos hidrometeorológicos."),
                ("#D9DFEA", "Relieve base emergido", "Terreno sin lámina de agua detectada a escala satelital."),
            ],
        ),
    ]

    tabs_html = []
    cards_html = []
    for idx, (pk, pnum, pshort, ptitle, preading, pvariants, pswatches) in enumerate(plates_meta):
        active_cls = " is-active" if idx == 0 else ""
        tabs_html.append(
            f'<button type="button" class="atlas-plate-tab{active_cls}" data-atlas-plate="{esc(pk)}">{esc(pshort)}</button>'
        )
        var_pills = "".join(
            f'<button type="button" class="atlas-variant-pill" data-atlas-plate-select="{esc(pk)}" data-atlas-variant-select="{esc(vk)}">{esc(vlbl)}</button>'
            for vk, vlbl in pvariants
        )
        sw_rows = "".join(
            f'<li class="atlas-swatch-item">'
            f'<span class="atlas-swatch-chip" style="background:{esc(c)};"></span>'
            f'<span class="atlas-swatch-label">{esc(lbl)}</span>'
            f'<span class="atlas-swatch-desc">{esc(d)}</span>'
            f"</li>"
            for c, lbl, d in pswatches
        )
        cards_html.append(
            f"""
            <article class="card" style="border-top:3px solid var(--c-brand-blue);display:flex;flex-direction:column;justify-content:space-between;">
              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;gap:0.4rem;margin-bottom:0.4rem;">
                  <span class="badge badge-lime">{esc(pnum)} · {len(pvariants)} capas/años</span>
                  <button type="button" class="btn btn-teal btn-xs" data-atlas-plate-select="{esc(pk)}">Ver lámina en el mapa ↑</button>
                </div>
                <h3 style="margin:0.2rem 0 0.4rem;font-size:1.02rem;color:var(--c-brand-blue);">{esc(ptitle)}</h3>
                <p style="font-size:0.86rem;color:var(--c-text-muted);margin-bottom:0.55rem;">{esc(preading)}</p>
                <div class="atlas-variant-box" style="margin-bottom:0.65rem;">
                  <div class="atlas-variant-box-label"><span>📅 Años / Capas disponibles (clic para cargar en el mapa):</span></div>
                  <div class="atlas-variant-pills">{var_pills}</div>
                </div>
                <ul class="atlas-swatch-list">{sw_rows}</ul>
              </div>
            </article>
            """
        )

    return f"""
    <section class="section" id="atlas-copernicus-zona" aria-labelledby="titulo-atlas-copernicus">
      <div class="section-header" style="margin-bottom:0.75rem;">
        <div>
          <span class="badge badge-lime">Cartografía Temática Enmascarada · 10 Láminas y Series Anuales Completas</span>
          <h2 id="titulo-atlas-copernicus" style="margin:0.3rem 0 0.2rem;">Atlas Temático Copernicus de la Zona de Estudio ({esc(territory_label)})</h2>
          <p style="margin:0;color:var(--c-text-muted);font-size:0.93rem;">Explora las <strong>10 láminas temáticas y todas las series multitemporales anuales (Mosaicos Sentinel-2 2018–2024, DEM GLO-30 en 3 modos, ESA WorldCover 2020–2021, Uso del Suelo LULC 2017–2023, Índices NDVI/NDBI/NDWI, Infrarrojo/SWIR, Radar Sentinel-1 y Agua JRC)</strong> recortadas visualmente con el perímetro de <strong>{esc(territory_label)}</strong>.</p>
        </div>
      </div>

      <div class="atlas-pdf-banner" role="region" aria-label="Descarga del Atlas Institucional en PDF">
        <div class="atlas-pdf-banner-inner">
          <div class="atlas-pdf-banner-text">
            <span class="atlas-pdf-banner-eyebrow">📘 Edición Editorial A4 Horizontal · Identidad Institucional 2.0.0-copernicus-2026</span>
            <h3 class="atlas-pdf-banner-title">Documento Oficial del Atlas Temático Copernicus para Descargar en PDF ({esc(territory_label)})</h3>
            <p class="atlas-pdf-banner-desc">Incluye portada institucional con trama cartográfica y logos oficiales, ficha técnica e índice, las <strong>10 láminas temáticas principales</strong> y las <strong>páginas de series multitemporales completas con todos los años y modos (2017–2024)</strong> recortadas con el límite de <strong>{esc(territory_label)}</strong> y sus leyendas cromáticas hexadecimales.</p>
          </div>
          <div class="atlas-pdf-banner-actions">
            <a class="btn btn-primary" href="{pdf_href}" download="{esc(pdf_dl_name)}">📥 Descargar Atlas Institucional Completo (PDF · 22 Págs. · 60 capas)</a>
            <button type="button" class="btn btn-teal" data-atlas-export-pdf>🖨️ Exportar lámina / año actual a PDF</button>
            <a class="btn btn-outline-light btn-xs" href="{pdf_href}" target="_blank" rel="noopener noreferrer">Abrir PDF en pestaña ↗</a>
          </div>
        </div>
      </div>

      <div class="atlas-plate-tabs" role="tablist" aria-label="Láminas temáticas del Atlas Copernicus">
        {"".join(tabs_html)}
      </div>

      <div class="atlas-copernicus-shell">
        <div class="atlas-copernicus-map-col">
          <div class="geovisor-toolbar" style="border-radius:0;">
            <div style="display:flex;flex-wrap:wrap;align-items:center;gap:0.5rem;">
              <strong id="atlas-toolbar-plate-label" style="font-size:0.82rem;color:var(--c-accent-yellow);">🛰️ 1. Mosaicos Anuales Sentinel-2 (2018–2024)</strong>
              <label style="display:inline-flex;align-items:center;gap:0.3rem;font-size:0.76rem;color:#FFFFFF;">
                <span>Año / Capa:</span>
                <select id="atlas-toolbar-variant-select" class="atlas-toolbar-select" aria-label="Seleccionar año o variante de la lámina en la barra del mapa"></select>
              </label>
              <button type="button" id="atlas-toolbar-play-btn" class="atlas-play-btn" title="Reproducir o pausar secuencia multitemporal animada">▶ Reproducir serie</button>
              <label style="display:inline-flex;align-items:center;gap:0.35rem;font-size:0.76rem;background:rgba(255,255,255,0.12);padding:0.2rem 0.48rem;border-radius:4px;cursor:pointer;">
                <input type="checkbox" id="atlas-toggle-mask" checked>
                <span>Enmascarar límite</span>
              </label>
              <label style="display:inline-flex;align-items:center;gap:0.3rem;font-size:0.74rem;">
                <span>Opacidad:</span>
                <input type="range" id="atlas-mask-opacity" min="0" max="1" step="0.05" value="0.88" style="width:68px;" aria-label="Opacidad de la máscara del límite">
              </label>
            </div>
            <div class="geovisor-toolbar-actions">
              <a class="btn btn-primary btn-xs" href="{pdf_href}" download="{esc(pdf_dl_name)}" title="Descargar el Atlas completo (10 láminas + series multitemporales) en PDF">📥 Descargar Atlas PDF</a>
              <button type="button" class="btn btn-outline-light btn-xs" data-atlas-export-pdf title="Exportar la lámina y año actuales en formato A4 Horizontal institucional">🖨️ Lámina a PDF</button>
              <button type="button" id="atlas-fit-bounds" class="btn btn-outline-light btn-xs">Encuadrar límite</button>
              <button type="button" id="atlas-toggle-fullscreen" class="btn btn-outline-light btn-xs">⛶ Pantalla completa</button>
            </div>
          </div>
          <div class="atlas-map-stage">
            <div id="atlas-map-year-badge" class="atlas-map-year-badge" aria-live="polite">
              <span id="atlas-map-year-top" class="atlas-map-year-badge-top">SERIE MULTITEMPORAL (7/7)</span>
              <span id="atlas-map-year-main" class="atlas-map-year-badge-main">2024</span>
            </div>
            <div id="atlas-copernicus-map" class="atlas-copernicus-canvas" data-center="{center_attr}" data-zoom="{initial_zoom}" role="region" aria-label="Mapa del Atlas Temático Copernicus enmascarado con la zona de estudio"></div>
          </div>
        </div>

        <div class="atlas-copernicus-info-col" id="atlas-plate-detail">
          <div>
            <span id="atlas-plate-badge" class="badge badge-lime">Lámina 1 · 2024</span>
            <h3 id="atlas-plate-title" style="margin:0.35rem 0 0.25rem;font-size:1.1rem;color:var(--c-brand-blue);">Mosaico Anual sin Nubes Copernicus Sentinel-2 Cloudless · Año 2024 (10 m)</h3>
            <p style="margin:0;font-size:0.8rem;color:var(--c-text-muted);"><strong>Sensor / Fuente:</strong> <span id="atlas-plate-sensor">Copernicus Sentinel-2 MSI · Mosaicos anuales sin nubes (10 m)</span></p>
            <p style="margin:0.15rem 0 0;font-size:0.78rem;color:var(--c-text-muted);"><strong>Parámetro / Expresión:</strong> <code id="atlas-plate-formula">Compuesto anual óptico en Color Verdadero RGB (B04-B03-B02)</code></p>
          </div>

          <div class="atlas-variant-box">
            <label for="atlas-panel-variant-select" id="atlas-variant-selector-label" class="atlas-variant-box-label">📅 Seleccionar año o variante de la capa:</label>
            <select id="atlas-panel-variant-select" class="atlas-variant-select" aria-label="Selector desplegable de año o capa del tema"></select>
            <div id="atlas-variant-pills" class="atlas-variant-pills" role="group" aria-label="Botones rápidos de año o variante"></div>
            <div id="atlas-timeline-controls" class="atlas-timeline-controls" aria-label="Controles de animación multitemporal">
              <div class="atlas-timeline-row">
                <button type="button" id="atlas-panel-play-btn" class="atlas-play-btn">▶ Reproducir secuencia</button>
                <button type="button" id="atlas-step-prev" class="atlas-step-btn" title="Año anterior">⏮ Ant.</button>
                <button type="button" id="atlas-step-next" class="atlas-step-btn" title="Año siguiente">Sig. ⏭</button>
                <select id="atlas-play-speed" class="atlas-speed-select" aria-label="Velocidad de la animación">
                  <option value="2800">Lento (2.8 s)</option>
                  <option value="1800" selected>Normal (1.8 s)</option>
                  <option value="1000">Rápido (1.0 s)</option>
                </select>
              </div>
              <div class="atlas-timeline-row" style="gap:0.5rem;">
                <input type="range" id="atlas-timeline-slider" min="0" max="6" step="1" value="6" style="flex:1;" aria-label="Deslizador de línea de tiempo">
                <span id="atlas-timeline-counter" style="font-size:0.74rem;font-weight:700;color:var(--c-brand-blue);min-width:44px;text-align:right;">7 / 7</span>
              </div>
            </div>
          </div>

          <div style="background:#F3F6FD;border-left:3px solid var(--c-brand-blue);padding:0.65rem 0.8rem;border-radius:4px;font-size:0.85rem;line-height:1.45;">
            <strong style="color:var(--c-brand-blue);display:block;margin-bottom:0.2rem;">Lectura e interpretación territorial en {esc(territory_label)}:</strong>
            <span id="atlas-plate-reading">Permite inspeccionar visualmente la evolución física del territorio año por año entre 2018 y 2024.</span>
          </div>

          <div>
            <h4 style="margin:0 0 0.45rem;font-size:0.86rem;text-transform:uppercase;letter-spacing:0.03em;color:var(--c-brand-blue);">Guía de interpretación de los colores de la leyenda</h4>
            <ul id="atlas-plate-swatches" class="atlas-swatch-list"></ul>
          </div>

          <div style="display:flex;flex-wrap:wrap;gap:0.45rem;padding-top:0.5rem;border-top:1px solid var(--c-border);">
            <a class="btn btn-primary btn-xs" href="{pdf_href}" download="{esc(pdf_dl_name)}">📥 Descargar Atlas Completo (PDF)</a>
            <button type="button" class="btn btn-teal btn-xs" data-atlas-export-pdf>🖨️ Exportar esta lámina y año a PDF</button>
          </div>
        </div>
      </div>

      <div style="margin-top:1.4rem;">
        <h3 style="margin:0 0 0.4rem;color:var(--c-brand-blue);">Catálogo completo de las 10 Láminas, Selectores Anuales y Leyendas Cromáticas</h3>
        <p style="margin:0 0 0.9rem;font-size:0.88rem;color:var(--c-text-muted);">Haz clic en cualquier <strong>año o modo</strong> dentro de las tarjetas inferiores (o en <strong>Ver lámina en el mapa ↑</strong>) para cargarlo directamente en el visor superior con el límite de la zona de estudio:</p>
        <div class="grid-2">
          {"".join(cards_html)}
        </div>
      </div>
    </section>
    """


def build_resultados_page(
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    atlas_products: list[dict[str, Any]],
    continuidad_md: str,
    branding: dict[str, Any],
    layers_cfg: dict[str, Any] | None = None,
) -> str:
    outputs_li = "".join(f"<li>{esc(o)}</li>" for o in manifest.get("expected_outputs", [])) or "<li>Productos esperados por detallar.</li>"

    atlas_cards = []
    for ap in atlas_products:
        ind = ap.get("indicator", {})
        cov = ap.get("coverage", {})
        outs = ap.get("outputs", {})
        viewer_btn = render_link_or_pending(outs.get("viewer_url"), "Abrir visor del producto", "Visor del producto aún no publicado")
        dl_btn = render_link_or_pending(outs.get("download_url"), "Descargar datos", "Descarga pendiente de publicación")
        atlas_cards.append(
            f"""
            <article class="card">
              <div style="display:flex;flex-wrap:wrap;gap:0.4rem;">
                {badge_html(ap.get('publication_status'), 'Publicación')}
                {badge_html(ap.get('validation', {}).get('state'), 'Validación')}
                <span class="badge badge-country">Tipo: {esc(ap.get('product_type'))}</span>
              </div>
              <h3>{esc(ap['title'])}</h3>
              <p>{esc(ap['summary'])}</p>
              <div class="table-wrap">
                <table>
                  <tbody>
                    <tr><th>ID de producto Atlas</th><td><code>{esc(ap['id'])}</code></td></tr>
                    <tr><th>Cobertura y resolución</th><td>{esc(cov.get('label'))} · Resolución: {esc(cov.get('spatial_resolution'), 'Por confirmar')}</td></tr>
                    <tr><th>Indicador y unidad</th><td>{esc(ind.get('name'), 'Por definir')} ({esc(ind.get('unit'), 'unidad por definir')})</td></tr>
                    <tr><th>Definición y agregación</th><td>{esc(ind.get('definition'), '—')} · Agregación: {esc(ind.get('aggregation'), '—')}</td></tr>
                    <tr><th>Institución custodia</th><td>{esc(ap.get('governance', {}).get('institution'), 'Por confirmar')}</td></tr>
                    <tr><th>Condición de reutilización</th><td>{esc(ap.get('license', {}).get('reuse_note'), 'Condiciones de reutilización por confirmar')}</td></tr>
                  </tbody>
                </table>
              </div>
              <div class="card-footer">
                {viewer_btn}
                {dl_btn}
              </div>
            </article>
            """
        )

    colaborar_logos_href = ctx.site_url("colaborar/") + "#anadir-actualizar-logos"

    figuras_dir = ROOT / "web" / "assets" / "img" / "figuras"
    figuras_html = ""
    if figuras_dir.is_dir():
        fig_files = sorted(
            f for f in figuras_dir.iterdir()
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".webp")
        )
        if fig_files:
            fig_cards = []
            for ff in fig_files:
                f_url = html.escape(ctx.site_url(f"assets/img/figuras/{ff.name}"), quote=True)
                f_label = esc(ff.stem.replace("_", " ").capitalize())
                fig_cards.append(
                    f"""
                    <article class="card">
                      <span class="badge badge-ok">Evidencia gráfica del repositorio</span>
                      <h3 style="margin:0.35rem 0 0.5rem;font-size:1rem;">{f_label}</h3>
                      <a href="{f_url}" target="_blank" rel="noopener noreferrer" style="display:block;border:1px solid var(--c-border);border-radius:8px;overflow:hidden;background:#070A14;">
                        <img src="{f_url}" alt="{f_label}" style="width:100%;height:auto;display:block;" loading="lazy">
                      </a>
                    </article>
                    """
                )
            figuras_html = f"""
            <section class="section">
              <h2>Figuras y visualizaciones analíticas incorporadas por el equipo</h2>
              <p>Gráficos y salidas analíticas generadas a partir de los scripts del proyecto en <code>src/</code> y almacenadas en <code>web/assets/img/figuras/</code>:</p>
              <div class="grid-2">{"".join(fig_cards)}</div>
            </section>
            """

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Evidencias y Atlas Urbano Regional</span>
          <span class="badge badge-country">{esc(manifest['id'])}</span>
        </div>
        <h1>Resultados disponibles, productos esperados y aporte al Atlas</h1>
        <p class="hero-lead">Separación explícita entre insumos/evidencias documentales existentes y productos comprometidos como meta del PMV en {esc(manifest['territory']['label'])}.</p>
      </div>
    </section>
    """

    mv = (layers_cfg or {}).get("map_view", {})
    initial_center = mv.get("initial_center", [-84.0, 10.0])
    initial_zoom = float(mv.get("initial_zoom", 12))
    atlas_copernicus_section = render_copernicus_study_area_atlas_section(
        territory_label=manifest["territory"]["label"],
        initial_center=initial_center,
        initial_zoom=initial_zoom,
        ctx=ctx,
        pid=manifest["id"],
    )

    body = f"""
    {render_status_strip(manifest)}

    {atlas_copernicus_section}

    <section class="section">
      <div class="grid-2">
        <article class="card">
          <span class="badge badge-declarado">Según el perfil</span>
          <h3>Productos y entregables esperados</h3>
          <ul>{outputs_li}</ul>
        </article>
        <article class="card">
          <span class="badge badge-pendiente">Verificación independiente</span>
          <h3>Estado de evidencias operativas</h3>
          <p><strong>Revisión técnica:</strong> {esc(manifest['status']['technical_review']['state'])} (revisor: {esc(manifest['status']['technical_review'].get('reviewer'), 'pendiente')}).</p>
          <p><strong>Validación institucional:</strong> {esc(manifest['status']['institutional_validation']['state'])} (referente: {esc(manifest['status']['institutional_validation'].get('reviewer'), 'pendiente')}).</p>
          <p><strong>Adopción institucional:</strong> {esc(manifest['status']['adoption']['state'])}.</p>
          <p style="font-size:0.86rem;color:var(--c-text-muted);">Para cambiar cualquiera de estos estados a <em>validado</em> o <em>uso documentado</em>, el esquema exige registrar fecha, persona revisora y URL HTTPS de evidencia verificable.</p>
        </article>
      </div>
    </section>

    <section class="section">
      <h2>Contribución prevista al Atlas Urbano Regional</h2>
      <p>Metadatos estructurados en <code>atlas/products/</code> conforme a <code>atlas-product.schema.json</code>:</p>
      {"".join(atlas_cards) if atlas_cards else "<p>Sin fichas de Atlas registradas todavía.</p>"}
    </section>

    {figuras_html}

    <section class="section">
      <div class="prose">
        {render_markdown(continuidad_md)}
      </div>
    </section>

    {render_project_institutions_band(ctx, branding, manifest, colaborar_href=colaborar_logos_href)}
    """

    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="Resultados y Atlas Copernicus",
        active_nav="resultados",
        hero_html=hero,
        body_html=body,
        include_maplibre=True,
    )


def build_colaborar_page(
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    branding: dict[str, Any],
) -> str:
    pid = manifest["id"]
    proposed_owner = repo_cfg.get("proposed_owner", "copernicuscentroamerica")
    proposed_repo = repo_cfg.get("proposed_repository", f"urbano-{pid}")
    confirmed_repo_url = manifest["links"].get("repository")
    canonical_slug = (
        ctx.canonical_repository
        if ctx.canonical_repository
        else f"{proposed_owner}/{proposed_repo}"
    )
    effective_slug = ctx.github_repository or canonical_slug
    repo_status_note = (
        f"Repositorio canónico verificado: <code>{esc(canonical_slug)}</code>."
        if confirmed_repo_url
        else f"Nombre propuesto sujeto a aprovisionamiento: <code>{esc(canonical_slug)}</code> (sustituye el propietario si se aloja en otra organización)."
    )

    issue_btn = render_link_or_pending(
        manifest["links"].get("issue_tracker"),
        "Abrir Issues del repositorio",
        "Formularios listos en .github/ISSUE_TEMPLATE/ (se activan al publicar el repo)",
        "btn btn-teal",
    )

    fork_cmds = f"""# 1. Crear fork personal en tu cuenta de GitHub y clonarlo localmente
gh repo fork {canonical_slug} --clone=false
git clone https://github.com/TU_USUARIO_GITHUB/{proposed_repo}.git
cd {proposed_repo}

# 2. Registrar el repositorio canónico como upstream (NO usar el portal general como upstream)
git remote add upstream https://github.com/{canonical_slug}.git
git remote -v
git fetch upstream
git switch -c feat/nueva-capa-geovisor upstream/main"""

    validate_cmds = f"""# 3. Validar fuentes, construir el sitio y comprobar enlaces internos
python3 scripts/validate.py --source
python3 scripts/build_site.py --output site
python3 scripts/validate.py --site site

# 4. Previsualizar localmente en http://localhost:8000
python3 -m http.server 8000 --directory site"""

    pr_cmds = f"""# 5. Confirmar solo los archivos modificados y enviar Pull Request al canónico
git status --short
git add project.json content/ geovisor/ branding/
git commit -m "Actualiza avances y recursos verificados de {pid}"
git push -u origin feat/nueva-capa-geovisor

gh pr create --repo {canonical_slug} --base main --head TU_USUARIO_GITHUB:feat/nueva-capa-geovisor --title "Actualiza geovisor, logos o documentación ({pid})" --body-file pr-body.md"""

    antigravity_logo_prompt = f"""He copiado los archivos de logos de las instituciones participantes del proyecto {pid} ({manifest['title']}) en la carpeta branding/logos/ de este repositorio.
Por favor:
1. Inspecciona los archivos nuevos dentro de branding/logos/ (comprueba que sean .svg o .png con proporciones naturales y peso menor a 2 MB).
2. Actualiza branding/project-branding.json conservando intacto "project_id": "{pid}" y "theme_version": "{THEME_VERSION}", y registrando cada institución en la lista "institutions" con su "id", "name", "acronym", "role", "logo_path", "alt_text" descriptivo, "url" (si aplica con https://), "order" y "aspect_hint" ("horizontal", "vertical" o "square").
3. Ejecuta python scripts/validate.py --source, python scripts/build_site.py --output site y python scripts/validate.py --site site para confirmar que toda la validación pasa sin errores.
4. Muéstrame git status y git diff branding/project-branding.json y deja lista una rama feat/logos-institucionales para enviar el Pull Request al repositorio {canonical_slug}."""

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Colaboración GitHub, Logos y GeoLibre</span>
          <span class="badge badge-country">{esc(pid)}</span>
        </div>
        <h1>Cómo colaborar en esta iniciativa (Fork, Capas, Logos y PR)</h1>
        <p class="hero-lead">Cada iniciativa evoluciona en su propio repositorio independiente. Las personas participantes trabajan en ramas de su fork personal y proponen mejoras, capas geoespaciales o logos institucionales mediante Pull Request.</p>
        <div class="hero-actions">
          <a class="btn btn-primary" href="#anadir-actualizar-logos">Añadir o actualizar logos</a>
          <a class="btn btn-outline-light" href="#ejercicio-practico">Ejercicio práctico Colab / GEE</a>
        </div>
      </div>
    </section>
    """

    hub_base = (ctx.hub_url or "https://copernicuscentroamerica.github.io/clusterurbano/").rstrip("/")
    ejercicio_url = f"{hub_base}/ejercicio/"
    repo_url = (confirmed_repo_url or f"https://github.com/{canonical_slug}").rstrip("/")
    effective_repo_url = f"https://github.com/{effective_slug}"
    gh_logos_dir_url = f"{effective_repo_url}/tree/main/branding/logos"
    gh_branding_json_url = f"{effective_repo_url}/blob/main/branding/project-branding.json"
    gh_guide_doc_url = f"{effective_repo_url}/blob/main/docs/identidad-visual.md"

    body = f"""
    <div class="callout">
      <strong>Identidad del repositorio de esta iniciativa</strong>
      <span>{repo_status_note} El identificador <code>{esc(pid)}</code> debe permanecer intacto en <code>project.json</code> y en <code>branding/project-branding.json</code> incluso cuando trabajes en un fork personal.</span>
    </div>

    <section class="section" id="anadir-actualizar-logos">
      <article class="card" style="border-top:4px solid var(--c-accent-yellow);">
        <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:0.75rem;">
          <div>
            <span class="badge badge-lime">Identidad local del proyecto</span>
            <h2 style="margin:0.35rem 0 0.2rem;color:var(--c-brand-blue);">Añadir o actualizar logos</h2>
            <p style="margin:0;font-size:0.92rem;color:var(--c-text-muted);">Procedimiento oficial para incorporar el logo del proyecto y los logos de las instituciones participantes en <code>{esc(pid)}</code> sin alterar el tema común.</p>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:0.5rem;">
            <a class="btn btn-teal btn-xs" href="{html.escape(gh_logos_dir_url, quote=True)}" target="_blank" rel="noopener noreferrer">Abrir carpeta branding/logos/ ↗</a>
            <a class="btn btn-outline btn-xs" href="{html.escape(gh_branding_json_url, quote=True)}" target="_blank" rel="noopener noreferrer">Editar branding/project-branding.json ↗</a>
            <a class="btn btn-outline btn-xs" href="{html.escape(gh_guide_doc_url, quote=True)}" target="_blank" rel="noopener noreferrer">Guía docs/identidad-visual.md ↗</a>
          </div>
        </div>

        <div class="grid-2" style="margin-top:0.85rem;">
          <div>
            <h3>Pasos para el equipo de la iniciativa</h3>
            <ol style="padding-left:1.25rem;line-height:1.65;">
              <li><strong>Abre el repositorio de tu iniciativa:</strong> trabaja sobre tu copia local clonada desde tu fork personal o abre el repositorio en GitHub.</li>
              <li><strong>Añade el archivo del logo a <code>branding/logos/</code>:</strong> prefiere formato <code>.svg</code> original o <code>.png</code> con fondo transparente (máximo 2 MB), conservando colores y proporciones oficiales.</li>
              <li><strong>Completa los datos en <code>branding/project-branding.json</code>:</strong> registra el nombre oficial (<code>name</code>), sigla (<code>acronym</code>), rol documentado (<code>role</code>), ruta (<code>logo_path</code>), texto alternativo (<code>alt_text</code>), enlace opcional (<code>url</code> con <code>https://</code>) y orden (<code>order</code>). Si una institución aún no tiene archivo de logo, deja <code>"logo_path": null</code> (nunca inventes logos con IA).</li>
              <li><strong>Comprueba la vista previa local:</strong> ejecuta <code>python3 scripts/validate.py --source</code> y <code>python3 scripts/build_site.py --output site</code>.</li>
              <li><strong>Presenta el cambio mediante una rama y un Pull Request:</strong> sube tu rama (por ejemplo, <code>feat/logos-institucionales</code>) y abre el Pull Request hacia <code>{esc(canonical_slug)}</code>.</li>
              <li><strong>Publicación tras revisión:</strong> al integrarse el PR, el sitio reconstruido de la iniciativa y la ficha del proyecto en el portal regional muestran los logos aprobados.</li>
            </ol>
          </div>

          <div>
            <h3>Prompt para Antigravity (sin editar JSON manualmente)</h3>
            <p style="font-size:0.88rem;color:var(--c-text-muted);">Coloca tus archivos de imagen en <code>branding/logos/</code> y pega esta instrucción en el chat de Antigravity para que prepare y valide toda la configuración automáticamente:</p>
            <pre id="prompt-antigravity-logos" class="code-block"><code>{html.escape(antigravity_logo_prompt)}</code></pre>
            <div style="margin-top:0.65rem;">
              <button type="button" class="btn btn-primary btn-xs" data-copy-target="prompt-antigravity-logos">Copiar prompt para Antigravity</button>
            </div>
          </div>
        </div>

        <div class="card" style="margin-top:1rem;background:#F8FAFF;" data-logo-preview-helper>
          <h3 style="margin-top:0;">Previsualizador local de logo y asistente de configuración JSON</h3>
          <div class="callout callout-warn" style="margin:0.25rem 0 0.85rem;">
            <strong>Importante sobre el funcionamiento de esta previsualización en el navegador</strong>
            <ul style="margin:0.35rem 0 0;padding-left:1.2rem;font-size:0.85rem;">
              <li><strong>Seleccionar y previsualizar un archivo local aquí no significa que ya esté publicado</strong> en el sitio oficial ni en GitHub.</li>
              <li>Esta herramienta permite comprobar las proporciones del logo en su tarjeta y <strong>descargar o copiar el bloque JSON preparado</strong> para incorporarlo en <code>branding/project-branding.json</code>.</li>
              <li>La publicación permanente debe seguir siempre el mecanismo de escritura autenticado y revisión del repositorio (commit en rama + Pull Request).</li>
              <li>Este sitio público es estático y <strong>no contiene ni solicita credenciales de escritura</strong>.</li>
            </ul>
          </div>

          <div class="grid-2">
            <div style="display:flex;flex-direction:column;gap:0.65rem;">
              <div class="filter-field">
                <label for="logo-file-inp">1. Seleccionar archivo local (.svg o .png) para previsualizar</label>
                <input id="logo-file-inp" type="file" accept=".svg,.png,.webp,.jpg,.jpeg,image/svg+xml,image/png" data-logo-file-input>
              </div>
              <div class="filter-field">
                <label for="logo-inst-name">2. Nombre oficial de la institución</label>
                <input id="logo-inst-name" type="text" placeholder="Ej. Ministerio de Vivienda y Ordenamiento Territorial" value="{esc((manifest['institutional_use'].get('institutions') or ['Institución participante'])[0])}" data-logo-inst-name>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.65rem;">
                <div class="filter-field">
                  <label for="logo-inst-acr">Sigla (opcional)</label>
                  <input id="logo-inst-acr" type="text" placeholder="Ej. MIVIOT" data-logo-inst-acronym>
                </div>
                <div class="filter-field">
                  <label for="logo-inst-ord">Orden de presentación</label>
                  <input id="logo-inst-ord" type="number" min="1" max="50" value="1" data-logo-inst-order>
                </div>
              </div>
              <div class="filter-field">
                <label for="logo-inst-role">Rol o agrupación documentada</label>
                <input id="logo-inst-role" type="text" value="Institución participante del proyecto" data-logo-inst-role>
              </div>
              <div class="filter-field">
                <label for="logo-inst-url">Enlace institucional opcional (https://...)</label>
                <input id="logo-inst-url" type="url" placeholder="https://..." data-logo-inst-url>
              </div>
            </div>

            <div style="display:flex;flex-direction:column;gap:0.75rem;">
              <div>
                <strong style="font-size:0.82rem;color:var(--c-brand-blue);display:block;margin-bottom:0.35rem;">Vista previa local de la tarjeta institucional:</strong>
                <div class="inst-proyecto-card" style="display:flex;align-items:center;gap:0.75rem;padding:0.65rem 0.85rem;background:#F9FAFE;border:1px solid #D5DDF0;border-radius:8px;">
                  <div class="inst-proyecto-logo-box is-horizontal" data-logo-preview-box style="height:48px;min-width:72px;max-width:130px;display:flex;align-items:center;justify-content:center;padding:0.25rem 0.5rem;background:#FFFFFF;border:1px solid #E4EAF7;border-radius:6px;flex-shrink:0;">
                    <img src="{html.escape(ctx.site_url('assets/img/brand/logo-copernicus-lac-chile.png'), quote=True)}" alt="Previsualización local del logo seleccionado" height="36" style="max-height:36px;max-width:118px;width:auto;height:auto;object-fit:contain;display:block;" data-logo-preview-img>
                  </div>
                  <div style="min-width:0;">
                    <div class="inst-proyecto-text-head" style="margin-bottom:0.2rem;">
                      <span class="inst-proyecto-acronym hidden" data-logo-preview-acronym>SIGLA</span>
                    </div>
                    <p class="inst-proyecto-name" data-logo-preview-name>{esc((manifest['institutional_use'].get('institutions') or ['Institución participante'])[0])}</p>
                    <p class="inst-proyecto-role" data-logo-preview-role>Institución participante del proyecto</p>
                  </div>
                </div>
              </div>

              <div>
                <strong style="font-size:0.82rem;color:var(--c-brand-blue);display:block;margin-bottom:0.35rem;">Entrada generada para <code>branding/project-branding.json</code>:</strong>
                <pre id="logo-json-snippet" class="code-block" style="margin:0;"><code data-logo-json-output></code></pre>
                <div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-top:0.55rem;">
                  <button type="button" class="btn btn-outline btn-xs" data-copy-target="logo-json-snippet">Copiar bloque JSON</button>
                  <button type="button" class="btn btn-teal btn-xs" data-logo-download-json>Descargar bloque (.json)</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </article>
    </section>

    <section class="section" id="ejercicio-practico">
      <article class="card" style="border-left:4px solid var(--c-brand-blue);">
        <span class="badge badge-ok">Ejercicio guiado de extremo a extremo</span>
        <h2>Ejercicio práctico: Mancha Urbana con Sentinel-2 (Google Colab + Google Earth Engine + Antigravity)</h2>
        <p>¿Es tu primera vez contribuyendo al proyecto? En el portal regional dispones de un ejercicio completo paso a paso para clasificar el área construida (<em>built-up</em>) con imágenes <strong>Copernicus Sentinel-2 L2A</strong> y un modelo <strong>Random Forest</strong> entrenado con etiquetas automáticas de edificios y red vial, usando la <strong>misma cuenta de Google</strong> que utilizas en Antigravity:</p>
        <ul>
          <li><strong>Guía A — Google Colab:</strong> ejecuta el cuaderno interactivo <code>mancha_urbana_sentinel2_vmod01.ipynb</code> en la nube sin instalar paquetes locales y descarga <code>probabilidad.tif</code>, <code>construido.tif</code>, <code>resumen.csv</code> y el polígono vectorial <code>.geojson</code>.</li>
          <li><strong>Guía B — Google Earth Engine (GEE):</strong> replica el flujo equivalente sobre el catálogo <code>COPERNICUS/S2_SR_HARMONIZED</code> y <code>ee.Classifier.smileRandomForest</code> para escalar a series multianuales y exportar directamente a <code>EPSG:4326</code>.</li>
          <li><strong>Integración con Antigravity:</strong> coloca los productos resultantes en <code>geovisor/capas/</code>, actualiza la narrativa en <code>content/</code> y envía tu Pull Request para revisión del equipo.</li>
        </ul>
        <div class="card-footer">
          <a class="btn btn-primary" href="{html.escape(ejercicio_url, quote=True)}">Ir al ejercicio guiado (Colab + GEE + Antigravity) →</a>
          <a class="btn btn-teal" href="{html.escape(ctx.site_url('aplicacion/'), quote=True)}">Abrir Geovisor de {esc(pid)}</a>
          <a class="btn btn-outline" href="{html.escape(repo_url + '/pulls', quote=True)}" target="_blank" rel="noopener noreferrer">Ver Pull Requests del proyecto ↗</a>
        </div>
      </article>
    </section>

    <section class="section">
      <div class="grid-2">
        <article class="card">
          <span class="badge badge-propuesta">Flujo A · Recomendado para participantes</span>
          <h3>1. Fork personal, clonación y rama descriptiva</h3>
          <p>Crea o reutiliza el fork en tu cuenta personal, configura <code>origin</code> (tu fork) y <code>upstream</code> (el repositorio canónico del equipo), y crea una rama con nombre descriptivo de tu tarea:</p>
          <pre id="cmd-fork" class="code-block"><code>{html.escape(fork_cmds)}</code></pre>
          <div class="card-footer">
            <button type="button" class="btn btn-outline btn-xs" data-copy-target="cmd-fork">Copiar comandos</button>
          </div>
        </article>

        <article class="card">
          <span class="badge badge-ok">Verificación local reproducible</span>
          <h3>2. Validar y previsualizar antes de subir cambios</h3>
          <p>Ejecuta siempre los tres comandos comunes antes de confirmar tu rama:</p>
          <pre id="cmd-val" class="code-block"><code>{html.escape(validate_cmds)}</code></pre>
          <div class="card-footer">
            <button type="button" class="btn btn-outline btn-xs" data-copy-target="cmd-val">Copiar comandos</button>
          </div>
        </article>
      </div>
    </section>

    <section class="section">
      <article class="card">
        <span class="badge badge-declarado">Despliegue de capas en el Geovisor GeoLibre</span>
        <h3>Cómo publicar una nueva capa geoespacial del equipo</h3>
        <ol>
          <li>Verifica que la capa tenga CRS <code>EPSG:4326</code> (WGS84), topología limpia, tabla de atributos documentada, autorización de publicación y ausencia de datos personales o prediales restringidos (puedes inspeccionarla antes en la pestaña <strong>Archivo local</strong> del geovisor).</li>
          <li>Coloca el archivo en <code>geovisor/capas/</code>:
            <ul>
              <li><code>.geojson</code>, <code>.json</code> y <code>.kml</code> se cargan directamente en el <strong>visor integrado (MapLibre)</strong> desde la pestaña <strong>Carpeta repo</strong>.</li>
              <li><code>.geolibre.json</code> abre el proyecto completo con estilos en <strong>GeoLibre Studio</strong> (<code>?url=...</code>).</li>
              <li><code>.tif</code> (COG), <code>.pmtiles</code>, <code>.fgb</code> y <code>.geoparquet</code> transfieren automáticamente su URL a <strong>GeoLibre Studio</strong> mediante <code>?data=...</code>.</li>
            </ul>
          </li>
          <li>Para dejar una capa activa por defecto al abrir el visor, edita <code>geovisor/layers.json</code>: coloca <code>geovisor/capas/tu_capa.geojson</code> en <code>source_path</code> y cambia <code>status</code> a <code>"en_revision"</code> o <code>"publicado"</code>.</li>
          <li>Ejecuta <code>python3 scripts/build_site.py --output site</code>: el generador actualizará automáticamente <code>site/geovisor/proyecto.geolibre.json</code> (v0.2.0) y activará el control en el Geovisor.</li>
        </ol>
      </article>
    </section>

    <section class="section">
      <div class="grid-2">
        <article class="card">
          <h3>3. Enviar Pull Request y dar seguimiento a la revisión</h3>
          <pre id="cmd-pr" class="code-block"><code>{html.escape(pr_cmds)}</code></pre>
          <p style="font-size:0.84rem;color:var(--c-text-muted);margin-top:0.65rem;">Tras abrir el Pull Request, GitHub Actions ejecuta automáticamente el validador. Si un chequeo aparece en rojo o la persona revisora solicita ajustes, corrige en tu misma rama y ejecuta <code>git push</code>: el PR se actualizará sin crear uno nuevo.</p>
          <div class="card-footer">
            <button type="button" class="btn btn-outline btn-xs" data-copy-target="cmd-pr">Copiar comandos</button>
          </div>
        </article>

        <article class="card">
          <h3>4. Registro de tareas, bloqueos y revisiones</h3>
          <p>Este repositorio incluye cuatro formularios estructurados en <code>.github/ISSUE_TEMPLATE/</code>:</p>
          <ul>
            <li><strong>Tarea del PMV:</strong> resultado concreto, criterio de aceptación y fecha objetivo propuesta.</li>
            <li><strong>Bloqueo o solicitud de apoyo:</strong> dificultad técnica o de datos y ayuda requerida (atendido por la facilitación técnica del clúster).</li>
            <li><strong>Solicitud de revisión:</strong> enlace a evidencia para revisión técnica o validación.</li>
            <li><strong>Contribución al Atlas:</strong> revisión de metadatos antes de pasar a publicado.</li>
          </ul>
          <div class="card-footer">
            {issue_btn}
          </div>
        </article>
      </div>
    </section>

    {render_project_institutions_band(ctx, branding, manifest)}
    """

    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="Colaborar",
        active_nav="colaborar",
        hero_html=hero,
        body_html=body,
    )


def build_404_page(ctx: SiteContext, manifest: dict[str, Any], repo_cfg: dict[str, Any]) -> str:
    hero = f"""
    <section class="hero">
      <div class="container">
        <h1>Página no encontrada (404)</h1>
        <p class="hero-lead">La ruta solicitada no existe dentro del sitio de <strong>{esc(manifest['title'])}</strong>.</p>
        <div class="hero-actions">
          <a class="btn btn-primary" href="{html.escape(ctx.site_url(''), quote=True)}">Volver a la portada de la iniciativa</a>
          <a class="btn btn-outline-light" href="{html.escape(ctx.site_url('aplicacion/'), quote=True)}">Ir al Geovisor GeoLibre</a>
        </div>
      </div>
    </section>
    """
    body = """
    <section class="section">
      <p>Comprueba la dirección o utiliza el menú superior para recorrer la ficha del proyecto, la metodología, los resultados o la guía de colaboración.</p>
    </section>
    """
    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="404 Página no encontrada",
        active_nav="",
        hero_html=hero,
        body_html=body,
    )


def write_deterministic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Construye el sitio estático de la iniciativa.")
    parser.add_argument("--output", type=str, default="site", help="Directorio de salida (por defecto: site).")
    parser.add_argument("--base-path", type=str, default=None, help="Prefijo explícito de ruta base (ej. / o /prueba-fork/).")
    parser.add_argument("--origin", type=str, default=None, help="Origen explícito HTTPS para generación de URLs absolutas.")
    args = parser.parse_args()

    if (ROOT / "data" / "projects.registry.json").exists():
        print("Error: directorio ambiguo (contiene data/projects.registry.json).", file=sys.stderr)
        return 1

    repo_cfg = json.loads((ROOT / "repo.config.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "project.json").read_text(encoding="utf-8"))
    layers_cfg = json.loads((ROOT / "geovisor" / "layers.json").read_text(encoding="utf-8"))
    branding_path = ROOT / "branding" / "project-branding.json"
    if branding_path.exists():
        branding = json.loads(branding_path.read_text(encoding="utf-8"))
    else:
        branding = {
            "schema_version": "1.0.0",
            "project_id": manifest["id"],
            "theme_version": THEME_VERSION,
            "updated_at": "2026-11-10",
            "project_logo": None,
            "institutions": [
                {
                    "id": f"inst-{idx}",
                    "name": nm,
                    "acronym": None,
                    "role": "Institución declarada en el perfil",
                    "logo_path": None,
                    "alt_text": f"Institución participante: {nm}",
                    "url": None,
                    "order": idx,
                    "aspect_hint": "auto",
                }
                for idx, nm in enumerate(manifest.get("institutional_use", {}).get("institutions", []), start=1)
            ],
        }

    project_md = (ROOT / "content" / "project.md").read_text(encoding="utf-8")
    metodologia_md = (ROOT / "content" / "metodologia.md").read_text(encoding="utf-8")
    pmv_md = (ROOT / "content" / "pmv.md").read_text(encoding="utf-8")
    continuidad_md = (ROOT / "content" / "continuidad.md").read_text(encoding="utf-8")

    atlas_products: list[dict[str, Any]] = []
    atlas_dir = ROOT / "atlas" / "products"
    if atlas_dir.exists():
        for ap_file in sorted(atlas_dir.glob("*.json")):
            atlas_products.append(json.loads(ap_file.read_text(encoding="utf-8")))

    explicit_bp = args.base_path if args.base_path is not None else os.environ.get("SITE_BASE_PATH")
    ctx = compute_site_context(
        canonical_repo_url_or_slug=manifest["links"].get("repository"),
        explicit_base_path=explicit_bp,
        explicit_origin=args.origin,
        hub_url=repo_cfg.get("hub_url"),
    )

    out_dir = (ROOT / args.output).resolve()
    if out_dir == ROOT:
        print("Error: --output no puede ser la raíz del repositorio.", file=sys.stderr)
        return 1
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Copiar recursos estáticos del tema común
    shutil.copytree(ROOT / "web" / "assets", out_dir / "assets")

    # Copiar logos propios de la iniciativa desde branding/logos/ hacia site/branding/logos/
    logos_src_dir = ROOT / "branding" / "logos"
    logos_out_dir = out_dir / "branding" / "logos"
    logos_out_dir.mkdir(parents=True, exist_ok=True)
    allowed_logo_exts = {".svg", ".png", ".webp", ".jpg", ".jpeg"}
    if logos_src_dir.exists():
        for lf in sorted(logos_src_dir.iterdir()):
            if lf.is_file() and lf.suffix.lower() in allowed_logo_exts:
                shutil.copy2(lf, logos_out_dir / lf.name)

    # Generar proyecto.geolibre.json actualizado y copiar capas públicas si existen
    geolibre_obj = build_geolibre_project_json(layers_cfg, manifest, ctx)
    write_deterministic(
        out_dir / "geovisor" / "layers.json",
        json.dumps(layers_cfg, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    write_deterministic(
        out_dir / "geovisor" / "proyecto.geolibre.json",
        json.dumps(geolibre_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    repo_geolibre = ROOT / "geovisor" / "proyecto.geolibre.json"
    if repo_geolibre.parent.exists():
        write_deterministic(
            repo_geolibre,
            json.dumps(geolibre_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
    data_layers_dir = ROOT / "geovisor" / "data"
    if data_layers_dir.exists():
        (out_dir / "geovisor" / "data").mkdir(parents=True, exist_ok=True)
        for f in sorted(data_layers_dir.iterdir()):
            if f.is_file() and f.name != ".gitkeep":
                shutil.copy2(f, out_dir / "geovisor" / "data" / f.name)

    # Indexar y publicar la carpeta geovisor/capas/ (formatos compatibles con GeoLibre)
    geolibre_exts = {".geojson", ".json", ".kml", ".pmtiles", ".fgb", ".tif", ".tiff", ".parquet", ".geoparquet"}
    capas_src_dir = ROOT / "geovisor" / "capas"
    capas_out_dir = out_dir / "geovisor" / "capas"
    capas_out_dir.mkdir(parents=True, exist_ok=True)
    indexed_files: list[dict[str, Any]] = []
    if capas_src_dir.exists():
        for f in sorted(capas_src_dir.iterdir()):
            if not f.is_file() or f.name in (".gitkeep", "README.md", "index.json"):
                continue
            if f.suffix.lower() in geolibre_exts or f.name.lower().endswith(".geolibre.json"):
                shutil.copy2(f, capas_out_dir / f.name)
                indexed_files.append(
                    {
                        "name": f.name,
                        "path": f"geovisor/capas/{f.name}",
                        "format": "geolibre" if f.name.lower().endswith(".geolibre.json") else f.suffix.lower().lstrip("."),
                        "size_bytes": f.stat().st_size,
                    }
                )
    effective_repo_slug = (
        ctx.github_repository
        if ctx.github_repository
        else (ctx.canonical_repository if ctx.effective_mode == "canonical" else None)
    )
    write_deterministic(
        capas_out_dir / "index.json",
        json.dumps(
            {
                "folder": "geovisor/capas",
                "project_id": manifest["id"],
                "repository": effective_repo_slug,
                "canonical_repository": ctx.canonical_repository,
                "effective_mode": ctx.effective_mode,
                "files": indexed_files,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    # Exportar JSONs públicos seleccionados
    write_deterministic(
        out_dir / "data" / "project.json",
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    write_deterministic(
        out_dir / "data" / "project-branding.json",
        json.dumps(branding, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    write_deterministic(
        out_dir / "data" / "atlas-products.json",
        json.dumps(atlas_products, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    build_meta = {
        "project_id": manifest["id"],
        "schema_version": manifest["schema_version"],
        "template_version": TEMPLATE_VERSION,
        "theme_version": THEME_VERSION,
        "repo_kind": repo_cfg.get("repo_kind"),
        "base_path": ctx.base_path,
        "origin": ctx.origin,
        "effective_mode": ctx.effective_mode,
        "canonical_repository": ctx.canonical_repository,
    }
    write_deterministic(
        out_dir / "data" / "build-meta.json",
        json.dumps(build_meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )

    # Generar páginas HTML estáticas
    write_deterministic(out_dir / "index.html", build_home_page(ctx, manifest, repo_cfg, layers_cfg, branding))
    write_deterministic(out_dir / "proyecto" / "index.html", build_proyecto_page(ctx, manifest, repo_cfg, project_md, pmv_md, branding))
    write_deterministic(out_dir / "aplicacion" / "index.html", build_aplicacion_page(ctx, manifest, repo_cfg, layers_cfg, branding))
    write_deterministic(out_dir / "modelo-suelo" / "index.html", build_modelo_suelo_page(ctx, manifest, repo_cfg, branding))
    write_deterministic(out_dir / "metodologia" / "index.html", build_metodologia_page(ctx, manifest, repo_cfg, metodologia_md, branding))
    write_deterministic(out_dir / "resultados" / "index.html", build_resultados_page(ctx, manifest, repo_cfg, atlas_products, continuidad_md, branding, layers_cfg))
    write_deterministic(out_dir / "colaborar" / "index.html", build_colaborar_page(ctx, manifest, repo_cfg, branding))
    write_deterministic(out_dir / "404.html", build_404_page(ctx, manifest, repo_cfg))

    print(
        f"[OK] Sitio construido para '{manifest['id']}' en {out_dir} "
        f"(base_path='{ctx.base_path}', modo='{ctx.effective_mode}', tema='{THEME_VERSION}')."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
