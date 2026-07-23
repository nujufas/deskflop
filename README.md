# deskflop

A minimal, from-scratch clone of the core idea behind [Deskflow](https://github.com/deskflow/deskflow)/Synergy:
share one keyboard and mouse between two computers over the network.

Put the two machines side by side. Push your mouse cursor off the edge of the
**server** machine's screen and it appears on the **client** machine, carrying
your keyboard input with it. Push it back and control returns.

## How it works

- The **server** is the machine physically connected to the mouse/keyboard you
  want to share. It watches the cursor; when it hits the configured screen
  edge, it freezes/hides the local cursor, captures all further mouse and
  keyboard input, and streams it to the client as relative deltas.
- The **client** simulates that input locally. When its cursor gets pushed
  back past the shared edge, it tells the server to take local control back.
- `Ctrl+Alt+Esc` on the server's physical keyboard always forces control back
  to the server, in case the mouse can't reach the edge for some reason.
- Both sides also poll their local clipboard twice a second; whichever one
  changes first pushes its text content to the other, so copy/paste works
  across the two machines regardless of which one currently has control.

Only one client can be connected at a time, and the two screens are assumed
to be arranged side-by-side (left/right), not stacked.

## Setup

Requires Python 3.8+ on both machines. Nothing else to install by hand:
`deskflop.sh` / `deskflop.bat` create a local `.venv` next to themselves and
install `requirements.txt` into it automatically the first time you run
them. (If you invoke `deskflop.py` directly instead of the wrapper, you're
responsible for `pip install -r requirements.txt` yourself.)

Platform notes:
- **Windows**: works out of the box.
- **macOS**: grant your terminal/Python "Accessibility" and "Input Monitoring"
  permission in System Settings → Privacy & Security, on both the server
  (to capture input) and client (to simulate it).
- **Linux**: requires an X11 session (Xorg or XWayland). Plain Wayland
  compositors generally block the global hooks pynput relies on. Clipboard
  sync needs a clipboard tool on the `PATH`: `xclip` or `xsel` for X11, or
  `wl-clipboard` under Wayland.

Open/forward the chosen TCP port (default `24800`) on the **server**
machine's firewall so the client can reach it.

## Usage

On the machine whose keyboard/mouse you want to share (the server), specify
which edge of its screen is adjacent to the client:

```bash
./deskflop.sh server --edge right --password "some-shared-secret"
```

On the other machine (the client), point it at the server:

```bash
./deskflop.sh client --host 192.168.1.10 --password "some-shared-secret"
```

On Windows, use `deskflop.bat` instead of `deskflop.sh` with the same arguments.

`--edge` is `left` or `right` and describes the server's own screen — e.g. if
the client sits physically to the server's right, use `--edge right` (the
default). The client automatically mirrors this, entering/exiting from the
opposite edge.

Full option list: `./deskflop.sh server --help` / `./deskflop.sh client --help`
(`--port`, `--width`/`--height` to override auto-detected screen size if
detection fails on a headless/multi-monitor setup, `--no-clipboard` to
disable clipboard syncing on that machine).

### Convenience scripts

`scripts/` has ready-made wrappers for each side of a left/right layout, on
both platforms. Each is named for which of *its own* screen edges faces the
other machine (not for where that machine physically sits on your desk), so
the two machines you run always pair up as one `left` + one `right`:

| This machine is...                          | Run (Linux/macOS)          | Run (Windows)               |
|----------------------------------------------|-----------------------------|-------------------------------|
| server, client is to my right (default)       | `scripts/server-right.sh`  | `scripts\server-right.bat`  |
| server, client is to my left                  | `scripts/server-left.sh`   | `scripts\server-left.bat`   |
| client, server is to my right                 | `scripts/client-right.sh`  | `scripts\client-right.bat`  |
| client, server is to my left                  | `scripts/client-left.sh`   | `scripts\client-left.bat`   |

e.g. for a server machine sitting physically on your left and a client
sitting physically on your right: on the server, the client is to *its*
right, so run `scripts/server-right.sh --password secret`; on the client,
the server is to *its* left, so run
`scripts/client-left.sh --host <server-ip> --password secret`. Any extra
flags (`--password`, `--host`, `--port`, ...) are forwarded straight through
to `deskflop.py`. If you pick a mismatched pair, the client prints a warning
(it still works — the server's setting is authoritative — but it's a sign
one of the scripts is wrong for the physical layout).

## Security

This is a small educational/utility tool, not a hardened product:

- The connection is **plain, unencrypted TCP** — every keystroke and every
  clipboard change (including things like passwords copied from a password
  manager) travels in the clear. `--password` is only a shared-secret
  handshake to keep strangers on the LAN from connecting, it does **not**
  encrypt traffic. Use `--no-clipboard` on either side if you'd rather it
  never leaves that machine.
- Only run this on a trusted network, or tunnel it over SSH/VPN
  (e.g. `ssh -L 24800:localhost:24800 user@server` and connect the client to
  `--host 127.0.0.1`).
- Always set `--password` to something non-empty; running without one lets
  anyone on the network who finds the port take over your keyboard/mouse.

## Limitations

- Two machines only, one direction of hand-off logic (left/right, not
  top/bottom).
- Clipboard sync is text-only (no images, files, or rich formatting), and is
  polling-based (up to ~0.5s latency) rather than event-driven.
- No drag-and-drop, no file transfer.
- The server's local cursor will visibly snap/jitter while control is handed
  to the client — this is an artifact of the portable "recenter and measure
  deltas" technique used instead of OS-specific relative-mouse-capture APIs.
