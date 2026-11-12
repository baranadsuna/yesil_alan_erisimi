# -*- coding: utf-8 -*-
"""
Main GUI Dialog for Green Space Accessibility & Pedshed Analysis.
Author / Developer: Baran Adsuna (https://github.com/baranadsuna)
CRS Standard: EPSG:5253 (TUREF / TM30)
Dual Compatible: QGIS 3.22+ and QGIS 4.x (Qt5 & Qt6)
"""
from __future__ import annotations

import re
import time
from typing import Any, List, Optional

from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsApplication, QgsProject, QgsVectorLayerFeatureSource
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox

from . import i18n, report
from .analysis_task import AnalysisTask, choose_calc_crs, log
from .compat import align_right, layer_filter
from .outputs import build_layers

PLUGIN_VERSION = "5.1.0"
SETTINGS_PREFIX = "GreenSpaceAccessibility/"
MAX_THRESHOLDS = 10

STYLE = """
QPushButton#runButton {
    background-color: #10b981; color: white; font-weight: bold;
    font-size: 13px; padding: 8px 16px; border-radius: 6px; border: none;
}
QPushButton#runButton:hover { background-color: #059669; }
QPushButton#runButton:pressed { background-color: #047857; }
QPushButton#runButton[running="true"] { background-color: #dc2626; }
QPushButton#presetButton { padding: 3px 8px; font-size: 11px; }
QProgressBar { border: 1px solid #cbd5e1; border-radius: 6px; text-align: center; height: 16px; font-size: 11px; }
QProgressBar::chunk { background-color: #10b981; border-radius: 5px; }
QLabel#statusHint { color: #64748b; font-size: 11px; }
QComboBox#langSelector { font-weight: bold; padding: 2px 8px; border-radius: 4px; }
"""


def parse_thresholds(text: str) -> List[float]:
    """Parses distance thresholds string: '300, 500; 1000' -> [300.0, 500.0, 1000.0]."""
    vals = set()
    cleaned = text.replace(";", " ").replace(",", " ")
    for tok in re.findall(r"\d+(?:\.\d+)*", cleaned):
        if re.fullmatch(r"[1-9]\d{0,2}(?:\.\d{3})+", tok):
            tok = tok.replace(".", "")
        try:
            v = float(tok)
            if v > 0:
                vals.add(v)
        except ValueError:
            continue
    sorted_vals = sorted(vals)
    if not sorted_vals:
        raise ValueError(i18n.tr("msg_enter_thresholds"))
    if len(sorted_vals) > MAX_THRESHOLDS:
        raise ValueError(i18n.tr("msg_max_thresholds", count=MAX_THRESHOLDS))
    return sorted_vals


class GreenAccessDialog(QDialog):
    """QGIS Dialog supporting 5-language runtime switching and non-blocking background analysis."""

    def __init__(self, iface: Any, parent: Optional[QWidget] = None):
        super(GreenAccessDialog, self).__init__(parent or (iface.mainWindow() if iface else None))
        self.iface = iface
        self._task: Optional[AnalysisTask] = None
        self._t_start = 0.0
        self._calc_crs = None
        self._crs_note = ""
        self._params: Optional[dict] = None
        self._current_lang = i18n.DEFAULT_LANGUAGE

        self._build_ui()
        self._load_settings()
        self._apply_translations()

    def _tr(self, key: str, **kwargs) -> str:
        return i18n.tr(key, lang=self._current_lang, **kwargs)

    # ==================================================================
    # UI Setup
    # ==================================================================
    def _build_ui(self) -> None:
        self.resize(580, 750)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)

        # Header with Language Selector
        header_layout = QHBoxLayout()
        self.lbl_title_box = QLabel()
        self.lbl_title_box.setTextFormat(Qt.TextFormat.RichText if hasattr(Qt, "TextFormat") else Qt.RichText)
        header_layout.addWidget(self.lbl_title_box, 1)

        # Language dropdown
        self.cmb_lang = QComboBox()
        self.cmb_lang.setObjectName("langSelector")
        for code, label in i18n.LANGUAGES.items():
            self.cmb_lang.addItem(label, code)
        self.cmb_lang.currentIndexChanged.connect(self._on_language_changed)
        header_layout.addWidget(self.cmb_lang)
        root.addLayout(header_layout)

        # Main Tabs
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tab_data = self._create_data_tab()
        self.tab_adv = self._create_advanced_tab()
        self.tab_rep = self._create_report_tab()

        self.tabs.addTab(self.tab_data, "")
        self.tabs.addTab(self.tab_adv, "")
        self.tabs.addTab(self.tab_rep, "")

        # Progress and status
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        root.addWidget(self.progress)
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setObjectName("statusHint")
        root.addWidget(self.lbl_status)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        self.btn_about = QPushButton()
        self.btn_about.clicked.connect(self._on_about_clicked)
        self.btn_close = QPushButton()
        self.btn_close.clicked.connect(self.close)

        self.btn_run = QPushButton()
        self.btn_run.setObjectName("runButton")
        self.btn_run.setProperty("running", False)
        self.btn_run.clicked.connect(self._on_run_clicked)

        btn_layout.addWidget(self.btn_about)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_close)
        btn_layout.addWidget(self.btn_run, 1)
        root.addLayout(btn_layout)

    def _create_data_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        self.grp_layers = QGroupBox()
        f = QFormLayout(self.grp_layers)

        self.cmb_roads = QgsMapLayerComboBox()
        self.cmb_roads.setFilters(layer_filter("LineLayer"))

        self.cmb_parks = QgsMapLayerComboBox()
        self.cmb_parks.setFilters(layer_filter("PolygonLayer"))

        self.cmb_buildings = QgsMapLayerComboBox()
        self.cmb_buildings.setFilters(layer_filter("PolygonLayer", "PointLayer"))
        self.cmb_buildings.setAllowEmptyLayer(True)
        self.cmb_buildings.setLayer(None)

        self.cmb_weight = QgsFieldComboBox()
        self.cmb_weight.setAllowEmptyFieldName(True)
        self.cmb_buildings.layerChanged.connect(self.cmb_weight.setLayer)
        self.cmb_weight.setLayer(self.cmb_buildings.currentLayer())

        self.chk_selected = QCheckBox()

        self.lbl_roads = QLabel()
        self.lbl_parks = QLabel()
        self.lbl_buildings = QLabel()
        self.lbl_weight = QLabel()

        f.addRow(self.lbl_roads, self.cmb_roads)
        f.addRow(self.lbl_parks, self.cmb_parks)
        f.addRow(self.lbl_buildings, self.cmb_buildings)
        f.addRow(self.lbl_weight, self.cmb_weight)
        f.addRow(self.chk_selected)
        lay.addWidget(self.grp_layers)

        self.grp_thresholds = QGroupBox()
        v = QVBoxLayout(self.grp_thresholds)
        self.txt_distances = QLineEdit("300, 500, 1000")
        v.addWidget(self.txt_distances)

        # Quick preset buttons (e.g. 500m, 300-500-1000, 400-800-1200 PlanX / PLN311 standard)
        pr = QHBoxLayout()
        for label, text in (
            ("500 m", "500"),
            ("300 · 500 · 1000 m", "300, 500, 1000"),
            ("400 · 800 · 1200 m (5-10-15 min)", "400, 800, 1200"),
            ("250 · 500 · 750 · 1000 m", "250, 500, 750, 1000"),
        ):
            b = QPushButton(label)
            b.setObjectName("presetButton")
            b.clicked.connect(lambda _=False, t=text: self.txt_distances.setText(t))
            pr.addWidget(b)
        pr.addStretch(1)
        v.addLayout(pr)

        self.lbl_thresholds_hint = QLabel()
        self.lbl_thresholds_hint.setObjectName("statusHint")
        v.addWidget(self.lbl_thresholds_hint)
        lay.addWidget(self.grp_thresholds)
        lay.addStretch(1)

        self._guess_layers()
        return w

    def _spin(self, lo: float, hi: float, val: float, decimals: int = 0, suffix: str = "", step: float = 1.0) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setDecimals(decimals)
        s.setRange(lo, hi)
        s.setValue(val)
        s.setSingleStep(step)
        if suffix:
            s.setSuffix(suffix)
        return s

    def _create_advanced_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        # Network Repair Group
        self.grp_repair = QGroupBox()
        f_rep = QFormLayout(self.grp_repair)
        self.spn_gap = self._spin(0, 100, 15, 0, " m")
        self.chk_disc = QCheckBox()
        self.chk_disc.setChecked(True)
        self.chk_node = QCheckBox()
        self.lbl_gap = QLabel()
        f_rep.addRow(self.lbl_gap, self.spn_gap)
        f_rep.addRow(self.chk_disc)
        f_rep.addRow(self.chk_node)
        lay.addWidget(self.grp_repair)

        # Park Entry & Snapping
        self.grp_entry = QGroupBox()
        f_ent = QFormLayout(self.grp_entry)
        self.cmb_origin = QComboBox()
        self.cmb_origin.addItem("Centroid", "centroid")
        self.cmb_origin.addItem("Entire boundary", "boundary")
        self.spn_snap = self._spin(10, 2000, 200, 0, " m")
        self.spn_area = self._spin(0, 1e7, 0, 0, " m²", 100)
        self.chk_offset = QCheckBox()
        self.chk_offset.setChecked(True)

        self.lbl_entry_mode = QLabel()
        self.lbl_snap = QLabel()
        self.lbl_area = QLabel()
        f_ent.addRow(self.lbl_entry_mode, self.cmb_origin)
        f_ent.addRow(self.lbl_snap, self.spn_snap)
        f_ent.addRow(self.lbl_area, self.spn_area)
        f_ent.addRow(self.chk_offset)
        lay.addWidget(self.grp_entry)

        # Outputs & Catchments
        self.grp_outputs = QGroupBox()
        f_out = QFormLayout(self.grp_outputs)
        self.chk_poly = QCheckBox()
        self.chk_poly.setChecked(True)
        self.spn_buf = self._spin(1, 500, 25, 0, " m")
        self.chk_circ = QCheckBox()
        self.chk_circ.setChecked(True)
        self.chk_debug = QCheckBox()
        self.chk_debug.setChecked(True)
        self.spn_speed = self._spin(1.0, 10.0, 4.8, 1, " km/h", 0.1)

        self.lbl_buf = QLabel()
        self.lbl_speed = QLabel()
        f_out.addRow(self.chk_poly)
        f_out.addRow(self.lbl_buf, self.spn_buf)
        f_out.addRow(self.chk_circ)
        f_out.addRow(self.chk_debug)
        f_out.addRow(self.lbl_speed, self.spn_speed)
        lay.addWidget(self.grp_outputs)

        self.chk_poly.toggled.connect(self.spn_buf.setEnabled)
        lay.addStretch(1)
        return w

    def _create_report_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.txt_report = QTextBrowser()
        self.txt_report.setOpenExternalLinks(True)
        lay.addWidget(self.txt_report, 1)

        self.btn_save_report = QPushButton()
        self.btn_save_report.clicked.connect(self._save_report)
        lay.addWidget(self.btn_save_report, 0, align_right())
        return w

    # ==================================================================
    # Multilingual & Translation Updates
    # ==================================================================
    def _on_language_changed(self, index: int) -> None:
        self._current_lang = self.cmb_lang.itemData(index)
        self._apply_translations()
        # Re-render report if results exist
        if self._task is not None and self._task.result_data is not None:
            html = report.build_report_html(
                self._task.result_data, self._params or {}, self._task.elapsed, self._crs_note, lang=self._current_lang
            )
            self.txt_report.setHtml(html)
        elif not self.txt_report.toPlainText().strip():
            self.txt_report.setHtml(self._tr("no_report_yet"))

    def _apply_translations(self) -> None:
        _t = self._tr
        self.setWindowTitle(_t("plugin_title"))

        title_html = (
            f"<b style='font-size:15px;color:#0f172a'>{_t('plugin_title')}</b><br>"
            f"<span style='color:#64748b;font-size:12px'>{_t('plugin_subtitle')}</span>"
        )
        self.lbl_title_box.setText(title_html)

        # Tabs
        self.tabs.setTabText(0, _t("tab_data"))
        self.tabs.setTabText(1, _t("tab_advanced"))
        self.tabs.setTabText(2, _t("tab_report"))

        # Data Tab
        self.grp_layers.setTitle(_t("layers_group"))
        self.lbl_roads.setText(_t("roads_layer"))
        self.lbl_parks.setText(_t("parks_layer"))
        self.lbl_buildings.setText(_t("buildings_layer"))
        self.lbl_weight.setText(_t("weight_field"))
        self.cmb_weight.setToolTip(_t("weight_field_tip"))
        self.chk_selected.setText(_t("use_selected"))

        self.grp_thresholds.setTitle(_t("thresholds_group"))
        self.lbl_thresholds_hint.setText(_t("thresholds_tip"))

        # Advanced Tab
        self.grp_repair.setTitle(_t("network_repair_group"))
        self.lbl_gap.setText(_t("gap_tolerance"))
        self.spn_gap.setToolTip(_t("gap_tolerance_tip"))
        self.chk_disc.setText(_t("only_disconnected"))
        self.chk_disc.setToolTip(_t("only_disconnected_tip"))
        self.chk_node.setText(_t("node_crossings"))
        self.chk_node.setToolTip(_t("node_crossings_tip"))

        self.grp_entry.setTitle(_t("park_entry_group"))
        self.lbl_entry_mode.setText(_t("entry_mode"))
        cur_origin = self.cmb_origin.currentData()
        self.cmb_origin.clear()
        self.cmb_origin.addItem(_t("entry_centroid"), "centroid")
        self.cmb_origin.addItem(_t("entry_boundary"), "boundary")
        idx = self.cmb_origin.findData(cur_origin)
        self.cmb_origin.setCurrentIndex(max(0, idx))

        self.lbl_snap.setText(_t("max_snap"))
        self.spn_snap.setToolTip(_t("max_snap_tip"))
        self.lbl_area.setText(_t("min_park_area"))
        self.spn_area.setToolTip(_t("min_park_area_tip"))
        self.chk_offset.setText(_t("include_snap_offset"))

        self.grp_outputs.setTitle(_t("outputs_group"))
        self.chk_poly.setText(_t("generate_polygons"))
        self.lbl_buf.setText(_t("polygon_buffer"))
        self.spn_buf.setToolTip(_t("polygon_buffer_tip"))
        self.chk_circ.setText(_t("generate_circles"))
        self.chk_debug.setText(_t("add_debug"))
        self.lbl_speed.setText(_t("walking_speed"))

        # Buttons & Status
        self.btn_about.setText(_t("btn_about"))
        self.btn_close.setText(_t("btn_close"))
        self.btn_save_report.setText(_t("btn_save_report"))
        is_running = self.btn_run.property("running")
        self.btn_run.setText(_t("btn_cancel") if is_running else _t("btn_run"))
        if not is_running:
            self.lbl_status.setText(_t("status_ready"))

        if not self.txt_report.toPlainText().strip() or "Henüz analiz" in self.txt_report.toPlainText():
            self.txt_report.setHtml(_t("no_report_yet"))

    # ==================================================================
    # Settings & Layer Helpers
    # ==================================================================
    def _guess_layers(self) -> None:
        hints = (
            (self.cmb_roads, ("yol", "road", "street", "highway", "ulasim", "network")),
            (self.cmb_parks, ("yesil", "yeşil", "park", "green", "acik_alan")),
            (self.cmb_buildings, ("bina", "konut", "building", "yapi", "residential")),
        )
        for combo, words in hints:
            for i in range(combo.count()):
                lyr = combo.layer(i)
                if lyr is not None and any(k in lyr.name().lower() for k in words):
                    combo.setLayer(lyr)
                    break

    def _load_settings(self) -> None:
        s = QSettings()
        g = lambda k, d: s.value(SETTINGS_PREFIX + k, d)
        saved_lang = str(g("language", i18n.DEFAULT_LANGUAGE))
        idx = self.cmb_lang.findData(saved_lang)
        if idx >= 0:
            self.cmb_lang.setCurrentIndex(idx)
            self._current_lang = saved_lang

        self.txt_distances.setText(str(g("distances", self.txt_distances.text())))
        self.spn_gap.setValue(float(g("gap", 15)))
        self.chk_disc.setChecked(str(g("only_disc", "true")).lower() == "true")
        self.chk_node.setChecked(str(g("node", "false")).lower() == "true")
        origin_val = str(g("origin", "centroid"))
        o_idx = self.cmb_origin.findData(origin_val)
        if o_idx >= 0:
            self.cmb_origin.setCurrentIndex(o_idx)
        self.spn_snap.setValue(float(g("snap", 200)))
        self.spn_area.setValue(float(g("min_area", 0)))
        self.chk_offset.setChecked(str(g("offset", "true")).lower() == "true")
        self.chk_poly.setChecked(str(g("poly", "true")).lower() == "true")
        self.spn_buf.setValue(float(g("buf", 25)))
        self.chk_circ.setChecked(str(g("circ", "true")).lower() == "true")
        self.chk_debug.setChecked(str(g("debug", "true")).lower() == "true")
        self.spn_speed.setValue(float(g("speed", 4.8)))
        self.chk_selected.setChecked(str(g("selected", "false")).lower() == "true")

    def _save_settings(self) -> None:
        s = QSettings()
        b = lambda v: "true" if v else "false"
        items = (
            ("language", self._current_lang),
            ("distances", self.txt_distances.text()),
            ("gap", self.spn_gap.value()),
            ("only_disc", b(self.chk_disc.isChecked())),
            ("node", b(self.chk_node.isChecked())),
            ("origin", self.cmb_origin.currentData()),
            ("snap", self.spn_snap.value()),
            ("min_area", self.spn_area.value()),
            ("offset", b(self.chk_offset.isChecked())),
            ("poly", b(self.chk_poly.isChecked())),
            ("buf", self.spn_buf.value()),
            ("circ", b(self.chk_circ.isChecked())),
            ("debug", b(self.chk_debug.isChecked())),
            ("speed", self.spn_speed.value()),
            ("selected", b(self.chk_selected.isChecked())),
        )
        for k, v in items:
            s.setValue(SETTINGS_PREFIX + k, v)

    def _warn(self, text: str) -> None:
        QMessageBox.warning(self, self._tr("plugin_title"), text)

    def _on_about_clicked(self) -> None:
        QMessageBox.information(
            self,
            self._tr("about_title"),
            self._tr("about_body", PLUGIN_VERSION),
        )

    def _save_report(self) -> None:
        path, _flt = QFileDialog.getSaveFileName(
            self,
            self._tr("save_report_title"),
            "green_space_accessibility_report.html",
            self._tr("save_report_filter"),
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                if path.lower().endswith(".txt"):
                    fh.write(self.txt_report.toPlainText())
                else:
                    fh.write(
                        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                        "<title>Green Space Accessibility Report</title></head><body>"
                        f"{self.txt_report.toHtml()}</body></html>"
                    )
        except OSError as exc:
            self._warn(f"Failed to save report:\n{exc}")

    def _set_running(self, running: bool) -> None:
        self.btn_run.setText(self._tr("btn_cancel") if running else self._tr("btn_run"))
        self.btn_run.setProperty("running", running)
        self.btn_run.style().unpolish(self.btn_run)
        self.btn_run.style().polish(self.btn_run)
        self.tabs.setEnabled(not running)
        self.cmb_lang.setEnabled(not running)

    def cancel_running(self) -> None:
        if self._task is not None:
            self._task.cancel()

    # ==================================================================
    # Execution Workflow
    # ==================================================================
    def _on_run_clicked(self) -> None:
        if self._task is not None:
            self.lbl_status.setText(self._tr("status_cancelling"))
            self._task.cancel()
            return
        self._start()

    def _start(self) -> None:
        try:
            thresholds = parse_thresholds(self.txt_distances.text())
        except ValueError as exc:
            self._warn(str(exc))
            return

        r_layer = self.cmb_roads.currentLayer()
        g_layer = self.cmb_parks.currentLayer()
        b_layer = self.cmb_buildings.currentLayer()

        if r_layer is None or g_layer is None:
            self._warn(self._tr("msg_select_layers"))
            return

        project = QgsProject.instance()
        self._calc_crs, self._crs_note = choose_calc_crs(r_layer, project)

        def make_input(layer: Any, field: Optional[str] = None) -> dict:
            use_sel = self.chk_selected.isChecked() and layer.selectedFeatureCount() > 0
            return {
                "source": QgsVectorLayerFeatureSource(layer),
                "fids": list(layer.selectedFeatureIds()) if use_sel else None,
                "field": field,
            }

        weight_field = self.cmb_weight.currentField() if b_layer is not None else ""
        inputs = {"roads": make_input(r_layer), "parks": make_input(g_layer)}
        if b_layer is not None:
            inputs["buildings"] = make_input(b_layer, weight_field or None)

        params = {
            "thresholds": thresholds,
            "gap_tol": self.spn_gap.value(),
            "only_disconnected": self.chk_disc.isChecked(),
            "node_crossings": self.chk_node.isChecked(),
            "origin_mode": self.cmb_origin.currentData(),
            "max_snap": self.spn_snap.value(),
            "min_area": self.spn_area.value(),
            "include_offset": self.chk_offset.isChecked(),
            "speed_kmh": self.spn_speed.value(),
            "generate_polygons": self.chk_poly.isChecked(),
            "polygon_buffer": self.spn_buf.value(),
            "generate_circles": self.chk_circ.isChecked(),
            "add_debug": self.chk_debug.isChecked(),
            "use_weight": bool(weight_field),
            "weight_label": weight_field,
        }
        self._params = params
        self._save_settings()

        self._task = AnalysisTask(
            inputs, params, self._calc_crs, project.transformContext(), lang=self._current_lang
        )
        self._task.status_message.connect(self.lbl_status.setText)
        self._task.progressChanged.connect(lambda p: self.progress.setValue(int(p)))
        self._task.finished_signal.connect(self._on_finished)
        self._t_start = time.time()
        self.progress.setValue(0)
        self.lbl_status.setText(self._tr("status_running"))
        self._set_running(True)
        QgsApplication.taskManager().addTask(self._task)

    def _on_finished(self, ok: bool) -> None:
        task = self._task
        self._task = None
        self._set_running(False)
        if task is None:
            return

        if ok and task.result_data is not None:
            try:
                self.lbl_status.setText(self._tr("status_generating_layers"))
                QgsApplication.processEvents()
                group_title = f"{self._tr('plugin_title')} – {time.strftime('%H:%M:%S')}"
                build_layers(
                    task.result_data,
                    self._params or {},
                    self._calc_crs,
                    QgsProject.instance(),
                    group_title,
                    lang=self._current_lang,
                )
                html = report.build_report_html(
                    task.result_data,
                    self._params or {},
                    task.elapsed,
                    self._crs_note,
                    lang=self._current_lang,
                )
                self.txt_report.setHtml(html)
                self.tabs.setCurrentIndex(2)
                self.progress.setValue(100)
                self.lbl_status.setText(self._tr("status_completed", task.elapsed))
                if self.iface:
                    self.iface.messageBar().pushSuccess(
                        self._tr("plugin_title"),
                        self._tr("msg_completed_bar", group_title),
                    )
            except Exception as exc:
                import traceback
                log(traceback.format_exc())
                self.lbl_status.setText(self._tr("status_error"))
                self._warn(f"Error creating map layers:\n{exc}")
        elif task.isCanceled():
            self.progress.setValue(0)
            self.lbl_status.setText(self._tr("status_cancelled"))
        else:
            self.progress.setValue(0)
            self.lbl_status.setText(self._tr("status_error"))
            if task.error:
                log(task.error)
                last_line = task.error.strip().splitlines()[-1]
                self._warn(f"Analysis error:\n{last_line}\n\n(See QGIS Log Messages panel)")
            else:
                self._warn(self._tr("status_error"))

    def closeEvent(self, event: Any) -> None:
        super(GreenAccessDialog, self).closeEvent(event)
