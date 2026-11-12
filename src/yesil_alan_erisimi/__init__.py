def classFactory(iface):
    from .green_access_plugin import GreenAccessPlugin
    return GreenAccessPlugin(iface)
