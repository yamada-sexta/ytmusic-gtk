import logging
import sys
import typing
from typing import Optional, Any, Dict, Tuple
from gi.repository import Gio, GLib
from reactivex import combine_latest

if typing.TYPE_CHECKING:
    from lib.ui.play_bar import PlayerState

# This XML defines the D-Bus API contract GNOME expects from your player
MPRIS_XML: str = """
<node>
  <interface name="org.mpris.MediaPlayer2">
    <property name="CanQuit" type="b" access="read"/>
    <property name="CanRaise" type="b" access="read"/>
    <property name="HasTrackList" type="b" access="read"/>
    <property name="Identity" type="s" access="read"/>
  </interface>
  <interface name="org.mpris.MediaPlayer2.Player">
    <method name="Next"/>
    <method name="Previous"/>
    <method name="Pause"/>
    <method name="PlayPause"/>
    <method name="Stop"/>
    <method name="Play"/>
    <property name="PlaybackStatus" type="s" access="read"/>
    <property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/>
    <property name="CanPlay" type="b" access="read"/>
    <property name="CanPause" type="b" access="read"/>
    <property name="CanControl" type="b" access="read"/>
    <property name="Metadata" type="a{sv}" access="read"/>
  </interface>
</node>
"""


class MPRISController:
    # Explicit class variable typing
    state: "PlayerState"
    node_info: Gio.DBusNodeInfo
    con: Gio.DBusConnection

    def __init__(self, state: "PlayerState") -> None:
        if sys.platform != "linux":
            logging.info("Platform is not Linux. MPRIS controller disabled.")
            return
        self.state = state
        self.node_info = Gio.DBusNodeInfo.new_for_xml(MPRIS_XML)
        self.con = Gio.bus_get_sync(Gio.BusType.SESSION, None)

        # Register the interfaces on D-Bus
        if self.node_info.interfaces:
            for interface in self.node_info.interfaces:
                self.con.register_object(
                    "/org/mpris/MediaPlayer2",
                    interface,
                    self.handle_method_call,
                    self.handle_get_property,
                    self.handle_set_property,
                )

        # Claim the bus name so GNOME knows we exist
        Gio.bus_own_name_on_connection(
            self.con,
            "org.mpris.MediaPlayer2.MyApp",
            Gio.BusNameOwnerFlags.NONE,
            None,
            None,
        )

        # Reactive Bindings: Update GNOME when internal state changes
        self.state.playing.subscribe(self.on_playback_status_changed)
        combine_latest(
            self.state.title, self.state.artist, self.state.total_time
        ).subscribe(self.on_metadata_changed)

    def handle_method_call(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        """Handles incoming commands from GNOME (e.g. Media Keys)."""
        if interface_name == "org.mpris.MediaPlayer2.Player":
            if method_name == "PlayPause":
                self.state.playing.on_next(not self.state.playing.value)
            elif method_name == "Play":
                self.state.playing.on_next(True)
            elif method_name == "Pause":
                self.state.playing.on_next(False)
            elif method_name in ("Next", "Previous"):
                # Add logic to skip tracks if you implement a queue in PlayerState
                pass

        # We must return something to the invocation to close the D-Bus call
        invocation.return_value(None)

    def handle_get_property(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        property_name: str,
    ) -> Optional[GLib.Variant]:
        """Tells GNOME the current state of our player."""
        if interface_name == "org.mpris.MediaPlayer2":
            if property_name == "Identity":
                return GLib.Variant("s", "YTMusic GTK")
            return GLib.Variant("b", False)

        if interface_name == "org.mpris.MediaPlayer2.Player":
            if property_name == "PlaybackStatus":
                status: str = "Playing" if self.state.playing.value else "Paused"
                return GLib.Variant("s", status)

            if property_name == "Metadata":
                return GLib.Variant("a{sv}", self.get_metadata())

            if property_name in [
                "CanGoNext",
                "CanGoPrevious",
                "CanPlay",
                "CanPause",
                "CanControl",
            ]:
                return GLib.Variant("b", True)

        return None

    def handle_set_property(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        property_name: str,
        value: GLib.Variant,
    ) -> bool:
        """Handles external attempts to modify properties."""
        return False  # We don't support external property setting

    def get_metadata(self) -> Dict[str, GLib.Variant]:
        """Constructs the MPRIS Metadata dictionary."""
        # MPRIS length expects microseconds. GStreamer yields nanoseconds.
        length_us: int = self.state.total_time.value // 1000

        return {
            "mpris:trackid": GLib.Variant("s", "/org/mpris/MediaPlayer2/Track/Current"),
            "xesam:title": GLib.Variant("s", self.state.title.value),
            "xesam:artist": GLib.Variant("as", [self.state.artist.value]),
            "mpris:length": GLib.Variant("x", length_us),
        }

    # --- PropertiesChanged Signal Emitters ---

    def on_playback_status_changed(self, is_playing: bool) -> None:
        """Reactive callback triggered by RxPY subject."""
        status: str = "Playing" if is_playing else "Paused"
        self._emit_properties_changed(
            "org.mpris.MediaPlayer2.Player",
            {"PlaybackStatus": GLib.Variant("s", status)},
        )

    def on_metadata_changed(self, _: Any) -> None:
        """Reactive callback triggered by RxPY combine_latest."""
        self._emit_properties_changed(
            "org.mpris.MediaPlayer2.Player",
            {"Metadata": GLib.Variant("a{sv}", self.get_metadata())},
        )

    def _emit_properties_changed(
        self, interface_name: str, changed_props: Dict[str, GLib.Variant]
    ) -> None:
        """Broadcasts state changes to the system so the UI updates instantly."""
        self.con.emit_signal(
            None,
            "/org/mpris/MediaPlayer2",
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            GLib.Variant("(sa{sv}as)", (interface_name, changed_props, [])),
        )
