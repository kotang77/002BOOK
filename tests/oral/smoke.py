# 화면·그림·논술 첨삭 PDF 연기 시험 (가짜 서버). run.sh가 함께 실행한다.
# 로그인 화면 로고, 캐릭터 고르기 그림, 논술 첨삭 평가서 PDF, 휴대폰·PC 화면, 페이지 오류를 확인한다.
import json, os, subprocess, sys, time, urllib.request
from playwright.sync_api import sync_playwright
API = 'http://localhost:8000'; WEB = 'http://localhost:8080'
OUT = os.environ.get('OUT', '/tmp/oraltest/') + 'smoke/'; os.makedirs(OUT, exist_ok=True)
LIBDIR = os.environ.get('PDFLIB', '/home/claude/fonts/node_modules')
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
s = mk('smoke01'); tok = s['token']
sv = {k: {'fun': 4, 'diff': 3, 'again': 4} for k in ['b0:book', 'b0:m1', 'b0:m2']}
api('db.set', tok, path='progress/smoke01', data={'done': {k: 1 for k in sv}, 'survey': sv, 'notes': {}, 'qs': {}, 'evalLog': [], 'drafts': {}, 'picks': {}})
T = '저는 순례주택의 주인공이 어른스러운 선택을 했다고 생각합니다.\n왜냐하면 가족을 먼저 생각했기 때문입니다. 그리고 이웃과 함께 사는 법을 배웠습니다.\n그래서 저도 이웃을 돕는 사람이 되고 싶습니다.'
W = {'plus': ['좋아요'], 'minus': ['더 구체적으로']}
EV = {'offTopic': False, 'praise': '주장이 분명해요.', 'progress': '', 'transcript': T, 'unreadable': [],
      'scores': {'논지': 86, '근거': 80, '구성': 82, '표현': 84, '맞춤법': 90, '적극성': 88}, 'scoreWhy': {k: W for k in ['논지', '근거', '구성', '표현', '맞춤법', '적극성']},
      'comment': '전체적으로 잘 썼어요.', 'spelling': [{'orig': '어른스러운', 'fix': '어른스러운', 'why': '맞아요'}],
      'sentences': [{'orig': '그래서 저도 이웃을 돕는 사람이 되고 싶습니다.', 'grade': '고침', 'why': '구체적 행동이 없어요', 'fix': '그래서 저도 매주 이웃 어르신을 돕겠습니다.'}],
      'paragraphs': '세 문단', 'paraReview': [{'no': 1, 'role': '주장', 'good': '분명', 'problem': '', 'rewrite': ''}],
      'strengths': ['주장 분명'], 'improvements': ['근거 보강'], 'tags': ['근거 부족'], 'cumulative': '첫 첨삭이에요.',
      'marks': [{'find': '왜냐하면', 'kind': 'good', 'fix': '', 'note': '이유 제시 좋아요'}, {'find': '그리고', 'kind': 'replace', 'fix': '또', 'note': '접속어 다양하게'}],
      'teacher': '잘했어요.', 'models': [{'title': '모범 답안 1', 'text': '모범 답안 내용입니다.'}, {'title': '모범 답안 2', 'text': '두 번째 모범 답안입니다.'}],
      'total': 85, 'question': '주인공의 선택을 평가해 보세요.', 'at': int(time.time() * 1000), 'title': '순례주택', 'g': '중1', 'm': '3월', 'kw': '가족'}
from PIL import Image; Image.new('RGB', (900, 600), (200, 120, 60)).save(OUT + 'photo.png')
r = api('db.set', tok, path='evals/smoke01_b0', data=EV); ok('첨삭 기록 준비', 'result' in r, r)
LIB = lambda rt: rt.fulfill(path=(LIBDIR + '/html2canvas/dist/html2canvas.min.js' if 'html2canvas' in rt.request.url else LIBDIR + '/jspdf/dist/jspdf.umd.min.js' if 'jspdf' in rt.request.url else '/dev/null'), content_type='application/javascript')
BROKEN = "[...document.images].filter(i=>i.complete&&i.src&&!i.src.startsWith('data:image/svg')&&i.naturalWidth===0).map(i=>i.src.slice(0,80))"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    for mode, vp in [('mobile', {'width': 390, 'height': 844}), ('desktop', {'width': 1280, 'height': 860})]:
        ctx = b.new_context(viewport=vp, device_scale_factor=1, locale='ko-KR', accept_downloads=True, service_workers='block')
        pg = ctx.new_page(); pg.route('**/cdnjs.cloudflare.com/**', LIB)
        pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
        pg.goto(WEB + '/'); pg.wait_for_selector('.biglogo', timeout=20000); time.sleep(1.2)
        ok(f'{mode}: 로그인 화면 로고', pg.evaluate("document.querySelector('.biglogo').naturalWidth") > 100)
        pg.screenshot(path=OUT + f'{mode}_0_login.png')
        pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))", s); pg.goto(WEB + '/'); pg.wait_for_selector('.who', timeout=20000); time.sleep(1.5)
        ok(f'{mode}: 학습 화면 그림 모두 열림', not pg.evaluate(BROKEN), pg.evaluate(BROKEN))
        pg.screenshot(path=OUT + f'{mode}_1_course.png')
        pg.evaluate("document.querySelector('[data-act=avatar]').click()"); time.sleep(1.2)
        n = pg.evaluate("[...document.querySelectorAll('.avo img')].filter(i=>i.naturalWidth>0).length")
        ok(f'{mode}: 캐릭터 그림 19개 열림', n >= 19, n); pg.screenshot(path=OUT + f'{mode}_2_avatar.png')
        if mode == 'mobile':
            pg.set_input_files('input[data-avatar]', OUT + 'photo.png'); time.sleep(2)
            d = api('db.get', tok, path='members/smoke01')['result']['data']
            ok('내 사진 올리기 (정사각 JPEG 40KB 이하)', d.get('avatar') == 'custom' and d.get('avatarImg', '').startswith('data:image/jpeg') and len(d['avatarImg']) <= 40000, (d.get('avatar'), len(d.get('avatarImg', ''))))
        pg.evaluate("document.querySelector('[data-act=close1]').click()"); time.sleep(.5)
        if mode == 'mobile':
            pg.evaluate("document.querySelector('[data-act=profile]').click()"); pg.wait_for_selector('input[data-budup]', state='attached', timeout=10000)
            pg.set_input_files('input[data-budup]', OUT + 'photo.png')
            for _ in range(30):
                if '그림을 넣었어요' in pg.inner_text('#toast'): break
                time.sleep(.2)
            ok('가상 친구 그림 올리기', '그림을 넣었어요' in pg.inner_text('#toast'), pg.inner_text('#toast'))
            pg.evaluate("document.querySelector('[data-act=close1]').click()"); time.sleep(.5)
            def click(sel, wait=.8):
                pg.wait_for_selector(sel, state='attached', timeout=15000); pg.evaluate("s=>document.querySelector(s).click()", sel); time.sleep(wait)
            click('[data-act=month][data-i="0"]'); click('[data-act=stab][data-v=essay]', 1.5); click('[data-act=vieweval]', .2); pg.wait_for_selector('[data-act=pdf]', timeout=15000); time.sleep(.8)
            pg.screenshot(path=OUT + 'mobile_3_eval.png')
            with pg.expect_download(timeout=90000) as dl: pg.evaluate("document.querySelector('[data-act=pdf]').click()")
            f = dl.value; f.save_as(OUT + 'essay.pdf'); ok('논술 첨삭 PDF 저장', True, f.suggested_filename)
            info = subprocess.run(['pdfinfo', OUT + 'essay.pdf'], capture_output=True, text=True).stdout
            pages = int([l for l in info.split('\n') if l.startswith('Pages:')][0].split()[1])
            ok('PDF 쪽 수', pages >= 2, pages)
            txt = f.suggested_filename
            ok('PDF 파일 이름 규칙', txt.endswith('.pdf') and ' 중1 가족 smoke01' in txt, txt)
            subprocess.run(['pdftoppm', '-r', '50', '-png', OUT + 'essay.pdf', OUT + 'essay'])
        ctx.close()
    b.close()
ok('페이지 오류 없음', not [e for e in errs if 'fonts.g' not in e], errs[:5])
print('%d/%d' % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
