# 양식 글자 비트맵 → KS X 1001 한글 2,350자 + 영문·숫자·기호 + 낱자(ㄱ~ㅎ, ㅏ~ㅣ) 비트맵
import cv2, numpy as np, glob, os
BOX = 408
L = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
V = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
T = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"
VERT = set("ㅏㅐㅑㅒㅓㅔㅕㅖㅣ"); HORI = set("ㅗㅛㅜㅠㅡ"); MIX = set("ㅘㅙㅚㅝㅞㅟㅢ")
DOUBLE = set("ㄲㄸㅃㅆㅉ")

def syl(l, v, t=" "): return chr(0xAC00 + (L.index(l) * 21 + V.index(v)) * 28 + T.index(t))
def dec(ch):
    o = ord(ch) - 0xAC00; return L[o // 588], V[(o % 588) // 28], T[o % 28]
def ks2350():
    out = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            try: out.append(bytes([hi, lo]).decode("euc-kr"))
            except UnicodeDecodeError: pass
    return [c for c in out if 0xAC00 <= ord(c) <= 0xD7A3]

def load(d="glyphs"):
    g = {}
    for f in glob.glob(os.path.join(d, "U*.png")):
        g[chr(int(os.path.basename(f)[1:6], 16))] = (cv2.imread(f, 0) > 127).astype(np.uint8)
    return g

def comps(bm):
    n, lab, st, cen = cv2.connectedComponentsWithStats(bm, 8)
    return [dict(i=i, x=st[i, 0], y=st[i, 1], w=st[i, 2], h=st[i, 3], cx=cen[i, 0], cy=cen[i, 1], m=(lab == i)) for i in range(1, n)]

def bb(bm):
    ys, xs = np.nonzero(bm)
    return xs.min(), ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1

def mask(cs, shape=(BOX, BOX)):
    m = np.zeros(shape, np.uint8)
    for c in cs: m[c["m"]] = 1
    return m

# ── 낱자 분리 ──
def split_vertical(bm):
    """X+세로모음: (자음, 모음). 모음 = 오른쪽 긴 세로획 + 그 곁의 짧은 획"""
    cs = comps(bm); X0, Y0, W, H = bb(bm)
    tall = [c for c in cs if c["h"] > 0.7 * H and c["cx"] > X0 + 0.45 * W and c["w"] < 0.45 * W]
    if not tall: return None
    left = min(c["x"] for c in tall)
    vow = [c for c in cs if c in tall or (c["cx"] >= left - 0.2 * W and c["h"] < 0.5 * H)]
    con = [c for c in cs if c not in vow]
    if not con:                                    # 자음이 모음에 붙어 한 덩어리 → 세로획 왼쪽을 잘라 자음으로
        m = bm.copy(); cut = int(left - 0.08 * W); c_ = np.zeros_like(bm); c_[:, :cut] = m[:, :cut]; v_ = m.copy(); v_[:, :cut] = 0
        return (c_, v_) if c_.sum() > 50 else None
    return mask(con), mask(vow)

def split_horizontal(bm):
    """X+가로모음: (자음, 모음). 모음 = 가장 긴 가로획(아래쪽) + 그 위아래 짧은 획"""
    cs = comps(bm); X0, Y0, W, H = bb(bm)
    wide = [c for c in cs if c["w"] > 0.6 * W and c["h"] < 0.45 * H and c["cy"] > Y0 + 0.4 * H]
    if not wide:
        return None
    line = min(wide, key=lambda c: c["cy"])
    top = line["y"]
    vow = [c for c in cs if c is line or c["cy"] > line["cy"] or (c["y"] + c["h"] >= top - 0.06 * H and c["h"] < 0.3 * H and c["w"] < 0.25 * W and abs(c["cx"] - line["cx"]) < 0.3 * W)]
    con = [c for c in cs if c not in vow]
    if not con: return None
    return mask(con), mask(vow)

def split_mixed_ui(bm):
    """X+ㅢ: 자음 = ㅡ와 ㅣ를 뺀 나머지 (섞인 모음용 자음 모양)"""
    cs = comps(bm); X0, Y0, W, H = bb(bm)
    tall = sorted([c for c in cs if c["h"] > 0.7 * H and c["cx"] > X0 + 0.5 * W], key=lambda c: c["cx"])
    wide = sorted([c for c in cs if c["w"] > 0.45 * W and c["h"] < 0.4 * H and c["cy"] > Y0 + 0.35 * H], key=lambda c: -c["w"])
    rm = set(id(c) for c in tall[-1:] + wide[:1])
    con = [c for c in cs if id(c) not in rm and c["cy"] < Y0 + 0.62 * H]
    return mask(con) if con else None

def strip_ieung(bm, layout):
    """ㅇ+모음 → 모음만. ㅇ = 구멍이 있는 동그란 덩어리(세로: 왼쪽, 가로·섞임: 위)"""
    cs = comps(bm); X0, Y0, W, H = bb(bm)
    def holey(c):
        sub = c["m"][c["y"]:c["y"] + c["h"], c["x"]:c["x"] + c["w"]].astype(np.uint8)
        cnt, hier = cv2.findContours(sub, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        return hier is not None and len(cnt) > 1
    cand = [c for c in cs if 0.5 < c["w"] / max(c["h"], 1) < 2.0 and c["w"] < 0.7 * W and c["h"] < 0.75 * H]
    if layout == "v": cand = [c for c in cand if c["cx"] < X0 + 0.55 * W]
    else: cand = [c for c in cand if c["cy"] < Y0 + 0.55 * H]
    if not cand: return None
    o = max(cand, key=lambda c: (holey(c), -c["cx"] if layout == "v" else -c["cy"]))
    return mask([c for c in cs if c is not o])

def final_from_go(bm):
    """고+받침 → 받침만: ㅗ의 가로획 아래쪽 픽셀"""
    rows = bm.sum(1); X0, Y0, W, H = bb(bm)
    band = range(int(Y0 + 0.25 * H), int(Y0 + 0.7 * H))
    r = max(band, key=lambda y: rows[y])
    thr = rows[r] * 0.35; y = r
    while y < BOX - 1 and rows[y] > thr: y += 1
    out = bm.copy(); out[:y + 3] = 0
    if not out.any(): return None
    _, fy, _, fh = bb(out)
    for c in comps(out):                                # ㅗ 가로획의 부스러기 제거
        if c["y"] <= y + 8 and c["h"] < 0.18 * fh and c["w"] > 1.5 * c["h"]: out[c["m"]] = 0
    return out if out.sum() > 40 else None

def squeeze_top(bm, k=0.68):
    ys = np.nonzero(bm.any(1))[0]
    if len(ys) == 0: return bm
    t = ys[0]; out = np.zeros_like(bm)
    src = bm[t:]; h = max(1, int(src.shape[0] * k))
    out[t:t + h] = cv2.resize(src, (BOX, h), interpolation=cv2.INTER_AREA) > 0
    return out

def put_final(base, f, vert, Ht):
    bx, by, bw, bh = bb(base); fx, fy, fw, fh = bb(f)
    sub = f[fy:fy + fh, fx:fx + fw]
    if fw > 0.85 * bw:                               # 받침이 너무 넓으면 줄임
        s = 0.85 * bw / fw; sub = (cv2.resize(sub.astype(np.float32), (max(1, int(fw * s)), max(1, int(fh * s)))) > 0.5).astype(np.uint8); fh, fw = sub.shape
    gap = int(0.05 * bh)
    hs = int(max(0.5 * bh, min(bh, Ht - fh - gap)))
    hs = max(8, min(hs, BOX - 2 - fh - gap - by))
    out = np.zeros_like(base)
    top = base[by:by + bh, bx:bx + bw]
    out[by:by + hs, bx:bx + bw] = cv2.resize(top.astype(np.float32), (bw, hs)) > 0.5
    cx = bx + bw * (0.45 if vert else 0.5)
    y0 = min(by + hs + gap, BOX - fh - 1); x0 = int(np.clip(cx - fw / 2, 0, BOX - fw - 1))
    out[y0:y0 + fh, x0:x0 + fw] |= sub
    return out

def shift(bm, dx, dy):
    M = np.float32([[1, 0, dx], [0, 1, dy]]); return cv2.warpAffine(bm, M, (BOX, BOX))

def build(g, log=print):
    out = dict(g)                                     # 쓴 글자는 그대로
    # 1) 모음 (ㅇ+모음)
    vow = {}
    for v in V:
        s = syl("ㅇ", v)
        if s in g:
            m = strip_ieung(g[s], "v" if v in VERT else "h")
            if m is not None: vow[v] = m
    def vgroups(m):                                  # 세로획: 글씨 높이의 45% 넘게 칠해진 열 묶음
        _, _, _, Hh = bb(m); col = m.sum(0); on = col > 0.45 * Hh; gs = []; x = 0
        while x < BOX:
            if on[x]:
                x0 = x
                while x < BOX and on[x]: x += 1
                if gs and x0 - gs[-1][1] < 4: gs[-1][1] = x
                else: gs.append([x0, x])
            x += 1
        return gs
    for a, b, c3 in (("ㅒ", "ㅐ", "ㅑ"), ("ㅖ", "ㅔ", "ㅕ")):   # 얘 = ㅑ + ㅐ의 오른쪽 획, 예 = ㅕ + ㅔ의 오른쪽 획
        if a in vow or b not in vow: continue
        gb, gc = vgroups(vow[b]), vgroups(vow[c3]) if c3 in vow else []
        if len(gb) >= 2 and gc:
            dx = (gb[0][0] + gb[0][1]) / 2 - (gc[-1][0] + gc[-1][1]) / 2
            right = np.zeros_like(vow[b]); x0, x1 = gb[-1]; right[:, x0 - 2:x1 + 2] = vow[b][:, x0 - 2:x1 + 2]
            vow[a] = np.clip(shift(vow[c3], dx, 0) + right, 0, 1)
        else: vow[a] = vow[b]
    # 2) 자음 (배치별)
    ini = {"v": {}, "h": {}, "m": {}}
    for l in L:
        for v in "ㅣㅏㅓ":
            s = syl(l, v)
            if s in g and l not in ini["v"]:
                r = split_vertical(g[s])
                if r: ini["v"][l] = r[0]
        for v in "ㅡㅗㅜ":
            s = syl(l, v)
            if s in g and l not in ini["h"]:
                r = split_horizontal(g[s])
                if r: ini["h"][l] = r[0]
        s = syl(l, "ㅢ")
        if s in g:
            r = split_mixed_ui(g[s])
            if r is not None: ini["m"][l] = r
        if l not in ini["m"] and l in ini["h"]:
            ini["m"][l] = shift(ini["h"][l], -0.09 * BOX, -0.02 * BOX)
    # 3) 받침 (고+받침)
    fin = {}
    for t in T[1:]:
        s = syl("ㄱ", "ㅗ", t)
        if s in g:
            m = final_from_go(g[s])
            if m is not None: fin[t] = m
    log(f"모음 {len(vow)}/21 · 자음 세로 {len(ini['v'])} 가로 {len(ini['h'])} 섞임 {len(ini['m'])} /19 · 받침 {len(fin)}/27")
    # 4) 받침 없는 글자(자음+모음) 확보
    def cv(l, v):
        s = syl(l, v)
        if s in out: return out[s]
        lay = "v" if v in VERT else ("h" if v in HORI else "m")
        if l in ini[lay] and v in vow:
            out[s] = np.clip(ini[lay][l] + vow[v], 0, 1); return out[s]
        return None
    hs_b = [bb(g[c])[3] for c in g if 0xAC00 <= ord(c) <= 0xD7A3 and dec(c)[2] != " " and g[c].any()]
    hs_n = [bb(g[c])[3] for c in g if 0xAC00 <= ord(c) <= 0xD7A3 and dec(c)[2] == " " and g[c].any()]
    Ht = float(np.median(hs_b)) if hs_b else 1.4 * float(np.median(hs_n))
    made, miss = 0, []
    for ch in ks2350():
        if ch in out: continue
        l, v, t = dec(ch)
        base = cv(l, v)
        if base is None: miss.append(ch); continue
        if t == " ": made += 1; continue
        if t not in fin: miss.append(ch); continue
        out[ch] = put_final(base, fin[t], v in VERT, Ht); made += 1
    # 5) 낱자 (ㄱ~ㅎ, ㅏ~ㅣ): 가운데로 옮겨 크게
    def center(m, k=1.25):
        ys, xs = np.nonzero(m)
        if len(xs) == 0: return m
        sub = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        h, w = sub.shape; s = min(k, 0.7 * BOX / max(h, w))
        sub = cv2.resize(sub, (max(1, int(w * s)), max(1, int(h * s))), interpolation=cv2.INTER_NEAREST)
        o = np.zeros_like(m); y0 = (BOX - sub.shape[0]) // 2 + int(0.03 * BOX); x0 = (BOX - sub.shape[1]) // 2
        o[y0:y0 + sub.shape[0], x0:x0 + sub.shape[1]] = sub; return o
    COMPAT = {c: 0x3131 + i for i, c in enumerate("ㄱㄲㄳㄴㄵㄶㄷㄸㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅃㅄㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ")}
    for c, cp in COMPAT.items():
        m = ini["h"].get(c) if c in L else vow.get(c)
        if m is None and c in fin: m = fin[c]
        if m is not None: out[chr(cp)] = center(m)
    log(f"조합으로 만든 글자 {made}자 · 못 만든 글자 {len(miss)}자 {''.join(miss[:40])}")
    return out, miss
