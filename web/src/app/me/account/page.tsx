"use client";

/**
 * حسابي — الإعدادات الشخصية (ق-58).
 *
 * ثلاثة أقسام لا غير: الصورة، واللغة، وكلمة المرور.
 * إعدادات الشركة شيء آخر تمامًا ولها شاشتها.
 */
import { useEffect, useRef, useState } from "react";

import { apiGet, apiPost, apiPut, API_BASE, ApiError, getToken } from "@/lib/api";
import { useT, usePrefs, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcUser } from "@/components/Icons";

const T: Dict = {
  title: { ar: "حسابي", en: "My account" },
  subtitle: {
    ar: "صورتك ولغتك وكلمة مرورك",
    en: "Your photo, language and password",
  },
  photo: { ar: "الصورة الشخصية", en: "Profile photo" },
  photoHint: {
    ar: "تُصغَّر تلقائيًا — JPG أو PNG حتى 2 ميغابايت",
    en: "Auto-resized — JPG or PNG up to 2 MB",
  },
  upload: { ar: "رفع صورة", en: "Upload" },
  changePhoto: { ar: "تغيير", en: "Change" },
  removePhoto: { ar: "إزالة", en: "Remove" },
  uploading: { ar: "جارٍ الرفع…", en: "Uploading…" },
  language: { ar: "لغة النظام", en: "System language" },
  languageHint: {
    ar: "تُستخدم في الإشعارات والقسائم المرسلة لك",
    en: "Used in notifications and payslips sent to you",
  },
  password: { ar: "كلمة المرور", en: "Password" },
  currentPassword: { ar: "كلمة المرور الحالية", en: "Current password" },
  newPassword: { ar: "كلمة المرور الجديدة", en: "New password" },
  confirmPassword: { ar: "تأكيد الجديدة", en: "Confirm" },
  passwordHint: {
    ar: "تغييرها يُخرجك من كل الأجهزة",
    en: "Changing it signs you out everywhere",
  },
  changePassword: { ar: "تغيير كلمة المرور", en: "Change password" },
  changing: { ar: "جارٍ التغيير…", en: "Changing…" },
  mismatch: { ar: "الكلمتان غير متطابقتين", en: "Passwords do not match" },
  changed: { ar: "غُيّرت كلمة المرور", en: "Password changed" },
  save: { ar: "حفظ", en: "Save" },
  saved: { ar: "حُفظ", en: "Saved" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  noProfile: { ar: "لا ملف موظف مرتبط بحسابك", en: "No profile linked" },
  username: { ar: "اسم المستخدم", en: "Username" },
  email: { ar: "البريد", en: "Email" },
  mobile: { ar: "الجوال", en: "Mobile" },
  contactHint: {
    ar: "لتعديل بريدك أو جوالك راجع مدير الموارد البشرية",
    en: "Contact HR to change your email or mobile",
  },
};

// اللغات المدعومة فعلًا في الواجهة والإشعارات.
// تُضاف لغة هنا حين تُترجم، لا قبلها — فالخيار الذي لا يعمل
// أسوأ من غيابه.
const LOCALES: [string, string][] = [
  ["ar", "العربية"],
  ["en", "English"],
];

type Account = {
  username: string;
  name_ar: string;
  email: string;
  mobile: string;
  preferred_locale: string;
  avatar_url: string | null;
};

export default function MyAccountPage() {
  const { L } = useT(T);
  const fileRef = useRef<HTMLInputElement>(null);

  const [data, setData] = useState<Account | null>(null);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);

  const [locale, setLocale] = useState("ar");
  const [savingLocale, setSavingLocale] = useState(false);
  const [localeSaved, setLocaleSaved] = useState(false);

  const [uploading, setUploading] = useState(false);
  const [photoError, setPhotoError] = useState("");
  const [bump, setBump] = useState(0);      // لكسر ذاكرة الصورة

  const [cur, setCur] = useState("");
  const [nw, setNw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwMsg, setPwMsg] = useState("");
  const [pwError, setPwError] = useState("");

  const load = () => {
    apiGet<Account>("/me/account/")
      .then((d) => {
        setData(d);
        setLocale(d.preferred_locale || "ar");
        setBusy(false);
      })
      .catch(() => { setDenied(true); setBusy(false); });
  };

  useEffect(load, []);

  async function saveLocale() {
    setSavingLocale(true);
    try {
      await apiPut("/me/account/", { preferred_locale: locale });
      setLocaleSaved(true);
      setTimeout(() => setLocaleSaved(false), 2500);
    } catch { /* تجاهل */ }
    finally { setSavingLocale(false); }
  }

  async function uploadPhoto(file: File) {
    setUploading(true);
    setPhotoError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/me/avatar/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
        body: form,
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || "تعذّر الرفع");
      }
      setBump((b) => b + 1);
      load();
    } catch (e) {
      setPhotoError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }

  async function removePhoto() {
    setUploading(true);
    try {
      await fetch(`${API_BASE}/me/avatar/`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      setBump((b) => b + 1);
      load();
    } finally { setUploading(false); }
  }

  async function changePassword() {
    setPwError("");
    setPwMsg("");
    if (nw !== confirm) { setPwError(L("mismatch")); return; }

    setPwBusy(true);
    try {
      await apiPost("/me/password/", {
        current_password: cur, new_password: nw,
      });
      setPwMsg(L("changed"));
      setCur(""); setNw(""); setConfirm("");
      setTimeout(() => { window.location.href = "/login"; }, 2000);
    } catch (e) {
      setPwError((e as ApiError).message);
    } finally {
      setPwBusy(false);
    }
  }

  if (busy) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
        {L("loading")}
      </div>
    );
  }

  if (denied || !data) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        <IcAlert size={22} />
        <div style={{ marginTop: 8 }}>{L("noProfile")}</div>
      </div>
    );
  }

  const avatarSrc = data.avatar_url
    ? `${API_BASE}${data.avatar_url}?v=${bump}`
    : null;

  return (
    <div className="stack">
      <div>
        <h1>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {L("subtitle")}
        </div>
      </div>

      {/* ══ الصورة ══ */}
      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>{L("photo")}</h2>
        <div className="muted" style={{ fontSize: ".84rem", marginBottom: 14 }}>
          {L("photoHint")}
        </div>

        <div className="row" style={{ gap: 18, alignItems: "center" }}>
          <div style={{
            width: 92, height: 92, borderRadius: "50%",
            background: "var(--paper-2)", overflow: "hidden",
            display: "grid", placeItems: "center", flexShrink: 0,
            border: "2px solid var(--line)",
          }}>
            {avatarSrc ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={avatarSrc} alt="" style={{
                width: "100%", height: "100%", objectFit: "cover",
              }} />
            ) : (
              <span style={{ color: "var(--ink-3)" }}>
                <IcUser size={38} />
              </span>
            )}
          </div>

          <div className="stack" style={{ gap: 8 }}>
            <div style={{ fontWeight: 600 }}>{data.name_ar}</div>
            <div className="row" style={{ gap: 8 }}>
              <button className="btn btn-sm btn-primary" disabled={uploading}
                onClick={() => fileRef.current?.click()}>
                {uploading ? L("uploading")
                  : avatarSrc ? L("changePhoto") : L("upload")}
              </button>
              {avatarSrc && (
                <button className="btn btn-sm btn-ghost" disabled={uploading}
                  style={{ color: "var(--danger)" }} onClick={removePhoto}>
                  {L("removePhoto")}
                </button>
              )}
            </div>
            {photoError && (
              <div style={{ color: "var(--danger)", fontSize: ".85rem" }}>
                {photoError}
              </div>
            )}
          </div>
        </div>

        <input ref={fileRef} type="file" hidden
          accept="image/jpeg,image/png,image/webp"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) uploadPhoto(f);
            e.target.value = "";
          }} />
      </div>

      {/* ══ اللغة ══ */}
      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>{L("language")}</h2>
        <div className="muted" style={{ fontSize: ".84rem", marginBottom: 14 }}>
          {L("languageHint")}
        </div>

        <div className="row" style={{ alignItems: "flex-end" }}>
          <div className="field" style={{ maxWidth: 220 }}>
            <select className="select" value={locale}
              onChange={(e) => setLocale(e.target.value)}>
              {LOCALES.map(([code, name]) => (
                <option key={code} value={code}>{name}</option>
              ))}
            </select>
          </div>
          <button className="btn btn-primary" disabled={savingLocale}
            onClick={saveLocale}>
            {savingLocale ? "…" : L("save")}
          </button>
          {localeSaved && (
            <span className="badge badge-ok">
              <IcCheck size={14} /> {L("saved")}
            </span>
          )}
        </div>
      </div>

      {/* ══ كلمة المرور ══ */}
      <div className="card" style={{ padding: 20 }}>
        <h2 style={{ fontSize: "1rem", marginBottom: 4 }}>{L("password")}</h2>
        <div className="muted" style={{ fontSize: ".84rem", marginBottom: 14 }}>
          {L("passwordHint")}
        </div>

        <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="field" style={{ maxWidth: 220 }}>
            <label className="label">{L("currentPassword")}</label>
            <input className="input" type="password" dir="ltr" value={cur}
              autoComplete="current-password"
              onChange={(e) => setCur(e.target.value)} />
          </div>
          <div className="field" style={{ maxWidth: 220 }}>
            <label className="label">{L("newPassword")}</label>
            <input className="input" type="password" dir="ltr" value={nw}
              autoComplete="new-password"
              onChange={(e) => setNw(e.target.value)} />
          </div>
          <div className="field" style={{ maxWidth: 220 }}>
            <label className="label">{L("confirmPassword")}</label>
            <input className="input" type="password" dir="ltr" value={confirm}
              autoComplete="new-password"
              onChange={(e) => setConfirm(e.target.value)} />
          </div>
          <button className="btn btn-primary"
            disabled={pwBusy || !cur || !nw || !confirm}
            onClick={changePassword}>
            {pwBusy ? L("changing") : L("changePassword")}
          </button>
        </div>

        {pwError && (
          <div style={{
            marginTop: 12, background: "var(--danger-soft)",
            color: "var(--danger)", padding: "10px 13px",
            borderRadius: "var(--radius-sm)", fontSize: ".88rem",
          }}>
            {pwError}
          </div>
        )}
        {pwMsg && (
          <div style={{
            marginTop: 12, background: "var(--ok-soft)", color: "var(--ok)",
            padding: "10px 13px", borderRadius: "var(--radius-sm)",
            fontSize: ".88rem",
          }}>
            {pwMsg}
          </div>
        )}
      </div>

      {/* ══ بيانات لا تُعدَّل هنا ══ */}
      <div className="card" style={{ padding: 20 }}>
        <div className="muted" style={{ fontSize: ".84rem", marginBottom: 12 }}>
          {L("contactHint")}
        </div>
        {[
          [L("username"), data.username],
          [L("email"), data.email],
          [L("mobile"), data.mobile],
        ].map(([k, v]) => (
          <div key={k} className="spread" style={{
            padding: "8px 0", borderBottom: "1px solid var(--line)",
          }}>
            <span className="muted" style={{ fontSize: ".86rem" }}>{k}</span>
            <span className="num">{v || "—"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
