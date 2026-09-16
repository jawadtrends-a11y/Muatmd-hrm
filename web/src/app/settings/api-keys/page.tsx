"use client";
/**
 * مفاتيح API (ق-151).
 *
 * ⚠️ **والمفتاح يُعرض مرّةً واحدة** — فمن فقده أنشأ غيره.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import DateField from "@/components/DateField";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "مفاتيح API", en: "API keys" },
  sub: {
    ar: "اربط أنظمتك ببياناتك — قراءةً بمفتاحٍ لشركةٍ ونطاق",
    en: "Connect your systems — read-only, scoped per company",
  },
  add: { ar: "مفتاح جديد", en: "New key" },
  name: { ar: "الاسم", en: "Name" },
  nameHint: {
    ar: "لأيّ تكاملٍ هذا المفتاح — فالاسم يُذكّرك عند المراجعة",
    en: "What integration is this for",
  },
  prefix: { ar: "البادئة", en: "Prefix" },
  scopes: { ar: "النطاقات", en: "Scopes" },
  scopeHint: {
    ar: "⚠️ اختر ما يحتاجه فقط — فمفتاح تكاملٍ محاسبيّ لا يقرأ ملفّات الموظفين",
    en: "Pick only what's needed",
  },
  rate: { ar: "السقف بالساعة", en: "Rate/hour" },
  expires: { ar: "ينتهي في", en: "Expires" },
  expiresHint: { ar: "اتركه فارغًا لمفتاحٍ دائم", en: "Empty = no expiry" },
  lastUsed: { ar: "آخر استعمال", en: "Last used" },
  calls: { ar: "النداءات", en: "Calls" },
  state: { ar: "الحالة", en: "Status" },
  active: { ar: "يعمل", en: "Active" },
  revoked: { ar: "موقوف", en: "Revoked" },
  expired: { ar: "منتهٍ", en: "Expired" },
  revoke: { ar: "إيقاف", en: "Revoke" },
  log: { ar: "السجلّ", en: "Log" },
  save: { ar: "إنشاء", en: "Create" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  close: { ar: "إغلاق", en: "Close" },
  empty: { ar: "لا مفاتيح بعد", en: "No keys yet" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "الواجهة البرمجية غير متاحة في باقتكم",
              en: "Not in your plan" },
  created: { ar: "أُنشئ المفتاح", en: "Key created" },
  copyNow: {
    ar: "⚠️ احفظه الآن — لن يُعرض ثانيةً، ومن فقده أنشأ غيره",
    en: "Save it now — it will never be shown again",
  },
  copy: { ar: "نسخ", en: "Copy" },
  copied: { ar: "نُسخ", en: "Copied" },
  revokeReason: { ar: "سبب الإيقاف", en: "Reason" },
  docs: { ar: "كيف تستعمله", en: "How to use" },
  docsBody: {
    ar: "أرسل المفتاح في ترويسة X-API-Key مع كل نداء. وابدأ بـ/api/v1/whoami/ للتأكّد من نطاقاتك.",
    en: "Send the key in the X-API-Key header. Start with /api/v1/whoami/.",
  },
  at: { ar: "الوقت", en: "Time" },
  path: { ar: "المسار", en: "Path" },
  status: { ar: "الردّ", en: "Status" },
};

type Key = {
  id: number; name: string; prefix: string; scopes: string[];
  rate_limit_per_hour: number; is_active: boolean; is_usable: boolean;
  expires_on: string | null; last_used_at: string | null;
  last_used_ip: string; call_count: number;
  revoked_at: string | null; revoked_reason: string;
};
type Scope = { value: string; label: string };
type Call = {
  at: string; path: string; method: string;
  status_code: number; ip: string;
};

export default function ApiKeysPage() {
  const { L } = useT(T);
  const [keys, setKeys] = useState<Key[]>([]);
  const [scopes, setScopes] = useState<Scope[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [err, setErr] = useState("");
  const [adding, setAdding] = useState(false);
  const [fresh, setFresh] = useState<{ key: string;
                                       name: string } | null>(null);
  const [logOf, setLogOf] = useState<Key | null>(null);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiGet<{ keys: Key[]; scopes: Scope[] }>(
        "/api-keys/");
      setKeys(d.keys);
      setScopes(d.scopes);
    } catch (e) {
      if ((e as ApiError).status === 402) setDenied(true);
      else setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const revoke = async (k: Key) => {
    const reason = prompt(L("revokeReason")) || "";
    setActing(true); setErr("");
    try {
      await apiPost(`/api-keys/${k.id}/revoke/`, { reason });
      await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setActing(false); }
  };

  const label = (v: string) =>
    scopes.find((s) => s.value === v)?.label || v;

  if (busy) return (
    <div className="card" style={{ padding: 40, textAlign: "center",
                                   color: "var(--ink-3)" }}>{L("loading")}</div>
  );

  if (denied) return (
    <div className="card" style={{ padding: 36, textAlign: "center",
                                   color: "var(--ink-3)" }}>
      <IcAlert size={22} />
      <div style={{ marginTop: 8 }}>{L("noAccess")}</div>
    </div>
  );

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1 style={{ margin: 0 }}>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("sub")}
          </div>
        </div>
        <button className="btn btn-primary btn-sm"
                onClick={() => setAdding(true)}>{L("add")}</button>
      </div>

      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div className="card" style={{ padding: 16,
                                     background: "var(--paper-2)" }}>
        <strong style={{ fontSize: ".9rem" }}>{L("docs")}</strong>
        <div className="muted" style={{ fontSize: ".84rem", marginTop: 6,
                                        lineHeight: 1.9 }}>
          {L("docsBody")}
        </div>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {keys.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center",
                        color: "var(--ink-3)" }}>
            <IcDoc size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("name")}</th>
                  <th style={{ width: 200 }}>{L("scopes")}</th>
                  <th style={{ width: 110 }}>{L("rate")}</th>
                  <th style={{ width: 130 }}>{L("lastUsed")}</th>
                  <th style={{ width: 110 }}>{L("state")}</th>
                  <th style={{ width: 140 }} />
                </tr>
              </thead>
              <tbody>
                {keys.map((k) => (
                  <tr key={k.id} style={{ opacity: k.is_usable ? 1 : .55 }}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{k.name}</div>
                      <div className="muted num"
                           style={{ fontSize: ".75rem" }}>
                        {k.prefix}…
                      </div>
                    </td>
                    <td>
                      <div className="row" style={{ gap: 4,
                                                    flexWrap: "wrap" }}>
                        {k.scopes.map((s) => (
                          <span key={s} className="badge"
                                style={{ fontSize: ".68rem" }}>
                            {label(s)}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td><span className="num">
                      {k.rate_limit_per_hour}
                    </span></td>
                    <td>
                      {k.last_used_at ? (
                        <div>
                          <span className="num"
                                style={{ fontSize: ".8rem" }}>
                            {k.last_used_at.slice(0, 16)
                              .replace("T", " ")}
                          </span>
                          <div className="muted num"
                               style={{ fontSize: ".72rem" }}>
                            {k.call_count} {L("calls")}
                          </div>
                        </div>
                      ) : <span className="muted">—</span>}
                    </td>
                    <td>
                      {k.revoked_at ? (
                        <span className="badge badge-danger"
                              title={k.revoked_reason}>
                          {L("revoked")}
                        </span>
                      ) : !k.is_usable ? (
                        <span className="badge badge-warn">
                          {L("expired")}
                        </span>
                      ) : (
                        <span className="badge badge-ok">
                          {L("active")}
                        </span>
                      )}
                    </td>
                    <td>
                      <div className="row" style={{ gap: 5 }}>
                        <button className="btn btn-sm btn-ghost"
                                onClick={() => setLogOf(k)}>
                          {L("log")}
                        </button>
                        {!k.revoked_at && (
                          <button className="btn btn-sm btn-danger"
                                  disabled={acting}
                                  onClick={() => revoke(k)}>
                            {L("revoke")}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {adding && (
        <CreateDialog scopes={scopes} L={L}
                      onClose={() => setAdding(false)}
                      onCreated={async (raw, name) => {
                        setAdding(false);
                        setFresh({ key: raw, name });
                        await load();
                      }} />
      )}

      {fresh && (
        <FreshKeyDialog data={fresh} L={L}
                        onClose={() => setFresh(null)} />
      )}

      {logOf && (
        <LogDialog k={logOf} L={L} onClose={() => setLogOf(null)} />
      )}
    </div>
  );
}


function CreateDialog({ scopes, L, onClose, onCreated }: {
  scopes: Scope[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onCreated: (raw: string, name: string) => void;
}) {
  const [name, setName] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [rate, setRate] = useState("1000");
  const [expires, setExpires] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const toggle = (v: string) =>
    setPicked((p) => p.includes(v) ? p.filter((x) => x !== v)
                                   : [...p, v]);

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const out = await apiPost<{ key: string }>("/api-keys/", {
        name, scopes: picked,
        rate_limit_per_hour: Number(rate),
        expires_on: expires || undefined,
      });
      onCreated(out.key, name);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <Modal onClose={onClose}>
      <h3 style={{ margin: 0 }}>{L("add")}</h3>
      {err && (
        <div style={{ background: "var(--danger-soft)",
                      color: "var(--danger)", padding: "9px 12px",
                      borderRadius: "var(--radius-sm)",
                      fontSize: ".86rem", marginTop: 14 }}>
          {err}
        </div>
      )}

      <label className="field" style={{ marginTop: 16 }}>
        <span className="label">{L("name")}</span>
        <input className="input" value={name}
               onChange={(e) => setName(e.target.value)} />
        <span className="muted" style={{ fontSize: ".78rem" }}>
          {L("nameHint")}
        </span>
      </label>

      <div className="field" style={{ marginTop: 14 }}>
        <span className="label">{L("scopes")}</span>
        <div className="row" style={{ gap: 6, flexWrap: "wrap",
                                      marginTop: 4 }}>
          {scopes.map((s) => (
            <button key={s.value} type="button"
                    className={`btn btn-sm ${picked.includes(s.value) ? "btn-primary" : "btn-ghost"}`}
                    onClick={() => toggle(s.value)}>
              {s.label}
            </button>
          ))}
        </div>
        <span className="muted" style={{ fontSize: ".78rem",
                                         marginTop: 6, display: "block",
                                         lineHeight: 1.8 }}>
          {L("scopeHint")}
        </span>
      </div>

      <div className="row" style={{ gap: 12, marginTop: 14 }}>
        <label className="field" style={{ width: 140 }}>
          <span className="label">{L("rate")}</span>
          <input className="input num" type="number" min={1}
                 value={rate}
                 onChange={(e) => setRate(e.target.value)} />
        </label>
        <div className="field" style={{ flex: 1 }}>
          <label className="label">{L("expires")}</label>
          <DateField value={expires} onChange={setExpires} />
          <span className="muted" style={{ fontSize: ".78rem" }}>
            {L("expiresHint")}
          </span>
        </div>
      </div>

      <div className="row" style={{ gap: 8, marginTop: 18 }}>
        <button className="btn btn-primary"
                disabled={busy || !name.trim() || picked.length === 0}
                onClick={submit}>{busy ? "…" : L("save")}</button>
        <button className="btn" onClick={onClose}>{L("cancel")}</button>
      </div>
    </Modal>
  );
}


function FreshKeyDialog({ data, L, onClose }: {
  data: { key: string; name: string };
  L: (k: string, f?: string) => string;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  return (
    <Modal onClose={onClose}>
      <h3 style={{ margin: 0 }}>{L("created")}</h3>
      <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>
        {data.name}
      </div>

      {/* ⚠️ التنبيه أوّلًا — فالمفتاح لا يُعرض ثانيةً */}
      <div style={{ background: "var(--copper-soft)",
                    color: "var(--copper)", padding: "11px 14px",
                    borderRadius: "var(--radius-sm)",
                    fontSize: ".84rem", lineHeight: 1.9,
                    marginTop: 14 }}>
        {L("copyNow")}
      </div>

      <div style={{ marginTop: 14, padding: "12px 14px",
                    background: "var(--paper-2)",
                    borderRadius: "var(--radius-sm)",
                    wordBreak: "break-all", direction: "ltr",
                    fontFamily: "monospace", fontSize: ".85rem" }}>
        {data.key}
      </div>

      <div className="row" style={{ gap: 8, marginTop: 16 }}>
        <button className="btn btn-primary"
                onClick={() => {
                  navigator.clipboard?.writeText(data.key);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2500);
                }}>
          {copied ? L("copied") : L("copy")}
        </button>
        <button className="btn" onClick={onClose}>{L("close")}</button>
      </div>
    </Modal>
  );
}


function LogDialog({ k, L, onClose }: {
  k: Key;
  L: (key: string, f?: string) => string;
  onClose: () => void;
}) {
  const [calls, setCalls] = useState<Call[]>([]);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    apiGet<{ calls: Call[] }>(`/api-keys/${k.id}/calls/`)
      .then((d) => setCalls(d.calls || []))
      .catch(() => setCalls([]))
      .finally(() => setBusy(false));
  }, [k.id]);

  return (
    <Modal onClose={onClose} wide>
      <h3 style={{ margin: 0 }}>{k.name} — {L("log")}</h3>

      <div style={{ marginTop: 14 }}>
        {busy ? (
          <div className="muted">{L("loading")}</div>
        ) : calls.length === 0 ? (
          <div className="muted" style={{ padding: "20px 0",
                                          textAlign: "center" }}>
            {L("empty")}
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 145 }}>{L("at")}</th>
                <th>{L("path")}</th>
                <th style={{ width: 80 }}>{L("status")}</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((c, i) => (
                <tr key={i}>
                  <td>
                    <span className="num" style={{ fontSize: ".8rem" }}>
                      {c.at.slice(0, 16).replace("T", " ")}
                    </span>
                  </td>
                  <td>
                    <span className="num" style={{ fontSize: ".8rem" }}>
                      {c.method} {c.path}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${c.status_code < 300 ? "badge-ok" : c.status_code < 500 ? "badge-warn" : "badge-danger"}`}>
                      {c.status_code}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <button className="btn" style={{ marginTop: 16 }}
              onClick={onClose}>{L("close")}</button>
    </Modal>
  );
}


function Modal({ children, onClose, wide }: {
  children: React.ReactNode; onClose: () => void; wide?: boolean;
}) {
  return (
    <div onMouseDown={(e) => {
      if (e.target === e.currentTarget) onClose();
    }} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24,
                                     maxWidth: wide ? 640 : 470,
                                     width: "100%", maxHeight: "90vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}
