# Accessibility Analysis (`v5.3.0`) — QGIS 3 & QGIS 4 Plugin

**Accessibility Analysis** is a high-precision urban network accessibility, 15-minute city, walkability isochrone, pedshed, and P-median facility capacity analyzer for **QGIS 3.22 – 4.99 (Qt5 & Qt6)**.

## Key Features
- **Prominent Blue Target Facility Symbology (`#2563EB`)**: Places target facilities at the top of the output layer group with a prominent `5.6 mm` Blue Circle Point marker and white halo outline.
- **Closest Road-Facing Facade Snapping**: Connects residential blocks and buildings from their facade closest to the street leading toward the target facility (schools, parks, healthcare, transit).
- **Colored Block/Building Polygons & Non-Overlapping Isochrones**: Paints residential blocks (`0–250 m` Green `#16a34a`, `250–500 m` Amber `#eab308`, `> 500 m` Red `#dc2626`) and generates clean, non-overlapping walkability isochrone bands.
- **Automatic Planar Road Noding & T-Junction Gap Healing**: Splits crossing road segments and repairs `<= 15 m` digitizing gaps and T-junction undershoots automatically.
- **Low-Threshold Dock & Float Controls (`18 px`)**: Includes `[⬅ Left | 🪟 Float | Right ➡]` buttons and prevents accidental docking while moving across the screen.
- **5-Language Runtime UI**: 100% English default with instant switching between **English**, **Türkçe**, **简体中文**, **Español**, and **Bahasa Indonesia**.

- **Author:** Baran Adsuna (https://github.com/baranadsuna)
- **CRS Standard:** `EPSG:5253` (TUREF / TM30)
- **Repository:** https://github.com/baranadsuna/yesil_alan_erisimi
