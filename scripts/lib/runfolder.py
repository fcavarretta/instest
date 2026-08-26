"""Output naming (FC design decision, 2026-08-25 — replaces dated run folders):
artifacts sit beside the audio file (or in an override folder), named after it:
<stem>.transcript.md, <stem>.questions.gift, <stem>.questions.json,
<stem>.metadata.yaml. Never-erase: if artifacts for <stem> already exist, the
run uses a numbered stem <stem>.2, <stem>.3, …
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .config import RunConfig
from .costs import CallUsage

_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)

# metadata.yaml is absent on purpose: it appends across phases (see write_metadata).
ROLES = ("transcript.md", "questions.gift", "questions.json")


@dataclass(frozen=True)
class OutputPlan:
    directory: Path
    stem: str

    def path(self, role: str) -> Path:
        return self.directory / f"{self.stem}.{role}"

    def describe(self) -> str:
        return str(self.directory / f"{self.stem}.*")


def plan_outputs(source: Path, out_dir: Path | None = None, roles: tuple[str, ...] = ROLES) -> OutputPlan:
    """source = the audio file, or an existing X.transcript.md in --generate-only.

    `roles` = the artifacts this run will write; the never-erase numbering only
    considers those, so a generate-only run pairs its questions with the
    existing transcript instead of bumping to a new stem."""
    directory = out_dir or source.parent
    base = source.stem
    if base.endswith(".transcript"):
        base = base[: -len(".transcript")]
    stem, n = base, 1
    while any((directory / f"{stem}.{role}").exists() for role in roles):
        n += 1
        stem = f"{base}.{n}"
    return OutputPlan(directory, stem)


def find_latest_transcript(source: Path, out_dir: Path | None = None) -> Path:
    """Most recent X*.transcript.md for this audio file (numbered re-runs included)."""
    import glob as _glob

    directory = out_dir or source.parent
    candidates = list(directory.glob(f"{_glob.escape(source.stem)}*.transcript.md"))
    if not candidates:
        raise FileNotFoundError(f"no transcript found for {source.stem} in {directory} — run the transcribe step first")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _write(plan: OutputPlan, role: str, text: str) -> Path:
    plan.directory.mkdir(parents=True, exist_ok=True)
    path = plan.path(role)
    path.write_text(text, encoding="utf-8")
    return path


def write_text(plan: OutputPlan, role: str, text: str) -> Path:
    return _write(plan, role, text)


def write_transcript(plan: OutputPlan, cfg: RunConfig, text: str, usage: CallUsage) -> Path:
    today = datetime.date.today().isoformat()
    session_txt = f" S{cfg.session_id}" if cfg.session_id is not None else ""
    header = {
        "title": f"{cfg.course_code}{session_txt} transcript",
        "created": today,
        "modified": today,
        "intent": "clean lecture transcript, source for question generation",
        "tags": ["tsct", "transcript", cfg.course_code.lower()],
        "course_name": cfg.course_name,
        "session_date": cfg.session_date,
        "audio_file": cfg.audio_file.name if cfg.audio_file else None,
        "model": usage.model,
        "dominant_language": cfg.dominant_language,
        "prompt_tokens": usage.prompt_tokens,
        "output_tokens": usage.output_tokens,
    }
    front = yaml.safe_dump(header, sort_keys=False, allow_unicode=True)
    return _write(plan, "transcript.md", f"---\n{front}---\n\n{text.strip()}\n")


def read_transcript(path: Path) -> str:
    """Read a transcript for --generate-only, stripping the YAML header if present."""
    if not path.exists():
        raise FileNotFoundError(f"transcript not found: {path}")
    return _FRONT_MATTER.sub("", path.read_text(encoding="utf-8"), count=1).strip()


def write_metadata(plan: OutputPlan, data: dict) -> Path:
    """Appends across phases: a transcribe-only run then a generate-only run
    accumulate their calls in the same X.metadata.yaml (a log grows, it is not erased)."""
    path = plan.path("metadata.yaml")
    if path.exists():
        try:
            existing = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            existing = {}
        calls = (existing.get("calls") or []) + (data.get("calls") or [])
        estimates = [c.get("usd_estimate") for c in calls]
        data = {
            **existing,
            **data,
            "calls": calls,
            "total_usd_estimate": round(sum(e for e in estimates), 4) if all(e is not None for e in estimates) else None,
        }
    return _write(plan, "metadata.yaml", yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
