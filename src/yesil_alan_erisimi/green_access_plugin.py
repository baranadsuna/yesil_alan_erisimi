# -*- coding: utf-8 -*-
"""
QGIS Plugin Interface Hook for Accessibility Analysis (Erişim Analizi).
Author / Developer: Baran Adsuna (https://github.com/baranadsuna)
CRS Standard: EPSG:5253 (TUREF / TM30)
Dual Compatible: QGIS 3 & QGIS 4 / Qt5 & Qt6
"""
from __future__ import annotations

import os
from typing import Any, Optional

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .compat import dock_right
from .gui_dialog import GreenAccessDockWidget

MENU_TITLE = "&Erişim Analizi (Accessibility Analysis)"


class GreenAccessPlugin:
    def __init__(self, iface: Any):
        self.iface = iface
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.action: Optional[QAction] = None
        self.dock: Optional[GreenAccessDockWidget] = None

    def initGui(self) -> None:
        icon_path = os.path.join(self.plugin_dir, "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self.action = QAction(icon, "Erişim Analizi (Accessibility Analysis)", self.iface.mainWindow())
        self.action.setToolTip(
            "Ağ tabanlı donatı erişilebilirliği, en yakın cephe bağlantısı ve pedshed analizi"
        )
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(MENU_TITLE, self.action)
        self.iface.addToolBarIcon(self.action)

        # Initialize dock widget and register to QGIS right dock area
        self.dock = GreenAccessDockWidget(self.iface)
        self.dock.closingPlugin.connect(self._on_dock_closed)
        self.iface.addDockWidget(dock_right(), self.dock)
        self.dock.hide()

    def _on_dock_closed(self) -> None:
        if self.action:
            self.action.setChecked(False)

    def unload(self) -> None:
        if self.dock is not None:
            self.dock.cancel_running()
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
        if self.action is not None:
            self.iface.removePluginMenu(MENU_TITLE, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    def run(self) -> None:
        if self.dock is None:
            self.dock = GreenAccessDockWidget(self.iface)
            self.dock.closingPlugin.connect(self._on_dock_closed)
            self.iface.addDockWidget(dock_right(), self.dock)

        if self.dock.isVisible():
            self.dock.hide()
            if self.action:
                self.action.setChecked(False)
        else:
            self.dock.show()
            self.dock.raise_()
            self.dock.activateWindow()
            if self.action:
                self.action.setChecked(True)
