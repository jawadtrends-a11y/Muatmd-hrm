"use client";
/** ضبط كلمة مرور جديدة بالرمز (ق-113). */
import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck } from "@/components/Icons";
import { Shell } from "../../../signup/page";

const T: Dict = {
  title: { ar: "كلمة مرور جديدة", en: "New password" },
  pass: { ar: "كلمة المرور", en: "Password" },
  again: { ar: "تأكيد كلمة المرور", en: "Confirm password" },
  hint: { ar: "ثماني خانات فأكثر", en: "8 characters or more" },
  save: { ar: "حفظ", en: "Save" },
  saving: { ar: "جارٍ الحفظ…", en: "Saving…" },
  mismatch: { ar: "الكلمتان غير متطابقتين", en: "Passwords do not match" },
  ok: { ar: "غُيّرت كلمة المرور", en: "Password changed" },
  login: { ar: "تسجيل الدخول", en: "Sign in" },
  forgotAgain: { ar: "اطلب رابطًا جديدًا", en: "Request a new link" },
};

export default function ResetPage() {
  const { L } = useT(T);
  const params = useParams();
  const [p1, setP1] = useState("");
  const [p2, setP2] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (p1 !== p2) { setErr(L("mismatch")); return; }
    setBusy(true); setErr("");
    try {
      const token = String(params?.token || "");
      await apiPost(`/password/reset/${encodeURIComponent(token)}/`,
                    { password: p1 });
      setDone(true);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally { setBusy(false); }
  };

  if (done) {
    return (
      <Shell>
        <div style={{ textAlign: "center" }}>
          <div style={{ color: "var(--ok)" }}><IcCheck size={34} /></div>
          <h2 style={{ margin: "12px 0 6px" }}>{L("ok")}</h2>
          <Link href="/login" className="btn btn-primary"
                style={{ marginTop: 16 }}>{L("login")}</Link>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <h1 style={{ margin: "0 0 20px", fontSize: "1.25rem" }}>{L("title")}</h1>

      {err && (
        <div style={{ background: "var(--danger-soft)", color: "var(--danger)",
                      padding: "9px 12px", borderRadius: "var(--radius-sm)",
                      fontSize: ".86rem", marginBottom: 14 }}>
          <IcAlert size={14} /> {err}
        </div>
      )}

      <div className="stack" style={{ gap: 14 }}>
        <div className="field">
          <label className="label">{L("pass")}</label>
          <input className="input" type="password" value={p1} autoFocus
                 onChange={(e) => setP1(e.target.value)} />
          <span className="muted" style={{ fontSize: ".78rem" }}>
            {L("hint")}
          </span>
        </div>
        <div className="field">
          <label className="label">{L("again")}</label>
          <input className="input" type="password" value={p2}
                 onChange={(e) => setP2(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && submit()} />
        </div>
      </div>

      <button className="btn btn-primary"
              style={{ width: "100%", height: 44, marginTop: 20 }}
              disabled={busy || !p1} onClick={submit}>
        {busy ? L("saving") : L("save")}
      </button>

      <div style={{ textAlign: "center", marginTop: 16 }}>
        <Link href="/password/forgot" className="muted"
              style={{ fontSize: ".86rem" }}>{L("forgotAgain")}</Link>
      </div>
    </Shell>
  );
}
