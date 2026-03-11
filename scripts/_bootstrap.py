from __future__ import annotations

from pathlib import Path
import sys


def ensure_project_paths(*, include_project_root: bool = False) -> None:
    """Fuegt Projektordner zu ``sys.path`` hinzu, damit die Beispielskripte lokalen Code importieren koennen.

    Warum es diese Funktion gibt:
    - Diese Dateien werden direkt mit ``python scripts/...`` gestartet.
    - Dann kennt Python die ``src``-Struktur des Projekts nicht automatisch.
    - Deshalb werden die benoetigten Ordner vor den Imports manuell eingetragen.

    Moegliche spaetere Vereinfachung:
    - Wenn das Projekt sauber als Paket installiert wird, kann diese Hilfe entfallen.
    """
    project_root = Path(__file__).resolve().parents[1]
    src_dir = project_root / "src"

    if include_project_root and str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
