"""배포 때 학습지도 자료(guides/lg2_*)를 웹사이트 묶음(dist/data/guides.json)으로 저장한다.
앱은 이 파일을 먼저 읽어 가입한 회원도 서버를 기다리지 않고 바로 자료를 본다(없는 달만 서버·AI).
REF·TOKEN이 없으면(로컬 빌드) 빈 묶음을 쓴다."""
import json, os, urllib.request
REF = os.environ.get('REF', ''); TOKEN = os.environ.get('TOKEN', '')
out = {}
if REF and TOKEN:
    q = "select id, data->'data' as d from docs where parent = 'guides' and id like 'lg2\\_%' and data ? 'data'"
    req = urllib.request.Request(f'https://api.supabase.com/v1/projects/{REF}/database/query', data=json.dumps({'query': q}).encode(),
        headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json', 'User-Agent': '002book-build'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=60) as r: rows = json.loads(r.read().decode() or '[]')
        for x in rows:
            d = x.get('d')
            if isinstance(d, str): d = json.loads(d)
            if isinstance(d, dict) and isinstance(d.get('works'), list): out[x['id']] = d
    except Exception as e: print('학습지도 묶음을 가져오지 못했어요(빈 묶음으로 계속):', e)
os.makedirs('dist/data', exist_ok=True)
with open('dist/data/guides.json', 'w') as f: json.dump({'at': __import__('time').time(), 'guides': out}, f, ensure_ascii=False, separators=(',', ':'))
print(f'학습지도 묶음 {len(out)}개 → dist/data/guides.json')
