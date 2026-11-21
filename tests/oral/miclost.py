import json, time, sys, os
from playwright.sync_api import sync_playwright
import importlib.util
API = 'http://localhost:8000'; WEB = 'http://localhost:8080'; OUT = os.environ.get('OUT','/tmp/oraltest/')+'mic/'
import urllib.request
os.makedirs(OUT, exist_ok=True)


def api(op, tok=None, **kw):
    h = {'content-type': 'application/json'}
    if tok: h['x-session'] = tok
    r = urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST')
    try: return json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())


res = []
def ok(n, c, x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ') + n + (' — ' + str(x)[:200] if x != '' else ''))

def mk(uid):
    r = api('auth.login', id=uid, pw='testpass1234')
    if 'result' in r: api('auth.withdraw', r['result']['session']['token'], pw='testpass1234')
    r = api('auth.signup', id=uid, pw='testpass1234', email=uid + '@ex.com', agreeTerms=True, agreePrivacy=True, birth='2010-01', grade='중1', nick=uid, gender='여')
    return r['result']['session']

s = mk('dropkid'); tok = s['token']
sv = {k: {'fun': 4, 'diff': 3, 'again': 4} for k in ['b0:book', 'b0:m1', 'b0:m2']}
api('db.set', tok, path='progress/dropkid', data={'done': {k: 1 for k in sv}, 'survey': sv, 'notes': {}, 'qs': {}, 'evalLog': [], 'drafts': {}, 'picks': {}})

TTS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'flow.py'),encoding='utf-8').read().split("TTS='''")[1].split("'''")[0]
# 다음 녹음 N번은 0.3초 만에 마이크가 저절로 끊긴 것처럼 만든다
DROP = '''(()=>{window.__drop=0;window.__starts=0;const st=MediaRecorder.prototype.start;
MediaRecorder.prototype.start=function(...a){window.__starts++;const r=st.apply(this,a);if(window.__drop>0){window.__drop--;setTimeout(()=>{try{this.stop()}catch(e){}},300)}return r}})()'''
errs = []
def toast(pg): return pg.evaluate("(()=>{const t=document.querySelector('#toast');return t?t.textContent:''})()")
def hint(pg): return pg.evaluate("(()=>{const b=document.querySelector('[data-act=oreval]');return b&&b.nextElementSibling?b.nextElementSibling.textContent:''})()")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, locale='ko-KR', permissions=['microphone'], service_workers='block')
    ctx.add_init_script(TTS); ctx.add_init_script(DROP)
    pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.goto(WEB + '/'); pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))", s); pg.goto(WEB + '/'); pg.wait_for_selector('.who', timeout=20000); time.sleep(1.2)
    pg.evaluate("document.querySelector('[data-act=month][data-i=\"0\"]').click()"); time.sleep(.8)
    pg.evaluate("document.querySelector('[data-act=stab][data-v=oral]').click()"); pg.wait_for_selector('.orcard', timeout=20000); time.sleep(.5)

    def go(n):
        pg.evaluate(f"document.querySelector('[data-act=orgo][data-s=\"{n}\"]').click()"); time.sleep(.3)
        pg.evaluate("document.querySelector('[data-act=orsay]').click()"); time.sleep(1.6)

    def start(n): pg.evaluate(f"document.querySelector('[data-act=orrec][data-n=\"{n}\"][data-m=\"1\"]').click()")

    def stop():
        pg.evaluate("document.querySelector('[data-act=orstop]').click()"); pg.wait_for_selector('#or-t', state='detached', timeout=15000); time.sleep(.5)

    # 질문 1·2: 정상
    for n in range(2):
        go(n); start(n); pg.wait_for_selector('#or-t', timeout=10000); time.sleep(4.2); stop()
        pg.fill(f'textarea[data-ortx="{n}"]', f'{n+1}번 질문에 대한 저의 생각은 이렇습니다 이유는 두 가지예요'); time.sleep(1.1)
    ok('1·2번 저장', hint(pg).startswith('답변 2 / 3'), hint(pg))

    # 질문 3: 마이크가 한 번 바로 끊김 → 자동으로 다시 연결해 녹음이 이어져야 함
    go(2); pg.evaluate('window.__drop=1'); s0 = pg.evaluate('window.__starts')
    start(2); time.sleep(1.0)
    t1 = toast(pg); ok('끊김 안내', '다시 연결' in t1, t1)
    time.sleep(1.5)
    ok('자동 재시작', pg.evaluate('window.__starts') - s0 == 2 and pg.locator('#or-t').count() == 1, pg.evaluate('window.__starts') - s0)
    pg.screenshot(path=OUT + '1_retry.png')
    time.sleep(3.5); stop()
    ok('3번 녹음 저장', pg.locator('textarea[data-ortx="2"]').count() == 1)
    secs = pg.evaluate("document.querySelector('.orcard .tagk').textContent")
    ok('녹음 시간 표시 정상', 'NaN' not in secs and 'undefined' not in secs, secs)
    ok('빈 답 안내', '3번은 녹음은 됐는데 말한 내용이 비어' in hint(pg), hint(pg))
    pg.fill('textarea[data-ortx="2"]', '저는 매일 조금씩 노력하는 습관을 만들고 싶어요 작은 실천이 쌓이기 때문이에요'); time.sleep(1.1)
    ok('평가 버튼 열림', pg.locator('[data-act=oreval]:not([disabled])').count() == 1, hint(pg))

    # 세 번 연속 끊기면: 저장하지 않고 안내
    pg.evaluate('window.__drop=3'); s0 = pg.evaluate('window.__starts')
    pg.evaluate("document.querySelector('[data-act=orrec][data-n=\"2\"][data-m=\"1\"]').click()")
    time.sleep(4)
    ok('세 번 시도 후 멈춤', pg.evaluate('window.__starts') - s0 == 3 and pg.locator('#or-t').count() == 0, pg.evaluate('window.__starts') - s0)
    ok('마이크 확인 안내', '다른 앱이 마이크' in toast(pg), toast(pg))
    d = api('db.get', tok, path='orals/dropkid_b0_a')['result']['data']
    ok('기존 3번 답 보존', '작은 실천' in (d['ans'][2] or {}).get('text', ''), d['ans'][2])
    pg.screenshot(path=OUT + '2_gaveup.png')
    ok('페이지 오류 없음', not errs, errs)
    b.close()
print(f'{sum(res)}/{len(res)}')

sys.exit(0 if all(res) else 1)
