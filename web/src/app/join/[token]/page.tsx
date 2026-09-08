"use client";
/**
 * قبول الدعوة للانضمام (ق-94).
 *
 * صفحة عامّة بلا توثيق: الموظف يفتحها قبل أن يملك حسابًا. تعرض
 * اسمه واسم شركته ليطمئنّ أن الرابط له، ثم يضبط كلمة مروره
 * بنفسه — فلا يعرفها أحد سواه.
 *
 * وتبدأ باللغتين معًا: لا لغة مفضّلة لمن لم يدخل النظام قطّ،
 * ويختار لغته هنا فتُحفظ في ملفّه.
 */
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { usePrefs, useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcGlobe, IcMoon, IcSun } from "@/components/Icons";

const T: Dict = {
  subtitle: { ar: "نظام الموارد البشرية — معتمد", en: "Muatmd HR System" },
  welcome: { ar: "مرحبًا", en: "Welcome" },
  invitedTo: { ar: "دُعيت للانضمام إلى", en: "You have been invited to join" },
  setPassword: { ar: "تعيين كلمة المرور", en: "Set your password" },
  password: { ar: "كلمة المرور", en: "Password" },
  confirm: { ar: "تأكيد كلمة المرور", en: "Confirm password" },
  hint: {
    ar: "ثمانية أحرف فأكثر، ولا تكن أرقامًا فقط",
    en: "At least 8 characters, not digits only",
  },
  mismatch: { ar: "الكلمتان غير متطابقتين", en: "Passwords do not match" },
  submit: { ar: "تفعيل حسابي", en: "Activate my account" },
  submitting: { ar: "جارٍ التفعيل…", en: "Activating…" },
  loading: { ar: "جارٍ التحقّق من الدعوة…", en: "Checking invitation…" },
  done: { ar: "فُعّل حسابك", en: "Your account is active" },
  doneHint: {
    ar: "ادخل ببريدك أو رقم هويتك أو جوالك وكلمة المرور التي اخترتها",
    en: "Sign in with your email, ID number or mobile and your new password",
  },
  toLogin: { ar: "الذهاب لتسجيل الدخول", en: "Go to sign in" },
  expired: {
    ar: "انتهت صلاحية هذه الدعوة أو استُعملت من قبل",
    en: "This invitation has expired or was already used",
  },
  notFound: {
    ar: "رابط الدعوة غير صحيح",
    en: "This invitation link is not valid",
  },
  askHr: {
    ar: "راجع إدارة الموارد البشرية في شركتك لإعادة إرسالها",
    en: "Ask your HR department to send it again",
  },
  network: { ar: "تعذّر الاتصال بالخادم", en: "Cannot reach the server" },
};

type Preview = {
  valid: boolean;
  name: string;
  company_ar: string;
  company_en: string;
  default_locale: string;
};

export default function JoinPage() {
  const router = useRouter();
  const params = useParams<{ token: string }>();
  const token = params?.token || "";
  const { lang, theme, toggleLang, setTheme } = usePrefs();
  const { L } = useT(T);

  const [info, setInfo] = useState<Preview | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "bad" | "done">(
    "loading");
  const [badCode, setBadCode] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const d = await apiGet<Preview>(`/join/${token}/`);
      setInfo(d);
      setState("ready");
    } catch (e) {
      const err = e as ApiError;
      setBadCode(err.status === 410 ? "expired" : "notFound");
      setState("bad");
    }
  }, [token]);

  useEffect(() => { if (token) load(); }, [token, load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (pw !== pw2) { setError(L("mismatch")); return; }
    setBusy(true);
    try {
      await apiPost(`/join/${token}/accept/`, { password: pw, locale: lang });
      setState("done");
    } catch (e) {
      const err = e as ApiError;
      // ApiError.message يحمل detail من الخادم — وهو بالعربية.
      setError(err.isNetwork ? L("network") : err.message);
      setBusy(false);
    }
  }

  const shell = (children: React.ReactNode) => (
    <div style={{
      minHeight: "100vh", display: "grid", placeItems: "center",
      background: "var(--paper-2)", padding: 20,
    }}>
      <div style={{ width: "100%", maxWidth: 420 }}>
        <div className="row" style={{ justifyContent: "flex-end", marginBottom: 16 }}>
          <button className="btn btn-ghost btn-sm" onClick={toggleLang}>
            <IcGlobe size={17} />
            {lang === "ar" ? "EN" : "ع"}
          </button>
          <button className="btn btn-ghost btn-sm"
                  onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? <IcSun size={17} /> : <IcMoon size={17} />}
          </button>
        </div>
        <div className="card" style={{ padding: 32 }}>
          <div style={{ textAlign: "center", marginBottom: 26 }}>
            <div style={{
              fontSize: "1.7rem", fontWeight: 600, color: "var(--teal)",
              marginBottom: 4,
            }}>معتمد</div>
            <div className="muted" style={{ fontSize: ".92rem" }}>
              {L("subtitle")}
            </div>
          </div>
          {children}
        </div>
      </div>
    </div>
  );

  if (state === "loading") return shell(
    <div className="muted" style={{ textAlign: "center" }}>{L("loading")}</div>);

  if (state === "bad") return shell(
    <div style={{ textAlign: "center" }}>
      <div style={{ color: "var(--danger)", marginBottom: 10 }}>
        <IcAlert size={26} />
      </div>
      <div style={{ fontWeight: 500, marginBottom: 8 }}>{L(badCode)}</div>
      <div className="muted" style={{ fontSize: ".88rem", marginBottom: 20 }}>
        {L("askHr")}
      </div>
      <button className="btn" onClick={() => router.replace("/login")}>
        {L("toLogin")}
      </button>
    </div>);

  if (state === "done") return shell(
    <div style={{ textAlign: "center" }}>
      <div style={{ color: "var(--ok)", marginBottom: 10 }}>
        <IcCheck size={26} />
      </div>
      <div style={{ fontWeight: 500, marginBottom: 8 }}>{L("done")}</div>
      <div className="muted" style={{ fontSize: ".88rem", marginBottom: 20 }}>
        {L("doneHint")}
      </div>
      <button className="btn btn-primary" style={{ width: "100%", height: 42 }}
              onClick={() => router.replace("/login")}>
        {L("toLogin")}
      </button>
    </div>);

  const company = lang === "en"
    ? (info?.company_en || info?.company_ar)
    : info?.company_ar;

  return shell(
    <>
      <div style={{ marginBottom: 22 }}>
        <div style={{ fontSize: "1.1rem", fontWeight: 600 }}>
          {L("welcome")} {info?.name}
        </div>
        <div className="muted" style={{ fontSize: ".9rem", marginTop: 4 }}>
          {L("invitedTo")} <b style={{ color: "var(--ink)" }}>{company}</b>
        </div>
      </div>
      <h1 style={{ fontSize: "1.05rem", marginBottom: 16 }}>
        {L("setPassword")}
      </h1>
      <form onSubmit={submit} className="stack">
        <div className="field">
          <label className="label" htmlFor="p1">{L("password")}</label>
          <input id="p1" className="input" type="password" dir="ltr"
                 value={pw} autoFocus autoComplete="new-password"
                 onChange={(e) => setPw(e.target.value)} />
          <span className="muted" style={{ fontSize: ".8rem" }}>
            {L("hint")}
          </span>
        </div>
        <div className="field">
          <label className="label" htmlFor="p2">{L("confirm")}</label>
          <input id="p2" className="input" type="password" dir="ltr"
                 value={pw2} autoComplete="new-password"
                 onChange={(e) => setPw2(e.target.value)} />
        </div>
        {error && (
          <div style={{
            background: "var(--danger-soft)", color: "var(--danger)",
            padding: "10px 12px", borderRadius: "var(--radius-sm)",
            fontSize: ".88rem",
          }}>{error}</div>
        )}
        <button type="submit" className="btn btn-primary" disabled={busy}
                style={{ width: "100%", height: 42 }}>
          {busy ? L("submitting") : L("submit")}
        </button>
      </form>
    </>
  );
}
