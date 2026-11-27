"""배포 때 서버에 쌓인 자료를 웹사이트 묶음으로 함께 올린다(가입 즉시 보기용, 11-27).
- 학습 자료(guides/lg2_·pre_·edu_·w2b_·w2m_) → dist/data/guides.json
- 회원이 올린 책 표지(covers/, data URL) → dist/data/cv/<id>.jpg 파일 + 목록
- 자동으로 찾은 표지·포스터 주소(sys/art_* 서버 캐시) → 종류|제목 기준 주소표
  표지 목록과 주소표는 dist/data/art.json 하나로 묶는다.
앱은 묶음을 먼저 쓰고, 묶음에 없는 것만 서버·AI에 묻는다. REF·TOKEN이 없으면(로컬 빌드) 빈 묶음을 쓴다."""
import base64, hashlib, json, os, re, time, urllib.parse, urllib.request
REF = os.environ.get('REF', ''); TOKEN = os.environ.get('TOKEN', '')
def sql(q):
    req = urllib.request.Request(f'https://api.supabase.com/v1/projects/{REF}/database/query', data=json.dumps({'query': q}).encode(),
        headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json', 'User-Agent': '002book-build'}, method='POST')
    with urllib.request.urlopen(req, timeout=90) as r: return json.loads(r.read().decode() or '[]')
def norm(s):  # 서버 media.ts normT 와 같은 규칙
    s = re.sub(r'<[^>]*>|!H[SE]', '', str(s or '')); s = re.sub(r'\(.*?\)|\[.*?\]', '', s)
    return re.sub(r'[^0-9A-Za-z가-힣]', '', s).lower()
os.makedirs('dist/data/cv', exist_ok=True)
guides, covers, art = {}, {}, {}
if REF and TOKEN:
    try:
        # 학습지도(lg2_)·책 읽기 전 생각하기(pre_)·작품 깊이 읽기(edu_)·작품별 부모 안내서(w2b_·w2m_) — 11-28 일체로 넓힘
        for x in sql("select id, data->'data' as d from docs where parent = 'guides' and (id like 'lg2\\_%' or id like 'pre\\_%' or id like 'edu\\_%' or id like 'w2b\\_%' or id like 'w2m\\_%') and data ? 'data'"):
            d = x.get('d'); d = json.loads(d) if isinstance(d, str) else d
            if not isinstance(d, dict) or not d: continue
            if x['id'].startswith('lg2_') and not isinstance(d.get('works'), list): continue
            guides[x['id']] = d
    except Exception as e: print('학습지도를 가져오지 못했어요:', e)
    try:
        for x in sql("select id, data->>'img' as img from docs where parent = 'covers' and data ? 'img'"):
            m = re.match(r'^data:image/(jpeg|jpg|png|webp);base64,(.+)$', x.get('img') or '', re.S)
            if not m or not re.match(r'^[A-Za-z0-9_-]+$', x['id']): continue
            ext = 'jpg' if m.group(1) in ('jpeg', 'jpg') else m.group(1)
            raw = base64.b64decode(m.group(2))
            with open(f"dist/data/cv/{x['id']}.{ext}", 'wb') as f: f.write(raw)
            covers[x['id']] = f"data/cv/{x['id']}.{ext}?v={hashlib.sha256(raw).hexdigest()[:8]}"
    except Exception as e: print('올린 표지를 가져오지 못했어요:', e)
    try:
        # 연도를 정해 찾은 것(11-28~)은 '종류|제목|연도' 키로 따로 둔다(같은 제목의 다른 작품과 섞이지 않게). 앱의 ART_Q가 이 키를 읽음
        for x in sql("select data->>'kind' as k, data->>'title' as t, data->>'year' as y, data->>'url' as u from docs where path like 'sys/art\\_%' and coalesce(data->>'url','') <> ''"):
            u = x.get('u') or ''
            if not u.startswith('https://'): continue
            y = x.get('y') or ''
            art[('m' if x.get('k') == 'movie' else 'b') + '|' + norm(x.get('t')) + ('|' + y if y else '')] = u
    except Exception as e: print('표지·포스터 주소를 가져오지 못했어요:', e)
# 11-28 속도: 자동으로 찾은 표지·포스터 그림도 사이트 안(data/art/)에 내려받아 둔다. 같은 주소라 서비스 워커가 기기에 저장해
# 두 번째부터는 내려받지 않고, 외부 서버(영상자료원·카카오)가 느리거나 막혀도 보인다. Pillow가 있으면 긴 변 480px JPEG로 줄인다.
# 못 받은 그림은 원래 주소를 그대로 둔다
def big(u):  # 카카오 작은 썸네일 → 다음 원본(앱 bigCover와 같은 규칙)
    m = re.search(r'[?&]fname=([^&]+)', u)
    if not m: return u
    f = urllib.parse.unquote(m.group(1))
    return re.sub(r'^http:', 'https:', f) if re.match(r'^https?://[a-z0-9.-]*daumcdn\.net/', f, re.I) else u
if art:
    os.makedirs('dist/data/art', exist_ok=True)
    try:
        from PIL import Image; import io
    except Exception: Image = None
    got = 0
    for k, u in list(art.items()):
        for src in dict.fromkeys([big(u), u]):
            try:
                with urllib.request.urlopen(urllib.request.Request(src, headers={'User-Agent': 'Mozilla/5.0 002book-build'}), timeout=20) as r: raw = r.read()
                if len(raw) < 800: continue
                ext = 'jpg'
                if Image:
                    im = Image.open(io.BytesIO(raw)).convert('RGB'); im.thumbnail((480, 480)); b = io.BytesIO(); im.save(b, 'JPEG', quality=82, optimize=True); raw = b.getvalue()
                elif raw[:8].startswith(b'\x89PNG'): ext = 'png'
                elif raw[8:12] == b'WEBP': ext = 'webp'
                name = hashlib.sha256(k.encode()).hexdigest()[:16]
                with open(f'dist/data/art/{name}.{ext}', 'wb') as f: f.write(raw)
                art[k] = f"data/art/{name}.{ext}?v={hashlib.sha256(raw).hexdigest()[:8]}"; got += 1
                break
            except Exception as e: print('그림을 받지 못했어요:', k, str(e)[:80])
    print(f'표지·포스터 그림 {got}/{len(art)}개를 사이트 안에 저장')
with open('dist/data/guides.json', 'w') as f: json.dump({'at': time.time(), 'guides': guides}, f, ensure_ascii=False, separators=(',', ':'))
with open('dist/data/art.json', 'w') as f: json.dump({'at': time.time(), 'covers': covers, 'art': art}, f, ensure_ascii=False, separators=(',', ':'))
print(f'묶음: 학습지도 {len(guides)} · 올린 표지 {len(covers)} · 표지·포스터 주소 {len(art)}')
# 정기 새로 고침(LIVE=사이트 주소): 지금 사이트의 묶음과 같으면 다시 올리지 않는다
LIVE = os.environ.get('LIVE', ''); changed = True
if LIVE:
    def live(name):
        try:
            with urllib.request.urlopen(urllib.request.Request(f'{LIVE}/data/{name}?t={int(time.time())}', headers={'User-Agent': '002book-build'}), timeout=30) as r: return json.loads(r.read().decode())
        except Exception: return None
    g, a = live('guides.json'), live('art.json')
    changed = not (g and a and g.get('guides') == guides and a.get('covers') == covers and a.get('art') == art)
    print('지금 사이트와 ' + ('달라요 → 새로 올려요' if changed else '같아요 → 올리지 않아요'))
if os.environ.get('GITHUB_OUTPUT'):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f: f.write(f"changed={'true' if changed else 'false'}\n")
