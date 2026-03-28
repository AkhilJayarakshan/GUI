"""
Hykon — Auto Cluster Firmware Updater
Premium Edition  |  Cyan · White · Black  |  CAN Bus
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import threading, time, math, os, platform

try:
    import serial.tools.list_ports
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyserial", "-q"])
    import serial.tools.list_ports

# ── FONT STACK: crisp, anti-aliased, never pixelated ─────────────────────────
_OS = platform.system()
if _OS == "Windows":
    SANS  = "Segoe UI"
    MONO  = "Consolas"
elif _OS == "Darwin":
    SANS  = "SF Pro Display"
    MONO  = "Menlo"
else:
    SANS  = "DejaVu Sans"
    MONO  = "DejaVu Sans Mono"

def F(size, weight="normal", family=SANS):
    return (family, size, weight)

def FM(size, weight="normal"):
    return (MONO, size, weight)

# ── PALETTE ──────────────────────────────────────────────────────────────────
BG         = "#06090F"
SURFACE    = "#0B111C"
SURFACE2   = "#0F1825"
BORDER     = "#162436"
BORDER_LT  = "#1E3448"

CYAN       = "#00E5FF"
CYAN_SOFT  = "#00B8D4"
CYAN_DIM   = "#004D5E"
CYAN_GLOW  = "#003A47"

WHITE      = "#FFFFFF"
WHITE_90   = "#E8F4F8"
WHITE_70   = "#B0CDD6"
WHITE_40   = "#6A909A"
WHITE_20   = "#2E4A54"

GREEN      = "#00E5A0"
AMBER      = "#FFB300"
RED        = "#FF3D5A"
BLACK      = "#000000"


# ── GLOW LINE ────────────────────────────────────────────────────────────────
class GlowLine(tk.Canvas):
    def __init__(self, parent, **kw):
        super().__init__(parent, height=4, bg=BG, highlightthickness=0, **kw)
        self.bind("<Configure>", self._draw)

    def _draw(self, e=None):
        self.delete("all")
        w = self.winfo_width() or 800
        profile = [(0, 12), (1, 80), (2, 220), (3, 80)]
        for y, a in profile:
            gv = int(0xE5 * a / 255)
            bv = int(0xFF * a / 255)
            self.create_line(0, y, w, y, fill=f"#00{gv:02x}{bv:02x}", width=1)


# ── ARC PROGRESS ─────────────────────────────────────────────────────────────
class ArcRing(tk.Canvas):
    def __init__(self, parent, size=210, **kw):
        super().__init__(parent, width=size, height=size,
                         bg=BG, highlightthickness=0, **kw)
        self.cx = size // 2
        self.cy = size // 2
        self.r  = size // 2 - 22
        self._pct    = 0.0
        self._target = 0.0
        self._phase  = 0.0
        self._animate()

    def _animate(self):
        self._phase += 0.05
        self._pct   += (self._target - self._pct) * 0.09
        self._draw()
        self.after(28, self._animate)

    def _draw(self):
        self.delete("all")
        cx, cy, r = self.cx, self.cy, self.r

        # Outer glow halo
        pr = r + 12 + 2 * math.sin(self._phase)
        pa = int(18 + 14 * abs(math.sin(self._phase)))
        gv = int(0xE5 * pa / 255); bv = int(0xFF * pa / 255)
        self.create_oval(cx-pr, cy-pr, cx+pr, cy+pr,
                         outline=f"#00{gv:02x}{bv:02x}", width=1)

        # Track ring (dark)
        self.create_oval(cx-r, cy-r, cx+r, cy+r,
                         outline=BORDER_LT, width=14, fill=BG)

        # Progress arc layers
        if self._pct > 0.3:
            ext = (self._pct / 100.0) * 359.8

            # Deep glow layer
            self.create_arc(cx-r, cy-r, cx+r, cy+r,
                            start=90, extent=-ext,
                            outline=CYAN_DIM, width=18, style="arc")
            # Mid glow
            self.create_arc(cx-r, cy-r, cx+r, cy+r,
                            start=90, extent=-ext,
                            outline=CYAN_SOFT, width=8, style="arc")
            # Bright top line
            self.create_arc(cx-r, cy-r, cx+r, cy+r,
                            start=90, extent=-ext,
                            outline=CYAN, width=2, style="arc")

            # White tip dot
            tip_a = math.radians(90 - ext)
            tx = cx + r * math.cos(tip_a)
            ty = cy - r * math.sin(tip_a)
            self.create_oval(tx-7, ty-7, tx+7, ty+7,
                             fill=WHITE, outline=CYAN, width=2)
            # Glow behind tip
            self.create_oval(tx-11, ty-11, tx+11, ty+11,
                             outline=CYAN_SOFT, width=1)

        # Center: big white number
        pct_i = int(self._pct)
        self.create_text(cx, cy - 10,
                         text=str(pct_i),
                         font=F(30, "bold"),
                         fill=WHITE if pct_i > 0 else WHITE_20)
        self.create_text(cx, cy + 20,
                         text="PERCENT",
                         font=F(8),
                         fill=WHITE_40)

    def set_pct(self, v):
        self._target = max(0.0, min(100.0, float(v)))


# ── PILL BUTTON ───────────────────────────────────────────────────────────────
class PillBtn(tk.Canvas):
    def __init__(self, parent, text, cmd,
                 w=200, h=48, style="filled", **kw):
        super().__init__(parent, width=w, height=h,
                         bg=BG, highlightthickness=0,
                         cursor="hand2", **kw)
        self.txt   = text
        self._cmd  = cmd
        self.w     = w
        self.h     = h
        self.style = style      # "filled" | "outline" | "ghost"
        self._hover  = False
        self._active = True
        self._draw()
        self.bind("<Enter>",    lambda e: self._hover_set(True))
        self.bind("<Leave>",    lambda e: self._hover_set(False))
        self.bind("<Button-1>", lambda e: self._click())

    def _hover_set(self, v):
        self._hover = v; self._draw()

    def _click(self):
        if self._active and self._cmd:
            self._cmd()

    def _draw(self):
        self.delete("all")
        w, h = self.w, self.h
        r = h // 2
        pts = [r,0, w-r,0, w,r, w,h-r, w-r,h, r,h, 0,h-r, 0,r]

        if not self._active:
            bg_c, fg_c, ol_c = BORDER, WHITE_20, BORDER
        elif self.style == "filled":
            bg_c = WHITE  if self._hover else CYAN
            fg_c = BLACK
            ol_c = CYAN
        elif self.style == "outline":
            bg_c = SURFACE2 if self._hover else BG
            fg_c = WHITE    if self._hover else CYAN
            ol_c = CYAN
        else:  # ghost
            bg_c = SURFACE  if self._hover else BG
            fg_c = WHITE_70 if self._hover else WHITE_40
            ol_c = BORDER_LT

        self.create_polygon(pts, fill=bg_c, outline=ol_c,
                            width=1, smooth=True)
        self.create_text(w // 2, h // 2,
                         text=self.txt,
                         font=F(12, "bold"),
                         fill=fg_c)

    def enable(self, v: bool):
        self._active = v
        self.config(cursor="hand2" if v else "arrow")
        self._draw()

    def set_text(self, t):
        self.txt = t; self._draw()


# ── LABEL HELPERS ─────────────────────────────────────────────────────────────
def lbl(parent, text, size=13, weight="normal",
        color=WHITE, bg=BG, **kw):
    return tk.Label(parent, text=text,
                    font=F(size, weight),
                    fg=color, bg=bg, **kw)

def lbl_var(parent, var, size=13, weight="normal",
            color=WHITE, bg=BG, **kw):
    return tk.Label(parent, textvariable=var,
                    font=F(size, weight),
                    fg=color, bg=bg, **kw)


# ── MAIN APP ──────────────────────────────────────────────────────────────────
class HykonApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hykon · CAN Firmware Updater")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(780, 660)

        # state
        self._port_var  = tk.StringVar(value="Select port…")
        self._file_path = ""
        self._status_v  = tk.StringVar(value="READY")
        self._elapsed   = tk.StringVar(value="00:00")
        self._uploading = False
        self._t0        = None
        self._timer_id  = None

        self._build_ui()
        self._scan_ports()

        # center
        self.update_idletasks()
        W, H = 820, 700
        sx = (self.winfo_screenwidth()  - W) // 2
        sy = (self.winfo_screenheight() - H) // 2
        self.geometry(f"{W}x{H}+{sx}+{sy}")

    # ─────────────────────────────────────────────────────────────────────────
    # BUILD
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._make_header()
        GlowLine(self).pack(fill="x")

        # Body wrapper
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=32, pady=18)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0)
        body.rowconfigure(0, weight=1)

        # Left column
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 0))
        left.rowconfigure(3, weight=1)   # log expands
        left.columnconfigure(0, weight=1)

        # Right column
        right = tk.Frame(body, bg=BG, width=230)
        right.grid(row=0, column=1, sticky="ns", padx=(28, 0))
        right.grid_propagate(False)

        self._make_port_section(left)
        self._make_file_section(left)
        self._make_btn_section(left)
        self._make_log_section(left)
        self._make_instruments(right)

        GlowLine(self).pack(fill="x")
        self._make_footer()

    # ── HEADER ───────────────────────────────────────────────────────────────

    def _make_header(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="x", padx=32, pady=(24, 16))

        # LEFT — brand
        brand = tk.Frame(outer, bg=BG)
        brand.pack(side="left")

        name_row = tk.Frame(brand, bg=BG)
        name_row.pack(anchor="w")
        lbl(name_row, "HY",  36, "bold", WHITE, BG).pack(side="left")
        lbl(name_row, "KON", 36, "bold", CYAN,  BG).pack(side="left")

        lbl(brand,
            "AUTO CLUSTER  ·  CAN BUS FIRMWARE UPDATE TOOL",
            10, color=WHITE_40).pack(anchor="w", pady=(3, 0))

        # RIGHT — status badge
        badge_frame = tk.Frame(outer, bg=BG)
        badge_frame.pack(side="right", anchor="center")

        self._badge = tk.Label(
            badge_frame,
            textvariable=self._status_v,
            font=F(11, "bold"),
            fg=BLACK, bg=GREEN,
            padx=18, pady=7)
        self._badge.pack()

    # ── SECTION TITLE ────────────────────────────────────────────────────────

    def _sec(self, parent, text, row):
        """Section title with cyan accent bar."""
        f = tk.Frame(parent, bg=BG)
        f.grid(row=row, column=0, sticky="ew", pady=(20, 6))
        tk.Frame(f, bg=CYAN, width=3, height=18).pack(side="left", padx=(0, 10))
        lbl(f, text, 12, "bold", WHITE).pack(side="left")

    # ── PORT ─────────────────────────────────────────────────────────────────

    def _make_port_section(self, parent):
        self._sec(parent, "COM PORT", 0)

        row = tk.Frame(parent, bg=BG)
        row.grid(row=1, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)

        # Dropdown frame
        port_frame = tk.Frame(row, bg=SURFACE,
                               highlightbackground=BORDER_LT,
                               highlightthickness=1)
        port_frame.grid(row=0, column=0, sticky="ew", ipady=1)

        self._port_mb = tk.Menubutton(
            port_frame,
            textvariable=self._port_var,
            font=F(13), fg=WHITE, bg=SURFACE,
            activeforeground=CYAN,
            activebackground=SURFACE,
            relief="flat", padx=16, pady=11,
            anchor="w", cursor="hand2",
            direction="below")
        self._port_mb.pack(fill="x")

        self._pmenu = tk.Menu(
            self._port_mb, tearoff=False,
            bg=SURFACE2, fg=WHITE,
            font=F(12),
            activebackground=BORDER_LT,
            activeforeground=CYAN,
            relief="flat", bd=0)
        self._port_mb["menu"] = self._pmenu

        # Scan button
        PillBtn(row, "⟳  SCAN", self._scan_ports,
                w=110, h=42, style="outline").grid(
            row=0, column=1, padx=(10, 0))

    # ── FILE ─────────────────────────────────────────────────────────────────

    def _make_file_section(self, parent):
        self._sec(parent, "FIRMWARE FILE  ·  .BIN", 2)

        row = tk.Frame(parent, bg=BG)
        row.grid(row=3, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)

        file_frame = tk.Frame(row, bg=SURFACE,
                               highlightbackground=BORDER_LT,
                               highlightthickness=1)
        file_frame.grid(row=0, column=0, sticky="ew", ipady=1)

        self._file_lbl = tk.Label(
            file_frame,
            text="No file selected",
            font=F(13), fg=WHITE_40, bg=SURFACE,
            padx=16, pady=11, anchor="w")
        self._file_lbl.pack(fill="x")

        PillBtn(row, "BROWSE", self._browse_file,
                w=110, h=42, style="outline").grid(
            row=0, column=1, padx=(10, 0))

        self._size_lbl = tk.Label(parent, text="",
                                   font=F(10), fg=WHITE_40, bg=BG)
        self._size_lbl.grid(row=4, column=0, sticky="w", pady=(5, 0))

    # ── BUTTONS ──────────────────────────────────────────────────────────────

    def _make_btn_section(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.grid(row=5, column=0, sticky="ew", pady=(18, 0))

        self._up_btn = PillBtn(
            row, "  ⬆   UPLOAD FIRMWARE  ",
            self._start_upload, w=260, h=52, style="filled")
        self._up_btn.pack(side="left")

        self._can_btn = PillBtn(
            row, "CANCEL", self._cancel_upload,
            w=120, h=52, style="outline")
        self._can_btn.pack(side="left", padx=(12, 0))

    # ── LOG ──────────────────────────────────────────────────────────────────

    def _make_log_section(self, parent):
        self._sec(parent, "EVENT LOG", 6)

        frame = tk.Frame(parent, bg=SURFACE,
                          highlightbackground=BORDER_LT,
                          highlightthickness=1)
        frame.grid(row=7, column=0, sticky="nsew", pady=(0, 4))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self._logbox = tk.Text(
            frame,
            font=F(11),
            bg=SURFACE, fg=CYAN,
            relief="flat", state="disabled",
            padx=14, pady=10,
            spacing3=4,
            insertbackground=CYAN,
            selectbackground=BORDER_LT,
            wrap="word")
        self._logbox.grid(row=0, column=0, sticky="nsew")

        sb = tk.Scrollbar(frame, orient="vertical",
                           command=self._logbox.yview,
                           bg=SURFACE, troughcolor=BG,
                           activebackground=CYAN, width=10)
        sb.grid(row=0, column=1, sticky="ns")
        self._logbox.config(yscrollcommand=sb.set)

        # Tags
        self._logbox.tag_config("ok",   foreground=GREEN,    font=F(11))
        self._logbox.tag_config("warn", foreground=AMBER,    font=F(11))
        self._logbox.tag_config("err",  foreground=RED,      font=F(11))
        self._logbox.tag_config("info", foreground=CYAN,     font=F(11))
        self._logbox.tag_config("dim",  foreground=WHITE_40, font=F(11))
        self._logbox.tag_config("ts",   foreground=WHITE_20, font=FM(10))

        self._log("System initialised.", "ok")
        self._log("Select a COM port to begin.", "dim")

    # ── RIGHT PANEL: instruments ─────────────────────────────────────────────

    def _make_instruments(self, parent):

        # ── Progress ring
        lbl(parent, "PROGRESS", 11, "bold",
            WHITE, BG).pack(pady=(4, 10))

        self._arc = ArcRing(parent, size=210)
        self._arc.pack()

        self._divider(parent)

        # ── Elapsed
        lbl(parent, "ELAPSED", 11, "bold",
            WHITE, BG).pack(pady=(0, 6))
        lbl_var(parent, self._elapsed,
                42, "bold", CYAN, BG).pack()
        lbl(parent, "MM  :  SS", 9,
            color=WHITE_40).pack(pady=(2, 0))

        self._divider(parent)

        # ── Session stats
        lbl(parent, "SESSION INFO", 10, "bold",
            WHITE, BG).pack(pady=(0, 8))

        stats = [
            ("Protocol",  "CAN Bus"),
            ("Baud rate", "500 Kbps"),
            ("Target ECU","Cluster"),
        ]
        for k, v in stats:
            row = tk.Frame(parent, bg=BG)
            row.pack(fill="x", pady=3)
            lbl(row, k, 10, color=WHITE_40,
                bg=BG).pack(side="left")
            lbl(row, v, 10, "bold", WHITE,
                bg=BG).pack(side="right")

    def _divider(self, parent):
        tk.Frame(parent, bg=BORDER_LT, height=1).pack(
            fill="x", pady=16)

    # ── FOOTER ───────────────────────────────────────────────────────────────

    def _make_footer(self):
        f = tk.Frame(self, bg=BG)
        f.pack(fill="x", padx=32, pady=10)
        lbl(f, "© 2025  Hykon India Pvt. Ltd.",
            10, color=WHITE_40).pack(side="left")
        lbl(f, "Auto Rickshaw Cluster Division",
            10, color=WHITE_40).pack(side="right")

    # ─────────────────────────────────────────────────────────────────────────
    # LOGIC
    # ─────────────────────────────────────────────────────────────────────────

    def _log(self, msg, tag="info"):
        self._logbox.config(state="normal")
        ts = time.strftime("%H:%M:%S")
        self._logbox.insert("end", f" {ts}  ", "ts")
        self._logbox.insert("end", f"{msg}\n", tag)
        self._logbox.see("end")
        self._logbox.config(state="disabled")

    def _set_status(self, text, color=GREEN):
        self._status_v.set(text)
        dark = color in (GREEN, CYAN, AMBER, WHITE)
        self._badge.config(bg=color, fg=BLACK if dark else WHITE)

    # ── Ports ─────────────────────────────────────────────────────────────────

    def _scan_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self._pmenu.delete(0, "end")
        if ports:
            for p in ports:
                self._pmenu.add_command(
                    label=p,
                    command=lambda v=p: self._sel_port(v))
            self._sel_port(ports[0])
            self._log(f"{len(ports)} port(s) found: {', '.join(ports)}", "ok")
        else:
            self._port_var.set("No ports detected")
            self._log("No COM ports found. Check connection.", "warn")

    def _sel_port(self, port):
        self._port_var.set(port)
        self._log(f"Port selected: {port}", "ok")

    # ── File ──────────────────────────────────────────────────────────────────

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select Firmware Binary",
            filetypes=[("Binary files", "*.bin"),
                       ("All files", "*.*")])
        if not path:
            return
        self._file_path = path
        name = os.path.basename(path)
        kb   = os.path.getsize(path) / 1024
        disp = name if len(name) <= 30 else "…" + name[-28:]
        self._file_lbl.config(text=disp, fg=WHITE)
        self._size_lbl.config(
            text=f"{name}   ·   {kb:.1f} KB")
        self._log(f"File loaded: {name}  [{kb:.1f} KB]", "ok")

    # ── Upload ────────────────────────────────────────────────────────────────

    def _start_upload(self):
        port = self._port_var.get()
        if any(x in port for x in ("Select", "No port")):
            messagebox.showerror(
                "Port Error", "Please select a valid COM port first.")
            return
        if not self._file_path:
            messagebox.showerror(
                "File Error", "Please select a .bin firmware file first.")
            return

        self._uploading = True
        self._set_status("UPLOADING", AMBER)
        self._up_btn.enable(False)
        self._arc.set_pct(0)
        self._elapsed.set("00:00")
        self._t0 = time.time()
        self._tick()
        self._log(f"Upload started  →  {port}", "info")
        threading.Thread(target=self._upload_worker, daemon=True).start()

    def _upload_worker(self):
        """
        ── Plug in your backend here ──────────────────────────────
        Progress:  self.after(0, self._on_progress, pct, message)
        Finished:  self.after(0, self._on_finish, True/False, msg)
        ────────────────────────────────────────────────────────────
        """
        steps = [
            ( 6,  "Establishing CAN bus connection…"),
            (13,  "ECU handshake acknowledged."),
            (22,  "Entering bootloader mode."),
            (34,  "Erasing flash memory…"),
            (48,  "Writing firmware block 1 / 4"),
            (62,  "Writing firmware block 2 / 4"),
            (76,  "Writing firmware block 3 / 4"),
            (89,  "Writing firmware block 4 / 4"),
            (94,  "Verifying CRC checksum…"),
            (98,  "Resetting ECU…"),
            (100, "Firmware update complete."),
        ]
        for pct, msg in steps:
            if not self._uploading:
                return
            time.sleep(1.15)
            self.after(0, self._on_progress, pct, msg)
        self.after(0, self._on_finish, True,
                   "Firmware updated successfully.")

    def _on_progress(self, pct, msg):
        self._arc.set_pct(pct)
        self._log(msg, "ok" if pct == 100 else "info")

    def _on_finish(self, ok, msg):
        self._uploading = False
        if self._timer_id:
            self.after_cancel(self._timer_id)
        self._up_btn.enable(True)
        if ok:
            self._set_status("COMPLETE", GREEN)
            self._log(msg, "ok")
            messagebox.showinfo("Hykon",
                                f"✅  {msg}")
        else:
            self._set_status("FAILED", RED)
            self._log(msg, "err")
            messagebox.showerror("Upload Failed", msg)

    def _cancel_upload(self):
        if not self._uploading:
            return
        self._uploading = False
        if self._timer_id:
            self.after_cancel(self._timer_id)
        self._arc.set_pct(0)
        self._elapsed.set("00:00")
        self._up_btn.enable(True)
        self._set_status("CANCELLED", AMBER)
        self._log("Upload cancelled by user.", "warn")

    # ── Timer ─────────────────────────────────────────────────────────────────

    def _tick(self):
        if not self._uploading:
            return
        s = int(time.time() - self._t0)
        self._elapsed.set(f"{s // 60:02d}:{s % 60:02d}")
        self._timer_id = self.after(1000, self._tick)


# ── ENTRY ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = HykonApp()
    app.mainloop()