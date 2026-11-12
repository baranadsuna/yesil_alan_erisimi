# -*- coding: utf-8 -*-
"""Unit tests for Multilingual Internationalization (i18n) module."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import i18n


class TestI18n(unittest.TestCase):
    def test_languages_present(self):
        expected_langs = {"en", "tr", "zh", "es", "id"}
        self.assertEqual(set(i18n.LANGUAGES.keys()), expected_langs)
        self.assertEqual(set(i18n.STRINGS.keys()), expected_langs)

    def test_all_keys_in_all_languages(self):
        en_keys = set(i18n.STRINGS["en"].keys())
        for lang, string_map in i18n.STRINGS.items():
            lang_keys = set(string_map.keys())
            missing = en_keys - lang_keys
            self.assertEqual(
                missing,
                set(),
                f"Language '{lang}' is missing string keys: {missing}",
            )
            # Verify no empty values
            for k, v in string_map.items():
                self.assertTrue(
                    isinstance(v, str) and len(v.strip()) > 0,
                    f"Empty string for key '{k}' in language '{lang}'",
                )

    def test_tr_function_fallback_and_format(self):
        # Default English
        self.assertEqual(i18n.tr("btn_run", "en"), "Start Analysis")
        # Turkish
        self.assertEqual(i18n.tr("btn_run", "tr"), "Analizi Başlat")
        # Chinese
        self.assertEqual(i18n.tr("btn_run", "zh"), "开始分析")
        # Spanish
        self.assertEqual(i18n.tr("btn_run", "es"), "Iniciar Análisis")
        # Indonesian
        self.assertEqual(i18n.tr("btn_run", "id"), "Mulai Analisis")
        # Fallback to English on unknown lang
        self.assertEqual(i18n.tr("btn_run", "xx"), "Start Analysis")
        # Formatting support
        formatted = i18n.tr("status_completed", "en", 3.25)
        self.assertIn("3.2", formatted)


if __name__ == "__main__":
    unittest.main()
