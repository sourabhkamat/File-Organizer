#!/usr/bin/env python3
from __future__ import annotations
import os, json, re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from typing import Dict

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
        self.combined: Dict[str, str] = {
            k.lstrip(".").lower(): v for k, v in raw.items()
        }

        # 🔑 SORT ONLY ONCE AT STARTUP
        self.combined = dict(
            sorted(self.combined.items(), key=lambda i: i[1].lower())
        )

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
        table.grid_columnconfigure(0, weight=1)

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
        grouped = {}
        for ext, cat in self.combined.items():
            grouped.setdefault(cat, []).append(ext)

        idx = 1
        for cat, exts in grouped.items():
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end",
                             values=(idx, ", ".join(exts), cat),
                             tags=(tag,))
            idx += 1

        tag = "even" if idx % 2 == 0 else "odd"
        self.tree.insert("", "end", values=(idx, "", ""), tags=(tag,))

    # ------------------ Search ------------------
    def _search(self):
        q = self.search_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())

        if not q:
            self._load_rows()
            return

        matched = {cat for ext, cat in self.combined.items()
                   if q in ext or q in cat.lower()}

        grouped = {}
        for ext, cat in self.combined.items():
            if cat in matched:
                grouped.setdefault(cat, []).append(ext)

        idx = 1
        for cat, exts in grouped.items():
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.insert("", "end",
                             values=(idx, ", ".join(exts), cat), tags=(tag,))
            idx += 1
        
        self.tree.insert("", "end", values=(idx, "", ""))

        

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

            if not exts or not cat:
                return

            parts = [p for p in (x.strip() for x in exts.split(",")) if p]

            is_new_row = rowid == self.tree.get_children()[-1]

            # ---------- Update data model ----------
            if is_new_row:
                for p in parts:
                    self.combined[p] = cat
            else:
                for k in list(self.combined):
                    if self.combined[k] == old_cat and k not in parts:
                        self.combined.pop(k)
                for p in parts:
                    self.combined[p] = cat

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
        exts = self.tree.set(sel[0], "e")
        for e in exts.split(","):
            self.combined.pop(e.strip(), None)
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
        self.combined.clear()

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
        self.combined = {k.lstrip(".").lower(): v for k, v in raw.items()}
        self.search_var.set("")
        self._load_rows()

    def _on_import(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        raw = read_json(path)
        for k, v in raw.items():
            self.combined[k.lstrip(".").lower()] = v
        self._load_rows()

    def _on_export(self):
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if not path:
            return
        write_json(path, {f".{k}": v for k, v in self.combined.items()})

    def _on_save(self):
        if not messagebox.askyesno("Save Presets", "Save current presets?"):
            return
        write_json(self.user_path, {f".{k}": v for k, v in self.combined.items()})
        messagebox.showinfo("Saved", "Presets saved successfully.")

# ------------------ Run ------------------
def action_manage_gui():
    app = ManageSpreadsheet()
    app.mainloop()

if __name__ == "__main__":
    action_manage_gui()
