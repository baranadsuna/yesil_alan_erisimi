# -*- coding: utf-8 -*-
"""Çekirdek (QGIS'siz) birim testleri:  python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import network as N  # noqa: E402


def grid_roads(n=5, step=100.0):
    lines, rid = [], 0
    for i in range(n):
        lines.append((rid, [(0, i * step), ((n - 1) * step, i * step)])); rid += 1
        lines.append((rid, [(i * step, 0), (i * step, (n - 1) * step)])); rid += 1
    return lines


class TestNetwork(unittest.TestCase):
    def test_grid_distance(self):
        net = N.RoadNetwork()
        net.add_lines(grid_roads(), node_crossings=True)
        self.assertEqual(net.component_count(), 1)
        src = net.add_source_point(0, 0, 10)
        dist, lab = net.dijkstra([(src[0], 0.0, "P")], 1000)
        c, l, _ = net.evaluate_point(300, 300, dist, lab, 10)
        self.assertAlmostEqual(c, 600.0, places=3)
        self.assertEqual(l, "P")

    def test_no_noding_means_no_junction(self):
        net = N.RoadNetwork()
        net.add_lines(grid_roads(), node_crossings=False)
        self.assertGreater(net.component_count(), 1)  # kesişimde düğüm yok

    def test_mid_edge_source_exact(self):
        net = N.RoadNetwork()
        net.add_lines([(1, [(0, 0), (1000, 0)])])
        src = net.add_source_point(500, 30, 100)       # ortadan, 30 m ofset
        self.assertAlmostEqual(src[1], 30.0)
        dist, lab = net.dijkstra([(src[0], 0.0, "P")], 1000)
        c, _, _ = net.evaluate_point(700, 0, dist, lab, 10)
        self.assertAlmostEqual(c, 200.0, places=3)
        pieces, tot = net.service_pieces(dist, lab, [100])
        self.assertAlmostEqual(tot[100], 200.0, places=3)  # 100 sola + 100 sağa

    def test_gap_node_bridge(self):
        net = N.RoadNetwork()
        net.add_lines([(1, [(0, 0), (100, 0)]), (2, [(110, 0), (200, 0)])])
        self.assertEqual(net.component_count(), 2)
        nn, ns = net.heal_gaps(15.0)
        self.assertEqual((nn, ns), (1, 0))
        self.assertEqual(net.component_count(), 1)
        self.assertAlmostEqual(net.bridges[0][4], 10.0)

    def test_gap_too_wide_not_bridged(self):
        net = N.RoadNetwork()
        net.add_lines([(1, [(0, 0), (100, 0)]), (2, [(130, 0), (200, 0)])])
        self.assertEqual(net.heal_gaps(15.0), (0, 0))
        self.assertEqual(net.component_count(), 2)

    def test_gap_t_junction(self):
        net = N.RoadNetwork()
        net.add_lines([(1, [(0, 0), (200, 0)]), (2, [(100, 12), (100, 100)])])
        nn, ns = net.heal_gaps(15.0)
        self.assertEqual((nn, ns), (0, 1))
        self.assertEqual(net.component_count(), 1)
        src = net.add_source_point(100, 100, 5)
        dist, lab = net.dijkstra([(src[0], 0.0, "P")], 1000)
        c, _, _ = net.evaluate_point(0, 0, dist, lab, 5)
        self.assertAlmostEqual(c, 88 + 12 + 100, places=3)

    def test_only_disconnected_avoids_shortcut(self):
        # U biçimli bağlı ağ: iki dikey kol uçları 10 m arayla, ama aynı bileşende
        roads = [(1, [(0, 0), (0, 100), (10, 100)]), (2, [(10, 100), (10, 0)])]
        a = N.RoadNetwork(); a.add_lines(roads)
        self.assertEqual(a.heal_gaps(15.0, True), (0, 0))
        b = N.RoadNetwork(); b.add_lines(roads)
        self.assertEqual(sum(b.heal_gaps(15.0, False)), 1)

    def test_partial_pieces_and_threshold_clip(self):
        net = N.RoadNetwork()
        net.add_lines([(1, [(0, 0), (300, 0)])])
        s = net.add_source_point(0, 0, 5)
        dist, lab = net.dijkstra([(s[0], 0.0, "P")], 250)
        pieces, tot = net.service_pieces(dist, lab, [100, 250])
        self.assertAlmostEqual(tot[100], 100.0)
        self.assertAlmostEqual(tot[250], 250.0)

    def test_analyze_end_to_end(self):
        roads = grid_roads()
        parks = [{"id": 7, "centroid": (0, 0), "ring": []}]
        blds = [(1, 100, 100, 5.0), (2, 400, 400, 20.0), (3, 5000, 5000, 1.0)]
        r = N.analyze(roads, parks, blds,
                      {"thresholds": [250, 500], "gap_tol": 15, "node_crossings": True,
                       "max_snap": 50, "include_offset": True})
        by = {b[0]: b for b in r["buildings"]}
        self.assertAlmostEqual(by[1][4], 200.0, places=3)
        self.assertIsNone(by[2][4])           # 800 m > 500
        self.assertIsNone(by[3][6])           # ağa bağlanamadı
        st = r["stats"]
        self.assertEqual(st["buildings_unsnapped"], 1)
        self.assertEqual(st["per_threshold"][250]["buildings"], 1)
        self.assertAlmostEqual(st["per_threshold"][500]["weight"], 5.0)

    def test_cancel(self):
        net = N.RoadNetwork(cancelled=lambda: True)
        with self.assertRaises(N.Cancelled):
            net.add_lines(grid_roads(40))


if __name__ == "__main__":
    unittest.main()
