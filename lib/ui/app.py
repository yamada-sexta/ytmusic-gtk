from reactivex.subject import BehaviorSubject
import logging
from reactivex.scheduler.mainloop.gtkscheduler import GtkScheduler
from lib.net.client import thread_pool_scheduler
from lib.net.api import auto_login
from lib.net.client import YTClient
from typing import Optional
from lib.ui.about import show_about_window
from lib.ui.main_window import YTMusicWindow
from pathlib import Path
import logging
from gi.repository import Gtk, Adw, Gst, GLib, Pango, Gio, GdkPixbuf, Gdk, GObject
import reactivex as rx
from reactivex import operators as ops
from reactivex.scheduler import ThreadPoolScheduler
import os
import subprocess
import sys


class YTMusicApp(Adw.Application):
    application_name: str
    application_icon: str
    developer_name: str
    app_version: str
    repo_url: str

    def __init__(
        self,
        application_id: str,
        application_name: str,
        application_icon: str,
        developer_name: str,
        app_version: str,
        repo_url: str,
        **kwargs,
    ):
        super().__init__(application_id=application_id, **kwargs)
        self.application_name = application_name
        self.application_id = application_id
        self.application_icon = application_icon
        self.developer_name = developer_name
        self.app_version = app_version
        self.repo_url = repo_url
        self.win: Optional[YTMusicWindow] = None
        self._tray_process: Optional[subprocess.Popen[str]] = None
        self.connect("startup", self.on_startup)
        self.connect("activate", self.on_activate)

        self.win: Optional[YTMusicWindow] = None
        # Create the subject here!
        self.client_subject = BehaviorSubject[Optional[YTClient]](None)
        logging.debug(
            f"YTMusicApp initialized with ID: {application_id}, Name: {application_name}"
        )

    def on_startup(self, app: Gtk.Application):
        logging.info("Application starting up...")
        display = Gdk.Display.get_default()
        if not display:
            logging.warning("Could not get default display for icon theming.")
        else:
            icon_theme = Gtk.IconTheme.get_for_display(display)
            base_dir = Path(__file__).parent.parent.parent.resolve()
            icons_path = str(base_dir / "assets" / "icons")

            logging.info(f"Looking for icons in: {icons_path}")
            if not os.path.exists(icons_path):
                logging.warning(f"Icons path does not exist: {icons_path}")

            # App icon directory
            app_icon_path = str(base_dir / "assets" / "app")
            logging.info(f"Looking for app icon in: {app_icon_path}")
            if not os.path.exists(app_icon_path):
                logging.warning(f"App icon path does not exist: {app_icon_path}")

            icon_theme.add_search_path(icons_path)
            icon_theme.add_search_path(app_icon_path)
            logging.info(f"Added custom icon path: {icons_path}")
            logging.info(f"Added custom icon path: {app_icon_path}")

        # Set macOS dock icon
        if sys.platform == "darwin":
            from lib.sys.mac_icon import set_macos_dock_icon

            set_macos_dock_icon()

        # About Action
        about_action = Gio.SimpleAction.new("about", None)

        def on_about_action(action: Gio.SimpleAction, param: Gio.ActionGroup):
            show_about_window(
                application_name=self.application_name,
                application_icon=self.application_icon,
                developer_name=self.developer_name,
                app_version=self.app_version,
                repo_url=self.repo_url,
                parent=self.get_active_window(),
            )

        about_action.connect("activate", on_about_action)
        self.add_action(about_action)

        # Preferences Action (Placeholder for now)
        pref_action = Gio.SimpleAction.new("preferences", None)
        pref_action.connect("activate", self.on_preferences_action)
        self.add_action(pref_action)

        # System tray icon
        from lib.sys.tray import setup_tray

        setup_tray(self)

        # macOS dock click handler
        from lib.sys.mac_dock import setup_macos_dock_handler

        setup_macos_dock_handler(self)

        logging.info("Application startup complete.")

    def on_activate(self, app: Gtk.Application):
        logging.info("Application activated.")
        if self.win:
            self.win.set_visible(True)
            self.win.present()
            return
        logging.info("Activating application and initializing main window.")

        self.win = YTMusicWindow(
            application=app,
            app_name=self.application_name,
            app_id=self.application_id,
            client_obs=self.client_subject,
        )

        self.win.present()

        if self.client_subject.value is None:

            def dispatch_on_next(client):
                GLib.idle_add(self.client_subject.on_next, client)

            rx.from_callable(auto_login).pipe(
                ops.subscribe_on(thread_pool_scheduler),
                ops.filter(lambda api: api is not None),
                ops.map(lambda api: YTClient(api)),
            ).subscribe(
                on_next=dispatch_on_next,
                on_error=lambda e: logging.error(f"Init failed: {e}"),
            )

    def on_preferences_action(
        self, action: Gio.SimpleAction, param: Optional[Gio.ActionGroup]
    ):
        """Placeholder for a preferences window."""
        logging.info("Preferences menu item clicked.")
