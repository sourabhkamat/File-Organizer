#!/usr/bin/env python3
# organizer.py - main entrypoint for File Organizer
# NOTE: Keep this file simple and ASCII-only docstrings to avoid pyinstaller unicodeescape issues.

from __future__ import annotations
import ctypes, msvcrt
import os, sys, json, shutil, time, traceback, re, subprocess
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Tuple
from action_manage_gui import action_manage_gui

# UI libs detection (used only for messageboxes)
try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
except Exception:
    import tkinter as tk
    from tkinter import messagebox, simpledialog, filedialog
    CTK_AVAILABLE = False

# optional send2trash
try:
    from send2trash import send2trash
    SEND2TRASH = True
except Exception:
    SEND2TRASH = False

APP_NAME = "File Organizer"
APPDATA_SUBDIR = "File Organizer"
IGNORE_FILENAMES = {"Thumbs.db", ".DS_Store", "desktop.ini"}
IGNORE_EXTENSIONS = {".tmp", ".crdownload", ".part", ".partial"}
MAX_WORKERS = max(2, min(32, (os.cpu_count() or 2) * 4))

# ---------------- Paths ----------------
def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_appdata_dir() -> str:
    appdata = os.getenv("APPDATA") or os.path.expanduser("~")
    path = os.path.join(appdata, APPDATA_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path

def appdata_file(name: str) -> str:
    return os.path.join(get_appdata_dir(), name)

# ---------------- JSON helpers ----------------
def read_json(path: str, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def write_json(path: str, data) -> None:
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        try:
            with open(os.path.join(get_appdata_dir(), "error.log"), "a", encoding="utf-8") as logf:
                logf.write(f"{time.ctime()}: Failed to write {path}\n")
        except Exception:
            pass

def ensure_appdata_defaults():
    base = get_base_dir()
    appdata = get_appdata_dir()
    for name in (
        "default_presets.json",
        "user_presets.json",
        "public_suffix_list.dat",
        "undo_stack.json",
        "boot_count.txt",
    ):
        src = os.path.join(base, name)
        dst = os.path.join(appdata, name)
        if not os.path.exists(dst) and os.path.exists(src):
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass
    if not os.path.exists(appdata_file("undo_stack.json")):
        write_json(appdata_file("undo_stack.json"), {})
    if not os.path.exists(appdata_file("user_presets.json")):
        write_json(appdata_file("user_presets.json"), {})

# =====================================================
# 🔁 BOOT SESSION DETECTION (NEW)
# =====================================================
def get_boot_id():
    try:
        GetTickCount64 = ctypes.windll.kernel32.GetTickCount64
        GetTickCount64.restype = ctypes.c_ulonglong
        uptime_ms = GetTickCount64()
        # reboot = uptime resets → use coarse bucket
        return int(uptime_ms // 1000)
    except Exception:
        return None


def check_boot_session():
    path = appdata_file("boot_id.txt")
    current = get_boot_id()
    if current is None:
        return

    try:
        old = int(open(path).read().strip())
    except Exception:
        old = None

    if old is None or current < old:
        # reboot detected
        write_json(appdata_file("undo_stack.json"), [])

    with open(path, "w") as f:
        f.write(str(current))


# =====================================================
# 🔁 UNDO STACK (NEW)
# =====================================================
def load_undo_stack() -> List[Dict[str, Any]]:
    return read_json(appdata_file("undo_stack.json"), []) or []

def save_undo_stack(stack: List[Dict[str, Any]]) -> None:
    write_json(appdata_file("undo_stack.json"), stack)

def push_undo_action(action: dict) -> None:
    path = appdata_file("undo_stack.json")

    # Ensure file exists
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("[]")

    with open(path, "r+", encoding="utf-8") as f:
        # Ensure file has at least 1 byte for locking
        f.seek(0, os.SEEK_END)
        if f.tell() == 0:
            f.write(" ")
            f.flush()

        # Lock the entire file
        while True:
            try:
                f.seek(0)
                size = max(1, os.path.getsize(path))
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, size)
                break
            except OSError:
                time.sleep(0.01)

        try:
            # Read existing undo stack
            f.seek(0)
            try:
                stack = json.load(f)
                if not isinstance(stack, list):
                    stack = []
            except Exception:
                stack = []

            # Append new action
            stack.append(action)

            # Rewrite file safely
            f.seek(0)
            f.truncate()
            json.dump(stack, f, indent=2)
            f.flush()

        finally:
            # Unlock
            f.seek(0)
            size = max(1, os.path.getsize(path))
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, size)

# ---------------- Safe move / collision ----------------
def unique_dest(dest_dir: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    candidate = filename
    i = 1
    while os.path.exists(os.path.join(dest_dir, candidate)):
        candidate = f"{base} ({i}){ext}"
        i += 1
    return os.path.join(dest_dir, candidate)

def safe_move(src: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)

# ---------------- Ignore tests ----------------
def is_ignored(path: str) -> bool:
    name = os.path.basename(path)
    if name in IGNORE_FILENAMES:
        return True
    _, ext = os.path.splitext(name)
    return ext.lower() in IGNORE_EXTENSIONS

# ---------------- PSL helper ----------------
class PublicSuffixList:
    def __init__(self, psl_path: Optional[str] = None):
        self.path = psl_path or os.path.join(get_base_dir(), "public_suffix_list.dat")
        self.rules: set = set()
        self.exceptions: set = set()
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("//"):
                        continue
                    if line.startswith("!"):
                        self.exceptions.add(line[1:])
                    else:
                        self.rules.add(line)
        except Exception:
            self.rules = set()
            self.exceptions = set()

    def get_registrable_domain(self, hostname: str) -> Optional[str]:
        if not hostname:
            return None
        hostname = hostname.strip().lower().rstrip(".")
        if re.match(r'^\d+(\.\d+){3}$', hostname) or hostname.startswith("[") or ":" in hostname:
            return None
        labels = hostname.split(".")
        for ex in self.exceptions:
            if hostname.endswith(ex):
                parts = hostname.split(".")
                if len(parts) > len(ex.split(".")):
                    return ".".join(parts[-(len(ex.split(".")) + 1):])
        match = ""
        for i in range(len(labels)):
            cand = ".".join(labels[i:])
            if cand in self.rules and len(cand) > len(match):
                match = cand
        if match:
            rule_parts = match.split(".")
            if len(labels) > len(rule_parts):
                return ".".join(labels[-(len(rule_parts) + 1):])
            return hostname
        if len(labels) >= 2:
            return ".".join(labels[-2:])
        return None

# ---------------- ADS reader ----------------
def get_hosturl_from_ads(path: str) -> Optional[str]:
    ads = path + ":Zone.Identifier"
    try:
        with open(ads, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.strip().startswith("HostUrl="):
                    return line.strip()[len("HostUrl="):].strip()
    except Exception:
        return None
    return None

# ---------------- presets ----------------
def load_presets_merge() -> Dict[str, str]:
    users = read_json(appdata_file("user_presets.json"), {}) or {}
    return {k.lower(): v for k, v in users.items()}

# ---------------- Action: By Type ----------------
def action_by_type(folder: str) -> int:
    if not os.path.isdir(folder):
        return 1
    presets = load_presets_merge()
    last = {"moves": [], "created_dirs": []}
    created = set()

    for name in os.listdir(folder):
        f = os.path.join(folder, name)
        if not os.path.isfile(f) or is_ignored(f):
            continue
        try:
            _, ext = os.path.splitext(name)
            cat = presets.get(ext.lower(), "Other Files")
            dest_dir = os.path.join(folder, cat)
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
                if dest_dir not in created:
                    created.add(dest_dir)
                    last["created_dirs"].append(os.path.abspath(dest_dir))
            dest = unique_dest(dest_dir, name)
            safe_move(f, dest)
            last["moves"].append([os.path.abspath(f), os.path.abspath(dest)])
        except Exception:
            continue

    push_undo_action(last)
    return 0

# ---------------- helpers for By Source parsing ----------------
def host_valid(hostname: Optional[str]) -> bool:
    if not hostname:
        return False
    if re.match(r'^[A-Za-z0-9\.\-]+$', hostname):
        if re.match(r'^\d+(\.\d+){3}$', hostname):
            return False
        if hostname.lower() in ("localhost",):
            return False
        return True
    return False

def sanitize_folder_name(name: str) -> Optional[str]:
    cleaned = re.sub(r'[^A-Za-z0-9\-_\. ]', '', name).strip()
    return cleaned.capitalize() if cleaned else None

def _parse_ads_domain_simple(path: str, psl: PublicSuffixList) -> Tuple[str, Optional[str]]:
    u = get_hosturl_from_ads(path)
    if not u:
        return (path, None)
    try:
        parsed = urlparse(u)
        if parsed.scheme not in ("http", "https"):
            return (path, None)
        hostname = parsed.hostname
        if not host_valid(hostname):
            return (path, None)
        registrable = psl.get_registrable_domain(hostname)
        if not registrable:
            return (path, None)
        labels = registrable.split(".")
        safe = sanitize_folder_name(labels[-2])
        return (path, safe)
    except Exception:
        return (path, None)

# ---------------- Action: By Source ----------------
def action_by_source(folder: str) -> int:
    if not os.path.isdir(folder):
        return 1
    files = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
    psl = PublicSuffixList(appdata_file("public_suffix_list.dat"))
    last = {"moves": [], "created_dirs": []}
    created = set()
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(_parse_ads_domain_simple, f, psl): f for f in files if not is_ignored(f)}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception:
                continue

    for f, domain in results:
        try:
            dest_dir = os.path.join(folder, domain or "Unknown Sources")
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
                if dest_dir not in created:
                    created.add(dest_dir)
                    last["created_dirs"].append(os.path.abspath(dest_dir))
            dest = unique_dest(dest_dir, os.path.basename(f))
            safe_move(f, dest)
            last["moves"].append([os.path.abspath(f), os.path.abspath(dest)])
        except Exception:
            continue

    push_undo_action(last)
    return 0

# ---------------- Action: Category (GUI + CLI) ----------------
def action_category_cli(folder: str, category: str) -> int:
    if not os.path.isdir(folder):
        return 1
    presets = load_presets_merge()
    last = {"moves": [], "created_dirs": []}
    created = set()

    for name in os.listdir(folder):
        f = os.path.join(folder, name)
        if not os.path.isfile(f) or is_ignored(f):
            continue
        _, ext = os.path.splitext(name)
        if presets.get(ext.lower()) == category:
            dest_dir = os.path.join(folder, category)
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
                if dest_dir not in created:
                    created.add(dest_dir)
                    last["created_dirs"].append(os.path.abspath(dest_dir))
            dest = unique_dest(dest_dir, name)
            safe_move(f, dest)
            last["moves"].append([os.path.abspath(f), os.path.abspath(dest)])

    push_undo_action(last)
    return 0

def action_category_gui(folder: str) -> int:
    presets = load_presets_merge()
    cats = sorted(set(presets.values()) | {"Images", "Videos", "Audio", "Other Files"})
    # lightweight GUI selection if CustomTkinter available
    if CTK_AVAILABLE:
        root = ctk.CTk(); root.title("Organize by Category"); root.geometry("420x480")
        var = ctk.StringVar(value=cats[0])
        frame = ctk.CTkFrame(root); frame.pack(fill="both", expand=True, padx=12, pady=12)
        ctk.CTkLabel(frame, text=f"Organize by Category in:\n{folder}", anchor="w").pack(anchor="w")
        scr = ctk.CTkScrollableFrame(frame); scr.pack(fill="both", expand=True, pady=(8,8))
        for c in cats:
            ctk.CTkRadioButton(scr, text=c, variable=var, value=c).pack(anchor="w", pady=3)
        def do_ok():
            root.destroy()
        ctk.CTkButton(frame, text="Organize", command=do_ok).pack(side="left", padx=6, pady=6)
        ctk.CTkButton(frame, text="Close", command=root.destroy).pack(side="right", padx=6, pady=6)
        root.mainloop()
        chosen = var.get()
    else:
        tk_root = tk.Tk(); tk_root.withdraw()
        chosen = simpledialog.askstring("Category", "Enter category to organize into:", initialvalue=cats[0])
        tk_root.destroy()
        if not chosen:
            return 1
    return action_category_cli(folder, chosen)

# ---------------- Action: File Puller ----------------
def action_file_puller(paths: List[str], mode: str = "all") -> int:
    last = {"moves": [], "created_dirs": []}

    for p in paths:
        if not os.path.isdir(p):
            continue

        # Snapshot files FIRST (critical)
        files_to_move = []
        for root, _, files in os.walk(p):
            for fname in files:
                src = os.path.join(root, fname)
                if is_ignored(src):
                    continue
                files_to_move.append(src)

        if not files_to_move:
            continue

        if mode == "above":
            parent = os.path.dirname(p)
            if not parent:
                continue

            for src in files_to_move:
                dest = unique_dest(parent, os.path.basename(src))
                safe_move(src, dest)
                last["moves"].append([os.path.abspath(src), os.path.abspath(dest)])

        elif mode == "here":
            for src in files_to_move:
                if os.path.dirname(src) == p:
                    continue
                dest = unique_dest(p, os.path.basename(src))
                safe_move(src, dest)
                last["moves"].append([os.path.abspath(src), os.path.abspath(dest)])

        else:  # mode == "all"
            parent = os.path.dirname(p) or p
            dest_dir = os.path.join(parent, "Files Bin")
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
                last["created_dirs"].append(os.path.abspath(dest_dir))

            for src in files_to_move:
                dest = unique_dest(dest_dir, os.path.basename(src))
                safe_move(src, dest)
                last["moves"].append([os.path.abspath(src), os.path.abspath(dest)])

    # Only push undo if something actually happened
    if last["moves"] or last["created_dirs"]:
        push_undo_action(last)
        return 0

    return 1


# ---------------- Delete Empty Folders ----------------
def action_delete_empty(folder: str) -> int:
    if not os.path.isdir(folder):
        return 1

    folder = os.path.abspath(folder)

    # If send2trash is not available, do NOT delete anything
    if not SEND2TRASH:
        return 1

    while True:
        deleted_any = False

        for root, dirs, files in os.walk(folder, topdown=False):
            # Never delete the root folder itself
            if root == folder:
                continue

            if not dirs and not files:
                try:
                    send2trash(root)   # Move to Recycle Bin
                    deleted_any = True
                except Exception:
                    # Locked / permission denied → skip
                    pass

        if not deleted_any:
            break

    return 0


# ---------------- Undo (Explorer-like, multi-level) ----------------
def action_undo(context: Optional[str] = None) -> int:
    stack = load_undo_stack()
    if not stack:
        return 1

    action = stack.pop()

    for src, dst in reversed(action.get("moves", [])):
        try:
            if not os.path.exists(dst):
                continue
            os.makedirs(os.path.dirname(src), exist_ok=True)
            final = src
            if os.path.exists(src):
                base, ext = os.path.splitext(src)
                i = 1
                while True:
                    candidate = f"{base} (restored {i}){ext}"
                    if not os.path.exists(candidate):
                        final = candidate
                        break
                    i += 1
            safe_move(dst, final)
        except Exception:
            continue

    for d in sorted(action.get("created_dirs", []), key=len, reverse=True):
        try:
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
        except Exception:
            continue

    save_undo_stack(stack)
    return 0

# ---------------- Undo all at once ----------------

def action_undo_all() -> int:
    stack = load_undo_stack()
    if not stack:
        return 1

    # Undo actions in reverse order (latest → oldest)
    while stack:
        action = stack.pop()

        # Undo file moves
        for src, dst in reversed(action.get("moves", [])):
            try:
                if not os.path.exists(dst):
                    continue

                os.makedirs(os.path.dirname(src), exist_ok=True)
                final = src

                if os.path.exists(src):
                    base, ext = os.path.splitext(src)
                    i = 1
                    while True:
                        candidate = f"{base} (restored {i}){ext}"
                        if not os.path.exists(candidate):
                            final = candidate
                            break
                        i += 1

                safe_move(dst, final)
            except Exception:
                continue

        # Remove empty created folders
        for d in sorted(action.get("created_dirs", []), key=len, reverse=True):
            try:
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
            except Exception:
                continue

    # Clear undo stack completely
    save_undo_stack([])
    return 0


# ---------------- CLI Entrypoint ----------------
def main(argv: List[str]) -> int:
    ensure_appdata_defaults()
    check_boot_session()

    if len(argv) < 2:
        print("Usage: organizer.exe <action> <path1> <path2> ...")
        return 1

    action = argv[1].lower()
    args = argv[2:]

    try:
        if action == "type":
            return action_by_type(args[0]) if args else 1
        elif action == "source":
            return action_by_source(args[0]) if args else 1
        elif action == "category":
            return action_category_gui(args[0]) if args else 1
        elif action == "pull":
            return action_file_puller(args, mode="all")
        elif action == "pull_here":
            return action_file_puller(args, mode="here")
        elif action == "pull_all":
            return action_file_puller(args, mode="all")
        elif action == "pull_above":
            return action_file_puller(args, mode="above")
        elif action == "delete_empty":
            return action_delete_empty(args[0]) if args else 1
        elif action == "manage":
            return action_manage_gui()
        elif action == "undo":
            return action_undo()
        elif action == "undo_all":
            return action_undo_all()
        else:
            print("Unknown action:", action)
            return 2
    except Exception as e:
        try:
            with open(os.path.join(get_appdata_dir(), "error.log"), "a", encoding="utf-8") as logf:
                logf.write(f"{time.ctime()}: Exception for action {action}: {repr(e)}\n{traceback.format_exc()}\n")
        except Exception:
            pass
        try:
            messagebox.showerror("Error", f"An error occurred: {e}")
        except Exception:
            pass
        return 3

if __name__ == "__main__":
    sys.exit(main(sys.argv))
