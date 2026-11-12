# -*- coding: utf-8 -*-
"""
Aesthetic, Responsive & Dockable GUI Panel for Green Space Accessibility & Pedshed Analysis.
Author / Developer: Baran Adsuna (https://github.com/baranadsuna)
CRS Standard: EPSG:5253 (TUREF / TM30)
Dual Compatible: QGIS 3.22+ and QGIS 4.x (Qt5 & Qt6)

Features:
  - Dockable panel (QDockWidget) dockable to Left, Right, Floating, or Tabbed in QGIS.
  - High-aesthetic card layout, emerald gradient banner, and responsive QScrollArea.
  - Dynamic 5-language runtime switching (EN, TR, ZH, ES, ID).
  - Quick-preset threshold pills and non-blocking background QgsTask execution.
"""
from __future__ import annotations

import os
import re
import time
from typing import Any, List, Optional

from qgis.PyQt.QtCore import QSettings, Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsApplication, QgsProject, QgsVectorLayerFeatureSource
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox

from . import i18n, report
from .analysis_task import AnalysisTask, choose_calc_crs, log
from .compat import align_right, dock_all_areas, layer_filter
from .outputs import build_layers

PLUGIN_VERSION = "5.1.0"
SETTINGS_PREFIX = "GreenSpaceAccessibility/"
MAX_THRESHOLDS = 10

STYLE = """
QDockWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #1e293b;
    font-size: 11.5px;
}
QDockWidget::title {
    text-align: left;
    background: #064e3b;
    color: #f8fafc;
    padding: 6px 10px;
    font-weight: 600;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QFrame#headerCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #022c22, stop:0.45 #064e3b, stop:1 #047857);
    border: 1px solid #059669;
    border-radius: 10px;
    padding: 10px 12px;
    margin-bottom: 4px;
}
QLabel#appTitle {
    color: #ffffff;
    font-weight: bold;
    font-size: 13.5px;
}
QLabel#appSubtitle {
    color: #a7f3d0;
    font-size: 11px;
}
QLabel#badgePill {
    background: rgba(16, 185, 129, 0.25);
    border: 1px solid #34d399;
    color: #d1fae5;
    font-size: 9.5px;
    font-weight: bold;
    padding: 2px 7px;
    border-radius: 10px;
}
QLabel#crsPill {
    background: rgba(56, 189, 248, 0.2);
    border: 1px solid #38bdf8;
    color: #e0f2fe;
    font-size: 9.5px;
    font-weight: bold;
    padding: 2px 7px;
    border-radius: 10px;
}
QComboBox#langSelector {
    background: #ffffff;
    border: 1px solid #6ee7b7;
    border-radius: 12px;
    padding: 2px 10px;
    font-weight: bold;
    color: #064e3b;
    font-size: 11px;
}
QTabWidget::pane {
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    background: #ffffff;
    padding: 4px;
}
QTabBar::tab {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 12px;
    margin-right: 3px;
    font-size: 11px;
    color: #64748b;
}
QTabBar::tab:selected {
    background: #ffffff;
    border-bottom: 2px solid #10b981;
    color: #047857;
    font-weight: bold;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 12px;
    background-color: #fafbfc;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #0f172a;
    font-size: 11.5px;
}
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px 8px;
    background: #ffffff;
    min-height: 22px;
    color: #0f172a;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid #10b981;
    background: #ffffff;
}
QPushButton#presetButton {
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 11px;
    padding: 3px 8px;
    font-size: 10px;
    color: #334155;
}
QPushButton#presetButton:hover {
    background: #ecfdf5;
    border-color: #10b981;
    color: #047857;
}
QPushButton#runButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
    color: #ffffff;
    font-weight: bold;
    font-size: 13px;
    padding: 9px 18px;
    border-radius: 8px;
    border: none;
}
QPushButton#runButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
}
QPushButton#runButton[running="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #dc2626);
}
QPushButton#secondaryBtn {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 11px;
    color: #334155;
}
QPushButton#secondaryBtn:hover {
    background: #e2e8f0;
    color: #0f172a;
}
QProgressBar {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    text-align: center;
    height: 14px;
    font-size: 10px;
    background: #f8fafc;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34d399, stop:1 #10b981);
    border-radius: 5px;
}
QLabel#statusHint {
    color: #64748b;
    font-size: 10.5px;
}
"""


def parse_thresholds(text: str) -> List[float]:
    """Parses comma/semicolon-separated distance thresholds string."""
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


class GreenAccessDockWidget(QDockWidget):
    """
    Modern QGIS Dockable Panel for Green Space Accessibility & Pedshed Analysis.
    Docks smoothly to the Left or Right of QGIS canvas, or floats independently.
    """
    closingPlugin = pyqtSignal()

    def __init__(self, iface: Any, parent: Optional[QWidget] = None):
        super(GreenAccessDockWidget, self).__init__(parent or (iface.mainWindow() if iface else None))
        self.iface = iface
        self.setObjectName("GreenAccessDockWidget")
        self.setAllowedAreas(dock_all_areas())

        self._task: Optional[AnalysisTask] = None
        self._t_start = 0.0
        self._calc_crs = None
        self._crs_note = ""
        self._params: Optional[dict] = None
        self._current_lang = i18n.DEFAULT_LANGUAGE
        self._plugin_dir = os.path.dirname(os.path.abspath(__file__))

        self._build_ui()
        self._load_settings()
        self._apply_translations()

    def _tr(self, key: str, *args, **kwargs) -> str:
        return i18n.tr(key, self._current_lang, *args, **kwargs)

    # ==================================================================
    # UI Setup & Card Architecture
    # ==================================================================
    def _build_ui(self) -> None:
        self.setStyleSheet(STYLE)

        # Scroll area container for responsive narrow sidebar docking
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff if hasattr(Qt, "ScrollBarPolicy") else Qt.ScrollBarAlwaysOff
        )

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # --- Header Card ---
        self.header_card = QFrame()
        self.header_card.setObjectName("headerCard")
        h_lay = QVBoxLayout(self.header_card)
        h_lay.setContentsMargins(6, 6, 6, 6)
        h_lay.setSpacing(6)

        top_row = QHBoxLayout()
        # Plugin Icon
        self.lbl_icon = QLabel()
        icon_path = os.path.join(self._plugin_dir, "icon.png")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(
                36, 36,
                Qt.AspectRatioMode.KeepAspectRatio if hasattr(Qt, "AspectRatioMode") else Qt.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation if hasattr(Qt, "TransformationMode") else Qt.SmoothTransformation
            )
            self.lbl_icon.setPixmap(pix)
        top_row.addWidget(self.lbl_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)
        self.lbl_app_title = QLabel("Green Space Accessibility")
        self.lbl_app_title.setObjectName("appTitle")
        self.lbl_app_subtitle = QLabel("Network Walkability & Pedshed Suite")
        self.lbl_app_subtitle.setObjectName("appSubtitle")
        title_vbox.addWidget(self.lbl_app_title)
        title_vbox.addWidget(self.lbl_app_subtitle)
        top_row.addLayout(title_vbox, 1)

        # Language dropdown
        self.cmb_lang = QComboBox()
        self.cmb_lang.setObjectName("langSelector")
        for code, label in i18n.LANGUAGES.items():
            self.cmb_lang.addItem(label, code)
        self.cmb_lang.currentIndexChanged.connect(self._on_language_changed)
        top_row.addWidget(self.cmb_lang)
        h_lay.addLayout(top_row)

        # Badges row (Version + Mandatory CRS Standard)
        badge_row = QHBoxLayout()
        self.badge_ver = QLabel(f"v{PLUGIN_VERSION}")
        self.badge_ver.setObjectName("badgePill")
        self.badge_crs = QLabel("CRS: EPSG:5253")
        self.badge_crs.setObjectName("crsPill")
        badge_row.addWidget(self.badge_ver)
        badge_row.addWidget(self.badge_crs)
        badge_row.addStretch(1)
        h_lay.addLayout(badge_row)

        root.addWidget(self.header_card)

        # --- Main Tabbed Panels ---
        self.tabs = QTabWidget()
        self.tabs.setObjectName("modernTabs")
        root.addWidget(self.tabs, 1)

        self.tab_data = self._create_data_tab()
        self.tab_adv = self._create_advanced_tab()
        self.tab_rep = self._create_report_tab()

        self.tabs.addTab(self.tab_data, "Data")
        self.tabs.addTab(self.tab_adv, "Advanced")
        self.tabs.addTab(self.tab_rep, "Report")

        # --- Progress Bar & Status Pill ---
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        root.addWidget(self.progress)

        self.lbl_status = QLabel("Ready")
        self.lbl_status.setObjectName("statusHint")
        root.addWidget(self.lbl_status)

        # --- Sticky Bottom Action Bar ---
        action_row = QHBoxLayout()
        self.btn_about = QPushButton()
        self.btn_about.setObjectName("secondaryBtn")
        self.btn_about.clicked.connect(self._on_about_clicked)

        self.btn_run = QPushButton()
        self.btn_run.setObjectName("runButton")
        self.btn_run.setProperty("running", False)
        self.btn_run.clicked.connect(self._on_run_clicked)

        action_row.addWidget(self.btn_about)
        action_row.addStretch(1)
        action_row.addWidget(self.btn_run, 2)
        root.addLayout(action_row)

        self.scroll_area.setWidget(container)
        self.setWidget(self.scroll_area)

    def _create_data_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        # Layer Selection Card
        self.grp_layers = QGroupBox()
        f = QFormLayout(self.grp_layers)
        f.setContentsMargins(8, 12, 8, 8)
        f.setSpacing(6)

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

        # Distance Thresholds Card
        self.grp_thresholds = QGroupBox()
        v = QVBoxLayout(self.grp_thresholds)
        v.setContentsMargins(8, 12, 8, 8)
        v.setSpacing(6)

        self.txt_distances = QLineEdit("300, 500, 1000")
        v.addWidget(self.txt_distances)

        # Quick preset buttons (e.g. 500m, 300-500-1000, 400-800-1200 PlanX / PLN311 standard)
        pr = QHBoxLayout()
        pr.setSpacing(4)
        for label, text in (
            ("500 m", "500"),
            ("300 · 500 · 1000", "300, 500, 1000"),
            ("400 · 800 · 1200 (5-10-15m)", "400, 800, 1200"),
            ("250 · 500 · 750 · 1000", "250, 500, 750, 1000"),
        ):
            b = QPushButton(label)
            b.setObjectName("presetButton")
            b.clicked.connect(lambda _=False, t=text: self.txt_distances.setText(t))
            pr.addWidget(b)
        pr.addStretch(1)
        v.addLayout(pr)

        self.lbl_thresholds_hint = QLabel()
        self.lbl_thresholds_hint.setObjectName("statusHint")
        self.lbl_thresholds_hint.setWordWrap(True)
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
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(8)

        # Network Gap Repair Card
        self.grp_repair = QGroupBox()
        f_rep = QFormLayout(self.grp_repair)
        f_rep.setContentsMargins(8, 12, 8, 8)
        self.spn_gap = self._spin(0, 100, 15, 0, " m")
        self.chk_disc = QCheckBox()
        self.chk_disc.setChecked(True)
        self.chk_node = QCheckBox()
        self.lbl_gap = QLabel()
        f_rep.addRow(self.lbl_gap, self.spn_gap)
        f_rep.addRow(self.chk_disc)
        f_rep.addRow(self.chk_node)
        lay.addWidget(self.grp_repair)

        # Park Access & Snapping Card
        self.grp_entry = QGroupBox()
        f_ent = QFormLayout(self.grp_entry)
        f_ent.setContentsMargins(8, 12, 8, 8)
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

        # Outputs & Catchments Card
        self.grp_outputs = QGroupBox()
        f_out = QFormLayout(self.grp_outputs)
        f_out.setContentsMargins(8, 12, 8, 8)
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
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        self.txt_report = QTextBrowser()
        self.txt_report.setOpenExternalLinks(True)
        lay.addWidget(self.txt_report, 1)

        self.btn_save_report = QPushButton()
        self.btn_save_report.setObjectName("secondaryBtn")
        self.btn_save_report.clicked.connect(self._save_report)
        lay.addWidget(self.btn_save_report, 0, align_right())
        return w

    # ==================================================================
    # Multilingual & Translation Updates
    # ==================================================================
    def _on_language_changed(self, index: int) -> None:
        self._current_lang = self.cmb_lang.itemData(index)
        self._apply_translations()
        if self._task is not None and self._task.result_data is not None:
            html = report.build_report_html(
                self._task.result_data, self._params or {}, self._task.elapsed, self._crs_note, lang=self._current_lang
            )
            self.txt_report.setHtml(html)
        elif not self.txt_report.toPlainText().strip() or "Henüz" in self.txt_report.toPlainText() or "No analysis" in self.txt_report.toPlainText():
            self.txt_report.setHtml(self._tr("no_report_yet"))

    def _apply_translations(self) -> None:
        _t = self._tr
        self.setWindowTitle(_t("plugin_title"))
        self.lbl_app_title.setText(_t("plugin_title"))
        self.lbl_app_subtitle.setText(_t("plugin_subtitle"))

        # Tabs
        self.tabs.setTabText(0, f"📊 {_t('tab_data')}")
        self.tabs.setTabText(1, f"⚙️ {_t('tab_advanced')}")
        self.tabs.setTabText(2, f"📑 {_t('tab_report')}")

        # Data Tab
        self.grp_layers.setTitle(f"🗺️ {_t('layers_group')}")
        self.lbl_roads.setText(_t("roads_layer"))
        self.lbl_parks.setText(_t("parks_layer"))
        self.lbl_buildings.setText(_t("buildings_layer"))
        self.lbl_weight.setText(_t("weight_field"))
        self.cmb_weight.setToolTip(_t("weight_field_tip"))
        self.chk_selected.setText(_t("use_selected"))

        self.grp_thresholds.setTitle(f"🚶 {_t('thresholds_group')}")
        self.lbl_thresholds_hint.setText(_t("thresholds_tip"))

        # Advanced Tab
        self.grp_repair.setTitle(f"🔧 {_t('network_repair_group')}")
        self.lbl_gap.setText(_t("gap_tolerance"))
        self.spn_gap.setToolTip(_t("gap_tolerance_tip"))
        self.chk_disc.setText(_t("only_disconnected"))
        self.chk_disc.setToolTip(_t("only_disconnected_tip"))
        self.chk_node.setText(_t("node_crossings"))
        self.chk_node.setToolTip(_t("node_crossings_tip"))

        self.grp_entry.setTitle(f"🌳 {_t('park_entry_group')}")
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

        self.grp_outputs.setTitle(f"📐 {_t('outputs_group')}")
        self.chk_poly.setText(_t("generate_polygons"))
        self.lbl_buf.setText(_t("polygon_buffer"))
        self.spn_buf.setToolTip(_t("polygon_buffer_tip"))
        self.chk_circ.setText(_t("generate_circles"))
        self.chk_debug.setText(_t("add_debug"))
        self.lbl_speed.setText(_t("walking_speed"))

        # Buttons & Status
        self.btn_about.setText(f"ℹ️ {_t('btn_about')}")
        self.btn_save_report.setText(f"💾 {_t('btn_save_report')}")
        is_running = self.btn_run.property("running")
        self.btn_run.setText(_t("btn_cancel") if is_running else f"▶ {_t('btn_run')}")
        if not is_running:
            self.lbl_status.setText(f"🟢 {_t('status_ready')}")

        if not self.txt_report.toPlainText().strip() or "Henüz" in self.txt_report.toPlainText():
            self.txt_report.setHtml(_t("no_report_yet"))

    # ==================================================================
    # Layer Auto-Detection & QSettings
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
        self.btn_run.setText(self._tr("btn_cancel") if running else f"▶ {self._tr('btn_run')}")
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
            self.lbl_status.setText(f"⏳ {self._tr('status_cancelling')}")
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
        self.lbl_status.setText(f"⏳ {self._tr('status_running')}")
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
                self.lbl_status.setText(f"📦 {self._tr('status_generating_layers')}")
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
                self.lbl_status.setText(f"✅ {self._tr('status_completed', task.elapsed)}")
                if self.iface:
                    self.iface.messageBar().pushSuccess(
                        self._tr("plugin_title"),
                        self._tr("msg_completed_bar", group_title),
                    )
            except Exception as exc:
                import traceback
                log(traceback.format_exc())
                self.lbl_status.setText(f"❌ {self._tr('status_error')}")
                self._warn(f"Error creating map layers:\n{exc}")
        elif task.isCanceled():
            self.progress.setValue(0)
            self.lbl_status.setText(f"⚠️ {self._tr('status_cancelled')}")
        else:
            self.progress.setValue(0)
            self.lbl_status.setText(f"❌ {self._tr('status_error')}")
            if task.error:
                log(task.error)
                last_line = task.error.strip().splitlines()[-1]
                self._warn(f"Analysis error:\n{last_line}\n\n(See QGIS Log Messages panel)")
            else:
                self._warn(self._tr("status_error"))

    def closeEvent(self, event: Any) -> None:
        self.closingPlugin.emit()
        event.accept()


# Compatibility alias for legacy imports
GreenAccessDialog = GreenAccessDockWidget
