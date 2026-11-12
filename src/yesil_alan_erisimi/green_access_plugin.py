# -*- coding: utf-8 -*-
"""
QGIS Plugin Interface Hook for Green Space Accessibility & Pedshed Analysis.
Author / Developer: Baran Adsuna (https://github.com/baranadsuna)
CRS Standard: EPSG:5253 (TUREF / TM30)
Dual Compatible: QGIS 3 & QGIS 4 / Qt5 & Qt6
"""
from __future__ import annotations

import os
from typing import Any, Optional

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .gui_dialog import GreenAccessDialog

MENU_TITLE = "&Green Space Analysis"


class GreenAccessPlugin:
    def __init__(self, iface: Any):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action: Optional[QAction] = None
        self.dialog: Optional[GreenAccessDialog] = None

    def initGui(self) -> None:
        icon_path = os.path.join(self.plugin_dir, "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        self.action = QAction(icon, "Green Space Accessibility Analysis", self.iface.mainWindow())
        self.action.setToolTip(
            "Calculate network-based walking distance, isochrones, pedshed ratio, and facility load to urban green spaces"
        )
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(MENU_TITLE, self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self) -> None:
        if self.dialog is not None:
            self.dialog.cancel_running()
            self.dialog.close()
            self.dialog.deleteLater()
            self.dialog = None
        if self.action is not None:
            self.iface.removePluginMenu(MENU_TITLE, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    def run(self) -> None:
        if self.dialog is None:
            self.dialog = GreenAccessDialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
