import logging
import sys
import typing
from typing import Optional, Any, Dict, Tuple
from gi.repository import Gio, GLib
from reactivex import combine_latest
from reactivex import operators as ops

if typing.TYPE_CHECKING:
    from lib.ui.play_bar import PlayerState
    from lib.state.player_state import PlayState, MediaStatus


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


def setup_mpris_controller(state: "PlayerState") -> None:
    """Sets up the MPRIS D-Bus interface using a functional, closure-based approach."""

    if not sys.platform.startswith("linux"):
        logging.info("Platform is not Linux. MPRIS controller disabled.")
        return

    node_info = Gio.DBusNodeInfo.new_for_xml(MPRIS_XML)
    if not node_info.interfaces:
        logging.error("Failed to parse MPRIS XML interfaces.")
        return

    con = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    # --- Helper Functions (Closures over `state` and `con`) ---

    def get_metadata() -> Dict[str, GLib.Variant]:
        if not state.current.value:
            return {}
        current = state.current.value
        # MPRIS length expects microseconds. GStreamer yields nanoseconds.
        length_us: int = state.stream.total_time.value // 1000

        return {
            "mpris:trackid": GLib.Variant("s", "/org/mpris/MediaPlayer2/Track/Current"),
            "xesam:title": GLib.Variant("s", current.title),
            "xesam:artist": GLib.Variant("as", [current.artist]),
            "mpris:length": GLib.Variant("x", length_us),
        }

    def emit_properties_changed(
        interface_name: str, changed_props: Dict[str, GLib.Variant]
    ) -> None:
        con.emit_signal(
            None,
            "/org/mpris/MediaPlayer2",
            "org.freedesktop.DBus.Properties",
            "PropertiesChanged",
            GLib.Variant("(sa{sv}as)", (interface_name, changed_props, [])),
        )

    # --- D-Bus Event Handlers ---

    def handle_method_call(
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        from lib.state.player_state import PlayState

        if interface_name == "org.mpris.MediaPlayer2.Player":
            if method_name == "PlayPause":
                current = state.state.value
                if current == PlayState.PLAYING:
                    state.state.on_next(PlayState.PAUSED)
                elif current == PlayState.PAUSED:
                    state.state.on_next(PlayState.PLAYING)
            elif method_name == "Play":
                state.state.on_next(PlayState.PLAYING)
            elif method_name == "Pause":
                state.state.on_next(PlayState.PAUSED)
            elif method_name in ("Next", "Previous"):
                # Add logic to skip tracks if you implement a queue in PlayerState
                pass

        invocation.return_value(None)

    def handle_get_property(
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        property_name: str,
    ) -> Optional[GLib.Variant]:
        from lib.state.player_state import PlayState

        if interface_name == "org.mpris.MediaPlayer2":
            if property_name == "Identity":
                return GLib.Variant("s", "YTMusic GTK")
            return GLib.Variant("b", False)

        if interface_name == "org.mpris.MediaPlayer2.Player":
            if property_name == "PlaybackStatus":
                status: str = (
                    "Playing" if state.state.value == PlayState.PLAYING else "Paused"
                )
                return GLib.Variant("s", status)

            if property_name == "Metadata":
                return GLib.Variant("a{sv}", get_metadata())

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
        connection: Gio.DBusConnection,
        sender: str,
        object_path: str,
        interface_name: str,
        property_name: str,
        value: GLib.Variant,
    ) -> bool:
        return False  # External property setting not supported

    # --- Register with D-Bus ---

    for interface in node_info.interfaces:
        con.register_object(
            "/org/mpris/MediaPlayer2",
            interface,
            handle_method_call,
            handle_get_property,
            handle_set_property,
        )

    Gio.bus_own_name_on_connection(
        con,
        "org.mpris.MediaPlayer2.MyApp",
        Gio.BusNameOwnerFlags.NONE,
        None,
        None,
    )

    # --- Reactive Subscriptions ---

    def on_playback_status_changed(play_state: "PlayState") -> None:
        from lib.state.player_state import PlayState

        status: str = "Playing" if play_state == PlayState.PLAYING else "Paused"
        emit_properties_changed(
            "org.mpris.MediaPlayer2.Player",
            {"PlaybackStatus": GLib.Variant("s", status)},
        )

    def on_metadata_changed(_: Any) -> None:
        emit_properties_changed(
            "org.mpris.MediaPlayer2.Player",
            {"Metadata": GLib.Variant("a{sv}", get_metadata())},
        )

    # def on_current_changed(current: Optional["CurrentMusic"]) -> None:
    #     if not current:
    #         return
    #     combine_latest(
    #         current.title,
    #         current.artist,
    #         state.stream.total_time,
    #     ).subscribe(on_metadata_changed)
    def on_current_changed(current: Optional["MediaStatus"]) -> None:
        if not current:
            return
        combine_latest(
            state.current.pipe(ops.filter(lambda c: c is not None)),
            state.stream.total_time,
        ).subscribe(on_metadata_changed)

    # Attach listeners to the state
    state.state.subscribe(on_playback_status_changed)
    state.current.subscribe(on_current_changed)
