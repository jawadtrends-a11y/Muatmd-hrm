"use client";
/**
 * تذاكر الدعم (ق-133).
 *
 * ⚠️ **والصورة إلزامية** — فالشاشة تقول أكثر من فقرة.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiPost, apiUpload, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import AuthImage from "@/components/AuthImage";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الدعم الفنّي", en: "Support" },
  sub: {
    ar: "افتح تذكرةً وتابعها — وردُّنا خلال المهلة المتعهَّد بها",
    en: "Open a ticket and track it",
  },
  add: { ar: "تذكرة جديدة", en: "New ticket" },
  no: { ar: "الرقم", en: "No." },
  subject: { ar: "العنوان", en: "Subject" },
  kind: { ar: "التصنيف", en: "Type" },
  state: { ar: "الحالة", en: "Status" },
  due: { ar: "موعد الردّ", en: "Response due" },
  open: { ar: "فتح", en: "Open" },
  body: { ar: "اشرح المشكلة", en: "Describe the issue" },
  screenshot: { ar: "صورة الشاشة", en: "Screenshot" },
  screenshotHint: {
    ar: "إلزامية — بها نفهم أسرع ونردّ أدقّ",
    en: "Required — a screenshot says more than a paragraph",
  },
  pick: { ar: "اختر صورة", en: "Choose image" },
  uploading: { ar: "جارٍ الرفع…", en: "Uploading…" },
  send: { ar: "إرسال", en: "Send" },
  reply: { ar: "ردّك", en: "Your reply" },
  close: { ar: "إغلاق", en: "Close" },
  closeTicket: { ar: "إغلاق التذكرة", en: "Close ticket" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  empty: { ar: "لا تذاكر — افتح واحدةً إن واجهتك مشكلة", en: "No tickets" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  newTitle: { ar: "تذكرة جديدة", en: "New ticket" },
  sla: {
    ar: "نردّ خلال {n} {unit} — بحسب باقتكم",
    en: "We respond within {n} {unit}",
  },
  hoursBiz: { ar: "ساعة عمل", en: "business hours" },
  hoursCal: { ar: "ساعة", en: "hours" },
  support: { ar: "الدعم", en: "Support" },
  you: { ar: "أنت", en: "You" },
  breached: { ar: "تجاوزنا المهلة", en: "Overdue" },
  answered: { ar: "رُدّ عليها", en: "Answered" },
  sentOk: { ar: "أُرسلت تذكرتك", en: "Ticket sent" },
};

type Ticket = {
  id: number; ticket_no: string; subject: string;
  kind: string; kind_label: string;
  status: string; status_label: string;
  created_at: string; due_at: string | null;
  sla_hours: number; sla_business: boolean;
  answered: boolean; breached: boolean;
  body?: string; screenshot_url?: string;
  messages?: { id: number; body: string; attachment_url: string;
               from_support: boolean; author: string; at: string }[];
};
type Kind = { value: string; label: string };

const TONE: Record<string, string> = {
  open: "badge-warn", answered: "badge-ok",
  waiting: "badge", resolved: "badge",
};

export default function SupportPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Ticket[]>([]);
  const [kinds, setKinds] = useState<Kind[]>([]);
  const [sla, setSla] = useState({ hours: 24, business: false });
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [adding, setAdding] = useState(false);
  const [shown, setShown] = useState<Ticket | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await apiGet<{ tickets: Ticket[]; kinds: Kind[];
                               sla: { hours: number; business: boolean } }>(
        "/support/tickets/");
      setRows(d.tickets);
      setKinds(d.kinds);
      setSla(d.sla);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const open = async (t: Ticket) => {
    try {
      setShown(await apiGet<Ticket>(`/support/tickets/${t.id}/`));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    }
  };

  if (busy) return (
    <div className="card" style={{ padding: 40, textAlign: "center",
                                   color: "var(--ink-3)" }}>{L("loading")}</div>
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

      <div className="card" style={{ padding: "10px 16px",
                                     fontSize: ".85rem" }}>
        {L("sla").replace("{n}", String(sla.hours))
          .replace("{unit}", sla.business ? L("hoursBiz") : L("hoursCal"))}
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      <div className="card" style={{ overflow: "hidden" }}>
        {rows.length === 0 ? (
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
                  <th style={{ width: 140 }}>{L("no")}</th>
                  <th>{L("subject")}</th>
                  <th style={{ width: 110 }}>{L("kind")}</th>
                  <th style={{ width: 120 }}>{L("state")}</th>
                  <th style={{ width: 170 }}>{L("due")}</th>
                  <th style={{ width: 90 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id}>
                    <td><span className="num"
                              style={{ fontSize: ".82rem" }}>
                      {t.ticket_no}
                    </span></td>
                    <td style={{ fontWeight: 500 }}>{t.subject}</td>
                    <td className="muted">{t.kind_label}</td>
                    <td>
                      <span className={`badge ${TONE[t.status] || "badge"}`}>
                        {t.status_label}
                      </span>
                    </td>
                    <td>
                      {t.answered ? (
                        <span className="muted"
                              style={{ fontSize: ".8rem" }}>
                          {L("answered")}
                        </span>
                      ) : t.breached ? (
                        <span style={{ color: "var(--danger)",
                                       fontSize: ".8rem" }}>
                          {L("breached")}
                        </span>
                      ) : (
                        <span className="num" style={{ fontSize: ".8rem" }}>
                          {t.due_at?.slice(0, 16).replace("T", " ")}
                        </span>
                      )}
                    </td>
                    <td>
                      <button className="btn btn-sm"
                              onClick={() => open(t)}>{L("open")}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {adding && (
        <NewTicket kinds={kinds} L={L} onClose={() => setAdding(false)}
                   onSaved={async () => {
                     setAdding(false);
                     setMsg(L("sentOk"));
                     setTimeout(() => setMsg(""), 4000);
                     await load();
                   }} />
      )}

      {shown && (
        <TicketView t={shown} L={L} onClose={() => setShown(null)}
                    onChanged={async () => { await load();
                                             await open(shown); }} />
      )}
    </div>
  );
}


/* ══ تذكرة جديدة ══ */

function NewTicket({ kinds, L, onClose, onSaved }: {
  kinds: Kind[];
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [f, setF] = useState({ subject: "", body: "", kind: "bug" });
  const [shot, setShot] = useState("");
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const upload = async (file: File) => {
    setUploading(true); setErr("");
    try {
      const res = await apiUpload<{ url: string }>("/files/", file);
      setShot(res.url);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "تعذّر رفع الصورة");
    } finally { setUploading(false); }
  };

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/support/tickets/", { ...f, screenshot_url: shot });
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 500,
                                     width: "100%" }}
           onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{L("newTitle")}</h3>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="stack" style={{ gap: 12, marginTop: 16 }}>
          <label className="field">
            <span className="label">{L("subject")}</span>
            <input className="input" value={f.subject} autoFocus
                   onChange={(e) => setF({ ...f,
                     subject: e.target.value })} />
          </label>

          <label className="field">
            <span className="label">{L("kind")}</span>
            <select className="select" value={f.kind}
                    onChange={(e) => setF({ ...f, kind: e.target.value })}>
              {kinds.map((k) => (
                <option key={k.value} value={k.value}>{k.label}</option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="label">{L("body")}</span>
            <textarea className="input" rows={5} value={f.body}
                      onChange={(e) => setF({ ...f,
                        body: e.target.value })} />
          </label>

          <div className="field">
            <span className="label">
              {L("screenshot")}
              <span style={{ color: "var(--danger)" }}> *</span>
            </span>
            <input ref={fileRef} type="file" accept="image/*"
                   style={{ display: "none" }}
                   onChange={(e) => e.target.files?.[0]
                     && upload(e.target.files[0])} />
            {shot ? (
              <div className="row" style={{ gap: 8, alignItems: "center" }}>
                <AuthImage src={shot} alt=""
                           style={{ width: 70, height: 48,
                                    objectFit: "cover",
                                    borderRadius: "var(--radius-sm)" }} />
                <button className="btn btn-sm btn-ghost"
                        onClick={() => setShot("")}>×</button>
              </div>
            ) : (
              <button className="btn btn-sm" disabled={uploading}
                      onClick={() => fileRef.current?.click()}>
                {uploading ? L("uploading") : L("pick")}
              </button>
            )}
            <span className="muted" style={{ fontSize: ".78rem" }}>
              {L("screenshotHint")}
            </span>
          </div>
        </div>

        <div className="row" style={{ gap: 8, marginTop: 18 }}>
          <button className="btn btn-primary"
                  disabled={busy || !f.subject.trim() || !f.body.trim()
                            || !shot}
                  onClick={submit}>
            {busy ? "…" : L("send")}
          </button>
          <button className="btn" onClick={onClose}>{L("cancel")}</button>
        </div>
      </div>
    </div>
  );
}


/* ══ عرض التذكرة ومحادثتها ══ */

function TicketView({ t, L, onClose, onChanged }: {
  t: Ticket;
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const send = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost(`/support/tickets/${t.id}/`, { body });
      setBody("");
      await onChanged();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  const close = async () => {
    setBusy(true);
    try {
      await apiPost(`/support/tickets/${t.id}/close/`, {});
      await onChanged();
      onClose();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.5)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 620,
                                     width: "100%", maxHeight: "88vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <div className="spread">
          <div>
            <h3 style={{ margin: 0 }}>{t.subject}</h3>
            <div className="muted num" style={{ fontSize: ".8rem",
                                                marginTop: 3 }}>
              {t.ticket_no}
            </div>
          </div>
          <span className={`badge ${TONE[t.status] || "badge"}`}>
            {t.status_label}
          </span>
        </div>

        {err && (
          <div style={{ background: "var(--danger-soft)",
                        color: "var(--danger)", padding: "9px 12px",
                        borderRadius: "var(--radius-sm)",
                        fontSize: ".86rem", marginTop: 14 }}>
            {err}
          </div>
        )}

        <div className="stack" style={{ gap: 12, marginTop: 18 }}>
          {(t.messages || []).map((m) => (
            <div key={m.id} style={{
              padding: "12px 14px",
              borderRadius: "var(--radius-sm)",
              background: m.from_support
                ? "var(--teal-soft)" : "var(--paper-2)",
              marginInlineStart: m.from_support ? 0 : 28,
              marginInlineEnd: m.from_support ? 28 : 0,
            }}>
              <div className="spread" style={{ fontSize: ".78rem" }}>
                <strong>{m.from_support ? L("support") : m.author}</strong>
                <span className="muted num">
                  {m.at?.slice(0, 16).replace("T", " ")}
                </span>
              </div>
              <div style={{ whiteSpace: "pre-wrap", marginTop: 6,
                            fontSize: ".92rem" }}>
                {m.body}
              </div>
              {m.attachment_url && (
                <AuthImage src={m.attachment_url} alt=""
                           style={{ marginTop: 8, maxWidth: "100%",
                                    borderRadius: "var(--radius-sm)" }} />
              )}
            </div>
          ))}
        </div>

        {t.status !== "resolved" && (
          <>
            <label className="field" style={{ marginTop: 18 }}>
              <span className="label">{L("reply")}</span>
              <textarea className="input" rows={3} value={body}
                        onChange={(e) => setBody(e.target.value)} />
            </label>
            <div className="row" style={{ gap: 8, marginTop: 12 }}>
              <button className="btn btn-primary"
                      disabled={busy || !body.trim()} onClick={send}>
                {L("send")}
              </button>
              <button className="btn" disabled={busy} onClick={close}>
                {L("closeTicket")}
              </button>
              <button className="btn btn-ghost"
                      onClick={onClose}>{L("close")}</button>
            </div>
          </>
        )}

        {t.status === "resolved" && (
          <button className="btn" style={{ marginTop: 18 }}
                  onClick={onClose}>{L("close")}</button>
        )}
      </div>
    </div>
  );
}
