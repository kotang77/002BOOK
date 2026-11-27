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
def prog(): return api('db.get', s['token'], path='progress/shelf01')['result']['data']
def toast(pg): return pg.inner_text('#toast')
def star(pg, sc, id_, q, v): pg.evaluate("a=>document.querySelector(`[data-act=mbrate][data-sc=\"${a[0]}\"][data-id=\"${a[1]}\"][data-q=\"${a[2]}\"][data-v=\"${a[3]}\"]`).click()", [sc, id_, q, str(v)]); time.sleep(.15)
def rate_all(pg, sc, id_): star(pg, sc, id_, 'fun', 4); star(pg, sc, id_, 'diff', 3); star(pg, sc, id_, 'again', 4.5)
def wait(f, n=40):
    for _ in range(n):
        try:
            if f(): return True
        except Exception: pass
        time.sleep(.25)
    return False
def mobile_flow(pg):
    # 1) 사진으로 추가: 평가해야 꽂을 수 있음
    ok('사진 추가: 평가 전에는 꽂기 버튼 잠김', pg.evaluate("document.querySelector('[data-act=bkconfirm]').disabled"))
    ids = pg.evaluate("[...document.querySelectorAll('[data-rbox^=\"rv:\"]')].map(e=>e.dataset.rbox.slice(3))")
    ok('사진 추가: 책마다 평가 칸', len(ids) == 2, ids)
    rate_all(pg, 'rv', ids[0])
    ok('사진 추가: 한 권만 평가하면 아직 잠김', pg.evaluate("document.querySelector('[data-act=bkconfirm]').disabled"))
    rate_all(pg, 'rv', ids[1])
    ok('사진 추가: 모두 평가하면 열림', not pg.evaluate("document.querySelector('[data-act=bkconfirm]').disabled"))
    pg.evaluate("document.querySelector('[data-act=bkconfirm]').click()")
    ok('사진 추가: 평가와 함께 저장', wait(lambda: len(prog().get('myBooks', [])) == 2 and all(b.get('rate') == {'fun': 4, 'diff': 2.5, 'again': 4.5} for b in prog()['myBooks'])), prog().get('myBooks'))
    # 2) 직접 추가: 평가 없이는 안 꽂힘, 별을 눌러도 적은 제목은 그대로
    pg.fill('#mb-title', '직접 넣은 책'); pg.select_option('#mb-ax', '0'); pg.select_option('#mb-cat', '소설')
    pg.evaluate("document.querySelector('form[data-form=mybook] button[type=submit]').click()"); time.sleep(.6)
    ok('직접 추가: 평가 없으면 안내만', '매겨' in toast(pg) and len(prog()['myBooks']) == 2, toast(pg))
    rate_all(pg, 'form', 'f')
    ok('직접 추가: 별을 눌러도 적은 제목 유지', pg.input_value('#mb-title') == '직접 넣은 책')
    pg.locator('form[data-form=mybook]').screenshot(path=OUT + 'form_rated.png')
    pg.evaluate("document.querySelector('form[data-form=mybook] button[type=submit]').click()")
    ok('직접 추가: 평가와 함께 저장', wait(lambda: any(b['title'] == '직접 넣은 책' and b.get('rate', {}).get('again') == 4.5 for b in prog()['myBooks'])))
    # 3) 서가의 책을 누르면 인상적인 문구가 맨 위에
    time.sleep(.6); pg.evaluate("document.querySelector('#layer1 [data-act=shbook]').click()"); pg.wait_for_selector('#layer1 .shqtop', timeout=10000)
    ok('책 상세는 한 곳에만', pg.locator('.sdt').count() == 1 and pg.locator('#sh-q').count() == 1, pg.locator('.sdt').count())
    ok('서가 책 누르면 문구 칸이 맨 위', pg.evaluate("(()=>{const a=document.querySelector('.shqtop'),b=document.querySelector('#shq-add');return !!(a&&b&&(a.compareDocumentPosition(b)&Node.DOCUMENT_POSITION_FOLLOWING))})()"))
    pg.fill('#sh-q', '마음에 남은 첫 문장'); pg.fill('#sh-qp', '42'); pg.evaluate("document.querySelector('[data-act=shqadd]').click()")
    ok('글 문구 저장 후 맨 위 카드', wait(lambda: '마음에 남은 첫 문장' in pg.inner_text('#layer1 .shqtop')))
    pg.fill('#sh-qr', '고쳐 쓰던 이유')
    sent = []; pg.on('request', lambda r: sent.append(r.post_data or '') if r.method == 'POST' and 'ai.sample' in (r.post_data or '') else None)
    pg.set_input_files('input[data-shqimg]', photo)
    ok('문구 사진: 글을 읽어 칸에 채움', wait(lambda: pg.input_value('#sh-q') == '작은 실천이 쌓여 큰 변화를 만든다.', 60), pg.input_value('#sh-q') if pg.locator('#sh-q').count() else '')
    ok('문구 사진: AI에 사진을 실제로 보냄(한 장 Blob)', any('"images":[{"media_type":"image/jpeg"' in x for x in sent), [x[:120] for x in sent])
    ok('문구 사진: 적던 이유 유지', pg.input_value('#sh-qr') == '고쳐 쓰던 이유')
    pg.evaluate("document.querySelector('[data-act=shqadd]').click()")
    ok('사진 문구 저장', wait(lambda: pg.locator('#layer1 .shqtop .shqim img').count() == 1))
    wait(lambda: any(x.get('img') for v in prog().get('quotes', {}).values() for x in v))  # 진도는 0.7초 뒤 묶어서 저장
    q = [x for v in prog().get('quotes', {}).values() for x in v if x.get('img')]
    ok('사진은 따로 저장(진도 문서엔 아이디만)', len(q) == 1 and q[0]['img'].startswith('shelf01_') and 'data:' not in json.dumps(prog()), q[:1])
    qid = q[0]['img'] if q else 'x'
    r = api('db.get', s['token'], path='qimgs/' + qid); ok('내 문구 사진 읽기', (r.get('result') or {}).get('data', {}).get('img', '').startswith('data:image/jpeg'))
    other = mk('stranger01'); r = api('db.get', other['token'], path='qimgs/' + qid); ok('친구 아닌 회원은 문구 사진 못 읽음', r.get('result') is None, r)
    r = api('db.set', other['token'], path='qimgs/' + qid, data={'uid': 'stranger01', 'img': 'x'}); ok('남의 문구 사진 못 바꿈', 'error' in r)
    pg.locator('#layer1 .sdt').screenshot(path=OUT + 'detail_top.png'); pg.locator('#layer1 .shqtop').screenshot(path=OUT + 'quotes.png')
    # 다시 들어와도 사진이 보임
    pg.goto(WEB + '/'); pg.wait_for_selector('.who', timeout=20000); time.sleep(1)
    pg.get_by_role('button', name='내 서재').first.click(); time.sleep(1)
    pg.evaluate("document.querySelector('[data-act=mybooks]').click()"); time.sleep(1)
    pg.evaluate("document.querySelector('#layer1 [data-act=shbook]').click()")
    ok('다시 열어도 문구 사진 보임', wait(lambda: pg.evaluate("[...document.querySelectorAll('#layer1 .shqtop .shqim img')].some(i=>i.naturalWidth>0)")))
    ok('서가 책 내 평가 보임', '재미 ★4.0' in pg.inner_text('#layer1 .sdrate'), pg.inner_text('#layer1 .sdrate'))
    n0 = len(prog()['quotes'][list(prog()['quotes'])[0]])
    pg.evaluate("[...document.querySelectorAll('#layer1 .shqtop .shqc')].find(f=>f.querySelector('.shqim')).querySelector('[data-act=shqdel]').click()")
    ok('사진 문구 지우면 사진도 삭제', wait(lambda: api('db.get', s['token'], path='qimgs/' + qid).get('result') is None))
    pg.evaluate("document.querySelector('[data-act=close1]').click()"); time.sleep(.5)
    # 4) 추천 책 '읽음'도 평가해야 꽂힘
    ok('추천 책 보임', wait(lambda: pg.locator('[data-act=recread]').count() > 0, 40))
    pg.evaluate("document.querySelector('[data-act=recread]').click()"); time.sleep(.5)
    pg.evaluate("document.querySelector('[data-act=recok]').click()"); time.sleep(.4)
    ok('추천 책: 평가 없으면 안 꽂힘', '매겨' in toast(pg) and not any(b['title'] == '추천 책 하나' for b in prog()['myBooks']))
    n = pg.evaluate("document.querySelector('[data-act=recok]').dataset.n")
    rate_all(pg, 'rec', n); pg.locator('.rcl').screenshot(path=OUT + 'rec_rate.png')
    pg.evaluate("document.querySelector('[data-act=recok]').click()")
    ok('추천 책: 평가와 함께 꽂힘', wait(lambda: any(b['title'] == '추천 책 하나' and b.get('rate', {}).get('fun') == 4 for b in prog()['myBooks'])))

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
        if mode == 'mobile': mobile_flow(pg)
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
        if mode == 'mobile':  # 표지가 이미 있으면 '바꾸기' 버튼은 없음(2026-11-26 사용자 지시)
            pg.keyboard.press('Escape'); pg.evaluate("()=>{const c=document.querySelector('[data-act=close1]');if(c)c.click()}"); time.sleep(.4)
            pg.goto(WEB + '/'); pg.wait_for_selector('[data-act=month]', timeout=20000); time.sleep(1)
            pg.evaluate("document.querySelector('[data-act=month][data-i=\"0\"]').click()"); time.sleep(1.5)
            ok('표지·포스터 바꾸기 버튼 없음', '바꾸기' not in pg.inner_text('#layer1'))
        ctx.close()
    b.close()
ok('페이지 오류 없음', not errs, errs[:3])
print('%d/%d' % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
