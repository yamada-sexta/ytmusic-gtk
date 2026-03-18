from __future__ import annotations

import os
from pathlib import Path


def configure_windows_gi_runtime() -> list[Path]:
    # If it is not windows return
    if os.name != "nt":
        return []
    configured_roots: list[Path] = []
    seen_roots: set[Path] = set()
    candidate_roots = [
        os.environ.get("GTK_ROOT"),
        os.environ.get("GTK_DIR"),
        r"C:\gtk",
    ]

    for candidate in candidate_roots:
        if not candidate:
            continue

        root = Path(candidate).expanduser()
        if root in seen_roots:
            continue
        seen_roots.add(root)

        bin_dir = root / "bin"
        typelib_dir = root / "lib" / "girepository-1.0"
        if not (bin_dir.is_dir() and typelib_dir.is_dir()):
            continue

        os.add_dll_directory(str(bin_dir))
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        os.environ["GI_TYPELIB_PATH"] = str(typelib_dir)

        configured_roots.append(root)

    return configured_roots
