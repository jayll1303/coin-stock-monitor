import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from convert_settings import convert_settings


class ConvertSettingsTests(unittest.TestCase):
    def test_existing_user_example_is_preserved(self):
        old = {
            "ApiUrl": "https://example.test/{symbol}", "PriceKey": "price",
            "Symbols": "BTC-USD|ETH-USD|AAPL", "EntryPrices": "BTC-USD=60000|NVL.VN=12,005",
            "TextAlign": "left", "ColorPreset": "blue_amber", "TextColor": "#19FF00",
            "UpColor": "#00A850", "DownColor": "#E0301E", "BackgroundMode": "transparent",
            "BackgroundColor": "#1E2633", "RefreshSeconds": 60, "LeftOffset": 8, "Width": 480,
        }
        new = convert_settings(old)
        self.assertEqual(new["Content"]["EntryPrices"], old["EntryPrices"])
        self.assertEqual(new["DataSource"], {"ApiUrl": old["ApiUrl"], "PriceKey": "price"})
        self.assertEqual(new["Appearance"]["Preset"], "blue_amber")
        self.assertEqual(new["Appearance"]["CustomColors"], {
            "Text": "#19FF00", "Gain": "#00A850", "Loss": "#E0301E", "Background": "#1E2633"})
        self.assertEqual(new["Appearance"]["Background"], "transparent")
        self.assertEqual(new["Placement"], {"TextAlign": "left", "LeftOffset": 8, "Width": 480})
        self.assertEqual(new["Content"]["Symbols"], old["Symbols"])
        self.assertEqual(new["Content"]["RefreshSeconds"], 60)

    def test_background_modes(self):
        for mode, sizing, expected in [
            ("transparent", "area", "transparent"), ("transparent", "text", "transparent"),
            ("solid", "area", "solid"), ("solid", "text", "text")]:
            with self.subTest(mode=mode, sizing=sizing):
                result = convert_settings({"BackgroundMode": mode, "BackgroundSizing": sizing})
                self.assertEqual(result["Appearance"]["Background"], expected)

    def test_empty_theme_following_and_partial_configs(self):
        self.assertEqual(convert_settings({"TextColor": ""}), {"Appearance": {"CustomColors": {"Text": ""}}})
        self.assertEqual(convert_settings({}), {})
        self.assertEqual(convert_settings({"Width": 0, "LeftOffset": 0}), {"Placement": {"Width": 0, "LeftOffset": 0}})

    def test_grouped_nested_and_flat_are_idempotent(self):
        grouped = {"Appearance": {"Preset": "porcelain", "Background": "text", "CustomColors": {"Text": ""}}}
        self.assertEqual(convert_settings(grouped), grouped)
        self.assertEqual(convert_settings({"Appearance.Preset": "porcelain", "Appearance.Background": "text", "Appearance.CustomColors.Text": ""}), grouped)

    def test_conflicting_or_invalid_values_fail(self):
        for data in [
            {"Width": 500, "Placement.Width": 480}, {"TextColor": "#fff", "Appearance.CustomColors.Text": ""},
            {"BackgroundMode": "solid", "Appearance.Background": "transparent"}, {"UnusedSetting": 1},
            {"Width": True}, {"TextColor": 123}, {"Symbols": []}, {"BackgroundMode": "unknown"},
            {"BackgroundSizing": "unknown"}, {"Appearance.Background": "unknown"},
            {"UnknownGroup": {}}, {"Symbols": {}}, {"Appearance": {"Unknown": {}}}, []]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                convert_settings(data)

    def test_converter_keys_match_runtime_setting_reads(self):
        import re
        source = (Path(__file__).resolve().parents[1] / "coin-stock-monitor.wh.cpp").read_text(encoding="utf-8")
        runtime = source[source.index("void LoadSettings()") :]
        reads = set(re.findall(r'(?:StringSetting::make|Wh_GetIntSetting|ColorSetting)\(L"([^"]+)"', runtime))
        from convert_settings import VALID_KEYS
        self.assertEqual(reads, VALID_KEYS)

    def test_cli_keeps_input_and_refuses_to_overwrite(self):
        script = Path(__file__).resolve().parents[1] / "scripts/convert_settings.py"
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "old.json"
            target = Path(folder) / "new.json"
            original = json.dumps({"TextColor": "", "BackgroundMode": "solid", "BackgroundSizing": "text"})
            source.write_text(original, encoding="utf-8-sig")
            command = [sys.executable, str(script), str(source), "-o", str(target)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(json.loads(target.read_text())["Appearance"]["Background"], "text")
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(source.read_text(encoding="utf-8-sig"), original)

    def test_cli_rejects_duplicate_keys(self):
        script = Path(__file__).resolve().parents[1] / "scripts/convert_settings.py"
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "old.json"
            source.write_text('{"TextColor":"", "TextColor":"#123456"}', encoding="utf-8")
            result = subprocess.run([sys.executable, str(script), str(source)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Duplicate JSON key", result.stderr)


if __name__ == "__main__":
    unittest.main()
