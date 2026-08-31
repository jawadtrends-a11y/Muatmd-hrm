"use client";

/** شاشة الدخول — تُعرض بلا هيكل (PUBLIC_PATHS في AppShell). */
import { useState } from "react";
import { useRouter } from "next/navigation";

import { apiPost, setToken, ApiError } from "@/lib/api";
import { usePrefs, useT, type Dict } from "@/lib/prefs";
import { IcGlobe, IcMoon, IcSun } from "@/components/Icons";

const T: Dict = {
  title: { ar: "تسجيل الدخول", en: "Sign in" },
  subtitle: { ar: "نظام الموارد البشرية — معتمد", en: "Muatmd HR System" },
  username: { ar: "اسم المستخدم أو البريد", en: "Username or email" },
  password: { ar: "كلمة المرور", en: "Password" },
  submit: { ar: "دخول", en: "Sign in" },
  submitting: { ar: "جارٍ الدخول…", en: "Signing in…" },
  required: { ar: "أدخل اسم المستخدم وكلمة المرور", en: "Enter both fields" },
  failed: { ar: "بيانات الدخول غير صحيحة", en: "Invalid credentials" },
  network: { ar: "تعذّر الاتصال بالخادم", en: "Cannot reach the server" },
};

export default function LoginPage() {
  const router = useRouter();
  const { lang, theme, toggleLang, setTheme } = usePrefs();
  const { L } = useT(T);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
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
      const res = await apiPost<{ token: string }>("/auth/login", {
        username: username.trim(),
        password,
      });
      setToken(res.token);
      router.replace("/");
    } catch (e) {
      const err = e as ApiError;
      setError(err.isNetwork ? L("network")
        : err.isAuth ? L("failed") : err.message);
      setBusy(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh", display: "grid", placeItems: "center",
      background: "var(--paper-2)", padding: 20,
    }}>
      <div style={{ width: "100%", maxWidth: 400 }}>
        <div className="row" style={{ justifyContent: "flex-end", marginBottom: 16 }}>
          <button className="btn btn-ghost btn-sm" onClick={toggleLang}>
            <IcGlobe size={17} />
            {lang === "ar" ? "EN" : "ع"}
          </button>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <IcSun size={17} /> : <IcMoon size={17} />}
          </button>
        </div>

        <div className="card" style={{ padding: 32 }}>
          <div style={{ textAlign: "center", marginBottom: 28 }}>
            <div style={{
              fontSize: "1.7rem", fontWeight: 600, color: "var(--teal)",
              marginBottom: 4,
            }}>
              معتمد
            </div>
            <div className="muted" style={{ fontSize: ".92rem" }}>
              {L("subtitle")}
            </div>
          </div>

          <h1 style={{ fontSize: "1.15rem", marginBottom: 20 }}>{L("title")}</h1>

          <form onSubmit={submit} className="stack">
            <div className="field">
              <label className="label" htmlFor="u">{L("username")}</label>
              <input id="u" className="input" value={username} dir="ltr"
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username" autoFocus />
            </div>

            <div className="field">
              <label className="label" htmlFor="p">{L("password")}</label>
              <input id="p" className="input" type="password" dir="ltr"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password" />
            </div>

            {error && (
              <div style={{
                background: "var(--danger-soft)", color: "var(--danger)",
                padding: "10px 12px", borderRadius: "var(--radius-sm)",
                fontSize: ".88rem",
              }}>
                {error}
              </div>
            )}

            <button type="submit" className="btn btn-primary" disabled={busy}
              style={{ width: "100%", height: 42 }}>
              {busy ? L("submitting") : L("submit")}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
