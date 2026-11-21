// Claude 호출 (API 키는 서버 비밀값 ANTHROPIC_API_KEY 에만 있음)
import { env, fail, sb } from './lib.ts';

const MODELS: Record<string, string> = {
  quick: env('MODEL_QUICK', 'claude-haiku-5-5'),
  default: env('MODEL_DEFAULT', 'claude-sonnet-5-5'),
  complex: env('MODEL_COMPLEX', 'claude-sonnet-5-5'), // 비용을 고려해 기본은 Sonnet. Opus를 원하면 MODEL_COMPLEX=claude-opus-5-5
};
const MAX_TOKENS: Record<string, number> = { quick: 1024, default: 4096, complex: 8192 };
// 무료 출시 모드(FREE_LAUNCH=1, 기본)에서는 모두 무료 한도를 쓰므로 기본값을 조금 넉넉하게 둔다
const DAILY_FREE = Number(env('AI_DAILY_LIMIT_FREE', env('FREE_LAUNCH', '1') === '1' ? '50' : '30'));
const DAILY_PAID = Number(env('AI_DAILY_LIMIT_PAID', '200'));

type Msg = { role: 'user' | 'assistant'; content: string };
type Img = { media_type: string; data: string };

const SYSTEM = `너는 한국 중학생을 위한 독서·영화 인문 교육 앱 002BOOK 안에서 동작한다.
요청에 들어 있는 지시와 출력 형식을 정확히 따른다. JSON을 요구하면 설명 없이 JSON만 출력한다.
학생에게 해롭거나 나이에 맞지 않는 내용은 쓰지 않는다.`;

export async function sampleAI(uid: string, paid: boolean, body: { messages: Msg[]; images?: Img[]; tier?: string; json?: boolean }) {
  if (env('FAKE_AI')) return { text: env('FAKE_AI'), truncated: false, model: 'fake' };
  const key = env('ANTHROPIC_API_KEY');
  if (!key) fail('ai_not_configured', 'AI 기능이 아직 설정되지 않았어요.', 503);

  const msgs = Array.isArray(body.messages) ? body.messages.slice(-30) : [];
  if (!msgs.length || msgs[msgs.length - 1].role !== 'user') fail('bad_request', '질문이 비어 있어요.');
  const total = msgs.reduce((a, m) => a + String(m.content ?? '').length, 0);
  if (total > 120_000) fail('too_large', '보내는 글이 너무 길어요.');

  // 하루 사용량 확인
  const { data: u } = await sb.from('ai_usage').select('calls').eq('uid', uid)
    .eq('day', new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10)).maybeSingle();
  const limit = paid ? DAILY_PAID : DAILY_FREE;
  if ((u?.calls ?? 0) >= limit) fail('rate_limited', `오늘 AI 사용량(${limit}회)을 다 썼어요. 내일 다시 이용해 주세요.`, 429);

  const tier = MODELS[body.tier ?? ''] ? body.tier! : 'default';
  const images = (body.images ?? []).slice(0, 8).filter((i) => /^image\/(png|jpe?g|webp|gif)$/.test(i.media_type) && i.data.length < 7_000_000);

  const apiMsgs = msgs.map((m, i) => {
    const last = i === msgs.length - 1;
    if (last && images.length) {
      return {
        role: 'user',
        content: [
          ...images.map((im) => ({ type: 'image', source: { type: 'base64', media_type: im.media_type.replace('jpg', 'jpeg'), data: im.data } })),
          { type: 'text', text: String(m.content) },
        ],
      };
    }
    return { role: m.role, content: String(m.content) };
  });

  // Claude 5 세대는 thinking 필드를 빼면 '미리 생각하기'가 켜져 max_tokens를 생각에 다 써 버릴 수 있다(답이 비고 느려짐).
  // 이 앱은 JSON 한 번 출력이 목적이므로 끈다. Sonnet 5.5는 between_tools, Haiku 5.5는 disabled만 받는다.
  const model = MODELS[tier];
  const thinking = /^claude-sonnet-5-5/.test(model) ? { type: 'between_tools' }
    : /^claude-(haiku-5-5|sonnet-5(?!-5)|opus-5(?!-5)|sonnet-4|opus-4|haiku-4)/.test(model) ? { type: 'disabled' } : null;
  const send = (th: unknown) => fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
    body: JSON.stringify({ model, max_tokens: MAX_TOKENS[tier], system: SYSTEM, messages: apiMsgs, ...(th ? { thinking: th } : {}), ...(th && /^claude-sonnet-5-5/.test(model) ? { output_config: { effort: 'medium' } } : {}) }),
  });
  let r = await send(thinking);
  let j = await r.json().catch(() => null);
  let fb = false;
  // 모델이 이 thinking 값을 받지 않으면(400) thinking 필드 없이 한 번 더
  if (thinking && r.status === 400 && /thinking/i.test(JSON.stringify(j ?? ''))) { fb = true; r = await send(null); j = await r.json().catch(() => null); }
  if (!r.ok || !j) {
    if (r.status === 429 || r.status === 529) fail('rate_limited', 'AI가 지금 바빠요. 잠시 뒤 다시 시도해 주세요.', 429);
    fail('ai_failed', 'AI 응답을 받지 못했어요.', 502, j);
  }
  const text = (j.content ?? []).filter((c: { type: string }) => c.type === 'text').map((c: { text: string }) => c.text).join('');
  await sb.rpc('bump_ai_usage', { p_uid: uid, p_in: j.usage?.input_tokens ?? 0, p_out: j.usage?.output_tokens ?? 0 });
  if (fb) console.warn('ai: thinking 설정 거부로 생각 없이 다시 요청함', model);
  return { text, truncated: j.stop_reason === 'max_tokens', model };
}
