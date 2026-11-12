# Changelog — Green Space Accessibility & Pedshed Analysis

## [5.1.0] - 2026-11-12

### Added
- **5-Language Multilingual Support**: Dynamic runtime language selector in dialog header for English (`en`), Turkish (`tr`), Chinese (`zh`), Spanish (`es`), and Indonesian (`id`).
- **PLN311 Topological Network Graph Engine**: Hardened primal network graph with O(1) spatial hashing, topological gap healing for dead-ends and T-junctions, and planar crossing noding.
- **P-Median Facility Allocation**: Added residential demand load tracking (`Served_Bld`, `Served_Pop`, `Mean_Dist`) per green space to identify over-demanded vs underutilized parks.
- **Pedshed Walkability Coverage Ratio**: Automated ratio calculation ($\text{Area}_{\text{network}} / \text{Area}_{\text{circle}} \times 100\%$) classifying pedestrian catchments into High Walkability ($\ge 40\%$) vs Isolated ($< 40\%$).
- **Benchmark Euclidean Circular Buffers**: Generates comparative circular buffer zones (WHO / MPYY 500m/1000m standards) with dashed visual boundary styling.
- **Academic Governance & Verified Real DOIs**: Full integration with `doi_dogrula.py` verified citations (Hakimi 1964, Teitz & Bart 1968, Talen 1997, Leslie et al. 2007, Dijkstra 1959).
- **EPSG:5253 Standard Enforcement**: Built-in validation and CRS recommendation for TUREF / TM30.
- **Unit Test Suite**: Added `test_i18n.py` verifying all string keys across 5 languages and updated `test_smoke_stub.py`.

### Changed
- Standardized UI and code identifiers to 100% English default.
- Upgraded `metadata.txt` to include `qgisMaximumVersion=4.99`, `supportsQt6=True`, and official repository links.
- Updated author metadata to Baran Adsuna.

## [5.0.0] - Legacy Initial Version
- Initial non-blocking `QgsTask` implementation with multi-source Dijkstra and mid-street edge clipping.
