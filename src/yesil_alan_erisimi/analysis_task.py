# -*- coding: utf-8 -*-
"""
Background Task for Green Space Accessibility & Pedshed Analysis.
Author / Developer: Baran Adsuna (https://github.com/baranadsuna)
CRS Standard: EPSG:5253 (TUREF / TM30)
"""
from __future__ import annotations

import math
import time
import traceback
from typing import Any, Dict, List, Tuple

from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeatureRequest,
    QgsGeometry,
    QgsMessageLog,
    QgsPointXY,
    QgsTask,
)

from . import i18n
from . import network as net
from .compat import meters_unit, task_can_cancel

LOG_TAG = "GreenSpaceAccessibility"


def log(msg: str, level: Any = None) -> None:
    lvl = level if level is not None else (
        Qgis.MessageLevel.Info if hasattr(Qgis, "MessageLevel") else Qgis.Info
    )
    QgsMessageLog.logMessage(msg, LOG_TAG, lvl)


def choose_calc_crs(road_layer: Any, project: Any) -> Tuple[QgsCoordinateReferenceSystem, str]:
    """
    Selects a metric coordinate system for accurate planar calculations.
    Prefers EPSG:5253 (TUREF / TM30) as required by project governance.
    """
    crs = road_layer.crs() if (road_layer and road_layer.isValid()) else project.crs()
    auth = crs.authid().upper() if (crs and crs.isValid()) else ""

    if auth == "EPSG:5253":
        return crs, "Calculation CRS: EPSG:5253 (TUREF / TM30 — Mandatory Standard)"

    try:
        if crs.isValid() and not crs.isGeographic() and crs.mapUnits() == meters_unit():
            return crs, f"Calculation CRS: {crs.authid()} (projected metric road layer)"
    except Exception:
        pass

    # For geographic CRS (e.g. EPSG:4326), derive appropriate metric UTM zone
    try:
        wgs = QgsCoordinateReferenceSystem("EPSG:4326")
        ct = QgsCoordinateTransform(crs, wgs, project)
        c = ct.transform(road_layer.extent().center())
        # If in Turkey territory (lon ~26-45, lat ~36-42), recommend EPSG:5253
        if 25.5 <= c.x() <= 45.0 and 35.5 <= c.y() <= 42.5:
            turef = QgsCoordinateReferenceSystem("EPSG:5253")
            if turef.isValid():
                return turef, f"Layer is geographic ({crs.authid()}); auto-projected to EPSG:5253 (TUREF / TM30)."

        zone = int((c.x() + 180.0) // 6.0) + 1
        zone = min(max(zone, 1), 60)
        epsg = (32600 if c.y() >= 0 else 32700) + zone
        utm = QgsCoordinateReferenceSystem(f"EPSG:{epsg}")
        if utm.isValid():
            return utm, f"Layer is geographic ({crs.authid()}); auto-projected to UTM (EPSG:{epsg})."
    except Exception:
        pass

    return crs, "WARNING: Metric CRS could not be determined; calculating in raw layer units."


def _line(x1: float, y1: float, x2: float, y2: float) -> QgsGeometry:
    return QgsGeometry.fromPolylineXY([QgsPointXY(x1, y1), QgsPointXY(x2, y2)])


class AnalysisTask(QgsTask):
    status_message = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(
        self,
        inputs: Dict[str, Any],
        params: Dict[str, Any],
        calc_crs: QgsCoordinateReferenceSystem,
        transform_context: Any,
        lang: str = "en",
    ):
        super(AnalysisTask, self).__init__("Green Space Accessibility Analysis", task_can_cancel())
        self.inputs = inputs
        self.params = params
        self.calc_crs = calc_crs
        self.ctx = transform_context
        self.lang = lang
        self.result_data: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.elapsed: float = 0.0
        self.skipped_small_parks: int = 0
        self._park_geoms: Dict[Any, QgsGeometry] = {}
        self._bldg_geoms: Dict[Any, QgsGeometry] = {}

    def _tr(self, key: str, **kwargs) -> str:
        return i18n.tr(key, self.lang, **kwargs)

    def _request(self, inp: Dict[str, Any], with_field: bool = False):
        src = inp["source"]
        req = QgsFeatureRequest()
        req.setDestinationCrs(self.calc_crs, self.ctx)
        attrs = [inp["field"]] if (with_field and inp.get("field")) else []
        req.setSubsetOfAttributes(attrs, src.fields())
        if inp.get("fids") is not None:
            req.setFilterFids(inp["fids"])
        return src.getFeatures(req)

    def _read_roads(self) -> List[Tuple[Any, List[Tuple[float, float]]]]:
        roads = []
        for k, feat in enumerate(self._request(self.inputs["roads"])):
            if k % 500 == 0 and self.isCanceled():
                raise net.Cancelled()
            geom = feat.geometry()
            if geom is None or geom.isNull() or geom.isEmpty():
                continue
            try:
                if geom.constGet().hasCurvedSegments():
                    geom.convertToStraightSegment()
            except Exception:
                pass
            parts = geom.asMultiPolyline() if geom.isMultipart() else [geom.asPolyline()]
            for part in parts:
                if len(part) >= 2:
                    roads.append((feat.id(), [(p.x(), p.y()) for p in part]))
        return roads

    def _read_parks(self) -> List[Dict[str, Any]]:
        parks = []
        boundary = self.params.get("origin_mode", "boundary") == "boundary"
        min_area = float(self.params.get("min_area", 0.0))

        for k, feat in enumerate(self._request(self.inputs["parks"])):
            if k % 200 == 0 and self.isCanceled():
                raise net.Cancelled()
            geom = feat.geometry()
            if geom is None or geom.isNull() or geom.isEmpty():
                continue
            p_area = float(geom.area()) if geom.isGeosValid() else 0.0
            if min_area > 0 and p_area > 0 and p_area < min_area:
                self.skipped_small_parks += 1
                continue

            c = geom.centroid()
            try:
                if p_area > 0 and not geom.contains(c):
                    c = geom.pointOnSurface()
            except Exception:
                pass
            if c is None or c.isNull() or c.isEmpty():
                continue
            pt = c.asPoint()

            ring = []
            if boundary and p_area > 0:
                dg = geom
                try:
                    dg = geom.densifyByDistance(5.0)
                except Exception:
                    pass
                ring = [(v.x(), v.y()) for v in dg.vertices()]
            else:
                ring = [(v.x(), v.y()) for v in geom.vertices()] or [(pt.x(), pt.y())]

            self._park_geoms[feat.id()] = QgsGeometry(geom)
            parks.append({
                "id": feat.id(),
                "centroid": (pt.x(), pt.y()),
                "ring": ring,
                "area_m2": p_area,
            })
        return parks

    def _read_buildings(self) -> List[Tuple[Any, float, float, float, List[Tuple[float, float]]]]:
        inp = self.inputs.get("buildings")
        if not inp:
            return []
        out = []
        field = inp.get("field")
        for k, feat in enumerate(self._request(inp, with_field=True)):
            if k % 1000 == 0 and self.isCanceled():
                raise net.Cancelled()
            geom = feat.geometry()
            if geom is None or geom.isNull() or geom.isEmpty():
                continue
            c = geom.centroid()
            try:
                if geom.area() > 0 and not geom.contains(c):
                    c = geom.pointOnSurface()
            except Exception:
                pass
            if c is None or c.isNull() or c.isEmpty():
                continue
            pt = c.asPoint()

            # Extract dense facade points along the block/building perimeter
            facade_pts: List[Tuple[float, float]] = []
            try:
                if geom.area() > 0:
                    self._bldg_geoms[feat.id()] = QgsGeometry(geom)
                    dg = geom.densifyByDistance(5.0)
                    facade_pts = [(v.x(), v.y()) for v in dg.vertices()]
                else:
                    facade_pts = [(v.x(), v.y()) for v in geom.vertices()]
            except Exception:
                facade_pts = [(pt.x(), pt.y())]
            if not facade_pts:
                facade_pts = [(pt.x(), pt.y())]

            w = 1.0
            if field:
                try:
                    val = feat[field]
                    if val is not None:
                        w = float(val)
                        if w != w or w < 0:
                            w = 0.0
                except Exception:
                    w = 0.0
            out.append((feat.id(), pt.x(), pt.y(), w, facade_pts))
        return out

    def run(self) -> bool:
        t0 = time.time()
        try:
            self.status_message.emit(self._tr("status_reading"))
            roads = self._read_roads()
            if not roads:
                raise ValueError("No usable line geometries found in road layer.")
            self.setProgress(4)

            parks = self._read_parks()
            if not parks:
                raise ValueError("No usable facility features found passing the filter.")
            self.setProgress(7)

            buildings = self._read_buildings()
            self.setProgress(10)

            def prog(p: float):
                self.setProgress(10 + p * 0.82)

            def emit_status(msg_key: str):
                self.status_message.emit(self._tr(msg_key))

            res = net.analyze(
                roads,
                parks,
                buildings,
                self.params,
                progress=prog,
                status=emit_status,
                cancelled=self.isCanceled,
            )

            self.status_message.emit(self._tr("status_generating_layers"))
            self._build_geometries(res)
            res["skipped_small_parks"] = self.skipped_small_parks
            res["park_geoms"] = self._park_geoms
            res["bldg_geoms"] = self._bldg_geoms
            self.result_data = res
            self.setProgress(98)
            return True
        except net.Cancelled:
            return False
        except Exception:
            self.error = traceback.format_exc()
            return False
        finally:
            self.elapsed = time.time() - t0

    def _build_geometries(self, res: Dict[str, Any]) -> None:
        """Constructs multi-part service roads, walking isochrones, and benchmark circles."""
        service = {}
        polygons = {}
        circles = {}
        pedshed_stats = {}

        buf = float(self.params.get("polygon_buffer", 25.0))
        make_poly = bool(self.params.get("generate_polygons", True))
        make_circ = bool(self.params.get("generate_circles", True))

        # Collect all facility seeds and polygon geometries
        all_park_centroids = []
        facility_polys = []
        for pid, geom in self._park_geoms.items():
            if geom and not geom.isEmpty():
                c = geom.centroid()
                if c and not c.isEmpty():
                    all_park_centroids.append(c.asPoint())
                if geom.area() > 0:
                    facility_polys.append(geom.buffer(max(buf * 0.5, 5.0), 6))

        for t, pcs in res["pieces"].items():
            if self.isCanceled():
                raise net.Cancelled()
            groups: Dict[Any, List[Any]] = {}
            flat: List[QgsGeometry] = []

            for x1, y1, x2, y2, cost, lab, road in pcs:
                g = groups.setdefault(road, [[], float("inf"), None])
                ln = _line(x1, y1, x2, y2)
                g[0].append(ln)
                flat.append(ln)
                if cost < g[1]:
                    g[1], g[2] = cost, lab

            service[t] = [
                (road, QgsGeometry.collectGeometry(g[0]), g[1], g[2]) for road, g in groups.items()
            ]

            # Isochrone Catchment Polygon
            net_area_m2 = 0.0
            if make_poly and flat:
                merged_lines = QgsGeometry.collectGeometry(flat)
                poly = merged_lines.buffer(buf, 8)
                if poly and not poly.isEmpty():
                    if facility_polys:
                        try:
                            poly = QgsGeometry.unaryUnion([poly] + facility_polys)
                        except Exception:
                            pass
                    try:
                        if hasattr(poly, "removeInteriorRings"):
                            cleaned = poly.removeInteriorRings(18000.0)
                            if cleaned and not cleaned.isEmpty():
                                poly = cleaned
                    except Exception:
                        pass
                    net_area_m2 = float(poly.area())
                    polygons[t] = (poly, net_area_m2)

            # Benchmark Euclidean Circular Buffer (MPYY / WHO baseline: Pi * R^2)
            circ_area_m2 = 0.0
            if make_circ and all_park_centroids:
                circ_geoms = [
                    QgsGeometry.fromPointXY(pt).buffer(t, 24) for pt in all_park_centroids
                ]
                if circ_geoms:
                    merged_circ = QgsGeometry.unaryUnion(circ_geoms)
                    if merged_circ and not merged_circ.isEmpty():
                        circ_area_m2 = float(merged_circ.area())
                        circles[t] = (merged_circ, circ_area_m2)

            # Calculate Pedshed Ratio: Network Area / Euclidean Buffer Area
            if circ_area_m2 > 0:
                ratio = round((net_area_m2 / circ_area_m2) * 100.0, 1)
            else:
                ratio = 0.0

            pedshed_stats[t] = {
                "net_area_ha": round(net_area_m2 / 10000.0, 2),
                "circ_area_ha": round(circ_area_m2 / 10000.0, 2),
                "ratio_pct": ratio,
                "status": "status_well_connected" if ratio >= 40.0 else "status_isolated",
            }

        res["service"] = service
        res["polygons"] = polygons
        res["circles"] = circles
        res["stats"]["pedshed"] = pedshed_stats
        res.pop("pieces", None)

    def finished(self, ok: bool) -> None:
        self.finished_signal.emit(bool(ok))
