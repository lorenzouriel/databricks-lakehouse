from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

import yaml


def load_settings(settings_path: str | None = None) -> dict[str, Any]:
    """
    Load settings from settings.yaml.
    Resolves run_date: null to today's date.
    """
    if settings_path is None:
        settings_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config",
            "settings.yaml",
        )

    with open(settings_path, "r") as f:
        settings = yaml.safe_load(f)

    run_date_raw = settings.get("pipeline", {}).get("run_date")
    if run_date_raw is None:
        settings["pipeline"]["run_date"] = date.today().isoformat()
    elif isinstance(run_date_raw, (date, datetime)):
        settings["pipeline"]["run_date"] = run_date_raw.strftime("%Y-%m-%d")

    return settings


def get_database_name(settings: dict[str, Any]) -> str:
    return settings["pipeline"]["database_name"]


def get_lookback_days(settings: dict[str, Any], is_initial: bool) -> int:
    key = "lookback_days_initial" if is_initial else "lookback_days_incremental"
    return settings["pipeline"][key]


def get_run_date(settings: dict[str, Any]) -> str:
    return settings["pipeline"]["run_date"]
