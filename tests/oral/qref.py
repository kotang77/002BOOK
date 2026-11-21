# 논술·구술 질문 새로고침 시험 (가짜 서버, run.sh가 FAKE_AI_MAP을 넘긴다)
import json, os, sys, time, urllib.request
from playwright.sync_api import sync_playwright
API = 'http://localhost:8000'; WEB = 'http://localhost:8080'
OUT = os.environ.get('OUT', '/tmp/oraltest/') + 'qref/'; os.makedirs(OUT, exist_ok=True)
res, errs = [], []
def ok(n, c, x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ') + n + (' — ' + str(x)[:200] if x != '' else ''))
def api(op, tok=None, **kw):
    h = {'content-type': 'application/json'}
    if tok: h['x-session'] = tok
    r = urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST')
    try: return json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())
r = api('auth.login', id='qref01', pw='testpass1234')
if 'result' in r: api('auth.withdraw', r['result']['session']['token'], pw='testpass1234')
s = api('auth.signup', id='qref01', pw='testpass1234', email='qref01@ex.com', agreeTerms=True, agreePrivacy=True, birth='2010-01', grade='중1', nick='qref01', gender='여')['result']['session']
sv = {k: {'fun': 4, 'diff': 3, 'again': 4} for k in ['b0:book', 'b0:m1', 'b0:m2']}
api('db.set', s['token'], path='progress/qref01', data={'done': {k: 1 for k in sv}, 'survey': sv, 'notes': {}, 'qs': {}, 'evalLog': [], 'drafts': {}, 'picks': {}})
def prog(): return api('db.get', s['token'], path='progress/qref01')['result']['data']
def wait(f, n=40):
    for _ in range(n):
        try:
            if f(): return True
        except Exception: pass
        time.sleep(.25)
    return False
TTS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flow.py'), encoding='utf-8').read().split("TTS='''")[1].split("'''")[0]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, locale='ko-KR', service_workers='block'); ctx.add_init_script(TTS); pg = ctx.new_page()
    pg.route('**/cdnjs.cloudflare.com/**', lambda rt: rt.fulfill(body='', content_type='application/javascript'))
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.goto(WEB + '/'); pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))", s); pg.goto(WEB + '/'); pg.wait_for_selector('.who', timeout=20000); time.sleep(1)
    J = lambda x: pg.evaluate(x)
    J("document.querySelector('[data-act=month][data-i=\"0\"]').click()"); time.sleep(.8)
    J("document.querySelector('[data-act=stab][data-v=essay]').click()"); pg.wait_for_selector('.qcard', timeout=20000); time.sleep(.5)
    ok('논술: 질문 옆 새로고침', pg.locator('.qcard [data-act=qref]').count() == 1, pg.inner_text('.qcard .qtop'))
    before = pg.inner_text('.qcard .qtx')
    J("document.querySelector('[data-act=qref]').click()")
    ok('논술: 지금 질문만 새 질문으로', wait(lambda: '새로 받은 논술 질문' in pg.inner_text('.qcard .qtx')), pg.inner_text('.qcard .qtx')[:60])
    ok('논술: 바뀐 질문 저장', wait(lambda: '새로 받은 논술 질문' in prog()['qs']['b0']['shown'][0]) and before not in prog()['qs']['b0']['shown'])
    pg.screenshot(path=OUT + 'essay.png')
    # 고르고 묻기를 마친 질문을 바꾸면 두 번 눌러야 함
    J("document.querySelector('[data-act=qnav][data-d=\"1\"]').click()"); time.sleep(.3)
    J("document.querySelector('[data-act=qpick]').click()"); time.sleep(.6)
    J("document.querySelector('[data-act=askdone]').click()"); time.sleep(.6)
    J("document.querySelector('[data-act=esqchg]').click()"); time.sleep(.6)
    J("document.querySelector('.es-chg [data-act=qref]').click()"); time.sleep(.4)
    ok('논술: 고른 질문 바꾸기 전 확인 안내', '한 번 더' in pg.inner_text('#toast'), pg.inner_text('#toast'))
    ok('논술: 한 번 누르면 그대로', prog()['picks'].get('b0') == 1)
    J("document.querySelector('.es-chg [data-act=qref]').click()")
    ok('논술: 두 번 누르면 바뀌고 처음 단계로', wait(lambda: 'b0' not in prog().get('picks', {}) and not prog()['prep']['b0'].get('qDone')), prog().get('picks'))
    J("document.querySelector('[data-act=stab][data-v=oral]').click()"); pg.wait_for_selector('.orcard', timeout=20000); time.sleep(.6)
    ok('구술: 질문 번호 옆 새로고침', pg.locator('.ortabs [data-act=orq1]').count() == 1)
    old = prog().get('oqs', {}).get('b0', {}).get('shown', [''])[0]
    J("document.querySelector('.ortabs [data-act=orq1]').click()")
    ok('구술: 지금 질문만 새 질문으로', wait(lambda: '새로 받은 구술 질문' in prog()['oqs']['b0']['shown'][0] and prog()['oqs']['b0']['shown'][0] != old), prog()['oqs']['b0']['shown'][:1])
    ok('구술: 질문 글은 여전히 숨김', pg.locator('.orcard .qtx').count() == 0)
    pg.screenshot(path=OUT + 'oral.png')
    b.close()
ok('페이지 오류 없음', not errs, errs[:3])
print('%d/%d' % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
