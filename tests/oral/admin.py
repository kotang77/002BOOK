# 관리자 대시보드 시험 (가짜 서버)
# 서버: 관리자 추가(최고 관리자만, 성인만), 추가 관리자 권한, 시험 재시험(보관)·리셋, 진도 덮어쓰기 방지, 평가 기준 설정 저장 권한
# 앱: 지표 타일, 펼치는 메뉴(한 번에 하나), 회원 필터·정렬, 회원 상세 탭, 재시험 주기, 평가 기준 편집, 월별 코스 편집, 관리자 추가·해제
import json, os, time, urllib.request
from playwright.sync_api import sync_playwright
API = 'http://localhost:8000'; WEB = 'http://localhost:8080'
OUT = os.environ.get('OUT', '/tmp/oraltest/') + 'admin/'; os.makedirs(OUT, exist_ok=True)
res = []
def ok(n, c, x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ') + n + (' — ' + str(x)[:220] if x != '' else ''))
def api(op, tok=None, **kw):
    h = {'content-type': 'application/json'}
    if tok: h['x-session'] = tok
    r = urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST')
    try: return json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())
code = lambda r: (r.get('error') or {}).get('code')
PW = 'testpass1234'
def user(uid, birth, grade, gender, nick):
    r = api('auth.login', id=uid, pw=PW)
    if 'result' in r:
        if uid != 'kotang77': api('auth.withdraw', r['result']['session']['token'], pw=PW)
        else: return r['result']['session']
    r = api('auth.signup', id=uid, pw=PW, email=uid + '@ex.com', agreeTerms=True, agreePrivacy=True, birth=birth, grade=grade, nick=nick, gender=gender)
    return r['result']['session'] if 'result' in r else api('auth.login', id=uid, pw=PW)['result']['session']
own = user('kotang77', '1980-01', '아빠', '남자', '관리자')
s1 = user('adm_s1', '2012-03', '중1', '여자', '하늘')
s2 = user('adm_s2', '2011-05', '중2', '남자', '바다')
p1 = user('adm_p1', '1982-04', '엄마', '여자', '엄마쌤')
p2 = user('adm_p2', '1979-09', '아빠', '남자', '아빠쌤')
T = own['token']
for u in ['adm_p1', 'adm_p2']: api('admin.adminRemove', T, id=u)

# ---- 관리자 추가 ----
ok('최고 관리자 세션 표시', own.get('admin') is True)
ok('일반 회원은 관리자 추가 못 함', code(api('admin.adminAdd', s1['token'], id='adm_p1')) in ('forbidden', 'unauthenticated'))
ok('학생(만 19세 미만)은 관리자 불가', code(api('admin.adminAdd', T, id='adm_s1')) == 'adult_only')
ok('없는 아이디는 관리자 불가', code(api('admin.adminAdd', T, id='nobody_x')) == 'no_user')
ok('성인 회원 관리자로 추가', api('admin.adminAdd', T, id='adm_p1').get('result', {}).get('ok') is True)
pa = api('auth.login', id='adm_p1', pw=PW)['result']['session']; PA = pa['token']
ok('추가된 관리자 로그인 → 관리자 세션', pa.get('admin') is True and not pa.get('owner'))
me = api('auth.me', PA)['result']
ok('auth.me: 관리자·유료, 최고 관리자 아님', me.get('admin') is True and me.get('paid') is True and me.get('owner') is False, me)
ok('추가 관리자는 회원 진도를 읽음', 'result' in api('db.get', PA, path='progress/adm_s1'))
ok('추가 관리자는 관리자 추가 못 함', code(api('admin.adminAdd', PA, id='adm_p2')) == 'forbidden')
ok('추가 관리자는 최고 관리자 삭제 못 함', code(api('admin.deleteMember', PA, id='kotang77')) == 'forbidden')
ok('추가 관리자는 최고 관리자 비밀번호 못 바꿈', code(api('admin.setPassword', PA, id='kotang77', pw='zzzzzzzz1')) == 'forbidden')
L = api('admin.admins', PA)['result']['admins']
ok('관리자 목록(최고 관리자 + 추가 관리자)', [x['id'] for x in L][:1] == ['kotang77'] and any(x['id'] == 'adm_p1' for x in L), L)
ok('일반 회원은 관리자 목록 못 봄', code(api('admin.admins', s1['token'])) == 'forbidden')

# ---- 시험 재시험·리셋 ----
S1 = s1['token']
api('db.set', S1, path='evals/adm_s1_b0', data={'title': '순례주택', 'g': '중1', 'm': '3월', 'total': 81, 'uid': 'adm_s1'})
api('db.set', S1, path='evals/adm_s1_b0_r2', data={'title': '순례주택', 'g': '중1', 'm': '3월', 'total': 88, 'round': 2})
api('db.set', S1, path='essays/hx1_adm_s1', data={'hid': 'hx1', 'book': '순례주택', 'uid': 'adm_s1', 'g': '중1', 'm': '3월', 'text': '글'})
api('db.set', S1, path='orals/adm_s1_b0_a', data={'ans': [{'text': '답'}]})
api('db.set', S1, path='orauds/adm_s1_b0_0_1', data={'uid': 'adm_s1', 'b64': 'AAAA'})
api('db.set', S1, path='orauds/adm_s1_b10_0_1', data={'uid': 'adm_s1', 'b64': 'BBBB'})
api('db.set', S1, path='progress/adm_s1', data={'done': {'b0:book': 1, 'b0:m1': 1, 'b0:m2': 1}, 'evDone': {'b0': 1, 'b1': 1}, 'orDone': {'b0': 1},
    'evalLog': [{'key': 'b0', 'title': '순례주택', 'm': '중1 3월', 'total': 81}, {'key': 'b1', 'title': '누가 내 치즈를 옮겼을까?', 'm': '중1 4월', 'total': 70}],
    'oralLog': [{'key': 'b0', 'title': '순례주택', 'm': '중1 3월', 't1': 66, 't2': 74, 'total': 74}], 'errs': [{'k': 'b0', 'id': 'e1'}, {'k': 'b1', 'id': 'e2'}], 'oqs': {'b0': {'shown': ['q']}}})
api('db.set', s2['token'], path='progress/adm_s2', data={'done': {'b12:book': 1}, 'evDone': {'b12': 1}, 'evalLog': [{'key': 'b12', 'title': '책', 'm': '중2 3월', 'total': 92}]})
ok('일반 회원은 시험 리셋 못 함', code(api('admin.resetTest', S1, id='adm_s1', key='b0', what='both', keep=True)) == 'forbidden')
ok('잘못된 키 거절', code(api('admin.resetTest', T, id='adm_s1', key='x0', what='both')) == 'bad_request')
r = api('admin.resetTest', PA, id='adm_s1', key='b0', what='both', keep=True)['result']
ok('추가 관리자가 재시험 부여(논술+구술)', r.get('done') == ['essay', 'oral'] and r.get('keep') is True, r)
g = lambda path, t=T: api('db.get', t, path=path).get('result')
ok('논술 1·2차 평가 삭제', g('evals/adm_s1_b0') is None and g('evals/adm_s1_b0_r2') is None)
ok('공개 논술 글 삭제', g('essays/hx1_adm_s1') is None)
ok('구술 답변·그 달 녹음 삭제, 다른 달 녹음은 남음', g('orals/adm_s1_b0_a') is None and g('orauds/adm_s1_b0_0_1') is None and g('orauds/adm_s1_b10_0_1') is not None)
P = g('progress/adm_s1')['data']
ok('진도: 그 달 완료 표시·기록만 빠짐', 'b0' not in P['evDone'] and P['evDone'].get('b1') == 1 and 'b0' not in P['orDone'] and [x['key'] for x in P['evalLog']] == ['b1'] and P['oralLog'] == [] and [e['k'] for e in P['errs']] == ['b1'] and 'b0' not in P.get('oqs', {}), P)
ok('진도: 책·영화 완료는 그대로, rv=1', P['done'].get('b0:book') == 1 and P.get('rv') == 1)
arch = api('db.query', S1, collection='archive', query={'where': [['uid', '==', 'adm_s1']]})['result']
ok('보관함: 논술·구술 두 건, 본인이 읽음', sorted(x['data']['kind'] for x in arch) == ['essay', 'oral'] and any(x['data'].get('total') == 88 for x in arch), [x['data'].get('total') for x in arch])
ok('보관함: 다른 회원은 못 읽음', not api('db.query', s2['token'], collection='archive', query={'where': [['uid', '==', 'adm_s1']]}).get('result'))
ok('보관함: 회원이 직접 못 씀', code(api('db.set', S1, path='archive/adm_s1_b0_x_1', data={'uid': 'adm_s1'})) == 'permission_denied')
old = dict(P); old.pop('rv', None); old['evDone'] = {'b0': 1, 'b1': 1}
ok('예전 화면(rv 없음)의 진도 덮어쓰기 거절', code(api('db.set', S1, path='progress/adm_s1', data=old)) == 'stale_progress')
P['rv'] = 1; P['notes'] = {'b1': {'sentence': '새로 씀'}}
ok('새 화면(rv=1)은 저장됨', 'result' in api('db.set', S1, path='progress/adm_s1', data=P))
api('db.set', S1, path='evals/adm_s1_b1', data={'title': '누가 내 치즈를 옮겼을까?', 'total': 70})
r = api('admin.resetTest', T, id='adm_s1', key='b1', what='essay', keep=False)['result']
ok('리셋(보관 안 함) 논술만', r.get('done') == ['essay'] and g('evals/adm_s1_b1') is None and len(api('db.query', T, collection='archive', query={'where': [['uid', '==', 'adm_s1']]})['result']) == 2)
ok('기록 없는 달은 아무것도 안 함', api('admin.resetTest', T, id='adm_s1', key='b5', what='oral', keep=True)['result'].get('done') == [])
api('db.set', S1, path='evals/adm_s1_b0', data={'title': '순례주택', 'g': '중1', 'm': '3월', 'total': 77})
P = g('progress/adm_s1')['data']; P['evDone'] = {'b0': 1}; P['evalLog'] = [{'key': 'b0', 'title': '순례주택', 'm': '중1 3월', 'total': 77}]
api('db.set', S1, path='progress/adm_s1', data=P)

# ---- 평가 기준 설정 ----
ok('일반 회원은 평가 기준 못 바꿈', code(api('db.set', S1, path='config/rubric', data={'essay': []})) == 'permission_denied')
api('db.delete', T, path='config/rubric')

# ---- 앱 ----
def wait(f, n=60):
    for _ in range(n):
        try:
            if f(): return True
        except Exception: pass
        time.sleep(.25)
    return False
def act(pg, sel): pg.evaluate("s=>{const e=document.querySelector(s);if(!e)throw new Error('없음 '+s);e.click()}", sel)
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', args=['--no-sandbox'])
    for vp in [('mobile', {'width': 390, 'height': 844}), ('desktop', {'width': 1280, 'height': 900})]:
        ctx = b.new_context(viewport=vp[1], device_scale_factor=2, locale='ko-KR'); pg = ctx.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        sess = api('auth.login', id='kotang77', pw=PW)['result']['session']
        pg.goto(WEB); pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))", sess); pg.goto(WEB)
        pg.wait_for_selector('[data-act=view][data-v=admin]', timeout=20000, state='attached')
        act(pg, '[data-act=view][data-v=admin]')
        ok(f'[{vp[0]}] 지표 타일 6개', wait(lambda: pg.locator('.ad-tile').count() == 6))
        ok(f'[{vp[0]}] 메뉴 7개, 처음엔 모두 닫힘', pg.locator('.ad-sec').count() == 7 and pg.locator('.ad-sec.open').count() == 0)
        ok(f'[{vp[0]}] 최근 가입·분포', '최근 가입' in pg.inner_text('.ad') and '학년' in pg.inner_text('.ad-two'))
        pg.screenshot(path=OUT + vp[0] + '_dash.png', full_page=True)
        if vp[0] == 'desktop': ctx.close(); continue
        act(pg, '[data-act=admsec][data-v=members]')
        ok('회원 관리 펼침', wait(lambda: pg.locator('.ad-sec.open #adm-q').count() == 1))
        names = lambda: [x.split('\n')[0] for x in pg.locator('.ad-mh .ad-mt b').all_inner_texts()]
        act(pg, '[data-act=admf][data-k=kind][data-v=parent]')
        ok('필터: 부모·선생님', wait(lambda: '엄마쌤' not in names() and '아빠쌤' in names() and '하늘' not in names()), names())
        act(pg, '[data-act=admf][data-k=kind][data-v=admin]')
        ok('필터: 관리자', wait(lambda: set(names()) >= {'엄마쌤'} and '하늘' not in names()), names())
        act(pg, '[data-act=admf][data-k=kind][data-v=student]'); act(pg, '[data-act=admf][data-k=gender][data-v=남자]')
        ok('필터: 학생 + 남자', wait(lambda: '바다' in names() and '하늘' not in names()), names())
        act(pg, '[data-act=admf][data-k=gender][data-v=all]'); act(pg, '[data-act=admf][data-k=grade][data-v=중1]')
        ok('필터: 중1', wait(lambda: '하늘' in names() and '바다' not in names()), names())
        act(pg, '[data-act=admf][data-k=grade][data-v=all]')
        pg.select_option('#adm-sort', 'esHi')
        ok('정렬: 논술 점수 높은순', wait(lambda: names().index('바다') < names().index('하늘')), names())
        pg.select_option('#adm-sort', 'esLo')
        ok('정렬: 논술 점수 낮은순', wait(lambda: names().index('하늘') < names().index('바다')), names())
        pg.fill('#adm-q', 'adm_s2')
        ok('검색', wait(lambda: names() == ['바다']), names())
        pg.fill('#adm-q', ''); pg.dispatch_event('#adm-q', 'input')
        act(pg, '[data-act=admopen][data-id=adm_s1]')
        ok('회원 상세 펼침(정보 탭)', wait(lambda: 'adm_s1@ex.com' in pg.inner_text('.ad-m.open')))
        act(pg, '[data-act=admmtab][data-v=study]')
        ok('학습·성적 탭', wait(lambda: '순례주택' in pg.inner_text('.ad-m.open') and '77점' in pg.inner_text('.ad-m.open')))
        act(pg, '[data-act=admmtab][data-v=test]')
        ok('시험 다시 열기 탭: 마친 달 목록', wait(lambda: pg.locator('[data-act=admtest][data-k=b0][data-v=keep]').count() == 1))
        act(pg, '[data-act=admrt][data-v=essay]')
        act(pg, '[data-act=admtest][data-k=b0][data-v=keep]')
        ok('한 번 누르면 확인 문구', wait(lambda: '한 번 더' in pg.inner_text('[data-act=admtest][data-k=b0][data-v=keep]')))
        pg.screenshot(path=OUT + 'member_test.png', full_page=True)
        act(pg, '[data-act=admtest][data-k=b0][data-v=keep]')
        ok('재시험 주기 실행 → 진도에서 빠짐', wait(lambda: 'b0' not in (g('progress/adm_s1')['data'].get('evDone') or {})))
        ok('재시험 알림이 회원에게 감', wait(lambda: any(x.get('to') == 'adm_s1' and '재시험' in x.get('title', '') for x in (g('config/notices') or {}).get('data', {}).get('items', []))))
        act(pg, '[data-act=admarch][data-id=adm_s1]')
        ok('보관된 이전 시험 불러오기', wait(lambda: '보관된 이전 시험' in pg.inner_text('.ad-m.open') and pg.locator('.ad-arch li').count() >= 3))
        # 평가 기준
        act(pg, '[data-act=admsec][data-v=rubric]')
        ok('메뉴는 한 번에 하나만 펼쳐짐', wait(lambda: pg.locator('.ad-sec.open').count() == 1 and pg.locator('#ads-rubric.open').count() == 1))
        act(pg, '[data-act=admsub][data-v=essay]')
        ok('논술 기준 편집 양식', wait(lambda: pg.locator('form[data-form=rubric][data-kind=essay] input[name=w0]').count() == 1) and pg.input_value('input[name=w1]') == '30')
        pg.fill('input[name=w1]', '29'); pg.dispatch_event('input[name=w1]', 'input')
        ok('합계 표시가 바로 바뀜', pg.inner_text('#rbsum-essay b') == '99')
        act(pg, 'form[data-form=rubric][data-kind=essay] button[type=submit]')
        ok('합계 100이 아니면 저장 안 됨', wait(lambda: '100' in pg.inner_text('#rberr-essay')))
        pg.fill('input[name=w0]', '21'); pg.fill('input[name=k5]', '생각의 깊이와 넓이')
        act(pg, 'form[data-form=rubric][data-kind=essay] button[type=submit]')
        ok('논술 기준 저장', wait(lambda: (g('config/rubric') or {}).get('data', {}).get('essay', [{}])[0].get('w') == 21))
        cfg = g('config/rubric')['data']
        ok('저장 내용: 이름·배점·설명', cfg['essay'][5]['k'] == '생각의 깊이와 넓이' and cfg['essay'][1]['w'] == 29 and len(cfg['essay'][0]['l']) > 20 and cfg['by'] == 'kotang77', cfg['essay'][5])
        ok('구술 기준은 그대로', [x['w'] for x in cfg['oral']] == [20, 30, 15, 10, 15, 10] and [x.get('h') for x in cfg['oral']][3:5] == [True, True])
        pg.screenshot(path=OUT + 'rubric.png', full_page=True)
        act(pg, '[data-act=admrbdef][data-v=essay]'); act(pg, 'form[data-form=rubric][data-kind=essay] button[type=submit]')
        ok('처음 기준으로 되돌려 저장', wait(lambda: g('config/rubric')['data']['essay'][0]['w'] == 20 and g('config/rubric')['data']['essay'][5]['k'] == '생각의 깊이'))
        # 코스
        act(pg, '[data-act=admsec][data-v=course]'); act(pg, '[data-act=admsub][data-v=month]')
        ok('월별 코스 목록(중1 12개월)', wait(lambda: pg.locator('.ad-cl li').count() == 12))
        act(pg, '[data-act=admced][data-v="0"]')
        ok('달 편집 양식', wait(lambda: pg.locator('form[data-form=admcourse] input[name=m1]').count() == 1))
        old_m1 = pg.input_value('form[data-form=admcourse] input[name=m1]')
        pg.fill('form[data-form=admcourse] input[name=m1]', '원더')
        pg.screenshot(path=OUT + 'course.png', full_page=True)
        act(pg, 'form[data-form=admcourse] button[type=submit]')
        ok('영화 바꿔 저장 → 계획표 반영', wait(lambda: (g('config/course') or {}).get('data', {}).get('items', [{}])[0].get('m1') == '원더'))
        it0 = g('config/course')['data']['items'][0]
        ok('바뀐 영화의 예전 정보는 지움, 나머지 유지', 'm1Info' not in it0 and 'm2Info' in it0 and it0['book'] == '순례주택' and len(g('config/course')['data']['items']) == 36 and g('config/course')['data'].get('via') == 'edit')
        api('db.delete', T, path='config/course')
        # 관리자
        act(pg, '[data-act=admsec][data-v=admins]')
        ok('관리자 목록', wait(lambda: '엄마쌤' in pg.inner_text('#ads-admins') and '최고 관리자' in pg.inner_text('#ads-admins')))
        pg.fill('form[data-form=admadd] input[name=id]', 'adm_s2'); act(pg, 'form[data-form=admadd] button[type=submit]')
        ok('학생은 추가 안 됨(안내)', wait(lambda: '19세' in pg.inner_text('#aderr')))
        pg.fill('form[data-form=admadd] input[name=id]', 'adm_p2'); act(pg, 'form[data-form=admadd] button[type=submit]')
        ok('성인 회원 관리자로 추가', wait(lambda: '아빠쌤' in pg.inner_text('#ads-admins')))
        pg.screenshot(path=OUT + 'admins.png', full_page=True)
        act(pg, '[data-act=admrm][data-id=adm_p2]'); act(pg, '[data-act=admrm][data-id=adm_p2]')
        ok('관리자 해제', wait(lambda: '아빠쌤' not in pg.inner_text('#ads-admins')))
        ok('페이지 오류 없음', not errs, errs)
        ctx.close()
    # 추가 관리자 화면
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, locale='ko-KR'); pg = ctx.new_page()
    sess = api('auth.login', id='adm_p1', pw=PW)['result']['session']
    pg.goto(WEB); pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))", sess); pg.goto(WEB)
    ok('추가 관리자에게 관리 메뉴 보임', wait(lambda: pg.locator('[data-act=view][data-v=admin]').count() > 0))
    act(pg, '[data-act=view][data-v=admin]'); wait(lambda: pg.locator('.ad-tile').count() == 6)
    act(pg, '[data-act=admsec][data-v=admins]')
    ok('추가 관리자: 관리자 추가 양식 없음', wait(lambda: '최고 관리자만' in pg.inner_text('#ads-admins')) and pg.locator('form[data-form=admadd]').count() == 0)
    ctx.close(); b.close()
api('admin.adminRemove', T, id='adm_p1')
ok('해제 뒤 관리자 권한 사라짐', code(api('admin.admins', PA)) == 'forbidden')
print(f'{sum(res)}/{len(res)}')
raise SystemExit(0 if all(res) else 1)
