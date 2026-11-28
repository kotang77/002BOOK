# 서가 샘플책(운수 좋은 날): 새 회원 서가에 한 권 비치 · 문구 꼬리표 3개 · 꼬리표/상세에서 문구 확인 · 빼기 (가짜 서버)
import json, os, time, urllib.request
from playwright.sync_api import sync_playwright
API = 'http://localhost:8000'; WEB = 'http://localhost:8080'
OUT = os.environ.get('OUT', '/tmp/oraltest/') + 'sample/'; os.makedirs(OUT, exist_ok=True)
res, errs = [], []
def ok(n, c, x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ') + n + (' — ' + str(x)[:200] if x != '' else ''))
def api(op, tok=None, **kw):
    h = {'content-type': 'application/json'}
    if tok: h['x-session'] = tok
    r = urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST')
    try: return json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())
def mk(uid):
    r = api('auth.login', id=uid, pw='testpass1234')
    if 'result' in r: api('auth.withdraw', r['result']['session']['token'], pw='testpass1234')
    return api('auth.signup', id=uid, pw='testpass1234', email=uid + '@ex.com', agreeTerms=True, agreePrivacy=True, birth='2010-01', grade='중1', nick=uid, gender='여')['result']['session']
SMP = '[data-act=shbook][aria-label^="샘플책"]'
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    for mode, vp in [('mobile', {'width': 390, 'height': 844}), ('desktop', {'width': 1280, 'height': 860})]:
        s = mk('sample' + mode[:3])
        ctx = b.new_context(viewport=vp, locale='ko-KR', service_workers='block', device_scale_factor=2); pg = ctx.new_page()
        pg.route('**/cdnjs.cloudflare.com/**', lambda rt: rt.fulfill(body='', content_type='application/javascript'))
        pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        pg.goto(WEB + '/'); pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))", s); pg.goto(WEB + '/'); pg.wait_for_selector('.who', timeout=20000); time.sleep(1)
        pg.get_by_role('button', name='내 서재').first.click(); time.sleep(1.2)
        ok(f'{mode}: 샘플책 한 권 비치', pg.locator('.mysh ' + SMP).count() == 1)
        ok(f'{mode}: 소설 칸 "샘플 1권"', '샘플 1권' in pg.inner_text('.mysh .bshf'))
        tabs = pg.locator('.mysh .sbw:has(' + SMP + ') .sqtab').count(); ok(f'{mode}: 문구 꼬리표 3개', tabs == 3, tabs)
        pg.locator('.mysh .bcase').screenshot(path=OUT + f'{mode}_shelf.png')
        pg.locator('.mysh .sbw:has(' + SMP + ') .sqtab').nth(2).click(); time.sleep(.4)
        t = pg.inner_text('.shqpop-c'); ok(f'{mode}: 꼬리표 누르면 문구', '설렁탕' in t and '/3' not in t and '2026.' in t, t)
        pg.screenshot(path=OUT + f'{mode}_pop.png')
        pg.locator('.shqpop-c [data-act=shqpopx]').first.click(); time.sleep(.3)
        pg.locator('.mysh ' + SMP).click(); time.sleep(.6)
        ok(f'{mode}: 상세에 샘플책 표시', pg.locator('.mysh .smpb').count() == 1)
        ok(f'{mode}: 상세 문구 3개, 지우기 없음', pg.locator('.mysh .shqtop .shqc').count() == 3 and pg.locator('.mysh .shqtop [data-act=shqdel]').count() == 0)
        pg.locator('.mysh .sdt').screenshot(path=OUT + f'{mode}_detail.png'); pg.locator('.mysh .shqtop').screenshot(path=OUT + f'{mode}_quotes.png')
        if mode == 'mobile':
            pg.locator('.mysh [data-act=smpdel]').click(); time.sleep(1)
            ok('빼기 → 서가에서 사라짐', pg.locator(SMP).count() == 0)
            for _ in range(20):
                d = api('db.get', s['token'], path='progress/' + 'samplemob').get('result') or {}
                if (d.get('data') or {}).get('noSample'): break
                time.sleep(.3)
            ok('빼기 저장', bool((d.get('data') or {}).get('noSample')), d)
        ctx.close()
    b.close()
ok('페이지 오류 없음', not errs, errs)
print(f'{sum(res)}/{len(res)}'); raise SystemExit(0 if all(res) else 1)
