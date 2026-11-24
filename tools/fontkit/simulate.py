# 시험용: 양식에 '대역 손글씨'(HiMelody, OFL)로 글자를 채우고 휴대폰 사진처럼 비틀어 저장
import asyncio, random, re, cv2, numpy as np
from playwright.async_api import async_playwright
random.seed(7); np.random.seed(7)
html = open("/home/claude/fonttpl/tpl_F.html", encoding="utf-8").read()
css = """@font-face{font-family:Writer;src:url(file:///home/claude/fontkit/ext/HiMelody-Regular.ttf)}
.bx span{position:absolute;left:50%;top:50%;font-family:Writer;color:#1a1a2a;line-height:1;white-space:nowrap}"""
html = html.replace("</style>", css + "</style>")
def fill(m):
    ch = m.group(1)
    s = random.uniform(11.5, 13.2); dx = random.uniform(-0.7, 0.7); dy = random.uniform(-0.6, 0.8); rot = random.uniform(-4, 4)
    return (f'<div class="cell"><div class="lb">{ch}<i>{m.group(2)}</i></div><div class="bx"><span style="font-size:{s:.1f}mm;'
            f'transform:translate(-50%,-52%) translate({dx:.2f}mm,{dy:.2f}mm) rotate({rot:.1f}deg)">{ch}</span></div></div>')
html = re.sub(r'<div class="cell"><div class="lb">(.*?)<i>(U\+[0-9A-F]+)</i></div><div class="bx"></div></div>', fill, html)
open("sim_filled.html", "w", encoding="utf-8").write(html)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        pg = await b.new_page(viewport={"width": 820, "height": 1200}, device_scale_factor=2.6)
        await pg.goto("file:///home/claude/fontkit/sim_filled.html"); await pg.wait_for_timeout(800)
        secs = await pg.query_selector_all("section.pg")
        for i, s in enumerate(secs[:5]):
            await s.screenshot(path=f"sim_flat_{i+1}.png")
        await b.close()
asyncio.run(main())

for i in range(1, 6):
    im = cv2.imread(f"sim_flat_{i}.png"); h, w = im.shape[:2]
    # 책상 위에 놓고 비스듬히 찍은 모양
    W, H = int(w * 1.25), int(h * 1.2)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    j = lambda a: random.uniform(-a, a)
    dst = np.float32([[W*.08+j(40), H*.06+j(40)], [W*.92+j(40), H*.05+j(40)], [W*.95+j(30), H*.95+j(30)], [W*.05+j(30), H*.93+j(30)]])
    M = cv2.getPerspectiveTransform(src, dst)
    bg = np.full((H, W, 3), (95, 115, 140), np.uint8)
    photo = cv2.warpPerspective(im, M, (W, H), dst=bg, borderMode=cv2.BORDER_TRANSPARENT)
    yy, xx = np.mgrid[0:H, 0:W]; light = 0.78 + 0.27 * (xx / W) * (1 - 0.4 * yy / H)
    photo = np.clip(photo * light[..., None] * np.array([0.97, 1.0, 1.04]), 0, 255).astype(np.uint8)
    photo = cv2.GaussianBlur(photo, (3, 3), 0.8); photo = np.clip(photo + np.random.normal(0, 4, photo.shape), 0, 255).astype(np.uint8)
    cv2.imwrite(f"sim_photo_{i}.jpg", photo, [cv2.IMWRITE_JPEG_QUALITY, 88])
print("ok")
