from lib.ui.main_ui import MainUI
from lib.ui.loading import LoadingUI
from typing import Optional
import logging
from reactivex import Observable

from gi.repository import Gtk, Adw, GLib

from lib.net.client import YTClient


class YTMusicWindow(Adw.ApplicationWindow):
    def __init__(
        self,
        client_obs: Observable[Optional["YTClient"]],
        app_name: str,
        app_id: str,
        **kwargs,
    ):
        super().__init__(**kwargs)
        logging.debug("Initializing YTMusicWindow with client observable.")
        self.app_name = app_name
        self.app_id = app_id

        self.set_default_size(900, 700)
        self.set_title(app_name)
        self.set_icon_name(app_id)

        self.window_stack = Gtk.Stack()
        self.window_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.set_content(self.window_stack)

        # Use the standalone function with custom text
        loading_view = LoadingUI(primary_text="Connecting to YouTube Music...")
        self.window_stack.add_named(loading_view, "loading")

        def on_client_received(client: Optional[YTClient]):
            if client:
                logging.info("YTClient received. Transitioning to main UI.")
                GLib.idle_add(self._load_main_ui, client)
            else:
                logging.warning("Received None for YTClient. Still waiting...")

        client_obs.subscribe(on_next=on_client_received)
        self.connect("close-request", self._on_close_request)

    def _load_main_ui(self, client: "YTClient"):
        """Handles the insertion of the main UI once the client is ready."""
        # Call the standalone builder function
        main_view = MainUI(client, self.app_name, self)

        self.window_stack.add_named(main_view, "main")
        self.window_stack.set_visible_child_name("main")

    def _on_close_request(self, window: Adw.ApplicationWindow) -> bool:
        app = self.get_application()
        if app and getattr(app, "_tray_process", None):
            logging.info("Hiding window, keeping process alive for tray.")
            self.set_visible(False)
            return True
        return False
