#!/usr/bin/env python3
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

def export_slides_via_com(pptx_path, slides_dir):
    from win32com.client import Dispatch

    # Launch PowerPoint
    ppt_app = Dispatch("PowerPoint.Application")

    # Minimize the PowerPoint window so it never pops up
    try:
        from win32com.client import constants
        ppt_app.WindowState = constants.ppWindowMinimized
    except Exception:
        pass

    # 1) Open with positional args: (FileName, ReadOnly, Untitled, WithWindow)
    pres = ppt_app.Presentations.Open(pptx_path,  # FileName
                                       True,        # ReadOnly
                                       False,       # Untitled (don’t prompt to save)
                                       False)       # WithWindow (no visible slide window)

    # Count slides
    slide_count = pres.Slides.Count
    os.makedirs(slides_dir, exist_ok=True)

    # 2) Export each slide
    for i in range(1, slide_count + 1):
        out_path = os.path.join(slides_dir, f"slide{i}.png")
        try:
            pres.Slides.Item(i).Export(out_path, "PNG")
            print(f"✅ Slide {i} → {out_path}")
        except Exception as ex:
            print(f"❌ Failed to export slide {i}: {ex}")

    # Clean up
    pres.Close()
    ppt_app.Quit()
    return slide_count

def main():
    if not sys.platform.startswith("win"):
        messagebox.showerror("Unsupported", "This script only runs on Windows with PowerPoint installed.")
        return

    root = tk.Tk(); root.withdraw()

    pptx = filedialog.askopenfilename(
        title="Select a .pptx file",
        filetypes=[("PowerPoint","*.pptx")]
    )
    if not pptx:
        messagebox.showinfo("Cancelled", "No file selected.")
        return

    outdir = filedialog.askdirectory(
        title="Select folder to save slides"
    )
    if not outdir:
        messagebox.showinfo("Cancelled", "No folder selected.")
        return

    slides_dir = os.path.join(outdir, "slides")

    try:
        count = export_slides_via_com(pptx, slides_dir)
        messagebox.showinfo("Done", f"Exported {count} slides to:\n{slides_dir}")
    except Exception as e:
        messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    main()
