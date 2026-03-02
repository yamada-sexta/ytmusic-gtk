---
name: YTMusic-GTK Guidelines
description: Core architectural and styling guidelines for the YTMusic-GTK project.
---

# YTMusic-GTK Agent Guidelines

This primary skill provides the core architectural context and programming guidelines for the `ytmusic-gtk` project. Whenever an agent is helping out in this repository, they MUST adhere to these practices.

## Core Technologies

- **UI Framework:** GTK4 with LibAdw (via `pygobject` bindings).
- **Python Version:** Python >= 3.13 (Targeting the absolute latest modern standards).
- **State Management:** ReactiveX (using the `reactivex` library).

## Modern Python & Type Hinting

- Provide **maximum possible type hinting** for all classes, arguments, returns, and variables.
- Utilize modern Python type-hinting features available in 3.13:
  - Use `|` instead of `Union` or `Optional` (e.g., `str | None`).
  - Use built-in generic collections (e.g., `list[str]`, `dict[str, int]`, `tuple[int, ...]`) instead of importing from `typing`.
  - Use Python 3.12+ type parameter syntax (`class MyClass[T]:` or `def generic_func[T](arg: T) -> T:`) for generic definitions.

## Functional & Reactive State Management

- **Functional Paradigm:** Prefer functional patterns such as pure functions, immutability, list comprehensions, and declarative logic over complex imperative loop mutation.
- **ReactiveX State Manager:** Avoid traditional callbacks and global mutable state variables. Instead, use ReactiveX (`reactivex`):
  - Expose application states as Observables (e.g., `BehaviorSubject`).
  - Connect disparate parts of the app exclusively via Stream subscriptions rather than direct method calls or signals.
- **Thread Safety in UI:** Always remember that ReactiveX subscriptions operating on background threads must dispatch UI updates back to the GTK main thread using `GLib.idle_add(callback)`.

## UI Architecture (GTK4 & LibAdw)

- Structure UI with `Adw` classes wherever possible (e.g., `Adw.ApplicationWindow`, `Adw.ToolbarView`, `Adw.HeaderBar`, `Adw.ViewStack`) to cleanly map to the modern GNOME HIG.
- Break down complex UIs into separate, cohesive modules or functions (e.g., `create_search_bar()`) returning GTK widgets, rather than keeping all assembly code bundled in the main window.

## Setup & Execution

- **Package Management & Environment:** This project is managed using `uv`.
- **Executing Code:** Always use `uv run <script>` (e.g., `uv run main.py`) instead of the system Python to ensure execution uses the correct virtual environment and dependencies.

## Comment Style

- **Avoid Counting** - Do not use `1.`, `2.`, `3.` etc. in comments. Use simple single line comments instead.
- **Avoid Deleting Comment** Do not delete unnecessary comments. Even if the comment is not useful, keep it.
- **Avoid Commenting Obvious Code** Do not comment obvious code. If the code is self-explanatory, do not comment it.
