# 002BOOK — 002book.com

중학생을 위한 책·영화 인생교육과 논술 첨삭 서비스.

```
app/source.html          원본 앱 (Claude 게시본에서 내보낸 그대로)
scripts/patches.mjs      원본 → 002book.com 패치 목록 (로그인·비밀번호·가입·결제)
scripts/build.mjs        빌드: 패치 적용 + PWA + 아이콘 + 약관 → dist/
web/                     어댑터(runtime/claude-shim.js), 서비스워커, 약관·결제·가져오기 페이지
supabase/                DB 스키마, 서버 API(Edge Function 'api')
android/twa-manifest.json  구글 플레이 앱(TWA) 설정
tests/e2e.py             끝-끝 테스트 (가짜 DB로 실행)
```

## 앱을 고칠 때
Claude 게시본에서 앱을 고친 뒤 '002book.com 이전용 내보내기'로 새 파일을 받아
`app/source.html`을 바꾸면 된다. `node scripts/build.mjs`가 패치가 맞지 않는 곳을 알려 준다.

## 로컬 테스트
```
FAKE_DB=1 FAKE_MAIL=1 FAKE_AI='{"msg":"hi"}' deno run -A supabase/functions/api/index.ts   # :8000
SUPABASE_URL=http://localhost:8000 node scripts/build.mjs && (cd dist && python3 -m http.server 8080)
python3 tests/e2e.py <내보내기 파일(비밀번호 testpass1234로 바꾼 테스트용)>
```

## 비밀값 (GitHub → Settings → Secrets and variables → Actions)
| 이름 | 종류 | 내용 |
|---|---|---|
| SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_PROJECT_REF | Variables | Supabase 프로젝트 정보 (공개돼도 되는 값) |
| SUPABASE_ACCESS_TOKEN, SUPABASE_DB_PASSWORD | Secrets | 서버 자동 배포용 |
| ANTHROPIC_API_KEY | Secret | AI 첨삭 |
| RESEND_API_KEY | Secret | 메일 발송 |
| TOSS_SECRET_KEY | Secret | 결제 승인 (클라이언트 키는 site.config.json) |
| ANDROID_KEYSTORE_PASSWORD, ANDROID_KEYSTORE_B64 | Secrets | 플레이 앱 서명 |
| ANDROID_SHA256 | Variable | 앱 서명 지문(쉼표로 여러 개) → assetlinks.json |
