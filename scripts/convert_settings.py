"""Convert old Coin & Stock Monitor JSON settings to the grouped layout.

Reads/writes JSON files only. Does not access Windhawk, Explorer or the registry.
"""

import argparse
import json
import sys
from pathlib import Path


GROUPS = ("Content", "Appearance", "Placement", "DataSource")
KEY_MAP = {
    "Symbols": "Content.Symbols",
    "EntryPrices": "Content.EntryPrices",
    "RefreshSeconds": "Content.RefreshSeconds",
    "ColorPreset": "Appearance.Preset",
    "TextColor": "Appearance.CustomColors.Text",
    "UpColor": "Appearance.CustomColors.Gain",
    "DownColor": "Appearance.CustomColors.Loss",
    "BackgroundColor": "Appearance.CustomColors.Background",
    "TextAlign": "Placement.TextAlign",
    "LeftOffset": "Placement.LeftOffset",
    "Width": "Placement.Width",
    "ApiUrl": "DataSource.ApiUrl",
    "PriceKey": "DataSource.PriceKey",
}
INTEGER_KEYS = {"Content.RefreshSeconds", "Placement.LeftOffset", "Placement.Width"}
VALID_KEYS = set(KEY_MAP.values()) | {"Appearance.Background"}


def _flatten(settings, prefix=""):
    if not isinstance(settings, dict):
        raise ValueError("Settings must be a JSON object.")
    flat = {}
    for key, value in settings.items():
        if not isinstance(key, str):
            raise ValueError("Setting names must be strings.")
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            if name not in (*GROUPS, "Appearance.CustomColors"):
                raise ValueError(f"Unknown group or object-valued setting: {name}")
            children = _flatten(value, name)
        else:
            children = {name: value}
        for child, item in children.items():
            if child in flat:
                raise ValueError(f"Duplicate setting: {child}")
            flat[child] = item
    return flat


def convert_settings(settings):
    """Preserve supplied values; leave omitted settings to Windhawk's defaults."""
    flat = _flatten(settings)
    converted = {}

    def put(key, value):
        if key in converted and converted[key] != value:
            raise ValueError(f"Conflicting old and grouped values for {key}")
        converted[key] = value

    for key, value in flat.items():
        if key in ("BackgroundMode", "BackgroundSizing"):
            continue
        target = KEY_MAP.get(key, key)
        if target not in VALID_KEYS:
            raise ValueError(f"Unknown setting: {key}; conversion stopped to avoid losing it.")
        if target in INTEGER_KEYS:
            if type(value) is not int:
                raise ValueError(f"{key} must be an integer.")
        elif not isinstance(value, str):
            raise ValueError(f"{key} must be a string.")
        put(target, value)

    if "BackgroundMode" in flat or "BackgroundSizing" in flat:
        mode = flat.get("BackgroundMode", "transparent")
        sizing = flat.get("BackgroundSizing", "area")
        if mode not in ("transparent", "solid"):
            raise ValueError("BackgroundMode must be transparent or solid.")
        if sizing not in ("area", "text"):
            raise ValueError("BackgroundSizing must be area or text.")
        background = "text" if mode == "solid" and sizing == "text" else mode
        put("Appearance.Background", background)

    choices = {
        "Appearance.Preset": ("", "custom", "slate", "charcoal", "warm_graphite", "blue_amber", "porcelain"),
        "Appearance.Background": ("transparent", "solid", "text"),
        "Placement.TextAlign": ("left", "right"),
    }
    for key, options in choices.items():
        if key in converted and converted[key] not in options:
            raise ValueError(f"Unsupported value for {key}.")

    result = {}
    for key, value in converted.items():
        group, *parts = key.split(".")
        node = result.setdefault(group, {})
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return {group: result[group] for group in GROUPS if group in result}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Exported settings JSON file")
    parser.add_argument("-o", "--output", type=Path, help="New output file; omit to print JSON")
    args = parser.parse_args(argv)
    try:
        original = json.loads(args.input.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_object)
        output = json.dumps(convert_settings(original), ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8", newline="\n") as file:
                file.write(output)
        else:
            sys.stdout.write(output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Conversion failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
