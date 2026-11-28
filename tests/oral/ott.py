# 영화 카드 '아직' 옆 볼 수 있는 OTT (media.ott, 가짜 서버: run.sh가 FAKE_OTT를 넘긴다)
import json, os, time, urllib.request
from playwright.sync_api import sync_playwright
API = 'http://localhost:8000'; WEB = 'http://localhost:8080'
OUT = os.environ.get('OUT', '/tmp/oraltest/') + 'ott/'; os.makedirs(OUT, exist_ok=True)
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
s = mk('ott01')
# 서버: 이름 맞추기·목록 밖 버리기·대여와 구독 겹침 제거·7일 캐시
r = api('media.ott', s['token'], title='쇼생크 탈출', year='')['result']
ok('구독 서비스 이름 맞춤(Netflix→넷플릭스), 목록 밖 버림', r['subs'] == ['넷플릭스', '웨이브'], r)
ok('대여에서 구독과 겹친 것·모르는 것 뺌', r['rent'] == ['네이버 시리즈온'], r)
ok('확인 시각', r['at'] > 0 and r['cached'] is False, r)
r2 = api('media.ott', s['token'], title='쇼생크 탈출', year='')['result']
ok('7일 안에는 캐시', r2['cached'] is True and r2['at'] == r['at'], r2)
ok('로그인 없으면 거절', 'error' in api('media.ott', None, title='쇼생크 탈출'))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    for mode, vp in [('mobile', {'width': 390, 'height': 844}), ('desktop', {'width': 1280, 'height': 860})]:
        ctx = b.new_context(viewport=vp, locale='ko-KR', service_workers='block', device_scale_factor=2); pg = ctx.new_page()
        pg.route('**/cdnjs.cloudflare.com/**', lambda rt: rt.fulfill(body='', content_type='application/javascript'))
        pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        pg.goto(WEB + '/'); pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))", s); pg.goto(WEB + '/'); pg.wait_for_selector('.who', timeout=20000); time.sleep(1)
        i = pg.evaluate("[...document.querySelectorAll('[data-act=month]')].findIndex(e=>/^11월/.test(e.textContent.trim()))")
        pg.evaluate("i=>document.querySelectorAll('[data-act=month]')[i].click()", i); time.sleep(1)
        def row(name): return pg.evaluate("n=>{const w=[...document.querySelectorAll('.wk')].find(x=>x.textContent.includes(n));return w?w.querySelector('.wk-x em').innerText:''}", name)
        for _ in range(40):
            if '넷플릭스' in row('쇼생크') and '구글' in row('당갈'): break
            time.sleep(.25)
        t1, t2 = row('쇼생크'), row('당갈')
        ok(f'{mode}: 쇼생크 탈출 아직 옆 넷플릭스·웨이브', t1.startswith('아직') and '넷플릭스' in t1 and '웨이브' in t1, t1)
        ok(f'{mode}: 구독 없으면 대여·구매', '대여·구매' in t2 and '구글 플레이' in t2, t2)
        tip = pg.evaluate("[...document.querySelectorAll('.wk')].find(x=>x.textContent.includes('쇼생크')).querySelector('.wk-ott').title")
        ok(f'{mode}: 확인 날짜·7일 안내', '확인' in tip and '7일' in tip, tip)
        ok(f'{mode}: 책 카드엔 없음', pg.evaluate("[...document.querySelectorAll('.wk')].filter(x=>/^책/.test(x.querySelector('small').textContent)).every(x=>!x.querySelector('.wk-ott'))"))
        pg.locator('.wk').first.locator('xpath=..').screenshot(path=OUT + f'{mode}_cards.png')
        if mode == 'mobile':
            # 기기 캐시: 7일이 지나면 다시 물음
            n0 = pg.evaluate("Object.keys(JSON.parse(localStorage.getItem('yw.ott')||'{}')).length")
            ok('기기에 기억', n0 >= 2, n0)
        ctx.close()
    b.close()
ok('페이지 오류 없음', not errs, errs)
print(f'{sum(res)}/{len(res)}'); raise SystemExit(0 if all(res) else 1)
