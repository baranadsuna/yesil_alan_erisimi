# -*- coding: utf-8 -*-
"""
Cross-version compatibility layer for QGIS 3.22+ and QGIS 4.x / Qt5 and Qt6.
Author / Developer: Baran Adsuna (https://github.com/baranadsuna)
"""
from qgis.core import Qgis, QgsField, QgsMapLayerProxyModel, QgsTask
from qgis.PyQt.QtCore import Qt, QVariant


def version_int() -> int:
    v = getattr(Qgis, "QGIS_VERSION_INT", None)
    if v is None:
        try:
            v = Qgis.versionInt()
        except Exception:
            v = 32200
    return int(v)


_KINDS = {"int": "Int", "double": "Double", "string": "QString"}


def make_field(name: str, kind: str) -> QgsField:
    """kind: 'int' | 'double' | 'string'"""
    if version_int() >= 33800:
        try:
            from qgis.PyQt.QtCore import QMetaType
            return QgsField(name, getattr(QMetaType.Type, _KINDS[kind]))
        except Exception:
            pass
    return QgsField(name, getattr(QVariant, _KINDS[kind] if kind != "string" else "String"))


def layer_filter(*names):
    """QgsMapLayerComboBox filter helper: layer_filter('LineLayer') ..."""
    holder = getattr(Qgis, "LayerFilter", None)
    flags = []
    for n in names:
        try:
            flags.append(getattr(holder, n))
        except Exception:
            flags.append(getattr(QgsMapLayerProxyModel.Filter if hasattr(QgsMapLayerProxyModel, "Filter") else QgsMapLayerProxyModel, n))
    result = flags[0]
    for f in flags[1:]:
        result = result | f
    return result


def task_can_cancel():
    try:
        return QgsTask.Flag.CanCancel
    except AttributeError:
        return QgsTask.CanCancel


def meters_unit():
    try:
        return Qgis.DistanceUnit.Meters
    except AttributeError:
        from qgis.core import QgsUnitTypes
        return QgsUnitTypes.DistanceMeters


def exec_dialog(dialog) -> int:
    """Safe execution of QDialog across Qt5 (.exec_ / .exec) and Qt6 (.exec)."""
    func = getattr(dialog, "exec", None) or getattr(dialog, "exec_", None)
    if func is not None:
        return int(func())
    return 0


def align_center():
    try:
        return Qt.AlignmentFlag.AlignCenter
    except AttributeError:
        return Qt.AlignCenter


def align_right():
    try:
        return Qt.AlignmentFlag.AlignRight
    except AttributeError:
        return Qt.AlignRight


def dock_right():
    try:
        return Qt.DockWidgetArea.RightDockWidgetArea
    except AttributeError:
        return Qt.RightDockWidgetArea


def dock_left():
    try:
        return Qt.DockWidgetArea.LeftDockWidgetArea
    except AttributeError:
        return Qt.LeftDockWidgetArea


def dock_all_areas():
    try:
        return Qt.DockWidgetArea.AllDockWidgetAreas
    except AttributeError:
        return Qt.AllDockWidgetAreas
