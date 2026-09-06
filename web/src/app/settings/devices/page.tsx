"use client";

/**
 * أجهزة البصمة.
 *
 * والمفتاح يُعرض مرة واحدة عند الإنشاء: من يقرأ القاعدة لا ينتحل
 * جهازًا، ومن ينساه يُنشئ جهازًا جديدًا.
 */
import { useCallback, useEffect, useState } from "react";

import { apiDelete, apiGet, apiPost, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import ConfirmDialog from "@/components/ConfirmDialog";
import { IcAlert, IcCheck, IcClock, IcPlus, IcX } from "@/components/Icons";

const T: Dict = {
  title: { ar: "أجهزة البصمة", en: "Punch devices" },
  subtitle: {
    ar: "الأجهزة المصرَّح لها بإرسال البصمات",
    en: "Devices allowed to submit punches",
  },
  add: { ar: "جهاز جديد", en: "New device" },
  code: { ar: "رمز الجهاز", en: "Device code" },
  name: { ar: "الاسم", en: "Name" },
  site: { ar: "الموقع", en: "Site" },
  noSite: { ar: "بلا موقع", en: "No site" },
  lastSeen: { ar: "آخر اتصال", en: "Last seen" },
  never: { ar: "لم يتصل بعد", en: "Never" },
  status: { ar: "الحالة", en: "Status" },
  active: { ar: "نشط", en: "Active" },
  inactive: { ar: "معطّل", en: "Inactive" },
  edit: { ar: "تعديل", en: "Edit" },
  del: { ar: "حذف", en: "Delete" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا أجهزة", en: "No devices" },
  noAccess: {
    ar: "لا تملك صلاحية إدارة الأجهزة",
    en: "You cannot manage devices",
  },
  confirmDelete: {
    ar: "حذف الجهاز؟ لن يستطيع إرسال بصمات بعدها.",
    en: "Delete? It will no longer submit punches.",
  },
  codeHint: {
    ar: "الرمز لا يُعدَّل — الجهاز يُصادق به",
    en: "The code cannot change — the device authenticates with it",
  },
  keyTitle: { ar: "مفتاح الجهاز", en: "Device key" },
  keyHint: {
    ar: "احفظه الآن — لا يُعرض مرة أخرى، ومن ينساه يُنشئ جهازًا جديدًا",
    en: "Save it now — it is never shown again",
  },
  copy: { ar: "نسخ", en: "Copy" },
  copied: { ar: "نُسخ", en: "Copied" },
  close: { ar: "إغلاق", en: "Close" },
  showGuide: { ar: "دليل الربط", en: "Integration guide" },
  hideGuide: { ar: "إخفاء الدليل", en: "Hide guide" },
  guideTitle: {
    ar: "ربط الأجهزة بالنظام",
    en: "Connecting devices",
  },
  ingestUrl: { ar: "رابط إرسال البصمات", en: "Ingest URL" },
  pingUrl: { ar: "رابط فحص الاتصال", en: "Ping URL" },
  headers: { ar: "الترويسات", en: "Headers" },
  bodyExample: { ar: "مثال الجسم", en: "Body example" },
  notes: { ar: "ملاحظات", en: "Notes" },
  wayBiotime: { ar: "عبر BioTime", en: "Via BioTime" },
  wayAgent: { ar: "برمجية معتمد", en: "Muatmd agent" },

  // ق-84: النصوص هنا لا في الخادم — فالواجهة تعرف لغة المستخدم
  bt1: {
    ar: "في BioTime: النظام ← إعدادات ← إعدادات FTP ← أضف",
    en: "In BioTime: System → Settings → FTP settings → Add",
  },
  bt2: {
    ar: "اختر SFTP، وأدخل المضيف والمنفذ واسم المستخدم وكلمة المرور",
    en: "Choose SFTP, then enter host, port, username and password",
  },
  bt3: {
    ar: "ثم: النظام ← تكامل ← تصدير تلقائي ← أضف",
    en: "Then: System → Integration → Auto export → Add",
  },
  bt4: {
    ar: "الشكل CSV، والتاريخ yyyy-MM-DD، والوقت HH:mm:ss",
    en: "Format CSV, date yyyy-MM-DD, time HH:mm:ss",
  },
  bt5: {
    ar: "قالب البيانات (مفصولًا بـTab):",
    en: "Data template (Tab separated):",
  },
  bt6: {
    ar: "في تبويب الوقت: فترة 5 دقائق أو أقل",
    en: "In the time tab: interval of 5 minutes or less",
  },
  bt7: {
    ar: "في مسار التصدير: اكتب upload",
    en: "In the export path: enter upload",
  },
  btNote: {
    ar: "كلمة المرور تُسلَّم عند إنشاء الحساب — راجع مزوّد الخدمة إن فقدتها",
    en: "The password is issued when the account is created",
  },

  ag1: {
    ar: "نزّل حزمة الوسيط، وفكّها في مجلد على جهاز يعمل دائمًا داخل شبكتك",
    en: "Download the agent package to an always-on machine on your network",
  },
  ag2: {
    ar: "شغّل muatmd-agent-setup.exe",
    en: "Run muatmd-agent-setup.exe",
  },
  ag3: {
    ar: "أدخل رمز الجهاز ومفتاحه من هذه الشاشة، وعنوان جهاز البصمة في شبكتك",
    en: "Enter the device code and key from this screen, and the device address",
  },
  ag4: {
    ar: "اضغط «فحص الاتصال» — لا تكمل حتى يقول «سليم بالطرفين»",
    en: "Press Test connection — do not continue until both sides pass",
  },
  ag5: {
    ar: "اضغط «حفظ» ثم أغلق النافذة",
    en: "Press Save, then close the window",
  },
  ag6: {
    ar: "افتح PowerShell بصلاحية مسؤول في مجلد الحزمة ونفّذ install-service.ps1",
    en: "Open PowerShell as admin in the package folder and run install-service.ps1",
  },
  ag7: {
    ar: "يعمل الوسيط خدمةً تبدأ مع الجهاز — ولا يحتاج فتحه كل صباح",
    en: "The agent runs as a service that starts with the machine",
  },
  agN1: {
    ar: "الوسيط يقرأ من الجهاز كل خمس دقائق ويرفع الجديد وحده.",
    en: "The agent reads every five minutes and uploads only what is new.",
  },
  agN2: {
    ar: "ولا تضيع بصمة بانقطاع: ما تراكم يُرفع عند عودة الاتصال.",
    en: "No punch is lost: what accumulates is uploaded when connectivity returns.",
  },
  agN3: {
    ar: "والسجل في agent.log بجانب الوسيط — منه تعرف ما جرى.",
    en: "The log is in agent.log next to the agent.",
  },

  hN1: {
    ar: "رقم الموظف على الجهاز هو الرقم الوظيفي في النظام.",
    en: "The employee number on the device is the one in the system.",
  },
  hN2: {
    ar: "البصمة تُسجَّل بوقتها الأصلي لا بوقت وصولها — فارفع المتأخرة بتواريخها.",
    en: "Punches are stored at their own time, not arrival time.",
  },
  hN3: {
    ar: "الرفع المتكرّر آمن: البصمة نفسها لا تُحتسب مرتين.",
    en: "Re-uploading is safe: the same punch is never counted twice.",
  },
  hN4: {
    ar: "والبصمة تُميَّز بالجهاز والموظف والوقت بالثانية لا بمعرّف ترسله أنت.",
    en: "A punch is identified by device, employee and time to the second.",
  },
  hN5: {
    ar: "جرّب ping أولًا: يؤكّد أن الرمز والمفتاح صحيحان قبل أن تبدأ.",
    en: "Try ping first: it confirms the code and key before you start.",
  },
  maxBatch: { ar: "أقصى دفعة", en: "Max batch" },
  punch: { ar: "بصمة", en: "punches" },
  template: { ar: "قالب البيانات", en: "Data template" },
  wayHttp: { ar: "ربط مباشر", en: "Direct" },
  agentTitle: {
    ar: "الربط ببرمجية معتمد — لمن لا BioTime عنده",
    en: "Muatmd agent — for those without BioTime",
  },
  biotimeTitle: {
    ar: "الربط عبر BioTime (SFTP)",
    en: "Connecting via BioTime (SFTP)",
  },
  httpTitle: {
    ar: "الربط المباشر (HTTP)",
    en: "Direct integration (HTTP)",
  },
  sftpHost: { ar: "المضيف", en: "Host" },
  sftpPort: { ar: "المنفذ", en: "Port" },
  sftpUser: { ar: "المستخدم", en: "Username" },
  sftpPath: { ar: "مسار الرفع", en: "Upload path" },
};

type Device = {
  id: number;
  device_code: string;
  name_ar: string;
  site: string | null;
  site_id: number | null;
  last_seen_at: string | null;
  is_active: boolean;
};

type Site = { id: number; name_ar: string };

type Guide = {
  ingest_url: string;
  ping_url: string;
  max_batch: number;
  fields: string[];
  body_example: unknown;
  biotime_template: string;
  sftp?: {
    host: string;
    port: number;
    username: string;
    upload_path: string;
    protocol: string;
  };
};

export default function DevicesPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Device[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [askDel, setAskDel] = useState<number | null>(null);
  const [newKey, setNewKey] = useState("");
  const [copied, setCopied] = useState(false);
  /** دليل الربط: من يشتري جهازًا يحتاج الرابط والترويسات */
  const [guide, setGuide] = useState<Guide | null>(null);
  const [showGuide, setShowGuide] = useState(false);
  /**
   * الطريقتان منفصلتان: من عنده BioTime لا يعنيه HTTP،
   * وعرضهما معًا يربك من يبحث عن إعداده.
   */
  const [way, setWay] = useState<"biotime" | "agent" | "http">(
    "biotime");

  const load = useCallback(() => {
    apiGet<Device[]>("/attendance/devices/")
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
        setCanEdit((d.permissions || []).includes("sites.manage")))
      .catch(() => setCanEdit(false));
    apiGet<Site[]>("/sites/").then(setSites).catch(() => setSites([]));
    apiGet<Guide>("/attendance/devices/guide/")
      .then(setGuide).catch(() => setGuide(null));
  }, []);

  async function save() {
    setSaving(true);
    setErr("");
    try {
      if (editing === "new") {
        const r = await apiPost<{ api_key?: string }>(
          "/attendance/devices/", draft);
        if (r?.api_key) {
          setNewKey(r.api_key);
          setCopied(false);
        }
      } else {
        await apiPut(`/attendance/devices/${editing}/`, draft);
      }
      setEditing(null);
      load();
    } catch (e) {
      setErr((e as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    try {
      await apiDelete(`/attendance/devices/${id}/`);
      load();
    } catch (e) {
      setErr((e as ApiError).message);
      setTimeout(() => setErr(""), 6000);
    }
  }

  const f = (k: string) => String(draft[k] ?? "");
  const set = (k: string, v: unknown) =>
    setDraft((d) => ({ ...d, [k]: v }));

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
      <ConfirmDialog
        open={askDel !== null}
        tone="danger"
        confirmLabel={L("del")}
        message={L("confirmDelete")}
        onCancel={() => setAskDel(null)}
        onConfirm={() => {
          const id = askDel;
          setAskDel(null);
          if (id !== null) remove(id);
        }}
      />

      {/* المفتاح يُعرض مرة واحدة */}
      {newKey && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 300,
          background: "rgba(16,28,38,.45)",
          display: "grid", placeItems: "center", padding: 20,
        }}>
          <div className="card" style={{
            width: "100%", maxWidth: 520, padding: 24,
          }}>
            <h3 style={{ fontSize: "1.05rem", marginBottom: 6 }}>
              {L("keyTitle")}
            </h3>
            <div style={{
              background: "var(--copper-soft)", color: "var(--copper)",
              padding: "10px 14px", borderRadius: "var(--radius-sm)",
              fontSize: ".86rem", marginBottom: 14,
            }}>
              {L("keyHint")}
            </div>
            <div className="num" style={{
              background: "var(--paper-2)", padding: "12px 14px",
              borderRadius: "var(--radius-sm)", wordBreak: "break-all",
              fontSize: ".88rem", marginBottom: 14,
            }}>
              {newKey}
            </div>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn btn-ghost btn-sm"
                onClick={() => {
                  navigator.clipboard?.writeText(newKey);
                  setCopied(true);
                }}>
                {copied ? L("copied") : L("copy")}
              </button>
              <button className="btn btn-primary btn-sm"
                onClick={() => setNewKey("")}>
                {L("close")}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        <div className="row" style={{ gap: 8 }}>
        {guide && (
          <button className="btn btn-ghost btn-sm"
            onClick={() => setShowGuide((v) => !v)}>
            {showGuide ? L("hideGuide") : L("showGuide")}
          </button>
        )}
        {canEdit && editing === null && (
          <button className="btn btn-primary" onClick={() => {
            setDraft({ device_code: "", name_ar: "", site_id: "",
                       is_active: true });
            setEditing("new");
            setErr("");
          }}>
            <IcPlus size={17} />
            {L("add")}
          </button>
        )}
        </div>
      </div>

      {/* دليل الربط — الرابط والترويسات وشكل الجسم في مكان واحد */}
      {showGuide && guide && (
        <div className="card" style={{ padding: 20 }}>
          <h3 style={{ fontSize: "1rem", marginBottom: 12 }}>
            {L("guideTitle")}
          </h3>

          {/* ق-85: تبويبان لا قسمان — كلٌّ يرى إعداد طريقته */}
          <div className="row" style={{ gap: 6, marginBottom: 16 }}>
            <button
              className={`btn btn-sm ${
                way === "biotime" ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setWay("biotime")}>
              {L("wayBiotime")}
            </button>
            <button
              className={`btn btn-sm ${
                way === "agent" ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setWay("agent")}>
              {L("wayAgent")}
            </button>
            <button
              className={`btn btn-sm ${
                way === "http" ? "btn-primary" : "btn-ghost"}`}
              onClick={() => setWay("http")}>
              {L("wayHttp")}
            </button>
          </div>

          {/* ق-86: لمن لا BioTime عنده — برمجية على شبكته */}
          {way === "agent" && (
            <div style={{
              background: "var(--paper-2)", padding: 16,
              borderRadius: "var(--radius-sm)",
            }}>
              <div style={{
                fontWeight: 600, color: "var(--teal)", marginBottom: 10,
              }}>
                {L("agentTitle")}
              </div>

              {guide.sftp && (
                <table className="table" style={{ marginBottom: 12 }}>
                  <tbody>
                    <tr>
                      <td className="muted" style={{ width: 130 }}>
                        {L("code")}
                      </td>
                      <td>
                        <span className="num">
                          {rows[0]?.device_code || "—"}
                        </span>
                      </td>
                    </tr>
                    <tr>
                      <td className="muted">{L("ingestUrl")}</td>
                      <td>
                        <span className="num" style={{ fontSize: ".82rem" }}>
                          {guide.ingest_url.replace(
                            "/api/attendance/ingest/", "")}
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              )}

              <ol style={{
                paddingInlineStart: 20, fontSize: ".86rem",
                lineHeight: 2, color: "var(--ink-2)", margin: 0,
              }}>
                {["ag1", "ag2", "ag3", "ag4", "ag5", "ag6", "ag7"].map((k) => (
                  <li key={k}>{L(k)}</li>
                ))}
              </ol>

              <ul style={{
                  paddingInlineStart: 18, fontSize: ".84rem",
                  lineHeight: 1.9, color: "var(--ink-3)",
                  marginTop: 12, marginBottom: 0,
                }}>
                  {["agN1", "agN2", "agN3"].map((k) => (
                    <li key={k}>{L(k)}</li>
                  ))}
                </ul>
            </div>
          )}

          {way === "biotime" && guide.sftp && (
            <div style={{
              background: "var(--paper-2)", padding: 16,
              borderRadius: "var(--radius-sm)", marginBottom: 16,
            }}>
              <div style={{
                fontWeight: 600, color: "var(--teal)", marginBottom: 10,
              }}>
                {L("biotimeTitle")}
              </div>

              <table className="table" style={{ marginBottom: 12 }}>
                <tbody>
                  <tr>
                    <td className="muted" style={{ width: 130 }}>
                      {L("sftpHost")}
                    </td>
                    <td><span className="num">{guide.sftp.host}</span></td>
                  </tr>
                  <tr>
                    <td className="muted">{L("sftpPort")}</td>
                    <td><span className="num">{guide.sftp.port}</span></td>
                  </tr>
                  <tr>
                    <td className="muted">{L("sftpUser")}</td>
                    <td><span className="num">{guide.sftp.username}</span></td>
                  </tr>
                  <tr>
                    <td className="muted">{L("sftpPath")}</td>
                    <td>
                      <span className="num">{guide.sftp.upload_path}</span>
                    </td>
                  </tr>
                </tbody>
              </table>

              <div className="muted" style={{
                fontSize: ".82rem", marginBottom: 12,
              }}>
                {L("btNote")}
              </div>

              <ol style={{
                  paddingInlineStart: 20, fontSize: ".86rem",
                  lineHeight: 2, color: "var(--ink-2)", margin: 0,
                }}>
                  {["bt1", "bt2", "bt3", "bt4"].map((k) => (
                    <li key={k}>{L(k)}</li>
                  ))}
                  <li>
                    {L("bt5")}
                    <div className="num" style={{
                      fontSize: ".78rem", marginTop: 4, direction: "ltr",
                      textAlign: "left", background: "var(--paper)",
                      padding: "6px 9px",
                      borderRadius: "var(--radius-sm)",
                    }}>
                      {guide.biotime_template}
                    </div>
                  </li>
                  {["bt6", "bt7"].map((k) => (
                    <li key={k}>{L(k)}</li>
                  ))}
                </ol>
            </div>
          )}

          {way === "http" && (
          <div className="stack" style={{ gap: 10 }}>
            <div>
              <div className="label">{L("ingestUrl")}</div>
              <div className="num" style={{
                background: "var(--paper-2)", padding: "9px 12px",
                borderRadius: "var(--radius-sm)", wordBreak: "break-all",
                fontSize: ".85rem",
              }}>
                {guide.ingest_url}
              </div>
            </div>

            <div>
              <div className="label">{L("pingUrl")}</div>
              <div className="num" style={{
                background: "var(--paper-2)", padding: "9px 12px",
                borderRadius: "var(--radius-sm)", wordBreak: "break-all",
                fontSize: ".85rem",
              }}>
                {guide.ping_url}
              </div>
            </div>

            <div>
              <div className="label">{L("headers")}</div>
              <div style={{
                background: "var(--paper-2)", padding: "9px 12px",
                borderRadius: "var(--radius-sm)", fontSize: ".84rem",
              }}>
                {["X-Device-Code", "X-Device-Key", "Content-Type"].map((h) => (
                  <div key={h} style={{ marginBottom: 3 }}>
                    <span className="num">{h}</span>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="label">{L("bodyExample")}</div>
              <pre className="num" style={{
                background: "var(--paper-2)", padding: "10px 12px",
                borderRadius: "var(--radius-sm)", fontSize: ".8rem",
                overflowX: "auto", margin: 0, direction: "ltr",
                textAlign: "left",
              }}>
{JSON.stringify(guide.body_example, null, 2)}
              </pre>
            </div>

            <div>
              <div className="label">{L("notes")}</div>
              <ul style={{
                paddingInlineStart: 18, fontSize: ".86rem",
                lineHeight: 1.9, color: "var(--ink-2)",
              }}>
                {["hN1", "hN2", "hN3", "hN4", "hN5"].map((k) => (
                  <li key={k}>{L(k)}</li>
                ))}
              </ul>
            </div>
          </div>
          )}
        </div>
      )}

      {err && (
        <div style={{
          background: "var(--danger-soft)", color: "var(--danger)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
          fontSize: ".9rem",
        }}>
          {err}
        </div>
      )}

      {editing !== null && (
        <div className="card" style={{ padding: 20 }}>
          <div className="row" style={{ flexWrap: "wrap", gap: 12 }}>
            <div className="field" style={{ minWidth: 160 }}>
              <label className="label">{L("code")}</label>
              <input className="input" value={f("device_code")}
                disabled={editing !== "new"}
                onChange={(e) =>
                  set("device_code", e.target.value.toUpperCase())} />
              {editing !== "new" && (
                <div className="muted" style={{ fontSize: ".76rem" }}>
                  {L("codeHint")}
                </div>
              )}
            </div>

            <div className="field" style={{ minWidth: 200 }}>
              <label className="label">{L("name")}</label>
              <input className="input" value={f("name_ar")}
                onChange={(e) => set("name_ar", e.target.value)} />
            </div>

            <div className="field" style={{ minWidth: 180 }}>
              <label className="label">{L("site")}</label>
              <select className="select" value={f("site_id")}
                onChange={(e) => set("site_id", e.target.value)}>
                <option value="">— {L("noSite")} —</option>
                {sites.map((s) => (
                  <option key={s.id} value={s.id}>{s.name_ar}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="row" style={{ marginTop: 16 }}>
            <button className="btn btn-primary btn-sm" disabled={saving}
              onClick={save}>
              <IcCheck size={16} />
              {L("save")}
            </button>
            <button className="btn btn-ghost btn-sm"
              onClick={() => { setEditing(null); setErr(""); }}>
              <IcX size={16} />
              {L("cancel")}
            </button>
          </div>
        </div>
      )}

      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            <IcClock size={22} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  <th>{L("code")}</th>
                  <th>{L("name")}</th>
                  <th>{L("site")}</th>
                  <th>{L("lastSeen")}</th>
                  <th>{L("status")}</th>
                  <th style={{ width: 140 }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr key={d.id}>
                    <td><span className="num">{d.device_code}</span></td>
                    <td>{d.name_ar}</td>
                    <td className="muted">{d.site || L("noSite")}</td>
                    <td className="muted">
                      {d.last_seen_at
                        ? <span className="num">
                            {String(d.last_seen_at).slice(0, 16)
                              .replace("T", " ")}
                          </span>
                        : L("never")}
                    </td>
                    <td>
                      <span className={d.is_active
                        ? "badge badge-ok" : "badge"}>
                        {d.is_active ? L("active") : L("inactive")}
                      </span>
                    </td>
                    <td>
                      {canEdit && (
                        <div className="row" style={{ gap: 6 }}>
                          <button className="btn btn-sm btn-ghost"
                            onClick={() => {
                              setDraft({
                                name_ar: d.name_ar,
                                site_id: d.site_id ?? "",
                                is_active: d.is_active,
                                device_code: d.device_code,
                              });
                              setEditing(d.id);
                              setErr("");
                            }}>
                            {L("edit")}
                          </button>
                          <button className="btn btn-sm btn-ghost"
                            style={{ color: "var(--danger)" }}
                            onClick={() => setAskDel(d.id)}>
                            {L("del")}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
