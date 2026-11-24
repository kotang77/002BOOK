import asyncio, sys
from playwright.async_api import async_playwright
font, name, out = sys.argv[1], sys.argv[2], sys.argv[3]
lines = ["다람쥐 헌 쳇바퀴에 타고파.", "한 달에 책 한 권, 영화 두 편, 글 세 편.", "중학교 3년이 끝나면 108편의 첨삭 기록이 남습니다.",
         "읽고 싶은 책이 많아서 닭갈비도 먹고 됐어! 왜 그랬을까?", "꽃밭에서 깨끗한 쨍한 햇빛, 얘들아 예쁜 껌 씹자 ㅋㅋ ㅠㅠ",
         "The quick brown fox jumps over the lazy dog. 0123456789 (꿈) 「책」 100%"]
mark = "읽 많 닭 됐 왜 얘 예 깨 쨍 껌 씹 뚫 앉 넓 괜 뭘 쉿 흙 삶 짧"
html = f"""<html><head><meta charset=utf-8><style>@font-face{{font-family:F;src:url(file://{font})}}
body{{margin:0;padding:40px 50px;background:#FFFDF6;width:1100px;font-family:'Noto Sans CJK KR'}}
h1{{font:700 22px 'Noto Sans CJK KR';color:#3E2F26;margin:0 0 6px}} p.s{{color:#8B7663;margin:0 0 24px;font-size:14px}}
.l{{font-family:F;font-size:44px;line-height:1.55;color:#222;border-bottom:1px dashed #E3D7C5}}
.g{{display:flex;flex-wrap:wrap;gap:8px;margin-top:26px}} .g span{{font-family:F;font-size:58px;width:84px;height:84px;display:flex;align-items:center;justify-content:center;background:#fff;border:1px solid #EADFCF;border-radius:10px}}
</style></head><body><h1>{name}</h1><p class=s>위: 문장 · 아래: 양식에 없어서 조합으로 만든 글자</p>
{''.join(f'<div class=l>{l}</div>' for l in lines)}<div class=g>{''.join(f'<span>{c}</span>' for c in mark.split())}</div></body></html>"""
open("pv.html", "w", encoding="utf-8").write(html)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome"); pg = await b.new_page(viewport={"width": 1200, "height": 800})
        await pg.goto("file:///home/claude/fontkit/pv.html"); await pg.wait_for_timeout(800)
        await pg.screenshot(path=out, full_page=True); await b.close()
asyncio.run(main())
