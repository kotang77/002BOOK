# 구글로 가입·로그인 시험 (가짜 서버: run.sh가 FAKE_GOOGLE로 가짜 ID 토큰 표를 넘긴다)
# 서버: 토큰 검증(이메일 확인·만료·발급자), 처음 오면 추가 정보 가입, 다시 오면 로그인, 보호자 동의, 이메일 중복 시 자동 연결 금지, 계정 연결, 구글로 탈퇴
# 앱: 구글 버튼(가짜 GIS 스크립트) → 추가 정보 양식 → 가입 → 내 정보(비밀번호 칸 없음) → 구글로 탈퇴, 비밀번호 회원의 구글 연결
import json, os, time, urllib.request
from playwright.sync_api import sync_playwright
API = 'http://localhost:8000'; WEB = 'http://localhost:8080'
OUT = os.environ.get('OUT', '/tmp/oraltest/') + 'google/'; os.makedirs(OUT, exist_ok=True)
res = []
def ok(n, c, x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ') + n + (' — ' + str(x)[:200] if x != '' else ''))
def api(op, tok=None, **kw):
    h = {'content-type': 'application/json'}
    if tok: h['x-session'] = tok
    r = urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST')
    try: return json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())
code = lambda r: (r.get('error') or {}).get('code')
G = dict(agreeTerms=True, agreePrivacy=True, grade='중1', gender='여', region='경기')
def clean_pw(uid):
    r = api('auth.login', id=uid, pw='testpass1234')
    if 'result' in r: api('auth.withdraw', r['result']['session']['token'], pw='testpass1234')
def clean_g(tok):
    r = api('auth.google', credential=tok)
    if r.get('result', {}).get('session'): api('auth.withdraw', r['result']['session']['token'], credential=tok)

for t in ['gtok_new', 'gtok_ui', 'gtok_taken', 'gtok_link']: clean_g(t)
for u in ['gtaken01', 'glinkui', 'gother01']: clean_pw(u)

# ---- 서버 ----
r = api('auth.google', credential='gtok_new')['result']
ok('처음 온 구글 계정은 추가 정보 요청', r.get('needSignup') and r.get('email') == 'gnew@gmail.com' and r.get('idHint') == 'gnew' and not r.get('session'), r)
ok('모르는 토큰 거절', code(api('auth.google', credential='nope')) == 'bad_google')
ok('이메일 미확인 구글 계정 거절', code(api('auth.google', credential='gtok_unverified')) == 'bad_google')
ok('만료된 토큰 거절', code(api('auth.google', credential='gtok_expired')) == 'google_expired')
ok('발급자가 구글이 아니면 거절', code(api('auth.google', credential='gtok_badiss')) == 'bad_google')
ok('동의 없으면 가입 안 됨', code(api('auth.google', credential='gtok_new', signup=True, id='gnew01', birth='2008-01', gender='여')) == 'need_agree')
r = api('auth.google', credential='gtok_new', signup=True, id='gnew01', birth='2008-01', nick='구글이', **G)
ok('구글 가입 완료·세션 발급', r.get('result', {}).get('session', {}).get('uid') == 'gnew01', r)
m = r['result']['member']; tok1 = r['result']['session']['token']
ok('가입 정보: 구글 이메일·구글 전용 표시', m.get('email') == 'gnew@gmail.com' and m.get('gOnly') is True and m.get('google') is True, m)
r = api('auth.google', credential='gtok_new')['result']
ok('다시 오면 바로 로그인', r.get('session', {}).get('uid') == 'gnew01' and r.get('member', {}).get('id') == 'gnew01', r)
ok('같은 구글로 또 가입하면 로그인으로 처리', api('auth.google', credential='gtok_new', signup=True, id='gnew02', birth='2008-01', **G).get('result', {}).get('session', {}).get('uid') == 'gnew01')
ok('구글 가입 계정은 아이디·비밀번호 로그인 불가', code(api('auth.login', id='gnew01', pw='testpass1234')) == 'bad_password')
g = api('db.get', tok1, path='sys/google_1000001'); ok('연결 정보(sys/)는 회원이 읽지 못함', not g.get('result'), g)
ok('구글 아이디 중복 거절', code(api('auth.google', credential='gtok_link', signup=True, id='gnew01', birth='2008-01', **G)) == 'id_taken')
ok('탈퇴: 비밀번호로는 안 됨', code(api('auth.withdraw', tok1, pw='')) == 'bad_password')
ok('탈퇴: 다른 구글 계정으로는 안 됨', code(api('auth.withdraw', tok1, credential='gtok_link')) == 'bad_google')
ok('탈퇴: 연결된 구글로 확인하면 됨', api('auth.withdraw', tok1, credential='gtok_new').get('result', {}).get('ok') is True)
ok('탈퇴 뒤 연결도 지워짐(다시 오면 새 가입)', api('auth.google', credential='gtok_new')['result'].get('needSignup') is True)
# 만 14세 미만 (가짜 서버를 다시 켜지 않고 두 번째 돌릴 때는 대기 계정이 남아 있어 건너뜀)
if code(api('auth.google', credential='gtok_minor')) != 'guardian_pending':
  r = api('auth.google', credential='gtok_minor', signup=True, id='gkid01', birth='2015-03', **G)
  ok('만 14세 미만은 보호자 정보 필요', code(r) == 'need_guardian')
  r = api('auth.google', credential='gtok_minor', signup=True, id='gkid01', birth='2015-03', guardianName='엄마', guardianEmail='mom@ex.com', **G)
  ok('만 14세 미만 구글 가입 → 보호자 동의 대기', r.get('result', {}).get('pending') == 'guardian' and not r['result'].get('session'), r)
ok('보호자 동의 전에는 구글 로그인 불가', code(api('auth.google', credential='gtok_minor')) == 'guardian_pending')
# 이메일이 같은 기존 회원: 자동 연결하지 않음
s = api('auth.signup', id='gtaken01', pw='testpass1234', email='gtaken@ex.com', birth='2009-01', nick='기존', **G)['result']['session']
r = api('auth.google', credential='gtok_taken')['result']
ok('이메일이 같아도 자동 로그인·연결 안 함', r.get('needSignup') is True and not r.get('session'))
r = api('auth.google', credential='gtok_taken', signup=True, id='gtaken02', birth='2009-01', **G)
ok('이메일 중복 가입 거절 + 연결 안내', code(r) == 'email_taken' and '연결' in r['error']['message'], r)
ok('계정 연결: 로그인해야 함', code(api('auth.googleLink', credential='gtok_taken')) == 'unauthenticated')
ok('계정 연결 성공', api('auth.googleLink', s['token'], credential='gtok_taken').get('result', {}).get('email') == 'gtaken@ex.com')
r = api('auth.google', credential='gtok_taken')['result']
ok('연결 뒤 구글로 기존 아이디 로그인', r.get('session', {}).get('uid') == 'gtaken01' and r['member'].get('google') is True and not r['member'].get('gOnly'), r)
ok('연결 뒤에도 비밀번호 로그인 유지', 'result' in api('auth.login', id='gtaken01', pw='testpass1234'))
s2 = api('auth.signup', id='gother01', pw='testpass1234', email='gother@ex.com', birth='2009-01', **G)['result']['session']
ok('다른 아이디에 연결된 구글은 연결 불가', code(api('auth.googleLink', s2['token'], credential='gtok_taken')) == 'google_taken')
ok('연결 회원은 비밀번호로 탈퇴', api('auth.withdraw', s['token'], pw='testpass1234').get('result', {}).get('ok') is True)
ok('연결 회원 탈퇴 뒤 연결 지워짐', api('auth.google', credential='gtok_taken')['result'].get('needSignup') is True)
api('auth.withdraw', s2['token'], pw='testpass1234')

# ---- 앱 ----
FAKE_GSI = """window.google={accounts:{id:{initialize(o){window.__gcfg=o},disableAutoSelect(){},prompt(){},
 renderButton(el,o){const b=document.createElement('button');b.type='button';b.className='fakegsi';b.textContent='G '+o.text;b.style.cssText='height:40px;border:1px solid #dadce0;border-radius:20px;background:#fff;width:'+o.width+'px';
 b.onclick=()=>window.__gcfg.callback({credential:window.__gTok});el.appendChild(b)}}}};"""
def setup(ctx, google=True):
    if google:
        ctx.route('**/runtime/config.js', lambda rt: rt.fulfill(status=200, content_type='application/javascript',
            body=urllib.request.urlopen(WEB + '/runtime/config.js').read().decode().replace('"google":""', '"google":"test.apps.googleusercontent.com"')))
    ctx.route('https://accounts.google.com/gsi/client', lambda rt: rt.fulfill(status=200, content_type='application/javascript', body=FAKE_GSI))
def uid(pg): return pg.evaluate("(()=>{try{const s=JSON.parse(localStorage.getItem('002.session'));return document.querySelector('#li-id')?null:(s&&s.uid)}catch(e){return null}})()")
def act(pg, a): pg.evaluate("a=>{const b=document.createElement('button');b.dataset.act=a;b.hidden=true;document.querySelector('#app').appendChild(b);b.click();b.remove()}", a)
def wait(f, n=60):
    for _ in range(n):
        try:
            if f(): return True
        except Exception: pass
        time.sleep(.25)
    return False
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', args=['--no-sandbox'])
    ctx0 = b.new_context(viewport={'width': 390, 'height': 844}); setup(ctx0, False); pg0 = ctx0.new_page(); pg0.goto(WEB); pg0.wait_for_selector('#li-id')
    ok('설정이 없으면 구글 버튼 숨김', pg0.locator('.gsi').count() == 0); ctx0.close()
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True); setup(ctx)
    pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(WEB); pg.wait_for_selector('#li-id')
    ok('로그인 화면에 구글 버튼', wait(lambda: pg.locator('[data-gsi=auth] .fakegsi').count() == 1) and 'signin_with' in pg.inner_text('.fakegsi'))
    pg.screenshot(path=OUT + 'login.png')
    pg.click('[data-act=authtab][data-v=signup]')
    ok('가입 탭에는 "구글로 가입" 버튼', wait(lambda: 'signup_with' in pg.inner_text('.fakegsi')))
    pg.evaluate("window.__gTok='gtok_ui'"); pg.click('.fakegsi')
    ok('구글 확인 뒤 추가 정보 양식', wait(lambda: pg.locator('form[data-form=gsignup]').count() == 1))
    ok('양식: 구글 이메일 안내·아이디 미리 채움', 'gbrowser@gmail.com' in pg.inner_text('form[data-form=gsignup]') and pg.input_value('#su-id') == 'gbrowser' and pg.input_value('#su-nick') == '브라우저')
    ok('양식: 비밀번호·이메일 칸 없음', pg.locator('#su-pw').count() == 0 and pg.locator('#su-email').count() == 0)
    pg.select_option('#su-gender', index=1); pg.fill('#su-birth', '2009-03')
    pg.screenshot(path=OUT + 'gsignup.png', full_page=True)
    pg.check('input[name=agt]'); pg.check('input[name=agp]')
    pg.click('form[data-form=gsignup] button[type=submit]')
    g = wait(lambda: uid(pg) == 'gbrowser'); pg.screenshot(path=OUT + 'after.png', full_page=True)
    ok('구글 가입 뒤 학습 화면', g, (pg.inner_text('#autherr') if pg.locator('#autherr').count() else '') + ' ' + ';'.join(errs))
    act(pg, 'profile')
    ok('내 정보: 비밀번호 칸 대신 로그인 방법 안내', wait(lambda: '로그인 방법' in pg.inner_text('#layer1')) and pg.locator('#pf-cur').count() == 0)
    ok('내 정보: 탈퇴는 구글 확인 버튼', wait(lambda: pg.locator('[data-gsi=withdraw] .fakegsi').count() == 1) and pg.locator('#wd-pw').count() == 0)
    pg.click('[data-gsi=withdraw] .fakegsi')
    ok('체크 안 하면 탈퇴 안 됨', wait(lambda: '체크' in pg.inner_text('#wderr')))
    pg.check('form[data-form=withdraw] input[name=ok]'); pg.click('[data-gsi=withdraw] .fakegsi')
    ok('구글로 확인하고 탈퇴', wait(lambda: pg.locator('#li-id').count() == 1) and uid(pg) is None)
    ok('탈퇴 뒤 구글 연결 지워짐', api('auth.google', credential='gtok_ui')['result'].get('needSignup') is True)
    # 비밀번호 회원: 구글 연결
    api('auth.signup', id='glinkui', pw='testpass1234', email='glinkui@ex.com', birth='2009-01', nick='연결이', **G)
    pg.fill('#li-id', 'glinkui'); pg.fill('#li-pw', 'testpass1234'); pg.click('form[data-form=login] button[type=submit]')
    wait(lambda: uid(pg) == 'glinkui')
    act(pg, 'profile')
    ok('비밀번호 회원: 구글 계정 연결 버튼', wait(lambda: pg.locator('[data-gsi=link] .fakegsi').count() == 1) and pg.locator('#pf-cur').count() == 1)
    pg.evaluate("window.__gTok='gtok_link'"); pg.click('[data-gsi=link] .fakegsi')
    ok('연결 완료 안내', wait(lambda: '연결돼 있어요' in pg.inner_text('#layer1')))
    act(pg, 'logout'); wait(lambda: pg.locator('.fakegsi').count() == 1)
    pg.click('.fakegsi')
    ok('로그아웃 뒤 구글로 기존 아이디 로그인', wait(lambda: uid(pg) == 'glinkui'))
    ok('페이지 오류 없음', not errs, errs)
    act(pg, 'logout')
    b.close()
api('auth.withdraw', api('auth.login', id='glinkui', pw='testpass1234')['result']['session']['token'], pw='testpass1234')
print(f'{sum(res)}/{len(res)}')
raise SystemExit(0 if all(res) else 1)
