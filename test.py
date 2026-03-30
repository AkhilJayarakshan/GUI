import tkinter as tk
from tkinter import filedialog, messagebox
import threading, time, math, os, platform

# ───────────────────── BACKENDS ─────────────────────
from backed import HykonUpdater
from backed2 import ServiceClearer

import serial.tools.list_ports

# ───────────────────── FONTS ─────────────────────
_OS = platform.system()
if _OS == "Windows":
    SANS = "Segoe UI"
    MONO = "Consolas"
elif _OS == "Darwin":
    SANS = "SF Pro Display"
    MONO = "Menlo"
else:
    SANS = "DejaVu Sans"
    MONO = "DejaVu Sans Mono"

def F(size, weight="normal", family=SANS):
    return (family, size, weight)

def FM(size, weight="normal"):
    return (MONO, size, weight)

# ───────────────────── COLORS ─────────────────────
BG = "#06090F"
SURFACE = "#0B111C"
SURFACE2 = "#0F1825"
BORDER_LT = "#1E3448"

CYAN = "#00E5FF"
CYAN_SOFT = "#00B8D4"
CYAN_DIM = "#004D5E"

WHITE = "#FFFFFF"
WHITE_70 = "#B0CDD6"
WHITE_40 = "#6A909A"
WHITE_20 = "#2E4A54"

GREEN = "#00E5A0"
AMBER = "#FFB300"
RED = "#FF3D5A"
BLACK = "#000000"

# ───────────────────── ARC PROGRESS ─────────────────────
class ArcRing(tk.Canvas):
    def __init__(self, parent, size=210):
        super().__init__(parent, width=size, height=size, bg=BG, highlightthickness=0)
        self.cx = size // 2
        self.cy = size // 2
        self.r = size // 2 - 22
        self._pct = 0
        self._target = 0
        self._animate()

    def _animate(self):
        self._pct += (self._target - self._pct) * 0.1
        self._draw()
        self.after(30, self._animate)

    def _draw(self):
        self.delete("all")
        pct = self._pct
        cx, cy, r = self.cx, self.cy, self.r

        self.create_oval(cx-r, cy-r, cx+r, cy+r,
                         outline=BORDER_LT, width=14)

        if pct > 0:
            ext = pct * 3.6
            self.create_arc(cx-r, cy-r, cx+r, cy+r,
                            start=90, extent=-ext,
                            outline=CYAN_SOFT, width=8, style="arc")

        self.create_text(cx, cy - 5, text=str(int(pct)),
                         font=F(32, "bold"), fill=WHITE)
        self.create_text(cx, cy + 22, text="PERCENT",
                         font=F(9), fill=WHITE_40)

    def set_pct(self, v):
        self._target = max(0, min(100, float(v)))

# ───────────────────── APP ─────────────────────
class HykonApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hykon · Premium Firmware Tool")
        self.configure(bg=BG)
        self.geometry("820x700")

        self._port = tk.StringVar(value="Select COM Port")
        self._mode = tk.StringVar(value="firmware")
        self._file = None
        self._uploading = False
        self._start_time = None

        self._build_ui()
        self._scan_ports()

    # ───────── UI ─────────
    def _build_ui(self):
        title = tk.Label(self, text="HYKON", font=F(36, "bold"), fg=CYAN, bg=BG)
        title.pack(pady=20)

        # PORT
        tk.Label(self, text="COM PORT", font=F(11, "bold"),
                 fg=WHITE, bg=BG).pack()

        self.port_menu = tk.OptionMenu(self, self._port, "")
        self.port_menu.config(bg=SURFACE, fg=WHITE, font=F(13))
        self.port_menu.pack(pady=6)

        tk.Button(self, text="Refresh Ports", command=self._scan_ports).pack()

        # MODE
        mode_frame = tk.Frame(self, bg=BG)
        mode_frame.pack(pady=10)

        tk.Radiobutton(mode_frame, text="Firmware Update",
                       variable=self._mode, value="firmware",
                       bg=BG, fg=WHITE, selectcolor=BG).pack(side="left", padx=10)

        tk.Radiobutton(mode_frame, text="Clear Service",
                       variable=self._mode, value="service",
                       bg=BG, fg=WHITE, selectcolor=BG).pack(side="left")

        # FILE
        tk.Button(self, text="Browse Firmware (.bin)",
                  command=self._browse).pack(pady=10)

        self.file_lbl = tk.Label(self, text="No file selected",
                                 font=F(11), fg=WHITE_40, bg=BG)
        self.file_lbl.pack()

        # ACTION
        tk.Button(self, text="START",
                  font=F(14, "bold"),
                  bg=CYAN, fg=BLACK,
                  command=self._start).pack(pady=14)

        # PROGRESS
        self.arc = ArcRing(self)
        self.arc.pack(pady=14)

        self.timer_lbl = tk.Label(self, text="00:00",
                                  font=F(28, "bold"), fg=CYAN, bg=BG)
        self.timer_lbl.pack()

        # LOG
        self.log = tk.Text(self, height=10,
                           bg=SURFACE, fg=CYAN, font=FM(10))
        self.log.pack(fill="both", expand=True, padx=20, pady=10)

    # ───────── LOGIC ─────────
    def _scan_ports(self):
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for p in ports:
            menu.add_command(label=p, command=lambda x=p: self._port.set(x))
        if ports:
            self._port.set(ports[0])

    def _browse(self):
        path = filedialog.askopenfilename(filetypes=[("BIN", "*.bin")])
        if path:
            self._file = path
            self.file_lbl.config(text=os.path.basename(path), fg=WHITE)

    def _start(self):
        if not self._port.get():
            messagebox.showerror("Error", "No COM port selected")
            return

        self._uploading = True
        self.arc.set_pct(0)
        self.log.delete("1.0", "end")
        self._start_time = time.time()
        self._tick()

        t = threading.Thread(target=self._worker, daemon=True)
        t.start()

    def _worker(self):
        try:
            if self._mode.get() == "firmware":
                updater = HykonUpdater(self._port.get())
                updater.run_update(
                    self._file,
                    progress_callback=self._progress,
                    done_callback=self._done
                )
            else:
                clearer = ServiceClearer(self._port.get())
                clearer.run_clear(
                    progress_callback=self._log_msg,
                    done_callback=self._done
                )
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _progress(self, val):
        if isinstance(val, str):
            self._log_msg(val)
        else:
            self.after(0, self.arc.set_pct, val)

    def _done(self, msg):
        self.after(0, lambda: messagebox.showinfo("Hykon", msg))
        self._uploading = False

    def _log_msg(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def _tick(self):
        if not self._uploading:
            return
        s = int(time.time() - self._start_time)
        self.timer_lbl.config(text=f"{s//60:02d}:{s%60:02d}")
        self.after(1000, self._tick)

# ───────────────────── ENTRY ─────────────────────
if __name__ == "__main__":
    app = HykonApp()
    app.mainloop()