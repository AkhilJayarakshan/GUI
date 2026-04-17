import tkinter as tk
from tkinter import filedialog, messagebox
import threading, time, os, platform, subprocess, sys

# --------------------- BACKENDS ---------------------
from update import HykonUpdater
from service import ServiceClearer
from odo import ServiceClearer as OdometerClearer

import serial.tools.list_ports

# --------------------- FONTS ---------------------
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
    return (family, int(size), weight)

def FM(size, weight="normal"):
    return (MONO, int(size), weight)

# --------------------- COLORS ---------------------
BG = "#0D0D0F"
SURFACE = "#141618"
SURFACE2 = "#1A1D20"
BORDER_LT = "#252A32"

CYAN = "#00E5FF"
CYAN_BRIGHT = "#00F5FF"
CYAN_SOFT = "#00B8D4"
CYAN_DIM = "#004D5E"

WHITE = "#FFFFFF"
WHITE_90 = "#E8E8E8"
WHITE_70 = "#B0CDD6"
WHITE_40 = "#6A909A"
WHITE_20 = "#2E4A54"

GREEN = "#00E5A0"
AMBER = "#FFB300"
RED = "#FF3D5A"
BLACK = "#000000"

UPDATE_COLOR = "#00C8FF"
SERVICE_COLOR = "#FF6B35"

# --------------------- PROGRESS ARC ---------------------
class ArcRing(tk.Canvas):
    def __init__(self, parent, size=160, color=CYAN_SOFT):
        super().__init__(parent, width=size, height=size, bg=SURFACE2, highlightthickness=0)
        self.color = color
        self.cx = size // 2
        self.cy = size // 2
        self.r = size // 2 - 18
        self._pct = 0
        self._target = 0
        self._animate()

    def _animate(self):
        self._pct += (self._target - self._pct) * 0.08
        self._draw()
        self.after(25, self._animate)

    def _draw(self):
        self.delete("all")
        pct = self._pct
        cx, cy, r = self.cx, self.cy, self.r

        self.create_oval(cx-r, cy-r, cx+r, cy+r, outline=BORDER_LT, width=10)

        if pct > 0:
            ext = pct * 3.6
            self.create_arc(cx-r, cy-r, cx+r, cy+r, start=90, extent=-ext,
                           outline=self.color, width=10, style="arc")

        self.create_text(cx, cy - 3, text=f"{int(pct)}%", font=F(28, "bold"), fill=WHITE)
        self.create_text(cx, cy + 18, text="PROGRESS", font=F(8, "bold"), fill=WHITE_70)

    def set_pct(self, v):
        self._target = max(0, min(100, float(v)))
    
    def set_color(self, color):
        self.color = color

# --------------------- MODE SELECTION WINDOW ---------------------
class ModeSelectionWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hykon - Select Service")
        self.geometry("900x700")
        self.configure(bg=BG)
        self.resizable(True, True)
        
        self.selected_mode = None
        self._connect_port = tk.StringVar(value="Select COM Port")
        self.build_ui()
    
    def build_ui(self):
        # Header
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=40, pady=(40, 20))
        
        tk.Label(header, text="⚙️  HYKON", font=F(48, "bold"), fg=CYAN, bg=BG).pack()
        tk.Button(self, text="🔌 CONNECT", font=F(12, "bold"), bg="#2D7DFF", fg=BLACK, activebackground="#68A9FF",
                 command=self._run_connect, padx=20, pady=10, relief="flat", cursor="hand2").pack(pady=(20, 12))
        
        port_frame = tk.Frame(self, bg=BG)
        port_frame.pack(fill="x", padx=40, pady=(0, 12))
        tk.Label(port_frame, text="📡 COM PORT", font=F(10, "bold"), fg=WHITE_70, bg=BG).pack(anchor="w")
        port_inner = tk.Frame(port_frame, bg=BG)
        port_inner.pack(fill="x", pady=(5, 0))

        self.connect_port_menu = tk.OptionMenu(port_inner, self._connect_port, "")
        self.connect_port_menu.config(bg=SURFACE2, fg=CYAN, font=F(10, "bold"), activebackground=CYAN_DIM)
        self.connect_port_menu.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Button(port_inner, text="🔄 REFRESH", command=self._scan_connect_ports,
                 bg=UPDATE_COLOR, fg=BLACK, font=F(10, "bold"), padx=18, pady=6,
                 relief="flat", cursor="hand2").pack(side="right")
        self._scan_connect_ports()
        
        # Choose service label
        tk.Label(self, text="Choose Your Service", font=F(18, "bold"), fg=WHITE, bg=BG).pack(pady=(0, 20))
        
        # Buttons container
        buttons_frame = tk.Frame(self, bg=BG)
        buttons_frame.pack(expand=True, fill="both", padx=40)
        
        # Firmware Update Button
        tk.Button(buttons_frame, text="📲 FIRMWARE UPDATE\nUpdate ECU firmware", 
                 font=F(12, "bold"), bg=UPDATE_COLOR, fg=BLACK, activebackground=CYAN_BRIGHT,
                 command=lambda: self.select_mode("firmware"),
                 padx=30, pady=30, relief="flat", cursor="hand2", highlightthickness=0).pack(fill="x", pady=(0, 12))
        
        # Service Reset Button
        tk.Button(buttons_frame, text="🛠️ SERVICE RESET\nClear warning light", 
                 font=F(12, "bold"), bg=SERVICE_COLOR, fg=WHITE, activebackground=AMBER,
                 command=lambda: self.select_mode("service"),
                 padx=30, pady=30, relief="flat", cursor="hand2", highlightthickness=0).pack(fill="x", pady=(0, 12))
        
        # Odometer Reset Button
        tk.Button(buttons_frame, text="📊 ODOMETER RESET\nClear odometer reading", 
                 font=F(12, "bold"), bg=GREEN, fg=BLACK, activebackground="#00F0A9",
                 command=lambda: self.select_mode("odometer"),
                 padx=30, pady=30, relief="flat", cursor="hand2", highlightthickness=0).pack(fill="x")
    
    def select_mode(self, mode):
        self.selected_mode = mode
        self.withdraw()  # Hide mode selection window
        
        if mode == "firmware":
            FirmwareWindow(self)
        elif mode == "service":
            ServiceWindow(self)
        else:  # odometer
            OdometerWindow(self)

    def _scan_connect_ports(self):
        menu = self.connect_port_menu["menu"]
        menu.delete(0, "end")
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for p in ports:
            menu.add_command(label=p, command=lambda x=p: self._connect_port.set(x))
        if ports:
            self._connect_port.set(ports[0])
        else:
            self._connect_port.set("Select COM Port")

    def _run_connect(self):
        if not self._connect_port.get() or "Select" in self._connect_port.get():
            messagebox.showerror("Error", "Select a COM port to connect!")
            return
        script_path = os.path.join(os.path.dirname(__file__), "connect.py")
        subprocess.Popen([sys.executable, script_path, self._connect_port.get()], shell=False)

# --------------------- FIRMWARE UPDATE WINDOW ---------------------
class FirmwareWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Hykon - Firmware Update")
        self.geometry("1366x750")
        self.minsize(1100, 650)
        self.configure(bg=BG)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.go_home)
        
        self._port = tk.StringVar(value="Select COM Port")
        self._update_type = tk.StringVar(value="firmware")
        self._file = None
        self._uploading = False
        self._start_time = None
        self._cancel_event = threading.Event()
        self._updater = None
        
        self.build_ui()
        self._scan_ports()
    
    def build_ui(self):
        main_frame = tk.Frame(self, bg=BG)
        main_frame.pack(fill="both", expand=True)
        
        # ===== HEADER =====
        header = tk.Frame(main_frame, bg=BG)
        header.pack(fill="x", padx=25, pady=(15, 10))
        
        left_h = tk.Frame(header, bg=BG)
        left_h.pack(side="left")
        tk.Label(left_h, text="📲 FIRMWARE UPDATE", font=F(28, "bold"), fg=UPDATE_COLOR, bg=BG).pack(anchor="w")
        #tk.Label(left_h, text="Update your autorickshaw''s electronic control unit", font=F(11), fg=WHITE_70, bg=BG).pack(anchor="w")
        
        right_h = tk.Frame(header, bg=BG)
        right_h.pack(side="right")
        tk.Label(right_h, text="● READY", font=F(11, "bold"), fg=GREEN, bg=BG).pack(anchor="e", padx=(0, 15))
        tk.Button(right_h, text="🏠 HOME", command=self.go_home,
                 bg=UPDATE_COLOR, fg=BLACK, font=F(10, "bold"), padx=15, pady=5,
                 relief="flat", cursor="hand2").pack(anchor="e")
        
        # ===== TOP SECTION - Connection & File =====
        top_panel = tk.Frame(main_frame, bg=BG)
        top_panel.pack(fill="x", padx=25, pady=(10, 15))
        
        # Connection
        conn_box = tk.Frame(top_panel, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER_LT)
        conn_box.pack(fill="x", pady=(0, 10))
        
        tk.Label(conn_box, text="📡 COM PORT", font=F(11, "bold"), fg=UPDATE_COLOR, bg=SURFACE).pack(anchor="w", padx=15, pady=(10, 5))
        
        port_inner = tk.Frame(conn_box, bg=SURFACE)
        port_inner.pack(fill="x", padx=15, pady=(0, 10))
        
        self.port_menu = tk.OptionMenu(port_inner, self._port, "")
        self.port_menu.config(bg=SURFACE2, fg=CYAN, font=F(11, "bold"), activebackground=CYAN_DIM)
        self.port_menu.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        tk.Button(port_inner, text="🔄 REFRESH", command=self._scan_ports,
                 bg=UPDATE_COLOR, fg=BLACK, font=F(10, "bold"), padx=20, pady=6, 
                 relief="flat", cursor="hand2").pack(side="right")
        
        # Update Type selection
        type_box = tk.Frame(top_panel, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER_LT)
        type_box.pack(fill="x", pady=(10, 10))
        
        tk.Label(type_box, text="🔧 UPDATE TYPE", font=F(11, "bold"), fg=UPDATE_COLOR, bg=SURFACE).pack(anchor="w", padx=15, pady=(10, 5))
        
        type_inner = tk.Frame(type_box, bg=SURFACE)
        type_inner.pack(fill="x", padx=15, pady=(0, 10))
        
        tk.Radiobutton(type_inner, text="📲 Firmware Update", variable=self._update_type, value="firmware",
                      bg=SURFACE, fg=CYAN, font=F(10), selectcolor=SURFACE, activebackground=SURFACE,
                      activeforeground=CYAN, command=self._update_file_label).pack(side="left", padx=(0, 20))
        
        tk.Radiobutton(type_inner, text="💾 Assets Update", variable=self._update_type, value="assets",
                      bg=SURFACE, fg=CYAN, font=F(10), selectcolor=SURFACE, activebackground=SURFACE,
                      activeforeground=CYAN, command=self._update_file_label).pack(side="left")
        
        # File selection
        file_box = tk.Frame(top_panel, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER_LT)
        file_box.pack(fill="x")
        
        self.file_label_title = tk.Label(file_box, text="📦 FIRMWARE FILE (.BIN)", font=F(11, "bold"), fg=UPDATE_COLOR, bg=SURFACE)
        self.file_label_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        file_inner = tk.Frame(file_box, bg=SURFACE)
        file_inner.pack(fill="x", padx=15, pady=(0, 10))
        
        tk.Button(file_inner, text="📁 BROWSE FILE", command=self._browse,
                 bg=CYAN_DIM, fg=CYAN, font=F(10, "bold"), padx=20, pady=6, 
                 relief="flat", cursor="hand2").pack(side="left", padx=(0, 10))
        
        self.file_lbl = tk.Label(file_inner, text="No file selected", font=F(10), fg=WHITE_40, bg=SURFACE)
        self.file_lbl.pack(side="left", fill="x", expand=True)
        
        # ===== MIDDLE SECTION - Progress + Button =====
        middle_panel = tk.Frame(main_frame, bg=BG)
        middle_panel.pack(fill="both", expand=True, padx=25, pady=(10, 15))
        
        # Progress container
        progress_box = tk.Frame(middle_panel, bg=SURFACE2, highlightthickness=1, highlightbackground=BORDER_LT)
        progress_box.pack(fill="both",  side="left", padx=(0, 15) , anchor="n")
        
        tk.Label(progress_box, text="⏱️  PROGRESS", font=F(11, "bold"), fg=CYAN, bg=SURFACE2).pack(padx=15, pady=(10, 0), anchor="center")
        
        prog_inner = tk.Frame(progress_box, bg=SURFACE2)
        prog_inner.pack(fill="both", expand=True, padx=15, pady=15)
        
        prog_left = tk.Frame(prog_inner, bg=SURFACE2)
        prog_left.pack(side="left", padx=(0, 20))
        
        self.arc = ArcRing(prog_left, 160, UPDATE_COLOR)
        self.arc.pack(side="left" , anchor="s")
        
        prog_right = tk.Frame(prog_inner, bg=SURFACE2)
        prog_right.pack(side="left", fill="both", expand=True)
        
        tk.Label(prog_right, text="Elapsed Time", font=F(10, "bold"), fg=WHITE_70, bg=SURFACE2).pack(anchor="w")
        self.timer_lbl = tk.Label(prog_right, text="00:00", font=F(40, "bold"), fg=CYAN, bg=SURFACE2)
        self.timer_lbl.pack(anchor="w", pady=(5, 10))
        tk.Label(prog_right, text="Status: Ready", font=F(10), fg=WHITE_40, bg=SURFACE2).pack(anchor="w")
        
        # Button + Log
        button_log = tk.Frame(middle_panel, bg=BG)
        button_log.pack(fill="both", expand=True, side="left")
        
        # START button
        self.start_btn = tk.Button(button_log, text="START", font=F(16, "bold"), bg=UPDATE_COLOR, fg=BLACK,
                 activebackground=CYAN_BRIGHT, command=self._start, relief="flat", 
                 cursor="hand2", highlightthickness=0)
        self.start_btn.pack(fill="both", expand=True, padx=(0, 10))
        
        # Log
        log_box = tk.Frame(button_log, bg=BG)
        log_box.pack(fill="both", expand=True)
        
        tk.Label(log_box, text="📋 LOG", font=F(10, "bold"), fg=CYAN, bg=BG).pack(anchor="w", pady=(0, 5))
        
        self.log = tk.Text(log_box, height=10, bg=SURFACE2, fg=CYAN, font=FM(9),
                          insertbackground=CYAN, highlightthickness=1, highlightbackground=BORDER_LT)
        self.log.pack(fill="both", expand=True)
        self.log.config(wrap="word")
        
        self.log.insert("end", "? Ready for firmware update\nSelect COM port and BIN file to begin\n\n")
    
    def _update_file_label(self):
        """Update file label based on selected update type"""
        if self._update_type.get() == "assets":
            self.file_label_title.config(text="💾 ASSETS FILE (.BIN)")
        else:
            self.file_label_title.config(text="📲 FIRMWARE FILE (.BIN)")
        self._file = None
        self.file_lbl.config(text="No file selected", fg=WHITE_40)
        self.log.insert("end", f"? Switched to {self._update_type.get()} update mode\n")
        self.log.see("end")
    
    def _scan_ports(self):
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for p in ports:
            menu.add_command(label=p, command=lambda x=p: self._port.set(x))
        if ports:
            self._port.set(ports[0])
            self.log.insert("end", f"? Found {len(ports)} COM port(s)\n")
        else:
            self.log.insert("end", "? No COM ports found\n")
    
    def _browse(self):
        path = filedialog.askopenfilename(filetypes=[("BIN", "*.bin")])
        if path:
            self._file = path
            filename = os.path.basename(path)
            self.file_lbl.config(text=filename, fg=CYAN)
            self.log.insert("end", f"? Selected: {filename}\n")
            self.log.see("end")
    
    def _start(self):
        if not self._port.get() or "Select" in self._port.get():
            messagebox.showerror("Error", "Select a COM port!")
            return
        if not self._file:
            messagebox.showerror("Error", "Select a binary file!")
            return
        
        self.start_btn.config(state="disabled")
        self._uploading = True
        self._cancel_event.clear()
        self._updater = None
        self.arc.set_pct(0)
        self.log.delete("1.0", "end")
        self._start_time = time.time()
        self._tick()
        
        update_type_display = "Firmware" if self._update_type.get() == "firmware" else "Assets"
        self.log.insert("end", f"🚀 Starting {update_type_display.lower()} update...\n")
        self.log.insert("end", f"📡 COM Port: {self._port.get()}\n")
        self.log.insert("end", f"📦 File: {os.path.basename(self._file)}\n")
        self.log.insert("end", f"🔧 Update Type: {update_type_display}\n\n")
        
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()
    
    def _worker(self):
        try:
            updater = HykonUpdater(self._port.get())
            self._updater = updater
            updater.run_update(
                self._file,
                progress_callback=self._progress,
                done_callback=self._done,
                update_type=self._update_type.get()
            )
        except Exception as e:
            if not self._cancel_event.is_set() and self.winfo_exists():
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self._updater = None
            self._uploading = False
            if self.winfo_exists():
                self.after(0, lambda: self.start_btn.config(state="normal"))
    
    def _progress(self, val):
        if isinstance(val, str):
            self.after(0, lambda: self.log.insert("end", val + "\n"))
            self.after(0, lambda: self.log.see("end"))
        else:
            self.after(0, self.arc.set_pct, val)
    
    def _done(self, msg):
        self._uploading = False
        if self.winfo_exists():
            self.after(0, self.arc.set_pct, 100)
            self.after(0, lambda: self.start_btn.config(state="normal"))
            self.after(0, lambda: messagebox.showinfo("Log", msg))
            self.after(0, lambda: self.log.insert("end", f"\n✅ {msg}\n"))
    
    def _tick(self):
        if not self._uploading:
            return
        s = int(time.time() - self._start_time)
        self.timer_lbl.config(text=f"{s//60:02d}:{s%60:02d}")
        self.after(1000, self._tick)
    
    def cancel_update(self):
        if self._uploading and self._updater:
            self._cancel_event.set()
            self.log.insert("end", "? Cancel requested. Stopping update...\n")
            self.log.see("end")
            self._updater.cancel()
            self._uploading = False

    def go_home(self):
        if self._uploading:
            self.cancel_update()
        self.parent.deiconify()  # Show mode selection window
        self.destroy()

class ServiceWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Hykon - Service Reset")
        self.geometry("1366x750")
        self.minsize(1100, 650)
        self.configure(bg=BG)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.go_home)
        
        self._port = tk.StringVar(value="Select COM Port")
        self._uploading = False
        self._start_time = None
        
        self.build_ui()
        self._scan_ports()
    
    def build_ui(self):
        main_frame = tk.Frame(self, bg=BG)
        main_frame.pack(fill="both", expand=True)
        
        # ===== HEADER =====
        header = tk.Frame(main_frame, bg=BG)
        header.pack(fill="x", padx=25, pady=(15, 10))
        
        left_h = tk.Frame(header, bg=BG)
        left_h.pack(side="left")
        tk.Label(left_h, text="🛠️  SERVICE RESET", font=F(28, "bold"), fg=SERVICE_COLOR, bg=BG).pack(anchor="w")
        tk.Label(left_h, text="Clear service warning and maintenance indicators", font=F(11), fg=WHITE_70, bg=BG).pack(anchor="w")
        
        right_h = tk.Frame(header, bg=BG)
        right_h.pack(side="right")
        tk.Label(right_h, text="● READY", font=F(11, "bold"), fg=GREEN, bg=BG).pack(anchor="e", padx=(0, 15))
        tk.Button(right_h, text="🏠 HOME", command=self.go_home,
                 bg=SERVICE_COLOR, fg=BLACK, font=F(10, "bold"), padx=15, pady=5,
                 relief="flat", cursor="hand2").pack(anchor="e")
        
        # ===== TOP SECTION - Connection =====
        top_panel = tk.Frame(main_frame, bg=BG)
        top_panel.pack(fill="x", padx=25, pady=(10, 15))
        
        conn_box = tk.Frame(top_panel, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER_LT)
        conn_box.pack(fill="x")
        
        tk.Label(conn_box, text="📡 COM PORT", font=F(11, "bold"), fg=SERVICE_COLOR, bg=SURFACE).pack(anchor="w", padx=15, pady=(10, 5))
        
        port_inner = tk.Frame(conn_box, bg=SURFACE)
        port_inner.pack(fill="x", padx=15, pady=(0, 10))
        
        self.port_menu = tk.OptionMenu(port_inner, self._port, "")
        self.port_menu.config(bg=SURFACE2, fg=CYAN, font=F(11, "bold"), activebackground=CYAN_DIM)
        self.port_menu.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        tk.Button(port_inner, text="🔄 REFRESH", command=self._scan_ports,
                 bg=SERVICE_COLOR, fg=BLACK, font=F(10, "bold"), padx=20, pady=6, 
                 relief="flat", cursor="hand2").pack(side="right")
        
        # ===== MIDDLE SECTION - Progress + Button =====
        middle_panel = tk.Frame(main_frame, bg=BG)
        middle_panel.pack(fill="both", expand=True, padx=25, pady=(10, 15))
        
        # Progress container
        progress_box = tk.Frame(middle_panel, bg=SURFACE2, highlightthickness=1, highlightbackground=BORDER_LT)
        progress_box.pack(fill="both", expand=True, side="left", padx=(0, 15))
        
        tk.Label(progress_box, text="⏱️  PROGRESS", font=F(11, "bold"), fg=CYAN, bg=SURFACE2).pack(padx=15, pady=(10, 0), anchor="center")
        
        prog_inner = tk.Frame(progress_box, bg=SURFACE2)
        prog_inner.pack(fill="both", expand=True, padx=15, pady=15)
        
        prog_left = tk.Frame(prog_inner, bg=SURFACE2)
        prog_left.pack(side="left", padx=(0, 20))
        
        self.arc = ArcRing(prog_left, 160, SERVICE_COLOR)
        self.arc.pack()
        
        prog_right = tk.Frame(prog_inner, bg=SURFACE2)
        prog_right.pack(side="left", fill="both", expand=True)
        
        tk.Label(prog_right, text="Elapsed Time", font=F(10, "bold"), fg=WHITE_70, bg=SURFACE2).pack(anchor="w")
        self.timer_lbl = tk.Label(prog_right, text="00:00", font=F(40, "bold"), fg=CYAN, bg=SURFACE2)
        self.timer_lbl.pack(anchor="w", pady=(5, 10))
        tk.Label(prog_right, text="Status: Ready", font=F(10), fg=WHITE_40, bg=SURFACE2).pack(anchor="w")
        
        # Button + Log
        button_log = tk.Frame(middle_panel, bg=BG)
        button_log.pack(fill="both", expand=True, side="left")
        
        # START button
        self.start_btn = tk.Button(button_log, text="START", font=F(16, "bold"), bg=SERVICE_COLOR, fg=WHITE,
                 activebackground=AMBER, command=self._start, relief="flat", 
                 cursor="hand2", highlightthickness=0)
        self.start_btn.pack(fill="both", expand=True, padx=(0, 10))
        
        # Log
        log_box = tk.Frame(button_log, bg=BG)
        log_box.pack(fill="both", expand=True)
        
        tk.Label(log_box, text="📋 LOG", font=F(10, "bold"), fg=CYAN, bg=BG).pack(anchor="w", pady=(0, 5))
        
        self.log = tk.Text(log_box, height=10, bg=SURFACE2, fg=CYAN, font=FM(9),
                          insertbackground=CYAN, highlightthickness=1, highlightbackground=BORDER_LT)
        self.log.pack(fill="both", expand=True)
        self.log.config(wrap="word")
        
        self.log.insert("end", "? Ready for service reset\nSelect COM port to begin\n\n")
    
    def _scan_ports(self):
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for p in ports:
            menu.add_command(label=p, command=lambda x=p: self._port.set(x))
        if ports:
            self._port.set(ports[0])
            self.log.insert("end", f"? Found {len(ports)} COM port(s)\n")
        else:
            self.log.insert("end", "? No COM ports found\n")
    
    def _start(self):
        if not self._port.get() or "Select" in self._port.get():
            messagebox.showerror("Error", "Select a COM port!")
            return
        
        self.start_btn.config(state="disabled")
        self._uploading = True
        self.arc.set_pct(0)
        self.log.delete("1.0", "end")
        self._start_time = time.time()
        self._tick()
        
        self.log.insert("end", f"🚀 Starting service reset...\n")
        self.log.insert("end", f"📡 COM Port: {self._port.get()}\n\n")
        
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()
    
    def _worker(self):
        try:
            clearer = ServiceClearer(self._port.get())
            clearer.run_clear(
                progress_callback=self._progress,
                done_callback=self._done
            )
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.after(0, lambda: self.start_btn.config(state="normal"))
    
    def _progress(self, val):
        self.after(0, lambda: self.log.insert("end", val + "\n"))
        self.after(0, lambda: self.log.see("end"))
    
    def _done(self, msg):
        self._uploading = False
        self.after(0, self.arc.set_pct, 100)
        self.after(0, lambda: self.start_btn.config(state="normal"))
        self.after(0, lambda: messagebox.showinfo("Log", msg))
        self.after(0, lambda: self.log.insert("end", f"\n✅ {msg}\n"))
    
    def _tick(self):
        if not self._uploading:
            return
        s = int(time.time() - self._start_time)
        self.timer_lbl.config(text=f"{s//60:02d}:{s%60:02d}")
        self.after(1000, self._tick)
    
    def go_home(self):
        self.parent.deiconify()  # Show mode selection window
        self.destroy()

# --------------------- ODOMETER RESET WINDOW ---------------------
class OdometerWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Hykon - Odometer Reset")
        self.geometry("1366x750")
        self.minsize(1100, 650)
        self.configure(bg=BG)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.go_home)
        
        self._port = tk.StringVar(value="Select COM Port")
        self._uploading = False
        self._start_time = None
        
        self.build_ui()
        self._scan_ports()
    
    def build_ui(self):
        main_frame = tk.Frame(self, bg=BG)
        main_frame.pack(fill="both", expand=True)
        
        # ===== HEADER =====
        header = tk.Frame(main_frame, bg=BG)
        header.pack(fill="x", padx=25, pady=(15, 10))
        
        left_h = tk.Frame(header, bg=BG)
        left_h.pack(side="left")
        tk.Label(left_h, text="📊 ODOMETER RESET", font=F(28, "bold"), fg=GREEN, bg=BG).pack(anchor="w")
        tk.Label(left_h, text="Clear odometer reading and reset mileage", font=F(11), fg=WHITE_70, bg=BG).pack(anchor="w")
        
        right_h = tk.Frame(header, bg=BG)
        right_h.pack(side="right")
        tk.Label(right_h, text="● READY", font=F(11, "bold"), fg=GREEN, bg=BG).pack(anchor="e", padx=(0, 15))
        tk.Button(right_h, text="🏠 HOME", command=self.go_home,
                 bg=GREEN, fg=BLACK, font=F(10, "bold"), padx=15, pady=5,
                 relief="flat", cursor="hand2").pack(anchor="e")
        
        # ===== TOP SECTION - Connection =====
        top_panel = tk.Frame(main_frame, bg=BG)
        top_panel.pack(fill="x", padx=25, pady=(10, 15))
        
        conn_box = tk.Frame(top_panel, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER_LT)
        conn_box.pack(fill="x")
        
        tk.Label(conn_box, text="📡 COM PORT", font=F(11, "bold"), fg=GREEN, bg=SURFACE).pack(anchor="w", padx=15, pady=(10, 5))
        
        port_inner = tk.Frame(conn_box, bg=SURFACE)
        port_inner.pack(fill="x", padx=15, pady=(0, 10))
        
        self.port_menu = tk.OptionMenu(port_inner, self._port, "")
        self.port_menu.config(bg=SURFACE2, fg=CYAN, font=F(11, "bold"), activebackground=CYAN_DIM)
        self.port_menu.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        tk.Button(port_inner, text="🔄 REFRESH", command=self._scan_ports,
                 bg=GREEN, fg=BLACK, font=F(10, "bold"), padx=20, pady=6, 
                 relief="flat", cursor="hand2").pack(side="right")
        
        # ===== MIDDLE SECTION - Progress + Button =====
        middle_panel = tk.Frame(main_frame, bg=BG)
        middle_panel.pack(fill="both", expand=True, padx=25, pady=(10, 15))
        
        # Progress container
        progress_box = tk.Frame(middle_panel, bg=SURFACE2, highlightthickness=1, highlightbackground=BORDER_LT)
        progress_box.pack(fill="both", expand=True, side="left", padx=(0, 15))
        
        tk.Label(progress_box, text="⏱️  PROGRESS", font=F(11, "bold"), fg=CYAN, bg=SURFACE2).pack(padx=15, pady=(10, 0), anchor="center")
        
        prog_inner = tk.Frame(progress_box, bg=SURFACE2)
        prog_inner.pack(fill="both", expand=True, padx=15, pady=15)
        
        prog_left = tk.Frame(prog_inner, bg=SURFACE2)
        prog_left.pack(side="left", padx=(0, 20))
        
        self.arc = ArcRing(prog_left, 160, GREEN)
        self.arc.pack()
        
        prog_right = tk.Frame(prog_inner, bg=SURFACE2)
        prog_right.pack(side="left", fill="both", expand=True)
        
        tk.Label(prog_right, text="Elapsed Time", font=F(10, "bold"), fg=WHITE_70, bg=SURFACE2).pack(anchor="w")
        self.timer_lbl = tk.Label(prog_right, text="00:00", font=F(40, "bold"), fg=CYAN, bg=SURFACE2)
        self.timer_lbl.pack(anchor="w", pady=(5, 10))
        tk.Label(prog_right, text="Status: Ready", font=F(10), fg=WHITE_40, bg=SURFACE2).pack(anchor="w")
        
        # Button + Log
        button_log = tk.Frame(middle_panel, bg=BG)
        button_log.pack(fill="both", expand=True, side="left")
        
        # START button
        self.start_btn = tk.Button(button_log, text="▶\nSTART", font=F(16, "bold"), bg=GREEN, fg=BLACK,
                 activebackground="#00F0A9", command=self._start, relief="flat", 
                 cursor="hand2", highlightthickness=0)
        self.start_btn.pack(fill="both", expand=True, padx=(0, 10))
        
        # Log
        log_box = tk.Frame(button_log, bg=BG)
        log_box.pack(fill="both", expand=True)
        
        tk.Label(log_box, text="📋 LOG", font=F(10, "bold"), fg=CYAN, bg=BG).pack(anchor="w", pady=(0, 5))
        
        self.log = tk.Text(log_box, height=10, bg=SURFACE2, fg=CYAN, font=FM(9),
                          insertbackground=CYAN, highlightthickness=1, highlightbackground=BORDER_LT)
        self.log.pack(fill="both", expand=True)
        self.log.config(wrap="word")
        
        self.log.insert("end", "📊 Ready for odometer reset\nSelect COM port to begin\n\n")
    
    def _scan_ports(self):
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for p in ports:
            menu.add_command(label=p, command=lambda x=p: self._port.set(x))
        if ports:
            self._port.set(ports[0])
            self.log.insert("end", f"✓ Found {len(ports)} COM port(s)\n")
        else:
            self.log.insert("end", "✗ No COM ports found\n")
    
    def _verify_password(self):
        """Verify password before allowing odometer reset"""
        from tkinter.simpledialog import askstring
        
        password = askstring(
            "🔐 Password Required",
            "Enter password to proceed with odometer reset:",
            show="*"
        )
        
        if password is None:  # User clicked Cancel
            return False
        
        if password == "hykon123":
            return True
        else:
            messagebox.showerror("Error", "❌ Incorrect password!")
            return False
    
    def _start(self):
        if not self._port.get() or "Select" in self._port.get():
            messagebox.showerror("Error", "Select a COM port!")
            return
        
        # Verify password before proceeding
        if not self._verify_password():
            return
        
        self.start_btn.config(state="disabled")
        self._uploading = True
        self.arc.set_pct(0)
        self.log.delete("1.0", "end")
        self._start_time = time.time()
        self._tick()
        
        self.log.insert("end", f"🚀 Starting odometer reset...\n")
        self.log.insert("end", f"📡 COM Port: {self._port.get()}\n\n")
        
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()
    
    def _worker(self):
        try:
            clearer = OdometerClearer(self._port.get())
            clearer.run_clear(
                progress_callback=self._progress,
                done_callback=self._done
            )
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.after(0, lambda: self.start_btn.config(state="normal"))
    
    def _progress(self, val):
        self.after(0, lambda: self.log.insert("end", val + "\n"))
        self.after(0, lambda: self.log.see("end"))
    
    def _done(self, msg):
        self._uploading = False
        self.after(0, self.arc.set_pct, 100)
        self.after(0, lambda: self.start_btn.config(state="normal"))
        self.after(0, lambda: messagebox.showinfo("Log", msg))
        self.after(0, lambda: self.log.insert("end", f"\n✅ {msg}\n"))
    
    def _tick(self):
        if not self._uploading:
            return
        s = int(time.time() - self._start_time)
        self.timer_lbl.config(text=f"{s//60:02d}:{s%60:02d}")
        self.after(1000, self._tick)
    
    def go_home(self):
        self.parent.deiconify()  # Show mode selection window
        self.destroy()

if __name__ == "__main__":
    mode_window = ModeSelectionWindow()
    mode_window.mainloop()
