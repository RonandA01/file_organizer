# 📂 File Organizer

A Windows desktop application for automatically organizing and cleaning up files. Built with Python and PyQt6, distributed as a standalone installer — no Python installation required.

---

## Features

### File Organizer Tab
- **Sort files** by type, extension, name, date, or size
- **Move or Copy** mode — relocate files or keep originals in place
- **Output directory** — organize into a separate folder or in-place
- **Sub-type grouping** — e.g. `Documents/PDF/`, `Images/JPEG/`
- **Filter rules** — per-file rules to skip, keep, or delete before organizing
- **Duplicate handling** — auto-rename, skip, or overwrite
- **Dry run** — preview every action without touching any files

### File Cleaner Tab
- **Deletion-only mode** — scan a folder and delete matching files
- **Two deletion modes:**
  - *Safe (default)* — only delete files with an explicit DELETE rule
  - *Delete all* — delete everything unless a SKIP/KEEP rule protects it
- **Filter rules** — same rule engine as the organizer
- **Dry run** — preview deletions before committing

### Shared
- **Live preview table** — see every planned action before running
- **ETA display** — estimated time remaining during long operations
- **Cancellable** — stop any operation mid-run instantly
- **Persistent settings** — directories, options, and rules are saved between sessions
- **Dark theme UI**

---

## Screenshots

| File Organizer | File Cleaner |
|---|---|
| *(organize tab)* | *(cleaner tab)* |

---

## Installation

1. Download `FileOrganizer_Setup_v1.0.0.exe` from [Releases](../../releases)
2. Run the installer — **no admin/UAC prompt** (installs per-user)
3. Launch from the Start Menu or optional desktop shortcut

---

## Building from Source

### Requirements
- Python 3.14+ (non-Microsoft-Store)
- PyQt6 — `pip install PyQt6`
- PyInstaller — `pip install pyinstaller`
- Pillow — `pip install Pillow` (only needed to regenerate the icon)
- [Inno Setup 6](https://jrsoftware.org/isdl.php) installed to `%LOCALAPPDATA%\InnoSetup6\`

### One-click build
```powershell
.\build.ps1
```
This runs PyInstaller → then Inno Setup and outputs the installer to `installer_output\`.

### Manual steps
```powershell
# 1. Build the EXE
pyinstaller file_organizer.spec --noconfirm

# 2. Build the installer
& "$env:LOCALAPPDATA\InnoSetup6\ISCC.exe" installer.iss
```

### Regenerate the icon
```powershell
python gen_icon.py
```

---

## Project Structure

```
file_organizer.py       # Core engine — FileOrganizer, FileCleaner, RuleEngine
file_organizer_app.py   # PyQt6 desktop application
file_organizer.spec     # PyInstaller build configuration
installer.iss           # Inno Setup 6 installer script
build.ps1               # Automated two-stage build script
app_icon.ico            # Multi-resolution folder icon (16–256 px)
gen_icon.py             # Pillow script to regenerate app_icon.ico
```

---

## Using as a Python Module

`file_organizer.py` is a standalone reusable module:

```python
from file_organizer import FileOrganizer, OrganizerConfig, SortMode, RuleEngine

rules = RuleEngine.from_specs([
    {"name": "Delete temp files", "condition": {"type": "extension_in", "value": ".tmp,.log"}, "action": "delete"},
    {"name": "Keep README",       "condition": {"type": "name_starts_with", "value": "README"}, "action": "keep"},
])

config = OrganizerConfig(
    sort_mode  = SortMode.TYPE,
    output_dir = "C:/Organized",
    rules      = rules,
    dry_run    = True,       # preview only
    copy_mode  = False,      # True = copy, False = move
)

organizer = FileOrganizer("C:/MyFolder", config)
organizer.run()
```

```python
from file_organizer import FileCleaner, CleanerConfig

config = CleanerConfig(
    delete_all_by_default = False,   # only delete files with explicit DELETE rules
    dry_run               = True,
)

cleaner = FileCleaner("C:/TempFolder", config)
print(cleaner.preview())
cleaner.run()
```

### CLI usage

```
python file_organizer.py <directory> [options]

Options:
  --sort {type,extension,name,size,date}
  --output DIR          output directory (default: in-place)
  --rule SPEC           filter rule: "condition:value:action[:priority]"
  --subtypes            enable sub-type grouping
  --dry-run, -n         preview without moving files
  --recursive, -r       include sub-folders
  --duplicate {rename,skip,overwrite}
  --verbose, -v         debug logging

Examples:
  python file_organizer.py ~/Downloads --sort type --dry-run
  python file_organizer.py ~/Downloads --sort extension --output ~/Organized
  python file_organizer.py ~/Downloads --rule "extension_in:.tmp:delete" --rule "name_starts_with:keep_:keep"
```

---

## License

MIT
