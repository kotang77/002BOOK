"""운영 계획표(config/course)의 작품 바꾸기. GitHub Actions '코스 작품 바꾸기'에서만 실행한다.
scripts/ops/course_fixes.json 의 from(옛 제목들) → to(새 제목)으로 바꾸고 작품 정보(m1Info·m2Info)를 새로 넣는다.
config/course가 없으면(=앱의 기본 계획표 DEFAULT를 쓰는 중) 아무것도 하지 않는다. MODE=check 는 바꿀 곳만 보여 준다."""
import json, os
REF = os.environ['REF']; TOKEN = os.environ['TOKEN']; MODE = os.environ.get('MODE', 'check'); SUM = os.environ.get('GITHUB_STEP_SUMMARY')
import urllib.request
def sql(q):
    req = urllib.request.Request(f'https://api.supabase.com/v1/projects/{REF}/database/query', data=json.dumps({'query': q}).encode(),
        headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json', 'User-Agent': '002book-ops'}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode() or 'null')
def out(line):
    print(line)
    if SUM:
        with open(SUM, 'a') as f: f.write(line + '\n')
FIX = json.load(open(os.path.join(os.path.dirname(__file__), 'course_fixes.json')))
rows = sql("select data from docs where path = 'config/course'")
if not rows:
    out('config/course 없음 → 앱 기본 계획표를 쓰는 중이라 바꿀 것이 없어요(기본 계획표는 코드에서 바뀜).'); raise SystemExit
data = rows[0]['data']; items = data.get('items') or []; n = 0
for it in items:
    for k in ('m1', 'm2'):
        f = next((f for f in FIX if it.get(k) in f['from']), None)
        if f and (it.get(k) != f['to'] or it.get(k + 'Info') != f['info']):
            out(f"- {it.get('g')} {it.get('m')} {k}: {it.get(k)} → {f['to']}"); it[k] = f['to']; it[k + 'Info'] = f['info']; n += 1
if not n: out('바꿀 작품이 없어요.'); raise SystemExit
if MODE != 'apply': out(f'(확인만) {n}곳'); raise SystemExit
lit = json.dumps(data, ensure_ascii=False).replace("'", "''")
sql(f"update docs set data = '{lit}'::jsonb, version = version + 1, updated_at = now() where path = 'config/course'")
out(f'{n}곳 바꿈')
