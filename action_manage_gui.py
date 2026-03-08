#!/usr/bin/env python3
from __future__ import annotations
import os, json, re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from typing import Dict, List, Tuple

APPDATA_SUBDIR = "File Organizer"

# ------------------ Helpers ------------------
def get_appdata_dir():
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APPDATA_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path

def appdata_file(name):
    return os.path.join(get_appdata_dir(), name)

def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

# ------------------ Main UI ------------------
class ManageSpreadsheet(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("File Organizer - Manage Presets")
        self.geometry("950x700")
        self.minsize(950, 700)

        self.default_path = appdata_file("default_presets.json")
        self.user_path = appdata_file("user_presets.json")

        raw = read_json(self.user_path)
        self.cat_to_exts: Dict[str, List[str]] = {}
        
        for k, v in raw.items():
            ext = k.lstrip(".").lower()
            cats = [c.strip() for c in v.split("|")] if isinstance(v, str) else v
            if not isinstance(cats, list): cats = [cats]
            for cat in cats:
                if cat not in self.cat_to_exts:
                    self.cat_to_exts[cat] = []
                if ext not in self.cat_to_exts[cat]:
                    self.cat_to_exts[cat].append(ext)

        self.sort_col = "c"
        self.sort_rev = False

        self._setup_styles()
        self._build_layout()
        self._load_rows()

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Delete>", lambda e: self._on_delete())

    # ------------------ Styles ------------------
    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("default")
        except Exception:
            pass

        style.configure(
            "Treeview",
            background="#2b2b2b",
            foreground="#e8e8e8",
            fieldbackground="#2b2b2b",
            rowheight=28,
            borderwidth=1,
            relief="solid"
        )
        style.map("Treeview", background=[("selected", "#1f6feb")])

        style.configure(
            "Vertical.TScrollbar",
            background="#353535",
            troughcolor="#1e1e1e",
            arrowcolor="#f0f0f0",
            arrowsize=12
        )

        style.configure(
            "Treeview.Heading",
            background="#424b54",
            foreground="#ffffff",
            borderwidth=1,
            relief="solid",
            font=("Segoe UI", 10, "bold"),
            padding=(6, 3)
        )

    # ------------------ Layout ------------------
    def _build_layout(self):
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=6)

        tk.Label(top, text="Search:",font=("Segoe UI", 12, "bold"), fg="#ddd", bg="#2b2b2b").pack(side="left", padx=6)
        self.search_var = tk.StringVar()
        ctk.CTkEntry(top, textvariable=self.search_var).pack(
            side="left", fill="x", expand=True
        )
        self.search_var.trace_add("write", lambda *_: self._search())

        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=10)

        table = tk.Frame(main, bg="#2b2b2b", bd=0, highlightthickness=0)
        table.pack(side="left", fill="both", expand=True)

        self.tree = ttk.Treeview(
            table,
            columns=("i", "e", "c"),
            show="headings",
            selectmode="browse"
        )

        self.tree.heading("i", text="Index")
        self.tree.heading("e", text="Extensions")
        self.tree.heading("c", text="Category")
        self.tree.column("i", width=50, anchor="center", minwidth=50, stretch=False)
        self.tree.column("e", width=580, minwidth=300, stretch=True)
        self.tree.column("c", width=180, minwidth=200, stretch=True)

        self.tree.tag_configure("odd", background="#353535")
        self.tree.tag_configure("even", background="#2f2f2f")

        vs = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")

        table.grid_rowconfigure(0, weight=1)
        self.tree.grid_columnconfigure(0, weight=1)

        # Bind headings for sorting
        self.tree.heading("e", text="Extensions", command=lambda: self._sort_column("e", False))
        self.tree.heading("c", text="Category", command=lambda: self._sort_column("c", False))

        right = ctk.CTkFrame(main, width=75)
        right.pack(side="right", fill="y", padx=6)
        right.pack_propagate(False)

        ctk.CTkButton(right, text="Import", command=self._on_import).pack(pady=(0, 6))
        ctk.CTkButton(right, text="Export", command=self._on_export).pack(pady=(0, 6))
        ctk.CTkButton(right, text="Delete", fg_color="#c0392b",

                      command=self._on_delete).pack(pady=(0, 6))
        ctk.CTkButton(right, text="Clear All", fg_color="#b88328", command=self._on_delete_all).pack(pady=(0, 6))
        ctk.CTkButton(right, text="Save", fg_color="#27ae60",
                      command=self._on_save).pack(pady=(40, 6))
        ctk.CTkButton(right, text="Close", command=self.destroy).pack(pady=(0, 6))
        ctk.CTkButton(right, text="Reset", fg_color="#424b54",
                      command=self._on_reset).pack(side="bottom", pady=6)

    # ------------------ Load Rows ------------------
    def _load_rows(self):
        self.tree.delete(*self.tree.get_children())
        
        wl_cats = {c: e for c, e in self.cat_to_exts.items() if c.lower().startswith("whitelist.")}
        norm_cats = {c: e for c, e in self.cat_to_exts.items() if not c.lower().startswith("whitelist.")}
        
        def sort_dict(d):
            if self.sort_col == "e":
                return sorted(d.items(), key=lambda item: item[1][0] if item[1] else "", reverse=self.sort_rev)
            else:
                return sorted(d.items(), key=lambda item: item[0].lower(), reverse=self.sort_rev)
                
        cats_to_render = sort_dict(wl_cats) + sort_dict(norm_cats)
        
        idx = 1
        for cat, exts in cats_to_render:
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end", values=(idx, ", ".join(exts), cat), tags=(tag,))
            idx += 1

        tag = "even" if idx % 2 == 0 else "odd"
        self.tree.insert("", "end", values=(idx, "", ""), tags=(tag,))

    # ------------------ Search ------------------
    def _search(self):
        q = self.search_var.get().strip().lower()
        if not q:
            self._load_rows()
            return
            
        self.tree.delete(*self.tree.get_children())
        
        matched_cats = {}
        for cat, exts in self.cat_to_exts.items():
            matching_exts = [e for e in exts if q in e]
            if q in cat.lower() or matching_exts:
                matched_cats[cat] = exts

        wl_cats = {c: e for c, e in matched_cats.items() if c.lower().startswith("whitelist.")}
        norm_cats = {c: e for c, e in matched_cats.items() if not c.lower().startswith("whitelist.")}
        
        def sort_dict(d):
            if self.sort_col == "e":
                return sorted(d.items(), key=lambda item: item[1][0] if item[1] else "", reverse=self.sort_rev)
            else:
                return sorted(d.items(), key=lambda item: item[0].lower(), reverse=self.sort_rev)
                
        cats_to_render = sort_dict(wl_cats) + sort_dict(norm_cats)
        
        idx = 1
        for cat, exts in cats_to_render:
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end", values=(idx, ", ".join(exts), cat), tags=(tag,))
            idx += 1
            
        tag = "even" if idx % 2 == 0 else "odd"
        self.tree.insert("", "end", values=(idx, "", ""), tags=(tag,))

        

    # ------------------ Double Click Edit ------------------
    def _on_double_click(self, event):
        if self.tree.identify("region", event.x, event.y) != "cell":
            return

        rowid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if col == "#1":
            return

        key = "e" if col == "#2" else "c"
        old_cat = self.tree.set(rowid, "c")
        old_val = self.tree.set(rowid, key)

        x, y, w, h = self.tree.bbox(rowid, col)
        entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, old_val)
        entry.focus_set()

        committed = False


        def commit():
            nonlocal committed

            # prevent double execution
            if committed:
                return
            committed = True

            # row may no longer exist (race condition protection)
            if not self.tree.exists(rowid):
                if entry.winfo_exists():
                    entry.destroy()
                return

            raw = entry.get().strip()

            # ---------- Silent sanitation ----------
            if key == "e":
                cleaned = []
                for part in raw.split(","):
                    safe = re.sub(r"[^a-zA-Z0-9]", "", part)
                    if safe:
                        cleaned.append(safe.lower())
                new_val = ", ".join(cleaned)
            else:
                new_val = re.sub(r'[\\/:*?"<>|]', "", raw).strip().title()

            # ---------- Update UI ----------
            self.tree.set(rowid, key, new_val)
            entry.destroy()

            exts = self.tree.set(rowid, "e").strip()
            cat = self.tree.set(rowid, "c").strip()

            is_new_row = rowid == self.tree.get_children()[-1]

            if not exts or not cat:
                # Revert visually if left blank on an existing row
                if not is_new_row:
                    self.tree.set(rowid, key, old_val)
                return

            parts = [p for p in (x.strip() for x in exts.split(",")) if p]

            # ---------- Update data model ----------
            if not cat.lower().startswith("whitelist."):
                for p in parts:
                    for exist_cat, exist_exts in self.cat_to_exts.items():
                        if exist_cat != old_cat and not exist_cat.lower().startswith("whitelist.") and p in exist_exts:
                            messagebox.showerror("Conflict", f"Extension '{p}' is already inside '{exist_cat}'.\n\nExtensions can only belong to one normal category.")
                            self.tree.set(rowid, key, old_val)
                            return
                            
            if not is_new_row and old_cat in self.cat_to_exts:
                self.cat_to_exts.pop(old_cat, None)
                
            if cat not in self.cat_to_exts:
                self.cat_to_exts[cat] = []
                
            for p in parts:
                if p not in self.cat_to_exts[cat]:
                    self.cat_to_exts[cat].append(p)
                    
            if not self.cat_to_exts[cat]:
                self.cat_to_exts.pop(cat, None)
                
            self._load_rows()

            # ---------- Ensure trailing empty row ----------
            children = self.tree.get_children()
            if children:
                last = children[-1]
                if self.tree.exists(last):
                    if self.tree.set(last, "e").strip() or self.tree.set(last, "c").strip():
                        idx = len(children) + 1
                        tag = "even" if idx % 2 == 0 else "odd"
                        self.tree.insert("", "end", values=(idx, "", ""), tags=(tag,))

        def finalize(_=None):
            if entry.winfo_exists():
                commit()

        entry.bind("<Return>", finalize)
        entry.bind("<Escape>", lambda e: entry.destroy())
        self.tree.bind("<Button-1>", finalize, add="+")


        # ---------- Ensure trailing empty row ----------
        children = self.tree.get_children()
        last = children[-1]
        last_ext = self.tree.set(last, "e").strip()
        last_cat = self.tree.set(last, "c").strip()

        if last_ext or last_cat:
            idx = len(children) + 1
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end", values=(idx, "", ""), tags=(tag,))


    # ------------------ Buttons ------------------
    def _on_delete(self):
        sel = self.tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Confirm Delete", "Delete selected preset?"):
            return
        cat = self.tree.set(sel[0], "c")
        if cat in self.cat_to_exts:
            self.cat_to_exts.pop(cat)
        self._load_rows()

    def _on_delete_all(self):
        if not self.tree.get_children():
            return

        if not messagebox.askyesno(
            "Delete All Presets",
            "This will remove ALL presets from the list.\n\nAre you sure?"
        ):
            return

        # clear data model
        self.cat_to_exts.clear()

        # clear UI
        self.tree.delete(*self.tree.get_children())

        # add single empty row
        self.tree.insert(
            "",
            "end",
            values=(1, "", ""),
            tags=("odd",)
        )


    def _on_reset(self):
        if not messagebox.askyesno("Reset Presets", "Reset to defaults?"):
            return
        raw = read_json(self.default_path)
        self.cat_to_exts.clear()
        for k, v in raw.items():
            ext = k.lstrip(".").lower()
            cats = [c.strip() for c in v.split("|")] if isinstance(v, str) else v
            for cat in cats:
                if ext not in self.cat_to_exts.setdefault(cat, []):
                    self.cat_to_exts[cat].append(ext)
        self.search_var.set("")
        self._load_rows()

    def _on_import(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        raw = read_json(path)
        for k, v in raw.items():
            ext = k.lstrip(".").lower()
            cats = [c.strip() for c in v.split("|")] if isinstance(v, str) else v
            for cat in cats:
                if ext not in self.cat_to_exts.setdefault(cat, []):
                    self.cat_to_exts[cat].append(ext)
        self._load_rows()

    def _get_export_dict(self):
        ext_to_cats = {}
        for cat, exts in self.cat_to_exts.items():
            for ext in exts:
                ext_to_cats.setdefault(ext, []).append(cat)
                
        out = {}
        for ext, cats in ext_to_cats.items():
            out[f".{ext}"] = "|".join(cats)
        return out

    def _on_export(self):
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if not path:
            return
        write_json(path, self._get_export_dict())

    def _on_save(self):
        if not messagebox.askyesno("Save Presets", "Save current presets?"):
            return
        write_json(self.user_path, self._get_export_dict())
        messagebox.showinfo("Saved", "Presets saved successfully.")

    def _sort_column(self, col, reverse):
        self.sort_col = col
        self.sort_rev = reverse
        self._load_rows()
        self.tree.heading(col, command=lambda: self._sort_column(col, not reverse))

# ------------------ Run ------------------
def action_manage_gui():
    app = ManageSpreadsheet()
    app.mainloop()

if __name__ == "__main__":
    action_manage_gui()
