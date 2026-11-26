"""002BOOK 끝-끝 테스트(가짜 서버): 관리자 로그인 → 화면 확인 → 회원가입(성인/만14세 미만) → 보호자 동의 → 비밀번호 찾기 → 탈퇴 → 권한 확인
실행: tests/oral/run.sh ../e2e.py"""
import json, re, sys, time, urllib.request
from playwright.sync_api import sync_playwright

WEB = 'http://localhost:8080'
API = 'http://localhost:8000'
errors, results = [], []

def ok(name, cond, extra=''):
    results.append((name, bool(cond), extra))
    print(('PASS ' if cond else 'FAIL ') + name + (' — ' + extra if extra else ''))

def api(op, session=None, **kw):
    h = {'content-type': 'application/json'}
    if session: h['x-session'] = session
    req = urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST')
    try:
        return json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())

with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, locale='ko-KR')
    page = ctx.new_page()
    page.on('pageerror', lambda e: errors.append('pageerror: ' + str(e)))
    page.on('console', lambda m: m.type == 'error' and errors.append('console: ' + m.text))

    # 1) 관리자·회원 준비 (그랜드 오픈 리셋 뒤처럼 빈 서버에서 가입)
    for uid, nick in [('kotang77', '관리자'), ('rich_claire', '클레어')]:
        r = api('auth.login', None, id=uid, pw='testpass1234')
        if 'result' in r: api('auth.withdraw', r['result']['session']['token'], pw='testpass1234')
        r = api('auth.signup', None, id=uid, pw='testpass1234', email=uid + '@ex.com', agreeTerms=True, agreePrivacy=True, birth='1980-01', grade='중1', nick=nick, gender='여')
        ok(f'가입 {uid}', 'result' in r, str(r)[:120])
    page.goto(WEB + '/'); page.evaluate("localStorage.clear()")
    # 2) 관리자 로그인 → 메인 화면
    page.goto(WEB + '/')
    page.wait_for_selector('form[data-form=login]', timeout=15000)
    page.screenshot(path='/tmp/s1_login.png')
    page.fill('#li-id', 'kotang77'); page.fill('#li-pw', 'testpass1234')
    page.click('form[data-form=login] button[type=submit]')
    page.wait_for_selector('.who', timeout=15000)
    time.sleep(2)
    page.screenshot(path='/tmp/s2_main.png')
    ok('관리자 로그인·메인 화면', page.locator('.who').count() > 0, page.inner_text('.who'))
    ok('관리자 배지', '관리자' in page.content())
    # 새로고침해도 로그인 유지
    page.reload(); page.wait_for_selector('.who', timeout=15000)
    ok('새로고침 후 로그인 유지', True)
    sess = page.evaluate("JSON.parse(localStorage.getItem('002.session')).token")

    # 관리 화면
    page.evaluate("document.querySelector('[data-act=view][data-v=admin]')&&document.querySelector('[data-act=view][data-v=admin]').click()")
    time.sleep(2); page.screenshot(path='/tmp/s3_admin.png')
    ok('관리 화면에 회원 목록', '전체 회원' in page.content() and 'rich_claire' in page.content())

    # 로그아웃
    page.evaluate("document.querySelector('[data-act=logout]').click()")
    page.wait_for_selector('form[data-form=login]', timeout=10000)
    ok('로그아웃 → 세션 삭제', api('auth.me', sess).get('error', {}).get('code') == 'unauthenticated')

    # 3) 성인 회원가입
    page.evaluate("document.querySelector('[data-act=authtab][data-v=signup]').click()")
    page.wait_for_selector('#su-id')
    page.screenshot(path='/tmp/s4_signup.png', full_page=True)
    nxt = lambda: page.click('form[data-form=signup] [data-act=sunext]')
    page.fill('#su-id', 'tester01'); page.fill('#su-pw', 'abcd1234!'); page.fill('#su-pw2', 'abcd1234?'); page.fill('#su-nick', '테스터')
    page.fill('#su-email', 'tester01@example.com'); nxt()
    ok('비밀번호 다시 입력이 다르면 못 넘어감', page.get_attribute('form[data-form=signup]', 'data-step') == '1' and '비밀번호' in page.inner_text('#autherr'))
    page.fill('#su-pw2', 'abcd1234!'); nxt()
    ok('가입 2단계로 넘어감', page.get_attribute('form[data-form=signup]', 'data-step') == '2')
    nxt(); ok('성별 안 고르면 다음으로 못 감', page.get_attribute('form[data-form=signup]', 'data-step') == '2' and '성별' in page.inner_text('#autherr'))
    ok('2단계 순서: 성별(남자·여자) → 중학생·성인', page.evaluate("(()=>{const f=document.querySelector('form[data-form=signup] [data-s=\"2\"]');const a=f.querySelector('.chipf'),b=f.querySelector('.gkind');return !!(a&&b&&(a.compareDocumentPosition(b)&4))&&f.querySelector('label[for=su-g0]').innerText.trim()==='남자'&&f.querySelector('.gkind').innerText.includes('중학생')})()"))
    page.click('label[for=su-g0]')
    page.select_option('#su-grade', label='부모') if page.locator('#su-grade option', has_text='부모').count() else None
    page.fill('#su-birth', '1985-03'); nxt()
    page.click('label[for=su-th-sky]')
    ok('앱 색 하늘 미리 적용', page.evaluate("document.documentElement.dataset.theme") == 'sky')
    nxt(); ok('성인은 보호자 칸 없음', page.locator('#su-guard').is_hidden())
    page.check('input[name=agt]'); page.check('input[name=agp]')
    page.screenshot(path='/tmp/s4_signup.png', full_page=True)
    page.click('form[data-form=signup] button[type=submit]')
    page.wait_for_selector('.who', timeout=15000)
    ok('성인 회원가입 → 바로 입장', True)
    ok('앱 색 저장(하늘)', page.evaluate("document.documentElement.dataset.theme") == 'sky')
    s2 = page.evaluate("JSON.parse(localStorage.getItem('002.session')).token")

    # 권한: 남의 진도·비공개 정보
    r = api('db.get', s2, path='progress/kotang77'); ok('남의 진도 못 읽음', r.get('result') is None, str(r)[:80])
    r = api('db.get', s2, path='members/kotang77'); d = (r.get('result') or {}).get('data', {})
    ok('남의 이메일·비번 안 보임', d and 'email' not in d and 'pw' not in d and 'salt' not in d and 'seen' not in d, ','.join(d.keys())[:120])
    r = api('db.set', s2, path='config/plans', data={'paid': {'tester01': {'at': 1}}}); ok('스스로 유료회원 못 됨', r.get('error', {}).get('code') == 'permission_denied')
    r = api('db.update', s2, path='members/kotang77', data={'nick': 'x'}); ok('남의 회원정보 못 바꿈', r.get('error', {}).get('code') == 'permission_denied')
    r = api('db.query', s2, collection='diaries'); ok('남의 일기 안 보임', r.get('result') == [], str(r)[:80])
    r = api('db.set', s2, path='diaries/tester01_2026-11-24', data={'uid': 'tester01', 'date': '2026-11-24'}); ok('일기 새로 못 씀(기능 종료)', r.get('error', {}).get('code') == 'permission_denied', str(r)[:80])
    r = api('db.set', s2, path='works/tester01_w1', data={'uid': 'tester01', 'id': 'w1', 'parts': []}); ok('책만들기 새로 못 씀(기능 종료)', r.get('error', {}).get('code') == 'permission_denied', str(r)[:80])
    r = api('db.set', s2, path='dykeys/tester01', data={'v': 1}); ok('일기 열쇠 새로 못 씀', r.get('error', {}).get('code') == 'permission_denied', str(r)[:80])
    r = api('media.art', s2, kind='book', title='순례주택 (유은실)'); ok('책 표지 자동 찾기', str((r.get('result') or {}).get('url')).startswith('data:image/png'), str(r)[:120])
    r = api('media.art', s2, kind='book', title='순례주택'); ok('같은 제목은 캐시', (r.get('result') or {}).get('cached') is True, str(r)[:120])
    r = api('media.art', s2, kind='movie', title='우리집', year='2019'); ok('영화 포스터 자동 찾기', str((r.get('result') or {}).get('url')).startswith('data:image/png'), str(r)[:120])
    r = api('media.art', s2, kind='movie', title='없는영화제목'); ok('못 찾으면 빈 주소', (r.get('result') or {}).get('url') == '', str(r)[:120])
    r = api('media.art', None, kind='book', title='순례주택'); ok('로그인 없이 표지 찾기 불가', r.get('error', {}).get('code') == 'unauthenticated', str(r)[:120])
    r = api('db.get', s2, path='sys/artuse_tester01'); ok('표지 조회 기록은 회원이 못 읽음', r.get('result') is None, str(r)[:80])
    r = api('db.query', s2, collection='evals'); ok('남의 첨삭 안 보임', r.get('result') == [], str(r)[:80])
    r = api('db.query', s2, collection='members'); ok('회원 목록은 공개 정보만', all('email' not in x['data'] for x in r.get('result', []) if x['id']!='tester01'), str(len(r.get('result', []))) + '명')
    r = api('db.set', s2, path='progress/tester01', data={'done': {'b0:book': 1}}); ok('내 진도 저장', 'result' in r)
    r = api('ai.sample', s2, messages=[{'role': 'user', 'content': '안녕'}]); ok('AI 호출(가짜)', 'result' in r)
    r = api('ai.sample', None, messages=[{'role': 'user', 'content': '안녕'}]); ok('로그인 없이 AI 못 씀', r.get('error', {}).get('code') == 'unauthenticated')

    # 비밀번호 바꾸기 & 이전 해시 업그레이드 확인
    r = api('auth.changePassword', s2, oldPw='abcd1234!', newPw='newpass999'); ok('비밀번호 변경', 'result' in r, str(r)[:80])
    r = api('auth.login', None, id='tester01', pw='abcd1234!'); ok('옛 비밀번호 거부', r.get('error', {}).get('code') == 'bad_password')

    # 4) 만 14세 미만 가입 → 보호자 동의
    page.evaluate("document.querySelector('[data-act=logout]').click()")
    page.wait_for_selector('form[data-form=login]')
    page.evaluate("document.querySelector('[data-act=authtab][data-v=signup]').click()")
    nxt = lambda: page.click('form[data-form=signup] [data-act=sunext]')
    page.fill('#su-id', 'kid01'); page.fill('#su-pw', 'kidpass123'); page.fill('#su-pw2', 'kidpass123'); page.fill('#su-nick', '꼬마'); page.fill('#su-email', 'kid01@example.com'); nxt()
    page.click('label[for=su-g1]'); page.fill('#su-birth', '2014-05'); nxt(); page.click('label[for=su-th-cream]'); nxt()
    ok('만 14세 미만은 보호자 칸 보임', page.locator('#su-guard').is_visible())
    page.check('input[name=agt]'); page.check('input[name=agp]')
    page.click('form[data-form=signup] button[type=submit]')
    time.sleep(1.5)
    ok('보호자 없으면 거절', '보호자' in page.inner_text('#autherr'), page.inner_text('#autherr'))
    page.fill('#su-gname', '보호자'); page.fill('#su-gemail', 'parent@example.com')
    page.click('form[data-form=signup] button[type=submit]')
    page.wait_for_selector('.okmsg', timeout=10000)
    ok('보호자 동의 요청 안내', '보호자' in page.inner_text('.okmsg'))
    r = api('auth.login', None, id='kid01', pw='kidpass123'); ok('동의 전 로그인 막힘', r.get('error', {}).get('code') == 'guardian_pending')
    time.sleep(.5)
    m = re.findall(r'guardian\.html\?t=([A-Za-z0-9_%-]+)', open('/tmp/api.log').read())
    ok('보호자 메일 발송', bool(m))
    if m:
        g = ctx.new_page(); g.goto(WEB + '/guardian.html?t=' + m[-1]); g.wait_for_selector('#f', timeout=10000)
        ok('보호자 동의 페이지(링크만 열어서는 동의 안 됨)', api('auth.login', None, id='kid01', pw='kidpass123').get('error', {}).get('code') == 'guardian_pending')
        g.screenshot(path='/tmp/s7_guardian.png', full_page=True)
        g.fill('input[name=name]', '김보호'); g.select_option('select[name=rel]', label='모'); g.check('input[name=ok]'); g.check('input[name=ok2]')
        g.click('#f button[type=submit]'); g.wait_for_selector('.card', timeout=10000); time.sleep(.5)
        ok('보호자 동의 완료', '동의가 완료' in g.inner_text('#box'))
        ok('보호자 확인 메일', '보호자 동의가 확인' in open('/tmp/api.log').read())
        r = api('auth.login', None, id='kid01', pw='kidpass123'); ok('동의 후 로그인', 'result' in r)
        kid = r['result']['session']['token']
        r = api('db.get', kid, path='members/kid01'); ok('만14세 미만 마케팅 동의 저장 안 함', r['result']['data'].get('marketing') is False)
        g.close()

    # 4-2) 공개 설정: 기본은 닉네임만, 켠 항목만 보임
    r = api('auth.login', None, id='tester01', pw='newpass999'); t1 = r['result']['session']['token']
    api('db.update', t1, path='members/tester01', data={'bio': '안녕', 'region': '경기', 'grade': '중1'})
    view = lambda: api('db.get', kid, path='members/tester01')['result']['data']
    v = view(); ok('기본: 닉네임만 공개', set(v.keys()) <= {'id', 'nick', 'pub', 'avatar'} and v['nick'] == '테스터', ','.join(v.keys()))
    api('db.update', t1, path='members/tester01', data={'pub': {'bio': True, 'region': False, 'grade': True, 'photo': False}})
    v = view(); ok('공개 켠 항목만 보임', v.get('bio') == '안녕' and v.get('grade') == '중1' and 'region' not in v, ','.join(v.keys()))

    # 5) 비밀번호 찾기 (메일)
    page.evaluate("document.querySelector('[data-act=authtab][data-v=find]').click()")
    page.fill('#fd-id', 'tester01'); page.fill('#fd-email', 'tester01@example.com')
    page.click('form[data-form=find] button[type=submit]'); time.sleep(1.5)
    tmp = re.findall(r'임시 비밀번호는 아래와 같아요\.\s+(\S+)', open('/tmp/api.log').read())
    ok('임시 비밀번호 메일', bool(tmp))
    if tmp:
        page.fill('#li-id', 'tester01'); page.fill('#li-pw', tmp[-1]); page.click('form[data-form=login] button[type=submit]')
        page.wait_for_selector('.who', timeout=10000); time.sleep(1)
        ok('임시 비번 로그인 → 비번 변경 화면', '임시 비밀번호' in page.content())
        page.screenshot(path='/tmp/s5_tmp.png')

    # 6) 탈퇴
    r = api('auth.login', None, id='kid01', pw='kidpass123'); ks = r['result']['session']['token']
    r = api('auth.withdraw', ks, pw='kidpass123'); ok('탈퇴', 'result' in r)
    r = api('auth.login', None, id='kid01', pw='kidpass123'); ok('탈퇴 후 계정 없음', r.get('error', {}).get('code') == 'no_user')

    # 7) 데스크톱 화면
    d = b.new_page(viewport={'width': 1280, 'height': 860})
    d.goto(WEB + '/'); d.wait_for_selector('form[data-form=login]'); d.fill('#li-id', 'kotang77'); d.fill('#li-pw', 'testpass1234')
    d.click('form[data-form=login] button[type=submit]'); d.wait_for_selector('.who', timeout=15000); time.sleep(2)
    d.screenshot(path='/tmp/s6_desktop.png')
    b.close()

errs = [e for e in errors if 'fonts.g' not in e and 'cdnjs' not in e and 'favicon' not in e]
print('\n브라우저 오류:', len(errs)); [print(' ', e[:200]) for e in errs[:15]]
print('%d/%d' % (sum(1 for r in results if r[1]), len(results)))

sys.exit(0 if all(r[1] for r in results) else 1)
