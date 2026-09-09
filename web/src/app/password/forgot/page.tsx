"use client";
/**
 * طلب استعادة كلمة المرور (ق-113).
 *
 * ⚠️ الرسالة واحدة سواء وُجد البريد أم لا — وإلا صارت الصفحة
 * أداةً لكشف من له حساب عندنا.
 */
import { useState } from "react";
import Link from "next/link";
import { apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck } from "@/components/Icons";
import { Shell } from "../../signup/page";

const T: Dict = {
  title: { ar: "استعادة كلمة المرور", en: "Reset your password" },
  sub: {
    ar: "أدخل بريدك المرتبط بالحساب ويصلك رابط الاستعادة",
    en: "Enter your account email and we'll send a reset link",
  },
  email: { ar: "البريد الإلكتروني", en: "Email" },
  send: { ar: "إرسال الرابط", en: "Send link" },
  sending: { ar: "جارٍ الإرسال…", en: "Sending…" },
  sentTitle: { ar: "راجع بريدك", en: "Check your email" },
  sentBody: {
    ar: "إن كان لهذا البريد حساب فستصلك رسالة الاستعادة خلال دقائق",
    en: "If an account exists, a reset email is on its way",
  },
  back: { ar: "العودة لتسجيل الدخول", en: "Back to sign in" },
};

export default function ForgotPage() {
  const { L } = useT(T);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!email.trim()) return;
    setBusy(true); setErr("");
    try {
      await apiPost("/password/forgot/", { email });
      setSent(true);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <Shell>
      {sent ? (
        <div style={{ textAlign: "center" }}>
          <div style={{ color: "var(--ok)" }}><IcCheck size={34} /></div>
          <h2 style={{ margin: "12px 0 6px" }}>{L("sentTitle")}</h2>
          <div className="muted" style={{ fontSize: ".9rem" }}>
            {L("sentBody")}
          </div>
          <Link href="/login" className="btn" style={{ marginTop: 20 }}>
            {L("back")}
          </Link>
        </div>
      ) : (
        <>
          <h1 style={{ margin: 0, fontSize: "1.25rem" }}>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 4,
                                          marginBottom: 20 }}>
            {L("sub")}
          </div>

          {err && (
            <div style={{ background: "var(--danger-soft)",
                          color: "var(--danger)", padding: "9px 12px",
                          borderRadius: "var(--radius-sm)",
                          fontSize: ".86rem", marginBottom: 14 }}>
              <IcAlert size={14} /> {err}
            </div>
          )}

          <div className="field">
            <label className="label">{L("email")}</label>
            <input className="input" type="email" value={email} dir="ltr"
                   autoFocus
                   onChange={(e) => setEmail(e.target.value)}
                   onKeyDown={(e) => e.key === "Enter" && submit()} />
          </div>

          <button className="btn btn-primary"
                  style={{ width: "100%", height: 44, marginTop: 18 }}
                  disabled={busy} onClick={submit}>
            {busy ? L("sending") : L("send")}
          </button>

          <div style={{ textAlign: "center", marginTop: 16 }}>
            <Link href="/login" className="muted"
                  style={{ fontSize: ".86rem" }}>{L("back")}</Link>
          </div>
        </>
      )}
    </Shell>
  );
}
