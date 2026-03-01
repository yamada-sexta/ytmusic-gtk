from gi.repository import Gst
import logging
import sys

Gst.init(None)
_player = Gst.ElementFactory.make("playbin", "player")
if not _player:
    logging.error("Failed to create GStreamer playbin element.")
    sys.exit(1)

player = _player
