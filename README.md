# YT Music GTK

![](./assets/icons/com.example.YTMusicApp.svg)

A Desktop YouTube Music client in GTK4.

> [!WARNING]  
> This project is currently HIGHLY experimental!

## Getting Started

### Prerequisites

To run this application, you will need to install the following dependencies on your system:

- **[uv](https://docs.astral.sh/uv/#installation)**: An extremely fast Python package installer and resolver.
- **[GTK4 / libadwaita](https://www.gtk.org/docs/installations/)**: The GNOME UI libraries and their respective Python bindings.
- **[NodeJS](https://nodejs.org/en/download/), [Bun](https://bun.sh/docs/installation), or [Deno](https://deno.land/manual/getting_started/installation)**: Required by `yt-dlp` to execute JavaScript for extracting certain streams.

### Running the App

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
> It reads cookies from Firefox or Chrome. You need to be logged in to YouTube Music in one of them.
>
> This, of course, is a bit sus, so use it at your own risk.

<img width="1014" alt="image" src="https://github.com/user-attachments/assets/590c56e9-2974-46eb-92a7-cd83ca3a36a3" />

<img width="1056" alt="" src="https://github.com/user-attachments/assets/5162050c-2572-4822-a3fc-d307af6972ed" />

<img width="824" alt="image" src="https://github.com/user-attachments/assets/ef56cddb-46cd-4088-b140-4b6d53081253" />

> Also works on macOS :D

<img width="1012" alt="mac" src="https://github.com/user-attachments/assets/7ef0acab-e0b2-48dd-a155-37dfd745eb87" />

## Features

- Login (partial)
- Playback (partial)
- Home Page (partial)
- Like/dislike
