"""
file_organizer.py — Flexible, reusable file organization module.

Usage (CLI):
    python file_organizer.py /path/to/folder --sort type --dry-run
    python file_organizer.py /path/to/folder --sort extension --output /organized
    python file_organizer.py /path/to/folder --rule "name_starts_with:t:delete" --rule "name_starts_with:f:keep"

Usage (as a module):
    from file_organizer import FileOrganizer, OrganizerConfig, SortMode, RuleEngine

    rules = RuleEngine.from_specs([
        {"name": "Delete thumbnails", "condition": {"type": "name_starts_with", "value": "t"}, "action": "delete"},
        {"name": "Keep recovered",    "condition": {"type": "name_starts_with", "value": "f"}, "action": "keep"},
    ])
    config = OrganizerConfig(
        sort_mode  = SortMode.TYPE,
        output_dir = "/path/to/output",
        rules      = rules,
        dry_run    = True,
    )
    organizer = FileOrganizer("/path/to/folder", config)
    organizer.run()
"""

import argparse
import fnmatch
import logging
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Sort configuration
# ---------------------------------------------------------------------------

class SortMode(str, Enum):
    TYPE      = "type"
    EXTENSION = "extension"
    NAME      = "name"
    SIZE      = "size"
    DATE      = "date"


DEFAULT_TYPE_MAP: dict[str, list[str]] = {
    "Images":      [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico"],
    "Documents":   [".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".csv",
                    ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx"],
    "Videos":      [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"],
    "Audio":       [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"],
    "Archives":    [".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"],
    "Code":        [".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".cs",
                    ".go", ".rs", ".rb", ".php", ".sh", ".bat", ".ps1"],
    "Executables": [".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage"],
    "Fonts":       [".ttf", ".otf", ".woff", ".woff2"],
    "Data":        [".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env"],
}

# Sub-type map: MainType → {SubFolder → [extensions]}
# Used only when OrganizerConfig.use_subtypes is True.
# Extend or replace per-instance via OrganizerConfig.subtype_map.
DEFAULT_SUBTYPE_MAP: dict[str, dict[str, list[str]]] = {
    "Documents": {
        "PDF":        [".pdf"],
        "Word":       [".doc", ".docx", ".odt", ".rtf"],
        "Excel":      [".xls", ".xlsx", ".xlsm", ".csv"],
        "PowerPoint": [".ppt", ".pptx"],
        "Text":       [".txt", ".md"],
    },
    "Images": {
        "JPEG":  [".jpg", ".jpeg"],
        "PNG":   [".png"],
        "GIF":   [".gif"],
        "SVG":   [".svg"],
        "WebP":  [".webp"],
        "Other": [".bmp", ".tiff", ".ico"],
    },
    "Videos": {
        "MP4":  [".mp4", ".m4v"],
        "MKV":  [".mkv"],
        "AVI":  [".avi"],
        "MOV":  [".mov"],
        "WMV":  [".wmv"],
        "WebM": [".webm"],
        "Other":[".flv"],
    },
    "Audio": {
        "MP3":      [".mp3"],
        "Lossless": [".flac", ".wav"],
        "AAC":      [".aac", ".m4a"],
        "OGG":      [".ogg"],
        "WMA":      [".wma"],
    },
    "Archives": {
        "ZIP": [".zip"],
        "TAR": [".tar", ".gz", ".bz2", ".xz"],
        "7Z":  [".7z"],
        "RAR": [".rar"],
    },
    "Code": {
        "Python":     [".py"],
        "JavaScript": [".js", ".ts"],
        "Web":        [".html", ".css", ".htm"],
        "Java":       [".java"],
        "C_CPP":      [".c", ".cpp", ".h", ".hpp"],
        "CSharp":     [".cs"],
        "Shell":      [".sh", ".bat", ".ps1"],
        "Other":      [".go", ".rs", ".rb", ".php"],
    },
    "Data": {
        "JSON":   [".json"],
        "XML":    [".xml"],
        "YAML":   [".yaml", ".yml"],
        "Config": [".toml", ".ini", ".cfg", ".env"],
    },
}

SIZE_BUCKETS: list[tuple[str, int]] = [
    ("Tiny",   100 * 1024),
    ("Small",  10  * 1024 * 1024),
    ("Medium", 100 * 1024 * 1024),
    ("Large",  1   * 1024 ** 3),
    ("Huge",   float("inf")),
]

DuplicatePolicy = str  # "rename" | "skip" | "overwrite"


# ---------------------------------------------------------------------------
# Filter / Rule engine
# ---------------------------------------------------------------------------

class FilterAction(str, Enum):
    KEEP   = "keep"    # organise and move the file
    DELETE = "delete"  # permanently delete the file
    SKIP   = "skip"    # leave the file exactly where it is


@dataclass
class FilterRule:
    name:      str
    condition: Callable[[Path], bool]
    action:    FilterAction
    priority:  int = 0   # higher value wins when multiple rules match


# ---------------------------------------------------------------------------
# Condition factories
# Call these to build the `condition` callable for a FilterRule.
# ---------------------------------------------------------------------------

class Condition:
    """Static factory methods that return Path → bool callables."""

    @staticmethod
    def name_starts_with(prefix: str) -> Callable[[Path], bool]:
        p = prefix.lower()
        return lambda f: f.stem.lower().startswith(p)

    @staticmethod
    def name_ends_with(suffix: str) -> Callable[[Path], bool]:
        s = suffix.lower()
        return lambda f: f.stem.lower().endswith(s)

    @staticmethod
    def name_contains(substring: str) -> Callable[[Path], bool]:
        sub = substring.lower()
        return lambda f: sub in f.stem.lower()

    @staticmethod
    def extension_in(*exts: str) -> Callable[[Path], bool]:
        normalised = {e.lower().lstrip(".") for e in exts}
        return lambda f: f.suffix.lower().lstrip(".") in normalised

    @staticmethod
    def size_gt(bytes_: int) -> Callable[[Path], bool]:
        return lambda f: _safe_size(f) > bytes_

    @staticmethod
    def size_lt(bytes_: int) -> Callable[[Path], bool]:
        return lambda f: _safe_size(f) < bytes_

    @staticmethod
    def matches_glob(pattern: str) -> Callable[[Path], bool]:
        pat = pattern.lower()
        return lambda f: fnmatch.fnmatch(f.name.lower(), pat)

    @staticmethod
    def matches_regex(pattern: str) -> Callable[[Path], bool]:
        compiled = re.compile(pattern, re.IGNORECASE)
        return lambda f: bool(compiled.search(f.name))

    @staticmethod
    def always() -> Callable[[Path], bool]:
        return lambda f: True

    @staticmethod
    def modified_before(dt: datetime) -> Callable[[Path], bool]:
        return lambda f: datetime.fromtimestamp(_safe_mtime(f)) < dt

    @staticmethod
    def modified_after(dt: datetime) -> Callable[[Path], bool]:
        return lambda f: datetime.fromtimestamp(_safe_mtime(f)) > dt


def _safe_size(f: Path) -> int:
    try:
        return f.stat().st_size
    except OSError:
        return 0


def _safe_mtime(f: Path) -> float:
    try:
        return f.stat().st_mtime
    except OSError:
        return 0.0


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------

# Serialisable spec format used by the desktop app and config files:
#   {"name": "...", "condition": {"type": "name_starts_with", "value": "t"}, "action": "delete", "priority": 0}
#
# Supported condition types:
#   name_starts_with, name_ends_with, name_contains, extension_in,
#   size_gt, size_lt, matches_glob, matches_regex, always

_CONDITION_BUILDERS: dict[str, Callable] = {
    "name_starts_with": lambda v: Condition.name_starts_with(v),
    "name_ends_with":   lambda v: Condition.name_ends_with(v),
    "name_contains":    lambda v: Condition.name_contains(v),
    "extension_in":     lambda v: Condition.extension_in(*([v] if isinstance(v, str) else v)),
    "size_gt":          lambda v: Condition.size_gt(int(v)),
    "size_lt":          lambda v: Condition.size_lt(int(v)),
    "matches_glob":     lambda v: Condition.matches_glob(v),
    "matches_regex":    lambda v: Condition.matches_regex(v),
    "always":           lambda v: Condition.always(),
}


class RuleEngine:
    """Evaluates an ordered list of FilterRules against a Path.

    Rules are sorted by descending priority.  The first matching rule wins.
    If no rule matches, the default action is KEEP (organise normally).
    """

    DEFAULT_ACTION = FilterAction.KEEP

    def __init__(self, rules: Optional[list[FilterRule]] = None):
        self._rules: list[FilterRule] = sorted(
            rules or [], key=lambda r: -r.priority
        )

    def __len__(self) -> int:
        return len(self._rules)

    def __bool__(self) -> bool:
        return bool(self._rules)

    def evaluate(self, file: Path) -> FilterAction:
        for rule in self._rules:
            try:
                if rule.condition(file):
                    return rule.action
            except Exception:
                pass
        return self.DEFAULT_ACTION

    def add(self, rule: FilterRule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: -r.priority)

    def remove(self, index: int) -> None:
        del self._rules[index]

    def rules(self) -> list[FilterRule]:
        return list(self._rules)

    def to_specs(self) -> list[dict]:
        """Serialise all rules to JSON-safe dicts (condition lambdas are not included)."""
        out = []
        for r in self._rules:
            out.append({
                "name":     r.name,
                "action":   r.action.value,
                "priority": r.priority,
                # condition is stored separately (built from type+value in the app)
            })
        return out

    @classmethod
    def from_specs(cls, specs: list[dict]) -> "RuleEngine":
        """Build a RuleEngine from a list of serialisable spec dicts.

        Each spec must have:
            name      (str)
            condition (dict)  – {"type": "...", "value": "..."}
            action    (str)   – "keep" | "delete" | "skip"
            priority  (int, optional)
        """
        rules: list[FilterRule] = []
        for spec in specs:
            ctype  = spec["condition"]["type"]
            cvalue = spec["condition"].get("value", "")
            builder = _CONDITION_BUILDERS.get(ctype)
            if builder is None:
                raise ValueError(f"Unknown condition type: {ctype!r}")
            rules.append(FilterRule(
                name      = spec.get("name", ctype),
                condition = builder(cvalue),
                action    = FilterAction(spec["action"]),
                priority  = int(spec.get("priority", 0)),
            ))
        return cls(rules)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class OrganizerConfig:
    sort_mode:        SortMode              = SortMode.TYPE
    output_dir:       Optional[str]         = None
    rules:            Optional[RuleEngine]  = None
    use_subtypes:     bool                  = False
    subtype_map:      dict[str, dict[str, list[str]]] = field(
        default_factory=lambda: {k: dict(v) for k, v in DEFAULT_SUBTYPE_MAP.items()}
    )
    dry_run:          bool                  = False
    recursive:        bool                  = False
    copy_mode:        bool                  = False   # True → copy files, keep originals
    duplicate_policy: DuplicatePolicy       = "rename"
    type_map:         dict[str, list[str]]  = field(default_factory=lambda: dict(DEFAULT_TYPE_MAP))
    size_buckets:     list[tuple[str, int]] = field(default_factory=lambda: list(SIZE_BUCKETS))
    log_level:        int                   = logging.INFO
    log_file:         Optional[str]         = None


# ---------------------------------------------------------------------------
# Cleaner config & class (deletion-only mode)
# ---------------------------------------------------------------------------

@dataclass
class CleanerConfig:
    rules:                Optional[RuleEngine] = None
    recursive:            bool                 = False
    dry_run:              bool                 = False
    # delete_all_by_default=False → only files with an explicit DELETE rule are removed.
    # delete_all_by_default=True  → all files are deleted unless a SKIP/KEEP rule protects them.
    delete_all_by_default: bool                = False
    log_level:            int                  = logging.INFO
    log_file:             Optional[str]        = None


class FileCleaner:
    """Scans a directory and deletes files according to CleanerConfig rules."""

    def __init__(self, target_dir: str | Path, config: Optional[CleanerConfig] = None):
        self.target   = Path(target_dir)
        self.config   = config or CleanerConfig()
        self.logger   = _setup_logger(f"FileCleaner.{id(self)}",
                                      self.config.log_level, self.config.log_file)
        self._deleted = 0
        self._skipped = 0
        self._errors  = 0

    def _validate_target(self) -> None:
        if not self.target.exists():
            raise FileNotFoundError(f"Directory not found: '{self.target}'")
        if not self.target.is_dir():
            raise NotADirectoryError(f"Path is not a directory: '{self.target}'")

    def _collect_files(self) -> list[Path]:
        pattern = "**/*" if self.config.recursive else "*"
        return [p for p in self.target.glob(pattern) if p.is_file()]

    def _should_delete(self, file: Path) -> bool:
        if not self.config.rules:
            return self.config.delete_all_by_default
        action = self.config.rules.evaluate(file)
        if action == FilterAction.DELETE:
            return True
        if action in (FilterAction.SKIP, FilterAction.KEEP):
            return False
        return self.config.delete_all_by_default   # no rule matched → use default

    def preview(self) -> list[dict]:
        self._validate_target()
        return [
            {"file": str(f), "action": "delete" if self._should_delete(f) else "skip"}
            for f in self._collect_files()
        ]

    def run(self) -> dict:
        self._validate_target()
        files = self._collect_files()
        self.logger.info(
            "Cleaner | %d file(s) | rules=%d | delete_all=%s | dry_run=%s",
            len(files),
            len(self.config.rules) if self.config.rules else 0,
            self.config.delete_all_by_default,
            self.config.dry_run,
        )
        for f in files:
            try:
                if self._should_delete(f):
                    self._delete_file(f)
                else:
                    self.logger.debug("KEEP: '%s'", f.name)
                    self._skipped += 1
            except Exception as exc:
                self.logger.error("Error processing '%s': %s", f.name, exc)
                self._errors += 1
        self.logger.info(
            "Done — deleted: %d | kept: %d | errors: %d",
            self._deleted, self._skipped, self._errors,
        )
        return {"deleted": self._deleted, "skipped": self._skipped, "errors": self._errors}

    def _delete_file(self, file: Path) -> None:
        if self.config.dry_run:
            self.logger.info("[DRY RUN] DELETE %s", file.name)
            self._deleted += 1
            return
        try:
            file.unlink()
            self.logger.info("Deleted %s", file.name)
            self._deleted += 1
        except PermissionError:
            self.logger.error("Permission denied: '%s'", file.name)
            self._errors += 1
        except FileNotFoundError:
            self.logger.warning("Already gone: '%s'", file.name)
        except OSError as exc:
            self.logger.error("Failed to delete '%s': %s", file.name, exc)
            self._errors += 1


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _setup_logger(name: str, level: int, log_file: Optional[str]) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    ch = logging.StreamHandler(sys.stdout)
    if hasattr(ch.stream, "reconfigure"):
        ch.stream.reconfigure(encoding="utf-8", errors="replace")
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


# ---------------------------------------------------------------------------
# Core organiser
# ---------------------------------------------------------------------------

class FileOrganizer:
    """Scans a directory, applies filter rules, and organises remaining files."""

    def __init__(self, target_dir: str | Path, config: Optional[OrganizerConfig] = None):
        self.target  = Path(target_dir)
        self.config  = config or OrganizerConfig()
        self.logger  = _setup_logger(__name__, self.config.log_level, self.config.log_file)
        self._moved   = 0
        self._skipped = 0
        self._deleted = 0
        self._errors  = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> dict:
        self._validate_target()
        if self.config.output_dir:
            self._ensure_output_dir()

        files = self._collect_files()
        if not files:
            self.logger.info("No files found in '%s'.", self.target)
            return self._summary()

        rules = self.config.rules
        subtypes_tag = "+subtypes" if self.config.use_subtypes else ""
        self.logger.info(
            "%s%s mode | %d file(s) | rules=%d | output=%s | dry_run=%s",
            self.config.sort_mode.value.upper(),
            subtypes_tag,
            len(files),
            len(rules) if rules else 0,
            self.config.output_dir or "(in-place)",
            self.config.dry_run,
        )

        strategy = self._get_strategy()
        move_plan: list[tuple[Path, Path]] = []

        for file in files:
            action = rules.evaluate(file) if rules else FilterAction.KEEP

            if action == FilterAction.DELETE:
                self._delete_file(file)

            elif action == FilterAction.SKIP:
                self.logger.debug("SKIP (rule): '%s'", file.name)
                self._skipped += 1

            else:  # KEEP → organise
                dest_folder = strategy(file)
                if dest_folder is None:
                    self.logger.debug("No bucket for '%s' — skipping.", file.name)
                    self._skipped += 1
                    continue
                dest_base = self._dest_base()
                move_plan.append((file, dest_base / dest_folder / file.name))

        self._execute_plan(move_plan)
        self._log_summary()
        return self._summary()

    def preview(self) -> list[dict]:
        """Return a plan list without touching the filesystem."""
        self._validate_target()
        files    = self._collect_files()
        strategy = self._get_strategy()
        rules    = self.config.rules
        results  = []

        for f in files:
            action = rules.evaluate(f) if rules else FilterAction.KEEP

            if action == FilterAction.DELETE:
                results.append({"file": str(f), "action": "delete", "destination": None})

            elif action == FilterAction.SKIP:
                results.append({"file": str(f), "action": "skip", "destination": None})

            else:
                dest_folder = strategy(f)
                dest_base   = self._dest_base()
                results.append({
                    "file":        str(f),
                    "action":      "copy" if self.config.copy_mode else "move",
                    "destination": str(dest_base / dest_folder / f.name) if dest_folder else None,
                })

        return results

    # ------------------------------------------------------------------
    # Validation & collection
    # ------------------------------------------------------------------

    def _validate_target(self) -> None:
        if not self.target.exists():
            raise FileNotFoundError(f"Directory not found: '{self.target}'")
        if not self.target.is_dir():
            raise NotADirectoryError(f"Path is not a directory: '{self.target}'")
        if not self.target.stat().st_mode & 0o200:
            raise PermissionError(f"No write permission for: '{self.target}'")

    def _ensure_output_dir(self) -> None:
        out = Path(self.config.output_dir)
        try:
            out.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise PermissionError(f"Cannot create output directory: '{out}'")

    def _collect_files(self) -> list[Path]:
        pattern = "**/*" if self.config.recursive else "*"
        return [p for p in self.target.glob(pattern) if p.is_file()]

    def _dest_base(self) -> Path:
        return Path(self.config.output_dir) if self.config.output_dir else self.target

    # ------------------------------------------------------------------
    # Sorting strategies
    # ------------------------------------------------------------------

    def _get_strategy(self):
        return {
            SortMode.TYPE:      self._bucket_by_type,
            SortMode.EXTENSION: self._bucket_by_extension,
            SortMode.NAME:      self._bucket_by_name,
            SortMode.SIZE:      self._bucket_by_size,
            SortMode.DATE:      self._bucket_by_date,
        }[self.config.sort_mode]

    def _bucket_by_type(self, file: Path) -> Optional[str]:
        ext = file.suffix.lower()
        for folder, exts in self.config.type_map.items():
            if ext in exts:
                if not self.config.use_subtypes:
                    return folder
                # Find the matching sub-type for this extension.
                sub_map = self.config.subtype_map.get(folder, {})
                for subname, sub_exts in sub_map.items():
                    if ext in sub_exts:
                        return f"{folder}/{subname}"
                # Extension is known to this type but has no sub-type entry →
                # use the raw extension uppercased as the subfolder.
                raw = ext.lstrip(".").upper() or "NoExtension"
                return f"{folder}/{raw}"
        # Completely unrecognised extension.
        if self.config.use_subtypes:
            raw = ext.lstrip(".").upper() or "NoExtension"
            return f"Other/{raw}"
        return "Other"

    def _bucket_by_extension(self, file: Path) -> Optional[str]:
        ext = file.suffix.lstrip(".").upper()
        return ext if ext else "NoExtension"

    def _bucket_by_name(self, file: Path) -> Optional[str]:
        first = file.stem[0].upper() if file.stem else "#"
        return first if first.isalpha() else "#"

    def _bucket_by_size(self, file: Path) -> Optional[str]:
        size = _safe_size(file)
        for label, limit in self.config.size_buckets:
            if size < limit:
                return label
        return "Huge"

    def _bucket_by_date(self, file: Path) -> Optional[str]:
        mtime = _safe_mtime(file)
        if mtime == 0:
            return "Unknown"
        return datetime.fromtimestamp(mtime).strftime("%Y-%m")

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _execute_plan(self, plan: list[tuple[Path, Path]]) -> None:
        for src, dest in plan:
            try:
                self._move_file(src, dest)
            except Exception as exc:
                self.logger.error("Failed to move '%s': %s", src.name, exc)
                self._errors += 1

    def _move_file(self, src: Path, dest: Path) -> None:
        verb = "COPY" if self.config.copy_mode else "MOVE"
        if self.config.dry_run:
            self.logger.info("[DRY RUN] %s %s -> %s", verb, src.name, dest.parent.name)
            self._moved += 1
            return

        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists():
            policy = self.config.duplicate_policy
            if policy == "skip":
                self.logger.warning("SKIP duplicate: '%s'", dest.name)
                self._skipped += 1
                return
            elif policy == "overwrite":
                self.logger.warning("OVERWRITE: '%s'", dest.name)
            else:
                dest = self._unique_path(dest)

        if self.config.copy_mode:
            shutil.copy2(str(src), str(dest))
            self.logger.info("Copied %s -> %s/%s", src.name, dest.parent.name, dest.name)
        else:
            shutil.move(str(src), str(dest))
            self.logger.info("Moved  %s -> %s/%s", src.name, dest.parent.name, dest.name)
        self._moved += 1

    def _delete_file(self, file: Path) -> None:
        if self.config.dry_run:
            self.logger.info("[DRY RUN] DELETE %s", file.name)
            self._deleted += 1
            return
        try:
            file.unlink()
            self.logger.info("Deleted %s", file.name)
            self._deleted += 1
        except PermissionError:
            self.logger.error("Permission denied deleting '%s'", file.name)
            self._errors += 1
        except FileNotFoundError:
            self.logger.warning("Already gone: '%s'", file.name)
        except OSError as exc:
            self.logger.error("Failed to delete '%s': %s", file.name, exc)
            self._errors += 1

    @staticmethod
    def _unique_path(path: Path) -> Path:
        counter = 1
        stem, suffix, parent = path.stem, path.suffix, path.parent
        while path.exists():
            path = parent / f"{stem} ({counter}){suffix}"
            counter += 1
        return path

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _log_summary(self) -> None:
        tag = "[DRY RUN] " if self.config.dry_run else ""
        self.logger.info(
            "%sDone — moved: %d | deleted: %d | skipped: %d | errors: %d",
            tag, self._moved, self._deleted, self._skipped, self._errors,
        )

    def _summary(self) -> dict:
        return {
            "moved":   self._moved,
            "deleted": self._deleted,
            "skipped": self._skipped,
            "errors":  self._errors,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_rule_arg(s: str) -> dict:
    """Parse a CLI rule string: "condition_type:value:action[:priority]"

    Examples:
        name_starts_with:t:delete
        name_starts_with:f:keep:10
        extension_in:.tmp:delete
        always::skip
    """
    parts = s.split(":", 3)
    if len(parts) < 3:
        raise argparse.ArgumentTypeError(
            f"Rule must be 'condition_type:value:action[:priority]', got: {s!r}"
        )
    ctype, value, action = parts[0], parts[1], parts[2]
    priority = int(parts[3]) if len(parts) == 4 else 0
    return {
        "name":      f"{ctype}:{value} -> {action}",
        "condition": {"type": ctype, "value": value},
        "action":    action,
        "priority":  priority,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="file_organizer",
        description="Organise files by type/extension/name/size/date with optional filtering.",
    )
    parser.add_argument("directory", help="Source directory to scan")
    parser.add_argument(
        "--sort", "-s",
        choices=[m.value for m in SortMode],
        default=SortMode.TYPE.value,
    )
    parser.add_argument(
        "--output", "-o",
        metavar="DIR",
        help="Output directory (default: organise in-place)",
    )
    parser.add_argument(
        "--rule",
        metavar="SPEC",
        action="append",
        default=[],
        type=_parse_rule_arg,
        help="Filter rule: 'condition_type:value:action[:priority]'  (repeatable)"
             "  e.g. --rule name_starts_with:t:delete --rule name_starts_with:f:keep",
    )
    parser.add_argument(
        "--subtypes",
        action="store_true",
        help="Further organise Type folders into sub-type sub-folders "
             "(e.g. Documents/PDF/, Images/JPEG/). Only applies to --sort type.",
    )
    parser.add_argument("--dry-run",   "-n", action="store_true")
    parser.add_argument("--recursive", "-r", action="store_true")
    parser.add_argument(
        "--duplicate",
        choices=["rename", "skip", "overwrite"],
        default="rename",
    )
    parser.add_argument("--log-file", metavar="PATH")
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    rules = RuleEngine.from_specs(args.rule) if args.rule else None

    config = OrganizerConfig(
        sort_mode        = SortMode(args.sort),
        output_dir       = args.output,
        rules            = rules,
        use_subtypes     = args.subtypes,
        dry_run          = args.dry_run,
        recursive        = args.recursive,
        duplicate_policy = args.duplicate,
        log_level        = logging.DEBUG if args.verbose else logging.INFO,
        log_file         = args.log_file,
    )

    try:
        organizer = FileOrganizer(args.directory, config)
        organizer.run()
    except (FileNotFoundError, NotADirectoryError, PermissionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
