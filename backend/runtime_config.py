from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import yaml

    YAML_READY = True
except Exception:
    yaml = None
    YAML_READY = False


def _default_config() -> dict[str, Any]:
    return {
        "app": {
            "name": "Asseri Modular AI",
            "version": "2.2.0",
            "max_message_chars": 0,
        },
        "compute": {
            "prefer_gpu": True,
            "allow_torch_cuda": True,
            "allow_native_cpp": False,
            "max_matrix_size": 128,
        },
        "learning": {
            "max_candidate_updates_per_30_msgs": 10,
            "min_candidate_confidence": 0.82,
            "min_candidate_support_signals": 2,
        },
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def _load_from_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}

    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    if path.suffix.lower() in {".yaml", ".yml"} and YAML_READY and yaml is not None:
        try:
            data = yaml.safe_load(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    out = dict(config)
    max_chars = os.getenv("ASSERI_MAX_MESSAGE_CHARS", "").strip()
    if max_chars:
        try:
            out.setdefault("app", {})["max_message_chars"] = max(0, int(max_chars))
        except Exception:
            pass
    prefer_gpu = os.getenv("ASSERI_PREFER_GPU", "").strip().lower()
    if prefer_gpu in {"1", "true", "yes", "on"}:
        out.setdefault("compute", {})["prefer_gpu"] = True
    if prefer_gpu in {"0", "false", "no", "off"}:
        out.setdefault("compute", {})["prefer_gpu"] = False
    return out


def load_runtime_config(base_dir: Path) -> dict[str, Any]:
    config_dir = base_dir / "config"
    default = _default_config()
    cfg_yaml = _load_from_file(config_dir / "system.yaml")
    cfg_json = _load_from_file(config_dir / "system.json")
    merged = _deep_merge(default, cfg_yaml)
    merged = _deep_merge(merged, cfg_json)
    merged = _apply_env_overrides(merged)
    return merged

