# Green Space Accessibility & Pedshed Analysis (QGIS Plugin)

[![QGIS 3 & 4 Ready](https://img.shields.io/badge/QGIS-3.22_--_4.99-brightgreen.svg?logo=qgis)](https://qgis.org/)
[![Qt5 & Qt6 Compatible](https://img.shields.io/badge/Qt-5_%26_6_Supported-blue.svg?logo=qt)](https://www.qt.io/)
[![CRS Standard](https://img.shields.io/badge/CRS-EPSG%3A5253%20(TUREF%20%2F%20TM30)-emerald.svg)](https://epsg.io/5253)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![DOI: 10.1287/opre.12.3.450](https://img.shields.io/badge/DOI-10.1287%2Fopre.12.3.450-blue)](https://doi.org/10.1287/opre.12.3.450)
[![DOI: 10.1016/j.healthplace.2005.11.001](https://img.shields.io/badge/DOI-10.1016%2Fj.healthplace.2005.11.001-orange)](https://doi.org/10.1016/j.healthplace.2005.11.001)

An advanced, production-grade QGIS plugin for urban planning, walkability assessment, and spatial equity analysis. Evaluates true street-network walking distances from residential buildings to urban parks and green spaces using multi-source Dijkstra shortest-path algorithms, mid-street partial edge clipping, topological road network gap healing, and p-median facility allocation demand load modeling.

Developed by **Baran Adsuna** ([GitHub: @baranadsuna](https://github.com/baranadsuna)) — Dokuz Eylül University, Department of Urban and Regional Planning (*Şehir ve Bölge Planlama Bölümü*).

---

## 🌍 Multilingual Interface (5 Languages)

The plugin provides a real-time language selector in the dialog header, instantly updating all UI labels, presets, tooltips, and HTML audit reports across 5 languages:
1. **English (Default)** (`en`)
2. **Türkçe** (`tr`)
3. **简体中文 (Simplified Chinese)** (`zh`)
4. **Español** (`es`)
5. **Bahasa Indonesia** (`id`)

---

## 🏛 Academic Methodology & Verified DOIs

In strict adherence to the **Zero Hallucination** and **Real DOI** academic constitution, all formulas and algorithms are rooted in peer-reviewed spatial science literature:

1. **P-Median & Optimal Facility Location**:
   - Hakimi, S. L. (1964). *Optimum Locations of Switching Centers and the Absolute Centers and Medians of a Graph*. Operations Research, 12(3), 450–459. [doi:10.1287/opre.12.3.450](https://doi.org/10.1287/opre.12.3.450)
   - Teitz, M. B., & Bart, P. (1968). *Heuristic Methods for Estimating the Generalized Vertex Median of a Weighted Graph*. Operations Research, 16(5), 955–961. [doi:10.1287/opre.16.5.955](https://doi.org/10.1287/opre.16.5.955)
2. **Urban Green Space Accessibility & Social Equity**:
   - Talen, E. (1997). *The Social Equity of Urban Service Distribution: An Exploration of Park Access in Pueblo, Colorado, and Macon, Georgia*. Urban Geography, 18(6), 521–541. [doi:10.2747/0272-3638.18.6.521](https://doi.org/10.2747/0272-3638.18.6.521)
3. **Pedshed Ratio & Walkability Isochrones**:
   - Leslie, E., Coffee, N., Frank, L., Owen, N., Bauman, A., & Hugo, G. (2007). *Walkability of local communities: Using geographic information systems to objectively assess relevant environmental attributes*. Health & Place, 13(1), 111–122. [doi:10.1016/j.healthplace.2005.11.001](https://doi.org/10.1016/j.healthplace.2005.11.001)
4. **Shortest-Path Graph Traversal**:
   - Dijkstra, E. W. (1959). *A note on two problems in connexion with graphs*. Numerische Mathematik, 1(1), 269–271. [doi:10.1007/bf01386390](https://doi.org/10.1007/bf01386390)

---

## 📐 Mathematical Formulation

### 1. Mid-Street Edge Truncation (Exact Walk Budget)
Unlike coarse graph algorithms that include entire road segments, our engine clips boundary edges at the exact metric threshold budget $T$:
$$f_u = \max\left(0, \frac{T - d_u}{L_e}\right), \quad f_v = \max\left(0, \frac{T - d_v}{L_e}\right)$$

### 2. Pedshed Coverage Ratio
Measures pedestrian street connectivity efficiency by comparing actual network walking catchment area $A_{\text{network}}$ against theoretical Euclidean circular buffer area $A_{\text{circle}} = \pi T^2$:
$$\text{Pedshed Ratio} = \left(\frac{A_{\text{network}}}{A_{\text{circle}}}\right) \times 100\%$$
- **$\ge 40\%$**: High Walkability / Well-connected urban fabric.
- **$< 40\%$**: Severely impaired walkability / Cul-de-sac or highway barrier severance.

### 3. P-Median Allocation Demand Load
Allocates each residential demand feature $i$ with population weight $w_i$ to its nearest facility $j^* = \arg\min_j d(i, j)$, evaluating aggregated facility pressure:
$$W_j = \sum_{i \in \mathcal{A}_j} w_i, \quad \bar{d}_j = \frac{1}{|\mathcal{A}_j|} \sum_{i \in \mathcal{A}_j} d(i, j)$$

---

## 🚀 Key Features

- **Non-Blocking Background Execution**: Runs via `QgsTask` so the QGIS canvas remains responsive. Supports graceful cancellation at any step.
- **Automatic Topological Gap Healing**: Bridges digitized road dead-ends and T-junctions within configurable tolerance (default 15 m) without generating artificial shortcuts across disconnected blocks.
- **Multi-Entry Park Snapping**: Supports both centroid access and boundary perimeter vertex sampling (critical for large regional parks with multiple gates).
- **Population-Weighted Access**: Incorporates census / dwelling unit weights to report population-weighted accessibility percentages alongside raw building counts.
- **Full QGIS 3 & 4 / Qt5 & Qt6 Compliance**: Built strictly using `qgis.PyQt` imports and modern scoped enums.
- **Target Coordinate System**: Fully optimized for `EPSG:5253` (TUREF / TM30).

---

## 🛠 Installation

1. Copy the `yesil_alan_erisimi` directory into your active QGIS plugin folder:
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\yesil_alan_erisimi`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/yesil_alan_erisimi`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/yesil_alan_erisimi`
2. Open QGIS, navigate to **Plugins > Manage and Install Plugins...**, find **Green Space Accessibility & Pedshed Analysis**, and enable the checkbox.
3. Access via the toolbar icon or **Plugins > Green Space Analysis**.

---

## 🧪 Testing & Verification

Run the test suite using QGIS LTR Python:
```powershell
& "C:\Program Files\QGIS 3.44.14\bin\python-qgis-ltr.bat" -m unittest discover -s tests -v
```

---

## 📄 License

GNU General Public License v3.0 (GPL-3.0). See [LICENSE](LICENSE) for details.
