"use client";
/** تأكيد البريد — يُنشئ الحساب ومالكه (ق-113). */
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiPost, setToken, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck } from "@/components/Icons";
import { Shell } from "../../page";

const T: Dict = {
  checking: { ar: "جارٍ تفعيل حسابك…", en: "Activating your account…" },
  ok: { ar: "فُعّل حسابك", en: "Account activated" },
  okBody: {
    ar: "سجّل دخولك ببريدك وكلمة المرور التي اخترتها",
    en: "Sign in with your email and password",
  },
  login: { ar: "تسجيل الدخول", en: "Sign in" },
  signupAgain: { ar: "التسجيل من جديد", en: "Sign up again" },
  continueSub: { ar: "أكمل اشتراكك", en: "Continue to subscribe" },
};

export default function VerifyPage() {
  const { L } = useT(T);
  const params = useParams();
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(true);
  // ق-225: ومن اختار باقةً قبل التسجيل يُكمل اشتراكه بعد الدخول.
  const [hasPick, setHasPick] = useState(false);

  useEffect(() => {
    try { setHasPick(!!localStorage.getItem("pick_plan")); }
    catch { /* لا يمنع شيئًا */ }
  }, []);

  const run = useCallback(async () => {
    const token = String(params?.token || "");
    if (!token) { setErr("رابط غير صالح"); setBusy(false); return; }
    try {
      // ق-225: \u26a0\u26a0 **والتفعيل يُدخل** (قرار جواد): فمن فتح
      // رابط بريده **لا يُطالَب بدخولٍ ثانٍ** — ومن اختار باقةً
      // قبل التسجيل يُنقل لإكمال دفعه مباشرة.
      const out = await apiPost<{ token?: string }>(
        `/signup/verify/${encodeURIComponent(token)}/`, {});
      if (out?.token) {
        setToken(out.token);
        let next = "/";
        try {
          if (localStorage.getItem("pick_plan")) next = "/subscribe";
        } catch { /* لا يمنع الدخول */ }
        window.location.href = next;
        return;
      }
      setDone(true);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [params]);

  useEffect(() => { run(); }, [run]);

  return (
    <Shell>
      <div style={{ textAlign: "center" }}>
        {busy ? (
          <div className="muted">{L("checking")}</div>
        ) : done ? (
          <>
            <div style={{ color: "var(--ok)" }}><IcCheck size={34} /></div>
            <h2 style={{ margin: "12px 0 6px" }}>{L("ok")}</h2>
            <div className="muted" style={{ fontSize: ".9rem" }}>
              {L("okBody")}
            </div>
            {/* ق-225: ومن جاء من صفحة الأسعار يُكمل اشتراكه —
                فلا يعود لصفر بعد أن اختار باقته وعدده. */}
            <Link href={hasPick ? "/login?next=/subscribe" : "/login"}
                  className="btn btn-primary"
                  style={{ marginTop: 20 }}>
              {hasPick ? L("continueSub") : L("login")}
            </Link>
          </>
        ) : (
          <>
            <div style={{ color: "var(--danger)" }}><IcAlert size={30} /></div>
            <div style={{ marginTop: 12 }}>{err}</div>
            <Link href="/signup" className="btn" style={{ marginTop: 20 }}>
              {L("signupAgain")}
            </Link>
          </>
        )}
      </div>
    </Shell>
  );
}
