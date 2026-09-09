"""GUI and optional command-line entry point for the decal artwork cooker."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from cooker_core import VERSION, cook_decal, detect_game, output_filenames, package_stem


class CookerApp(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=18)
        self.master = master
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.last_output: Path | None = None
        self.preview_image: tk.PhotoImage | None = None

        master.title(f"LET IT DIE Decal Artwork Cooker v{VERSION}")
        master.minsize(790, 650)
        master.geometry("860x720")
        self.pack(fill="both", expand=True)

        style = ttk.Style(master)
        if "vista" in style.theme_names():
            style.theme_use("vista")

        ttk.Label(self, text="LET IT DIE Decal Artwork Cooker", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(
            self,
            text="Create and validate the large, medium, and small UPK artwork files from one PNG. "
                 "This tool reads stock donors but never writes to the game.",
            wraplength=800,
        ).pack(anchor="w", pady=(4, 16))

        form = ttk.LabelFrame(self, text="Artwork settings", padding=14)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        self.image_var = tk.StringVar()
        self.identifier_var = tk.StringVar()
        found = detect_game()
        self.game_var = tk.StringVar(value=str(found) if found else "")
        default_output = Path.home() / "Documents" / "LET IT DIE Decal Cooker Output"
        self.output_var = tk.StringVar(value=str(default_output))

        ttk.Label(form, text="Source artwork (PNG)").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=6)
        ttk.Entry(form, textvariable=self.image_var).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Button(form, text="Browse…", command=self.choose_image).grid(row=0, column=2, padx=(8, 0), pady=6)

        ttk.Label(form, text="New decal ID").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=6)
        identifier_entry = ttk.Entry(form, textvariable=self.identifier_var)
        identifier_entry.grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Label(form, text="Example: YIPPEE_KI_YAY").grid(row=1, column=2, sticky="w", padx=(8, 0), pady=6)
        identifier_entry.bind("<KeyRelease>", lambda _event: self.update_preview())

        ttk.Label(form, text="LET IT DIE folder").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=6)
        ttk.Entry(form, textvariable=self.game_var).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Button(form, text="Browse…", command=self.choose_game).grid(row=2, column=2, padx=(8, 0), pady=6)

        ttk.Label(form, text="Output parent folder").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=6)
        ttk.Entry(form, textvariable=self.output_var).grid(row=3, column=1, sticky="ew", pady=6)
        ttk.Button(form, text="Browse…", command=self.choose_output).grid(row=3, column=2, padx=(8, 0), pady=6)

        preview_frame = ttk.LabelFrame(self, text="Automatic outputs", padding=12)
        preview_frame.pack(fill="x", pady=(12, 0))
        self.filename_preview = ttk.Label(
            preview_frame,
            text="Enter a decal ID to preview the three package filenames.",
            justify="left",
            font=("Consolas", 10),
        )
        self.filename_preview.pack(anchor="w")

        action = ttk.Frame(self)
        action.pack(fill="x", pady=14)
        self.cook_button = ttk.Button(action, text="Cook and validate all 3 sizes", command=self.start_cook)
        self.cook_button.pack(side="left")
        self.open_button = ttk.Button(action, text="Open output folder", command=self.open_output, state="disabled")
        self.open_button.pack(side="left", padx=(10, 0))
        self.progress = ttk.Progressbar(action, mode="indeterminate")
        self.progress.pack(side="right", fill="x", expand=True, padx=(20, 0))

        log_frame = ttk.LabelFrame(self, text="Activity", padding=8)
        log_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_frame, height=16, wrap="word", state="disabled", font=("Consolas", 9))
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        ttk.Label(
            self,
            text="Artwork only: database records, effects, pool entries, quests, and ownership are not created. "
                 "Always choose a new ID; stock packages are protected from collisions.",
            foreground="#7b3f00",
            wraplength=800,
        ).pack(anchor="w", pady=(12, 0))
        master.after(100, self.poll_events)

    def choose_image(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.master,
            title="Choose decal artwork",
            filetypes=(("PNG artwork", "*.png"), ("All files", "*.*")),
        )
        if selected:
            self.image_var.set(selected)
            if not self.identifier_var.get().strip():
                self.identifier_var.set(Path(selected).stem)
            self.update_preview()

    def choose_game(self) -> None:
        selected = filedialog.askdirectory(parent=self.master, title="Choose the LET IT DIE installation folder")
        if selected:
            self.game_var.set(selected)

    def choose_output(self) -> None:
        selected = filedialog.askdirectory(parent=self.master, title="Choose where cooked decal folders are created")
        if selected:
            self.output_var.set(selected)

    def update_preview(self) -> None:
        try:
            stem = package_stem(self.identifier_var.get())
            files = output_filenames(self.identifier_var.get())
            text = (
                f"Internal stem: {stem}\n"
                f"Large   512×512  {files[0]}\n"
                f"Medium  256×256  {files[1]}\n"
                f"Small   128×128  {files[2]}"
            )
        except ValueError as error:
            text = str(error)
        self.filename_preview.configure(text=text)

    def append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", str(message).rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def start_cook(self) -> None:
        source = Path(self.image_var.get())
        identifier = self.identifier_var.get()
        game = Path(self.game_var.get())
        output = Path(self.output_var.get())
        self.cook_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        self.progress.start(12)
        self.append_log("Starting isolated artwork cook…")

        def worker() -> None:
            try:
                result = cook_decal(source, identifier, game, output, lambda text: self.events.put(("log", text)))
                self.events.put(("done", result))
            except Exception as error:
                self.events.put(("error", error))

        threading.Thread(target=worker, name="decal-cooker", daemon=True).start()

    def poll_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.append_log(str(value))
                elif kind == "done":
                    self.progress.stop()
                    self.cook_button.configure(state="normal")
                    self.last_output = Path(value)
                    self.open_button.configure(state="normal")
                    self.append_log(f"SUCCESS: {self.last_output}")
                    messagebox.showinfo(
                        "Artwork cooked successfully",
                        "All three UPKs passed validation. A ready-to-share ZIP was created in:\n\n"
                        + str(self.last_output),
                        parent=self.master,
                    )
                elif kind == "error":
                    self.progress.stop()
                    self.cook_button.configure(state="normal")
                    self.append_log(f"ERROR: {value}")
                    messagebox.showerror("Cooking failed", str(value), parent=self.master)
        except queue.Empty:
            pass
        self.master.after(100, self.poll_events)

    def open_output(self) -> None:
        if self.last_output and self.last_output.is_dir():
            os.startfile(self.last_output)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cook one PNG into a three-size LET IT DIE decal artwork set.")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--id", dest="identifier")
    parser.add_argument("--game", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    headless_values = (arguments.image, arguments.identifier, arguments.game, arguments.output)
    if any(value is not None for value in headless_values):
        if not all(value is not None for value in headless_values):
            raise SystemExit("--image, --id, --game, and --output must be supplied together.")
        result = cook_decal(arguments.image, arguments.identifier, arguments.game, arguments.output)
        print(result)
        return
    root = tk.Tk()
    CookerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
