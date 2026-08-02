import os
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from pydub import AudioSegment
except ImportError:
    raise SystemExit("Missing dependency 'pydub'. Install it with: pip install pydub")


SUPPORTED_TYPES = [
    ("Audio Files", "*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.wma *.aiff *.aif *.au"),
    ("All Files", "*.*"),
]

FFMPEG_INSTALL_MSG = (
    "FFmpeg (or the ffplay tool that ships with it) was not found on this system.\n\n"
    "This app needs FFmpeg to load/export most audio formats (mp3, m4a, aac, wma, "
    "etc.) and to play previews.\n\n"
    "How to install:\n"
    "  Windows:  Download 'ffmpeg-release-essentials.zip' from\n"
    "            https://www.gyan.dev/ffmpeg/builds/, unzip it,\n"
    "            and add its 'bin' folder to your PATH.\n"
    "  macOS:    brew install ffmpeg\n"
    "  Linux:    sudo apt install ffmpeg\n\n"
    "After installing, restart this app."
)

# Suppress the console window ffplay/ffmpeg would otherwise flash open on Windows.
_SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

if sys.platform == "win32":
    import winreg


def _registry_path_dirs():
    """Read the PATH value straight from the Windows registry (both the
    per-user and system-wide entries).

    A newly launched process only sees the PATH that existed at the moment it
    was spawned. On a freshly downloaded, SmartScreen-flagged .exe, that
    inherited PATH can be stale even if the user added FFmpeg to PATH earlier
    -- closing and relaunching the app then "fixes" it because the *new*
    process picks up a fresher inherited PATH. Reading directly from the
    registry sidesteps that entirely, since it always reflects the current
    value regardless of when this process started.
    """
    if sys.platform != "win32":
        return []

    dirs = []
    registry_locations = [
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ]
    for hive, subkey in registry_locations:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
                dirs.extend(p for p in value.split(os.pathsep) if p)
        except OSError:
            continue
    return dirs


def find_executable(name):
    """Locate an executable, checking this process's own PATH first and
    falling back to a live read of the Windows registry's PATH if not found
    there. This makes detection resilient to a stale inherited environment."""
    found = shutil.which(name)
    if found:
        return found

    reg_dirs = _registry_path_dirs()
    if not reg_dirs:
        return None

    combined_path = os.pathsep.join(reg_dirs)
    return shutil.which(name, path=combined_path)


def ffmpeg_available():
    """Check if ffmpeg, ffprobe, and ffplay are all available (via PATH or,
    as a fallback, the Windows registry)."""
    return all(find_executable(tool) is not None for tool in ("ffmpeg", "ffprobe", "ffplay"))


def configure_pydub_paths():
    """Point pydub directly at resolved ffmpeg/ffprobe paths (rather than letting
    it resolve bare 'ffmpeg'/'ffprobe' names itself at call time). This makes
    audio loading and exporting immune to the same stale-PATH issue that can
    otherwise affect a freshly launched, SmartScreen-flagged .exe."""
    ffmpeg_path = find_executable("ffmpeg")
    ffprobe_path = find_executable("ffprobe")
    if ffmpeg_path:
        AudioSegment.converter = ffmpeg_path
    if ffprobe_path:
        AudioSegment.ffprobe = ffprobe_path


def resource_path(relative_path):
    """Resolve a path to a bundled resource (e.g. icon.ico), whether running as a
    plain script or as a PyInstaller-built exe (which unpacks bundled files into a
    temporary folder referenced by sys._MEIPASS)."""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class AudioDbTweakerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Audio Decibel Adjuster")
        self.geometry("520x420")
        self.resizable(False, False)

        # Window / taskbar icon (Windows uses .ico; other platforms just skip
        # this if the file isn't present or the format isn't supported).
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass

        # Use the native Windows visual-style theme when available, so buttons,
        # entries, etc. render with real OS-drawn rounded corners on Windows 11.
        style = ttk.Style(self)
        for theme in ("vista", "winnative", "clam"):
            try:
                style.theme_use(theme)
                break
            except tk.TclError:
                continue

        self.file_path = None
        self.original_audio = None   # untouched AudioSegment
        self.modified_audio = None   # AudioSegment with gain applied
        self.db_change = 0

        self._play_proc = None       # subprocess.Popen running ffplay
        self._play_tempfile = None   # temp wav file path being played

        self._build_ui()

    # ---------- UI ----------

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}

        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        # --- File selection ---
        ttk.Label(main_frame, text="Audio File").pack(anchor="w", **pad)

        file_row = ttk.Frame(main_frame)
        file_row.pack(fill="x", **pad)

        self.file_var = tk.StringVar(value="No file selected")
        self.file_entry = ttk.Entry(file_row, textvariable=self.file_var, state="readonly")
        self.file_entry.pack(side="left", fill="x", expand=True)

        ttk.Button(file_row, text="Browse...", command=self.upload_file).pack(side="left", padx=(6, 0))

        # --- dB control ---
        ttk.Label(main_frame, text="Volume Adjustment").pack(anchor="w", **pad)

        db_row = ttk.Frame(main_frame)
        db_row.pack(**pad)

        ttk.Button(db_row, text="− 1 dB", width=10, command=self.decrease_db).pack(side="left", padx=6)

        self.db_var = tk.StringVar(value="0 dB")
        ttk.Label(
            db_row, textvariable=self.db_var, width=8, anchor="center", font=("Segoe UI", 13, "bold")
        ).pack(side="left", padx=10)

        ttk.Button(db_row, text="+ 1 dB", width=10, command=self.increase_db).pack(side="left", padx=6)

        ttk.Button(main_frame, text="Reset to 0 dB", command=self.reset_db).pack(pady=(0, 6))

        ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=10)

        # --- Preview ---
        ttk.Label(main_frame, text="Preview").pack(anchor="w", **pad)

        button_row = ttk.Frame(main_frame)
        button_row.pack(fill="x", pady=6)

        self.play_orig_btn = ttk.Button(
            button_row, text="Play Original", command=self.play_original, state="disabled"
        )
        self.play_orig_btn.pack(side="left", padx=(12, 6))

        self.play_mod_btn = ttk.Button(
            button_row, text="Play Modified", command=self.play_modified, state="disabled"
        )
        self.play_mod_btn.pack(side="left", padx=6)

        self.stop_btn = ttk.Button(
            button_row, text="Stop", command=self.stop_playback, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=6)

        ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=10)

        # --- Export ---
        self.export_btn = ttk.Button(
            main_frame, text="Save Modified Audio As...", command=self.export_file
        )
        self.export_btn.pack(fill="x", **pad)

        # --- Status ---
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(
            main_frame, textvariable=self.status_var, foreground="gray",
            wraplength=460, justify="left",
        ).pack(anchor="w", **pad)

    # ---------- File handling ----------

    def upload_file(self):
        path = filedialog.askopenfilename(title="Select an audio file", filetypes=SUPPORTED_TYPES)
        if not path:
            return

        self.status_var.set("Loading audio...")
        self.update_idletasks()

        try:
            audio = AudioSegment.from_file(path)
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Could not load audio file:\n{e}\n\nMake sure FFmpeg is installed and on your PATH.",
            )
            self.status_var.set("Ready")
            return

        self.stop_playback()
        self.file_path = path
        self.original_audio = audio
        self.modified_audio = audio
        self.db_change = 0
        self.db_var.set("0 dB")

        self.file_var.set(os.path.basename(path))
        self.play_orig_btn.config(state="normal")
        self.play_mod_btn.config(state="normal")
        self.stop_btn.config(state="normal")
        self.status_var.set(f"Loaded: {os.path.basename(path)}")

    # ---------- dB adjustment ----------

    def increase_db(self):
        if self.original_audio is None:
            return
        self.db_change += 1
        self._apply_gain()

    def decrease_db(self):
        if self.original_audio is None:
            return
        self.db_change -= 1
        self._apply_gain()

    def reset_db(self):
        if self.original_audio is None:
            return
        self.db_change = 0
        self._apply_gain()

    def _apply_gain(self):
        self.db_var.set(f"{self.db_change:+d} dB" if self.db_change != 0 else "0 dB")
        self.modified_audio = self.original_audio.apply_gain(self.db_change)
        self.status_var.set(f"Gain set to {self.db_change:+d} dB (not yet saved)")

    # ---------- Playback (via ffplay) ----------

    def play_original(self):
        if self.original_audio is not None:
            self._play_audio(self.original_audio, "original")

    def play_modified(self):
        if self.modified_audio is not None:
            self._play_audio(self.modified_audio, "modified")

    def _play_audio(self, segment, label):
        self.stop_playback()

        ffplay_path = find_executable("ffplay")
        if ffplay_path is None:
            messagebox.showerror(
                "ffplay Not Found",
                "Playback requires 'ffplay', which ships with FFmpeg.\n\n" + FFMPEG_INSTALL_MSG,
            )
            return

        self.status_var.set(f"Playing {label} audio...")

        # Export to a temp WAV file for ffplay to read.
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()
        segment.export(tmp_path, format="wav")
        self._play_tempfile = tmp_path

        try:
            self._play_proc = subprocess.Popen(
                [ffplay_path, "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path],
                creationflags=_SUBPROCESS_FLAGS,
            )
        except Exception as e:
            messagebox.showerror("Playback Error", str(e))
            self.status_var.set("Ready")
            self._cleanup_tempfile()
            return

        threading.Thread(target=self._watch_playback, args=(self._play_proc,), daemon=True).start()

    def _watch_playback(self, proc):
        proc.wait()
        if self._play_proc is proc:
            self._play_proc = None
            self._cleanup_tempfile()
            self.status_var.set("Ready")

    def stop_playback(self):
        if self._play_proc is not None:
            try:
                self._play_proc.terminate()
            except Exception:
                pass
            self._play_proc = None
            self._cleanup_tempfile()
            self.status_var.set("Stopped")

    def _cleanup_tempfile(self):
        if self._play_tempfile and os.path.exists(self._play_tempfile):
            try:
                os.remove(self._play_tempfile)
            except Exception:
                pass
        self._play_tempfile = None

    # ---------- Export ----------

    def export_file(self):
        if self.modified_audio is None:
            messagebox.showinfo("No audio", "Please upload a file first.")
            return

        base_name = os.path.splitext(os.path.basename(self.file_path))[0]
        default_name = f"{base_name}_{self.db_change:+d}db.wav"

        save_path = filedialog.asksaveasfilename(
            title="Save modified audio as",
            initialfile=default_name,
            defaultextension=".wav",
            filetypes=[
                ("WAV", "*.wav"),
                ("MP3", "*.mp3"),
                ("OGG", "*.ogg"),
                ("FLAC", "*.flac"),
                ("All Files", "*.*"),
            ],
        )
        if not save_path:
            return

        fmt = os.path.splitext(save_path)[1][1:].lower() or "wav"
        try:
            self.modified_audio.export(save_path, format=fmt)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")
            return

        self.status_var.set(f"Saved to {save_path}")
        messagebox.showinfo("Saved", f"File saved:\n{save_path}")

    def on_close(self):
        self.stop_playback()
        self.destroy()


def main():
    configure_pydub_paths()

    app = AudioDbTweakerApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)

    if not ffmpeg_available():
        # Force the main window to the front first, then show the warning as its
        # child. Without this, the dialog can occasionally spawn behind the main
        # window (most noticeable in compiled .exe builds), making it look like
        # it "disappeared" until the app is closed.
        app.deiconify()
        app.lift()
        app.attributes("-topmost", True)
        app.after(0, lambda: app.attributes("-topmost", False))
        messagebox.showwarning("FFmpeg Not Found", FFMPEG_INSTALL_MSG, parent=app)

    app.mainloop()

# Hi there.
if __name__ == "__main__":
    main()
