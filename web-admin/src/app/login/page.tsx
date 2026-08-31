"use client";

/**
 * دخول لوحة المنصة — خطوتان (ق-51).
 *
 * التحقق الثنائي إلزامي: الحساب يفتح بيانات كل العملاء.
 */
import { useState } from "react";
import { useRouter } from "next/navigation";

import { pPost, AdminError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcShield } from "@/components/Icons";

const T: Dict = {
  title: { ar: "لوحة معتمد", en: "Muatmd Console" },
  subtitle: { ar: "إدارة المنصة", en: "Platform administration" },
  username: { ar: "اسم المستخدم", en: "Username" },
  password: { ar: "كلمة المرور", en: "Password" },
  totp: { ar: "رمز التحقق", en: "Verification code" },
  totpHint: {
    ar: "أدخل الرمز من تطبيق المصادقة",
    en: "Enter the code from your authenticator app",
  },
  submit: { ar: "دخول", en: "Sign in" },
  verify: { ar: "تحقق", en: "Verify" },
  submitting: { ar: "جارٍ الدخول…", en: "Signing in…" },
  back: { ar: "رجوع", en: "Back" },
  required: { ar: "أدخل البيانات المطلوبة", en: "Enter required fields" },
  restricted: {
    ar: "دخول مقيّد — كل محاولة تُسجَّل",
    en: "Restricted access — all attempts are logged",
  },
};

export default function AdminLoginPage() {
  const router = useRouter();
  const { L } = useT(T);

  const [step, setStep] = useState<"credentials" | "totp">("credentials");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError(L("required"));
      return;
    }

    setBusy(true);
    setError("");
    try {
      await pPost("/platform/auth/login", {
        username: username.trim(),
        password,
        ...(step === "totp" ? { totp_code: totp.trim() } : {}),
      });
      router.replace("/");
    } catch (e) {
      const err = e as AdminError;
      if (err.needsTotp) {
        setStep("totp");
        setError("");
      } else {
        setError(err.message);
      }
      setBusy(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh", display: "grid", placeItems: "center",
      background: "var(--paper-2)", padding: 20,
    }}>
      <div style={{ width: "100%", maxWidth: 390 }}>
        <div className="card" style={{ padding: 32 }}>
          <div style={{ textAlign: "center", marginBottom: 26 }}>
            <div style={{ color: "var(--teal)", marginBottom: 8 }}>
              <IcShield size={30} />
            </div>
            <div style={{
              fontSize: "1.45rem", fontWeight: 600, color: "var(--teal)",
            }}>
              {L("title")}
            </div>
            <div className="muted" style={{ fontSize: ".9rem", marginTop: 2 }}>
              {L("subtitle")}
            </div>
          </div>

          <form onSubmit={submit} className="stack">
            {step === "credentials" ? (
              <>
                <div className="field">
                  <label className="label" htmlFor="u">{L("username")}</label>
                  <input id="u" className="input" dir="ltr" autoFocus
                    value={username} autoComplete="username"
                    onChange={(e) => setUsername(e.target.value)} />
                </div>
                <div className="field">
                  <label className="label" htmlFor="p">{L("password")}</label>
                  <input id="p" className="input" type="password" dir="ltr"
                    value={password} autoComplete="current-password"
                    onChange={(e) => setPassword(e.target.value)} />
                </div>
              </>
            ) : (
              <div className="field">
                <label className="label" htmlFor="t">{L("totp")}</label>
                <input id="t" className="input" dir="ltr" autoFocus
                  inputMode="numeric" maxLength={6}
                  style={{
                    textAlign: "center", fontSize: "1.4rem",
                    letterSpacing: "0.4em", fontVariantNumeric: "tabular-nums",
                  }}
                  value={totp}
                  onChange={(e) => setTotp(
                    e.target.value.replace(/\D/g, "").slice(0, 6))} />
                <div className="hint">{L("totpHint")}</div>
              </div>
            )}

            {error && (
              <div style={{
                background: "var(--danger-soft)", color: "var(--danger)",
                padding: "10px 12px", borderRadius: "var(--radius-sm)",
                fontSize: ".88rem", display: "flex", alignItems: "center",
                gap: 8,
              }}>
                <IcAlert size={16} />
                {error}
              </div>
            )}

            <button type="submit" className="btn btn-primary" disabled={busy}
              style={{ width: "100%", height: 42 }}>
              {busy ? L("submitting")
                : step === "totp" ? L("verify") : L("submit")}
            </button>

            {step === "totp" && (
              <button type="button" className="btn btn-ghost btn-sm"
                onClick={() => { setStep("credentials"); setTotp(""); }}>
                ← {L("back")}
              </button>
            )}
          </form>
        </div>

        <div className="muted" style={{
          textAlign: "center", marginTop: 16, fontSize: ".82rem",
        }}>
          {L("restricted")}
        </div>
      </div>
    </div>
  );
}
