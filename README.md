# YT Music GTK

<p align="center">
    <img src="./assets/app/com.yamadasexta.YTMusicApp.svg" width="256" height="150">
</p>

A cross-platform Desktop YouTube Music client made with Libadwaita

---

<img width="950" alt="image" src="https://github.com/user-attachments/assets/a285caed-e31f-4186-8c31-d3cf4498dde8" />


<img width="1012" alt="mac" src="https://github.com/user-attachments/assets/7ef0acab-e0b2-48dd-a155-37dfd745eb87" />

> [!WARNING]  
> This project is currently HIGHLY experimental!

## Getting Started

### Prerequisites

To run this application, you will need to install the following dependencies on your system:

- **[uv](https://docs.astral.sh/uv/#installation)**: An extremely fast Python package installer and resolver.
- **[GTK4 / libadwaita / GObject](https://www.gtk.org/docs/installations/)**: The GNOME UI libraries and their respective Python bindings.
- **[NodeJS](https://nodejs.org/en/download/), [Bun](https://bun.sh/docs/installation), or [Deno](https://deno.land/manual/getting_started/installation)**: Required by `yt-dlp` to execute JavaScript for extracting certain streams.
- **[mpv](https://mpv.io/)**: A free and open-source media player.

### Running the App

> If it doesn't work, try checkout an older commit, particularly, the ones that didn't have a failed check.

Clone the repo:

```bash
git clone https://github.com/yamada-sexta/ytmusic-gtk.git --depth 1
cd ytmusic-gtk
```

Install dependencies:

```bash
uv sync
```

Run the app:

```bash
uv run main.py
```

> [!NOTE]
> It reads cookies from Firefox or Chrome directly. You need to be logged in to YouTube Music in one of them.
>
> This, of course, is a bit sus, so use it at your own risk.

It is only tested on macOS and Linux.

## Features

- Login (partial)
- Playback (partial)
- Home Page (partial)
- Like/dislike
- System Tray & Background Play (macOS/DBus)
- Search (partial)



