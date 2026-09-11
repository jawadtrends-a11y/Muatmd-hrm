"use client";
/**
 * تذاكر الدعم (ق-133).
 *
 * ⚠️ **المرتّبة بالأحقّ لا بالأحدث**: ما لم يُردّ عليه أوّلًا، ثم
 * الأقرب استحقاقًا — فمستوى الخدمة يُقاس بأول ردّ.
 */
import { useCallback, useEffect, useState } from "react";
import { pGet, pPost, type AdminError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck } from "@/components/Icons";

const T: Dict = {
  title: { ar: "تذاكر الدعم", en: "Support tickets" },
  sub: {
    ar: "ما لم يُردّ عليه أوّلًا — والمتجاوَز بالأحمر",
    en: "Unanswered first — breached in red",
  },
  all: { ar: "الكل", en: "All" },
  openOnly: { ar: "المفتوحة", en: "Open" },
  no: { ar: "الرقم", en: "No." },
  subject: { ar: "الموضوع", en: "Subject" },
  company: { ar: "العميل", en: "Customer" },
  plan: { ar: "الباقة", en: "Plan" },
  due: { ar: "موعد الردّ", en: "Due" },
  state: { ar: "الحالة", en: "Status" },
  open: { ar: "فتح", en: "Open" },
  reply: { ar: "الردّ", en: "Reply" },
  send: { ar: "إرسال", en: "Send" },
  resolve: { ar: "إغلاق التذكرة", en: "Resolve" },
  close: { ar: "إغلاق", en: "Close" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا تذاكر", en: "No tickets" },
  breached: { ar: "تجاوَزنا", en: "Breached" },
  answered: { ar: "رُدّ", en: "Answered" },
  openCount: { ar: "مفتوحة", en: "Open" },
  breachCount: { ar: "متجاوَزة", en: "Breached" },
  hoursBiz: { ar: "ساعة عمل", en: "business h" },
  hoursCal: { ar: "ساعة", en: "hours" },
  sla: { ar: "المهلة", en: "SLA" },
  by: { ar: "فتحها", en: "Opened by" },
  support: { ar: "الدعم", en: "Support" },
  sentOk: { ar: "أُرسل الردّ", en: "Reply sent" },
};

type Ticket = {
  id: number; ticket_no: string; subject: string;
  kind: string; priority: string; status: string;
  opened_by_name: string; created_at: string; due_at: string | null;
  sla_hours: number; sla_business_hours: boolean;
  plan_code_at_open: string;
  company_name: string; account_name: string;
  msgs: number; breached: boolean; answered: boolean;
};
type Detail = Ticket & {
  body: string; screenshot_url: string; status_label: string;
  kind_label: string;
  messages: { id: number; body: string; attachment_url: string;
              from_support: boolean; author: string; at: string }[];
};

const TONE: Record<string, string> = {
  open: "badge-warn", answered: "badge-ok",
  waiting: "badge", resolved: "badge",
};

export default function TicketsPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Ticket[]>([]);
  const [stats, setStats] = useState({ open: 0, breached: 0 });
  const [onlyOpen, setOnlyOpen] = useState(true);
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [shown, setShown] = useState<Detail | null>(null);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const d = await pGet<{ tickets: Ticket[]; open: number;
                             breached: number }>(
        `/platform/tickets/?open=${onlyOpen ? "1" : "0"}`);
      setRows(d.tickets);
      setStats({ open: d.open, breached: d.breached });
    } catch (e) {
      setErr((e as AdminError).message);
    } finally { setBusy(false); }
  }, [onlyOpen]);

  useEffect(() => { load(); }, [load]);

  const open = async (t: Ticket) => {
    try {
      setShown(await pGet<Detail>(`/platform/tickets/${t.id}/`));
    } catch (e) {
      setErr((e as AdminError).message);
    }
  };

  if (busy) return (
    <div style={{ padding: 40, textAlign: "center",
                  color: "var(--ink-3)" }}>{L("loading")}</div>
  );

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("sub")}
          </div>
        </div>
        <div className="row" style={{ gap: 18 }}>
          <Stat label={L("openCount")} value={stats.open} />
          <Stat label={L("breachCount")} value={stats.breached}
                tone={stats.breached ? "var(--danger)" : undefined} />
        </div>
      </div>

      {msg && (
        <div style={{ background: "var(--ok-soft)", color: "var(--ok)",
                      padding: "10px 14px",
                      borderRadius: "var(--radius-sm)" }}>
          <IcCheck size={15} /> {msg}
        </div>
      )}
      {err && (
        <div style={{ background: "var(--danger-soft)",
                      color: "var(--danger)", padding: "10px 14px",
                      borderRadius: "var(--radius-sm)" }}>
          <IcAlert size={15} /> {err}
        </div>
      )}

      <div className="row" style={{ gap: 6 }}>
        <button className={`btn btn-sm ${onlyOpen ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setOnlyOpen(true)}>{L("openOnly")}</button>
        <button className={`btn btn-sm ${!onlyOpen ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setOnlyOpen(false)}>{L("all")}</button>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center",
                        color: "var(--ink-3)" }}>{L("empty")}</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 140 }}>{L("no")}</th>
                  <th>{L("subject")}</th>
                  <th style={{ width: 180 }}>{L("company")}</th>
                  <th style={{ width: 110 }}>{L("sla")}</th>
                  <th style={{ width: 160 }}>{L("due")}</th>
                  <th style={{ width: 80 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <span className="num" style={{ fontSize: ".8rem" }}>
                        {t.ticket_no}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{t.subject}</div>
                      <div className="muted" style={{ fontSize: ".75rem" }}>
                        {L("by")} {t.opened_by_name}
                      </div>
                    </td>
                    <td className="muted">{t.company_name}</td>
                    <td>
                      <span className="num">{t.sla_hours}</span>{" "}
                      <span className="muted" style={{ fontSize: ".75rem" }}>
                        {t.sla_business_hours ? L("hoursBiz")
                          : L("hoursCal")}
                      </span>
                    </td>
                    <td>
                      {t.answered ? (
                        <span className="badge badge-ok">{L("answered")}</span>
                      ) : t.breached ? (
                        <span className="badge badge-danger">
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

      {shown && (
        <TicketDialog t={shown} L={L} onClose={() => setShown(null)}
                      onChanged={async () => {
                        setMsg(L("sentOk"));
                        setTimeout(() => setMsg(""), 4000);
                        await load();
                        await open(shown);
                      }} />
      )}
    </div>
  );
}

function Stat({ label, value, tone }: {
  label: string; value: number; tone?: string;
}) {
  return (
    <div style={{ textAlign: "center" }}>
      <div className="muted" style={{ fontSize: ".76rem" }}>{label}</div>
      <div className="num" style={{ fontSize: "1.5rem", fontWeight: 600,
                                    color: tone }}>{value}</div>
    </div>
  );
}


function TicketDialog({ t, L, onClose, onChanged }: {
  t: Detail;
  L: (k: string, f?: string) => string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const act = async (payload: Record<string, unknown>) => {
    setBusy(true); setErr("");
    try {
      await pPost(`/platform/tickets/${t.id}/`, payload);
      setBody("");
      await onChanged();
    } catch (e) {
      setErr((e as AdminError).message);
    } finally { setBusy(false); }
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.5)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 24, maxWidth: 660,
                                     width: "100%", maxHeight: "90vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <div className="spread">
          <div>
            <h3 style={{ margin: 0 }}>{t.subject}</h3>
            <div className="muted" style={{ fontSize: ".8rem",
                                            marginTop: 3 }}>
              <span className="num">{t.ticket_no}</span>
              {" · "}{t.company_name}
              {" · "}{t.kind_label}
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
          {t.messages.map((m) => (
            <div key={m.id} style={{
              padding: "12px 14px",
              borderRadius: "var(--radius-sm)",
              background: m.from_support
                ? "var(--teal-soft)" : "var(--paper-2)",
              marginInlineStart: m.from_support ? 30 : 0,
              marginInlineEnd: m.from_support ? 0 : 30,
            }}>
              <div className="spread" style={{ fontSize: ".78rem" }}>
                <strong>{m.from_support ? L("support") : m.author}</strong>
                <span className="muted num">
                  {m.at?.slice(0, 16).replace("T", " ")}
                </span>
              </div>
              <div style={{ whiteSpace: "pre-wrap", marginTop: 6,
                            fontSize: ".92rem" }}>{m.body}</div>
              {m.attachment_url && (
                <a href={m.attachment_url} target="_blank"
                   rel="noreferrer"
                   style={{ fontSize: ".8rem", display: "block",
                            marginTop: 6 }}>
                  {m.attachment_url.split("/").pop()}
                </a>
              )}
            </div>
          ))}
        </div>

        {t.status !== "resolved" && (
          <>
            <label className="field" style={{ marginTop: 18 }}>
              <span className="label">{L("reply")}</span>
              <textarea className="input" rows={4} value={body}
                        onChange={(e) => setBody(e.target.value)} />
            </label>
            <div className="row" style={{ gap: 8, marginTop: 12 }}>
              <button className="btn btn-primary"
                      disabled={busy || !body.trim()}
                      onClick={() => act({ body })}>{L("send")}</button>
              <button className="btn" disabled={busy}
                      onClick={() => act({ action: "resolve" })}>
                {L("resolve")}
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
