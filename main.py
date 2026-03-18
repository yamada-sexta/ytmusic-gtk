import logging
import sys


def main():
    # Add current directory to sys.path
    import os

    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    logging.basicConfig(
        level=logging.DEBUG, format="[%(levelname)s] %(name)s: %(message)s"
    )

    from lib.sys.mac_gi import mac_brew_fix

    windows_gi_roots = []
    windows_mpv_dirs = []
    if sys.platform == "darwin":
        mac_brew_fix()
    elif sys.platform == "win32":
        from lib.sys.win_gi import configure_windows_gi_runtime
        from lib.sys.win_mpv import configure_windows_mpv_runtime

        windows_gi_roots = configure_windows_gi_runtime()
        windows_mpv_dirs = configure_windows_mpv_runtime()

    try:
        import gi
    except ImportError as exc:
        if sys.platform == "win32":
            configured = ", ".join(str(path) for path in windows_gi_roots) or "none"
            raise RuntimeError(
                "PyGObject could not load on Windows. Install a GTK4 runtime "
                "(for example under C:\\gtk with bin/ and lib\\girepository-1.0) "
                f"and ensure it matches this Python architecture. Configured GTK roots: {configured}."
            ) from exc
        raise

    required_namespaces = {
        "Gtk": "4.0",
        "Adw": "1",
        "Pango": "1.0",
        "Gio": "2.0",
        "GdkPixbuf": "2.0",
        "Gdk": "4.0",
    }
    try:
        for namespace, version in required_namespaces.items():
            gi.require_version(namespace, version)
    except ValueError as exc:
        if sys.platform == "win32":
            configured = ", ".join(str(path) for path in windows_gi_roots) or "none"
            missing_namespace = str(exc)
            raise RuntimeError(
                "A required GI namespace is missing from the Windows GTK runtime. "
                "This app needs GTK4 and libadwaita typelibs installed. "
                f"{missing_namespace}. Configured GTK roots: {configured}."
            ) from exc
        raise

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

    try:
        from lib.ui.app import YTMusicApp
    except OSError as exc:
        if sys.platform == "win32" and "mpv" in str(exc).lower():
            configured = ", ".join(str(path) for path in windows_mpv_dirs) or "none"
            raise RuntimeError(
                "libmpv could not be loaded on Windows. Install a build that includes "
                "mpv-2.dll or libmpv-2.dll, or point MPV_DLL_DIR at that folder. "
                f"Configured mpv directories: {configured}."
            ) from exc
        raise

    app = YTMusicApp(
        application_id=app_id,
        application_name=app_name,
        application_icon=app_id,
        developer_name=developer_name,
        app_version=app_version,
        repo_url=repo_url,
    )
    app.run(sys.argv)


# Capture exit to make sure we can do cleanup if needed
import atexit

atexit.register(lambda: logging.info("Application exiting..."))

if __name__ == "__main__":
    main()
