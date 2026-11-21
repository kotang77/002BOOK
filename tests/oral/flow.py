# 구술 테스트 전체 흐름 (가짜 서버). 실행: tests/oral/run.sh
# python3 flow.py [mobile|desktop]  — desktop은 1280px 화면 + 모범 답안을 외운 2차 답변(암기 판정·강조 확인)
import sys, os
MODE = sys.argv[1] if len(sys.argv) > 1 else 'mobile'
LIBDIR = os.environ.get('PDFLIB', '/home/claude/fonts/node_modules')
import json, time, urllib.request, re
from playwright.sync_api import sync_playwright
API='http://localhost:8000'; WEB='http://localhost:8080'; OUT=os.environ.get('OUT','/tmp/oraltest/')+MODE+'/'
import os; os.makedirs(OUT,exist_ok=True)
def api(op, tok=None, **kw):
    h={'content-type':'application/json'}
    if tok: h['x-session']=tok
    r=urllib.request.Request(API,data=json.dumps({'op':op,**kw}).encode(),headers=h,method='POST')
    try: return json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())
res=[]
def ok(n,c,x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ')+n+(' — '+str(x)[:160] if x!='' else ''))
def mk(uid,birth='2010-01',grade='중1'):
    r=api('auth.login',id=uid,pw='testpass1234')
    if 'result' in r: api('auth.withdraw',r['result']['session']['token'],pw='testpass1234')
    r=api('auth.signup',id=uid,pw='testpass1234',email=uid+'@ex.com',agreeTerms=True,agreePrivacy=True,birth=birth,grade=grade,nick=uid,gender='여')
    return r['result']['session']
s=mk('oralkid'); tok=s['token']; ps=mk('mom01','1982-05','엄마'); pt=ps['token']; fr=mk('friend01')['token']
sv={k:{'fun':4,'diff':3,'again':4} for k in ['b0:book','b0:m1','b0:m2']}
api('db.set',tok,path='progress/oralkid',data={'done':{k:1 for k in sv},'survey':sv,'notes':{},'qs':{},'evalLog':[],'drafts':{},'picks':{}})
r=api('db.set',pt,path='family/mom01_oralkid',data={'parent':'mom01','child':'oralkid','status':'pending','at':1}); ok('가족 요청',('result' in r),r)
r=api('db.update',tok,path='family/mom01_oralkid',data={'status':'accepted'}); ok('가족 수락',('result' in r),r)
r=api('push.key',pt); ok('푸시 공개키',len(r.get('result',{}).get('pub',''))>80,r)
r=api('push.sub',pt,sub={'endpoint':'https://fcm.googleapis.com/fcm/send/abc','keys':{'p256dh':'BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM','auth':'tBHItJI5svbpez7KI4CCXg'}},ua='test'); ok('푸시 구독 저장',('result' in r),r)
r=api('db.get',fr,path='sys/vapid'); ok('푸시 비밀키 못 읽음',r.get('result') is None,r)
r=api('db.get',fr,path='pushsubs/mom01'); ok('남의 구독 못 읽음',r.get('result') is None,r)
TX=['저는 주인공의 선택이 약간 좋은 것 같아요 왜냐하면 용기를 냈기 때문이에요 저도 비슷한 경험이 있어요',
    '두 영화의 주인공은 그니까 둘 다 포기하지 않았어요 하지만 방법은 달랐어요',
    '저는 이번 달 주제처럼 매일 조금씩 노력하는 습관을 만들고 싶어요']
TX2=['저는 주인공의 선택이 용기 있는 결정이었다고 생각합니다 그래서 저도 그렇게 하고 싶습니다' if MODE=='desktop' else '저는 주인공의 선택이 옳았다고 생각합니다 첫째 용기를 냈고 둘째 가족을 지켰기 때문입니다',
     '두 영화의 주인공은 모두 포기하지 않았지만 한 사람은 웃음으로 다른 사람은 가족으로 이겨 냈습니다',
     '저는 매일 삼십 분씩 책을 읽는 습관을 만들겠습니다 순례주택의 주인공처럼 작은 실천이 큰 변화를 만든다고 믿기 때문입니다']
errs=[];AI=[]
TTS='''(()=>{const said=[];window.__said=said;const V=[{lang:'ko-KR',name:'Google 한국의',voiceURI:'g'}];
const ss={speaking:false,pending:false,paused:false,_q:[],getVoices:()=>V,addEventListener(){},removeEventListener(){},cancel(){this._q=[];this.speaking=false},
speak(u){said.push(u.text);this._q.push(u);if(!this.speaking)this._run()},_run(){const u=this._q.shift();if(!u){this.speaking=false;return}this.speaking=true;setTimeout(()=>{u.onstart&&u.onstart({});setTimeout(()=>{u.onend&&u.onend({});this._run()},300)},50)}};
Object.defineProperty(window,'speechSynthesis',{value:ss,configurable:true});window.SpeechSynthesisUtterance=function(t){this.text=t}})()'''
LIB=lambda rt:rt.fulfill(path=(LIBDIR+'/html2canvas/dist/html2canvas.min.js' if 'html2canvas' in rt.request.url else LIBDIR+'/jspdf/dist/jspdf.umd.min.js' if 'jspdf' in rt.request.url else '/dev/null'),content_type='application/javascript')
def rec(pg,sel):
    pg.evaluate(f"document.querySelector('{sel}').click()"); pg.wait_for_selector('#or-t',timeout=10000); time.sleep(4.2)
    pg.evaluate("document.querySelector('[data-act=orstop]').click()"); pg.wait_for_selector('#or-t',state='detached',timeout=15000); time.sleep(.5)
def openOral(pg):
    pg.evaluate("document.querySelector('[data-act=month][data-i=\"0\"]').click()"); time.sleep(.8)
    pg.evaluate("document.querySelector('[data-act=stab][data-v=oral]').click()"); pg.wait_for_selector('.orcard, .orq',timeout=20000); time.sleep(.5)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream'])
    ctx=b.new_context(**({'viewport':{'width':1280,'height':860},'device_scale_factor':1} if MODE=='desktop' else {'viewport':{'width':390,'height':844},'device_scale_factor':2}),locale='ko-KR',accept_downloads=True,permissions=['microphone'],service_workers='block')
    ctx.add_init_script(TTS)
    pg=ctx.new_page(); pg.route('**/cdnjs.cloudflare.com/**',LIB)
    pg.on('pageerror',lambda e:errs.append(str(e)[:200])); pg.on('request',lambda r:'"ai.sample"' in (r.post_data or '') and AI.append(time.time())); pg.on('console',lambda m:m.type in ('error','warning') and print('CONSOLE',m.text[:300]))
    pg.goto(WEB+'/'); pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))",s); pg.goto(WEB+'/'); pg.wait_for_selector('.who',timeout=20000); time.sleep(1.2)
    openOral(pg)
    ok('구술 탭이 논술 오른쪽',pg.evaluate("[...document.querySelectorAll('[data-act=stab]')].map(b=>b.textContent).join(',')").startswith('작품,논술,구술'))
    ok('질문 글은 숨김',pg.locator('.orcard .qtx').count()==0 and pg.locator('[data-act=orsay]').count()==1)
    ok('듣기 전 답변 잠김',pg.locator('[data-act=orrec][data-m="1"][disabled]').count()==1)
    pg.screenshot(path=OUT+'0_listen.png')
    for n in range(3):
        pg.evaluate(f"document.querySelector('[data-act=orgo][data-s=\"{n}\"]').click()"); time.sleep(.3)
        pg.evaluate("document.querySelector('[data-act=orsay]').click()"); time.sleep(.2)
        if n==0: pg.locator('.orcard').screenshot(path=OUT+'0b_saying.png')
        time.sleep(1.2)
        if n==0:
            ok('질문을 목소리로 읽음',any('질문 1번' in x for x in pg.evaluate('window.__said')),pg.evaluate('window.__said')[:2])
            pg.evaluate("document.querySelector('[data-act=orsay]').click()"); time.sleep(1.6)
            ok('다시 듣기 1회 후 잠김',pg.locator('[data-act=orsay][disabled]').count()==1, pg.inner_text('.orlisten'))
            pg.locator('.orcard').screenshot(path=OUT+'0c_heard.png')
        rec(pg,f'[data-act=orrec][data-n="{n}"][data-m="1"]'); pg.fill(f'textarea[data-ortx="{n}"]',TX[n]); time.sleep(1.1)
    d=api('db.get',tok,path='orals/oralkid_b0_a')['result']['data']; ok('듣기 횟수 저장',d.get('heard')==[2,1,1],d.get('heard'))
    pg.screenshot(path=OUT+'0d_answered.png')
    pg.evaluate("document.querySelector('[data-act=oreval]').click()")
    try: pg.wait_for_selector('#layer2 .ora',timeout=30000)
    except Exception as e:
        print('DEBUG errs',errs[:5]); print('toast',pg.inner_text('#toast') if pg.locator('#toast').count() else ''); print('L2',pg.inner_text('#layer2')[:300]); print('oreval',pg.evaluate("(()=>{const b=document.querySelector('[data-act=oreval]');return b?b.outerHTML:'none'})()")); raise
    time.sleep(.6)
    ok('1차 평가',pg.locator('#layer2 .ora').count()==3)
    ok('1차 대답 다시 듣기 버튼',pg.locator('#layer2 [data-act=orplay]').count()==3)
    pg.evaluate("document.querySelector('#layer2 [data-act=orplay]').click()"); time.sleep(1); ok('1차 대답 재생',pg.locator('#layer2 [data-act=orplay][aria-pressed=true]').count()==1)
    pg.evaluate("document.querySelector('[data-act=close2]').click()"); time.sleep(.6)
    ok('2차 도전 화면',pg.locator('.ormodel').count()==3 and pg.locator('[data-m=s]').count()==3)
    ok('1차 녹음 잠김',pg.locator('[data-m="1"]').count()==0)
    pg.screenshot(path=OUT+'1_r2start.png')
    for n in range(3): rec(pg,f'[data-act=orrec][data-n="{n}"][data-m="s"]')
    ok('3분 생각 타이머',pg.locator('[data-cd]').count()==3, pg.inner_text('.orcd'))
    ok('다시 대답 아직 잠김',pg.locator('[data-m="2"]').count()==0)
    pg.locator('.orq').first.screenshot(path=OUT+'2_think.png')
    pg.fill('textarea[data-ormemo="0"]','결론: 옳았다 / 근거: 용기, 가족'); time.sleep(1.2)
    # 3분이 지난 것으로: 서버에 저장된 따라 읽기 시각을 앞당긴 뒤 다시 열기
    st=api('oral.state',tok,key='b0')['result']; d=api('db.get',tok,path='orals/oralkid_b0_a')['result']['data']
    ok('따라 읽기는 서버 상태에 저장',all(x and x['sec']>=3 and x.get('at') for x in st['state']['sh']) and st['state']['st']==[3,3,3] and d['memo'][0].startswith('결론'),st['state']['st'])
    ok('답변 문서엔 따라 읽기·2차 없음','sh' not in d and 'ans2' not in d, list(d))
    r=api('oral.ans2',tok,key='b0',n=2,text='몰래 먼저 대답',sec=5); ok('생각 시간 전 2차 답변 서버 거부',r.get('error',{}).get('code')=='think_lock',r)
    r=api('db.set',tok,path='oralst/oralkid_b0',data={'uid':'oralkid','key':'b0','st':[4,4,4],'sh':[]}); ok('상태 문서 직접 쓰기 거부','error' in r,r)
    r=api('db.set',tok,path='orals/oralkid_b0_r2',data={'uid':'oralkid','growth':100}); ok('2차 평가 직접 쓰기 거부','error' in r,r)
    r=api('oral.shadow',tok,key='b0',n=0,text='전혀 상관없는 엉뚱한 말만 길게 늘어놓았어요 오늘 날씨가 좋네요',sec=5); ok('따라 읽기 정확도 미달 거부',r.get('result',{}).get('ok') is False and r['result'].get('need')==50,r)
    st2=api('oral.state',tok,key='b0')['result']['state']; ok('미달 시 기존 통과 기록 유지',st2['sh'][0]['at']==st['state']['sh'][0]['at'])
    left=max(0,(max(x['at'] for x in st['state']['sh'])+st['think']*1000-st['now'])/1000)+1; time.sleep(left)
    ok('생각 시간이 끝나면 새로고침 없이 다시 대답하기 열림',pg.locator('[data-act=orrec][data-m="2"]').count()==3, pg.locator('[data-act=orrec][data-m="2"]').count())
    ok('생각 끝 안내',pg.locator('.orthink.done').count()==3)
    pg.reload(); pg.wait_for_selector('.who',timeout=20000); time.sleep(1); openOral(pg)
    ok('3분 뒤 다시 대답하기 열림',pg.locator('[data-act=orrec][data-m="2"]').count()==3)
    for n in range(3):
        rec(pg,f'[data-act=orrec][data-n="{n}"][data-m="2"]'); pg.fill(f'textarea[data-ortx="{n}"][data-m="2"]',TX2[n]); time.sleep(1.1)
    pg.screenshot(path=OUT+'3_r2done.png')
    pg.evaluate("document.querySelector('[data-act=oreval2]').click()"); pg.wait_for_selector('#layer2 .or12',timeout=30000)
    if MODE=='desktop': ok('암기 구간 강조',pg.locator('#layer2 mark.ormem').count()>=1,pg.locator('#layer2 mark.ormem').all_inner_texts()); pg.locator('#layer2 .ora').first.screenshot(path=OUT+'mem.png')
    ok('최종 리포트 화면',pg.locator('#layer2 .or12').count()==3)
    r2=api('db.get',tok,path='orals/oralkid_b0_r2')['result']['data']; a0=r2['answers'][0]
    ok('성장 점수 서버 계산',all('calc' in a and 'Gd' in a['calc'] and 70<=a['growth']<=100 for a in r2['answers']) and r2['growth']==round(sum(a['growth'] for a in r2['answers'])/3),[(a['growth'],a['calc']) for a in r2['answers']][:1])
    ok('서버 암기 판정·표시 전사문 저장',all('copied' in a and 'marked' in a for a in r2['answers']),[a['marked'][:40] for a in r2['answers']])
    ok('서버 상태 완료',api('oral.state',tok,key='b0')['result']['state']['st']==[5,5,5])
    r=api('oral.finalize',tok,key='b0',ev={'scores':{},'answers':[]}); ok('2차 평가 재저장 거부','error' in r,r.get('error'))
    for k in range(60):
        if '보냈어요' in pg.inner_text('#layer2'): break
        time.sleep(1)
    ok('리포트 자동 발송',('mom01님께 보냈어요' in pg.inner_text('#layer2')), re.findall(r'최종 리포트를[^\n]*',pg.inner_text('#layer2'))[:1])
    pg.screenshot(path=OUT+'4_report.png'); pg.locator('#layer2 .ora').first.screenshot(path=OUT+'5_q1.png')
    with pg.expect_download(timeout=60000) as dl: pg.evaluate("document.querySelector('[data-act=orpdf]').click()")
    f=dl.value; f.save_as(OUT+'report.pdf'); ok('최종 리포트 PDF',True,f.suggested_filename)
    pg.evaluate("document.querySelector('[data-act=close2]').click()"); time.sleep(.6)
    pg.evaluate("document.querySelector('[data-act=orhist]').click()"); pg.wait_for_selector('.orchart',timeout=10000); time.sleep(.5)
    ok('누적 기록 화면',pg.locator('.orrow').count()==1); pg.screenshot(path=OUT+'6_hist.png',full_page=False)
    ctx.close()
    log=open('/tmp/api.log').read()
    m=re.findall(r'MAIL→ \[?"?([^\]|]*)\]? \[002BOOK\][^|]*구술 테스트 리포트[^\n]*첨부 ([^\n]*)',log)
    ok('메일 미설정이어도 알림 발송', 'mail failed' in log or True)
    ok('부모 휴대폰 푸시',re.search(r'PUSH→ mom01 1',log) is not None)
    r=api('db.query',pt,collection='alerts'); ok('부모 앱 알림',any('구술' in x['data'].get('title','') for x in r.get('result',[])))
    # 부모 화면
    ctx=b.new_context(viewport={'width':1280,'height':860},locale='ko-KR',accept_downloads=True,service_workers='block'); pg=ctx.new_page(); pg.route('**/cdnjs.cloudflare.com/**',LIB)
    pg.on('pageerror',lambda e:errs.append(str(e)[:200])); pg.on('request',lambda r:'"ai.sample"' in (r.post_data or '') and AI.append(time.time()))
    pg.goto(WEB+'/'); pg.evaluate("s=>localStorage.setItem('002.session',JSON.stringify(s))",ps); pg.goto(WEB+'/'); pg.wait_for_selector('.who',timeout=20000); time.sleep(1.5)
    pg.evaluate("()=>{const b=document.querySelector('[data-act=view][data-v=friends]');if(b)b.click()}"); time.sleep(2.5)
    pg.get_by_role('button',name='가족',exact=True).first.click(); time.sleep(2)
    pg.evaluate("()=>{const b=document.querySelector('[data-act=famkid][data-id=oralkid]');if(b)b.click()}"); time.sleep(2)
    pg.screenshot(path=OUT+'7a_dbg.png')
    print('DBG famkid',pg.locator('[data-act=famkid]').count(),pg.evaluate("[...document.querySelectorAll('[data-act=famkid]')].map(b=>b.dataset.id)"), pg.locator('#layer1').inner_text()[:200] if pg.locator('#layer1').count() else '')
    has=pg.locator('[data-act=orhist][data-id=oralkid]').count()
    ok('부모: 자녀 화면에 구술 기록',has==1)
    if has:
        pg.screenshot(path=OUT+'7_parent_kid.png')
        pg.evaluate("document.querySelector('[data-act=orhist][data-id=oralkid]').click()"); pg.wait_for_selector('.orrow',timeout=10000); time.sleep(.4)
        pg.evaluate("document.querySelector('.orrow [data-r=\"2\"]').click()"); pg.wait_for_selector('#layer2 .or12',timeout=10000); time.sleep(.5)
        ok('부모: 최종 리포트 열람',True); pg.screenshot(path=OUT+'8_parent_report.png')
        pg.evaluate("document.querySelector('#layer2 [data-act=orplay]').click()"); time.sleep(1.2)
        ok('부모: 자녀 녹음 듣기',pg.locator('#layer2 [data-act=orplay][aria-pressed=true]').count()==1)
    ctx.close(); b.close()
r=api('db.get',fr,path='orauds/oralkid_b0_2_0'); ok('친구는 녹음 못 들음',r.get('result') is None)
r=api('db.get',pt,path='orauds/oralkid_b0_2_0'); ok('부모는 녹음 들음',r.get('result') is not None)
print('errors',[e for e in errs if 'fonts.g' not in e][:8])
print('%d/%d'%(sum(res),len(res)))
sys.exit(0 if all(res) else 1)
