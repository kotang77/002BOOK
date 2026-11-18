// 테스트용 메모리 DB: api 함수가 쓰는 supabase-js 기능만 흉내 낸다
type R = Record<string, unknown>;
const T: Record<string, R[]> = { docs: [], accounts: [], sessions: [], ai_usage: [], payments: [] };
const PK: Record<string, string[]> = { docs: ['path'], accounts: ['id'], sessions: ['token_hash'], ai_usage: ['uid', 'day'], payments: ['order_id'] };

function get(r: R, col: string): unknown {
  const m = col.match(/^(\w+)->>?(\w+)$/);
  if (m) { const o = r[m[1]] as R | null; const v = o ? o[m[2]] : undefined; return col.includes('->>') ? (v == null ? null : typeof v === 'object' ? JSON.stringify(v) : String(v)) : v; }
  return r[col];
}
const likeRe = (p: string, ci = false) => new RegExp('^' + p.replace(/\\_/g, '\u0001').replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/%/g, '.*').replace(/_/g, '.').replace(/\u0001/g, '_') + '$', ci ? 'i' : '');

class Q {
  filters: ((r: R) => boolean)[] = []; mode = 'select'; payload: R | R[] | null = null; one = 0; lim = 0; ord: [string, boolean] | null = null;
  constructor(public t: string) {}
  select() { return this; }
  insert(p: R | R[]) { this.mode = 'insert'; this.payload = p; return this; }
  upsert(p: R | R[]) { this.mode = 'upsert'; this.payload = p; return this; }
  update(p: R) { this.mode = 'update'; this.payload = p; return this; }
  delete() { this.mode = 'delete'; return this; }
  eq(c: string, v: unknown) { this.filters.push((r) => get(r, c) === v || (typeof v !== 'object' && String(get(r, c)) === String(v) && get(r, c) != null)); return this; }
  in(c: string, vs: unknown[]) { this.filters.push((r) => vs.includes(get(r, c))); return this; }
  like(c: string, p: string) { const re = likeRe(p); this.filters.push((r) => re.test(String(get(r, c) ?? ''))); return this; }
  ilike(c: string, p: string) { const re = likeRe(p, true); this.filters.push((r) => re.test(String(get(r, c) ?? ''))); return this; }
  or(s: string) {
    const parts = s.split(',').map((x) => { const m = x.match(/^(.+)\.eq\.(.*)$/)!; return [m[1], m[2]]; });
    this.filters.push((r) => parts.some(([c, v]) => get(r, c) === v)); return this;
  }
  order(c: string, o?: { ascending?: boolean }) { this.ord = [c, o?.ascending !== false]; return this; }
  limit(n: number) { this.lim = n; return this; }
  maybeSingle() { this.one = 1; return this; }
  single() { this.one = 2; return this; }
  then(res: (v: unknown) => void, rej?: (e: unknown) => void) { try { res(this.run()); } catch (e) { rej?.(e); } }
  run() {
    const tab = T[this.t]; const match = (r: R) => this.filters.every((f) => f(r));
    const key = (r: R) => PK[this.t].map((k) => r[k]).join('|');
    if (this.mode === 'insert' || this.mode === 'upsert') {
      for (const p of ([] as R[]).concat(this.payload as R)) {
        const row = structuredClone(p); const i = tab.findIndex((r) => key(r) === key(row));
        if (i >= 0 && this.mode === 'insert') return { data: null, error: { message: 'duplicate' } };
        if (this.t === 'accounts' && this.mode === 'insert' && row.email && tab.some((r) => String(r.email ?? '').toLowerCase() === String(row.email).toLowerCase())) return { data: null, error: { message: 'dup email' } };
        if (i >= 0) tab[i] = { ...tab[i], ...row }; else tab.push({ created_at: new Date().toISOString(), version: 1, ...row });
      }
      return { data: null, error: null };
    }
    if (this.mode === 'update') { tab.filter(match).forEach((r) => Object.assign(r, structuredClone(this.payload))); return { data: null, error: null }; }
    if (this.mode === 'delete') {
      if (this.t === 'accounts') for (const r of tab.filter(match)) T.sessions = T.sessions.filter((s) => s.uid !== r.id);
      T[this.t] = tab.filter((r) => !match(r)); return { data: null, error: null };
    }
    let rows = tab.filter(match).map((r) => structuredClone(r));
    if (this.ord) { const [c, asc] = this.ord; rows.sort((a, b) => (String(a[c]) > String(b[c]) ? 1 : -1) * (asc ? 1 : -1)); }
    if (this.lim) rows = rows.slice(0, this.lim);
    if (this.one) { if (this.one === 2 && rows.length !== 1) return { data: null, error: { message: 'not single' } }; return { data: rows[0] ?? null, error: null }; }
    return { data: rows, error: null };
  }
}

export function fake() {
  return {
    from: (t: string) => new Q(t),
    rpc: async (_n: string, a: { p_uid: string; p_in: number; p_out: number }) => {
      const day = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
      let r = T.ai_usage.find((x) => x.uid === a.p_uid && x.day === day);
      if (!r) { r = { uid: a.p_uid, day, calls: 0 }; T.ai_usage.push(r); }
      r.calls = (r.calls as number) + 1; return { data: r.calls, error: null };
    },
    storage: { from: () => ({ list: async () => ({ data: [] }), remove: async () => ({}) }) },
    __tables: T,
  };
}
