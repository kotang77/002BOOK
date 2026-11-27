import re
# 논술 첨삭(누적 오류 프로파일)·논술 질문 생성(공통 주제) 시험. 가짜 서버 위에서 화면의 AI 호출만 가짜 응답으로 바꿔 흐름 전체를 돌린다
import json, os, sys, time, urllib.request
from playwright.sync_api import sync_playwright
API = 'http://localhost:8000'; WEB = 'http://localhost:8080'
res, errs = [], []
def ok(n, c, x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ') + n + (' — ' + str(x)[:300] if x != '' else ''))
def api(op, tok=None, **kw):
    h = {'content-type': 'application/json'}
    if tok: h['x-session'] = tok
    r = urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST')
    try: return json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())
U = 'essay01'
r = api('auth.login', id=U, pw='testpass1234')
if 'result' in r: api('auth.withdraw', r['result']['session']['token'], pw='testpass1234')
s = api('auth.signup', id=U, pw='testpass1234', email=U + '@ex.com', agreeTerms=True, agreePrivacy=True, birth='2010-01', grade='중1', nick=U, gender='여')['result']['session']
sv = {k: {'fun': 4, 'diff': 3, 'again': 4} for k in ['b0:book', 'b0:m1', 'b0:m2', 'b1:book', 'b1:m1', 'b1:m2']}
api('db.set', s['token'], path='progress/' + U, data={'done': {k: 1 for k in sv}, 'survey': sv, 'notes': {}, 'qs': {}, 'evalLog': [], 'drafts': {}, 'picks': {}})
def prog(): return api('db.get', s['token'], path='progress/' + U)['result']['data']
def wait(f, n=60):
    for _ in range(n):
        try:
            if f(): return True
        except Exception: pass
        time.sleep(.25)
    return False
TTS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flow.py'), encoding='utf-8').read().split("TTS='''")[1].split("'''")[0]
# 화면의 AI 호출을 가로채는 가짜 응답. window.__calls에 보낸 지시문을 모은다
STUB = r"""
window.__calls=[];window.__mode={};
const EV=(o)=>Object.assign({offTopic:false,praise:'잘했어요',progress:'좋아졌어요',unreadable:[],scores:{'작품 이해와 활용':4,'주장과 근거':3,'구성':3,'표현':4,'어문 규범':2,'생각의 깊이':3},process:{plan:'충실',note:'계획을 따랐어요'},scoreWhy:{},comment:'',paragraphs:'',paraReview:[],strengths:['a'],improvements:['띄어쓰기를 고쳐요'],tags:['띄어쓰기'],cumulative:'',marks:[],teacher:'좋아요',models:[]},o);
S.sample.json=async(p,o)=>{window.__calls.push(p);const it=items()[0];
  if(p.includes('후보 주제어'))return window.__mode.nometa?{x:1}:{works:[{id:'책',summary:'주인공이 가족과 부딪치며 스스로 서는 법을 배운다. 가족의 의미를 묻는다.',entities:['가나다라','마바사']},{id:'영화 ①',summary:'아버지가 가족을 지키려고 애쓴다. 가족의 의미와 희생을 보여 준다.',entities:['아자차카']},{id:'영화 ②',summary:'주인공이 가족과 함께하는 삶에서 가족의 의미를 깨닫는다.',entities:['타파하하']}],themes:['가족의 의미','어른의 책임']};
  if(p.includes('정확히 3개를 출제'))return [{q:'「'+PX.tt(it.book)+'」과 「'+PX.tt(it.m1)+'」에서 가족의 의미를 비교하고 논하시오. (800자 내외)',from:['책','영화 ①']},{q:'두 작품의 주인공이 공동체를 대하는 태도를 비교하고 논하시오. (800자 내외)',from:['책','영화 ②']},{q:'「'+PX.tt(it.book)+'」, 「'+PX.tt(it.m1)+'」, 「'+PX.tt(it.m2)+'」을 관통하는 가족의 의미를 논하시오. (1000자 내외)',from:['책','영화 ①','영화 ②']}];
  if(p.includes('근거가 약하다'))return [{n:2,q:'「'+PX.tt(it.book)+'」과 「'+PX.tt(it.m2)+'」의 주인공이 가족의 의미를 깨닫는 과정을 비교하고 논하시오. (800자 내외)'}];
  if(p.includes('검증에 실패'))return p.includes('"ok"')?[{id:(p.match(/id:(e\d+)/)||[])[1],ok:true}]:[...p.matchAll(/id:(e\d+)/g)].map(m=>({id:m[1],recur:true}));
  if(p.includes('20년 넘게')){
    if(p.includes('[1차 오류 해소 판정]')){const ids=[...p.matchAll(/id:(e\d+)/g)].map(m=>m[1]);return EV({transcript:window.__t2,spelling:[],sentences:[],fixed:ids.slice(0,-1).map(id=>({id,ok:true}))})}
    const base={transcript:window.__t1,spelling:[{orig:'됬다고',fix:'되었다고',why:''},{orig:'줄수있다',fix:'줄 수 있다',why:''}],sentences:[{orig:'그래서 가족은 중요하다 왜냐하면 가족이 없으면 힘들기 때문에 가족은 소중하다.',grade:'고침',type:'긴 문장',why:'',fix:'가족은 중요하다.'},{orig:'나는 어른이 됬다고 생각한다.',grade:'잘함',why:'',fix:''}]};
    if(p.includes('[지속 오류 확인]')){const ids=[...p.matchAll(/id:(e\d+)/g)].map(m=>m[1]);base.spelling=[{orig:'갈수있다',fix:'갈 수 있다',why:''}];base.sentences=[];base.recur=ids.slice(0,1).map(id=>({id,recur:false}))}
    return EV(base)}
  return {}};0
"""
T1 = '나는 어른이 됬다고 생각한다. 주인공은 가족을 도와 줄수있다. 그래서 가족은 중요하다 왜냐하면 가족이 없으면 힘들기 때문에 가족은 소중하다.'
PAD = ' 이 책을 읽고 나는 가족과 이웃이 서로를 지키는 마음이 얼마나 큰 힘이 되는지 다시 생각하게 되었다. 영화 속 아버지도 아들을 위해 끝까지 웃음을 잃지 않았다. 두 작품은 모두 가족이 함께 견디는 힘을 보여 준다. 나도 내 가족과 이웃을 먼저 돌보는 사람이 되고 싶다. 작은 실천이 쌓이면 공동체가 단단해진다고 믿는다. 물론 가족이 늘 옳은 것은 아니어서 서로 부딪칠 때도 있다. 그럴 때일수록 먼저 이야기를 듣고 마음을 헤아리는 태도가 필요하다. 그래서 나는 앞으로 일주일에 한 번 가족과 저녁을 먹으며 서로의 하루를 나누겠다.'
T1 += PAD
T2 = '나는 어른이 되었다고 생각한다. 주인공은 가족을 도와 줄수있다. 가족은 중요하다. 가족이 없으면 힘들기 때문이다.' + PAD
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, locale='ko-KR', service_workers='block'); ctx.add_init_script(TTS); ctx.add_init_script('window.__002TEST=o=>{Object.assign(window,o)}'); pg = ctx.new_page()
    pg.route('**/cdnjs.cloudflare.com/**', lambda rt: rt.fulfill(body='', content_type='application/javascript'))
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.goto(WEB + '/'); pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))", s); pg.goto(WEB + '/'); pg.wait_for_selector('.who', timeout=20000); time.sleep(1)
    J = lambda x, *a: pg.evaluate(x, *a)
    J(STUB); J("([a,b])=>{window.__t1=a;window.__t2=b}", [T1, T2])
    # 시험 고정: 1번 달은 '가족' 주제(순례주택), 2번 달은 '비전'(누가 내 치즈를…) — 계획표 순서가 바뀌어도 같은 조건으로 시험
    J("()=>{const c=S.course,a=c.findIndex(x=>/순례주택/.test(x.book)),b=c.findIndex(x=>/치즈/.test(x.book));const A=c[a],B=c[b];c.splice(0,0);const r=c.filter((x,i)=>i!==a&&i!==b);S.course=[Object.assign({},A,{g:'중1',m:'3월'}),Object.assign({},B,{g:'중1',m:'4월'})].concat(r);render()}")
    ok('계산부 탑재', J("typeof PX==='object'&&typeof PX.emb==='function'"))
    # ── 논술 질문 생성: 서술문·공통 주제·근거 점수·재생성
    J("document.querySelector('[data-act=month][data-i=\"0\"]').click()"); time.sleep(.8)
    J("document.querySelector('[data-act=stab][data-v=essay]').click()")
    ok('질문 3개 생성', wait(lambda: len(prog().get('qs', {}).get('b0', {}).get('shown', [])) == 3 and prog()['qs']['b0'].get('ai')), str(prog().get('qs', {}).get('b0'))[:200])
    q = prog()['qs']['b0']; calls = J("window.__calls")
    ok('작품 서술문·후보 주제어를 먼저 요청', any('후보 주제어' in c for c in calls))
    ok('공통 주제 선택·저장', q.get('theme') == '가족의 의미', q.get('theme'))
    gen = next((c for c in calls if '정확히 3개를 출제' in c), '')
    ok('생성 지시에 공통 주제·요약·엔티티', '[공통 주제] 가족의 의미' in gen and '가나다라' in gen and '요소:' in gen)
    ok('근거가 약한 2번만 다시 생성', sum('근거가 약하다' in c for c in calls) == 1 and '공동체' not in ' '.join(q['shown']), q['shown'][1][:60])
    ok('근거 점수 통과 표시', q.get('gr') == [True, True, True], q.get('gr'))
    # ── 질문 교체: 공통 주제·난이도 조건, 이력 저장
    n0 = len(J("window.__calls")); old = prog()['qs']['b0']['shown'][0]
    J("S.sample.json=(f=>async(p,o)=>p.includes('자리에 들어갈 질문이므로')?(window.__calls.push(p),[{q:(window.__rep=(window.__rep||0)+1)===1?'주인공의 선택을 평가하시오. (700자 내외)':'주인공의 선택에 드러난 가족의 의미를 근거를 들어 논하시오. (700자 내외)',from:['책','영화 ①']}]):f(p,o))(S.sample.json);0")
    J("genQ1(0,0)")
    ok('교체: 조건에 안 맞는 후보는 사유를 넣어 다시 요청', wait(lambda: '가족의 의미를 근거를 들어' in prog()['qs']['b0']['shown'][0]), prog()['qs']['b0']['shown'][0][:60])
    rc = [c for c in J("window.__calls")[n0:] if '자리에 들어갈 질문이므로' in c]
    ok('교체 지시에 공통 주제·목표 난이도', len(rc) == 2 and '[공통 주제] 가족의 의미' in rc[0] and '[목표 난이도]' in rc[0] and '직전 후보는 조건에 맞지 않았다' in rc[1], len(rc))
    ok('제시 이력 저장', old in prog()['qs']['b0'].get('hist', []) and len(prog()['qs']['b0']['hist']) >= 4)
    # ── 1차 첨삭: 오류 레코드 저장
    J("(t)=>{const k=nk(0);const P=prepOf(0);P.qDone=true;P.roadDone=true;S.essayDraft={i:0,q:0,text:t,files:[]};S.progress.picks=Object.assign({},S.progress.picks,{[k]:0})}", T1)
    J("evaluate(0)")
    ok('1차 첨삭 완료', wait(lambda: J("!!S.evals[nk(0)]&&!S.essayBusy"), 80), J("S.essayBusy"))
    wait(lambda: len(prog().get('errs', [])) == 3); pr = prog(); e = pr.get('errs', [])
    ok('오류 레코드 3건 저장(식별자·유형·회차)', [x['t'] for x in e] == ['맞춤법', '띄어쓰기', '긴 문장'] and all(x['id'].startswith('e') and x['rd'] == 1 and x['st'] == 'open' for x in e), e)
    ev1 = api('db.get', s['token'], path='evals/' + U + '_b0')['result']['data']
    ok('첨삭 기록에 px 저장, 임시 필드 없음', ev1.get('px', {}).get('n') == 3 and 'recur' not in ev1, ev1.get('px'))
    ok('개정 기준: 수준 환산·가중 총점(73)·쓰기 과정 분리', ev1.get('total') == 73 and ev1.get('levels', {}).get('어문 규범') == 2 and ev1['scores'].get('어문 규범') == 55 and ev1.get('process', {}).get('plan') == '충실' and '적극성' not in ev1['scores'], (ev1.get('total'), ev1.get('scores'), ev1.get('process')))
    mp = next((c for c in J("window.__calls") if '20년 넘게' in c), '')
    ok('지시문: 여섯 영역 기술어·학년 기대 수준·하한 없음', '① 작품 이해와 활용(배점 20)' in mp and '중1의 도달(3)' in mp and '70점 아래로' not in mp and '적극성' not in mp, mp[:200])
    ok('첫 첨삭 지시에는 지속 오류 없음, 유형 지시는 있음', not any('[지속 오류 확인]' in c for c in J("window.__calls")) and any('[문장 오류 유형]' in c for c in J("window.__calls")))
    # ── 2차 첨삭: 문장 정렬·이중 판정·재질의·해소 상태
    J("(t)=>{const k=nk(0);const e=S.evals[k];e.at-=80*3600e3;e.firstAt=e.at;S.progress.drafts2=Object.assign({},S.progress.drafts2,{[k]:t})}", T2)
    ok('다시 쓰기 잠금 풀림(시험용)', J("rwLeft(S.evals[nk(0)])===0"))
    n1 = len(J("window.__calls")); J("evaluate(0,2)")
    ok('2차 첨삭 완료', wait(lambda: J("!!S.evals2[nk(0)]&&!S.essayBusy"), 80), J("S.essayBusy"))
    c2 = J("window.__calls")[n1:]
    ok('2차 지시에 오류 식별자와 대응 문장', any('[1차 오류 해소 판정]' in c and '2차 대응 문장' in c and 'id:e1' in c for c in c2))
    ok('빠진 식별자만 재질의', sum('검증에 실패' in c for c in c2) == 1)
    px2 = J("S.evals2[nk(0)].px")
    fx = {x['id']: x['c'] for x in px2['fix']}
    ok('해소·부분해소 분류', fx == {'e1': 'res', 'e2': 'part', 'e3': 'res'}, fx)
    ok('고친 정도 산출', px2['n'] == 3 and px2['res'] == 2 and px2['part'] == 1 and px2['rate'] == 83, px2)
    ok('오류 레코드 해소 상태 저장', wait(lambda: {x['id']: x['st'] for x in prog()['errs']} == {'e1': 'res', 'e2': 'part', 'e3': 'res'}), [(x['id'], x['st']) for x in prog()['errs']])
    ok('결과 화면에 해소 요약', wait(lambda: '1차에서 짚은 오류 3개' in pg.inner_text('body')), '')
    # ── 다음 달 첨삭: 지속 오류 주입·재발 판정·재질의
    J("document.querySelector('[data-act=closesheet]')&&document.querySelector('[data-act=closesheet]').click()"); time.sleep(.3)
    J("(t)=>{S.evalView=null;const k=nk(1);S.progress.qs[k]={shown:['가족의 의미를 논하시오. (800자 내외)','b','c'],tags:[[],[],[]],ai:true,v:3};const P=prepOf(1);P.qDone=true;P.roadDone=true;S.essayDraft={i:1,q:0,text:t,files:[]}}", '주인공은 가족에게 갈수있다고 믿는다. 가족의 의미는 서로 돕는 데 있다고 생각한다.'+PAD)
    n2 = len(J("window.__calls")); J("evaluate(1)")
    ok('다음 달 첨삭 완료', wait(lambda: J("!!S.evals[nk(1)]&&!S.essayBusy"), 80), J("S.essayBusy"))
    c3 = J("window.__calls")[n2:]
    main = next((c for c in c3 if '20년 넘게' in c), '')
    ok('지시에 지속 오류 식별자·예문', '[지속 오류 확인]' in main and 'id:e2' in main and '줄수있다' in main, main[-400:])
    ok('해소된 유형보다 남은 유형이 먼저', main.find('유형: 띄어쓰기') < main.find('유형: 맞춤법') if '유형: 맞춤법' in main else '유형: 띄어쓰기' in main)
    ok('재발 판정이 빠진 식별자는 재질의', sum('검증에 실패' in c for c in c3) == 1)
    px3 = J("S.evals[nk(1)].px")
    ok('재발 판정 기록', px3 and len(px3['recur']) >= 2 and all(isinstance(x['recur'], bool) for x in px3['recur']), px3)
    wait(lambda: any(x['rd'] == 2 for x in prog()['errs'])); e3 = [x for x in prog()['errs'] if x['rd'] == 2]
    ok('재발한 지속 오류가 이번 회차 건수에 반영', any(x.get('re') for x in e3) and any(x['t'] == '띄어쓰기' and not x.get('re') for x in e3), e3)
    # ── 주제 게이트: 낙서는 AI를 부르지 않고 돌려보냄
    n3 = len(J("window.__calls"))
    J("()=>{S.evalView=null;delete S.evals[nk(1)];S.essayDraft={i:1,q:0,text:'아아아아아아아아아아아아아아아아아아',files:[]}}"); J("evaluate(1)"); time.sleep(.8)
    ok('낙서는 AI 호출 없이 주제 불일치 안내', len(J("window.__calls")) == n3 and J("!!S.essayOff&&!S.essayBusy"), J("S.essayOff"))
    # ── 최소 분량: 학년 권장 분량 하한의 50% 미만이면 AI를 부르지 않고 '조금 더' 안내
    n4 = len(J("window.__calls"))
    J("()=>{S.evalView=null;S.essayOff=null;delete S.evals[nk(1)];S.essayDraft={i:1,q:0,text:'가족의 의미는 서로 돕는 데 있다. 주인공은 가족을 도왔다. 그래서 가족은 소중하다고 생각한다.',files:[]}}"); J("evaluate(1)"); time.sleep(.8)
    ok('짧은 글은 채점하지 않고 분량 안내', len(J("window.__calls")) == n4 and J("!!(S.essayOff&&S.essayOff.short)&&!S.essayBusy"), J("S.essayOff"))
    # ── 육각형 독서(지식 분야·깊이·학년 목표)
    J("""()=>{const P=S.progress;P.done=Object.assign({},P.done,{'b0:book':1,'b1:book':1});P.evDone={b0:1};P.orDone={};P.quotes={};P.notes={};P.catOv={};
      P.myBooks=[{id:'o1',title:'시간의 역사',main:5,sub:null,cat:'과학',at:1},{id:'v1',title:'어느 역사 소설',main:3,sub:0,v:2,g:'중1',cat:'소설',at:2},{id:'c1',title:'만화 한국사',main:3,v:2,nc:1,g:'중1',cat:'역사/문화',at:3},{id:'u1',title:'모르는 책',main:-1,v:2,g:'중1',cat:'기타',at:4}];
      P.quotes[hid('시간의 역사')]=[{t:'우주는 넓다'}]}""")
    hx = J("(()=>{const h=hexScores('중1');return {p:h.p,t:h.t,n:h.n,un:h.un,even:h.even}})()")
    ok('육각형: 분야별 점수(코스 책 고정 분야·논술 깊이 2·문장 1.5·0.7/0.3·만화 제외·미정 제외)', hx['p'] == [2.3, 1, 0, 0.7, 1.5, 0] and hx['t'] == [9, 4, 4, 4, 6, 3] and hx['n'] == 4 and hx['un'] == 1, hx)
    J("()=>{S.progress.catOv={[hid('모르는 책')]:'역사/문화'}}")
    ok('육각형: 서가에서 고른 서점 분류로 미정 책 분야 결정', J("hexScores('중1').p[3]") == 1.7, J("hexScores('중1').p"))
    ok('육각형: 3년 누적 목표 90점', J("hexScores('all').t.reduce((a,b)=>a+b,0)") == 90)
    svg = J("radarSVG([0,0,0,0,0,0],300,true)")
    ok('육각형: 0은 중심점, 숫자 병기', 'NaN' not in svg and '0 / 9' in re.sub(r'<[^>]+>','',svg), svg[:120])
    J("()=>{S.view='me';S.sheet=null;render()}"); time.sleep(.5)
    body = pg.text_content('body')  # 정의는 접힌 펼침 상자 안에 있음
    ok('육각형 화면 문구: 능력 점수가 아님·고른 읽기', '능력이나 인성 점수가 아니에요' in body and '고른 읽기' in body and '절대 실행력' not in body, body[:200])
    ok('구술 군말 규칙: 뜻 있는 낱말은 세지 않음', J("orFill('그 장면은 약간 다르다 음 저는 막 시작했을 때 어 그러니까')") == 2 and J("orSpeed(250)") == '알맞아요' and J("orSpeed(300)") == '알맞아요' and J("orSpeed(150)") == '많이 느려요')
    # ── ISBN·서명 서지 조회(가짜 국립중앙도서관 응답)
    ok('ISBN 검사', J("isbnOK('9780306406157')&&isbnOK('0-306-40615-2')&&!isbnOK('9780306406158')"))
    x = J("bkLookup({isbn:'9780306406157'})")
    ok('ISBN 조회: KDC 443 → 과학·기술, 저자 정리', x and x['main'] == 4 and x['kdc'] == '443' and x['author'] == '브라이언 그린', x)
    J("()=>{S.mbRate={fun:4,diff:3,again:4};S.nlOff=null}")
    J("async()=>{const f=new FormData();f.set('isbn','9780306406157');f.set('title','');f.set('author','');f.set('ax','auto');f.set('cat','auto');await addMyBook(f)}"); time.sleep(.5)
    nb = J("S.progress.myBooks[S.progress.myBooks.length-1]")
    ok('ISBN만 넣어도 제목·분야·서가 칸을 정함(AI 호출 없음)', nb['title'] == '우주의 구조' and nb['main'] == 4 and nb['src'] == 'nl' and nb['cat'] == '과학' and nb['isbn'] == '9780306406157', nb)
    J("async()=>{const f=new FormData();f.set('isbn','');f.set('title','만화로 보는 한국사');f.set('author','');f.set('ax','auto');f.set('cat','auto');S.mbRate={fun:4,diff:3,again:4};await addMyBook(f)}"); time.sleep(.5)
    nb = J("S.progress.myBooks[S.progress.myBooks.length-1]")
    ok('제목 조회: 부가기호 만화는 세지 않음', nb['main'] == 3 and nb.get('nc') == 1 and nb.get('ncw') == '그림책·만화', nb)
    ok('해설서 말고 같은 제목의 책을 고름', J("bkLookup({title:'시간을 파는 상점'})")['author'] == '김선영')
    ok('찾지 못한 책은 null', J("bkLookup({title:'세상에 없는 책 제목'})") is None)
    J("()=>{const i=S.course.findIndex(x=>/청소년 논어/.test(x.book));S.progress.bkax={};S.progress.done=Object.assign({},S.progress.done,{['b'+i+':book']:1})}"); J("hxSync()"); time.sleep(1.5)
    ok('코스 책을 도서관 분류로 확인해 저장', J("((S.progress.bkax||{})[hid('진짜 어른이 되기 위한 청소년 논어')]||{}).m") == 1, J("S.progress.bkax"))
    # ── 새 단계가 실패해도 예전처럼 동작
    J("()=>{window.__mode.nometa=true;S.qmeta={};localStorage.removeItem('002.px.qm');S.essayOff=null}")
    J("genQs(1)")
    ok('서술문 요청이 실패해도 질문은 생성', wait(lambda: '비교하고 논하시오' in prog()['qs']['b1']['shown'][0] and len(prog()['qs']['b1']['shown']) == 3 and 'theme' not in prog()['qs']['b1']), str(prog()['qs'].get('b1'))[:160])
    b.close()
ok('페이지 오류 없음', not errs, errs[:3])
print('%d/%d' % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
