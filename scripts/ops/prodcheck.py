"""운영 사이트 점검: 페이지·정책 문서·앱 연결 파일이 열리는지, 신규 가입 → 로그인 → 내 정보 → 진도 저장 → 탈퇴까지
실제 서버에서 해 본다. 시험 계정은 매번 새로 만들고 마지막에 탈퇴해서 지운다(비밀번호는 실행할 때마다 무작위)."""
import json, os, secrets, sys, time, urllib.request, urllib.error

SITE = os.environ.get('SITE', 'https://002book.com').rstrip('/')
API = os.environ.get('API') or (os.environ['SUPABASE_URL'].rstrip('/') + '/functions/v1/api')
SUM = os.environ.get('GITHUB_STEP_SUMMARY'); res = []

def out(s):
    print(s)
    if SUM:
        with open(SUM, 'a') as f: f.write(s + '\n')
def ok(name, cond, info=''):
    res.append(bool(cond)); out(f"- {'✅' if cond else '❌'} {name}" + (f' — {info}' if (info and not cond) else ''))
def get(path):
    try:
        with urllib.request.urlopen(urllib.request.Request(SITE + path, headers={'User-Agent': 'Mozilla/5.0 002book-check'}), timeout=30) as r: return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e: return e.code, ''
def api(op, tok=None, **kw):
    h = {'content-type': 'application/json', 'Origin': SITE}
    if tok: h['x-session'] = tok
    try:
        with urllib.request.urlopen(urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST'), timeout=60) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read())
        except Exception: return {'error': {'code': e.code}}

out('### 사이트')
for p, must in [('/', '__002CFG'), ('/privacy.html', '개인정보'), ('/terms.html', '이용약관'), ('/delete-account.html', '삭제'), ('/manifest.webmanifest', 'start_url'), ('/sw.js', '')]:
    c, body = get(p); ok(f'{p} 열림', c == 200 and must in body, c)
c, body = get('/.well-known/assetlinks.json')
fp = c == 200 and 'sha256_cert_fingerprints' in body
out('- ' + ('✅ 앱 연결 파일(assetlinks.json)에 서명 지문 있음' if fp else '⚠ 앱 연결 파일(assetlinks.json)이 비어 있음 → 앱 위에 주소창이 보여요. ANDROID_SHA256 변수를 넣고 다시 배포'))

out('### 신규 가입 시험 (실서버, 끝나면 탈퇴)')
uid = 'qa' + secrets.token_hex(4); pw = secrets.token_urlsafe(12)
r = api('auth.signup', id=uid, pw=pw, email=f'{uid}@example.com', agreeTerms=True, agreePrivacy=True, birth='2000-01', grade='중1', nick='점검', gender='여', region='서울')
s = (r.get('result') or {}).get('session') or {}
ok('가입 (만 14세 이상)', bool(s.get('token')), r.get('error'))
tok = s.get('token')
if tok:
    r = api('auth.login', id=uid, pw=pw); t2 = ((r.get('result') or {}).get('session') or {}).get('token')
    ok('아이디·비밀번호 로그인', bool(t2), r.get('error'))
    r = api('auth.me', tok); ok('내 정보 확인', (r.get('result') or {}).get('uid') == uid, r)
    r = api('db.get', tok, path='members/' + uid); ok('회원 문서 읽기', ((r.get('result') or {}).get('data') or {}).get('nick') == '점검', r.get('error'))
    r = api('db.set', tok, path='progress/' + uid, data={'done': {}, 'at': int(time.time() * 1000)}); ok('진도 저장', 'error' not in r, r.get('error'))
    r = api('db.get', tok, path='progress/kotang77'); ok('다른 회원의 진도는 못 봄', not r.get('result'), r)
    r = api('auth.signup', id=uid, pw=pw, email=f'{uid}b@example.com', agreeTerms=True, agreePrivacy=True, birth='2000-01'); ok('같은 아이디 중복 가입 막음', (r.get('error') or {}).get('code') == 'id_taken', r.get('error'))
    r = api('auth.signup', id='qa' + secrets.token_hex(4), pw='short', email='x@example.com', agreeTerms=True, agreePrivacy=True, birth='2000-01'); ok('짧은 비밀번호 막음', (r.get('error') or {}).get('code') == 'weak_password', r.get('error'))
    r = api('auth.signup', id='qa' + secrets.token_hex(4), pw=pw, email='y@example.com', agreeTerms=True, agreePrivacy=True, birth='2015-01'); ok('만 14세 미만은 보호자 정보 요구', (r.get('error') or {}).get('code') == 'need_guardian', r.get('error'))
    r = api('auth.withdraw', tok, pw=pw); ok('탈퇴(시험 계정 삭제)', 'error' not in r, r.get('error'))
    r = api('auth.login', id=uid, pw=pw); ok('탈퇴 뒤 로그인 안 됨', 'error' in r)
out(f"\n결과: {sum(res)}/{len(res)} 통과")
sys.exit(0 if all(res) else 1)
