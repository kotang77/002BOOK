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
const EV=(o)=>Object.assign({offTopic:false,praise:'잘했어요',progress:'좋아졌어요',unreadable:[],scores:{'논지':85,'근거':80,'구성':82,'표현':84,'맞춤법':78,'적극성':90},scoreWhy:{},comment:'',paragraphs:'',paraReview:[],strengths:['a'],improvements:['띄어쓰기를 고쳐요'],tags:['띄어쓰기'],cumulative:'',marks:[],teacher:'좋아요',models:[]},o);
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
T2 = '나는 어른이 되었다고 생각한다. 주인공은 가족을 도와 줄수있다. 가족은 중요하다. 가족이 없으면 힘들기 때문이다.'
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, locale='ko-KR', service_workers='block'); ctx.add_init_script(TTS); ctx.add_init_script('window.__002TEST=o=>{Object.assign(window,o)}'); pg = ctx.new_page()
    pg.route('**/cdnjs.cloudflare.com/**', lambda rt: rt.fulfill(body='', content_type='application/javascript'))
    pg.on('pageerror', lambda e: errs.append(str(e)[:200]))
    pg.goto(WEB + '/'); pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))", s); pg.goto(WEB + '/'); pg.wait_for_selector('.who', timeout=20000); time.sleep(1)
    J = lambda x, *a: pg.evaluate(x, *a)
    J(STUB); J("([a,b])=>{window.__t1=a;window.__t2=b}", [T1, T2])
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
    J("(t)=>{S.evalView=null;const k=nk(1);S.progress.qs[k]={shown:['가족의 의미를 논하시오. (800자 내외)','b','c'],tags:[[],[],[]],ai:true,v:3};const P=prepOf(1);P.qDone=true;P.roadDone=true;S.essayDraft={i:1,q:0,text:t,files:[]}}", '주인공은 가족에게 갈수있다고 믿는다. 가족의 의미는 서로 돕는 데 있다고 생각한다.')
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
    # ── 새 단계가 실패해도 예전처럼 동작
    J("()=>{window.__mode.nometa=true;S.qmeta={};localStorage.removeItem('002.px.qm');S.essayOff=null}")
    J("genQs(1)")
    ok('서술문 요청이 실패해도 질문은 생성', wait(lambda: '비교하고 논하시오' in prog()['qs']['b1']['shown'][0] and len(prog()['qs']['b1']['shown']) == 3 and 'theme' not in prog()['qs']['b1']), str(prog()['qs'].get('b1'))[:160])
    b.close()
ok('페이지 오류 없음', not errs, errs[:3])
print('%d/%d' % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
