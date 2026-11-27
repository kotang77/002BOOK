# 꿈 인터뷰: 학생(중1)은 학생용 10문항, 부모·선생님·일반 어른은 성인용 10문항(학교·대학 대신 건강 습관, 스무 살 대신 5년 뒤)
import json, sys, time, urllib.request
from playwright.sync_api import sync_playwright
API = 'http://localhost:8000'; WEB = 'http://localhost:8080'; PW = 'testpass1234'; res = []; errs = []
def ok(n, c, x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ') + n + ('' if c else f' — {x}'))
def api(op, tok=None, **kw):
    h = {'content-type': 'application/json'}
    if tok: h['x-session'] = tok
    r = urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST')
    try: return json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())
def user(U, grade, birth):
    r = api('auth.login', id=U, pw=PW)
    if 'result' in r: api('auth.withdraw', r['result']['session']['token'], pw=PW)
    return api('auth.signup', id=U, pw=PW, email=U + '@ex.com', agreeTerms=True, agreePrivacy=True, birth=birth, grade=grade, nick=U, gender='여')['result']['session']
def cards(pg, s):
    pg.goto(WEB + '/'); pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))", s); pg.goto(WEB + '/'); pg.wait_for_selector('.who', timeout=20000); time.sleep(1)
    pg.evaluate("document.querySelector('[data-act=view][data-v=vision]').click()"); pg.wait_for_selector('.vbz-c', timeout=10000); time.sleep(.5)
    return pg.evaluate("[...document.querySelectorAll('.vbz-c')].map(c=>c.querySelector('.vbz-q').textContent+' | '+c.querySelector('textarea').placeholder)")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    pg = b.new_page(viewport={'width': 390, 'height': 844}); pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    kid = cards(pg, user('vbkid01', '중1', '2010-01'))
    ok('학생: 10문항', len(kid) == 10, len(kid))
    ok('학생: 스무 살·학교·학과 질문 그대로', '스무 살' in kid[1] and '학교와 학과' in kid[4], kid[:5])
    for g in ['엄마', '선생님']:
        pg2 = b.new_page(viewport={'width': 390, 'height': 844}); pg2.on('pageerror', lambda e: errs.append(str(e)[:200]))
        ad = cards(pg2, user('vbad' + ('m' if g == '엄마' else 't') + '01', g, '1980-01'))
        ok(g + ': 성인용 10문항', len(ad) == 10, len(ad))
        ok(g + ': 5년 뒤·건강 습관, 학교·스무 살 없음', '5년 뒤' in ad[1] and '건강 습관' in ad[4] and not any(('스무 살' in x or '학교와 학과' in x or '고등학교' in x) for x in ad), ad)
        pg2.close()
    ok('화면 오류 없음', not errs, errs)
    b.close()
for U in ['vbkid01', 'vbadm01', 'vbadt01']:
    r = api('auth.login', id=U, pw=PW)
    if 'result' in r: api('auth.withdraw', r['result']['session']['token'], pw=PW)
print(f'{sum(res)}/{len(res)}'); sys.exit(0 if all(res) else 1)
