"""SCORM Engine runtime blobs (scormregistration.runtime_data).

When the engine hasn't written a learner's state out to scormactivityrt, it is still in this blob:
4 bytes of uncompressed length (little-endian), then a zlib stream holding a <RunTimeData> XML
document. Each <Activity> (one per SCO) has an <ActivityRunTime> with the resume state: Location (the
bookmark), SuspendData, CompletionStatus, SuccessStatus, scores and time. Format confirmed on demo
2026-11-14.

The runner calls summarize() as it reads S10, so only a fingerprint and the bookmarks reach the CSV,
never the learner's raw state.
"""
from __future__ import annotations

import hashlib
import re
import zlib

# Identity attributes differ between an Original and its copy (or are internal): left out of the fingerprint.
_SKIP = {"ActivityId", "dbid", "RegistrationId", "LaunchHistoryId", "ActivityObjectiveId"}
# Activity-level attributes that matter for resuming: which SCO, attempts, and attempt status.
_ACTIVITY_KEEP = ("ItemIdentifier", "ActivityAttemptCount", "AttemptCompletionStatus", "AttemptProgressStatus")

_ACTIVITY = re.compile(r"<Activity ([^>]*)>(.*?)</Activity>", re.S)
_RUNTIME = re.compile(r"<ActivityRunTime ([^>]*)>")
_ATTR = re.compile(r'(\w+)="([^"]*)"')


def decode(blob) -> str | None:
    if blob is None:
        return None
    b = bytes(blob)
    if len(b) < 6:
        return None
    try:
        return zlib.decompress(b[4:]).decode("utf-8", "replace")
    except zlib.error:
        return None


def summarize(blob) -> dict:
    """Fingerprint of the resume state, the bookmarks, and how many SCOs carry runtime data."""
    xml = decode(blob)
    if xml is None:
        return {"blob_md5": "", "blob_scos": "", "blob_locations": ""}
    parts, locations, scos = [], [], 0
    for act_attrs, body in _ACTIVITY.findall(xml):
        act = dict(_ATTR.findall(act_attrs))
        rt = _RUNTIME.search(body)
        if not rt:
            continue
        scos += 1
        state = {k: v for k, v in _ATTR.findall(rt.group(1)) if k not in _SKIP}
        if state.get("Location"):
            locations.append(state["Location"])
        parts.append("|".join(f"{k}={act.get(k, '')}" for k in _ACTIVITY_KEEP) + "|"
                     + "|".join(f"{k}={v}" for k, v in sorted(state.items())))
    return {"blob_md5": hashlib.md5("#".join(parts).encode()).hexdigest() if parts else "",
            "blob_scos": scos, "blob_locations": ", ".join(locations)}
