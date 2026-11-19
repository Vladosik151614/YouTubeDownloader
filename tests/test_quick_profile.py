import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from app.main_window_profile import on_quick_codec_changed, on_quick_upscale_toggled
from app.toggle_switch import ToggleSwitch


class QuickProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        window = SimpleNamespace(
            settings={"auto_convert": False, "upscale_to_profile": False, "default_codec": "original"},
            quick_auto_convert_switch=ToggleSwitch(False),
        )
        window.quick_upscale_switch = ToggleSwitch(False)
        window.quick_upscale_switch.toggled.connect(lambda value: on_quick_upscale_toggled(window, value))
        return window

    @patch("app.main_window_profile.save_settings")
    def test_upscale_then_original_preserves_processing(self, _save):
        window = self.make_window()
        window.quick_upscale_switch.setChecked(True)
        on_quick_codec_changed(window, 0)
        self.assertTrue(window.settings["upscale_to_profile"])
        self.assertTrue(window.settings["auto_convert"])
        self.assertTrue(window.quick_auto_convert_switch.isChecked())

    @patch("app.main_window_profile.save_settings")
    def test_codec_then_original_then_upscale_enables_processing(self, _save):
        window = self.make_window()
        on_quick_codec_changed(window, 1)
        self.assertTrue(window.quick_auto_convert_switch.isChecked())
        on_quick_codec_changed(window, 0)
        # Other profile options may still require processing with original codec.
        self.assertTrue(window.quick_auto_convert_switch.isChecked())
        window.quick_upscale_switch.setChecked(True)
        self.assertTrue(window.settings["auto_convert"])
        self.assertTrue(window.quick_auto_convert_switch.isChecked())

    @patch("app.main_window_profile.save_settings")
    def test_changing_codec_syncs_master_without_emitting_toggle(self, _save):
        window = self.make_window()
        toggled = []
        window.quick_auto_convert_switch.toggled.connect(toggled.append)
        on_quick_codec_changed(window, 1)
        self.assertTrue(window.settings["auto_convert"])
        self.assertTrue(window.quick_auto_convert_switch.isChecked())
        self.assertEqual(toggled, [])
