# 내 서재 '사진으로 추가하기': 앞표지만 배경 없이 잘라내는지 시험 (가짜 서버, run.sh가 FAKE_AI_MAP을 넘긴다)
# 합성 사진: 나무결 배경 + 기울어진 책 표지(안쪽 노란 테두리, 그림자) + 책등만 보이는 책.
# 가짜 AI는 표지 꼭짓점을 일부러 2~3% 어긋나게 돌려준다 → 앱이 실제 테두리에 맞춰 잘라야 통과.
import base64, io, json, os, random, sys, time, urllib.request
from PIL import Image, ImageDraw, ImageFilter
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
API = 'http://localhost:8000'; WEB = 'http://localhost:8080'
OUT = os.environ.get('OUT', '/tmp/oraltest/') + 'shelf/'; os.makedirs(OUT, exist_ok=True)
MAP = json.load(open(os.path.join(HERE, 'fakeai_map.json'), encoding='utf-8'))
TRUE = MAP['_truth']  # 0~1000 좌표 실제 꼭짓점
res, errs = [], []
def ok(n, c, x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ') + n + (' — ' + str(x)[:200] if x != '' else ''))
def api(op, tok=None, **kw):
    h = {'content-type': 'application/json'}
    if tok: h['x-session'] = tok
    r = urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST')
    try: return json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())

# 합성 사진 만들기
W, H = 1200, 900; random.seed(7)
P = lambda q: [(x * W / 1000, y * H / 1000) for x, y in q]
im = Image.new('RGB', (W, H))
px = im.load()
for y in range(H):
    for x in range(W):
        g = int(18 * ((x * 0.03 + y * 0.004) % 1)) + random.randint(-6, 6)
        px[x, y] = (150 + g, 108 + g, 70 + g)  # 나무결 비슷한 갈색
d = ImageDraw.Draw(im)
d.line([(0, 820), (W, 835)], fill=(90, 60, 40), width=6)  # 책상 모서리
d.rectangle([980, 120, 1040, 760], fill=(170, 40, 40))  # 책등만 보이는 책
cover = P(TRUE)
sh = Image.new('L', (W, H), 0); ImageDraw.Draw(sh).polygon([(x + 14, y + 12) for x, y in cover], fill=150)
im.paste((60, 42, 30), mask=sh.filter(ImageFilter.GaussianBlur(7)))  # 부드러운 그림자(실제 사진처럼)
d = ImageDraw.Draw(im)
d.polygon(cover, fill=(28, 58, 122))  # 남색 표지
c = [sum(p[0] for p in cover) / 4, sum(p[1] for p in cover) / 4]
inner = [(c[0] + (x - c[0]) * .84, c[1] + (y - c[1]) * .84) for x, y in cover]
d.line(inner + [inner[0]], fill=(240, 200, 60), width=5)  # 안쪽 인쇄 테두리(속이기용)
d.text((c[0] - 40, c[1] - 10), 'TEST BOOK', fill=(255, 255, 255))
im = im.filter(ImageFilter.GaussianBlur(1.2))
photo = OUT + 'photo.jpg'; im.save(photo, quality=88)

def mk(uid):
    r = api('auth.login', id=uid, pw='testpass1234')
    if 'result' in r: api('auth.withdraw', r['result']['session']['token'], pw='testpass1234')
    return api('auth.signup', id=uid, pw='testpass1234', email=uid + '@ex.com', agreeTerms=True, agreePrivacy=True, birth='2010-01', grade='중1', nick=uid, gender='여')['result']['session']
s = mk('shelf01')
LIB = os.environ.get('PDFLIB', '/home/claude/fonts/node_modules')
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    for mode, vp in [('mobile', {'width': 390, 'height': 844}), ('desktop', {'width': 1280, 'height': 860})]:
        ctx = b.new_context(viewport=vp, locale='ko-KR', service_workers='block'); pg = ctx.new_page()
        pg.route('**/cdnjs.cloudflare.com/**', lambda rt: rt.fulfill(body='', content_type='application/javascript'))
        pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        pg.goto(WEB + '/'); pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))", s); pg.goto(WEB + '/'); pg.wait_for_selector('.who', timeout=20000); time.sleep(1)
        pg.get_by_role('button', name='내 서재').first.click(); time.sleep(1)
        pg.evaluate("document.querySelector('[data-act=mybooks]').click()"); pg.wait_for_selector('input[data-bkphoto][multiple]', state='attached', timeout=10000)
        pg.set_input_files('input[data-bkphoto][multiple]', photo)
        pg.wait_for_selector('.rvrow', timeout=30000); time.sleep(.5)
        rows = pg.locator('.rvrow').count(); ok(f'{mode}: 인식한 책 2권', rows == 2, rows)
        srcs = pg.evaluate("[...document.querySelectorAll('.rvth img')].map(i=>i.src)")
        ok(f'{mode}: 앞표지 보이는 책만 잘라냄', len(srcs) == 1, len(srcs))
        ok(f'{mode}: 책등만 보이는 책은 표지 비움 안내', '앞표지가 보이지 않아' in pg.inner_text('.bkrv'))
        pg.locator('.bkrv').screenshot(path=OUT + f'{mode}_review.png')
        if srcs:
            cut = Image.open(io.BytesIO(base64.b64decode(srcs[0].split(',', 1)[1]))).convert('RGB'); cut.save(OUT + f'{mode}_cut.png')
            w, h = cut.size
            ring = [cut.getpixel((x, y)) for x in range(w) for y in range(h) if x < 4 or y < 4 or x >= w - 4 or y >= h - 4]
            navy = sum(1 for r_, g, b_ in ring if abs(r_ - 28) + abs(g - 58) + abs(b_ - 122) < 70) / len(ring)
            wood = sum(1 for r_, g, b_ in ring if r_ > 120 and r_ > b_ + 40) / len(ring)
            ok(f'{mode}: 가장자리에 배경이 없음 (표지색 {navy:.0%}, 배경색 {wood:.1%})', navy > .9 and wood < .02)
            ok(f'{mode}: 표지 비율 유지 ({w}x{h})', .7 < w / h < .9)
            yel = sum(1 for x in range(w) for y in range(h // 2 - 3, h // 2 + 3) if (lambda c_: c_[0] > 180 and c_[1] > 150 and c_[2] < 120)(cut.getpixel((x, y))))
            ok(f'{mode}: 안쪽 노란 테두리까지 보존 (가운데 줄 노란 점 {yel})', yel >= 6)
        if mode == 'mobile':  # 코스 카드의 '표지 올리기'도 같은 방식으로 잘라 저장
            pg.keyboard.press('Escape'); pg.evaluate("()=>{const c=document.querySelector('[data-act=close1]');if(c)c.click()}"); time.sleep(.4)
            pg.goto(WEB + '/'); pg.wait_for_selector('[data-act=month]', timeout=20000); time.sleep(1)
            pg.evaluate("document.querySelector('[data-act=month][data-i=\"0\"]').click()"); pg.wait_for_selector('input[data-cover]', state='attached', timeout=15000)
            pg.set_input_files('input[data-cover] >> nth=0', photo)
            for _ in range(40):
                cs = api('db.query', s['token'], collection='covers').get('result', [])
                if cs: break
                time.sleep(.5)
            ok('코스 표지 올리기 저장', bool(cs), len(cs))
            if cs:
                cut = Image.open(io.BytesIO(base64.b64decode(cs[0]['data']['img'].split(',', 1)[1]))).convert('RGB'); cut.save(OUT + 'course_cut.png'); w, h = cut.size
                ring = [cut.getpixel((x, y)) for x in range(w) for y in range(h) if x < 4 or y < 4 or x >= w - 4 or y >= h - 4]
                navy = sum(1 for r_, g, b_ in ring if abs(r_ - 28) + abs(g - 58) + abs(b_ - 122) < 70) / len(ring)
                ok(f'코스 표지도 배경 없이 (표지색 {navy:.0%}, {w}x{h})', navy > .9 and .7 < w / h < .9)
        ctx.close()
    b.close()
ok('페이지 오류 없음', not errs, errs[:3])
print('%d/%d' % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
