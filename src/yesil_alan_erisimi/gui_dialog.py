# -*- coding: utf-8 -*-
"""
Simple, Aesthetic & Smoothly Dockable GUI Panel for Accessibility Analysis (Erişim Analizi).
Author / Developer: Baran Adsuna (https://github.com/baranadsuna)
CRS Standard: EPSG:5253 (TUREF / TM30)
Dual Compatible: QGIS 3.22+ and QGIS 4.x (Qt5 & Qt6)

Key Features:
  - Reduced 18px outer-edge snap threshold + one-click [⬅ Left | 🪟 Float | Right ➡] buttons
    so the panel never snaps accidentally while moving across the screen.
  - Warm Terracotta & Amber-Bronze architectural theme (non-blue, ultra-clean & simple).
  - Universal facility support (Schools, Parks, Health, Transit, etc. — Point or Polygon).
  - Closest road-facing facade connection for residential blocks/buildings.
  - Dynamic 5-language runtime switching (TR, EN, ZH, ES, ID).
"""
from __future__ import annotations

import os
import re
import time
from typing import Any, List, Optional

from qgis.PyQt.QtCore import QSettings, Qt, pyqtSignal
from qgis.PyQt.QtGui import QCursor, QPixmap
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
    QSizePolicy,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsApplication, QgsProject, QgsVectorLayerFeatureSource
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox

from . import i18n, report
from .analysis_task import AnalysisTask, choose_calc_crs, log
from .compat import align_right, dock_left, dock_left_right, dock_none, dock_right, layer_filter
from .outputs import build_layers

PLUGIN_VERSION = "5.3.0"
SETTINGS_PREFIX = "UrbanAccessibilityAnalysis_v53/"
MAX_THRESHOLDS = 10
SNAP_EDGE_MARGIN_PX = 18  # Only snap when dragged within 18px of extreme outer left/right edge

STYLE = """
QDockWidget, QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    color: #1c1917;
    font-size: 11px;
}
QDockWidget::title {
    text-align: left;
    background: #7c2d12;
    color: #fafaf9;
    padding: 5px 10px;
    font-weight: 600;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QFrame#headerCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #431407, stop:0.5 #7c2d12, stop:1 #c2410c);
    border: 1px solid #ea580c;
    border-radius: 10px;
    padding: 8px 10px;
    margin-bottom: 2px;
}
QLabel#appTitle {
    color: #ffffff;
    font-weight: bold;
    font-size: 14px;
}
QLabel#appSubtitle {
    color: #fed7aa;
    font-size: 10.5px;
}
QLabel#badgePill {
    background: rgba(251, 146, 60, 0.25);
    border: 1px solid #fb923c;
    color: #ffedd5;
    font-size: 9.5px;
    font-weight: bold;
    padding: 2px 7px;
    border-radius: 9px;
}
QLabel#crsPill {
    background: rgba(245, 158, 11, 0.22);
    border: 1px solid #fbbf24;
    color: #fef3c7;
    font-size: 9.5px;
    font-weight: bold;
    padding: 2px 7px;
    border-radius: 9px;
}
QPushButton#dockBtn {
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(254, 215, 170, 0.45);
    border-radius: 6px;
    color: #fff7ed;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 7px;
}
QPushButton#dockBtn:hover {
    background: rgba(251, 146, 60, 0.45);
    border-color: #fdba74;
    color: #ffffff;
}
QComboBox#langSelector {
    background: #fff7ed;
    border: 1px solid #fdba74;
    border-radius: 10px;
    padding: 2px 8px;
    font-weight: bold;
    color: #7c2d12;
    font-size: 10.5px;
}
QTabWidget::pane {
    border: 1px solid #e7e5e4;
    border-radius: 8px;
    background: #ffffff;
    padding: 4px;
}
QTabBar::tab {
    background: #f5f5f4;
    border: 1px solid #e7e5e4;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 5px 12px;
    margin-right: 3px;
    font-size: 11px;
    color: #57534e;
}
QTabBar::tab:selected {
    background: #ffffff;
    border-bottom: 2px solid #ea580c;
    color: #9a3412;
    font-weight: bold;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #e7e5e4;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 10px;
    background-color: #fafaf9;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #292524;
    font-size: 11px;
}
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
    border: 1px solid #d6d3d1;
    border-radius: 6px;
    padding: 4px 7px;
    background: #ffffff;
    min-height: 21px;
    color: #1c1917;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid #ea580c;
    background: #ffffff;
}
QPushButton#presetButton {
    background: #fafaf9;
    border: 1px solid #d6d3d1;
    border-radius: 10px;
    padding: 3px 8px;
    font-size: 10px;
    color: #44403c;
}
QPushButton#presetButton:hover {
    background: #fff7ed;
    border-color: #ea580c;
    color: #9a3412;
}
QPushButton#runButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ea580c, stop:1 #c2410c);
    color: #ffffff;
    font-weight: bold;
    font-size: 12.5px;
    padding: 8px 16px;
    border-radius: 7px;
    border: none;
}
QPushButton#runButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #c2410c, stop:1 #9a3412);
}
QPushButton#runButton[running="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #dc2626, stop:1 #b91c1c);
}
QPushButton#secondaryBtn {
    background: #f5f5f4;
    border: 1px solid #d6d3d1;
    border-radius: 6px;
    padding: 6px 11px;
    font-size: 11px;
    color: #44403c;
}
QPushButton#secondaryBtn:hover {
    background: #e7e5e4;
    color: #1c1917;
}
QProgressBar {
    border: 1px solid #d6d3d1;
    border-radius: 6px;
    text-align: center;
    height: 13px;
    font-size: 9.5px;
    background: #fafaf9;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fb923c, stop:1 #ea580c);
    border-radius: 5px;
}
QLabel#statusHint {
    color: #57534e;
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
        raise ValueError(i18n.tr("msg_max_thresholds", None, MAX_THRESHOLDS))
    return sorted_vals


class GreenAccessDockWidget(QDockWidget):
    """
    Simple, Responsive & Low-Snap-Threshold Panel for Accessibility Analysis (Erişim Analizi).
    """
    closingPlugin = pyqtSignal()

    def __init__(self, iface: Any, parent: Optional[QWidget] = None):
        super(GreenAccessDockWidget, self).__init__(parent or (iface.mainWindow() if iface else None))
        self.iface = iface
        self.setObjectName("GreenAccessDockWidget")
        # Allow Left & Right docking when explicitly docked, but prevent aggressive snapping when floating
        self.setAllowedAreas(dock_left_right())
        self.topLevelChanged.connect(self._on_floating_changed)

        self._task: Optional[AnalysisTask] = None
        self._t_start = 0.0
        self._calc_crs = None
        self._crs_note = ""
        self._params: Optional[dict] = None
        self._current_lang = "en"
        self._plugin_dir = os.path.dirname(os.path.abspath(__file__))

        self._build_ui()
        self._load_settings()
        self._apply_translations()

    def _tr(self, key: str, *args, **kwargs) -> str:
        return i18n.tr(key, self._current_lang, *args, **kwargs)

    # ==================================================================
    # Reduced Snap Threshold & Explicit Dock Controls
    # ==================================================================
    def _on_floating_changed(self, floating: bool) -> None:
        """When torn off into floating mode, disable aggressive auto-snapping immediately."""
        if floating:
            self.setAllowedAreas(dock_none())

    def moveEvent(self, event: Any) -> None:
        """
        Enforces a tight 18-pixel outer-edge threshold when dragging the floating panel.
        Prevents Qt from snapping to wide sidebars or top/bottom toolbars while moving.
        """
        super(GreenAccessDockWidget, self).moveEvent(event)
        if self.isFloating() and self.iface and self.iface.mainWindow():
            try:
                mw_rect = self.iface.mainWindow().frameGeometry()
                cursor_x = QCursor.pos().x()
                if abs(cursor_x - mw_rect.left()) <= SNAP_EDGE_MARGIN_PX:
                    if self.allowedAreas() != dock_left():
                        self.setAllowedAreas(dock_left())
                elif abs(cursor_x - mw_rect.right()) <= SNAP_EDGE_MARGIN_PX:
                    if self.allowedAreas() != dock_right():
                        self.setAllowedAreas(dock_right())
                else:
                    if self.allowedAreas() != dock_none():
                        self.setAllowedAreas(dock_none())
            except Exception:
                pass

    def _dock_to_left(self) -> None:
        self.setAllowedAreas(dock_left_right())
        self.setFloating(False)
        if self.iface:
            self.iface.addDockWidget(dock_left(), self)
        self.show()

    def _undock_free(self) -> None:
        self.setAllowedAreas(dock_none())
        self.setFloating(True)
        if self.iface and self.iface.mainWindow():
            mw = self.iface.mainWindow().geometry()
            w = max(self.width(), 390)
            h = max(self.height(), 540)
            self.setGeometry(
                mw.center().x() - w // 2,
                mw.center().y() - h // 2,
                w,
                h,
            )
        self.show()
        self.raise_()

    def _dock_to_right(self) -> None:
        self.setAllowedAreas(dock_left_right())
        self.setFloating(False)
        if self.iface:
            self.iface.addDockWidget(dock_right(), self)
        self.show()

    # ==================================================================
    # UI Setup & Clean Card Architecture
    # ==================================================================
    def _build_ui(self) -> None:
        self.setStyleSheet(STYLE)

        outer = QWidget()
        root = QVBoxLayout(outer)
        root.setContentsMargins(7, 7, 7, 7)
        root.setSpacing(5)

        # --- Header Card ---
        self.header_card = QFrame()
        self.header_card.setObjectName("headerCard")
        h_lay = QVBoxLayout(self.header_card)
        h_lay.setContentsMargins(6, 5, 6, 5)
        h_lay.setSpacing(4)

        top_row = QHBoxLayout()
        self.lbl_icon = QLabel()
        icon_path = os.path.join(self._plugin_dir, "icon.png")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(
                34, 34,
                Qt.AspectRatioMode.KeepAspectRatio if hasattr(Qt, "AspectRatioMode") else Qt.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation if hasattr(Qt, "TransformationMode") else Qt.SmoothTransformation
            )
            self.lbl_icon.setPixmap(pix)
        top_row.addWidget(self.lbl_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)
        self.lbl_app_title = QLabel("Accessibility Analysis")
        self.lbl_app_title.setObjectName("appTitle")
        self.lbl_app_subtitle = QLabel("Network Facility & Facade Accessibility Suite")
        self.lbl_app_subtitle.setObjectName("appSubtitle")
        self.lbl_app_subtitle.setWordWrap(True)
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

        # Badges + Quick Dock/Float Bar
        badge_row = QHBoxLayout()
        badge_row.setSpacing(4)
        fixed_pol = (
            QSizePolicy.Policy.Maximum if hasattr(QSizePolicy, "Policy") else QSizePolicy.Maximum
        )
        self.badge_ver = QLabel(f"v{PLUGIN_VERSION}")
        self.badge_ver.setObjectName("badgePill")
        self.badge_ver.setSizePolicy(fixed_pol, fixed_pol)
        self.badge_crs = QLabel("EPSG:5253")
        self.badge_crs.setObjectName("crsPill")
        self.badge_crs.setSizePolicy(fixed_pol, fixed_pol)
        badge_row.addWidget(self.badge_ver)
        badge_row.addWidget(self.badge_crs)
        badge_row.addStretch(1)

        self.btn_dock_l = QPushButton("⬅ Left")
        self.btn_dock_l.setObjectName("dockBtn")
        self.btn_dock_l.clicked.connect(self._dock_to_left)

        self.btn_dock_f = QPushButton("🪟 Float")
        self.btn_dock_f.setObjectName("dockBtn")
        self.btn_dock_f.clicked.connect(self._undock_free)

        self.btn_dock_r = QPushButton("Right ➡")
        self.btn_dock_r.setObjectName("dockBtn")
        self.btn_dock_r.clicked.connect(self._dock_to_right)

        badge_row.addWidget(self.btn_dock_l)
        badge_row.addWidget(self.btn_dock_f)
        badge_row.addWidget(self.btn_dock_r)
        h_lay.addLayout(badge_row)

        root.addWidget(self.header_card)

        # --- Main Tabbed Panels (Inside ScrollArea) ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff if hasattr(Qt, "ScrollBarPolicy") else Qt.ScrollBarAlwaysOff
        )

        self.tabs = QTabWidget()
        self.tabs.setObjectName("modernTabs")

        self.tab_data = self._create_data_tab()
        self.tab_adv = self._create_advanced_tab()
        self.tab_rep = self._create_report_tab()

        self.tabs.addTab(self.tab_data, "Data")
        self.tabs.addTab(self.tab_adv, "Settings")
        self.tabs.addTab(self.tab_rep, "Report")

        self.scroll_area.setWidget(self.tabs)
        root.addWidget(self.scroll_area, 1)

        # --- Progress Bar & Status ---
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

        self.setWidget(outer)

    def _create_data_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # 1. Layer Selection Card
        self.grp_layers = QGroupBox()
        f = QVBoxLayout(self.grp_layers)
        f.setContentsMargins(8, 10, 8, 8)
        f.setSpacing(4)

        self.cmb_roads = QgsMapLayerComboBox()
        self.cmb_roads.setFilters(layer_filter("LineLayer"))

        # Supports ANY target facility (School, Park, Health, Station — Polygon or Point)
        self.cmb_parks = QgsMapLayerComboBox()
        self.cmb_parks.setFilters(layer_filter("PolygonLayer", "PointLayer"))

        self.cmb_buildings = QgsMapLayerComboBox()
        self.cmb_buildings.setFilters(layer_filter("PolygonLayer", "PointLayer"))
        self.cmb_buildings.setAllowEmptyLayer(True)

        self.cmb_bldg_mode = QComboBox()
        self.cmb_bldg_mode.addItem("Closest road-facing facade", "facade")
        self.cmb_bldg_mode.addItem("Centroid", "centroid")

        self.cmb_weight = QgsFieldComboBox()
        self.cmb_weight.setAllowEmptyFieldName(True)
        self.cmb_buildings.layerChanged.connect(self.cmb_weight.setLayer)
        self.cmb_weight.setLayer(self.cmb_buildings.currentLayer())

        self.chk_selected = QCheckBox()

        self.lbl_roads = QLabel()
        self.lbl_parks = QLabel()
        self.lbl_buildings = QLabel()
        self.lbl_bldg_mode = QLabel()
        self.lbl_weight = QLabel()

        adj_pol = (
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            if hasattr(QComboBox, "SizeAdjustPolicy")
            else QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        for lbl, wdg in (
            (self.lbl_roads, self.cmb_roads),
            (self.lbl_parks, self.cmb_parks),
            (self.lbl_buildings, self.cmb_buildings),
            (self.lbl_bldg_mode, self.cmb_bldg_mode),
            (self.lbl_weight, self.cmb_weight),
        ):
            wdg.setSizeAdjustPolicy(adj_pol)
            wdg.setMinimumContentsLength(6)
            wdg.setMinimumWidth(80)
            f.addWidget(lbl)
            f.addWidget(wdg)
        f.addWidget(self.chk_selected)
        lay.addWidget(self.grp_layers)

        # 2. Distance Thresholds Card
        self.grp_thresholds = QGroupBox()
        v = QVBoxLayout(self.grp_thresholds)
        v.setContentsMargins(8, 10, 8, 8)
        v.setSpacing(5)

        self.txt_distances = QLineEdit("250, 500, 1000")
        v.addWidget(self.txt_distances)

        pr = QHBoxLayout()
        pr.setSpacing(3)
        for label, text in (
            ("250·500", "250, 500"),
            ("250·500·1000", "250, 500, 1000"),
            ("300·500·1000", "300, 500, 1000"),
            ("400·800·1200", "400, 800, 1200"),
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
        lay.setSpacing(6)

        # Network Gap Repair Card
        self.grp_repair = QGroupBox()
        f_rep = QVBoxLayout(self.grp_repair)
        f_rep.setContentsMargins(8, 10, 8, 8)
        f_rep.setSpacing(4)
        self.spn_gap = self._spin(0, 100, 15, 0, " m")
        self.chk_node = QCheckBox()
        self.chk_node.setChecked(True)  # Default ON: automatically node crossing road lines
        self.chk_disc = QCheckBox()
        self.chk_disc.setChecked(False)  # Default OFF: heal local T-junction gaps even in same component
        self.lbl_gap = QLabel()
        row_gap = QHBoxLayout()
        row_gap.addWidget(self.lbl_gap, 1)
        row_gap.addWidget(self.spn_gap)
        f_rep.addLayout(row_gap)
        f_rep.addWidget(self.chk_node)
        f_rep.addWidget(self.chk_disc)
        lay.addWidget(self.grp_repair)

        # Target Facility Access & Snapping Card
        self.grp_entry = QGroupBox()
        f_ent = QVBoxLayout(self.grp_entry)
        f_ent.setContentsMargins(8, 10, 8, 8)
        f_ent.setSpacing(4)
        self.cmb_origin = QComboBox()
        adj_pol = (
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            if hasattr(QComboBox, "SizeAdjustPolicy")
            else QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.cmb_origin.setSizeAdjustPolicy(adj_pol)
        self.cmb_origin.setMinimumContentsLength(6)
        self.cmb_origin.setMinimumWidth(80)
        self.cmb_origin.addItem("All facades / boundary", "boundary")
        self.cmb_origin.addItem("Centroid", "centroid")
        self.spn_snap = self._spin(10, 2000, 200, 0, " m")
        self.spn_area = self._spin(0, 1e7, 0, 0, " m²", 100)
        self.chk_offset = QCheckBox()
        self.chk_offset.setChecked(False)  # Default OFF: treat closest road-facing facade as block origin

        self.lbl_entry_mode = QLabel()
        self.lbl_snap = QLabel()
        self.lbl_area = QLabel()
        f_ent.addWidget(self.lbl_entry_mode)
        f_ent.addWidget(self.cmb_origin)
        row_snap = QHBoxLayout()
        row_snap.addWidget(self.lbl_snap, 1)
        row_snap.addWidget(self.spn_snap)
        f_ent.addLayout(row_snap)
        row_area = QHBoxLayout()
        row_area.addWidget(self.lbl_area, 1)
        row_area.addWidget(self.spn_area)
        f_ent.addLayout(row_area)
        f_ent.addWidget(self.chk_offset)
        lay.addWidget(self.grp_entry)

        # Outputs & Catchments Card
        self.grp_outputs = QGroupBox()
        f_out = QVBoxLayout(self.grp_outputs)
        f_out.setContentsMargins(8, 10, 8, 8)
        f_out.setSpacing(4)
        self.chk_poly = QCheckBox()
        self.chk_poly.setChecked(True)
        self.spn_buf = self._spin(1, 500, 28, 0, " m")
        self.chk_circ = QCheckBox()
        self.chk_circ.setChecked(True)
        self.chk_debug = QCheckBox()
        self.chk_debug.setChecked(True)
        self.spn_speed = self._spin(1.0, 10.0, 4.8, 1, " km/h", 0.1)

        self.lbl_buf = QLabel()
        self.lbl_speed = QLabel()
        f_out.addWidget(self.chk_poly)
        row_buf = QHBoxLayout()
        row_buf.addWidget(self.lbl_buf, 1)
        row_buf.addWidget(self.spn_buf)
        f_out.addLayout(row_buf)
        f_out.addWidget(self.chk_circ)
        f_out.addWidget(self.chk_debug)
        row_spd = QHBoxLayout()
        row_spd.addWidget(self.lbl_speed, 1)
        row_spd.addWidget(self.spn_speed)
        f_out.addLayout(row_spd)
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

        self.btn_dock_l.setText(_t("btn_dock_left"))
        self.btn_dock_f.setText(_t("btn_dock_float"))
        self.btn_dock_r.setText(_t("btn_dock_right"))

        # Tabs
        self.tabs.setTabText(0, f"📊 {_t('tab_data')}")
        self.tabs.setTabText(1, f"⚙️ {_t('tab_advanced')}")
        self.tabs.setTabText(2, f"📑 {_t('tab_report')}")

        # Data Tab
        self.grp_layers.setTitle(f"🗺️ {_t('layers_group')}")
        self.lbl_roads.setText(_t("roads_layer"))
        self.lbl_parks.setText(_t("parks_layer"))
        self.lbl_buildings.setText(_t("buildings_layer"))
        self.lbl_bldg_mode.setText(_t("bldg_mode_label"))

        cur_bmode = self.cmb_bldg_mode.currentData() or "facade"
        self.cmb_bldg_mode.clear()
        self.cmb_bldg_mode.addItem(_t("bldg_mode_facade"), "facade")
        self.cmb_bldg_mode.addItem(_t("bldg_mode_centroid"), "centroid")
        b_idx = self.cmb_bldg_mode.findData(cur_bmode)
        self.cmb_bldg_mode.setCurrentIndex(max(0, b_idx))

        self.lbl_weight.setText(_t("weight_field"))
        self.cmb_weight.setToolTip(_t("weight_field_tip"))
        self.chk_selected.setText(_t("use_selected"))

        self.grp_thresholds.setTitle(f"🚶 {_t('thresholds_group')}")
        self.lbl_thresholds_hint.setText(_t("thresholds_tip"))

        # Settings Tab
        self.grp_repair.setTitle(f"🔧 {_t('network_repair_group')}")
        self.lbl_gap.setText(_t("gap_tolerance"))
        self.spn_gap.setToolTip(_t("gap_tolerance_tip"))
        self.chk_disc.setText(_t("only_disconnected"))
        self.chk_disc.setToolTip(_t("only_disconnected_tip"))
        self.chk_node.setText(_t("node_crossings"))
        self.chk_node.setToolTip(_t("node_crossings_tip"))

        self.grp_entry.setTitle(f"🎯 {_t('park_entry_group')}")
        self.lbl_entry_mode.setText(_t("entry_mode"))
        cur_origin = self.cmb_origin.currentData() or "boundary"
        self.cmb_origin.clear()
        self.cmb_origin.addItem(_t("entry_boundary"), "boundary")
        self.cmb_origin.addItem(_t("entry_centroid"), "centroid")
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
            self.lbl_status.setText(f"🟠 {_t('status_ready')}")

        if not self.txt_report.toPlainText().strip() or "Henüz" in self.txt_report.toPlainText():
            self.txt_report.setHtml(_t("no_report_yet"))

    # ==================================================================
    # Layer Auto-Detection & QSettings
    # ==================================================================
    def _guess_layers(self) -> None:
        hints = (
            (self.cmb_roads, ("yol", "sokak", "cadde", "road", "street", "highway", "ulasim", "ulaşım", "network")),
            (
                self.cmb_parks,
                (
                    "donati", "donatı", "okul", "egitim", "eğitim", "saglik", "sağlık",
                    "yesil", "yeşil", "park", "istasyon", "durak", "hedef", "facility",
                    "school", "green", "health",
                ),
            ),
            (self.cmb_buildings, ("ada", "konut", "bina", "parsel", "yapi", "yapı", "building", "block", "residential")),
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
        saved_lang = str(g("language", "en"))
        idx = self.cmb_lang.findData(saved_lang)
        if idx >= 0:
            self.cmb_lang.setCurrentIndex(idx)
            self._current_lang = saved_lang

        self.txt_distances.setText(str(g("distances", "250, 500, 1000")))
        self.spn_gap.setValue(float(g("gap", 15)))
        self.chk_disc.setChecked(str(g("only_disc", "false")).lower() == "true")
        self.chk_node.setChecked(str(g("node", "true")).lower() == "true")

        origin_val = str(g("origin", "boundary"))
        o_idx = self.cmb_origin.findData(origin_val)
        if o_idx >= 0:
            self.cmb_origin.setCurrentIndex(o_idx)

        bmode_val = str(g("bldg_mode", "facade"))
        b_idx = self.cmb_bldg_mode.findData(bmode_val)
        if b_idx >= 0:
            self.cmb_bldg_mode.setCurrentIndex(b_idx)

        self.spn_snap.setValue(float(g("snap", 200)))
        self.spn_area.setValue(float(g("min_area", 0)))
        self.chk_offset.setChecked(str(g("offset", "false")).lower() == "true")
        self.chk_poly.setChecked(str(g("poly", "true")).lower() == "true")
        self.spn_buf.setValue(float(g("buf", 28)))
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
            ("bldg_mode", self.cmb_bldg_mode.currentData()),
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
            "accessibility_analysis_report.html",
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
                        "<title>Accessibility Analysis Report</title></head><body>"
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
            "origin_mode": self.cmb_origin.currentData() or "boundary",
            "bldg_mode": self.cmb_bldg_mode.currentData() or "facade",
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
