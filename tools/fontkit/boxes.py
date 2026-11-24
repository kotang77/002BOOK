# 양식 HTML에서 쪽마다 정합 표식·칸 위치(mm)를 뽑는다
import asyncio, json, sys
from playwright.async_api import async_playwright
TPL = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/fonttpl/tpl_F.html"
JS = """() => { const mm = 25.4/96; const out = [];
 document.querySelectorAll('section.pg').forEach((pg, i) => { const r0 = pg.getBoundingClientRect();
  const R = el => { const r = el.getBoundingClientRect(); return [(r.left-r0.left)*mm,(r.top-r0.top)*mm,r.width*mm,r.height*mm]; };
  const reg = [...pg.querySelectorAll('.reg')].map(R);
  const cells = [...pg.querySelectorAll('.cell')].map(c => ({ch: c.querySelector('.lb').childNodes[0].textContent, box: R(c.querySelector('.bx'))}));
  const lines = [...pg.querySelectorAll('.ln')].map(R);
  out.push({page: i+1, size: [r0.width*mm, r0.height*mm], reg, cells, lines}); });
 return out; }"""
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome"); pg = await b.new_page(viewport={"width": 900, "height": 1200})
        await pg.goto("file://" + TPL); await pg.wait_for_timeout(300)
        data = await pg.evaluate(JS); await b.close()
    json.dump(data, open("boxes.json", "w"), ensure_ascii=False)
    print([(d["page"], len(d["cells"]), len(d["lines"])) for d in data], data[0]["reg"], data[0]["cells"][0])
asyncio.run(main())
