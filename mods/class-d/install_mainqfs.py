"""Reversible install of the clsd-modified MAIN.QFS."""
import sys, shutil, hashlib
from pathlib import Path
GAME=Path("Need For Speed II SE/FEDATA/PC/ART")
LIVE=GAME/"MAIN.QFS"
BAK=GAME/"MAIN.QFS.class-d.bak"
NEW=Path("mods/class-d/MAIN.QFS.new")
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
def main():
    act=sys.argv[1] if len(sys.argv)>1 else "status"
    if act=="apply":
        if not BAK.exists(): shutil.copy2(LIVE,BAK); print("backed up ->",BAK.name)
        shutil.copy2(NEW,LIVE); print("installed clsd MAIN.QFS  sha=%s size=%d"%(sha(LIVE),LIVE.stat().st_size))
    elif act=="revert":
        if BAK.exists(): shutil.copy2(BAK,LIVE); print("reverted MAIN.QFS  sha=%s"%sha(LIVE))
        else: print("no backup found")
    else:
        print("LIVE sha=%s size=%d"%(sha(LIVE),LIVE.stat().st_size))
        print("BAK  ", "present" if BAK.exists() else "absent")
        print("NEW sha=%s size=%d"%(sha(NEW),NEW.stat().st_size))
if __name__=="__main__": main()
