from __future__ import annotations

import ctypes
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
import pyperclip
from PIL import Image, ImageTk

from core.detector import ProjectDetector
from core.exporter import Exporter
from core.scanner import ProjectScanner
from core.summarizer import ProjectSummarizer
from models.project_model import ProjectSnapshot


class SimpleTooltip:
    def __init__(self, widget, text: str, delay: int = 400) -> None:
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tw: tk.Toplevel | None = None
        self._id = None
        try:
            widget.bind("<Enter>", self._enter, add="+")
            widget.bind("<Leave>", self._leave, add="+")
            widget.bind("<ButtonPress>", self._leave, add="+")
        except Exception:
            pass

    def _enter(self, _e=None):
        self._cancel()
        self._id = self.widget.after(self.delay, self._show)

    def _leave(self, _e=None):
        self._cancel()
        if self.tw:
            try:
                self.tw.destroy()
            except Exception:
                pass
            self.tw = None

    def _cancel(self):
        if self._id:
            try:
                self.widget.after_cancel(self._id)
            except Exception:
                pass
            self._id = None

    def _show(self):
        if self.tw:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        try:
            self.tw.attributes("-topmost", True)
        except Exception:
            pass
        self.tw.geometry(f"+{x}+{y}")
        tk.Label(
            self.tw, text=self.text, justify="left",
            bg="#1e293b", fg="#f1f5f9", bd=0, padx=10, pady=5,
            font=("Segoe UI", 9),
        ).pack()


class PicaflorApp(ctk.CTk):
    CLR_OPEN = ("#3b82f6", "#2563eb")
    CLR_RELOAD = ("#6366f1", "#4f46e5")
    CLR_RUN = ("#22c55e", "#16a34a")
    CLR_COPY = ("#a855f7", "#9333ea")
    CLR_SAVE = ("#06b6d4", "#0891b2")
    CLR_THEME = ("#64748b", "#475569")

    CLR_EXCL = ("#f97316", "#ea580c")
    CLR_INCL = ("#22c55e", "#16a34a")
    CLR_NONE = ("#ef4444", "#dc2626")
    CLR_ALL = ("#3b82f6", "#2563eb")

    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.base_dir = Path(__file__).resolve().parents[1]
        self.snapshot: ProjectSnapshot | None = None

        self.scanner = ProjectScanner()
        self.detector = ProjectDetector()
        self.summarizer = ProjectSummarizer()
        self.exporter = Exporter()

        self._icon_ref = None
        self._tips: list[SimpleTooltip] = []

        self.theme_var = ctk.StringVar(value="dark")
        self.mode_var = ctk.StringVar(value="summary")
        self.project_name_var = ctk.StringVar()
        self.status_var = ctk.StringVar(value="Abre una carpeta para comenzar.")

        if sys.platform.startswith("win"):
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Picaflor.App")
            except Exception:
                pass

        self.title("Picaflor")
        self.geometry("1140x740")
        self.minsize(960, 620)

        self._build()
        self._load_icon()
        self._style_tree()
        self._shortcuts()

    def _tip(self, w, t):
        self._tips.append(SimpleTooltip(w, t))

    def _pill(self, parent, label, cmd, tip, color, w=62, h=30):
        fg, hover = color
        b = ctk.CTkButton(
            parent, text=label, width=w, height=h,
            corner_radius=15,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=fg, hover_color=hover, text_color="#ffffff",
            command=cmd,
        )
        self._tip(b, tip)
        return b

    def _mini_pill(self, parent, label, cmd, tip, color, w=42, h=24):
        fg, hover = color
        b = ctk.CTkButton(
            parent, text=label, width=w, height=h,
            corner_radius=12,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=fg, hover_color=hover, text_color="#ffffff",
            command=cmd,
        )
        self._tip(b, tip)
        return b

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(self, corner_radius=0, height=46, fg_color=("gray94", "#0f1219"))
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)

        self.info_label = ctk.CTkLabel(
            bar, text="Sin carpeta abierta",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("gray50", "#64748b"),
        )
        self.info_label.grid(row=0, column=0, sticky="w", padx=(14, 0), pady=8)

        center = ctk.CTkFrame(bar, fg_color="transparent")
        center.grid(row=0, column=1, sticky="")

        self.mode_seg = ctk.CTkSegmentedButton(
            center,
            values=["summary", "hybrid", "full"],
            command=lambda v: self.mode_var.set(v),
            height=28, corner_radius=14,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            selected_color="#3b82f6",
            selected_hover_color="#2563eb",
            unselected_color=("gray85", "#1e2433"),
            unselected_hover_color=("gray78", "#262d3d"),
        )
        self.mode_seg.pack()
        self.mode_seg.set("summary")

        right_bar = ctk.CTkFrame(bar, fg_color="transparent")
        right_bar.grid(row=0, column=2, sticky="e", padx=(0, 10), pady=8)

        pills = [
            ("Open", self.open_project, "Abrir carpeta  Ctrl+O", self.CLR_OPEN),
            ("Reload", self.rescan_project, "Releer  Ctrl+R", self.CLR_RELOAD),
            ("Run", self.generate_summary, "Generar  Ctrl+G", self.CLR_RUN),
            ("Copy", self.copy_output, "Copiar al portapapeles", self.CLR_COPY),
            ("Save", self.save_output, "Guardar .md  Ctrl+S", self.CLR_SAVE),
            ("Theme", self.toggle_theme, "Cambiar tema", self.CLR_THEME),
        ]
        for i, (label, cmd, tip, clr) in enumerate(pills):
            self._pill(right_bar, label, cmd, tip, clr).grid(row=0, column=i, padx=2)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=0, minsize=310)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color=("gray97", "#0d1017"), corner_radius=0, width=310)
        left.grid(row=0, column=0, sticky="nsw")
        left.grid_propagate(False)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        tree_bar = ctk.CTkFrame(left, fg_color="transparent")
        tree_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 2))
        tree_bar.grid_columnconfigure(0, weight=1)

        self.count_label = ctk.CTkLabel(
            tree_bar, text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray50", "#64748b"),
            anchor="w",
        )
        self.count_label.grid(row=0, column=0, sticky="w")

        mini_bar = ctk.CTkFrame(tree_bar, fg_color="transparent")
        mini_bar.grid(row=0, column=1, sticky="e")

        mini_pills = [
            ("Excl", self.exclude_selected, "Omitir seleccionados", self.CLR_EXCL),
            ("Incl", self.include_selected, "Incluir seleccionados", self.CLR_INCL),
            ("None", self.exclude_all, "Omitir todo", self.CLR_NONE),
            ("All", self.include_all, "Incluir todo", self.CLR_ALL),
        ]
        for i, (label, cmd, tip, clr) in enumerate(mini_pills):
            self._mini_pill(mini_bar, label, cmd, tip, clr).grid(row=0, column=i, padx=2)

        self.tree_frame = ctk.CTkFrame(left, corner_radius=0, fg_color="transparent")
        self.tree_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        self.tree_frame.grid_rowconfigure(0, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            self.tree_frame, show="tree", selectmode="extended",
            style="P.Treeview",
        )
        self.tree.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", self._dbl_click)

        right = ctk.CTkFrame(body, fg_color="transparent", corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        fields = ctk.CTkFrame(right, fg_color="transparent")
        fields.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        fields.grid_columnconfigure(0, weight=1)
        fields.grid_columnconfigure(1, weight=1)

        self.name_entry = ctk.CTkEntry(
            fields, textvariable=self.project_name_var,
            placeholder_text="Nombre del proyecto",
            height=34, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self.name_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.obj_entry = ctk.CTkEntry(
            fields, placeholder_text="Contexto adicional (opcional)",
            height=34, corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self.obj_entry.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.output = ctk.CTkTextbox(
            right, wrap="word", corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=13),
        )
        self.output.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.output.insert("1.0", "Picaflor\n\n1. Abre una carpeta\n2. Omite lo que no necesites\n3. Genera el resumen\n")

        self.sbar = ctk.CTkLabel(
            self, textvariable=self.status_var,
            anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray50", "#475569"),
            height=22,
        )
        self.sbar.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 5))

    def _load_icon(self) -> None:
        ico = self.base_dir / "assets" / "Picaflor.ico"
        png = self.base_dir / "assets" / "Picaflor.png"
        try:
            if ico.exists():
                self.iconbitmap(str(ico))
        except Exception:
            pass
        try:
            if png.exists():
                img = Image.open(png).convert("RGBA")
                self._icon_ref = ImageTk.PhotoImage(img)
                self.iconphoto(True, self._icon_ref)
        except Exception:
            pass

    def _shortcuts(self):
        self.bind("<Control-o>", lambda _: self.open_project())
        self.bind("<Control-r>", lambda _: self.rescan_project())
        self.bind("<Control-g>", lambda _: self.generate_summary())
        self.bind("<Control-s>", lambda _: self.save_output())

    def _style_tree(self):
        s = ttk.Style()
        s.theme_use("default")
        dark = self.theme_var.get() == "dark"

        bg = "#0d1017" if dark else "#ffffff"
        fg = "#94a3b8" if dark else "#475569"
        sel_bg = "#1e3a5f" if dark else "#dbeafe"
        sel_fg = "#e2e8f0" if dark else "#1e3a5f"

        s.configure(
            "P.Treeview",
            background=bg, fieldbackground=bg, foreground=fg,
            borderwidth=0, relief="flat",
            rowheight=26,
            font=("Segoe UI", 10),
        )
        s.map("P.Treeview",
              background=[("selected", sel_bg)],
              foreground=[("selected", sel_fg)])
        s.configure("P.Treeview", indent=18)

        self.tree.tag_configure("included", foreground=fg)
        self.tree.tag_configure("excluded", foreground="#ef4444" if dark else "#dc2626")
        self.tree.tag_configure("dir", foreground="#60a5fa" if dark else "#2563eb")
        self.tree.tag_configure("dir_excluded", foreground="#ef4444" if dark else "#dc2626")
        self.tree.tag_configure("dir_partial", foreground="#f59e0b" if dark else "#d97706")

        sb_bg = "#1e293b" if dark else "#e2e8f0"
        s.configure("Vertical.TScrollbar",
                     background=sb_bg, troughcolor=bg,
                     borderwidth=0, relief="flat", width=6)
        s.map("Vertical.TScrollbar",
              background=[("active", "#3b82f6")])

    def toggle_theme(self):
        n = "light" if self.theme_var.get() == "dark" else "dark"
        self.theme_var.set(n)
        ctk.set_appearance_mode(n)
        self._style_tree()
        if self.snapshot:
            self._rlbl()

    def _status(self, t):
        self.status_var.set(t)
        self.update_idletasks()

    def _short(self, v, mx=60):
        v = v.strip()
        return v if len(v) <= mx else f"...{v[-(mx-3):]}"

    # ── Scan ──

    def open_project(self):
        d = filedialog.askdirectory(title="Abrir carpeta del proyecto")
        if d:
            self._scan(d)

    def rescan_project(self):
        if self.snapshot:
            self._scan(self.snapshot.root_path)

    def _scan(self, root):
        self._status("Escaneando...")
        self.info_label.configure(text=self._short(root))

        def work():
            try:
                snap = self.scanner.scan(root, project_name=Path(root).name)
                snap = self.detector.analyze(snap)
                self.after(0, lambda: self._scanned(snap))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Picaflor", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _scanned(self, snap):
        self.snapshot = snap
        if not self.project_name_var.get().strip():
            self.project_name_var.set(snap.project_name)
        self.info_label.configure(text=self._short(snap.root_path))
        self.title(f"Picaflor — {snap.project_name}")
        self._populate()
        self._counts()
        self._status("Listo. Omite archivos y pulsa Run para generar.")

    def _counts(self):
        if not self.snapshot:
            return
        t = self.snapshot.file_count()
        i = self.snapshot.included_count()
        o = t - i
        techs = ", ".join(self.snapshot.detected_technologies[:5]) if self.snapshot.detected_technologies else ""
        extra = f"  |  {techs}" if techs else ""
        self.count_label.configure(text=f"{i} incl  {o} omit{extra}")

    # ── Tree ──

    def _populate(self):
        self.tree.delete(*self.tree.get_children())
        if not self.snapshot:
            return

        all_dirs = sorted(self.snapshot.directories)
        dm: dict[str, str] = {}

        def ensure_dir(d: str) -> str:
            if not d:
                return ""
            if d in dm:
                return dm[d]
            parent = str(Path(d).parent).replace("\\", "/")
            if parent == ".":
                parent = ""
            pi = ensure_dir(parent)
            iid = f"d:{d}"
            name = Path(d).name
            st = self._state(d, True)
            tag = {"excluded": "dir_excluded", "partial": "dir_partial"}.get(st, "dir")
            self.tree.insert(pi, "end", iid=iid, text=f"  {name}/", open="/" not in d, tags=(tag,))
            dm[d] = iid
            return iid

        for d in all_dirs:
            ensure_dir(d)

        for rel in sorted(self.snapshot.files):
            parent = str(Path(rel).parent).replace("\\", "/")
            if parent == ".":
                parent = ""
            pi = ensure_dir(parent) if parent else ""
            iid = f"f:{rel}"
            name = Path(rel).name
            st = self._state(rel, False)
            tag = "excluded" if st == "excluded" else "included"
            self.tree.insert(pi, "end", iid=iid, text=f"  {name}", tags=(tag,))

    def _state(self, r, is_dir):
        if not self.snapshot:
            return "included"
        if not is_dir:
            f = self.snapshot.files.get(r)
            return "excluded" if f and not f.included else "included"
        px = r.rstrip("/") + "/"
        ch = [f for f in self.snapshot.files.values()
              if f.relative_path.startswith(px)]
        if not ch:
            return "included"
        n = sum(1 for f in ch if f.included)
        if n == 0:
            return "excluded"
        if n == len(ch):
            return "included"
        return "partial"

    def _dbl_click(self, _e=None):
        for iid in self.tree.selection():
            r, d = self._pid(iid)
            self._apply(r, d, self._state(r, d) == "excluded")
        self._rlbl()
        self._counts()

    def _pid(self, iid):
        return (iid[2:], True) if iid.startswith("d:") else (iid[2:], False)

    def _apply(self, r, is_dir, v):
        if not self.snapshot:
            return
        if not is_dir:
            if r in self.snapshot.files:
                self.snapshot.files[r].included = v
            return
        px = r.rstrip("/") + "/"
        for f in self.snapshot.files.values():
            if f.relative_path.startswith(px):
                f.included = v

    def _rlbl(self):
        if not self.snapshot:
            return
        for iid in self.tree.get_children(""):
            self._rr(iid)

    def _rr(self, iid):
        r, d = self._pid(iid)
        name = Path(r).name
        if d:
            st = self._state(r, True)
            tag = {"excluded": "dir_excluded", "partial": "dir_partial"}.get(st, "dir")
            self.tree.item(iid, text=f"  {name}/", tags=(tag,))
        else:
            st = self._state(r, False)
            tag = "excluded" if st == "excluded" else "included"
            self.tree.item(iid, text=f"  {name}", tags=(tag,))
        for c in self.tree.get_children(iid):
            self._rr(c)

    def exclude_selected(self):
        self._setsel(False)

    def include_selected(self):
        self._setsel(True)

    def _setsel(self, v):
        if not self.snapshot:
            return
        for iid in self.tree.selection():
            r, d = self._pid(iid)
            self._apply(r, d, v)
        self._rlbl()
        self._counts()

    def include_all(self):
        if not self.snapshot:
            return
        for f in self.snapshot.files.values():
            f.included = True
        self._rlbl()
        self._counts()

    def exclude_all(self):
        if not self.snapshot:
            return
        for f in self.snapshot.files.values():
            f.included = False
        self._rlbl()
        self._counts()

    # ── Output ──

    def generate_summary(self):
        if not self.snapshot:
            return
        self._status("Analizando...")

        def work():
            try:
                c = self.summarizer.generate(
                    snapshot=self.snapshot,
                    mode=self.mode_var.get(),
                    project_name=self.project_name_var.get().strip() or self.snapshot.project_name,
                    objective=self.obj_entry.get().strip(),
                )
                self.after(0, lambda: self._out(c))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Picaflor", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _out(self, c):
        self.output.delete("1.0", "end")
        self.output.insert("1.0", c)
        self._status("Resumen listo.")

    def copy_output(self):
        c = self.output.get("1.0", "end").strip()
        if not c:
            return
        try:
            pyperclip.copy(c)
        except Exception:
            self.clipboard_clear()
            self.clipboard_append(c)
        self._status("Copiado.")

    def save_output(self):
        c = self.output.get("1.0", "end").strip()
        if not c:
            return
        p = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Texto", "*.txt")],
        )
        if not p:
            return
        try:
            self.exporter.save_text(p, c)
            self._status(f"Guardado: {p}")
        except Exception as e:
            messagebox.showerror("Picaflor", str(e))