# 회원 구분(11-27): 학생 중1·중2·중3·기타 / 성인 부모·선생님·독서회원
# 친구 맺기는 중학생이면 같은 학년끼리만(서버가 막음), 성인은 책 읽기 시작 알림을 보내지 않음
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
U = {'gra1': ('중1', '2010-01'), 'grb1': ('중1', '2010-02'), 'grc2': ('중2', '2010-03'), 'grpa': ('부모', '1980-01'), 'grrd': ('독서회원', '1985-01'), 'gret': ('기타', '2010-01')}
def wipe():
    for u in U:
        r = api('auth.login', id=u, pw=PW)
        if 'result' in r: api('auth.withdraw', r['result']['session']['token'], pw=PW)
wipe()
S = {u: api('auth.signup', id=u, pw=PW, email=u + '@ex.com', agreeTerms=True, agreePrivacy=True, birth=b, grade=g, nick=u, gender='여')['result']['session'] for u, (g, b) in U.items()}
def fr(x, y):
    a, b = sorted([x, y])
    return api('db.set', S[x]['token'], path='friends/' + a + '__' + b, data={'a': a, 'b': b, 'from': x, 'to': y, 'status': 'pending', 'at': 1})
ok('중1 ↔ 중1 친구 요청 가능', 'result' in fr('gra1', 'grb1'))
ok('중1 → 중2 친구 요청 막힘', 'error' in fr('gra1', 'grc2'))
ok('부모 → 중1 친구 요청 막힘', 'error' in fr('grpa', 'gra1'))
ok('중1 → 부모 친구 요청 막힘', 'error' in fr('gra1', 'grpa'))
ok('기타 학생 → 중1 친구 요청 막힘', 'error' in fr('gret', 'gra1'))
ok('부모 ↔ 독서회원 친구 요청 가능', 'result' in fr('grpa', 'grrd'))
ok('기타 학생 ↔ 독서회원 친구 요청 가능', 'result' in fr('gret', 'grrd'))
a, b = sorted(['gra1', 'grb1'])
ok('같은 학년 친구 수락', 'result' in api('db.update', S['grb1']['token'], path='friends/' + a + '__' + b, data={'status': 'accepted'}))
a, b = sorted(['grpa', 'grrd'])
api('db.update', S['grrd']['token'], path='friends/' + a + '__' + b, data={'status': 'accepted'})
with sync_playwright() as p:
    br = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    pg = br.new_page(viewport={'width': 390, 'height': 844}); pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.goto(WEB + '/'); pg.wait_for_selector('[data-act=authtab][data-v=signup], [data-v=signup]', timeout=20000)
    pg.evaluate("document.querySelector('[data-v=signup]').click()"); time.sleep(.8)
    stu = pg.evaluate("[...document.querySelectorAll('select[name=grade]')][0] && [...[...document.querySelectorAll('select[name=grade]')][0].options].map(o=>o.value)")
    adu = pg.evaluate("[...document.querySelectorAll('select[name=grade]')][1] && [...[...document.querySelectorAll('select[name=grade]')][1].options].map(o=>o.value)")
    ok('가입: 학생 4종류(중1·중2·중3·기타)', stu == ['중1', '중2', '중3', '기타'], stu)
    ok('가입: 성인 3종류(부모·선생님·독서회원)', adu == ['부모', '선생님', '독서회원'], adu)
    def start_alerts(u):
        pg2 = br.new_page(viewport={'width': 390, 'height': 844}); pg2.on('pageerror', lambda e: errs.append(str(e)[:200]))
        sent = []; pg2.on('request', lambda r: sent.append(r.post_data or '') if r.method == 'POST' and '"alerts/' in (r.post_data or '') else None)
        pg2.goto(WEB + '/'); pg2.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))", S[u]); pg2.goto(WEB + '/'); pg2.wait_for_selector('.who', timeout=20000); time.sleep(1.5)
        pg2.evaluate("document.body.insertAdjacentHTML('beforeend','<button id=tst data-act=start data-i=0 data-k=book>x</button>');document.getElementById('tst').click()"); time.sleep(2)
        t = pg2.text_content('#toast') or ''; pg2.close(); return sent, t
    s1, t1 = start_alerts('gra1')
    ok('학생: 책 시작하면 친구에게 시작 알림', any('시작 알림' in x for x in s1) and '알렸어요' in t1, (len(s1), t1))
    s2, t2 = start_alerts('grrd')
    ok('독서회원: 책 시작해도 알림 안 보냄', not s2 and '알렸어요' not in t2, (s2[:1], t2))
    s3, t3 = start_alerts('grpa')
    ok('부모: 책 시작해도 알림 안 보냄', not s3, s3[:1])
    ok('화면 오류 없음', not errs, errs)
    br.close()
wipe()
print(f'{sum(res)}/{len(res)}'); sys.exit(0 if all(res) else 1)
