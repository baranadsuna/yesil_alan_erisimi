# -*- coding: utf-8 -*-
"""
Green Space Accessibility & Network Analysis Core Engine.
Author / Developer: Baran Adsuna (https://github.com/baranadsuna)
CRS Standard: EPSG:5253 (TUREF / TM30)

Pure Python & NumPy computational graph engine (no GUI/QGIS UI dependencies).
Thread-safe for background QgsTask execution and headless unit testing.

Key Capabilities:
  - Primal road network graph construction with spatial indexing.
  - Optional planar noding of intersecting road segments.
  - Topological gap healing (dead-end and T-junction bridges within tolerance).
  - Green space and building snapping (centroid or perimeter boundary multi-entry).
  - Multi-source Dijkstra with facility attribution (nearest-park tracking).
  - Exact mid-street edge clipping at specified distance thresholds.
  - P-median / Location-allocation demand load modeling (buildings & population per park).
  - Pedshed walkability coverage ratio evaluation (network catchment vs benchmark circles).
"""
from __future__ import annotations

import heapq
import math
import statistics
from typing import Any, Callable, Dict, List, Optional, Tuple

INF = float("inf")


class Cancelled(Exception):
    """User cancelled background analysis task."""


# ----------------------------------------------------------------------
# Topological Helpers & Union-Find
# ----------------------------------------------------------------------
class UnionFind:
    """Disjoint-set data structure with path compression."""

    def __init__(self):
        self.parent: List[int] = []

    def add(self) -> int:
        idx = len(self.parent)
        self.parent.append(idx)
        return idx

    def find(self, x: int) -> int:
        p = self.parent
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _project_point_to_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> Tuple[float, float, float, float]:
    """Project point (px, py) onto segment AB -> (t, qx, qy, perp_dist)."""
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 <= 0.0:
        return 0.0, ax, ay, math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / l2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    qx, qy = ax + t * dx, ay + t * dy
    return t, qx, qy, math.hypot(px - qx, py - qy)


def _seg_intersection(
    ax: float, ay: float, bx: float, by: float,
    cx: float, cy: float, dx: float, dy: float
) -> Optional[Tuple[float, float, float, float]]:
    """Segment AB and CD intersection -> (t, u, eps_t, eps_u) or None."""
    rx, ry = bx - ax, by - ay
    sx, sy = dx - cx, dy - cy
    denom = rx * sy - ry * sx
    if abs(denom) < 1e-12:
        return None  # Parallel or collinear
    qpx, qpy = cx - ax, cy - ay
    t = (qpx * sy - qpy * sx) / denom
    u = (qpx * ry - qpy * rx) / denom
    la = math.hypot(rx, ry)
    lc = math.hypot(sx, sy)
    eps_t = 1e-6 / la if la > 0 else 1e-9
    eps_u = 1e-6 / lc if lc > 0 else 1e-9
    if -eps_t <= t <= 1 + eps_t and -eps_u <= u <= 1 + eps_u:
        return t, u, eps_t, eps_u
    return None


# ----------------------------------------------------------------------
# Road Network Graph Class
# ----------------------------------------------------------------------
class RoadNetwork:
    """
    Prepared Road Network Graph.
    Uses grid-based spatial hashing for O(1) snapping, edge splitting,
    topological gap healing, and multi-source Dijkstra.
    """

    def __init__(
        self,
        cell_size: float = 30.0,
        precision: float = 0.01,
        cancelled: Optional[Callable[[], bool]] = None,
    ):
        self.cs = max(float(cell_size), 1.0)
        self.prec = precision
        self._cancelled = cancelled
        self.nx: List[float] = []
        self.ny: List[float] = []
        self.adj: List[List[Tuple[int, int]]] = []  # node -> list of (neighbor_node, edge_id)
        self.eu: List[int] = []                    # edge -> from_node
        self.ev: List[int] = []                    # edge -> to_node
        self.el: List[float] = []                  # edge -> length (meters)
        self.eroad: List[Any] = []                 # edge -> original road_id
        self._node_key: Dict[Tuple[int, int], int] = {}
        self._egrid: Dict[Tuple[int, int], List[int]] = {}
        self._ngrid: Dict[Tuple[int, int], List[int]] = {}
        self.uf = UnionFind()
        self.bridges: List[Tuple[float, float, float, float, float, str]] = []  # (x1, y1, x2, y2, len, type)
        self.segment_count = 0

    def _check(self) -> None:
        if self._cancelled is not None and self._cancelled():
            raise Cancelled()

    def _cell(self, x: float, y: float) -> Tuple[int, int]:
        return int(math.floor(x / self.cs)), int(math.floor(y / self.cs))

    def _cells_for_segment(self, x1: float, y1: float, x2: float, y2: float) -> List[Tuple[int, int]]:
        cs = self.cs
        c1x, c1y = int(math.floor(x1 / cs)), int(math.floor(y1 / cs))
        c2x, c2y = int(math.floor(x2 / cs)), int(math.floor(y2 / cs))
        minx, maxx = min(c1x, c2x), max(c1x, c2x)
        miny, maxy = min(c1y, c2y), max(c1y, c2y)
        if (maxx - minx + 1) * (maxy - miny + 1) <= 64:
            return [(i, j) for i in range(minx, maxx + 1) for j in range(miny, maxy + 1)]

        # Long diagonal segment: sample points
        length = math.hypot(x2 - x1, y2 - y1)
        n = max(int(length / (cs / 4.0)) + 1, 2)
        cells = set()
        for k in range(n + 1):
            f = k / float(n)
            cells.add(self._cell(x1 + f * (x2 - x1), y1 + f * (y2 - y1)))
        return list(cells)

    def add_node(self, x: float, y: float) -> int:
        key = (int(round(x / self.prec)), int(round(y / self.prec)))
        idx = self._node_key.get(key)
        if idx is not None:
            return idx
        idx = len(self.nx)
        self._node_key[key] = idx
        self.nx.append(x)
        self.ny.append(y)
        self.adj.append([])
        self.uf.add()
        self._ngrid.setdefault(self._cell(x, y), []).append(idx)
        return idx

    def _add_edge(self, u: int, v: int, road: Any) -> int:
        if u == v:
            return -1
        length = math.hypot(self.nx[u] - self.nx[v], self.ny[u] - self.ny[v])
        e = len(self.eu)
        self.eu.append(u)
        self.ev.append(v)
        self.el.append(length)
        self.eroad.append(road)
        self.adj[u].append((v, e))
        self.adj[v].append((u, e))
        self.uf.union(u, v)
        for c in self._cells_for_segment(self.nx[u], self.ny[u], self.nx[v], self.ny[v]):
            self._egrid.setdefault(c, []).append(e)
        return e

    def _replace_adj(self, n: int, old_nb: int, e: int, new_nb: int, new_e: int) -> None:
        lst = self.adj[n]
        for i, (nb, ee) in enumerate(lst):
            if ee == e and nb == old_nb:
                lst[i] = (new_nb, new_e)
                return

    def split_edge(self, e: int, px: float, py: float) -> int:
        """Splits an edge at point (px, py) and returns the node index."""
        u, v = self.eu[e], self.ev[e]
        if math.hypot(px - self.nx[u], py - self.ny[u]) < 1e-6:
            return u
        if math.hypot(px - self.nx[v], py - self.ny[v]) < 1e-6:
            return v
        p = self.add_node(px, py)
        if p == u or p == v:
            return p
        road = self.eroad[e]
        self.ev[e] = p
        self.el[e] = math.hypot(self.nx[u] - self.nx[p], self.ny[u] - self.ny[p])
        self._replace_adj(u, v, e, p, e)

        e2 = len(self.eu)
        self.eu.append(p)
        self.ev.append(v)
        self.el.append(math.hypot(self.nx[p] - self.nx[v], self.ny[p] - self.ny[v]))
        self.eroad.append(road)
        self._replace_adj(v, u, e, p, e2)

        self.adj[p].append((u, e))
        self.adj[p].append((v, e2))
        self.uf.union(p, u)
        for c in self._cells_for_segment(self.nx[p], self.ny[p], self.nx[v], self.ny[v]):
            self._egrid.setdefault(c, []).append(e2)
        return p

    def add_lines(self, lines: List[Tuple[Any, List[Tuple[float, float]]]], node_crossings: bool = False) -> None:
        """lines: [(road_id, [(x, y), ...]), ...]"""
        segs = []
        for road_id, coords in lines:
            for i in range(len(coords) - 1):
                x1, y1 = coords[i]
                x2, y2 = coords[i + 1]
                if (x1 - x2) ** 2 + (y1 - y2) ** 2 < 1e-12:
                    continue
                segs.append((x1, y1, x2, y2, road_id))
        self.segment_count = len(segs)
        splits = self._find_crossings(segs) if node_crossings else {}

        for i, (x1, y1, x2, y2, road) in enumerate(segs):
            if i % 5000 == 0:
                self._check()
            pts = [(x1, y1)]
            extra = splits.get(i)
            if extra:
                extra = sorted(set(extra), key=lambda p: (p[0] - x1) ** 2 + (p[1] - y1) ** 2)
                pts.extend(extra)
            pts.append((x2, y2))
            prev = self.add_node(*pts[0])
            for p in pts[1:]:
                cur = self.add_node(*p)
                self._add_edge(prev, cur, road)
                prev = cur

    def _find_crossings(self, segs: List[Tuple[float, float, float, float, Any]]) -> Dict[int, List[Tuple[float, float]]]:
        grid: Dict[Tuple[int, int], List[int]] = {}
        for i, (x1, y1, x2, y2, _r) in enumerate(segs):
            for c in self._cells_for_segment(x1, y1, x2, y2):
                grid.setdefault(c, []).append(i)
        splits: Dict[int, List[Tuple[float, float]]] = {}
        for i, (ax, ay, bx, by, _r) in enumerate(segs):
            if i % 2000 == 0:
                self._check()
            cand = set()
            for c in self._cells_for_segment(ax, ay, bx, by):
                cand.update(grid.get(c, ()))
            for j in cand:
                if j <= i:
                    continue
                cx, cy, dx, dy, _rj = segs[j]
                res = _seg_intersection(ax, ay, bx, by, cx, cy, dx, dy)
                if res is None:
                    continue
                t, u, eps_t, eps_u = res
                split_i = eps_t < t < 1 - eps_t
                split_j = eps_u < u < 1 - eps_u
                if not split_i and not split_j:
                    continue
                if split_i and split_j:
                    pt = (ax + t * (bx - ax), ay + t * (by - ay))
                elif split_i:
                    pt = (cx, cy) if u <= 0.5 else (dx, dy)
                else:
                    pt = (ax, ay) if t <= 0.5 else (bx, by)
                if split_i:
                    splits.setdefault(i, []).append(pt)
                if split_j:
                    splits.setdefault(j, []).append(pt)
        return splits

    def component_count(self) -> int:
        roots = set()
        for n in range(len(self.nx)):
            if self.adj[n]:
                roots.add(self.uf.find(n))
        return len(roots)

    def heal_gaps(self, tol: float, only_disconnected: bool = True) -> Tuple[int, int]:
        """
        Connects dead-end (degree=1) nodes to another node or edge within `tol` meters.
        If only_disconnected=True, bridges only across disconnected network components.
        Returns: (bridged_to_node, bridged_to_segment)
        """
        if tol <= 0:
            return 0, 0
        dangling = [n for n in range(len(self.nx)) if len(self.adj[n]) == 1]
        n_node = n_edge = 0
        uf = self.uf
        for k, d in enumerate(dangling):
            if k % 500 == 0:
                self._check()
            x, y = self.nx[d], self.ny[d]
            cx, cy = self._cell(x, y)
            d_root = uf.find(d)
            best = None
            neighbours_of_d = {nb for nb, _e in self.adj[d]}

            # 1. Search nearby nodes
            for ix in (-1, 0, 1):
                for iy in (-1, 0, 1):
                    for n in self._ngrid.get((cx + ix, cy + iy), ()):
                        if n == d or not self.adj[n]:
                            continue
                        dd = math.hypot(self.nx[n] - x, self.ny[n] - y)
                        if dd > tol:
                            continue
                        if only_disconnected:
                            if uf.find(n) == d_root:
                                continue
                        elif n in neighbours_of_d:
                            continue
                        if best is None or dd < best[0]:
                            best = (dd, "n", n)

            # 2. Search nearby segments (T-junctions)
            seen = set()
            for ix in (-1, 0, 1):
                for iy in (-1, 0, 1):
                    for e in self._egrid.get((cx + ix, cy + iy), ()):
                        if e in seen:
                            continue
                        seen.add(e)
                        if self.eroad[e] is None:
                            continue
                        u, v = self.eu[e], self.ev[e]
                        if u == d or v == d:
                            continue
                        if only_disconnected and uf.find(u) == d_root:
                            continue
                        t, qx, qy, dd = _project_point_to_segment(
                            x, y, self.nx[u], self.ny[u], self.nx[v], self.ny[v]
                        )
                        if dd > tol or t <= 1e-6 or t >= 1 - 1e-6:
                            continue
                        if best is None or dd < best[0] - 1e-9:
                            best = (dd, "e", (e, qx, qy))

            if best is None:
                continue
            if best[1] == "n":
                target = best[2]
                kind = "node"
                n_node += 1
            else:
                e, qx, qy = best[2]
                target = self.split_edge(e, qx, qy)
                kind = "segment"
                n_edge += 1
            if target == d:
                continue
            e_new = self._add_edge(d, target, None)
            if e_new >= 0:
                self.bridges.append((x, y, self.nx[target], self.ny[target], self.el[e_new], kind))
        return n_node, n_edge

    def nearest_edge(self, x: float, y: float, max_dist: float) -> Optional[Tuple[int, float, float, float, float]]:
        """Finds nearest edge -> (edge_id, t, qx, qy, dist) or None."""
        cs = self.cs
        cx, cy = self._cell(x, y)
        max_r = int(max_dist // cs) + 1
        best_d = INF
        best = None
        seen = set()
        r = 0
        while r <= max_r:
            cells = [(cx, cy)] if r == 0 else []
            if r > 0:
                for i in range(-r, r + 1):
                    cells.append((cx + i, cy - r))
                    cells.append((cx + i, cy + r))
                for j in range(-r + 1, r):
                    cells.append((cx - r, cy + j))
                    cells.append((cx + r, cy + j))
            for c in cells:
                for e in self._egrid.get(c, ()):
                    if e in seen:
                        continue
                    seen.add(e)
                    u, v = self.eu[e], self.ev[e]
                    t, qx, qy, dd = _project_point_to_segment(
                        x, y, self.nx[u], self.ny[u], self.nx[v], self.ny[v]
                    )
                    if dd < best_d:
                        best_d = dd
                        best = (e, t, qx, qy, dd)
            if best is not None and best_d <= r * cs:
                break
            r += 1
        if best is None or best_d > max_dist:
            return None
        return best

    def edges_within_distance(
        self, x: float, y: float, max_dist: float
    ) -> List[Tuple[int, float, float, float, float]]:
        """Finds all edges within max_dist -> [(edge_id, t, qx, qy, dist), ...]."""
        cs = self.cs
        cx, cy = self._cell(x, y)
        max_r = int(max_dist // cs) + 1
        out: List[Tuple[int, float, float, float, float]] = []
        seen = set()
        for ix in range(-max_r, max_r + 1):
            for iy in range(-max_r, max_r + 1):
                for e in self._egrid.get((cx + ix, cy + iy), ()):
                    if e in seen:
                        continue
                    seen.add(e)
                    u, v = self.eu[e], self.ev[e]
                    t, qx, qy, dd = _project_point_to_segment(
                        x, y, self.nx[u], self.ny[u], self.nx[v], self.ny[v]
                    )
                    if dd <= max_dist:
                        out.append((e, t, qx, qy, dd))
        return out

    def add_source_point(self, x: float, y: float, max_snap: float) -> Optional[Tuple[int, float, float, float]]:
        """Connects point to network by splitting nearest edge -> (node_id, snap_dist, px, py)."""
        ne = self.nearest_edge(x, y, max_snap)
        if ne is None:
            return None
        e, _t, qx, qy, dd = ne
        node = self.split_edge(e, qx, qy)
        return node, dd, self.nx[node], self.ny[node]

    def add_facility_sources(
        self,
        seeds: List[Tuple[float, float]],
        max_snap: float,
        multi_street: bool = True,
    ) -> List[Tuple[int, float, float, float]]:
        """
        Connects a target facility (school, park, station, etc.) to the road network.
        When multi_street=True, in addition to the nearest road for each boundary seed,
        it also connects to all bounding streets around the facility block within frontage
        tolerance so streets on all sides of the facility receive direct access.
        Returns: [(node_id, snap_dist, px, py), ...]
        """
        if not seeds:
            return []

        # 1. Find nearest edge for each seed
        nearest_per_seed = []
        min_dd = INF
        for sx, sy in seeds:
            ne = self.nearest_edge(sx, sy, max_snap)
            if ne is not None:
                nearest_per_seed.append((sx, sy, ne))
                if ne[4] < min_dd:
                    min_dd = ne[4]

        if not nearest_per_seed:
            return []

        snap_targets: List[Tuple[float, float, float]] = []  # (qx, qy, dd)
        for _sx, _sy, (_e, _t, qx, qy, dd) in nearest_per_seed:
            snap_targets.append((qx, qy, dd))

        # 2. Also collect surrounding streets within block-frontage tolerance (up to 35m)
        if multi_street and min_dd < INF:
            frontage_tol = min(max_snap, max(min_dd + 25.0, min_dd * 3.0, 35.0))
            best_by_road: Dict[Any, Tuple[float, float, float]] = {}
            for sx, sy in seeds:
                for e, _t, qx, qy, dd in self.edges_within_distance(sx, sy, frontage_tol):
                    road_key = self.eroad[e] if self.eroad[e] is not None else f"bridge_{e}"
                    prev = best_by_road.get(road_key)
                    if prev is None or dd < prev[2]:
                        best_by_road[road_key] = (qx, qy, dd)
            for qx, qy, dd in best_by_road.values():
                snap_targets.append((qx, qy, dd))

        # Deduplicate snap targets within 2.0m and split edges
        results: List[Tuple[int, float, float, float]] = []
        placed_pts: List[Tuple[float, float]] = []
        for qx, qy, dd in sorted(snap_targets, key=lambda item: item[2]):
            if any(math.hypot(qx - px, qy - py) < 2.0 for px, py in placed_pts):
                continue
            ne = self.nearest_edge(qx, qy, max(5.0, dd + 1.0))
            if ne is None:
                continue
            e_now, _t_now, qx_now, qy_now, _d_now = ne
            node = self.split_edge(e_now, qx_now, qy_now)
            placed_pts.append((self.nx[node], self.ny[node]))
            results.append((node, dd, self.nx[node], self.ny[node]))

        return results

    def dijkstra(
        self, sources: List[Tuple[int, float, Any]], cutoff: float
    ) -> Tuple[Dict[int, float], Dict[int, Any]]:
        """
        Multi-source Dijkstra with nearest facility attribution.
        sources: [(node_id, initial_cost, facility_id)]
        Returns: (dist_map, label_map)
        """
        dist: Dict[int, float] = {}
        label: Dict[int, Any] = {}
        heap: List[Tuple[float, int]] = []

        for node, c0, lab in sources:
            if c0 > cutoff:
                continue
            if c0 < dist.get(node, INF):
                dist[node] = c0
                label[node] = lab
                heapq.heappush(heap, (c0, node))

        el, adj = self.el, self.adj
        pops = 0
        while heap:
            d, n = heapq.heappop(heap)
            if d > dist.get(n, INF):
                continue
            pops += 1
            if pops % 20000 == 0:
                self._check()
            lab = label[n]
            for nb, e in adj[n]:
                nd = d + el[e]
                if nd <= cutoff and nd < dist.get(nb, INF):
                    dist[nb] = nd
                    label[nb] = lab
                    heapq.heappush(heap, (nd, nb))
        return dist, label

    def service_pieces(
        self, dist: Dict[int, float], label: Dict[int, Any], thresholds: List[float]
    ) -> Tuple[Dict[float, List[Tuple[float, float, float, float, float, Any, Any]]], Dict[float, float]]:
        """
        Calculates mid-street clipped service area line pieces for each distance threshold.
        Returns: ({threshold: [(x1, y1, x2, y2, cost, label, road_id)]}, {threshold: total_length_m})
        """
        thresholds = sorted(thresholds)
        out = {t: [] for t in thresholds}
        total = {t: 0.0 for t in thresholds}
        visited = set()
        nx, ny = self.nx, self.ny

        for k, n in enumerate(list(dist.keys())):
            if k % 20000 == 0:
                self._check()
            for _nb, e in self.adj[n]:
                if e in visited:
                    continue
                visited.add(e)
                u, v = self.eu[e], self.ev[e]
                du, dv = dist.get(u), dist.get(v)
                L = self.el[e]
                road = self.eroad[e]
                x1, y1, x2, y2 = nx[u], ny[u], nx[v], ny[v]

                for t in thresholds:
                    a = (t - du) if (du is not None and du <= t) else None
                    b = (t - dv) if (dv is not None and dv <= t) else None
                    if a is None and b is None:
                        continue
                    if (a or 0.0) + (b or 0.0) >= L - 1e-9:
                        if du is not None and (dv is None or du <= dv):
                            lab, cost = label[u], du
                        else:
                            lab, cost = label[v], dv
                        out[t].append((x1, y1, x2, y2, cost, lab, road))
                        total[t] += L
                        continue
                    if a is not None and a > 1e-9:
                        f = a / L
                        out[t].append((x1, y1, x1 + f * (x2 - x1), y1 + f * (y2 - y1), du, label[u], road))
                        total[t] += a
                    if b is not None and b > 1e-9:
                        f = b / L
                        out[t].append((x2, y2, x2 + f * (x1 - x2), y2 + f * (y1 - y2), dv, label[v], road))
                        total[t] += b
        return out, total

    def evaluate_point(
        self,
        x: float,
        y: float,
        dist: Dict[int, float],
        label: Dict[int, Any],
        max_snap: float,
        include_offset: bool = True,
    ) -> Tuple[Optional[float], Optional[Any], Optional[float]]:
        """
        Evaluates point (e.g. building centroid) for shortest network distance to facility.
        Returns: (cost, nearest_facility_id, snap_dist)
        """
        ne = self.nearest_edge(x, y, max_snap)
        if ne is None:
            return None, None, None
        e, t, _qx, _qy, dd = ne
        u, v = self.eu[e], self.ev[e]
        L = self.el[e]
        cand = []
        cu, cv = dist.get(u), dist.get(v)
        if cu is not None:
            cand.append((cu + t * L, label[u]))
        if cv is not None:
            cand.append((cv + (1.0 - t) * L, label[v]))
        if not cand:
            return None, None, dd
        cost, lab = min(cand)
        if include_offset:
            cost += dd
        return cost, lab, dd

    def _edge_cost_at(
        self, e: int, t: float, dist: Dict[int, float], label: Dict[int, Any]
    ) -> Tuple[Optional[float], Optional[Any]]:
        u, v = self.eu[e], self.ev[e]
        L = self.el[e]
        cand = []
        cu, cv = dist.get(u), dist.get(v)
        if cu is not None:
            cand.append((cu + t * L, label[u]))
        if cv is not None:
            cand.append((cv + (1.0 - t) * L, label[v]))
        if not cand:
            return None, None
        return min(cand)

    def evaluate_building(
        self,
        cx: float,
        cy: float,
        facade_pts: Optional[List[Tuple[float, float]]],
        dist: Dict[int, float],
        label: Dict[int, Any],
        max_snap: float,
        include_offset: bool = False,
        bldg_mode: str = "facade",
    ) -> Tuple[Optional[float], Optional[Any], Optional[float], float, float, float, float]:
        """
        Evaluates a residential block or building using its road-facing facades (cepheler).
        Finds the facade exit point (fx, fy) and fronting road projection (qx, qy)
        that gives the shortest network path to the target facility (e.g. school/park),
        treating the block as if its origin were at that closest-to-facility road facade.
        Returns: (cost, nearest_facility_id, snap_dist, fx, fy, qx, qy)
        """
        if bldg_mode == "centroid" or not facade_pts:
            ne = self.nearest_edge(cx, cy, max_snap)
            if ne is None:
                return None, None, None, cx, cy, cx, cy
            e, t, qx, qy, dd = ne
            rcost, lab = self._edge_cost_at(e, t, dist, label)
            if rcost is None:
                return None, None, dd, cx, cy, qx, qy
            cost = (rcost + dd) if include_offset else rcost
            return cost, lab, dd, cx, cy, qx, qy

        pts = _thin(facade_pts, 4.0)
        if not pts:
            pts = [(cx, cy)]

        # 1. Inspect nearest road for each facade point around the perimeter
        perim_snaps: List[Tuple[float, float, int, float, float, float, float]] = []
        min_dd = INF
        for fx, fy in pts:
            ne = self.nearest_edge(fx, fy, max_snap)
            if ne is not None:
                e, t, qx, qy, dd = ne
                perim_snaps.append((fx, fy, e, t, qx, qy, dd))
                if dd < min_dd:
                    min_dd = dd

        if not perim_snaps:
            return None, None, None, cx, cy, cx, cy

        # 2. Street-frontage band: all facades facing bounding roads around this block
        frontage_tol = min(max_snap, max(min_dd + 25.0, min_dd * 3.0, 32.0))

        best_key = None
        best_res = None

        # Check all candidate edges within frontage_tol of each facade point
        for fx, fy, e0, t0, qx0, qy0, dd0 in perim_snaps:
            if dd0 > frontage_tol:
                continue
            cand_edges = [(e0, t0, qx0, qy0, dd0)]
            for ce in self.edges_within_distance(fx, fy, frontage_tol):
                if ce[0] != e0:
                    cand_edges.append(ce)
            for e, t, qx, qy, dd in cand_edges:
                rcost, lab = self._edge_cost_at(e, t, dist, label)
                if rcost is None:
                    continue
                total_cost = (rcost + dd) if include_offset else rcost
                # Prioritize shortest network distance to facility, break ties by closest facade-to-road perpendicular distance
                key = (round(total_cost, 2), round(dd, 3))
                if best_key is None or key < best_key:
                    best_key = key
                    best_res = (total_cost, lab, dd, fx, fy, qx, qy)

        if best_res is not None:
            return best_res

        # 3. Fallback: if no road in frontage_tol was reached, check any facade snap up to max_snap
        for fx, fy, e, t, qx, qy, dd in perim_snaps:
            rcost, lab = self._edge_cost_at(e, t, dist, label)
            if rcost is None:
                continue
            total_cost = (rcost + dd) if include_offset else rcost
            key = (round(total_cost, 2), round(dd, 3))
            if best_key is None or key < best_key:
                best_key = key
                best_res = (total_cost, lab, dd, fx, fy, qx, qy)

        if best_res is not None:
            return best_res

        # Snapped to an isolated road segment not reached by any facility
        closest = min(perim_snaps, key=lambda item: item[6])
        fx, fy, _e, _t, qx, qy, dd = closest
        return None, None, dd, fx, fy, qx, qy


# ----------------------------------------------------------------------
# Thinning & Polygon Helpers
# ----------------------------------------------------------------------
def _thin(points: List[Tuple[float, float]], min_gap: float) -> List[Tuple[float, float]]:
    out = []
    last = None
    for p in points:
        if last is None or math.hypot(p[0] - last[0], p[1] - last[1]) >= min_gap:
            out.append(p)
            last = p
    return out


# ----------------------------------------------------------------------
# High-Level Analysis Workflow
# ----------------------------------------------------------------------
def analyze(
    roads: List[Tuple[Any, List[Tuple[float, float]]]],
    parks: List[Dict[str, Any]],
    buildings: List[Any],
    params: Dict[str, Any],
    progress: Optional[Callable[[float], None]] = None,
    status: Optional[Callable[[str], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    """
    Main accessibility & facility allocation pipeline.
    All inputs and outputs are clean Python structures, fully testable without QGIS GUI.
    """
    progress = progress or (lambda p: None)
    status = status or (lambda s: None)
    thresholds = sorted(set(params["thresholds"]))
    max_t = thresholds[-1]
    max_snap = float(params.get("max_snap", 200.0))
    include_offset = bool(params.get("include_offset", False))
    bldg_mode = str(params.get("bldg_mode", "facade"))
    gap_tol = float(params.get("gap_tol", 15.0))
    stats: Dict[str, Any] = {}

    cell = max(30.0, gap_tol * 2.0)
    net = RoadNetwork(cell_size=cell, cancelled=cancelled)

    status("status_building_graph")
    net.add_lines(roads, node_crossings=bool(params.get("node_crossings", True)))
    stats["segments"] = net.segment_count
    stats["nodes"] = len(net.nx)
    stats["components_before"] = net.component_count()
    progress(30)

    status("status_healing_gaps")
    n_node, n_seg = net.heal_gaps(gap_tol, bool(params.get("only_disconnected", False)))
    stats["bridges_node"] = n_node
    stats["bridges_segment"] = n_seg
    stats["components_after"] = net.component_count()
    progress(45)

    status("status_snapping_parks")
    sources = []
    access_points = []
    unsnapped_parks = []
    mode = params.get("origin_mode", "boundary")

    for k, park in enumerate(parks):
        if k % 200 == 0 and cancelled is not None and cancelled():
            raise Cancelled()
        if mode == "boundary" and park.get("ring"):
            seeds = _thin(park["ring"], 5.0)
            multi_street = True
        else:
            seeds = [park["centroid"]]
            multi_street = bool(park.get("ring"))
        snapped_nodes = net.add_facility_sources(seeds, max_snap, multi_street=multi_street)
        if not snapped_nodes:
            unsnapped_parks.append(park["id"])
            continue
        for node, off, px, py in snapped_nodes:
            sources.append((node, off if include_offset else 0.0, park["id"]))
            access_points.append((park["id"], px, py, off))

    stats["parks_total"] = len(parks)
    stats["parks_unsnapped"] = len(unsnapped_parks)
    stats["parks_snapped"] = len(parks) - len(unsnapped_parks)
    stats["edges"] = len(net.eu)
    progress(60)

    status("status_dijkstra")
    max_edge_len = max(net.el) if net.el else 0.0
    dist, label = net.dijkstra(sources, max_t + max_edge_len + 50.0)
    stats["nodes_reached"] = sum(1 for d in dist.values() if d <= max_t)
    progress(75)

    status("status_clipping_pieces")
    pieces, piece_len = net.service_pieces(dist, label, thresholds)
    progress(85)

    status("status_eval_buildings")
    speed_mps = float(params.get("speed_kmh", 4.8)) * 1000.0 / 3600.0
    b_out = []
    b_connectors = []
    unsnapped_b = unreached_b = 0
    park_alloc: Dict[Any, Dict[str, Any]] = {
        p["id"]: {"buildings": 0, "weight": 0.0, "distances": [], "area_m2": p.get("area_m2", 0.0)}
        for p in parks
    }

    for k, b_item in enumerate(buildings):
        if k % 2000 == 0 and cancelled is not None and cancelled():
            raise Cancelled()
        if len(b_item) >= 5:
            bid, bx, by, w, facade_pts = b_item[0], b_item[1], b_item[2], b_item[3], b_item[4]
        else:
            bid, bx, by, w = b_item[0], b_item[1], b_item[2], b_item[3]
            facade_pts = None

        cost, lab, snap_d, fx, fy, qx, qy = net.evaluate_building(
            bx, by, facade_pts, dist, label, max_snap, include_offset, bldg_mode=bldg_mode
        )
        if snap_d is None:
            unsnapped_b += 1
        elif cost is None or cost > max_t:
            unreached_b += 1
            cost = None
        else:
            # Successfully reached and allocated to nearest facility
            if lab in park_alloc:
                park_alloc[lab]["buildings"] += 1
                park_alloc[lab]["weight"] += w
                park_alloc[lab]["distances"].append(cost)

        b_out.append((bid, bx, by, w, cost, lab, snap_d))
        b_connectors.append((bid, bx, by, fx, fy, qx, qy, cost, lab, snap_d))

    stats["buildings_total"] = len(buildings)
    stats["buildings_unsnapped"] = unsnapped_b
    stats["buildings_unreached"] = unreached_b

    # Breakdown per threshold
    per_t = {}
    total_w = sum(b[3] for b in buildings)
    for t in thresholds:
        cnt = 0
        wsum = 0.0
        for b in b_out:
            if b[4] is not None and b[4] <= t:
                cnt += 1
                wsum += b[3]
        per_t[t] = {"buildings": cnt, "weight": wsum, "road_m": piece_len[t]}
    stats["per_threshold"] = per_t
    stats["total_weight"] = total_w

    costs = [b[4] for b in b_out if b[4] is not None]
    stats["mean_cost"] = statistics.mean(costs) if costs else None
    stats["median_cost"] = statistics.median(costs) if costs else None
    stats["speed_mps"] = speed_mps

    # P-median & Facility Allocation Summary Table
    allocations_summary = {}
    for pid, data in park_alloc.items():
        d_list = data["distances"]
        allocations_summary[pid] = {
            "buildings": data["buildings"],
            "weight": data["weight"],
            "mean_dist": statistics.mean(d_list) if d_list else None,
            "median_dist": statistics.median(d_list) if d_list else None,
            "area_m2": data["area_m2"],
        }
    stats["allocations"] = allocations_summary

    progress(95)

    return {
        "thresholds": thresholds,
        "pieces": pieces,
        "bridges": net.bridges,
        "access_points": access_points,
        "unsnapped_parks": unsnapped_parks,
        "buildings": b_out,
        "building_connectors": b_connectors,
        "allocations": allocations_summary,
        "stats": stats,
    }
