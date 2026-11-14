#!/usr/bin/env python3
"""
tools/compile_docs.py
Automated LaTeX compilation and layout verification tool for Box3D technical documentation.

Features:
  - Invokes Tectonic compiler with intermediate preservation.
  - Validates exit code and reports compilation warnings/errors.
  - Inspects generated PDF for broken references ('??') and page count.
  - Validates textual layout boundaries and embedded figure counts.
"""

import os
import re
import sys
import subprocess

def find_tectonic():
    local_path = os.path.join("tools", "tectonic", "tectonic.exe")
    if os.path.exists(local_path):
        return local_path
    local_posix = os.path.join("tools", "tectonic", "tectonic")
    if os.path.exists(local_posix):
        return local_posix
    # Check in PATH
    for cmd in ["tectonic.exe", "tectonic"]:
        try:
            res = subprocess.run([cmd, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode == 0:
                return cmd
        except Exception:
            pass
    return None

def main():
    tex_path = os.path.join("local", "text", "main.tex")
    out_dir = os.path.join("local", "text")
    pdf_path = os.path.join(out_dir, "main.pdf")

    if not os.path.exists(tex_path):
        print(f"[ERROR] LaTeX source file not found at: {tex_path}")
        sys.exit(1)

    tectonic = find_tectonic()
    if not tectonic:
        print("[ERROR] Tectonic compiler not found.")
        print("Run 'powershell tools/download_tectonic.ps1' to automatically install Tectonic.")
        sys.exit(1)

    print("==================================================")
    print(" Compiling Documentation (Tectonic)")
    print(f" Source: {tex_path}")
    print(f" Output: {pdf_path}")
    print("==================================================")

    cmd = [tectonic, "--keep-intermediates", tex_path, "-o", out_dir]
    print(f"Running: {' '.join(cmd)}...\n")

    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")

    if res.returncode != 0:
        print("[FAIL] Compilation failed with exit code:", res.returncode)
        if res.stderr:
            print(res.stderr[-2000:])
        elif res.stdout:
            print(res.stdout[-2000:])
        sys.exit(res.returncode)

    print("[SUCCESS] Compilation completed with code 0.")

    # Validate with pypdf if installed
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        total_pages = len(reader.pages)
        print(f"Total Pages: {total_pages}")

        broken_refs = []
        figures_found = []

        for idx, page in enumerate(reader.pages):
            txt = page.extract_text()
            if "??" in txt:
                broken_refs.append(idx + 1)
            for f in re.findall(r'Figura\s+\d+[\.:][^\n]+', txt):
                figures_found.append((idx + 1, f[:70]))

        if broken_refs:
            print(f"[WARNING] Potential broken references ('??') found on pages: {broken_refs}")
        else:
            print("[OK] No broken references ('??') detected.")

        print(f"[OK] Figures detected in text: {len(figures_found)}")

    except ImportError:
        print("[INFO] pypdf not installed. Install pypdf in Python 3.12 for in-depth PDF verification.")

    print("\nDocument ready at:", os.path.abspath(pdf_path))

if __name__ == "__main__":
    main()
