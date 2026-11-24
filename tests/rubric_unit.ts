// 구술 평가 영역 설정(config/rubric.oral) 검사와 가중 총점
import { RB_DEF, rbValid, rubric } from '../supabase/functions/api/oral.ts';
let bad = 0; const ok = (n: string, c: boolean) => { console.log((c ? 'PASS ' : 'FAIL ') + n); if (!c) bad++; };
const lv = { '질문 이해와 작품 활용': 3, '주장과 근거': 5, '구성': 3, '표현': 3, '전달': 3, '생각의 깊이': 3 };
ok('기본 영역: 70*0.7 + 100*0.3 = 79', rubric(lv).total === 79);
const cfg = RB_DEF.map((x) => ({ ...x })); cfg[1].w = 50; cfg[2].w = 5; cfg[5].w = 0;
ok('배점 0은 거절', rbValid(cfg) === null);
cfg[5].w = 5; cfg[0].w = 15; cfg[4].w = 15; cfg[3].w = 10;
ok('합계 100 아님 거절', rbValid(cfg.map((x, n) => n === 0 ? { ...x, w: 16 } : x)) === null);
const v = rbValid(cfg)!;
ok('바른 설정 통과', !!v && v.length === 6);
ok('바뀐 배점으로 총점: 70*0.5 + 100*0.5 = 85', rubric(lv, v).total === 85);
ok('이름 겹침 거절', rbValid(cfg.map((x, n) => n === 1 ? { ...x, k: cfg[0].k } : x)) === null);
ok('영역 5개 거절', rbValid(cfg.slice(0, 5)) === null);
const noHold = v.map((x) => ({ ...x, h: false }));
let threw = false; try { rubric({ ...lv, '전달': 0 }, noHold); } catch { threw = true; }
ok('보류 불가 영역이 비면 오류', threw);
ok('보류 가능 영역이 비면 빼고 계산', rubric({ ...lv, '전달': 0 }, v).held[0] === '전달');
if (bad) Deno.exit(1);
