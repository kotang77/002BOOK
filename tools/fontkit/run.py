"""양식 사진 → 손글씨 글꼴 한 번에
사용: python3 run.py --name "002 여중생체" --ps YW-Girl --out out/ 사진1.jpg 사진2.jpg ...
(사진 순서는 상관없음. 쪽은 칸 위치로 알아냄. 6쪽 문장 쓰기는 넣지 않아도 됨)"""
import argparse, os, shutil, subprocess, sys
from scan import scan
from build import make
ap = argparse.ArgumentParser(); ap.add_argument("photos", nargs="+"); ap.add_argument("--name", required=True)
ap.add_argument("--ps", default="YW-Handwriting"); ap.add_argument("--out", default="out")
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); gd = os.path.join(a.out, "glyphs")
shutil.rmtree(gd, ignore_errors=True)
got, rep = scan(a.photos, gd)
for r in rep: print("사진", r)
print(f"양식에서 읽은 글자 {len(got)} / 495")
otf = os.path.join(a.out, a.ps + ".otf"); make(gd, otf, a.name, ps=a.ps)
subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "preview.py"), os.path.abspath(otf), a.name, os.path.join(a.out, "preview.png")], check=True)
print("끝:", otf, otf.replace(".otf", ".woff2"), os.path.join(a.out, "preview.png"))
