#!/usr/bin/env python3
from __future__ import annotations
import os
import sys
import json
import shutil
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from typing import Dict, List, Tuple

APPDATA_SUBDIR = "File Organizer"

# ------------------ Helpers: AppData, JSON ------------------
def get_appdata_dir() -> str:
    appdata = os.getenv("APPDATA") or os.path.expanduser("~")
    path = os.path.join(appdata, APPDATA_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path

def appdata_file(name: str) -> str:
    return os.path.join(get_appdata_dir(), name)

def get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def ensure_defaults_in_appdata():
    base = get_base_dir()
    appdata = get_appdata_dir()
    for name in ("default_presets.json", "user_presets.json"):
        src = os.path.join(base, name)
        dst = os.path.join(appdata, name)
        try:
            if os.path.exists(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)
        except Exception:
            pass
    dp = appdata_file("default_presets.json")
    up = appdata_file("user_presets.json")
    if not os.path.exists(dp):
        fallback = {
            ".jpg": "Images",
            ".jpeg": "Images",
            ".png": "Images",
            ".mp4": "Videos",
            ".mp3": "Audio",
            ".zip": "Archives",
            ".pdf": "Documents",
            ".txt": "Documents"
        }
        with open(dp, "w", encoding="utf-8") as f:
            json.dump(fallback, f, indent=2, ensure_ascii=False)
    if not os.path.exists(up):
        with open(up, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2, ensure_ascii=False)

def read_json(path: str) -> Dict[str, str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def write_json(path: str, data: Dict[str, str]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

# ------------------ Main UI Class ------------------
class ManageSpreadsheet(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Manage File Types - Spreadsheet Test UI")
        self.geometry("980x680")
        self.minsize(900, 600)

        ensure_defaults_in_appdata()
        self.default_path = appdata_file("default_presets.json")
        self.user_path = appdata_file("user_presets.json")

        self.defaults = read_json(self.default_path) or {}   # kept only for reset use
        self.users = read_json(self.user_path) or {}         # the ONLY data used
        self.combined = dict(self.users)                     # load only user presets

        # used for search & stable reloading
        self._all_rows_cache: List[Tuple[str, str]] = []

        # editing overlay widget
        self._entry_editor: tk.Entry | None = None
        self._editing_item = None  # item id being edited
        self._editing_col = None   # 'exts' or 'cat'

        # drag-reorder state
        self._dragging_item = None

        self._setup_styles()
        self._build_layout()
        self._load_rows()

        # keyboard bindings for navigation and Ctrl+A select-all
        self.tree.bind("<Up>", self._on_arrow_up)
        self.tree.bind("<Down>", self._on_arrow_down)
        self.tree.bind("<Left>", self._on_arrow_left)
        self.tree.bind("<Right>", self._on_arrow_right)
        self.tree.bind("<Return>", self._on_enter_key)
        self.bind_all("<Control-a>", self._on_ctrl_a)

        # bind header double-click for auto-resize (use Button-1 double-click)
        self.tree.bind("<Button-1>", self._on_tree_click, add="+")
        self.tree.bind("<Double-1>", self._on_tree_double_click, add="+")

        # Drag & drop bindings
        self.tree.bind("<ButtonPress-1>", self._on_button_press, add="+")
        self.tree.bind("<B1-Motion>", self._on_b1_motion, add="+")
        self.tree.bind("<ButtonRelease-1>", self._on_button_release, add="+")

    # ------------------ merge defaults & users into combined map ------------------
    def _build_combined(self) -> Dict[str, str]:
        merged = {}
        for k, v in self.defaults.items():
            merged[k.lstrip(".").lower()] = v
        for k, v in self.users.items():
            merged[k.lstrip(".").lower()] = v
        return merged

    # ------------------ ttk / treeview style (dark) ------------------
    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview",
                        background="#2b2b2b",
                        foreground="#e8e8e8",
                        fieldbackground="#2b2b2b",
                        rowheight=26,
                        borderwidth=0)
        style.map("Treeview", background=[("selected", "#1f6feb")], foreground=[("selected", "white")])
        style.configure("Treeview.Heading", background="#2d2d2d", foreground="#ffffff", relief="flat")
        style.configure("Vertical.TScrollbar", troughcolor="#202020", background="#3a3a3a", width=8)
        style.configure("Horizontal.TScrollbar", troughcolor="#202020", background="#3a3a3a", width=8)

    # ------------------ Build window layout ------------------
    def _build_layout(self):
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=(10, 6))

        tk.Label(top, text="Search:", bg="#1f1f1f", fg="#ddd").pack(side="left", padx=(6, 6))
        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(top, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.search_var.trace_add("write", lambda *_: self._search())

        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        # left: table
        table_container = tk.Frame(main, bg="#2b2b2b")
        table_container.pack(side="left", fill="both", expand=True)

        self.tree = ttk.Treeview(table_container, columns=("index", "exts", "cat"), show="headings", selectmode="browse")
        self.tree.heading("index", text="Index")
        self.tree.heading("exts", text="Extensions")
        self.tree.heading("cat", text="Category")
        self.tree.column("index", width=60, anchor="center", stretch=False)
        self.tree.column("exts", width=480, anchor="w")
        self.tree.column("cat", width=280, anchor="w")

        # alternating rows
        self.tree.tag_configure("odd", background="#353535")
        self.tree.tag_configure("even", background="#2f2f2f")

        vs = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview, style="Vertical.TScrollbar")
        hs = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview, style="Horizontal.TScrollbar")
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns", padx=(2,0))
        hs.grid(row=1, column=0, sticky="ew", pady=(2,0))
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        # double-click editing
        self.tree.bind("<Double-1>", self._on_double_click, add="+")

        # right panel buttons
        right = ctk.CTkFrame(main, width=160)
        right.pack(side="right", fill="y", padx=(10, 0))

        self.btn_import = ctk.CTkButton(right, text="Import", width=140, command=self._on_import)
        self.btn_export = ctk.CTkButton(right, text="Export", width=140, command=self._on_export)
        self.btn_delete = ctk.CTkButton(right, text="Delete Row", width=140, fg_color="#c0392b",
                                        hover_color="#e74c3c", command=self._on_delete)

        self.btn_import.pack(pady=(12, 6))
        self.btn_export.pack(pady=(0, 6))
        self.btn_delete.pack(pady=(18, 10))

        self.btn_save = ctk.CTkButton(right, text="Save and Close", fg_color="#27ae60", width=140, command=self._on_save_and_close)
        self.btn_close = ctk.CTkButton(right, text="Close", fg_color="#2980b9", width=140, command=self.destroy)
        self.btn_reset = ctk.CTkButton(right, text="Reset", fg_color="#f39c12", width=140, command=self._on_reset_confirm)

        self.btn_save.pack(pady=(40, 6))
        self.btn_close.pack(pady=6)
        self.btn_reset.pack(pady=6)

    # ------------------ Load rows into tree & cache for search ------------------
    def _load_rows(self):
        # clear
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        # group mapping by category to display ext lists per row
        by_cat = {}
        for ext, cat in sorted(self.combined.items(), key=lambda x: (x[1].lower(), x[0])):
            by_cat.setdefault(cat, []).append(ext)

        self._all_rows_cache = []
        idx = 1
        for cat, ext_list in by_cat.items():
            exts_csv = ", ".join(ext_list)
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end", values=(idx, exts_csv, cat), tags=(tag,))
            self._all_rows_cache.append((exts_csv, cat))
            idx += 1

        # trailing blank row (not included in cache)
        tag = "even" if idx % 2 == 0 else "odd"
        self.tree.insert("", "end", values=(idx, "", ""), tags=(tag,))

    def _refresh_indexes_and_trailing(self):
        children = list(self.tree.get_children())
        for i, iid in enumerate(children, start=1):
            self.tree.set(iid, "index", str(i))
            self.tree.item(iid, tags=("even",) if i % 2 == 0 else ("odd",))
        # ensure trailing blank
        if children:
            last = children[-1]
            if self.tree.set(last, "exts").strip() or self.tree.set(last, "cat").strip():
                idx = len(children) + 1
                tag = "even" if idx % 2 == 0 else "odd"
                self.tree.insert("", "end", values=(idx, "", ""), tags=(tag,))

    # ------------------ Search (fixed: filter from cache + rebuild) ------------------
    def _search(self):
        q = self.search_var.get().strip().lower()
        if not q:
            # restore full
            self._load_rows()
            return
        # filtered from cached full rows
        filtered = []
        for exts, cat in self._all_rows_cache:
            if q in exts.lower() or q in cat.lower():
                filtered.append((exts, cat))
        # rebuild tree with filtered rows (plus trailing blank)
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        idx = 1
        for exts, cat in filtered:
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end", values=(idx, exts, cat), tags=(tag,))
            idx += 1
        tag = "even" if idx % 2 == 0 else "odd"
        self.tree.insert("", "end", values=(idx, "", ""), tags=(tag,))

    # ------------------ Inline editing (double-click / Enter) ------------------
    def _on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        rowid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)  # "#1","#2","#3"
        if not rowid or not col:
            return
        if col == "#1":
            return  # don't edit index

        # compute bbox
        x, y, width, height = self.tree.bbox(rowid, col)
        curval = self.tree.set(rowid, "exts" if col == "#2" else "cat")

        # create entry overlay
        if self._entry_editor:
            self._entry_editor.destroy()
            self._entry_editor = None

        entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, curval)
        entry.focus_set()
        entry.selection_range(0, 'end')

        # store editing state
        self._entry_editor = entry
        self._editing_item = rowid
        self._editing_col = "exts" if col == "#2" else "cat"

        def commit(event=None):
            val = entry.get().strip()
            if self._editing_col == "exts":
                parts = [p.strip().lstrip(".").lower() for p in val.split(",") if p.strip()]
                new = ", ".join(parts)
                self.tree.set(rowid, "exts", new)
            else:
                new = re.sub(r"[^A-Za-z0-9 ]+", "", val).strip().title()
                self.tree.set(rowid, "cat", new)
            entry.destroy()
            self._entry_editor = None
            # After commit, refresh indexes/trailing and update cache & combined
            self._refresh_indexes_and_trailing()
            self._sync_cache_from_tree()

        def cancel(event=None):
            if self._entry_editor:
                self._entry_editor.destroy()
                self._entry_editor = None

        entry.bind("<Return>", commit)
        entry.bind("<Escape>", cancel)
        entry.bind("<FocusOut>", commit)

    # commit any visible editor
    def _commit_editor_if_any(self):
        if self._entry_editor and self._editing_item and self._editing_col:
            try:
                val = self._entry_editor.get().strip()
                if self._editing_col == "exts":
                    parts = [p.strip().lstrip(".").lower() for p in val.split(",") if p.strip()]
                    new = ", ".join(parts)
                    self.tree.set(self._editing_item, "exts", new)
                else:
                    new = re.sub(r"[^A-Za-z0-9 ]+", "", val).strip().title()
                    self.tree.set(self._editing_item, "cat", new)
            except Exception:
                pass
            try:
                self._entry_editor.destroy()
            except Exception:
                pass
            self._entry_editor = None
            self._editing_item = None
            self._editing_col = None
            self._refresh_indexes_and_trailing()
            self._sync_cache_from_tree()

    # ------------------ Sync cache (order sensitive) ------------------
    def _sync_cache_from_tree(self):
        # rebuild _all_rows_cache from tree rows (excluding trailing blank)
        rows = []
        children = list(self.tree.get_children())
        for iid in children:
            exts = self.tree.set(iid, "exts").strip()
            cat = self.tree.set(iid, "cat").strip()
            if not exts and not cat:
                continue
            rows.append((exts, cat))
        self._all_rows_cache = rows
        # also rebuild combined mapping (used for saving/export/import)
        new_combined = {}
        for exts, cat in rows:
            parts = [p.strip().lstrip(".").lower() for p in exts.split(",") if p.strip()]
            for p in parts:
                new_combined[p] = cat
        self.combined = new_combined

    # ------------------ Keyboard navigation ------------------
    def _select_item_by_index(self, idx: int):
        children = list(self.tree.get_children())
        if not children:
            return
        if idx < 0:
            idx = 0
        if idx >= len(children):
            idx = len(children) - 1
        iid = children[idx]
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self.tree.see(iid)

    def _on_arrow_up(self, event):
        sel = self.tree.selection()
        children = list(self.tree.get_children())
        if not children:
            return "break"
        if not sel:
            self._select_item_by_index(0)
            return "break"
        idx = children.index(sel[0])
        self._select_item_by_index(max(0, idx - 1))
        return "break"

    def _on_arrow_down(self, event):
        sel = self.tree.selection()
        children = list(self.tree.get_children())
        if not children:
            return "break"
        if not sel:
            self._select_item_by_index(0)
            return "break"
        idx = children.index(sel[0])
        self._select_item_by_index(min(len(children) - 1, idx + 1))
        return "break"

    def _on_arrow_left(self, event):
        # move focus to previous column (not implemented as separate focus; start edit on previous col)
        sel = self.tree.selection()
        if not sel:
            return "break"
        iid = sel[0]
        # start edit on exts column
        x, y, w, h = self.tree.bbox(iid, "#2")
        self._on_double_click(tk.Event(x=x + 2, y=y + 2))
        return "break"

    def _on_arrow_right(self, event):
        sel = self.tree.selection()
        if not sel:
            return "break"
        iid = sel[0]
        # start edit on category column
        x, y, w, h = self.tree.bbox(iid, "#3")
        self._on_double_click(tk.Event(x=x + 2, y=y + 2))
        return "break"

    def _on_enter_key(self, event):
        sel = self.tree.selection()
        if not sel:
            return "break"
        iid = sel[0]
        # open editor in first editable column (extensions)
        bbox = self.tree.bbox(iid, "#2")
        if bbox:
            event.x, event.y = bbox[0] + 2, bbox[1] + 2
            self._on_double_click(event)
        return "break"

    # ------------------ Ctrl+A select all (skip trailing blank) ------------------
    def _on_ctrl_a(self, event=None):
        children = list(self.tree.get_children())
        if not children:
            return "break"
        # exclude trailing blank row if empty
        last = children[-1]
        if not (self.tree.set(last, "exts").strip() or self.tree.set(last, "cat").strip()):
            sel = children[:-1]
        else:
            sel = children
        try:
            self.tree.selection_set(sel)
            if sel:
                self.tree.focus(sel[0])
                self.tree.see(sel[0])
        except Exception:
            pass
        return "break"

    # ------------------ Header click/double-click handling (auto-resize) ------------------
    def _on_tree_click(self, event):
        # single-click header: allow standard behavior; we intercept in double-click
        pass

    def _on_tree_double_click(self, event):
        # If double-click was on heading, auto-size that column
        region = self.tree.identify("region", event.x, event.y)
        if region != "heading":
            return
        col = self.tree.identify_column(event.x)
        if not col:
            return
        self._autosize_column(col)

    def _autosize_column(self, col_id: str):
        # find widest content in column (including header)
        col = {"#1": "index", "#2": "exts", "#3": "cat"}[col_id]
        max_w = 0
        # measure header
        hdr = self.tree.heading(col, option="text")
        font = tk.font.nametofont("TkDefaultFont")
        tmp_w = font.measure(hdr) + 20
        if tmp_w > max_w:
            max_w = tmp_w
        # measure cells
        for iid in self.tree.get_children():
            text = self.tree.set(iid, col)
            w = font.measure(text) + 20
            if w > max_w:
                max_w = w
        # set column width
        self.tree.column(col, width=max_w)

    # ------------------ Drag & drop reorder ------------------
    def _on_button_press(self, event):
        # remember start item
        iid = self.tree.identify_row(event.y)
        self._dragging_item = iid if iid else None

    def _on_b1_motion(self, event):
        if not self._dragging_item:
            return
        # give visual feedback (optional)
        # scroll if near edge
        height = self.tree.winfo_height()
        if event.y < 20:
            self.tree.yview_scroll(-1, "units")
        elif event.y > height - 20:
            self.tree.yview_scroll(1, "units")

    def _on_button_release(self, event):
        if not self._dragging_item:
            return
        target = self.tree.identify_row(event.y)
        src = self._dragging_item
        self._dragging_item = None
        if not target or target == src:
            return
        # reorder: move src before target (or after depending on y)
        children = list(self.tree.get_children())
        src_idx = children.index(src)
        tgt_idx = children.index(target)
        # decide insertion index based on y-position midpoint
        y_mid = self.tree.bbox(target)[1] + (self.tree.bbox(target)[3] // 2)
        insert_after = False
        if event.y > y_mid:
            insert_after = True
        try:
            # detach and reinsert at new pos
            vals = self.tree.item(src, "values")
            tags = self.tree.item(src, "tags")
            self.tree.delete(src)
            children = list(self.tree.get_children())
            if insert_after:
                # insert after target: position = index(target)+1
                pos = children.index(target) + 1 if target in children else len(children)
            else:
                pos = children.index(target) if target in children else len(children)
            # build list of values to insert at that position; tkinter tree doesn't have insert by index, but by iid reference
            if pos >= len(children):
                self.tree.insert("", "end", values=vals, tags=tags)
            else:
                self.tree.insert("", children[pos], values=vals, tags=tags)
        except Exception:
            pass
        # refresh indexes and update cache & combined
        self._refresh_indexes_and_trailing()
        self._sync_cache_from_tree()

    # ------------------ Import / Export / Delete / Reset / Save ------------------
    def _on_import(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        data = read_json(path)
        if not isinstance(data, dict):
            messagebox.showerror("Import", "Invalid JSON mapping.")
            return
        for k, v in data.items():
            if isinstance(k, str) and isinstance(v, str):
                self.combined[k.lstrip(".").lower()] = v
        self._load_rows()
        messagebox.showinfo("Import", "Import complete.")

    def _on_export(self):
        mapping = {}
        for iid in self.tree.get_children():
            exts = self.tree.set(iid, "exts").strip()
            cat = self.tree.set(iid, "cat").strip()
            if not exts or not cat:
                continue
            parts = [p.strip().lstrip(".").lower() for p in exts.split(",") if p.strip()]
            for p in parts:
                mapping[f".{p}"] = cat
        if not mapping:
            messagebox.showwarning("Export", "Nothing to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if not path:
            return
        write_json(path, mapping)
        messagebox.showinfo("Export", "Exported successfully.")

    def _on_delete(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Delete", "No row selected.")
            return
        iid = sel[0]
        ex = self.tree.set(iid, "exts").strip()
        cat = self.tree.set(iid, "cat").strip()
        children = list(self.tree.get_children())
        if iid == children[-1] and (ex == "" and cat == ""):
            messagebox.showwarning("Delete", "Cannot delete the final empty row.")
            return
        if not messagebox.askyesno("Delete Row", "Delete selected row?"):
            return
        try:
            self.tree.delete(iid)
        except Exception:
            pass
        self._refresh_indexes_and_trailing()
        self._sync_cache_from_tree()

    def _on_reset_confirm(self):
        if not messagebox.askyesno(
            "Reset to Factory Defaults",
            "This will restore from default presets.\nAll your custom presets will be replaced. Continue?"
        ):
            return

        try:
            # Load defaults
            defaults = read_json(self.default_path)

            # Write defaults into user presets
            write_json(self.user_path, defaults)

            # Reload internal data
            self.users = defaults
            self.combined = dict(defaults)

            # Reload UI
            self._load_rows()

            messagebox.showinfo("Reset", "Restored defaults into user presets.")
        except Exception as e:
            messagebox.showerror("Reset", f"Failed to restore defaults:\n{e}")


    def _on_save_and_close(self):
        # commit any active editor first
        self._commit_editor_if_any()
        mapping = {}
        for iid in self.tree.get_children():
            exts = self.tree.set(iid, "exts").strip()
            cat = self.tree.set(iid, "cat").strip()
            if not exts or not cat:
                continue
            parts = [p.strip().lstrip(".").lower() for p in exts.split(",") if p.strip()]
            for p in parts:
                mapping[f".{p}"] = cat
        try:
            write_json(self.user_path, mapping)
            messagebox.showinfo("Saved", f"Saved to {self.user_path}")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save: {e}")


# ------------------ Run ------------------
def action_manage_gui() -> int:
    app = ManageSpreadsheet()
    app.mainloop()
    return 0

if __name__ == "__main__":
    action_manage_gui()


