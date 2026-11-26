# 라운지 엽서 시험: 서버 규칙(받는 사람만 열어 봄 표시·내용 못 바꿈·열기 전에만 발신 취소·받은 엽서는 남음·남은 못 읽음)과
# 화면 흐름(엽서 쓰기 → 디자인·받는 사람 고르기 → 보내기 → 받는 사람 새 엽서 → 열면 우체국 소인 → 보낸 사람 화면에서 '읽음'·취소 버튼 사라짐)
import json, sys, time, urllib.request
from playwright.sync_api import sync_playwright
API = 'http://localhost:8000'; WEB = 'http://localhost:8080'
res = []
def ok(n, c, x=''): res.append(bool(c)); print(('PASS ' if c else 'FAIL ') + n + (' — ' + str(x)[:160] if x != '' else ''))
def api(op, tok=None, **kw):
    h = {'content-type': 'application/json'}
    if tok: h['x-session'] = tok
    r = urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST')
    try: return json.loads(urllib.request.urlopen(r).read())
    except urllib.error.HTTPError as e: return json.loads(e.read())
def mk(uid, grade='중1', birth='2010-01'):
    r = api('auth.login', id=uid, pw='testpass1234')
    if 'result' in r: api('auth.withdraw', r['result']['session']['token'], pw='testpass1234')
    r = api('auth.signup', id=uid, pw='testpass1234', email=uid + '@ex.com', agreeTerms=True, agreePrivacy=True, birth=birth, grade=grade, nick=uid, gender='여')
    return r['result']['session']['token']
A, B, C, T = mk('pcsend1'), mk('pcrecv1'), mk('pcother1'), mk('pcteach1', '선생님', '1980-03')
pid = '__'.join(sorted(['pcsend1', 'pcrecv1']))
api('db.set', A, path='friends/' + pid, data={'a': min('pcsend1', 'pcrecv1'), 'b': max('pcsend1', 'pcrecv1'), 'from': 'pcsend1', 'to': 'pcrecv1', 'status': 'pending', 'at': 1})
r = api('db.update', B, path='friends/' + pid, data={'status': 'accepted'}); ok('친구 맺기', 'result' in r, r)
api('db.set', T, path='family/pcteach1_pcsend1', data={'parent': 'pcteach1', 'child': 'pcsend1', 'status': 'pending', 'at': 1})
r = api('db.update', A, path='family/pcteach1_pcsend1', data={'status': 'accepted'}); ok('선생님과 가족 맺기', 'result' in r, r)

# 서버 규칙
P = {'id': 'post_rule1', 'kind': 'post', 'pair': pid, 'from': 'pcsend1', 'to': 'pcrecv1', 'fromNick': 'pcsend1', 'toNick': 'pcrecv1', 'design': 'kraft', 'text': '같이 읽자!', 'at': 1000, 'openedAt': 0}
r = api('db.set', A, path='msgs/post_rule1', data=P); ok('엽서 보내기', 'result' in r, r)
r = api('db.get', B, path='msgs/post_rule1'); ok('배달 전(24시간, 시험 서버 3초)에는 받는 사람에게 안 보임', r.get('result') is None, r)
r = api('db.get', A, path='msgs/post_rule1'); d = (r.get('result') or {}).get('data', r.get('result') or {})
ok('배달 시각은 서버가 정함', isinstance(d, dict) and d.get('deliverAt', 0) - d.get('at', 0) == 3000, d)
time.sleep(3.3)
r = api('db.set', A, path='msgs/post_fake', data={**P, 'id': 'post_fake', 'from': 'pcrecv1'}); ok('남의 이름으로 못 보냄', 'result' not in r, r)
r = api('db.get', C, path='msgs/post_rule1'); ok('남은 엽서를 못 읽음', r.get('result') is None, r)
r = api('db.update', B, path='msgs/post_rule1', data={'text': '바꿈'}); ok('받는 사람도 내용은 못 바꿈', 'result' not in r, r)
r = api('db.update', A, path='msgs/post_rule1', data={'openedAt': 5}); ok('보낸 사람은 읽음 표시 못 함', 'result' not in r, r)
r = api('db.delete', B, path='msgs/post_rule1'); ok('받은 엽서는 지워지지 않고 남음', 'result' not in r, r)
r = api('db.update', B, path='msgs/post_rule1', data={'openedAt': 2000}); ok('받는 사람이 열어 봄 표시', 'result' in r, r)
r = api('db.delete', A, path='msgs/post_rule1'); ok('읽은 엽서는 발신 취소 못 함', 'result' not in r, r)
r = api('db.set', A, path='msgs/post_rule2', data={**P, 'id': 'post_rule2', 'at': 3000}); r = api('db.delete', A, path='msgs/post_rule2'); ok('안 읽은(배달 중) 엽서는 발신 취소', 'result' in r, r)
S = {**P, 'id': 'post_self1', 'to': 'pcsend1', 'pair': 'pcsend1__pcsend1', 'deliverAt': int(time.time() * 1000) + 100000}
r = api('db.set', A, path='msgs/post_self1', data=S); ok('나에게 엽서 보내기', 'result' in r, r)
r = api('db.get', A, path='msgs/post_self1'); ok('나에게 보낸 엽서는 받을 날까지 나도 못 봄', r.get('result') is None, r)
r = api('db.delete', A, path='msgs/post_self1'); ok('나에게 보낸 엽서는 취소 못 함', 'result' not in r, r)
r = api('db.set', A, path='msgs/post_self2', data={**S, 'id': 'post_self2', 'deliverAt': 5}); time.sleep(1.3)
r = api('db.get', A, path='msgs/post_self2'); ok('지난 날짜는 바로 다음으로 맞춰 배달', r.get('result') is not None, r)
api('db.delete', B, path='friends/' + pid)  # (친구 관계는 화면 시험을 위해 다시 맺는다)
api('db.set', A, path='friends/' + pid, data={'a': min('pcsend1', 'pcrecv1'), 'b': max('pcsend1', 'pcrecv1'), 'from': 'pcsend1', 'to': 'pcrecv1', 'status': 'pending', 'at': 1})
api('db.update', B, path='friends/' + pid, data={'status': 'accepted'})

with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
    def page(uid):
        c = b.new_context(viewport={'width': 390, 'height': 844}, service_workers='block')
        q = c.new_page(); q.goto(WEB + '/'); q.wait_for_selector('#li-id')
        q.fill('#li-id', uid); q.fill('#li-pw', 'testpass1234'); q.click('form[data-form=login] button[type=submit]')
        q.wait_for_selector('.who', timeout=15000); time.sleep(1.5)
        q.evaluate("document.querySelector('nav.nav [data-v=friends]').click()"); time.sleep(2)
        q.click('[data-act=frtab][data-v=post]'); time.sleep(.8)
        return q
    qa = page('pcsend1')
    ok('메뉴 이름 라운지', '라운지' in qa.inner_text('nav.nav'))
    ok('라운지 탭 순서: 친구·가족·북클럽·엽서함·알람', qa.evaluate("[...document.querySelectorAll('[data-act=frtab]')].map(b=>b.dataset.v).join()") == 'my,fam,club,post,alarm')
    qa.click('[data-act=pcnew]'); time.sleep(.8)
    opts = qa.evaluate("[...document.querySelectorAll('#pc-to option')].map(o=>o.textContent)")
    ok('받는 사람 = 친구·선생님', any('pcrecv1' in o and '친구' in o for o in opts) and any('pcteach1' in o for o in opts) and not any('pcother1' in o for o in opts), opts)
    ok('엽서 디자인 5종', qa.evaluate("document.querySelectorAll('.pc-dch').length") == 5)
    qa.click('.pc-dch[data-k="3"]'); time.sleep(.4)
    qa.select_option('#pc-to', 'pcrecv1'); qa.fill('#pc-in', '이번 달 책 같이 끝내자!'); time.sleep(.3)
    ok('미리보기: 보내는 사람 닉네임·에어메일·우표', qa.evaluate("(()=>{const p=document.querySelector('#pc-prev .pc');return p.classList.contains('pc-air')&&p.textContent.includes('pcsend1')&&p.textContent.includes('이번 달 책')&&!!p.querySelector('.pc-stamp')})()"))
    qa.click('.pc-go'); time.sleep(1.5)
    ok('보낸 엽서에 남고 배달 중·취소 가능', qa.evaluate("document.body.innerText.includes('pcrecv1에게')&&document.body.innerText.includes('배달 중')&&!!document.querySelector('[data-act=pccancel]')"))
    qa.click('[data-act=pcnew]'); time.sleep(.6); qa.select_option('#pc-to', 'pcsend1'); time.sleep(.3)
    ok('나에게: 받을 날짜 칸', qa.evaluate("!document.querySelector('.pc-day').hidden&&!!document.querySelector('#pc-day').value"))
    qa.fill('#pc-in', '한 달 뒤의 나에게, 잘 하고 있지?'); qa.click('.pc-go'); time.sleep(1.5)
    ok('나에게 보낸 엽서는 보낸 엽서함에 안 남음', qa.evaluate("!document.body.innerText.includes('한 달 뒤의 나에게')&&document.querySelectorAll('[data-act=pccancel]').length===1"))
    time.sleep(2)
    qb = page('pcrecv1')
    ok('받는 사람 엽서함에 새 엽서', qb.evaluate("document.body.innerText.includes('새 엽서')&&!!document.querySelector('.pc.seal')"))
    qb.click('.pc-row[data-act=pcopen]'); time.sleep(1.2)
    ok('열면 영원이북 우체국 소인과 내용', qb.evaluate("(()=>{const v=document.querySelector('#layer1 .pc-big');return !!v&&!!v.querySelector('.pc-mark')&&v.textContent.includes('이번 달 책 같이 끝내자')})()"))
    qa.reload(); qa.wait_for_selector('.who', timeout=15000); time.sleep(1.5)
    qa.evaluate("document.querySelector('nav.nav [data-v=friends]').click()"); time.sleep(2)
    qa.click('[data-act=frtab][data-v=post]'); time.sleep(.8)
    ok('엽서 아이콘 한 줄(쓰기·받은·보낸)', qa.evaluate("document.querySelectorAll('.pc-bar .pc-ic').length") == 3)
    qa.click('[data-act=pcbox][data-v=out]'); time.sleep(.5)
    ok('보낸 사람 화면: 읽음, 취소 버튼 없음', qa.evaluate("document.body.innerText.includes('상대가 읽었어요')&&!document.querySelector('[data-act=pccancel]')"))
    b.close()
print(f'{sum(res)}/{len(res)}')
sys.exit(0 if all(res) else 1)
