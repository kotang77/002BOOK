// 토스페이먼츠 결제 (1회 결제 이용권 방식: 결제하면 정해진 기간 동안 유료회원)
// 정기결제(자동 갱신)는 토스페이먼츠와 '빌링' 계약이 따로 필요해서 1차 출시에서는 쓰지 않는다.
import { env, fail, sb, sha256hex } from './lib.ts';

type Plan = { name: string; amount: number; days: number };
const PLANS: Record<string, Plan> = JSON.parse(env('PLANS_JSON', JSON.stringify({
  month1: { name: '002BOOK 유료회원 1개월', amount: 9900, days: 31 },
  month6: { name: '002BOOK 유료회원 6개월', amount: 49000, days: 183 },
})));

export function payPlans() {
  return Object.entries(PLANS).map(([id, p]) => ({ id, ...p }));
}

export async function payReady(uid: string, plan: string) {
  const p = PLANS[plan];
  if (!p) fail('bad_plan', '없는 이용권이에요.');
  const orderId = `002b_${Date.now().toString(36)}_${crypto.randomUUID().slice(0, 8)}`;
  const { error } = await sb.from('payments').insert({ order_id: orderId, uid, plan, amount: p.amount, status: 'READY' });
  if (error) fail('db_error', '주문을 만들지 못했어요.', 500, error.message);
  return { orderId, amount: p.amount, orderName: p.name, customerKey: 'c_' + (await sha256hex('002book:' + uid)).slice(0, 40) };
}

export async function payConfirm(
  uid: string,
  b: { paymentKey: string; orderId: string; amount: number },
  markPaid: (until: number, orderId: string) => Promise<void>,
) {
  const secret = env('TOSS_SECRET_KEY');
  if (!secret) fail('pay_not_configured', '결제가 아직 설정되지 않았어요.', 503);
  const { data: order } = await sb.from('payments').select('*').eq('order_id', String(b.orderId)).maybeSingle();
  if (!order || order.uid !== uid) fail('bad_order', '주문을 찾지 못했어요.', 404);
  if (order.status === 'DONE') return { ok: true, until: order.paid_until, already: true };
  if (Number(b.amount) !== order.amount) {           // 금액 위변조 방지
    await sb.from('payments').update({ status: 'FAILED', raw: { reason: 'amount_mismatch', got: b.amount } }).eq('order_id', order.order_id);
    fail('amount_mismatch', '결제 금액이 맞지 않아요.');
  }
  const r = await fetch('https://api.tosspayments.com/v1/payments/confirm', {
    method: 'POST',
    headers: { authorization: 'Basic ' + btoa(secret + ':'), 'content-type': 'application/json', 'idempotency-key': order.order_id },
    body: JSON.stringify({ paymentKey: b.paymentKey, orderId: order.order_id, amount: order.amount }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.status !== 'DONE') {
    await sb.from('payments').update({ status: 'FAILED', raw: j, updated_at: new Date().toISOString() }).eq('order_id', order.order_id);
    fail('pay_failed', j.message || '결제를 승인하지 못했어요.', 400);
  }
  // 이미 유료 기간이 남아 있으면 그 뒤로 이어 붙인다
  const { data: last } = await sb.from('payments').select('paid_until').eq('uid', uid).eq('status', 'DONE').order('paid_until', { ascending: false }).limit(1).maybeSingle();
  const base = Math.max(Date.now(), last?.paid_until ? new Date(last.paid_until).getTime() : 0);
  const until = base + PLANS[order.plan].days * 864e5;
  await sb.from('payments').update({ status: 'DONE', payment_key: b.paymentKey, paid_until: new Date(until).toISOString(), raw: j, updated_at: new Date().toISOString() }).eq('order_id', order.order_id);
  await markPaid(until, order.order_id);
  return { ok: true, until };
}
