"use client";
/**
 * الإعلانات — إرسال وسجلّ (ق-102).
 *
 * لمن يملك الإرسال وحده؛ وما يصل الموظف يقرؤه في «إشعاراتي».
 * والنطاق في الصلاحية: من يملك الإدارية يرى إداراته وحدها.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc, IcPlus, IcX } from "@/components/Icons";

const T: Dict = {
  title: { ar: "الإعلانات", en: "Announcements" },
  subtitle: { ar: "رسالة تصل موظفًا أو إدارة أو الشركة كلّها",
              en: "A message to an employee, a department or the company" },
  neu: { ar: "إعلان جديد", en: "New announcement" },
  kind: { ar: "النوع", en: "Type" },
  general: { ar: "إعلان عام", en: "General" },
  event: { ar: "فعالية", en: "Event" },
  meeting: { ar: "اجتماع", en: "Meeting" },
  congrats: { ar: "تهنئة", en: "Congratulations" },
  condolence: { ar: "تعزية", en: "Condolence" },
  decision: { ar: "قرار إداري", en: "Administrative decision" },
  audience: { ar: "المستقبلون", en: "Recipients" },
  company: { ar: "كل الشركة", en: "Whole company" },
  departments: { ar: "إدارات محددة", en: "Specific departments" },
  persons: { ar: "أشخاص محددون", en: "Specific people" },
  pickDept: { ar: "اختر الإدارات", en: "Pick departments" },
  pickPeople: { ar: "اختر الأشخاص", en: "Pick people" },
  titleAr: { ar: "العنوان", en: "Title" },
  titleEn: { ar: "العنوان بالإنجليزية", en: "Title (English)" },
  bodyAr: { ar: "النص", en: "Body" },
  bodyEn: { ar: "النص بالإنجليزية", en: "Body (English)" },
  enHint: { ar: "يقرؤه من ضبط لغته إنجليزية — واتركه فارغًا فيرى العربي",
            en: "Read by English-language users — leave blank to fall back to Arabic" },
  viaEmail: { ar: "إرسال بالبريد أيضًا", en: "Send by email too" },
  emailHint: { ar: "يصل داخل النظام دائمًا — والبريد باختيارك",
               en: "Always delivered in-app — email is your choice" },
  attach: { ar: "مرفقات", en: "Attachments" },
  addFile: { ar: "أضف ملفًا", en: "Add file" },
  fileHint: { ar: "PDF أو صورة — خمسة كحدّ أقصى",
              en: "PDF or image — five max" },
  send: { ar: "إرسال الآن", en: "Send now" },
  sending: { ar: "جارٍ الإرسال…", en: "Sending…" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  sentTo: { ar: "أُرسل إلى", en: "Sent to" },
  people: { ar: "موظفًا", en: "people" },
  history: { ar: "ما أُرسل", en: "Sent announcements" },
  empty: { ar: "لا إعلانات بعد", en: "No announcements yet" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noAccess: { ar: "لا تملك صلاحية إرسال الإعلانات",
              en: "You cannot send announcements" },
  required: { ar: "العنوان والنص مطلوبان", en: "Title and body are required" },
  confirmTitle: { ar: "تأكيد الإرسال", en: "Confirm sending" },
  confirmBody: { ar: "سيصل هذا الإعلان فورًا ولا يمكن سحبه بعد إرساله.",
                 en: "This is delivered immediately and cannot be recalled." },
  confirmYes: { ar: "نعم، أرسل", en: "Yes, send" },
};

const KINDS = ["general", "event", "meeting", "congrats",
               "condolence", "decision"] as const;
const KIND_COLOR: Record<string, string> = {
  general: "var(--ink-3)", event: "var(--teal)", meeting: "var(--teal)",
  congrats: "var(--ok)", condolence: "var(--ink-2)", decision: "var(--copper)",
};

type Dept = { id: number; name_ar: string; name_en?: string };
type Row = {
  id: number; kind: string; title: string; body: string;
  audience_type: string; via_email: boolean;
  recipient_count: number; sent_at: string | null;
  attachments: { id: number; name: string }[];
};

export default function AnnouncementsPage() {
  const { L, lang } = useT(T);
  const [perms, setPerms] = useState<string[]>([]);
  const [rows, setRows] = useState<Row[]>([]);
  const [depts, setDepts] = useState<Dept[]>([]);
  const [busy, setBusy] = useState(true);
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [sending, setSending] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const [kind, setKind] = useState<string>("general");
  const [aud, setAud] = useState<string>("company");
  const [audIds, setAudIds] = useState<number[]>([]);
  const [tAr, setTAr] = useState(""); const [tEn, setTEn] = useState("");
  const [bAr, setBAr] = useState(""); const [bEn, setBEn] = useState("");
  const [viaEmail, setViaEmail] = useState(false);
  const [files, setFiles] = useState<{ id: number; name: string }[]>([]);

  const canCompany = perms.includes("announcements.send_company");
  const canDept = perms.includes("announcements.send_department");
  const canSend = canCompany || canDept;

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const p = await apiGet<{ permissions: string[] }>("/me/workspace/");
      setPerms(p.permissions || []);
      const d = await apiGet<Row[]>("/announcements/");
      setRows(d);
      const dp = await apiGet<Dept[]>("/org/departments/").catch(() => []);
      setDepts(Array.isArray(dp) ? dp : []);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const reset = () => {
    setKind("general"); setAud(canCompany ? "company" : "departments");
    setAudIds([]); setTAr(""); setTEn(""); setBAr(""); setBEn("");
    setViaEmail(false); setFiles([]);
  };

  const upload = async (f: File) => {
    const form = new FormData();
    form.append("file", f);
    try {
      const r = await fetch("/api/files/", {
        method: "POST", body: form,
        headers: { Authorization: `Bearer ${sessionStorage.getItem("muatmd_hr_token")}` },
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d?.detail || "تعذّر الرفع");
      setFiles((x) => [...x, { id: d.id, name: d.original_name || f.name }]);
    } catch (e) {
      setErr(String((e as Error).message));
    }
  };

  const send = async () => {
    setConfirm(false); setSending(true); setErr("");
    try {
      const d = await apiPost<Row>("/announcements/", {
        kind, audience_type: aud, audience_ids: audIds,
        title_ar: tAr, title_en: tEn, body_ar: bAr, body_en: bEn,
        via_email: viaEmail, file_ids: files.map((f) => f.id),
      });
      setMsg(`${L("sentTo")} ${d.recipient_count} ${L("people")}`);
      setTimeout(() => setMsg(""), 5000);
      setOpen(false); reset(); await load();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setSending(false); }
  };

  const tryStart = () => {
    if (!tAr.trim() || !bAr.trim()) { setErr(L("required")); return; }
    setErr(""); setConfirm(true);
  };

  if (busy) return <div className="card" style={{ padding: 40,
    textAlign: "center", color: "var(--ink-3)" }}>{L("loading")}</div>;

  if (!canSend) return (
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
            {L("subtitle")}
          </div>
        </div>
        {!open && (
          <button className="btn btn-primary" onClick={() => { reset(); setOpen(true); }}>
            <IcPlus size={16} /> {L("neu")}
          </button>
        )}
      </div>

      {msg && <div className="card" style={{ borderColor: "var(--ok)" }}>
        <IcCheck /> {msg}
      </div>}
      {err && <div className="card" style={{ borderColor: "var(--danger)" }}>
        <IcAlert /> {err}
      </div>}

      {open && (
        <div className="card" style={{ padding: 22 }}>
          <div className="stack" style={{ gap: 16 }}>
            <div className="field">
              <label className="label">{L("kind")}</label>
              <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                {KINDS.map((k) => (
                  <button key={k} type="button"
                    className={`btn btn-sm ${kind === k ? "btn-primary" : "btn-ghost"}`}
                    onClick={() => setKind(k)}
                    style={kind === k ? undefined
                      : { color: KIND_COLOR[k] }}>
                    {L(k)}
                  </button>
                ))}
              </div>
            </div>

            <div className="field">
              <label className="label">{L("audience")}</label>
              <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                {canCompany && (
                  <button type="button"
                    className={`btn btn-sm ${aud === "company" ? "btn-primary" : "btn-ghost"}`}
                    onClick={() => { setAud("company"); setAudIds([]); }}>
                    {L("company")}
                  </button>
                )}
                <button type="button"
                  className={`btn btn-sm ${aud === "departments" ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => { setAud("departments"); setAudIds([]); }}>
                  {L("departments")}
                </button>
              </div>
            </div>

            {aud === "departments" && (
              <div className="field">
                <label className="label">{L("pickDept")}</label>
                <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                  {depts.map((d) => {
                    const on = audIds.includes(d.id);
                    return (
                      <button key={d.id} type="button"
                        className={`btn btn-sm ${on ? "btn-primary" : "btn-ghost"}`}
                        onClick={() => setAudIds((x) =>
                          on ? x.filter((i) => i !== d.id) : [...x, d.id])}>
                        {(lang === "en" ? d.name_en : d.name_ar) || d.name_ar}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="row" style={{ flexWrap: "wrap", gap: 14,
                                          alignItems: "flex-start" }}>
              <div className="field" style={{ flex: "1 1 260px", minWidth: 260 }}>
                <label className="label">{L("titleAr")}</label>
                <input className="input" value={tAr}
                       onChange={(e) => setTAr(e.target.value)} />
              </div>
              <div className="field" style={{ flex: "1 1 260px", minWidth: 260 }}>
                <label className="label">{L("titleEn")}</label>
                <input className="input" value={tEn} dir="ltr"
                       onChange={(e) => setTEn(e.target.value)} />
              </div>
            </div>

            <div className="field">
              <label className="label">{L("bodyAr")}</label>
              <textarea className="textarea" rows={4} value={bAr}
                        onChange={(e) => setBAr(e.target.value)} />
            </div>
            <div className="field">
              <label className="label">{L("bodyEn")}</label>
              <textarea className="textarea" rows={3} value={bEn} dir="ltr"
                        onChange={(e) => setBEn(e.target.value)} />
              <span className="muted" style={{ fontSize: ".8rem" }}>
                {L("enHint")}
              </span>
            </div>

            <div className="field">
              <label className="label">{L("attach")}</label>
              <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
                {files.map((f) => (
                  <span key={f.id} className="btn btn-sm">
                    <IcDoc size={14} /> {f.name}
                    <button type="button" className="btn-ghost"
                      style={{ border: "none", background: "none",
                               cursor: "pointer", padding: 0 }}
                      onClick={() => setFiles((x) => x.filter((y) => y.id !== f.id))}>
                      <IcX size={13} />
                    </button>
                  </span>
                ))}
                {files.length < 5 && (
                  <label className="btn btn-sm" style={{ cursor: "pointer" }}>
                    <IcPlus size={14} /> {L("addFile")}
                    <input type="file" style={{ display: "none" }}
                           accept=".pdf,image/*"
                           onChange={(e) => {
                             const f = e.target.files?.[0];
                             if (f) upload(f);
                             e.target.value = "";
                           }} />
                  </label>
                )}
              </div>
              <span className="muted" style={{ fontSize: ".8rem" }}>
                {L("fileHint")}
              </span>
            </div>

            <label className="row" style={{ gap: 8, cursor: "pointer" }}>
              <input type="checkbox" checked={viaEmail}
                     onChange={(e) => setViaEmail(e.target.checked)} />
              <span>
                {L("viaEmail")}
                <span className="muted" style={{ fontSize: ".8rem",
                                                 marginInlineStart: 8 }}>
                  {L("emailHint")}
                </span>
              </span>
            </label>

            <div className="row" style={{ gap: 8 }}>
              <button className="btn btn-primary" onClick={tryStart}
                      disabled={sending}>
                {sending ? L("sending") : L("send")}
              </button>
              <button className="btn" onClick={() => { setOpen(false); reset(); }}>
                {L("cancel")}
              </button>
            </div>
          </div>
        </div>
      )}

      <h3 style={{ margin: "6px 0 0" }}>{L("history")}</h3>
      {rows.length === 0 ? (
        <div className="card" style={{ padding: 34, textAlign: "center",
                                       color: "var(--ink-3)" }}>
          {L("empty")}
        </div>
      ) : (
        <div className="stack" style={{ gap: 10 }}>
          {rows.map((a) => (
            <div key={a.id} className="card" style={{
              padding: 16,
              borderInlineStartWidth: 3, borderInlineStartStyle: "solid",
              borderInlineStartColor: KIND_COLOR[a.kind] || "var(--line)",
            }}>
              <div className="spread" style={{ alignItems: "flex-start" }}>
                <div style={{ fontWeight: 600 }}>{a.title}</div>
                <span className="muted" style={{ fontSize: ".76rem",
                                                 flexShrink: 0 }}>
                  {a.recipient_count} {L("people")}
                  {a.via_email ? " · ✉" : ""}
                </span>
              </div>
              <div style={{ fontSize: ".74rem", marginTop: 3,
                            color: KIND_COLOR[a.kind] || "var(--ink-3)" }}>
                {L(a.kind, a.kind)}
              </div>
              <div className="muted" style={{ marginTop: 6, fontSize: ".88rem",
                                              lineHeight: 1.6 }}>
                {a.body}
              </div>
            </div>
          ))}
        </div>
      )}

      {confirm && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(16,28,38,.45)",
          display: "grid", placeItems: "center", padding: 20, zIndex: 70,
        }} onClick={() => setConfirm(false)}>
          <div className="card" style={{ padding: 26, maxWidth: 420,
                                         width: "100%" }}
               onClick={(e) => e.stopPropagation()}>
            <h3 style={{ margin: "0 0 8px" }}>{L("confirmTitle")}</h3>
            <div className="muted" style={{ fontSize: ".9rem",
                                            lineHeight: 1.7 }}>
              {L("confirmBody")}
            </div>
            <div className="row" style={{ gap: 8, marginTop: 20 }}>
              <button className="btn btn-primary" onClick={send}>
                {L("confirmYes")}
              </button>
              <button className="btn" onClick={() => setConfirm(false)}>
                {L("cancel")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
