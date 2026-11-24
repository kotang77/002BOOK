"""손글씨 폰트 양식 (A4, 칸 쓰기 + 문장 쓰기). 선생님·남학생·여학생 3종"""
import json, unicodedata

def uniq(seq):
    out, seen = [], set()
    for c in seq:
        if c.strip() and c not in seen:
            seen.add(c); out.append(c)
    return out

# 1. 받침 없음 · 세로 모음(ㅏ ㅓ ㅣ ㅐ ㅔ ㅑ ㅕ)
A = list("가까나다따라마바빠사싸아자짜차카타파하") + list("거너더러머버서어저처커터퍼허") + list("기니디리미비시이지치키티피히") + list("개내대래매배새애재채캐태패해") + list("게네데레메베세에제체케테페헤") + list("갸냐댜랴먀뱌샤야쟈챠캬탸퍄햐") + list("겨녀뎌려며벼셔여져쳐켜텨펴혀")
# 2. 받침 없음 · 가로 모음(ㅗ ㅜ ㅡ ㅛ ㅠ)
B = list("고꼬노도또로모보뽀소쏘오조쪼초코토포호") + list("구꾸누두뚜루무부뿌수쑤우주쭈추쿠투푸후") + list("그끄느드뜨르므브쁘스쓰으즈쯔츠크트프흐") + list("교뇨됴료묘뵤쇼요죠쵸쿄툐표효") + list("규뉴듀류뮤뷰슈유쥬츄큐튜퓨휴")
# 3. 섞인 모음(ㅘ ㅙ ㅚ ㅝ ㅞ ㅟ ㅢ)
C = list("과놔돠롸뫄봐솨와좌촤콰톼퐈화") + list("괘왜쇄좨쾌홰") + list("괴뇌되뢰뫼뵈쇠외죄최쾨퇴푀회") + list("궈눠둬뤄뭐붜숴워줘춰쿼퉈풔훠") + list("궤웨줴췌퀘훼") + list("귀뉘뒤뤼뮈뷔쉬위쥐취퀴튀퓌휘") + list("긔늬듸릐믜븨싀의즤츼킈틔픠희")
# 4. 받침 27가지 (세로 모음 위 · 가로 모음 위 · 섞인 모음 위)
D = list("각갂갃간갅갆갇갈갉갊갋갌갍갎갏감갑값갓갔강갖갗갘같갚갛") + list("곡곢곣곤곥곦곧골곩곪곫곬곭곮곯곰곱곲곳곴공곶곷곸곹곺곻") + list("괵괸괼굄굅굇굉") + list("귁귄귈귐귑귓귕") + list("의읜읠읨읩읫읭")
# 5. 자주 쓰는 글자(문장 속 모양 확인용)
E = list("이다는의에하고을가지기로서리사어한나도대자일시정인수들그적아게만것해전으상주장니부우있라화국과와소제성동비원보생여문연년신학히마조공되경실위했무내중미개요관계방회물면법행거결영각산금말오업진체않없었던할점함음것들책영화논술구술글씨생각마음친구선생님학생엄마아빠")
# 영문·숫자·기호
F = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + list("abcdefghijklmnopqrstuvwxyz") + list("0123456789") + list(".,?!'\"()~-:;/%·…「」『』[]+=<>@#&*")

groups = [("1. 받침 없는 글자 · 세로 모음", uniq(A)), ("2. 받침 없는 글자 · 가로 모음", uniq(B)),
          ("3. 섞인 모음", uniq(C)), ("4. 받침 있는 글자", uniq(D))]
seen = set(c for _, g in groups for c in g)
groups.append(("5. 자주 쓰는 글자", [c for c in uniq(E) if c not in seen]))
groups.append(("6. 영문 · 숫자 · 기호", uniq(F)))

SENT = ["다람쥐 헌 쳇바퀴에 타고파.", "정말 큰 꿈을 품은 학생들이 책을 읽고 생각을 글로 씁니다.",
        "한 달에 책 한 권, 영화 두 편, 글 세 편.", "꿈이 이루어지는 곳이 천국이다.",
        "The quick brown fox jumps over the lazy dog. 0123456789"]

COLS = 10
# 높이(mm)로 쪽을 나눈다: 쓸 수 있는 높이, 첫 쪽은 안내 상자만큼 덜 씀
AVAIL, TIPH, ROWH, HDRH = 251, 21, 20.6, 4.6
pages = []; cur = []; used = TIPH
for title, g in groups:
    rows = [g[i:i + COLS] for i in range(0, len(g), COLS)]
    for n, row in enumerate(rows):
        need = ROWH + (HDRH if n == 0 or not cur else 0)
        if used + need > AVAIL:
            pages.append(cur); cur = []; used = 0; need = ROWH + HDRH
        hdr = title if (n == 0 or not cur) else None
        if hdr and n > 0: hdr = title + ' (이어서)'
        cur.append((hdr, row)); used += need
pages.append(cur)
TOTAL = len(pages) + 1
nhan = sum(len(g) for t, g in groups if not t.startswith('6'))
print('hangul', nhan, 'other', len(groups[-1][1]), 'pages', TOTAL)

WHO = [("선생님", "T", "#2F6FB5"), ("남학생", "M", "#2F8F7A"), ("여학생", "F", "#D9822B")]

CSS = """
@page{size:A4;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Noto Sans CJK KR','Noto Sans KR',sans-serif;color:#222}
.pg{position:relative;width:210mm;height:297mm;padding:12mm 13mm 10mm;page-break-after:always;overflow:hidden}
.reg{position:absolute;width:7mm;height:7mm;background:#000}
.r1{left:5mm;top:5mm}.r2{right:5mm;top:5mm}.r3{left:5mm;bottom:5mm}.r4{right:5mm;bottom:5mm}
.hd{display:flex;align-items:center;justify-content:space-between;margin:0 6mm 3mm}
.hd h1{font-size:15pt;font-weight:700}
.hd h1 small{font-size:9pt;font-weight:400;color:#666;margin-left:6px}
.who{display:flex;align-items:center;gap:6px;font-size:11pt;font-weight:700}
.who b{display:inline-flex;align-items:center;justify-content:center;width:9mm;height:9mm;border-radius:50%;color:#fff;font-size:13pt}
.tip{margin:0 6mm 3mm;font-size:8.6pt;line-height:1.5;color:#444;border:0.3mm solid #ccc;border-radius:2mm;padding:2mm 3mm}
.tip b{color:#000}
.grid{display:grid;grid-template-columns:repeat(10,17mm);justify-content:center;row-gap:1.6mm}
.cell{width:17mm}
.lb{height:3.4mm;font-size:7.2pt;line-height:3.4mm;color:#888;padding-left:0.6mm;white-space:nowrap;overflow:hidden}
.lb i{font-style:normal;color:#bbb;margin-left:1mm;font-size:5.5pt}
.bx{position:relative;width:17mm;height:17mm;border:0.25mm solid #9aa;margin-left:-0.25mm}
.bx:before{content:"";position:absolute;left:50%;top:1.5mm;bottom:1.5mm;border-left:0.15mm dashed #dde}
.bx:after{content:"";position:absolute;top:50%;left:1.5mm;right:1.5mm;border-top:0.15mm dashed #dde}
.gt{grid-column:1/-1;font-size:8.4pt;font-weight:700;color:#555;margin:1mm 0 -0.6mm 0.4mm}
.ft{position:absolute;left:14mm;right:14mm;bottom:6mm;display:flex;justify-content:space-between;font-size:8pt;color:#777}
.id{font-family:monospace;font-size:9pt;color:#000;letter-spacing:.1em}
.sent{margin:2mm 6mm 0}
.sent .ex{font-size:9pt;color:#777;margin:4mm 0 1mm}
.ln{height:15mm;border-bottom:0.3mm solid #9aa;position:relative}
.ln:after{content:"";position:absolute;left:0;right:0;top:50%;border-top:0.15mm dashed #dde}
.free{margin:4mm 6mm 0}
.free h2{font-size:10pt;margin-bottom:1mm}
"""

def page_cells(pcells, pno, who):
    name, code, color = who
    h = [f'<section class="pg">{reg()}{head(pno, who)}']
    if pno == 1:
        h.append('''<div class="tip"><b>쓰는 법</b> · 검은색 사인펜이나 0.5~0.7mm 볼펜으로, 칸 크기의 80% 정도로 <b>평소 글씨 그대로</b> 써 주세요. 칸 위의 작은 회색 글자를 칸 안에 한 번씩 씁니다.
 틀리면 두 줄로 긋고 칸 바로 아래 여백에 다시 써요. 지우개·수정 테이프는 괜찮아요.<br>
<b>찍는 법</b> · 밝은 곳에서 그림자 없이, 종이 바로 위에서 <b>네 모서리의 검은 사각형이 모두 보이게</b> 한 장씩 찍어 주세요. 구겨지거나 접히지 않게 평평하게 두면 좋아요.</div>''')
    h.append('<div class="grid">')
    for hdr, row in pcells:
        if hdr: h.append(f'<div class="gt">{hdr}</div>')
        for c in row:
            cp = 'U+%04X' % ord(c)
            disp = c.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
            h.append(f'<div class="cell"><div class="lb">{disp}<i>{cp}</i></div><div class="bx"></div></div>')
    h.append('</div>')
    h.append(foot(pno, who) + '</section>')
    return ''.join(h)

def reg():
    return '<i class="reg r1"></i><i class="reg r2"></i><i class="reg r3"></i><i class="reg r4"></i>'

def head(pno, who):
    name, code, color = who
    return f'<div class="hd"><h1>영원이북 손글씨 폰트 양식<small>{pno} / {TOTAL}쪽</small></h1><div class="who">글씨 주인 <b style="background:{color}">{code}</b>{name}</div></div>'

def foot(pno, who):
    return f'<div class="ft"><span>이름(또는 별명): ______________ · 쓴 날짜: ______</span><span class="id">YW-FONT-{who[1]}-P{pno:02d}</span></div>'

def page_sent(pno, who):
    h = [f'<section class="pg">{reg()}{head(pno, who)}<div class="sent">']
    for s in SENT:
        h.append(f'<p class="ex">{s}</p><div class="ln"></div>')
    h.append('</div><div class="free"><h2>자유롭게 한 문장 (글씨 느낌 확인용)</h2><div class="ln"></div><div class="ln"></div><div class="ln"></div></div>')
    h.append(foot(pno, who) + '</section>')
    return ''.join(h)

for who in WHO:
    body = ''.join(page_cells(p, n + 1, who) for n, p in enumerate(pages)) + page_sent(TOTAL, who)
    html = f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{body}</body></html>'
    open(f'/home/claude/fonttpl/tpl_{who[1]}.html', 'w', encoding='utf-8').write(html)
# 글자 목록(복원용)
json.dump({'pages': [[r for _, r in p] for p in pages], 'cols': COLS, 'sentences': SENT},
          open('/home/claude/fonttpl/layout.json', 'w', encoding='utf-8'), ensure_ascii=False)
