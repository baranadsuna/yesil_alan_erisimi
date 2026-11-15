# -*- coding: utf-8 -*-
"""
Map Layer Generation & Visual Styling for Green Space Accessibility & Pedshed Analysis.
Author / Developer: Baran Adsuna (https://github.com/baranadsuna)
CRS Standard: EPSG:5253 (TUREF / TM30)
Dual Compatible: QGIS 3 & QGIS 4 / Qt5 & Qt6
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsCoordinateTransform,
    QgsFeature,
    QgsFillSymbol,
    QgsGeometry,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsPointXY,
    QgsRendererCategory,
    QgsSingleSymbolRenderer,
    QgsVectorLayer,
)

from . import i18n
from .compat import make_field
from .report import fmt_m

# Color ramp from high walkability (vibrant green) to far / unreached (red/gray)
RAMP = ["#16a34a", "#65a30d", "#eab308", "#f97316", "#dc2626"]
NO_ACCESS = "#dc2626"
NO_SNAP = "#9ca3af"


def threshold_colors(n: int) -> List[str]:
    if n <= 1:
        return [RAMP[0]]
    return [RAMP[int(round(i * (len(RAMP) - 1) / float(n - 1)))] for i in range(n)]


def class_labels(thresholds: List[float], lang: str = "en") -> Tuple[List[str], str, str]:
    labels, prev = [], 0.0
    for t in thresholds:
        if prev == 0.0:
            labels.append(f"0–{fmt_m(t)} m")
        else:
            labels.append(f"{fmt_m(prev)}–{fmt_m(t)} m")
        prev = t

    no_access_suffix = {
        "en": f"> {fmt_m(thresholds[-1])} m (Unreached)",
        "tr": f"> {fmt_m(thresholds[-1])} m (Erişim Dışı)",
        "zh": f"> {fmt_m(thresholds[-1])} 米 (不可达)",
        "es": f"> {fmt_m(thresholds[-1])} m (Sin acceso)",
        "id": f"> {fmt_m(thresholds[-1])} m (Di luar jangkauan)",
    }.get(lang, f"> {fmt_m(thresholds[-1])} m (Unreached)")

    no_snap_str = {
        "en": "Unsnapped to Road Network",
        "tr": "Ağa Bağlanamadı",
        "zh": "未吸附至路网",
        "es": "No conectado a la red",
        "id": "Tidak tersambung ke jalan",
    }.get(lang, "Unsnapped to Road Network")

    return labels, no_access_suffix, no_snap_str


def _new_layer(geom_type: str, name: str, crs: Any, fields: List[Tuple[str, str]]) -> QgsVectorLayer:
    lyr = QgsVectorLayer(geom_type, name, "memory")
    lyr.setCrs(crs)
    lyr.dataProvider().addAttributes([make_field(n, k) for n, k in fields])
    lyr.updateFields()
    return lyr


def _fill(lyr: QgsVectorLayer, geoms_attrs: List[Tuple[QgsGeometry, List[Any]]], transform: Any) -> QgsVectorLayer:
    feats = []
    for geom, attrs in geoms_attrs:
        if geom is None or geom.isNull() or geom.isEmpty():
            continue
        g_copy = QgsGeometry(geom)
        if transform is not None:
            try:
                g_copy.transform(transform)
            except Exception:
                pass
        f = QgsFeature(lyr.fields())
        f.setGeometry(g_copy)
        f.setAttributes(attrs)
        feats.append(f)
    if feats:
        lyr.dataProvider().addFeatures(feats)
    lyr.updateExtents()
    return lyr


def _multi(g: QgsGeometry) -> QgsGeometry:
    if g is not None and not g.isNull() and not g.isMultipart():
        g.convertToMultiType()
    return g


def _point(x: float, y: float) -> QgsGeometry:
    return QgsGeometry.fromPointXY(QgsPointXY(x, y))


def build_layers(
    result: Dict[str, Any],
    params: Dict[str, Any],
    calc_crs: Any,
    project: Any,
    group_title: str,
    lang: str = "en",
) -> List[str]:
    """Generates styled vector memory layers and adds them to the project."""
    proj_crs = project.crs()
    ct = None
    if calc_crs.isValid() and proj_crs.isValid() and calc_crs != proj_crs:
        ct = QgsCoordinateTransform(calc_crs, proj_crs, project)
    out_crs = proj_crs if proj_crs.isValid() else calc_crs

    ths = result["thresholds"]
    colors = threshold_colors(len(ths))
    root = project.layerTreeRoot()
    group = root.insertGroup(0, group_title)
    created = []

    def add(layer: QgsVectorLayer) -> None:
        project.addMapLayer(layer, False)
        group.addLayer(layer)
        created.append(layer.name())

    # 1. Building / Block Accessibility Results (Points + Colored Polygons)
    blds = result.get("buildings", [])
    bldg_geoms = result.get("bldg_geoms", {})
    if blds:
        use_w = bool(params.get("use_weight"))
        fields = [
            ("Bldg_ID", "int"),
            ("Target_ID", "int"),
            ("Dist_m", "double"),
            ("Time_min", "double"),
            ("Class", "string"),
            ("Snap_m", "double"),
        ]
        for t in ths:
            fields.append((f"Reach_{fmt_m(t)}m", "int"))
        if use_w:
            fields.append(("Weight", "double"))

        layer_name = i18n.tr("layer_bldgs_name", lang)
        lyr = _new_layer("Point", layer_name, out_crs, fields)
        labels, none_lbl, nosnap_lbl = class_labels(ths, lang=lang)
        spd = result["stats"].get("speed_mps") or (4.8 * 1000.0 / 3600.0)
        rows = []
        poly_rows = []

        for bid, x, y, w, cost, lab, snap in blds:
            if snap is None:
                cls = nosnap_lbl
            elif cost is None:
                cls = none_lbl
            else:
                cls = none_lbl
                for t, lbl in zip(ths, labels):
                    if cost <= t:
                        cls = lbl
                        break
            attrs = [
                bid,
                lab,
                None if cost is None else round(cost, 1),
                None if (cost is None or not spd) else round(cost / spd / 60.0, 1),
                cls,
                None if snap is None else round(snap, 1),
            ]
            attrs += [1 if (cost is not None and cost <= t) else 0 for t in ths]
            if use_w:
                attrs.append(w)
            rows.append((_point(x, y), attrs))
            if bid in bldg_geoms:
                bg = bldg_geoms[bid]
                if bg is not None and not bg.isEmpty():
                    poly_rows.append((_multi(QgsGeometry(bg)), list(attrs)))

        _fill(lyr, rows, ct)

        cats = []
        for lbl, col in zip(labels, colors):
            cats.append(
                QgsRendererCategory(
                    lbl,
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "circle",
                            "color": col,
                            "size": "2.6",
                            "outline_color": "#ffffff",
                            "outline_width": "0.3",
                        }
                    ),
                    lbl,
                )
            )
        cats.append(
            QgsRendererCategory(
                none_lbl,
                QgsMarkerSymbol.createSimple(
                    {"name": "circle", "color": NO_ACCESS, "size": "2.4", "outline_style": "no"}
                ),
                none_lbl,
            )
        )
        cats.append(
            QgsRendererCategory(
                nosnap_lbl,
                QgsMarkerSymbol.createSimple(
                    {"name": "circle", "color": NO_SNAP, "size": "2.0", "outline_style": "no"}
                ),
                nosnap_lbl,
            )
        )
        lyr.setRenderer(QgsCategorizedSymbolRenderer("Class", cats))
        add(lyr)

        # Colored Building / Block Polygon Layer (so blocks within 250m are painted green!)
        if poly_rows:
            poly_layer_name = i18n.tr("layer_bldgs_poly_name", lang)
            poly_lyr = _new_layer("MultiPolygon", poly_layer_name, out_crs, fields)
            _fill(poly_lyr, poly_rows, ct)
            poly_cats = []
            for lbl, col in zip(labels, colors):
                sym = QgsFillSymbol.createSimple(
                    {"color": col, "outline_color": "#1e293b", "outline_width": "0.25"}
                )
                sym.setOpacity(0.62)
                poly_cats.append(QgsRendererCategory(lbl, sym, lbl))
            sym_none = QgsFillSymbol.createSimple(
                {"color": NO_ACCESS, "outline_color": "#1e293b", "outline_width": "0.25"}
            )
            sym_none.setOpacity(0.45)
            poly_cats.append(QgsRendererCategory(none_lbl, sym_none, none_lbl))
            sym_nosnap = QgsFillSymbol.createSimple(
                {"color": NO_SNAP, "outline_color": "#475569", "outline_width": "0.25"}
            )
            sym_nosnap.setOpacity(0.35)
            poly_cats.append(QgsRendererCategory(nosnap_lbl, sym_nosnap, nosnap_lbl))
            poly_lyr.setRenderer(QgsCategorizedSymbolRenderer("Class", poly_cats))
            add(poly_lyr)

    # 2. Road Network Service Area Lines (Clipped at Thresholds)
    for t, col in zip(ths, colors):
        pcs = result.get("service", {}).get(t, [])
        if pcs:
            rows = [
                (_multi(g), [rid, None if cost is None else round(cost, 1), lab])
                for rid, g, cost, lab in pcs
            ]
            layer_name = i18n.tr("layer_roads_name", lang, fmt_m(t))
            lyr = _new_layer(
                "MultiLineString",
                layer_name,
                out_crs,
                [("Road_ID", "int"), ("Dist_m", "double"), ("Target_ID", "int")],
            )
            _fill(lyr, rows, ct)
            sym = QgsLineSymbol.createSimple(
                {"line_color": col, "line_width": "1.7", "capstyle": "round", "joinstyle": "round"}
            )
            lyr.setRenderer(QgsSingleSymbolRenderer(sym))
            add(lyr)

    # 3. Walkability Isochrone Catchment Polygons (Non-overlapping clean bands)
    if params.get("generate_polygons", True):
        prev_iso_geom = None
        for t, col in zip(ths, colors):
            if t in result.get("polygons", {}):
                geom, area_m2 = result["polygons"][t]
                disp_geom = QgsGeometry(geom)
                if prev_iso_geom is not None:
                    try:
                        diff = disp_geom.difference(prev_iso_geom)
                        if diff is not None and not diff.isEmpty():
                            disp_geom = diff
                    except Exception:
                        pass
                prev_iso_geom = QgsGeometry(geom)

                layer_name = i18n.tr("layer_isochrones_name", lang, fmt_m(t))
                lyr = _new_layer(
                    "MultiPolygon",
                    layer_name,
                    out_crs,
                    [("Threshold_m", "double"), ("Area_ha", "double")],
                )
                _fill(lyr, [(_multi(disp_geom), [float(t), round(area_m2 / 10000.0, 2)])], ct)
                sym = QgsFillSymbol.createSimple(
                    {"color": col, "outline_color": col, "outline_width": "0.4"}
                )
                sym.setOpacity(0.38)
                lyr.setRenderer(QgsSingleSymbolRenderer(sym))
                add(lyr)

    # 4. Benchmark Euclidean Circular Buffers (WHO / MPYY Baseline)
    if params.get("generate_circles", True):
        for t, col in zip(ths, colors):
            if t in result.get("circles", {}):
                geom, circ_m2 = result["circles"][t]
                layer_name = i18n.tr("layer_circles_name", lang, fmt_m(t))
                lyr = _new_layer(
                    "MultiPolygon",
                    layer_name,
                    out_crs,
                    [("Threshold_m", "double"), ("Area_ha", "double")],
                )
                _fill(lyr, [(_multi(geom), [float(t), round(circ_m2 / 10000.0, 2)])], ct)
                sym = QgsFillSymbol.createSimple(
                    {
                        "color": "transparent",
                        "outline_color": col,
                        "outline_width": "0.6",
                        "outline_style": "dash",
                    }
                )
                lyr.setRenderer(QgsSingleSymbolRenderer(sym))
                add(lyr)

    # 5. Target Facility Allocation & Pedshed Summary Layer (Prominent Blue Point Symbol)
    park_geoms = result.get("park_geoms", {})
    allocations = result.get("allocations", {})
    if park_geoms and allocations:
        fields = [
            ("Target_ID", "int"),
            ("Area_ha", "double"),
            ("Served_Bld", "int"),
            ("Served_Pop", "double"),
            ("Mean_Dist", "double"),
            ("Status", "string"),
        ]
        layer_name = i18n.tr("layer_parks_summary_name", lang)
        poly_rows = []
        pt_rows = []
        for pid, data in allocations.items():
            geom = park_geoms.get(pid)
            if geom and not geom.isEmpty():
                p_area_ha = round(data.get("area_m2", 0.0) / 10000.0, 2)
                blds_cnt = data.get("buildings", 0)
                mean_d = data.get("mean_dist")
                status_str = (
                    i18n.tr("status_well_connected", lang)
                    if blds_cnt > 0
                    else i18n.tr("status_isolated", lang)
                )
                row_attrs = [
                    pid,
                    p_area_ha,
                    blds_cnt,
                    round(data.get("weight", 0.0), 1),
                    None if mean_d is None else round(mean_d, 1),
                    status_str,
                ]
                # Always generate a prominent Blue Point symbol at the facility centroid
                c = geom.centroid()
                if c and not c.isEmpty():
                    pt = c.asPoint()
                    pt_rows.append((_point(pt.x(), pt.y()), list(row_attrs)))
                if geom.area() > 0:
                    poly_rows.append((_multi(QgsGeometry(geom)), list(row_attrs)))

        # Optional translucent Blue Polygon Footprint when target facility is a polygon
        if poly_rows:
            poly_lyr = _new_layer("MultiPolygon", f"{layer_name} (Polygon)", out_crs, fields)
            _fill(poly_lyr, poly_rows, ct)
            sym_poly = QgsFillSymbol.createSimple(
                {"color": "#3b82f6", "outline_color": "#1d4ed8", "outline_width": "0.6"}
            )
            sym_poly.setOpacity(0.42)
            poly_lyr.setRenderer(QgsSingleSymbolRenderer(sym_poly))
            project.addMapLayer(poly_lyr, False)
            group.insertLayer(0, poly_lyr)
            created.insert(0, poly_lyr.name())

        # Prominent, slightly larger Blue Point Symbol (#2563eb) placed at the very top of the group
        if pt_rows:
            pt_lyr = _new_layer("Point", layer_name, out_crs, fields)
            _fill(pt_lyr, pt_rows, ct)
            sym_pt = QgsMarkerSymbol.createSimple(
                {
                    "name": "circle",
                    "color": "#2563eb",
                    "size": "5.6",
                    "outline_color": "#ffffff",
                    "outline_width": "0.8",
                }
            )
            pt_lyr.setRenderer(QgsSingleSymbolRenderer(sym_pt))
            project.addMapLayer(pt_lyr, False)
            group.insertLayer(0, pt_lyr)
            created.insert(0, pt_lyr.name())

    # 6. Audit & Debug Layers (Facade Connectors, Bridges & Access Points)
    if params.get("add_debug", True):
        if result.get("building_connectors"):
            conn_rows = []
            for bid, _cx, _cy, fx, fy, qx, qy, cost, lab, snap_d in result["building_connectors"]:
                if snap_d is not None and snap_d > 0.05:
                    conn_rows.append((
                        QgsGeometry.fromPolylineXY([QgsPointXY(fx, fy), QgsPointXY(qx, qy)]),
                        [bid, lab, None if cost is None else round(cost, 1), round(snap_d, 1)],
                    ))
            if conn_rows:
                layer_name = i18n.tr("layer_connectors_name", lang)
                lyr = _new_layer(
                    "LineString",
                    layer_name,
                    out_crs,
                    [("Bldg_ID", "int"), ("Target_ID", "int"), ("Dist_m", "double"), ("Snap_m", "double")],
                )
                _fill(lyr, conn_rows, ct)
                lyr.setRenderer(
                    QgsSingleSymbolRenderer(
                        QgsLineSymbol.createSimple(
                            {"line_color": "#c2410c", "line_width": "0.7", "line_style": "dot"}
                        )
                    )
                )
                add(lyr)

        if result.get("bridges"):
            layer_name = i18n.tr("layer_bridges_name", lang)
            lyr = _new_layer(
                "LineString",
                layer_name,
                out_crs,
                [("Length_m", "double"), ("Bridge_Type", "string")],
            )
            rows = [
                (
                    QgsGeometry.fromPolylineXY([QgsPointXY(x1, y1), QgsPointXY(x2, y2)]),
                    [round(L, 2), "node-node" if kind == "node" else "T-junction"],
                )
                for x1, y1, x2, y2, L, kind in result["bridges"]
            ]
            _fill(lyr, rows, ct)
            lyr.setRenderer(
                QgsSingleSymbolRenderer(
                    QgsLineSymbol.createSimple(
                        {"line_color": "#d97706", "line_width": "1.3", "line_style": "dash"}
                    )
                )
            )
            add(lyr)

        if result.get("access_points"):
            layer_name = i18n.tr("layer_access_points_name", lang)
            lyr = _new_layer(
                "Point",
                layer_name,
                out_crs,
                [("Target_ID", "int"), ("Snap_m", "double")],
            )
            rows = [
                (_point(px, py), [pid, round(off, 1)])
                for pid, px, py, off in result["access_points"]
            ]
            _fill(lyr, rows, ct)
            lyr.setRenderer(
                QgsSingleSymbolRenderer(
                    QgsMarkerSymbol.createSimple(
                        {
                            "name": "circle",
                            "color": "#3b82f6",
                            "size": "3.2",
                            "outline_color": "#ffffff",
                            "outline_width": "0.5",
                        }
                    )
                )
            )
            add(lyr)

    return created
