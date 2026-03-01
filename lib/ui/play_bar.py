import logging
from gi.repository import Gtk, GLib, Adw, Pango
from reactivex.subject import BehaviorSubject


def PlayBar(playing: BehaviorSubject[bool] = BehaviorSubject(False)) -> Gtk.ActionBar:
    play_bar = Gtk.ActionBar()

    # Increase the overall height of the Action Bar
    play_bar.set_size_request(-1, 80)

    # ----------------------------------------------------
    # 1. PLAY CONTROLS (Left)
    # ----------------------------------------------------
    controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    controls_box.set_valign(Gtk.Align.CENTER)
    controls_box.set_margin_start(16)  # Padding from the left edge

    prev_btn = Gtk.Button(icon_name="media-skip-backward-symbolic")
    prev_btn.add_css_class("flat")

    play_icon = Gtk.Image.new_from_icon_name("media-playback-start-symbolic")
    play_icon.set_pixel_size(32)

    play_pause_btn = Gtk.Button()
    play_pause_btn.set_child(play_icon)
    play_pause_btn.add_css_class("flat")
    play_pause_btn.add_css_class("suggested-action")

    def on_play_pause_toggled(button: Gtk.Button):
        logging.debug("Play/Pause button clicked")
        playing.on_next(not playing.value)

        play_icon.set_from_icon_name(
            "media-playback-pause-symbolic"
            if playing.value
            else "media-playback-start-symbolic"
        )

    play_pause_btn.connect("clicked", on_play_pause_toggled)
    # make the button larger without increasing the icon size:
    play_pause_btn.set_size_request(48, 48)

    next_btn = Gtk.Button(icon_name="media-skip-forward-symbolic")
    next_btn.add_css_class("flat")

    time_label = Gtk.Label(label="0:04 / 3:09")
    time_label.add_css_class("dim-label")
    time_label.set_margin_start(8)

    controls_box.append(prev_btn)
    controls_box.append(play_pause_btn)
    controls_box.append(next_btn)
    controls_box.append(time_label)

    play_bar.pack_start(controls_box)

    # ----------------------------------------------------
    # 2. SONG INFO & ACTIONS (Center)
    # ----------------------------------------------------
    center_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    center_box.set_valign(Gtk.Align.CENTER)

    album_art = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
    album_art.set_pixel_size(48)  # Made slightly larger for the taller bar

    text_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    text_vbox.set_valign(Gtk.Align.CENTER)

    title_label = Gtk.Label(label="サイエンス - Science (feat. KASANE TETO)")
    title_label.set_halign(Gtk.Align.START)
    title_label.set_ellipsize(Pango.EllipsizeMode.END)
    title_label.set_markup("<b>サイエンス - Science (feat. KASANE TETO)</b>")

    subtitle_label = Gtk.Label(label="MIMI • Science • 2024")
    subtitle_label.set_halign(Gtk.Align.START)
    subtitle_label.set_ellipsize(Pango.EllipsizeMode.END)
    subtitle_label.add_css_class("dim-label")

    text_vbox.append(title_label)
    text_vbox.append(subtitle_label)

    actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    actions_box.set_valign(Gtk.Align.CENTER)
    actions_box.set_margin_start(16)

    dislike_btn = Gtk.Button(icon_name="face-sad-symbolic")
    dislike_btn.add_css_class("flat")
    like_btn = Gtk.Button(icon_name="face-smile-symbolic")
    like_btn.add_css_class("flat")
    more_btn = Gtk.Button(icon_name="view-more-symbolic")
    more_btn.add_css_class("flat")

    actions_box.append(dislike_btn)
    actions_box.append(like_btn)
    actions_box.append(more_btn)

    center_box.append(album_art)
    center_box.append(text_vbox)
    center_box.append(actions_box)

    # Set as the center widget
    play_bar.set_center_widget(center_box)

    # ----------------------------------------------------
    # 3. SYSTEM CONTROLS (Right)
    # ----------------------------------------------------
    right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    right_box.set_valign(Gtk.Align.CENTER)
    right_box.set_margin_end(16)  # Padding from the right edge

    vol_btn = Gtk.Button(icon_name="audio-volume-high-symbolic")
    vol_btn.add_css_class("flat")

    repeat_btn = Gtk.Button(icon_name="media-playlist-repeat-symbolic")
    repeat_btn.add_css_class("flat")

    shuffle_btn = Gtk.Button(icon_name="media-playlist-shuffle-symbolic")
    shuffle_btn.add_css_class("flat")

    expand_btn = Gtk.Button(icon_name="pan-up-symbolic")
    expand_btn.add_css_class("flat")

    right_box.append(vol_btn)
    right_box.append(repeat_btn)
    right_box.append(shuffle_btn)
    right_box.append(expand_btn)

    play_bar.pack_end(right_box)

    return play_bar
