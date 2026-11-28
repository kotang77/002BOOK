"""기본 코스 영화의 국내 관람등급을 KMDb(한국영상자료원)에서 확인한다. 브랜치 ops-ratings에 push하면 Actions에서만 돈다."""
import json, os, re, urllib.parse, urllib.request
KEY = os.environ['KMDB_KEY']; SUM = os.environ.get('GITHUB_STEP_SUMMARY')
s = open('app/source.html', encoding='utf8').read()
i = s.index('const DEFAULT='); j = s.index('];', i) + 1
D = json.loads(s[i + len('const DEFAULT='):j])
norm = lambda t: re.sub(r'[^0-9A-Za-z가-힣]', '', re.sub(r'<[^>]*>|!H[SE]|\(.*?\)', '', str(t or ''))).lower()
EXTRA = {'알파: 위대한 여정': ('2018', 'alpha'), '루디 이야기': ('1993', 'rudy'), '러브레터': ('1995', 'loveletter')}
out = ['| 학년 | 달 | 칸 | 앱 제목 | 찾은 제목(제작연도·나라) | 관람등급 | 감독 | 포스터 |', '|---|---|---|---|---|---|---|---|']
def q(title):
    u = 'http://api.koreafilm.or.kr/openapi-data2/wisenut/search_api/search_json2.jsp?' + urllib.parse.urlencode({'collection': 'kmdb_new2', 'detail': 'Y', 'ServiceKey': KEY, 'title': title, 'listCount': '30'})
    with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': '002book-ops'}), timeout=30) as r:
        return (json.loads(r.read().decode('utf8')).get('Data') or [{}])[0].get('Result') or []
n = 0
for it in D:
    for k in ('m1', 'm2'):
        t = it.get(k) or ''
        if not t: continue
        inf = it.get(k + 'Info') or {}
        yr, en = str(inf.get('year') or ''), ''
        if t in EXTRA: yr, en = EXTRA[t]
        base = re.sub(r'\s*\(.*\)\s*$', '', t)
        try: rows = q(base); n += 1
        except Exception as e: out.append(f"| {it['g']} | {it['m']} | {k} | {t} | 오류 {e} | | | |"); continue
        def score(m):
            sc = 0; mt = norm(m.get('title')); y = int(m.get('prodYear') or 0)
            if mt == norm(base): sc += 10
            elif norm(base) in mt or mt in norm(base): sc += 4
            if en and en in norm(str(m.get('titleEng','')) + str(m.get('titleOrg',''))): sc += 8
            if yr and y and abs(y - int(yr)) <= 1: sc += 6
            elif yr and y: sc -= min(6, abs(y - int(yr)) // 3)
            if m.get('posters'): sc += 1
            return sc
        rows.sort(key=score, reverse=True)
        m = rows[0] if rows else None
        if not m: out.append(f"| {it['g']} | {it['m']} | {k} | {t} | 없음 | | | |"); continue
        rat = m.get('rating') or ''
        rr = ((m.get('ratings') or {}).get('rating') or [])
        grades = '·'.join(dict.fromkeys([x.get('ratingGrade', '') for x in rr if x.get('ratingGrade')])) or rat
        dirs = ','.join(d.get('directorNm', '') for d in ((m.get('directors') or {}).get('director') or [])[:2])
        post = 'O' if m.get('posters') else '-'
        ft = re.sub(r'!H[SE]', '', m.get('title', '')).strip()
        out.append(f"| {it['g']} | {it['m']} | {k} | {t} | {ft} ({m.get('prodYear','')}·{m.get('nation','')}) | {grades} | {dirs} | {post} |")
        if t in EXTRA:
            for x in rows[:6]:
                out.append(f"|  |  |  | ↳후보 | {re.sub(r'!H[SE]','',x.get('title','')).strip()} / {x.get('titleEng','')} ({x.get('prodYear','')}·{x.get('nation','')}) | {x.get('rating','')} | | {(x.get('posters') or '').split('|')[0]} |")
out.append(f'\nKMDb 호출 {n}번')
txt = '\n'.join(out); print(txt)
if SUM: open(SUM, 'a').write(txt + '\n')
