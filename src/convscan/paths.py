"""Where a run's data and reports go.

A run has two folders. The data folder (data_dir/<name>) holds run.json and one CSV per query,
including learner-level records: it stays local and is deleted at sign-off. The reports folder
(reports_dir/<name>) holds the reports, idmap.csv and a copy of run.json: it's what gets shared.
"""
from __future__ import annotations

import datetime
import pathlib
import re

# Folder names that mean "synced to a cloud service", compared case-insensitively.
_SYNCED = ("onedrive", "dropbox", "google drive", "googledrive", "my drive", "icloud drive",
           "mobile documents", "box sync", "box")


def resolve(name_or_path: str, cfg: dict) -> tuple[pathlib.Path, pathlib.Path]:
    """(data folder, reports folder) for a run.

    A plain name ("batch01_pre") goes under data_dir and reports_dir. A path ("runs/batch01_pre",
    or absolute) keeps the older single-folder layout: data there, reports in its reports/ folder.
    """
    p = pathlib.Path(name_or_path).expanduser()
    if p.is_absolute() or len(p.parts) > 1:
        return p, p / "reports"
    reports = cfg["reports_dir"]
    if cfg.get("reports_by_date"):   # one folder per day: the date the run name starts with, else today
        m = re.match(r"\d{4}-\d{2}-\d{2}(?=_|$)", p.name)
        reports = reports / (m.group(0) if m else datetime.date.today().isoformat())
    return cfg["data_dir"] / p, reports / p


def shared_location(path: pathlib.Path) -> str | None:
    """Why a folder is a poor place for learner data (synced or inside a Git repo), or None."""
    path = pathlib.Path(path).expanduser().resolve()
    for part in path.parts:
        low = part.lower()
        if any(low == s or low.startswith(s + " ") or low.startswith(s + "-") for s in _SYNCED):
            return f"it's inside a synced folder ({part})"
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            return f"it's inside a Git repository ({parent})"
    return None
