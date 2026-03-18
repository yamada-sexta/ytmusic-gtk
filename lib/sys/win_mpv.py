from __future__ import annotations

import os
from pathlib import Path


def configure_windows_mpv_runtime() -> list[Path]:
    if os.name != "nt":
        return []
    configured_dirs: list[Path] = []
    seen_dirs: set[Path] = set()
    candidate_dirs = [
        os.environ.get("MPV_DLL_DIR"),
        str(Path.home() / "scoop" / "apps" / "mpv" / "current"),
        r"C:\msys64\ucrt64\bin",
        r"C:\msys64\mingw64\bin",
    ]

    for candidate in candidate_dirs:
        if not candidate:
            continue

        directory = Path(candidate).expanduser()  # type: ignore
        if directory in seen_dirs or not directory.is_dir():
            continue
        seen_dirs.add(directory)

        if not any(
            (directory / dll_name).is_file()
            for dll_name in ("mpv-2.dll", "libmpv-2.dll", "mpv-1.dll")
        ):
            continue

        os.add_dll_directory(str(directory))  # type: ignore
        os.environ["PATH"] = f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"
        configured_dirs.append(directory)

    return configured_dirs
