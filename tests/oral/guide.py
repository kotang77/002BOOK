import os
# 학습지도 시험 (가짜 서버): A4 두 장 자료, 평가 방식·근거 문헌, 관리자 전체 만들기, 계획표 변경 시 다시 만들기
import json, time, urllib.request, sys
from playwright.sync_api import sync_playwright
API = 'http://localhost:8000'; WEB = 'http://localhost:8080'; PW = 'testpass1234'; res = []
def ok(n, c, x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ') + n + ('' if c else f' — {x}'))
def api(op, tok=None, **kw):
    h = {'content-type': 'application/json'}
    if tok: h['x-session'] = tok
    r = urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST')
    try: return json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())
r = api('auth.login', id='kotang77', pw=PW)
if 'result' not in r: api('auth.signup', id='kotang77', pw=PW, email='kotang77@ex.com', agreeTerms=True, agreePrivacy=True, birth='1980-01', grade='아빠', nick='관리자', gender='남자'); r = api('auth.login', id='kotang77', pw=PW)
T = r['result']['session']['token']
for d in api('db.query', T, collection='guides').get('result', []): api('db.delete', T, path='guides/' + d['id'])
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../app/source.html'), encoding='utf-8').read()
DEF = json.loads(next(l for l in _src.split('\n') if l.startswith('const DEFAULT='))[len('const DEFAULT='):].rstrip().rstrip(';'))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome'); pg = b.new_page(viewport={'width': 390, 'height': 800}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(WEB + '/'); pg.wait_for_selector('#li-id'); pg.fill('#li-id', 'kotang77'); pg.fill('#li-pw', PW); pg.click('form[data-form=login] button[type=submit]')
    pg.wait_for_selector('.who', timeout=15000); time.sleep(1.5)
    pg.evaluate("document.querySelector('nav.nav [data-v=guide]').click()"); time.sleep(1)
    for _ in range(40):
        if pg.locator('#lgsheet .lgpage').count() == 2: break
        time.sleep(.5)
    ok('A4 두 장(두 쪽) 자료', pg.locator('#lgsheet .lgpage').count() == 2, pg.inner_text('main')[:200])
    t = pg.inner_text('.lgsh')
    ok('세 작품 요약·포인트·질문·낱말·주의', all(x in t for x in ['순례주택에 사는 사람들', '가족의 뜻', '우리 가족의 좋은 점', '순례', '전쟁 장면']), t[:300])
    ok('A4 두 장은 화면에서 숨김(인쇄·PDF용)', pg.locator('.lgprint').count() == 1 and not pg.locator('.lgprint').is_visible())
    act = lambda sel: pg.evaluate("s=>{const e=document.querySelector(s);if(!e)throw new Error('없음 '+s);e.click()}", sel)
    act('[data-act=lgqo][data-i="1"]'); time.sleep(.3)
    ok('질문 힌트 펼치기', pg.locator('.lgqh').count() == 1 and '구체적' in pg.inner_text('.lgqh'))
    act('[data-act=lgchk][data-i="0"]'); time.sleep(.3)
    ok('활동 체크 저장', pg.locator('.lgac.on').count() == 1)
    ok('학년·달 칩 줄 없음, 학년 표시', pg.locator('.lgsel').count() == 0 and pg.inner_text('.lggr b') == '1학년')
    ok('평가 방식 요약(지도안 아래)', pg.locator('.lgevr').count() == 3 and pg.evaluate("document.querySelector('.lgevsum').compareDocumentPosition(document.querySelector('.lghero'))&2")>0)
    act('[data-act=lgevopen]'); time.sleep(.4)
    ok('평가 방식 탭: 논술·구술·육각형', pg.locator('.lgtile').count() == 3 and '100' in pg.inner_text('.lgtiles'))
    ok('평가 배점은 지금 기준표', '20점' in pg.inner_text('.lgsh') and pg.locator('.lgrb').count() == 6)
    act('[data-act=lgev][data-v=hex]'); time.sleep(.3)
    ok('육각형 그림', pg.locator('svg.lghex text').count() == 6)
    act('[data-act=lgrefs]'); time.sleep(.3)
    links = pg.eval_on_selector_all('.lgref a', 'a=>a.map(x=>x.href)')
    ok('근거 연구: 국내 교수 논문 먼저·요약 카드·원문 링크', pg.locator('.lgref.kr').count() >= 4 and 'kci.go.kr' in links[0] and len(links) >= 5 and pg.locator('.lgref p').count() == pg.locator('.lgref').count(), links)
    act('[data-act=lgevopen]'); time.sleep(.3)
    m0 = pg.inner_text('.lgmon:not(.lggr) b'); act('[data-act=lgmstep][data-d="-1"]' if pg.locator('.lgmon:not(.lggr) [data-act=lgmstep][data-d="1"]').is_disabled() else '[data-act=lgmstep][data-d="1"]'); time.sleep(.5)
    ok('달 넘기기', pg.inner_text('.lgmon:not(.lggr) b') != m0, m0)
    ok('학년 알약 ‹ 1학년 ›, 처음엔 이전 꺼짐', pg.inner_text('.lggr b') == '1학년' and pg.locator('[data-act=lggstep][data-d="-1"]').is_disabled())
    act('[data-act=lggstep][data-d="1"]'); time.sleep(.6)
    ok('학년 바꾸기', pg.inner_text('.lggr b') == '2학년')
    act('[data-act=lggstep][data-d="1"]'); time.sleep(.6)
    ok('3학년에서 다음 꺼짐', pg.inner_text('.lggr b') == '3학년' and pg.locator('[data-act=lggstep][data-d="1"]').is_disabled())
    act('[data-act=lggstep][data-d="-1"]'); time.sleep(.6); act('[data-act=lggstep][data-d="-1"]'); time.sleep(.6)
    ok('학년·달 알약 테두리만·같은 줄', pg.evaluate("(()=>{const m=[...document.querySelectorAll('.lgmon')];const c=e=>{const r=e.getBoundingClientRect();return r.top+r.height/2};return m.length==2&&Math.abs(c(m[0])-c(m[1]))<2&&getComputedStyle(m[0]).backgroundColor=='rgba(0, 0, 0, 0)'&&getComputedStyle(m[1]).backgroundColor=='rgba(0, 0, 0, 0)'})()") and pg.inner_text('.lggr b') == '1학년')
    pg.evaluate("document.querySelector('[data-act=lgall]').click()")
    def pref():
        ids = [d['id'] for d in api('db.query', T, collection='guides').get('result', [])]
        return {k: sum(1 for i in ids if i.startswith(k)) for k in ('lg2_', 'pre_', 'edu_', 'w2b_', 'w2m_')}
    for _ in range(400):
        if pg.evaluate("!!window.__lgLast"): break
        time.sleep(.5)
    c = pref(); nw = 36 * 3 - sum(1 for it in DEF for k in ('m1', 'm2') if not str(it.get(k) or '').strip())
    ok('관리자 일체 만들기 → 36개월 학습지도·읽기 전·깊이 읽기·작품별 안내서', c['lg2_'] == 36 and c['pre_'] == 36 and c['edu_'] == 36 and c['w2b_'] + c['w2m_'] == nw, (c, nw))
    n = sum(c.values())
    time.sleep(2)
    # 계획표 한 달 바꾸면 그 달 자료를 새로 만든다
    act('[data-act=view][data-v=admin]'); time.sleep(1); act('[data-act=admsec][data-v=course]'); time.sleep(.5); act('[data-act=admsub][data-v=month]'); time.sleep(.5)
    act('[data-act=admced][data-v="0"]'); time.sleep(.5)
    pg.fill('form[data-form=admcourse] input[name=m1]', '원더'); act('form[data-form=admcourse] button[type=submit]')
    for _ in range(60):
        n2 = sum(pref().values())
        if n2 >= n + 4: break
        time.sleep(.5)
    time.sleep(2); n2 = sum(pref().values())
    ok('책·영화가 바뀐 달은 자동으로 새 자료(학습지도·읽기 전·깊이 읽기·바뀐 영화 안내서)', n2 == n + 4, (n, n2))
    api('db.delete', T, path='config/course')
    ok('화면 오류 없음', not errs, errs)
    b.close()
for d in api('db.query', T, collection='guides').get('result', []): api('db.delete', T, path='guides/' + d['id'])
print(f'{sum(res)}/{len(res)}'); sys.exit(0 if all(res) else 1)
