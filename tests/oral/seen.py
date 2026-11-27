# 책 1권 + 영화 1편만 끝냈을 때: 글쓰기·말하기 질문은 끝낸 작품으로만(안 본 영화 제외),
# 1단계 화면 아래 '책 읽기 전 생각하기'(예전 교육자료 칩 대신, 줄거리·결말 없이), 논술 첨삭의 '작품 깊이 읽기'
import json, os, sys, time, urllib.request
from playwright.sync_api import sync_playwright
API = 'http://localhost:8000'; WEB = 'http://localhost:8080'; res = []; errs = []
def ok(n, c, x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ') + n + ('' if c else f' — {x}'))
def api(op, tok=None, **kw):
    h = {'content-type': 'application/json'}
    if tok: h['x-session'] = tok
    r = urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST')
    try: return json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())
U = 'seen01'; PW = 'testpass1234'
r = api('auth.login', id=U, pw=PW)
if 'result' in r: api('auth.withdraw', r['result']['session']['token'], pw=PW)
s = api('auth.signup', id=U, pw=PW, email=U + '@ex.com', agreeTerms=True, agreePrivacy=True, birth='2010-01', grade='중1', nick=U, gender='여')['result']['session']
sv = {k: {'fun': 4, 'diff': 3, 'again': 4} for k in ['b0:book', 'b0:m1']}
api('db.set', s['token'], path='progress/' + U, data={'done': {k: 1 for k in sv}, 'survey': sv, 'notes': {}, 'qs': {}, 'evalLog': [], 'drafts': {}, 'picks': {}})
TTS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flow.py'), encoding='utf-8').read().split("TTS='''")[1].split("'''")[0]
STUB = r"""
window.__calls=[];
S.sample.json=async(p,o)=>{window.__calls.push(p);const it=items()[0];
  if(p.includes('책 읽기 전 생각하기'))return {theme:'가족은 서로를 돌보는 사이예요. 이달에는 가족이 무엇인지 생각해요.',why:'책과 영화는 같은 주제를 다른 방법으로 보여 줘요.',before:['내가 가족에게 고마웠던 때는?','가족과 다퉜던 때는?','가족이란 무엇일까?'],look:[{k:'책',t:'인물이 집을 어떻게 생각하는지 보세요.'},{k:'영화 ①',t:'아버지의 표정을 보세요.'},{k:'영화 ②',t:'식탁 장면을 보세요.'}],link:'책과 영화에서 가족을 지키는 방법은 어떻게 다를까요?'};
  if(p.includes('구술 질문'))return [0,1,2].map(n=>({q:'가족의 의미 질문 '+(n+1)+'번은 무엇인가요?',from:['책'],tip:'경험을 들어요'}));
  if(p.includes('후보 주제어'))return {works:[{id:'책',summary:'가족의 의미를 묻는 책.',entities:['가나다']},{id:'영화 ①',summary:'가족을 지키는 아버지 이야기.',entities:['라마바']}],themes:['가족의 의미','어른의 책임']};
  if(p.includes('정확히 3개를 출제')&&p.includes('논술'))return [0,1,2].map(n=>({q:'「'+PX.tt(it.book)+'」과 「'+PX.tt(it.m1)+'」에서 가족의 의미를 '+['비교','평가','적용'][n]+'하여 논하시오. (600자 내외)',from:['책','영화 ①','영화 ②']}));
  return {}};0
"""
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, locale='ko-KR', service_workers='block'); ctx.add_init_script(TTS); ctx.add_init_script('window.__002TEST=o=>{Object.assign(window,o)}'); pg = ctx.new_page()
    pg.route('**/cdnjs.cloudflare.com/**', lambda rt: rt.fulfill(body='', content_type='application/javascript'))
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.goto(WEB + '/'); pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))", s); pg.goto(WEB + '/'); pg.wait_for_selector('.who', timeout=20000); time.sleep(1)
    J = lambda x, *a: pg.evaluate(x, *a)
    J(STUB)
    M2 = J("PX.tt(items()[0].m2)"); M1 = J("PX.tt(items()[0].m1)")
    # ── 1단계 화면: 아래 버튼 = 책 읽기 전 생각하기 (아직 시작 안 한 달)
    J("document.querySelector('[data-act=month][data-i=\"1\"]').click()"); time.sleep(.8)
    ok('교육자료 칩 없음', J("!document.querySelector('#layer1 .mmore')"))
    ok('아래 버튼 = 책 읽기 전 생각하기', J("(document.querySelector('#mact .mact-b')||{}).textContent") == '책 읽기 전 생각하기', J("(document.querySelector('#mact')||{}).outerHTML"))
    ok('아래 큰 「…」 읽기 시작 버튼 없음', J("!document.querySelector('#mact [data-act=start]')"))
    J("document.querySelector('#mact .mact-b').click()"); time.sleep(1.5)
    txt = J("(document.querySelector('#layer1 .edu.pre')||{}).innerText||''")
    ok('책 읽기 전 생각하기 화면', '책 읽기 전 생각하기' in txt and '이달의 주제' in txt and '읽기 전에 나에게 물어봐요' in txt and '책과 영화를 이어 생각하기' in txt, txt[:300])
    pp = J("window.__calls.find(c=>c.includes('책 읽기 전 생각하기'))||''")
    ok('지시문: 줄거리·결말 금지(저장본이 있으면 생략)', (not pp) or ('결말' in pp and '줄거리 요약' in pp), pp[:200])
    ok('돌아가기 버튼', J("(document.querySelector('#mact .mact-b')||{}).textContent") == '1단계 · 읽고 보기로 가기')
    J("document.querySelector('#layer1 .ph .x').click()"); time.sleep(.6)
    # ── 책 + 영화 ①만 끝낸 달: 논술 질문은 두 작품으로만
    J("window.__calls=[]")
    J("document.querySelector('[data-act=month][data-i=\"0\"]').click()"); time.sleep(.8)
    J("document.querySelector('.msteps [data-act=stab][data-v=essay]').click()")
    ok('논술 질문 생성', J("()=>new Promise(r=>{let n=0;const t=setInterval(()=>{const q=S.progress.qs[nk(0)];if((q&&q.ai)||++n>80){clearInterval(t);r(!!(q&&q.ai))}},150)})"))
    gen = J("window.__calls.filter(c=>c.includes('정확히 3개를 출제'))")
    ok('질문 지시문에 안 본 영화 없음', gen and all(M2 not in c for c in gen) and all(M1 in c for c in gen), [c[:200] for c in gen])
    meta = J("window.__calls.find(c=>c.includes('후보 주제어'))||''")
    ok('공통 주제(2차 특허) 두 작품으로', meta and M2 not in meta and '두 작품' in meta, meta[:200])
    q = J("S.progress.qs[nk(0)]")
    ok('질문 표시 = 책+영화 ①', q.get('sig') == '책+영화 ①' and all(set(t) <= {'책', '영화 ①'} for t in q.get('tags', [])), q)
    ok('안 본 영화 안내 문구 없음', J("!document.querySelector('#layer1 .qseen')"))
    # ── 말하기도 열리고 두 작품으로만
    J("document.querySelector('.msteps [data-act=stab][data-v=oral]').click()")
    ok('말하기 열림(책+영화 1편)', J("()=>new Promise(r=>{let n=0;const t=setInterval(()=>{const q=(S.progress.oqs||{})[nk(0)];if((q&&q.shown&&q.shown.length>=3)||++n>80){clearInterval(t);r(!!(q&&q.shown&&q.shown.length>=3))}},150)})"))
    oq = J("window.__calls.filter(c=>c.includes('구술 질문'))")
    ok('구술 지시문에 안 본 영화 없음', oq and all(M2 not in c for c in oq), [c[:200] for c in oq])
    # ── 나머지 영화도 보면(아직 질문을 고르지 않았으면) 세 작품으로 다시
    J("()=>{S.progress.done['b0:m2']=1;S.progress.survey['b0:m2']={fun:4,diff:3,again:4};window.__calls=[]}")
    J("document.querySelector('.msteps [data-act=stab][data-v=essay]').click()")
    ok('세 작품으로 다시 만듦', J("()=>new Promise(r=>{let n=0;const t=setInterval(()=>{const q=S.progress.qs[nk(0)];if((q&&q.sig==='책+영화 ①+영화 ②')||++n>80){clearInterval(t);r(!!(q&&q.sig==='책+영화 ①+영화 ②'))}},150)})"))
    gen = J("window.__calls.filter(c=>c.includes('정확히 3개를 출제'))")
    ok('이번엔 두 영화 모두', gen and M2 in gen[0] and M1 in gen[0])
    ok('화면 오류 없음', not errs, errs)
    b.close()
api('auth.withdraw', api('auth.login', id=U, pw=PW)['result']['session']['token'], pw=PW)
print(f'{sum(res)}/{len(res)}'); sys.exit(0 if all(res) else 1)
