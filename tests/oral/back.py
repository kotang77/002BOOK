# 휴대폰 뒤로가기: 창이 열려 있으면 앱을 떠나지 않고 맨 위 창부터 닫는다
import json, time, urllib.request, sys
from playwright.sync_api import sync_playwright
API='http://localhost:8000'; WEB='http://localhost:8080'; PW='testpass1234'; res=[]
def ok(n,c,x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ')+n+('' if c else f' — {x}'))
def api(op, tok=None, **kw):
    h={'content-type':'application/json'}
    if tok: h['x-session']=tok
    r=urllib.request.Request(API,data=json.dumps({'op':op,**kw}).encode(),headers=h,method='POST')
    try: return json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())
if 'result' not in api('auth.login',id='backtest',pw=PW): api('auth.signup',id='backtest',pw=PW,email='bt@ex.com',agreeTerms=True,agreePrivacy=True,birth='1980-01',grade='아빠',nick='뒤로',gender='남자')
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome'); pg=b.new_page(viewport={'width':390,'height':844}); errs=[]
    pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(WEB+'/'); pg.wait_for_selector('#li-id'); pg.fill('#li-id','backtest'); pg.fill('#li-pw',PW); pg.click('form[data-form=login] button[type=submit]')
    pg.wait_for_selector('.who',timeout=15000); time.sleep(1.5)
    act=lambda sel: pg.evaluate("s=>{const e=document.querySelector(s);if(!e)throw new Error('없음 '+s);e.click()}", sel)
    act('[data-act=month][data-i="0"]'); time.sleep(.8)
    ok('창 열림', not pg.locator('#layer1').is_hidden())
    x=pg.locator('#layer1 .ph .x').first; bg=pg.evaluate("e=>{const c=getComputedStyle(e);return c.backgroundColor+' | '+c.backgroundImage+' | '+c.boxShadow}", x.element_handle())
    ok('닫기 버튼 중간 호박색 단색 원 40px(빛·광택 없음, 11-28)', bg == 'rgb(224, 162, 58) | none | none' and x.bounding_box()['width']>=39, bg[:160])
    pg.go_back(); time.sleep(.8)
    ok('뒤로가기 → 창만 닫힘(앱 그대로)', pg.locator('#layer1').is_hidden() and pg.locator('.who').count()==1 and pg.url.startswith(WEB))
    act('[data-act=view][data-v=vision]'); time.sleep(.8)
    ok('비전보드 메뉴 열림', pg.locator('main .vpage').count()==1)
    pg.go_back(); time.sleep(.8)
    ok('다른 메뉴에서 뒤로가기 → 독서(홈)', pg.locator('main .vpage').count()==0 and pg.locator('#layer1').is_hidden())
    act('[data-act=month][data-i="0"]'); time.sleep(.6); act('#layer1 .ph .x'); time.sleep(.8)
    ok('X로 닫은 뒤 뒤로가기 기록 정리', pg.evaluate("history.state&&history.state.nav||0")==0, pg.evaluate("history.state"))
    ok('화면 오류 없음', not errs, errs)
    b.close()
api('auth.withdraw', api('auth.login',id='backtest',pw=PW)['result']['session']['token'], pw=PW)
print(f'{sum(res)}/{len(res)}'); sys.exit(0 if all(res) else 1)
