"""운영 데이터 초기화(그랜드 오픈). GitHub Actions '운영 데이터 초기화'에서만 실행한다.
지우는 것: 회원 계정·세션·AI 사용량·결제 기록, 회원이 만든 모든 문서(진도·논술·구술·후기·친구·가족·엽서·사진 등),
          관리자 추가 목록·구글 연결, 업로드 사진(Storage 'uploads' 버킷).
남기는 것: 운영 설정(config/: 코스·평가 기준·요금·공지·영상), 작품 정보(info/), 학습지도 자료(guides/), 작품 표지(covers/, 2026-11-26 결정),
          표지·포스터·사진 검색 캐시(sys/art_·pic_·isbn_·bkt_), 알림 서명 키(sys/vapid).
MODE=check 는 개수만 보여 주고 아무것도 지우지 않는다. MODE=delete + CONFIRM=전체삭제 일 때만 지운다."""
import json, os, sys, urllib.request

REF = os.environ['REF']; TOKEN = os.environ['TOKEN']
MODE = os.environ.get('MODE', 'check'); CONFIRM = os.environ.get('CONFIRM', '')
KEEP = "(parent in ('config','info','guides','covers') or path = 'sys/vapid' or path ~ '^sys/(art|pic|isbn|bkt)_')"
SUM = os.environ.get('GITHUB_STEP_SUMMARY')

def call(url, body=None, headers=None, method=None):
    h = {'Content-Type': 'application/json', 'User-Agent': '002book-ops'}; h.update(headers or {})
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), headers=h, method=method or ('POST' if body is not None else 'GET'))
    with urllib.request.urlopen(req, timeout=60) as r:
        t = r.read().decode() or 'null'
        return json.loads(t)

def sql(q):
    return call(f'https://api.supabase.com/v1/projects/{REF}/database/query', {'query': q}, {'Authorization': f'Bearer {TOKEN}'})

def out(line):
    print(line)
    if SUM:
        with open(SUM, 'a') as f: f.write(line + '\n')

def counts(title):
    out(f'### {title}')
    r = sql(f"""select 'accounts' k, count(*) n from accounts union all select 'sessions', count(*) from sessions
      union all select 'ai_usage', count(*) from ai_usage union all select 'payments', count(*) from payments
      union all select 'docs 지울 것', count(*) from docs where not {KEEP} union all select 'docs 남길 것', count(*) from docs where {KEEP}""")
    for x in r: out(f"- {x['k']}: {x['n']}")
    r = sql(f"select parent, count(*) n from docs where not {KEEP} group by parent order by n desc")
    out('- 지울 문서 종류: ' + (', '.join(f"{x['parent']} {x['n']}" for x in r) or '없음'))
    r = sql("select count(*) n from storage.objects where bucket_id = 'uploads'")
    out(f"- 업로드 사진(Storage): {r[0]['n']}")

def service_key():
    ks = call(f'https://api.supabase.com/v1/projects/{REF}/api-keys?reveal=true', None, {'Authorization': f'Bearer {TOKEN}'})
    k = next((x for x in ks if x.get('name') == 'service_role' and x.get('api_key')), None) or next((x for x in ks if x.get('type') == 'secret' and x.get('api_key')), None)
    if not k: sys.exit('서비스 키를 가져오지 못했어요.')
    print('::add-mask::' + k['api_key'])
    return k['api_key']

def empty_bucket():
    key = service_key(); base = f'https://{REF}.supabase.co/storage/v1'
    H = {'Authorization': f'Bearer {key}', 'apikey': key}
    def files(prefix):
        got, off = [], 0
        while True:
            items = call(f'{base}/object/list/uploads', {'prefix': prefix, 'limit': 1000, 'offset': off}, H) or []
            for it in items:
                p = (prefix + '/' if prefix else '') + it['name']
                if it.get('id') is None: got += files(p)   # 폴더
                else: got.append(p)
            if len(items) < 1000: return got
            off += 1000
    all_files = files('')
    for i in range(0, len(all_files), 500):
        call(f'{base}/object/uploads', {'prefixes': all_files[i:i + 500]}, H, 'DELETE')
    out(f'- 지운 업로드 사진: {len(all_files)}')

counts('지우기 전' if MODE == 'delete' else '확인만 (아무것도 지우지 않음)')
if MODE != 'delete':
    sys.exit(0)
if CONFIRM != '전체삭제':
    sys.exit("확인 문구가 '전체삭제'가 아니라서 지우지 않았어요.")
sql(f"""begin;
  delete from sessions; delete from ai_usage; delete from payments; delete from accounts;
  delete from docs where not {KEEP};
commit;""")
empty_bucket()
counts('지운 뒤')
out('완료. 지금 바로 002book.com에서 관리자 아이디(kotang77)로 가입하세요.')
