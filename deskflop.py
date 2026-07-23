#!/usr/bin/env python3
"""deskflop - minimal cross-platform mouse/keyboard sharing tool (Deskflow/Synergy-style).

One machine is the "server" (it owns the physical mouse/keyboard). One machine
is the "client" (it receives events over the network and simulates them).
Moving the server's cursor into the shared screen edge hands control to the
client; moving the client's cursor back past that same edge hands it back.

    deskflop.py server --edge right --password SECRET
    deskflop.py client --host 192.168.1.10 --password SECRET

NOTE: traffic is a plain, unencrypted TCP stream carrying every keystroke.
Only use this on a trusted LAN, or tunnel it over SSH/VPN. --password only
provides a shared-secret handshake, not encryption.
"""
import argparse
import hashlib
import json
import socket
import sys
import threading
import time

from pynput import keyboard, mouse

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

DEFAULT_PORT = 24800
CLIPBOARD_POLL_INTERVAL = 0.5

BUTTON_NAMES = {mouse.Button.left: "left", mouse.Button.right: "right", mouse.Button.middle: "middle"}
BUTTON_FROM_NAME = {v: k for k, v in BUTTON_NAMES.items()}

ESCAPE_MODIFIERS = {"ctrl_l", "ctrl_r", "alt_l", "alt_r"}


def get_screen_size():
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
        return w, h
    except Exception:
        return None


def key_to_wire(key):
    if isinstance(key, keyboard.KeyCode):
        if key.char is not None:
            return {"char": key.char}
        return {"vk": key.vk}
    return {"special": key.name}


def key_from_wire(data):
    if "char" in data:
        return keyboard.KeyCode.from_char(data["char"])
    if "vk" in data:
        return keyboard.KeyCode.from_vk(data["vk"])
    return getattr(keyboard.Key, data["special"])


def password_token(password):
    return hashlib.sha256((password or "").encode("utf-8")).hexdigest()


class Connection:
    """Line-delimited JSON messages over a TCP socket, with a write lock
    since mouse/keyboard listener threads can all send concurrently."""

    def __init__(self, sock):
        self.sock = sock
        self.rfile = sock.makefile("r", encoding="utf-8", newline="\n")
        self.wfile = sock.makefile("w", encoding="utf-8", newline="\n")
        self.lock = threading.Lock()

    def send(self, obj):
        line = json.dumps(obj)
        with self.lock:
            self.wfile.write(line + "\n")
            self.wfile.flush()

    def recv(self):
        line = self.rfile.readline()
        if not line:
            return None
        return json.loads(line)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class ClipboardSync:
    """Polls the local clipboard for changes and forwards them to the peer;
    applies clipboard content received from the peer without echoing it back."""

    def __init__(self, send_func):
        self.send_func = send_func
        self.last_value = self._read()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    @staticmethod
    def _read():
        try:
            return pyperclip.paste()
        except Exception:
            return None

    def _poll_loop(self):
        while not self._stop.wait(CLIPBOARD_POLL_INTERVAL):
            current = self._read()
            if current is not None and current != self.last_value:
                self.last_value = current
                self.send_func(current)

    def apply_remote(self, text):
        self.last_value = text
        try:
            pyperclip.copy(text)
        except Exception:
            pass


class Server:
    def __init__(self, port, edge, password, width=None, height=None, clipboard=True):
        self.port = port
        self.edge = edge  # which edge of THIS screen borders the client
        self.password = password
        size = (width, height) if width and height else get_screen_size()
        if not size or not size[0] or not size[1]:
            sys.exit("Could not detect screen size automatically; pass --width and --height.")
        self.width, self.height = size
        self.center = (self.width // 2, self.height // 2)
        self.last_pos = self.center

        self.captured = False
        self.conn = None
        self.state_lock = threading.Lock()
        self.mouse_controller = mouse.Controller()
        self.pressed_specials = set()

        self.mouse_listener = None
        self.keyboard_listener = None

        self.clipboard = None
        if clipboard and HAS_PYPERCLIP:
            self.clipboard = ClipboardSync(lambda text: self._safe_send({"t": "clipboard", "text": text}))
        elif clipboard:
            print("[deskflop] clipboard sync disabled: install 'pyperclip' to enable it")

    def edge_hit(self, x, y):
        return x >= self.width - 1 if self.edge == "right" else x <= 0

    def start_normal_listener(self):
        self.mouse_listener = mouse.Listener(on_move=self.on_move_idle, suppress=False)
        self.mouse_listener.start()

    def start_captured_listeners(self):
        self.mouse_listener = mouse.Listener(
            on_move=self.on_move_captured,
            on_click=self.on_click_captured,
            on_scroll=self.on_scroll_captured,
            suppress=True,
        )
        self.mouse_listener.start()
        self.keyboard_listener = keyboard.Listener(
            on_press=lambda k: self.on_key_captured(k, True),
            on_release=lambda k: self.on_key_captured(k, False),
            suppress=True,
        )
        self.keyboard_listener.start()

    def stop_listeners(self):
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None

    def on_move_idle(self, x, y):
        if self.captured or self.conn is None:
            return
        if self.edge_hit(x, y):
            self.enter_capture(y)

    def enter_capture(self, y):
        with self.state_lock:
            if self.captured:
                return
            self.captured = True
        y_ratio = max(0.0, min(1.0, y / max(1, self.height - 1)))
        self.stop_listeners()
        self.mouse_controller.position = self.center
        self.last_pos = self.center
        self.start_captured_listeners()
        self._safe_send({"t": "enter", "y_ratio": y_ratio})
        print("[deskflop] control -> client")

    def leave_capture(self):
        with self.state_lock:
            if not self.captured:
                return
            self.captured = False
        self.stop_listeners()
        edge_x = self.width - 2 if self.edge == "right" else 1
        self.mouse_controller.position = (edge_x, self.center[1])
        self.pressed_specials.clear()
        self.start_normal_listener()
        print("[deskflop] control -> server")

    def on_move_captured(self, x, y):
        dx, dy = x - self.last_pos[0], y - self.last_pos[1]
        if dx or dy:
            self._safe_send({"t": "move", "dx": dx, "dy": dy})
        if (x, y) != self.center:
            self.mouse_controller.position = self.center
            self.last_pos = self.center
        else:
            self.last_pos = (x, y)

    def on_click_captured(self, x, y, button, pressed):
        name = BUTTON_NAMES.get(button)
        if name:
            self._safe_send({"t": "click", "button": name, "pressed": pressed})

    def on_scroll_captured(self, x, y, dx, dy):
        self._safe_send({"t": "scroll", "dx": dx, "dy": dy})

    def on_key_captured(self, key, pressed):
        name = getattr(key, "name", None)
        if name in ESCAPE_MODIFIERS:
            if pressed:
                self.pressed_specials.add(name)
            else:
                self.pressed_specials.discard(name)
        has_ctrl = "ctrl_l" in self.pressed_specials or "ctrl_r" in self.pressed_specials
        has_alt = "alt_l" in self.pressed_specials or "alt_r" in self.pressed_specials
        if pressed and name == "esc" and has_ctrl and has_alt:
            self.leave_capture()  # panic button: force control back to the server
            return
        self._safe_send({"t": "key", "key": key_to_wire(key), "pressed": pressed})

    def _safe_send(self, obj):
        if self.conn is None:
            return
        try:
            self.conn.send(obj)
        except OSError:
            pass

    def handle_client_messages(self):
        while True:
            try:
                msg = self.conn.recv()
            except (OSError, ValueError):
                break
            if msg is None:
                break
            t = msg.get("t")
            if t == "switch_back":
                self.leave_capture()
            elif t == "clipboard" and self.clipboard:
                self.clipboard.apply_remote(msg.get("text", ""))
        self.conn.close()
        if self.captured:
            self.leave_capture()
        self.conn = None
        print("[deskflop] client disconnected")

    def run(self):
        srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv_sock.bind(("0.0.0.0", self.port))
        srv_sock.listen(1)
        print(f"[deskflop] server listening on port {self.port} "
              f"({self.width}x{self.height}, hand-off edge={self.edge})")
        if not self.password:
            print("[deskflop] WARNING: no --password set, anyone on the network can connect")
        self.start_normal_listener()
        if self.clipboard:
            self.clipboard.start()
        try:
            while True:
                sock, addr = srv_sock.accept()
                print(f"[deskflop] connection from {addr[0]}")
                conn = Connection(sock)
                first = conn.recv()
                if not first or first.get("t") != "auth" or first.get("token") != password_token(self.password):
                    print("[deskflop] auth failed, rejecting")
                    conn.close()
                    continue
                conn.send({"t": "hello", "edge": self.edge})
                self.conn = conn
                self.handle_client_messages()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_listeners()
            srv_sock.close()


class Client:
    def __init__(self, host, port, password, width=None, height=None, clipboard=True, edge=None):
        self.host = host
        self.port = port
        self.password = password
        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()
        size = (width, height) if width and height else get_screen_size()
        if not size or not size[0] or not size[1]:
            sys.exit("Could not detect screen size automatically; pass --width and --height.")
        self.width, self.height = size
        self.server_edge = "right"
        self.expected_edge = edge  # which edge of THIS (client) screen the user expects borders the server
        self.conn = None

        self.clipboard = None
        if clipboard and HAS_PYPERCLIP:
            self.clipboard = ClipboardSync(lambda text: self._safe_send({"t": "clipboard", "text": text}))
        elif clipboard:
            print("[deskflop] clipboard sync disabled: install 'pyperclip' to enable it")

    def connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        conn = Connection(sock)
        conn.send({"t": "auth", "token": password_token(self.password)})
        reply = conn.recv()
        if not reply or reply.get("t") != "hello":
            raise RuntimeError("authentication with server failed (check --password)")
        self.server_edge = reply.get("edge", "right")
        self.conn = conn
        print(f"[deskflop] connected to server {self.host}:{self.port}")
        expected = "left" if self.server_edge == "right" else "right"
        if self.expected_edge and self.expected_edge != expected:
            print(f"[deskflop] WARNING: this client was started with --edge {self.expected_edge}, "
                  f"but the server's config implies this client's bordering edge should be '{expected}' "
                  f"-- double check the left/right script you ran on each machine")

    def run(self):
        if self.clipboard:
            self.clipboard.start()
        while True:
            try:
                self.connect()
            except RuntimeError as e:
                sys.exit(f"[deskflop] {e}")
            except OSError as e:
                print(f"[deskflop] connect failed ({e}), retrying in 2s")
                time.sleep(2)
                continue
            self.serve_forever()
            print("[deskflop] disconnected from server, retrying...")
            time.sleep(1)

    def serve_forever(self):
        while True:
            try:
                msg = self.conn.recv()
            except (OSError, ValueError):
                break
            if msg is None:
                break
            self.handle(msg)
        self.conn.close()

    def handle(self, msg):
        t = msg.get("t")
        if t == "enter":
            y = int(msg["y_ratio"] * (self.height - 1))
            edge_x = 1 if self.server_edge == "right" else self.width - 2
            self.mouse_controller.position = (edge_x, y)
        elif t == "move":
            x, y = self.mouse_controller.position
            nx = max(0, min(self.width - 1, x + msg["dx"]))
            ny = max(0, min(self.height - 1, y + msg["dy"]))
            self.mouse_controller.position = (nx, ny)
            hit_back = (nx <= 0) if self.server_edge == "right" else (nx >= self.width - 1)
            if hit_back:
                self._safe_send({"t": "switch_back"})
        elif t == "click":
            button = BUTTON_FROM_NAME.get(msg["button"])
            if button:
                if msg["pressed"]:
                    self.mouse_controller.press(button)
                else:
                    self.mouse_controller.release(button)
        elif t == "scroll":
            self.mouse_controller.scroll(msg["dx"], msg["dy"])
        elif t == "key":
            key = key_from_wire(msg["key"])
            if msg["pressed"]:
                self.keyboard_controller.press(key)
            else:
                self.keyboard_controller.release(key)
        elif t == "clipboard" and self.clipboard:
            self.clipboard.apply_remote(msg.get("text", ""))

    def _safe_send(self, obj):
        if self.conn is None:
            return
        try:
            self.conn.send(obj)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description="deskflop - share one keyboard/mouse across two machines")
    sub = parser.add_subparsers(dest="mode", required=True)

    srv = sub.add_parser("server", help="run as the server (owns the physical keyboard/mouse)")
    srv.add_argument("--port", type=int, default=DEFAULT_PORT)
    srv.add_argument("--edge", choices=["left", "right"], default="right",
                      help="which edge of THIS screen borders the client machine (default: right)")
    srv.add_argument("--password", default="", help="shared secret, must match the client")
    srv.add_argument("--width", type=int, default=None, help="override auto-detected screen width")
    srv.add_argument("--height", type=int, default=None, help="override auto-detected screen height")
    srv.add_argument("--no-clipboard", action="store_true", help="disable clipboard sync")

    cli = sub.add_parser("client", help="run as the client (receives keyboard/mouse events)")
    cli.add_argument("--host", required=True, help="server hostname or IP")
    cli.add_argument("--port", type=int, default=DEFAULT_PORT)
    cli.add_argument("--password", default="", help="shared secret, must match the server")
    cli.add_argument("--width", type=int, default=None, help="override auto-detected screen width")
    cli.add_argument("--height", type=int, default=None, help="override auto-detected screen height")
    cli.add_argument("--no-clipboard", action="store_true", help="disable clipboard sync")
    cli.add_argument("--edge", choices=["left", "right"], default=None,
                      help="which edge of THIS (client) screen borders the server; optional, "
                           "only used to sanity-check against what the server reports")

    args = parser.parse_args()

    if args.mode == "server":
        Server(args.port, args.edge, args.password, args.width, args.height, not args.no_clipboard).run()
    else:
        Client(args.host, args.port, args.password, args.width, args.height,
               not args.no_clipboard, args.edge).run()


if __name__ == "__main__":
    main()
