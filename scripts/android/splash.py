"""앱 시작 화면(스플래시) 교체 (2026-11-27 사용자 지시, Figma 16 '앱 시작 화면').
Bubblewrap이 만든 res/drawable*/splash.png(아이콘만 있는 정사각형)를 android/splash/splash-master.png
(흰 바탕 · 아이콘을 예전보다 3% 작게 · 아래에 002BOOK)로 바꾼다. 각 파일의 가로 크기를 그대로 지켜 밀도별 크기가 맞게 한다."""
import glob, sys
from PIL import Image
m = Image.open('splash/splash-master.png').convert('RGB')
files = glob.glob('app/src/main/res/drawable*/splash.png')
if not files: sys.exit('splash.png를 찾지 못했어요(Bubblewrap 프로젝트 구조가 바뀌었는지 확인).')
for f in files:
    w = Image.open(f).width
    m.resize((w, round(w * m.height / m.width)), Image.LANCZOS).save(f, optimize=True)
    print('교체', f, w)
