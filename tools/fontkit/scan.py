# 사진 → 네 모서리 표식으로 펴기 → 쪽 판별 → 칸마다 글자 비트맵(408x408, 글씨=255)
import cv2, json, numpy as np, sys, os, glob
PX = 24                      # 1mm = 24px
B = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "boxes.json"), encoding="utf-8"))
BOX = 408                    # 17mm * 24

def find_marks(gray):
    h, w = gray.shape
    norm = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    _, bw = cv2.threshold(norm, 70, 255, cv2.THRESH_BINARY_INV)
    cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cand = []
    for c in cnts:
        a = cv2.contourArea(c)
        if a < (w * 0.008) ** 2 or a > (w * 0.06) ** 2: continue
        x, y, ww, hh = cv2.boundingRect(c)
        if not 0.6 < ww / hh < 1.6: continue
        hull = cv2.convexHull(c)
        if a / max(cv2.contourArea(hull), 1) < 0.85: continue
        if a / (ww * hh) < 0.55: continue
        m = cv2.moments(c); cand.append((m["m10"] / m["m00"], m["m01"] / m["m00"], a))
    if len(cand) < 4: raise RuntimeError(f"모서리 표식을 {len(cand)}개만 찾았어요")
    corners = [(0, 0), (w, 0), (0, h), (w, h)]   # r1 왼위, r2 오위, r3 왼아래, r4 오아래
    pick = []
    for cx, cy in corners:
        pick.append(min(cand, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)[:2])
    return np.float32(pick)

def flatten(img, page):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    src = find_marks(gray)
    dst = np.float32([[(x + ww / 2) * PX, (y + hh / 2) * PX] for x, y, ww, hh in page["reg"]])
    M = cv2.getPerspectiveTransform(src, dst)
    W, H = int(page["size"][0] * PX), int(page["size"][1] * PX)
    flat = cv2.warpPerspective(gray, M, (W, H), flags=cv2.INTER_CUBIC, borderValue=255)
    bgd = cv2.GaussianBlur(flat, (0, 0), 25)                 # 조명 고르게
    return np.clip(flat.astype(np.float32) / np.maximum(bgd, 1) * 235, 0, 255).astype(np.uint8)

def border_score(flat, page):
    s = []
    for c in page["cells"]:
        x, y, w, h = [int(v * PX) for v in c["box"]]
        if x < 2 or y < 2 or x + w >= flat.shape[1] - 2 or y + h >= flat.shape[0] - 2: return 0
        edge = np.concatenate([flat[y - 2:y + 3, x + w // 4:x + 3 * w // 4].min(0), flat[y + h // 4:y + 3 * h // 4, x - 2:x + 3].min(1)])
        s.append((edge < 170).mean())
    return float(np.mean(s)) if s else 0

def cut(flat, page):
    out = {}
    ins = int(0.55 * PX)
    for c in page["cells"]:
        x, y, w, h = [int(round(v * PX)) for v in c["box"]]
        crop = flat[y + ins:y + h - ins, x + ins:x + w - ins]
        bw = (crop < 150).astype(np.uint8) * 255
        n, lab, st, _ = cv2.connectedComponentsWithStats(bw, 8)
        keep = np.zeros_like(bw)
        for i in range(1, n):
            if st[i, cv2.CC_STAT_AREA] >= 40: keep[lab == i] = 255
        full = np.zeros((BOX, BOX), np.uint8)
        full[ins:ins + keep.shape[0], ins:ins + keep.shape[1]] = keep[:BOX - ins, :BOX - ins]
        if full.sum() > 255 * 60: out[c["ch"]] = full
    return out

def scan(paths, outdir="glyphs"):
    os.makedirs(outdir, exist_ok=True); got = {}; report = []
    cell_pages = [p for p in B if p["cells"]]
    for pth in paths:
        img = cv2.imread(pth)
        best = max(((border_score(flatten(img, p), p), p) for p in cell_pages), key=lambda t: t[0])
        sc, page = best; flat = flatten(img, page)
        g = cut(flat, page); got.update(g)
        report.append((os.path.basename(pth), page["page"], round(sc, 3), f'{len(g)}/{len(page["cells"])}'))
        cv2.imwrite(os.path.join(outdir, f"_flat_p{page['page']}.jpg"), cv2.resize(flat, None, fx=.25, fy=.25))
    for ch, bm in got.items():
        cv2.imwrite(os.path.join(outdir, f"U{ord(ch):05X}.png"), bm)
    return got, report

if __name__ == "__main__":
    paths = sys.argv[1:] or sorted(glob.glob("sim_photo_*.jpg"))
    got, rep = scan(paths)
    for r in rep: print(r)
    print("글자", len(got))
