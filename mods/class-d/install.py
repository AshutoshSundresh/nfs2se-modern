#!/usr/bin/env python3
"""One-command install/uninstall for the whole Class D feature.

Manages three files reversibly:
  - nfs2sen.exe       (Class D picker entry + bonus cars, via patch_class_d.py)
  - FEDATA/PC/ART/MAIN.QFS   (adds the 'clsd' preview card)
  - FEDATA/PC/TEXT/TEXT.ENG  (adds the 'class D' label)

Usage (from project root):
  python mods/class-d/install.py status
  python mods/class-d/install.py apply
  python mods/class-d/install.py revert
"""
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable


def run(args):
    print("  $", " ".join(str(a) for a in args))
    r = subprocess.run([PY, *[str(a) for a in args]])
    return r.returncode


def bonus_state():
    """Return current nfs2sen.exe state as reported by patch_class_d."""
    subprocess.run([PY, HERE / "patch_class_d.py", "status"])


def apply():
    print("[1/3] nfs2sen.exe")
    # combined patcher needs the pristine original; revert the older bonus-only mod if present
    run([HERE.parent / "bonus-ai-cars" / "patch_bonus_ai_cars.py", "revert"])
    rc = run([HERE / "patch_class_d.py", "apply"])
    if rc:
        print("  exe patch failed - aborting"); return rc
    print("[2/3] MAIN.QFS (clsd card)")
    run([HERE / "install_mainqfs.py", "apply"])
    print("[3/3] TEXT.ENG (class D label)")
    run([HERE / "tools" / "text_patch.py", "apply"])
    print("Done. Launch nfs2sen.exe and pick opponents -> Class D.")
    return 0


def revert():
    print("[1/3] nfs2sen.exe -> original")
    run([HERE / "patch_class_d.py", "revert"])
    print("[2/3] MAIN.QFS -> original")
    run([HERE / "install_mainqfs.py", "revert"])
    print("[3/3] TEXT.ENG -> original")
    run([HERE / "tools" / "text_patch.py", "revert"])
    print("Reverted all Class D changes.")
    return 0


def status():
    run([HERE / "patch_class_d.py", "status"])
    run([HERE / "install_mainqfs.py", "status"])
    run([HERE / "tools" / "text_patch.py", "status"])
    return 0


if __name__ == "__main__":
    act = sys.argv[1] if len(sys.argv) > 1 else "status"
    raise SystemExit({"apply": apply, "revert": revert, "status": status}.get(act, status)())
