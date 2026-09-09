"use client";
/**
 * عودة العميل من بوابة الدفع (ق-109).
 *
 * الصفحة لا تصدّق معطيات الرابط: تسأل الخادم، وهو يسأل ميسر —
 * فالرابط قابل للتزوير، ولا يُعلَّم شيء مدفوعًا بكلام العائد.
 */
import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck } from "@/components/Icons";

const T: Dict = {
  checking: { ar: "جارٍ التحقّق من الدفع…", en: "Verifying payment…" },
  paid: { ar: "تمّ الدفع", en: "Payment successful" },
  paidHint: {
    ar: "فُعّل اشتراكك، وستصلك الفاتورة الضريبية بالبريد",
    en: "Your subscription is active — the invoice will arrive by email",
  },
  failed: { ar: "لم تتمّ العملية", en: "Payment did not go through" },
  failedHint: {
    ar: "لم يُخصم من بطاقتك شيء — جرّب مرّة أخرى أو استعمل بطاقة غيرها",
    en: "Nothing was charged — try again or use another card",
  },
  invoice: { ar: "مرجع العملية", en: "Reference" },
  amount: { ar: "المبلغ", en: "Amount" },
  home: { ar: "الرئيسية", en: "Home" },
  retry: { ar: "المحاولة ثانية", en: "Try again" },
  noId: { ar: "لا معرّف عملية في الرابط", en: "No payment id in the link" },
};

type Res = {
  paid: boolean; status_label: string;
  invoice_no: string; amount: string;
};

function CallbackInner() {
  const { L } = useT(T);
  const params = useSearchParams();
  const router = useRouter();
  const [res, setRes] = useState<Res | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(true);

  const check = useCallback(async () => {
    const id = params.get("id");
    if (!id) { setErr(L("noId")); setBusy(false); return; }
    try {
      setRes(await apiGet<Res>(`/billing/confirm/?id=${encodeURIComponent(id)}`));
    } catch (e) {
      setErr((e as Error).message);
    } finally { setBusy(false); }
  }, [params, L]);

  useEffect(() => { check(); }, [check]);

  const ok = res?.paid;

  return (
    <div style={{ display: "grid", placeItems: "center",
                  minHeight: "60vh", padding: 20 }}>
      <div className="card" style={{ padding: 32, maxWidth: 440,
                                     width: "100%", textAlign: "center" }}>
        {busy ? (
          <div className="muted">{L("checking")}</div>
        ) : err ? (
          <>
            <div style={{ color: "var(--danger)" }}><IcAlert size={30} /></div>
            <div style={{ marginTop: 10 }}>{err}</div>
          </>
        ) : (
          <>
            <div style={{ color: ok ? "var(--ok)" : "var(--danger)" }}>
              {ok ? <IcCheck size={34} /> : <IcAlert size={34} />}
            </div>
            <h2 style={{ margin: "12px 0 6px" }}>
              {ok ? L("paid") : L("failed")}
            </h2>
            <div className="muted" style={{ fontSize: ".88rem" }}>
              {ok ? L("paidHint") : L("failedHint")}
            </div>

            {res && (
              <div style={{ marginTop: 18, display: "grid", gap: 6,
                            fontSize: ".88rem" }}>
                <div className="spread">
                  <span className="muted">{L("invoice")}</span>
                  <span className="num">{res.invoice_no}</span>
                </div>
                <div className="spread">
                  <span className="muted">{L("amount")}</span>
                  <span className="num">{res.amount}</span>
                </div>
              </div>
            )}

            <div className="row" style={{ gap: 8, marginTop: 22,
                                          justifyContent: "center" }}>
              {ok ? (
                <button className="btn btn-primary"
                        onClick={() => router.replace("/")}>
                  {L("home")}
                </button>
              ) : (
                <>
                  <Link href="/subscribe" className="btn btn-primary">
                    {L("retry")}
                  </Link>
                  <Link href="/" className="btn">{L("home")}</Link>
                </>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}


// useSearchParams يشترط حدّ Suspense في الصفحات المُصدَّرة — وبدونه
// يسقط البناء عند التصيير المسبق.
export default function CallbackPage() {
  return (
    <Suspense fallback={
      <div style={{ display: "grid", placeItems: "center",
                    minHeight: "60vh" }}>
        <div className="card" style={{ padding: 32 }}>…</div>
      </div>
    }>
      <CallbackInner />
    </Suspense>
  );
}
