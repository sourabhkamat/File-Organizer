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
        "boot_id.txt",
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
        try:
            shutil.copy2(os.path.join(base, "default_presets.json"), appdata_file("user_presets.json"))
        except Exception:
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
        with open(path, "r") as f:
            old = int(f.read().strip())
    except Exception:
        old = None

    if old is None or current < old:
        # reboot detected
        try:
            with open(appdata_file("undo_stack.json"), "w", encoding="utf-8") as fs:
                fs.write("[]")
        except Exception:
            pass

    with open(path, "w") as f:
        f.write(str(current))


# =====================================================
# 🔁 UNDO STACK (NEW)
# =====================================================
import contextlib

@contextlib.contextmanager
def locked_undo_file(mode="r+"):
    path = appdata_file("undo_stack.json")
    
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("[]")

    f = open(path, mode, encoding="utf-8")
    
    if mode in ("r+", "w", "a"):
        f.seek(0, os.SEEK_END)
        if f.tell() == 0:
            f.write(" ")
            f.flush()

    while True:
        try:
            f.seek(0)
            size = max(1, os.path.getsize(path))
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, size)
            break
        except OSError:
            time.sleep(0.01)

    try:
        yield f
    finally:
        f.seek(0)
        size = max(1, os.path.getsize(path))
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, size)
        f.close()


def load_undo_stack() -> List[Dict[str, Any]]:
    try:
        with locked_undo_file("r") as f:
            f.seek(0)
            stack = json.load(f)
            return stack if isinstance(stack, list) else []
    except Exception:
        return []

def save_undo_stack(stack: List[Dict[str, Any]]) -> None:
    try:
        with locked_undo_file("r+") as f:
            f.seek(0)
            f.truncate()
            json.dump(stack, f, indent=2)
            f.flush()
    except Exception:
        pass

def push_undo_action(action: dict) -> None:
    try:
        with locked_undo_file("r+") as f:
            f.seek(0)
            try:
                stack = json.load(f)
                if not isinstance(stack, list):
                    stack = []
            except Exception:
                stack = []

            stack.append(action)

            f.seek(0)
            f.truncate()
            json.dump(stack, f, indent=2)
            f.flush()
    except Exception:
        pass

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

# ---------------- Action: Blacklist ----------------
def is_blacklisted(path: str, is_items: bool = False) -> bool:
    try:
        path = os.path.abspath(path).lower()
        if path.endswith(os.sep):
            path = path[:-1]
            
        sys_drive = os.environ.get('SystemDrive', 'C:').lower()
        
        forbidden_prefixes = [
            os.environ.get('SystemRoot', f'{sys_drive}\\windows').lower(),
            os.environ.get('ProgramFiles', f'{sys_drive}\\program files').lower(),
            os.environ.get('ProgramFiles(x86)', f'{sys_drive}\\program files (x86)').lower(),
            os.environ.get('ProgramData', f'{sys_drive}\\programdata').lower(),
        ]
        
        for fp in forbidden_prefixes:
            if fp and path.startswith(fp):
                return True
                
        # Handle C:\Users
        users_root = os.path.dirname(os.environ.get('USERPROFILE', f'{sys_drive}\\users\\default')).lower()
        if path.startswith(users_root):
            rel = os.path.relpath(path, users_root)
            if rel == ".": 
                return True # exactly C:\Users
            parts = rel.split(os.sep)
            if len(parts) == 1:
                return True # exactly C:\Users\Username
            # Allowed: C:\Users\Username\Desktop...
        
        # Checking root drives
        # path could be "c:" or "d:" natively after stripping os.sep
        is_root_drive = len(path) == 2 and path.endswith(':')
        
        if not is_items:
            # Running on background of ANY root drive is forbidden
            if is_root_drive:
                return True
        else:
            # If the selected item itself is a root drive (e.g. they selected "D:\" from My PC)
            if is_root_drive:
                return True
                
            # If the item is located DIRECTLY in the root of the System Drive 
            # e.g., path="c:\file.txt", dirname is "c:\" -> "c:"
            # We want to forbid organizing directly on the system drive root.
            parent = os.path.dirname(path)
            if parent.endswith(os.sep): 
                parent = parent[:-1]
            if len(parent) == 2 and parent.endswith(':') and parent == sys_drive:
                return True
            
        return False
    except Exception:
        return True # Safe default

def get_category_for_path(path: str, presets: Dict[str, str], current_folder: str = "") -> Tuple[str, bool]:
    if os.path.isdir(path):
        val = presets.get(".folder", "Other Files")
    else:
        _, ext = os.path.splitext(path)
        val = presets.get(ext.lower(), "Other Files")
        
    cats = [c.strip() for c in str(val).split("|")]
    
    dest_cat = "Other Files"
    is_whitelisted = False
    
    for c in cats:
        if c.lower().startswith("whitelist."):
            wl_target = c.split(".", 1)[1].lower()
            if os.path.basename(current_folder).lower() == wl_target:
                is_whitelisted = True
        else:
            dest_cat = c
            
    return dest_cat, is_whitelisted

# ---------------- Action: By Type ----------------
def action_by_type(paths: List[str], is_items: bool) -> int:
    presets = load_presets_merge()
    last = {"moves": [], "created_dirs": []}
    created = set()
    
    for base_arg in paths:
        if is_blacklisted(base_arg, is_items):
            continue
            
        targets = []
        if is_items:
            parent_dir = os.path.dirname(os.path.abspath(base_arg))
            if os.path.isfile(base_arg):
                targets.append((base_arg, parent_dir))
            elif os.path.isdir(base_arg):
                for root, _, files in os.walk(base_arg):
                    for fname in files:
                        targets.append((os.path.join(root, fname), parent_dir))
        else:
            if not os.path.isdir(base_arg):
                continue
            for name in os.listdir(base_arg):
                item_path = os.path.join(base_arg, name)
                if os.path.isfile(item_path):
                    targets.append((item_path, os.path.abspath(base_arg)))

        for f, folder in targets:
            if not os.path.exists(f) or is_ignored(f) or os.path.abspath(f) == folder:
                continue
                
            dest_cat, is_whitelisted = get_category_for_path(f, presets, folder)
            
            if not is_items and is_whitelisted:
                continue

            dest_dir = os.path.join(folder, dest_cat)
            
            # Prevent moving a folder into its own subfolder
            if os.path.isdir(f) and os.path.abspath(dest_dir).startswith(os.path.abspath(f) + os.sep):
                continue

            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
                if dest_dir not in created:
                    created.add(dest_dir)
                    last["created_dirs"].append(os.path.abspath(dest_dir))
                    
            dest = unique_dest(dest_dir, os.path.basename(f))
            try:
                safe_move(f, dest)
                last["moves"].append([os.path.abspath(f), os.path.abspath(dest)])
            except Exception:
                pass

    if last["moves"] or last["created_dirs"]:
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
def action_by_source(paths: List[str], is_items: bool) -> int:
    psl = PublicSuffixList(appdata_file("public_suffix_list.dat"))
    last = {"moves": [], "created_dirs": []}
    created = set()
    results = []
    
    for base_arg in paths:
        if is_blacklisted(base_arg, is_items):
            continue
            
        targets = []
        if is_items:
            parent_dir = os.path.dirname(os.path.abspath(base_arg))
            if os.path.isfile(base_arg):
                targets.append((base_arg, parent_dir))
            elif os.path.isdir(base_arg):
                for root, _, files in os.walk(base_arg):
                    for fname in files:
                        targets.append((os.path.join(root, fname), parent_dir))
        else:
            if not os.path.isdir(base_arg):
                continue
            for name in os.listdir(base_arg):
                item_path = os.path.join(base_arg, name)
                if os.path.isfile(item_path):
                    targets.append((item_path, os.path.abspath(base_arg)))
                
        # By Source only operates on files since folders don't have Zone.Identifier downloads natively
        files = [f for f, _ in targets if os.path.isfile(f) and not is_ignored(f)]
        folder_map = {f: folder for f, folder in targets}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        # Use map instead of submitting all futures at once to save memory
        valid_files = [f for f in files if not is_ignored(f)]
        for f, domain in ex.map(lambda f: _parse_ads_domain_simple(f, psl), valid_files):
            try:
                results.append((f, domain))
            except Exception:
                continue

    for f, domain in results:
        try:
            folder = folder_map[f]
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

    if last["moves"] or last["created_dirs"]:
        push_undo_action(last)
    return 0

# ---------------- Action: Category (GUI + CLI) ----------------
def action_category_cli(paths: List[str], category: str, is_items: bool) -> int:
    presets = load_presets_merge()
    last = {"moves": [], "created_dirs": []}
    created = set()

    for base_arg in paths:
        if is_blacklisted(base_arg, is_items):
            continue
            
        targets = []
        if is_items:
            parent_dir = os.path.dirname(os.path.abspath(base_arg))
            if os.path.isfile(base_arg):
                targets.append((base_arg, parent_dir))
            elif os.path.isdir(base_arg):
                for root, _, files in os.walk(base_arg):
                    for fname in files:
                        targets.append((os.path.join(root, fname), parent_dir))
        else:
            if not os.path.isdir(base_arg):
                continue
            for name in os.listdir(base_arg):
                item_path = os.path.join(base_arg, name)
                if os.path.isfile(item_path):
                    targets.append((item_path, os.path.abspath(base_arg)))

        for f, folder in targets:
            if not os.path.exists(f) or is_ignored(f) or os.path.abspath(f) == folder:
                continue
            
            dest_cat, is_whitelisted = get_category_for_path(f, presets, folder)
            
            if not is_items and is_whitelisted:
                continue
            
            if dest_cat == category:
                dest_dir = os.path.join(folder, category)
                
                # Prevent moving folder into its own subfolder
                if os.path.isdir(f) and os.path.abspath(dest_dir).startswith(os.path.abspath(f) + os.sep):
                    continue
                    
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir, exist_ok=True)
                    if dest_dir not in created:
                        created.add(dest_dir)
                        last["created_dirs"].append(os.path.abspath(dest_dir))
                dest = unique_dest(dest_dir, os.path.basename(f))
                try:
                    safe_move(f, dest)
                    last["moves"].append([os.path.abspath(f), os.path.abspath(dest)])
                except Exception:
                    pass

    if last["moves"] or last["created_dirs"]:
        push_undo_action(last)
    return 0

def action_category_gui(paths: List[str], is_items: bool) -> int:
    presets = load_presets_merge()
    cats = sorted(set(presets.values()) | {"Images", "Videos", "Audio", "Other Files"})
    # lightweight GUI selection if CustomTkinter available
    if CTK_AVAILABLE:
        root = ctk.CTk(); root.title("Organize by Category"); root.geometry("420x480")
        var = ctk.StringVar(value=cats[0])
        frame = ctk.CTkFrame(root); frame.pack(fill="both", expand=True, padx=12, pady=12)
        ctk.CTkLabel(frame, text=f"Organize into Category:", anchor="w").pack(anchor="w")
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
    return action_category_cli(paths, chosen, is_items)

# ---------------- Action: File Puller ----------------
def action_file_puller(paths: List[str], mode: str, is_items: bool) -> int:
    last = {"moves": [], "created_dirs": []}

    targets = []
    if is_items:
        targets = [p for p in paths if os.path.isdir(p) and not is_blacklisted(p, is_items)]
    else:
        targets = [p for p in paths if os.path.isdir(p) and not is_blacklisted(p, is_items)]

    for p in targets:
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
def action_delete_empty(paths: List[str], is_items: bool) -> int:
    targets = [os.path.abspath(p) for p in paths if os.path.isdir(p) and not is_blacklisted(p, is_items)]
    if not targets:
        return 1

    for folder in targets:
        while True:
            deleted_any = False

            for root, dirs, files in os.walk(folder, topdown=False):
                # Only prevent deletion of the root directory if we executed on its background 
                if not is_items and root == folder:
                    continue

                if not dirs and not files:
                    try:
                        if SEND2TRASH:
                            send2trash(root)   # Move to Recycle Bin
                        else:
                            os.rmdir(root)     # Safe native fallback, only works if actually empty
                        deleted_any = True
                    except Exception:
                        pass # Locked / permission denied → skip

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
        print("Usage: organizer.exe <action> [--items/--background] <path1> <path2> ...")
        return 1

    action = argv[1].lower()
    
    is_items = "--items" in argv
    is_background = "--background" in argv
    
    # default to items if they passed explicit paths, unless --background explicitly requested
    if is_items:
        mode_is_items = True
    elif is_background:
        mode_is_items = False
    else:
        # Default behavior: if they pass a single directory, usually it's background for backwards compatibility
        # If they pass multiple files, it's items.
        mode_is_items = len(argv) > 3 or (len(argv) > 2 and os.path.isfile(argv[2]))
        
    args: List[str] = [a for a in argv[2:] if a not in ("--items", "--background")]

    try:
        if action == "type":
            return action_by_type(args, is_items=mode_is_items) if args else 1
        elif action == "source":
            return action_by_source(args, is_items=mode_is_items) if args else 1
        elif action == "category":
            return action_category_gui(args, is_items=mode_is_items) if args else 1
        elif action == "pull":
            return action_file_puller(args, mode="all", is_items=mode_is_items)
        elif action == "pull_here":
            return action_file_puller(args, mode="here", is_items=mode_is_items)
        elif action == "pull_all":
            return action_file_puller(args, mode="all", is_items=mode_is_items)
        elif action == "pull_above":
            return action_file_puller(args, mode="above", is_items=mode_is_items)
        elif action == "delete_empty":
            return action_delete_empty(args, is_items=mode_is_items) if args else 1
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
