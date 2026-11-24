# 002BOOK — 002book.com

중학생을 위한 책·영화 인생교육과 논술 첨삭 서비스.

```
app/source.html          앱 원본 (유일한 원본. 여기서 직접 고친다)
scripts/build.mjs        빌드: 문법·위험 패턴 검사 + 그림 분리 + PWA + 아이콘 + 약관 → dist/
web/                     어댑터(runtime/claude-shim.js), 서비스워커, 약관·결제·가져오기 페이지
supabase/                DB 스키마, 서버 API(Edge Function 'api')
android/twa-manifest.json  구글 플레이 앱(TWA) 설정
tests/e2e.py             끝-끝 테스트: 가입·보호자 동의·비밀번호 찾기·탈퇴·권한
tests/oral/              구술 흐름·마이크 끊김·화면/그림/논술 PDF 연기 시험 (run.sh로 전부 실행)
```

## 앱을 고칠 때
`app/source.html`을 직접 고친 뒤 시험을 모두 통과하면 main에 올린다(올리면 바로 배포된다).

## 로컬 테스트
```
DENO=deno PDFLIB=<html2canvas·jspdf가 든 node_modules> tests/oral/run.sh      # 전부
tests/oral/run.sh ../e2e.py     # 하나만
```
가짜 서버(:8000, 생각 시간 25초)와 웹(:8080)을 띄우고 시험한다.

## 비밀값 (GitHub → Settings → Secrets and variables → Actions)
| 이름 | 종류 | 내용 |
|---|---|---|
| SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_PROJECT_REF | Variables | Supabase 프로젝트 정보 (공개돼도 되는 값) |
| SUPABASE_ACCESS_TOKEN, SUPABASE_DB_PASSWORD | Secrets | 서버 자동 배포용 |
| ANTHROPIC_API_KEY | Secret | AI 첨삭 |
| RESEND_API_KEY | Secret | 메일 발송 |
| TOSS_SECRET_KEY | Secret | 결제 승인 (클라이언트 키는 site.config.json) |
| NL_CERT_KEY | Secret | 국립중앙도서관 ISBN 서지정보 API 인증키 (nl.go.kr › Open API › 인증키 신청). 없으면 책 분야를 AI 추정으로만 정한다 |
| KAKAO_REST_KEY | Secret | 카카오 디벨로퍼스 REST API 키. 국립중앙도서관에 표지가 없을 때 다음 책 검색 표지를 쓴다 (선택) |
| TMDB_TOKEN | Secret | (사용 안 함, 2026-11-24 결정) TMDB API 읽기 토큰(v4). 상업 이용은 월 149달러 구독이라 보류. 넣으면 화면 하단에 TMDB 출처 문구·로고를 다시 넣어야 함 |
| KMDB_KEY | Secret | 한국영상자료원 KMDb Open API 키. 영화 포스터 기본 출처 |
| GOOGLE_CLIENT_ID | Variable | 구글 로그인 OAuth 클라이언트 ID (웹 애플리케이션 유형, 승인된 JavaScript 원본 https://002book.com, https://www.002book.com). 비우면 구글 버튼이 숨겨진다 |
| ANDROID_KEYSTORE_PASSWORD, ANDROID_KEYSTORE_B64 | Secrets | 플레이 앱 서명 |
| ANDROID_SHA256 | Variable | 앱 서명 지문(쉼표로 여러 개) → assetlinks.json |
