python
import os
import json
import unittest
import tempfile

from src.non_ui_components.configurations_manager import ConfigurationsManager


class TestConfigurationsManager(unittest.TestCase):

    def test_initialization_uses_existing_config_and_sets_rgb_components(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = os.path.join(tmpdir, "config.json")
            # First run creates the file with defaults
            _ = ConfigurationsManager(cfg_path)
            # Second run reads the existing config
            cm = ConfigurationsManager(cfg_path)

            self.assertEqual(cm.config_file_path, cfg_path)
            # Derived RGB components from defaults
            self.assertEqual((cm.FILE_EXPLORER_GRID_COLOR_R,
                              cm.FILE_EXPLORER_GRID_COLOR_G,
                              cm.FILE_EXPLORER_GRID_COLOR_B), (220, 220, 220))
            self.assertEqual((cm.FILE_EXPLORER_ROW_HOVER_R,
                              cm.FILE_EXPLORER_ROW_HOVER_G,
                              cm.FILE_EXPLORER_ROW_HOVER_B), (240, 240, 240))
            self.assertEqual((cm.FILE_EXPLORER_DRAGGED_ROW_HOVER_R,
                              cm.FILE_EXPLORER_DRAGGED_ROW_HOVER_G,
                              cm.FILE_EXPLORER_DRAGGED_ROW_HOVER_B), (140, 200, 240))
            # Nested color value loaded
            self.assertEqual(cm.BOTTOM_STRIP_TEXT_COLOR, "rgb(100, 100, 100)")

    def test_set_attr_updates_attribute_and_config_for_string_and_list_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = os.path.join(tmpdir, "config.json")
            cm = ConfigurationsManager(cfg_path)

            # Update a top-level attribute
            cm.set_attr("WINDOW_WIDTH", 1024)
            self.assertEqual(cm.WINDOW_WIDTH, 1024)
            self.assertEqual(cm.config["WINDOW_WIDTH"], 1024)

            # Update a nested attribute via list key path
            cm.set_attr(["fonts", "font_sizes", "TEXT_FONT_SIZE"], 18)
            self.assertEqual(cm.TEXT_FONT_SIZE, 18)
            self.assertEqual(cm.config["fonts"]["font_sizes"]["TEXT_FONT_SIZE"], 18)

    def test_get_returns_attribute_or_nested_config_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = os.path.join(tmpdir, "config.json")
            cm = ConfigurationsManager(cfg_path)

            # Attribute-backed key
            self.assertEqual(cm.get("WINDOW_WIDTH"), cm.WINDOW_WIDTH)

            # Nested key path
            nested_path = ["fonts", "font_sizes", "TEXT_FONT_SIZE"]
            self.assertEqual(cm.get(nested_path), cm.config["fonts"]["font_sizes"]["TEXT_FONT_SIZE"])

    def test_missing_config_path_creates_file_with_defaults_and_initializes_attributes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = os.path.join(tmpdir, "config.json")
            self.assertFalse(os.path.exists(cfg_path))

            cm = ConfigurationsManager(cfg_path)

            self.assertTrue(os.path.exists(cfg_path))
            with open(cfg_path, "r") as f:
                saved_cfg = json.load(f)

            # File content matches loaded configuration
            self.assertEqual(saved_cfg, cm.config)

            # Attributes initialized from defaults
            self.assertEqual(cm.TEXT_FONT, saved_cfg["fonts"]["TEXT_FONT"])
            self.assertEqual(cm.WINDOW_WIDTH, saved_cfg["WINDOW_WIDTH"])
            self.assertEqual(cm.DEFAULT_PATH, saved_cfg["DEFAULT_PATH"])

    def test_set_attr_invalid_rgb_string_for_category_raises_on_parsing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = os.path.join(tmpdir, "config.json")
            cm = ConfigurationsManager(cfg_path)

            with self.assertRaises(ValueError):
                cm.set_attr("FILE_EXPLORER_GRID_COLOR", "rgb(a, b, c)")

    def test_set_attr_non_string_value_for_y_n_toggle_results_in_false_and_config_raw_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = os.path.join(tmpdir, "config.json")
            cm = ConfigurationsManager(cfg_path)

            cm.set_attr("SHOW_HIDDEN_ITEMS", True)

            # Property setter interprets non 'Y'/'N' as False
            self.assertFalse(cm.SHOW_HIDDEN_ITEMS)
            # Config dict stores the raw provided value
            self.assertIs(cm.config["SHOW_HIDDEN_ITEMS"], True)


if __name__ == "__main__":
    unittest.main()