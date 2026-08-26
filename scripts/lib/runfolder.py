"""Output naming (FC design decisions, 2026-08-25/26):
artifacts sit beside the audio file (or in an override folder), named after it:
<stem>.transcript.md, <stem>.questions.gift, <stem>.questions.json,
<stem>.metadata.yaml.

Head convention (2026-08-26, replaces the numbered-stem scheme): the canonical
name always holds the MOST RECENT version. Before overwriting, the existing
file is archived in place by appending its own modification timestamp before
the final extension: x.questions-2026-08-25 19-36-13.gift. metadata.yaml is
the exception: it is a log and accumulates calls in place (see write_metadata).
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

@dataclass(frozen=True)
class OutputPlan:
    directory: Path
    stem: str

    def path(self, role: str) -> Path:
        return self.directory / f"{self.stem}.{role}"

    def describe(self) -> str:
        return str(self.directory / f"{self.stem}.*")


def plan_outputs(source: Path, out_dir: Path | None = None) -> OutputPlan:
    """source = the audio file, or an existing X.transcript.md in --generate-only."""
    directory = out_dir or source.parent
    base = source.stem
    if base.endswith(".transcript"):
        base = base[: -len(".transcript")]
    return OutputPlan(directory, base)


def find_latest_transcript(source: Path, out_dir: Path | None = None) -> Path:
    """Head convention: the most recent transcript is the one with the canonical name."""
    directory = out_dir or source.parent
    path = directory / f"{source.stem}.transcript.md"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run the transcribe step first")
    return path


def _archive_if_exists(path: Path) -> None:
    """Head convention: before replacing a file, move the existing one into an
    old/ subfolder beside it, renamed with its own mtime stamp."""
    if not path.exists():
        return
    old_dir = path.parent / "old"
    old_dir.mkdir(exist_ok=True)
    mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime)
    head, ext = path.name.rsplit(".", 1)
    archived = old_dir / f"{head}-{mtime.strftime('%Y-%m-%d %H-%M-%S')}.{ext}"
    if archived.exists():  # same-second collision: add microseconds
        archived = old_dir / f"{head}-{mtime.strftime('%Y-%m-%d %H-%M-%S.%f')}.{ext}"
    path.rename(archived)
    print(f"♻️  previous {path.name} kept as old/{archived.name}")


def _write(plan: OutputPlan, role: str, text: str, archive: bool = True) -> Path:
    plan.directory.mkdir(parents=True, exist_ok=True)
    path = plan.path(role)
    if archive:
        _archive_if_exists(path)
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
    """metadata.yaml is a log: it accumulates calls in place (never archived) —
    a transcribe phase, its generate phase, and later regenerations all append."""
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
    return _write(plan, "metadata.yaml", yaml.safe_dump(data, sort_keys=False, allow_unicode=True), archive=False)
