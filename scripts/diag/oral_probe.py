import os, secrets
"""운영 서버에서 구술 1차 평가와 같은 크기의 AI 요청을 보내 시간과 오류를 잰다. 끝나면 테스트 계정을 지운다."""
import json, time, urllib.request, threading, sys
API = 'https://' + os.environ['REF'] + '.supabase.co/functions/v1/api'
ANON = 'sb_publishable_gostrwsJINSvsAuY8YD2ag_fMfErcfA'
UID, PW = 'zzdiag' + secrets.token_hex(3), 'Dg!' + secrets.token_hex(8)


def api(op, tok=None, timeout=400, **kw):
    h = {'content-type': 'application/json', 'apikey': ANON, 'authorization': 'Bearer ' + ANON, 'origin': 'https://002book.com'}
    if tok: h['x-session'] = tok
    r = urllib.request.Request(API, data=json.dumps({'op': op, **kw}).encode(), headers=h, method='POST')
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(r, timeout=timeout); body = resp.read(); st = resp.status
    except urllib.error.HTTPError as e:
        body = e.read(); st = e.code
    except Exception as e:
        return {'status': 'EXC', 'err': repr(e)[:200], 'sec': round(time.time() - t0, 1)}
    try: j = json.loads(body)
    except Exception: j = {'raw': body[:300].decode('utf-8', 'replace')}
    j['status'] = st; j['sec'] = round(time.time() - t0, 1)
    return j


def short(r):
    if 'result' in r:
        t = r['result'].get('text', '') if isinstance(r['result'], dict) else ''
        R = r['result'] if isinstance(r['result'], dict) else {}
        return f"OK {r['status']} {r['sec']}s len={len(t)} trunc={R.get('truncated')} out={R.get('out')} thinkBlocks={R.get('think')} fallback={R.get('fb')}"
    return f"ERR {r.get('status')} {r.get('sec')}s {json.dumps(r.get('error') or r.get('raw') or r.get('err'), ensure_ascii=False)[:300]}"


mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
r = api('auth.login', id=UID, pw=PW)
if 'result' not in r:
    r = api('auth.signup', id=UID, pw=PW, email=UID + '@example.com', agreeTerms=True, agreePrivacy=True, birth='1990-01', grade='기타', nick='probe', gender='남')
print('session:', short(r) if 'result' not in r else 'ok')
tok = r['result']['session']['token']

prompts = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompts.json')))
if mode in ('all', 'parallel'):
    out = [None] * len(prompts)
    def run(k): out[k] = api('ai.sample', tok, messages=[{'role': 'user', 'content': prompts[k]}], tier='complex', json=True)
    t0 = time.time(); th = [threading.Thread(target=run, args=(k,)) for k in range(len(prompts))]
    [t.start() for t in th]; [t.join() for t in th]
    print(f'parallel x{len(prompts)} total {time.time()-t0:.1f}s')
    for k, o in enumerate(out): print(' ', k, short(o))
if mode in ('all', 'single'):
    print('single main:', short(api('ai.sample', tok, messages=[{'role': 'user', 'content': prompts[0]}], tier='complex', json=True)))
if mode in ('all', 'cleanup'):
    print('withdraw:', short(api('auth.withdraw', tok, pw=PW)))
