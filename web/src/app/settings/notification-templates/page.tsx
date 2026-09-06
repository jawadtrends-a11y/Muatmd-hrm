"use client";

/**
 * قوالب الإشعارات.
 *
 * لكل حدث قوالب بعدد قنواته ولغاته. والقوالب العامة يشترك فيها
 * الجميع — وتعديل الشركة ينسخها لها فلا يمسّ غيرها.
 */
import { useCallback, useEffect, useState } from "react";

import { apiGet, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc, IcX } from "@/components/Icons";

const T: Dict = {
  title: { ar: "قوالب الإشعارات", en: "Notification templates" },
  subtitle: {
    ar: "نصّ كل إشعار في قنواته ولغاته",
    en: "Text of each notification per channel and language",
  },
  search: { ar: "ابحث في الأحداث…", en: "Search events…" },
  show: { ar: "عرض القوالب", en: "Show templates" },
  hide: { ar: "إخفاء", en: "Hide" },
  channel: { ar: "القناة", en: "Channel" },
  locale: { ar: "اللغة", en: "Language" },
  subject: { ar: "العنوان", en: "Subject" },
  body: { ar: "النص", en: "Body" },
  edit: { ar: "تعديل", en: "Edit" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  isDefault: { ar: "افتراضي", en: "Default" },
  customized: { ar: "مخصَّص", en: "Customized" },
  mandatory: { ar: "إلزامي", en: "Mandatory" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا أحداث", en: "No events" },
  noTemplates: { ar: "لا قوالب لهذا الحدث", en: "No templates" },
  noAccess: { ar: "لا تملك هذه الصلاحية", en: "Not permitted" },
  varsHint: {
    ar: "المتغيّرات بين قوسين معقوفين تُملأ عند الإرسال — حذفها "
        + "يُرسل نصًّا ناقصًا",
    en: "Variables in braces are filled on send — removing them "
        + "sends incomplete text",
  },
  defaultHint: {
    ar: "قالب افتراضي — تعديله ينشئ نسخة لشركتك",
    en: "Default template — editing creates a copy for your company",
  },
  inApp: { ar: "داخل النظام", en: "In-app" },
  email: { ar: "بريد", en: "Email" },
  sms: { ar: "رسالة نصية", en: "SMS" },
  whatsapp: { ar: "واتساب", en: "WhatsApp" },
};

type Template = {
  id: number;
  channel: string;
  locale: string;
  subject: string;
  body: string;
  is_default: boolean;
};

type Event = {
  event_key: string;
  name_ar: string;
  module: string;
  channels: string[];
  is_mandatory: boolean;
  templates: Template[];
};

export default function NotificationTemplatesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Event[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState<{ subject: string; body: string }>({
    subject: "", body: "",
  });
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    apiGet<Event[]>("/notifications/templates/")
      .then((d) => { setRows(d); setBusy(false); })
      .catch((e: ApiError) => {
        setDenied(e.status === 403);
        setBusy(false);
      });
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    apiGet<{ permissions: string[] }>("/me/workspace/")
      .then((d) =>
        setCanEdit((d.permissions || []).includes("company.edit")))
      .catch(() => setCanEdit(false));
  }, []);

  async function save(id: number) {
    setErr("");
    try {
      await apiPut(`/notifications/templates/${id}/`, draft);
      setEditing(null);
      load();
    } catch (e) {
      setErr((e as ApiError).message);
      setTimeout(() => setErr(""), 6000);
    }
  }

  const chLabel = (ch: string) =>
    ch === "in_app" ? L("inApp")
      : ch === "email" ? L("email")
      : ch === "sms" ? L("sms")
      : ch === "whatsapp" ? L("whatsapp") : ch;

  const visible = q
    ? rows.filter((e) =>
        e.name_ar.includes(q) || e.event_key.includes(q.toLowerCase()))
    : rows;

  if (denied) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        <IcAlert size={22} />
        <div style={{ marginTop: 8 }}>{L("noAccess")}</div>
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        <input className="input" placeholder={L("search")}
          style={{ maxWidth: 230 }}
          value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {err && (
        <div style={{
          background: "var(--danger-soft)", color: "var(--danger)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
          fontSize: ".9rem",
        }}>
          {err}
        </div>
      )}

      {busy ? (
        <div className="card" style={{
          padding: 40, textAlign: "center", color: "var(--ink-3)",
        }}>
          {L("loading")}
        </div>
      ) : visible.length === 0 ? (
        <div className="card" style={{
          padding: 40, textAlign: "center", color: "var(--ink-3)",
        }}>
          <IcDoc size={22} />
          <div style={{ marginTop: 8 }}>{L("empty")}</div>
        </div>
      ) : (
        <div className="stack" style={{ gap: 8 }}>
          {visible.map((ev) => (
            <div key={ev.event_key} className="card">
              <div className="spread" style={{ padding: "13px 18px" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>
                    {ev.name_ar}
                    {ev.is_mandatory && (
                      <span className="badge" style={{
                        marginInlineStart: 6, fontSize: ".72rem",
                      }}>
                        {L("mandatory")}
                      </span>
                    )}
                  </div>
                  <div className="muted num" style={{
                    fontSize: ".76rem", marginTop: 2,
                  }}>
                    {ev.event_key}
                    {" · "}
                    {ev.channels.map(chLabel).join("، ")}
                  </div>
                </div>

                <button className="btn btn-sm btn-ghost"
                  onClick={() => setOpen(
                    open === ev.event_key ? null : ev.event_key)}>
                  {open === ev.event_key ? L("hide") : L("show")}
                  {" "}
                  <span className="num muted">
                    ({ev.templates.length})
                  </span>
                </button>
              </div>

              {open === ev.event_key && (
                <div style={{
                  borderTop: "1px solid var(--line)",
                  padding: "12px 18px",
                }}>
                  {ev.templates.length === 0 ? (
                    <div className="muted" style={{ fontSize: ".85rem" }}>
                      {L("noTemplates")}
                    </div>
                  ) : ev.templates.map((t) => (
                    <div key={t.id} style={{
                      padding: "10px 0",
                      borderBottom: "1px solid var(--line)",
                    }}>
                      <div className="spread">
                        <div className="row" style={{ gap: 8 }}>
                          <span className="badge">
                            {chLabel(t.channel)}
                          </span>
                          <span className="num muted" style={{
                            fontSize: ".78rem",
                          }}>
                            {t.locale}
                          </span>
                          <span className={t.is_default
                            ? "muted" : "badge badge-ok"}
                            style={{ fontSize: ".74rem" }}>
                            {t.is_default ? L("isDefault") : L("customized")}
                          </span>
                        </div>

                        {canEdit && editing !== t.id && (
                          <button className="btn btn-sm btn-ghost"
                            onClick={() => {
                              setDraft({
                                subject: t.subject, body: t.body,
                              });
                              setEditing(t.id);
                            }}>
                            {L("edit")}
                          </button>
                        )}
                      </div>

                      {editing === t.id ? (
                        <div style={{ marginTop: 10 }}>
                          {t.is_default && (
                            <div className="muted" style={{
                              fontSize: ".8rem", marginBottom: 8,
                            }}>
                              {L("defaultHint")}
                            </div>
                          )}

                          <div className="field">
                            <label className="label">{L("subject")}</label>
                            <input className="input" value={draft.subject}
                              onChange={(e) => setDraft((d) => ({
                                ...d, subject: e.target.value,
                              }))} />
                          </div>

                          <div className="field" style={{ marginTop: 8 }}>
                            <label className="label">{L("body")}</label>
                            <textarea className="input" rows={4}
                              value={draft.body}
                              onChange={(e) => setDraft((d) => ({
                                ...d, body: e.target.value,
                              }))} />
                          </div>

                          <div className="muted" style={{
                            fontSize: ".78rem", marginTop: 6,
                          }}>
                            {L("varsHint")}
                          </div>

                          <div className="row" style={{ marginTop: 10 }}>
                            <button className="btn btn-sm btn-primary"
                              onClick={() => save(t.id)}>
                              <IcCheck size={15} />
                              {L("save")}
                            </button>
                            <button className="btn btn-sm btn-ghost"
                              onClick={() => setEditing(null)}>
                              <IcX size={15} />
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div style={{ marginTop: 6 }}>
                          {t.subject && (
                            <div style={{ fontSize: ".88rem" }}>
                              {t.subject}
                            </div>
                          )}
                          <div className="muted" style={{
                            fontSize: ".82rem", whiteSpace: "pre-wrap",
                            marginTop: 3,
                          }}>
                            {t.body}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
