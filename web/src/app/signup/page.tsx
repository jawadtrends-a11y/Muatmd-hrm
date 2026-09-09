"use client";
/**
 * تسجيل شركة جديدة (ق-113).
 *
 * ولا يُنشأ الحساب هنا: يُرسل رابط تأكيد للبريد أوّلًا — فالبريد
 * غير المؤكَّد يملأ المنصّة بحسابات وهمية، ويحرم صاحبه من استعادة
 * كلمة مروره حين ينساها.
 */
import { useState } from "react";
import Link from "next/link";
import { apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck } from "@/components/Icons";

const T: Dict = {
  title: { ar: "إنشاء حساب شركة", en: "Create a company account" },
  sub: { ar: "جرّب النظام سبعة أيام مجانًا", en: "Try it free for 7 days" },
  company: { ar: "اسم الشركة", en: "Company name" },
  fullName: { ar: "اسمك", en: "Your name" },
  email: { ar: "البريد الإلكتروني", en: "Email" },
  mobile: { ar: "الجوال", en: "Mobile" },
  password: { ar: "كلمة المرور", en: "Password" },
  passHint: { ar: "ثماني خانات فأكثر", en: "8 characters or more" },
  create: { ar: "إنشاء الحساب", en: "Create account" },
  creating: { ar: "جارٍ الإرسال…", en: "Sending…" },
  haveAccount: { ar: "لديك حساب؟ سجّل الدخول", en: "Have an account? Sign in" },
  doneTitle: { ar: "راجع بريدك", en: "Check your email" },
  doneBody: {
    ar: "أرسلنا رابط التأكيد إلى {e} — افتحه لتفعيل حسابك",
    en: "We sent a confirmation link to {e}",
  },
  backLogin: { ar: "العودة لتسجيل الدخول", en: "Back to sign in" },
};

export default function SignupPage() {
  const { L } = useT(T);
  const [f, setF] = useState({
    company_name: "", full_name: "", email: "", mobile: "", password: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [sent, setSent] = useState("");

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await apiPost("/signup/", f);
      setSent(f.email);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  const F = (label: string, key: keyof typeof f, type = "text",
             hint?: string) => (
    <div className="field">
      <label className="label">{label}</label>
      <input className="input" type={type} value={f[key]}
             dir={type === "email" || key === "mobile" ? "ltr" : undefined}
             onChange={(e) => setF({ ...f, [key]: e.target.value })}
             onKeyDown={(e) => e.key === "Enter" && submit()} />
      {hint && <span className="muted" style={{ fontSize: ".78rem" }}>
        {hint}
      </span>}
    </div>
  );

  if (sent) {
    return (
      <Shell>
        <div style={{ textAlign: "center" }}>
          <div style={{ color: "var(--ok)" }}><IcCheck size={34} /></div>
          <h2 style={{ margin: "12px 0 6px" }}>{L("doneTitle")}</h2>
          <div className="muted" style={{ fontSize: ".9rem" }}>
            {L("doneBody").replace("{e}", sent)}
          </div>
          <Link href="/login" className="btn" style={{ marginTop: 20 }}>
            {L("backLogin")}
          </Link>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <h1 style={{ margin: 0, fontSize: "1.3rem" }}>{L("title")}</h1>
      <div className="muted" style={{ fontSize: ".88rem", marginTop: 4,
                                      marginBottom: 20 }}>
        {L("sub")}
      </div>

      {err && (
        <div style={{ background: "var(--danger-soft)", color: "var(--danger)",
                      padding: "9px 12px", borderRadius: "var(--radius-sm)",
                      fontSize: ".86rem", marginBottom: 14 }}>
          <IcAlert size={14} /> {err}
        </div>
      )}

      <div className="stack" style={{ gap: 14 }}>
        {F(L("company"), "company_name")}
        {F(L("fullName"), "full_name")}
        {F(L("email"), "email", "email")}
        {F(L("mobile"), "mobile")}
        {F(L("password"), "password", "password", L("passHint"))}
      </div>

      <button className="btn btn-primary"
              style={{ width: "100%", height: 44, marginTop: 20 }}
              disabled={busy} onClick={submit}>
        {busy ? L("creating") : L("create")}
      </button>

      <div style={{ textAlign: "center", marginTop: 16 }}>
        <Link href="/login" className="muted" style={{ fontSize: ".86rem" }}>
          {L("haveAccount")}
        </Link>
      </div>
    </Shell>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: "grid", placeItems: "center",
                  minHeight: "100vh", padding: 20 }}>
      <div className="card" style={{ padding: 32, maxWidth: 420,
                                     width: "100%" }}>
        {children}
      </div>
    </div>
  );
}
