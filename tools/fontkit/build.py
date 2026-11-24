# 비트맵 → 곡선(potrace) → OTF(CFF) / WOFF2
import sys, time, numpy as np, cv2, potrace
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from compose import load, build, BOX

UPM, ASC, DESC = 1000, 880, -120
S = UPM / BOX

def trace(bm, res=272):
    h, w = bm.shape; rh = int(res * h / w)
    b = cv2.resize(bm * 255, (res, rh), interpolation=cv2.INTER_AREA)
    b = cv2.GaussianBlur(b, (3, 3), 0) > 110
    k = w / res
    return potrace.Bitmap(~b).trace(turdsize=8, alphamax=1.0, opticurve=True, opttolerance=0.25), k

PADPX = int(0.15 * BOX)
def draw(pen, paths, k, dx=0):
    X = lambda p: round(p.x * k * S + dx); Y = lambda p: round(ASC - (p.y * k - PADPX) * S)
    for c in paths:
        pen.moveTo((X(c.start_point), Y(c.start_point)))
        for sg in c.segments:
            if sg.is_corner:
                pen.lineTo((X(sg.c), Y(sg.c))); pen.lineTo((X(sg.end_point), Y(sg.end_point)))
            else:
                pen.curveTo((X(sg.c1), Y(sg.c1)), (X(sg.c2), Y(sg.c2)), (X(sg.end_point), Y(sg.end_point)))
        pen.closePath()

def make(glyph_dir, out, family, style="Regular", ps="YW-Handwriting"):
    t0 = time.time()
    g = load(glyph_dir); bms, miss = build(g)
    # 크기 맞추기: 받침 없는 한글의 보통 높이를 칸의 66%로, 가운데로
    from compose import dec, bb
    hs, ha, cys, cxs = [], [], [], []
    for ch, bm in g.items():
        if 0xAC00 <= ord(ch) <= 0xD7A3 and bm.any():
            x0, y0, w, h = bb(bm); ha.append(h); cys.append(y0 + h / 2); cxs.append(x0 + w / 2)
            if dec(ch)[2] == " ": hs.append(h)
    k = min(0.64 * BOX / float(np.median(hs)), 0.86 * BOX / float(np.percentile(ha, 95)))
    cx, cy = float(np.median(cxs)), float(np.median(cys))
    PAD = int(0.15 * BOX); CH = BOX + 2 * PAD
    M = np.float32([[k, 0, BOX / 2 - k * cx], [0, k, BOX * 0.5 - k * cy + PAD]])
    print(f"크기 x{k:.2f}")
    big = lambda bm: np.pad(bm, ((PAD, PAD), (0, 0))).astype(np.float32)
    M2 = M.copy(); M2[1, 2] -= 0  # 입력도 위아래로 늘린 판에 놓음
    bms = {ch: (cv2.warpAffine(big(bm), np.float32([[k, 0, M[0, 2]], [0, k, M[1, 2] - k * PAD]]), (BOX, CH), flags=cv2.INTER_LINEAR) > 0.5).astype(np.uint8) for ch, bm in bms.items()}
    order = [".notdef", "space"]; cmap = {32: "space"}; cs = {}; adv = {".notdef": 500, "space": 280}
    p = T2CharStringPen(500, None); p.moveTo((50, 0)); p.lineTo((450, 0)); p.lineTo((450, 700)); p.lineTo((50, 700)); p.closePath()
    p.moveTo((100, 50)); p.lineTo((100, 650)); p.lineTo((400, 650)); p.lineTo((400, 50)); p.closePath(); cs[".notdef"] = p.getCharString()
    cs["space"] = T2CharStringPen(280, None).getCharString()
    for ch in sorted(bms, key=ord):
        bm = bms[ch]; cp = ord(ch); name = f"uni{cp:04X}" if cp <= 0xFFFF else f"u{cp:05X}"
        hangul = 0xAC00 <= cp <= 0xD7A3 or 0x3131 <= cp <= 0x318E
        paths, k = trace(bm)
        if hangul:
            w, dx = 920, -40
        else:
            xs = np.nonzero(bm.any(0))[0]
            if len(xs) == 0: continue
            lsb, rsb = 45, 45
            dx = lsb - xs[0] * S; w = int((xs[-1] - xs[0]) * S + lsb + rsb)
        pen = T2CharStringPen(w, None); draw(pen, paths, k, dx)
        cs[name] = pen.getCharString(); adv[name] = w; order.append(name); cmap[cp] = name
    fb = FontBuilder(UPM, isTTF=False)
    fb.setupGlyphOrder(order); fb.setupCharacterMap(cmap)
    fb.setupCFF(ps + "-" + style, {"FullName": f"{family} {style}"}, cs, {})
    fb.setupHorizontalMetrics({n: (adv[n], 0) for n in order})
    fb.setupHorizontalHeader(ascent=ASC, descent=DESC)
    fb.setupNameTable({"familyName": family, "styleName": style, "uniqueFontIdentifier": f"{ps}-{style}-1.000",
                       "fullName": f"{family} {style}", "psName": f"{ps}-{style}", "version": "Version 1.000",
                       "copyright": "Copyright 2026 TAi Edutech (002BOOK)", "licenseDescription": "002BOOK 앱 안에서만 쓰는 손글씨 글꼴"})
    fb.setupOS2(sTypoAscender=ASC, sTypoDescender=DESC, usWinAscent=ASC + 40, usWinDescent=-DESC + 40, achVendID="TAIE")
    fb.setupPost(); fb.save(out)
    from fontTools.ttLib import TTFont
    f = TTFont(out); f.flavor = "woff2"; f.save(out.rsplit(".", 1)[0] + ".woff2")
    print(f"글자 {len(order) - 2}개 · 못 만든 글자 {len(miss)} · {time.time() - t0:.0f}초 → {out}")

if __name__ == "__main__":
    make(sys.argv[1] if len(sys.argv) > 1 else "glyphs", sys.argv[2] if len(sys.argv) > 2 else "YW-Test-F.otf",
         sys.argv[3] if len(sys.argv) > 3 else "YW Test F")
