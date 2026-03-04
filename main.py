import logging
import os
import sys
import subprocess

# --- macOS Homebrew & Virtual Environment Fix ---
try:
    brew_prefix = subprocess.check_output(["brew", "--prefix"], text=True).strip()
    brew_lib_path = f"{brew_prefix}/lib"

    os.environ["GI_TYPELIB_PATH"] = f"{brew_lib_path}/girepository-1.0"
    current_dyld = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")

    if brew_lib_path not in current_dyld:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = f"{brew_lib_path}:{current_dyld}"
        os.execv(sys.executable, [sys.executable] + sys.argv)
except Exception as e:
    print(f"Warning: Could not configure Homebrew paths automatically: {e}")
# ------------------------------------------------


def main():
    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")

    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("Gst", "1.0")
    gi.require_version("Pango", "1.0")
    gi.require_version("Gio", "2.0")
    gi.require_version("GdkPixbuf", "2.0")
    gi.require_version("Gdk", "4.0")

    from gi.repository import GLib

    # Read properties from pyproject.toml
    import tomllib

    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)

    app_name = pyproject["tool"]["ytmusic-gtk"]["app_name"]
    app_id = pyproject["tool"]["ytmusic-gtk"]["app_id"]
    developer_name = pyproject["tool"]["ytmusic-gtk"]["developer_name"]
    app_version = pyproject["project"]["version"]
    repo_url = pyproject["tool"]["ytmusic-gtk"]["repo_url"]
    logging.info(f"Application name: {app_name}")
    logging.info(f"Application ID: {app_id}")
    logging.info(f"Developer name: {developer_name}")
    logging.info(f"Application version: {app_version}")
    logging.info(f"Repository URL: {repo_url}")

    GLib.set_prgname(app_name)
    GLib.set_application_name(app_name)

    from lib.ui.app import YTMusicApp

    app = YTMusicApp(
        application_id=app_id,
        application_name=app_name,
        application_icon=app_id,
        developer_name=developer_name,
        app_version=app_version,
        repo_url=repo_url,
    )
    app.run(sys.argv)


if __name__ == "__main__":
    main()
