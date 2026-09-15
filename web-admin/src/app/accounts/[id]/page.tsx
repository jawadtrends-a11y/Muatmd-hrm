"use client";

/**
 * تفصيل الحساب (ق-183).
 *
 * ⚠️⚠️ **والمسار كان مبنيًّا بلا شاشة**: فـ`platform/accounts/<id>/`
 * يُرجع الاشتراك والشركات والمسيرات **والفواتير** — ولا يراها أحد.
 *
 * ⚠️ **والفواتير من «معتمد المحاسبيّ» حصرًا** (قرار جواد): فهو
 * يُصدرها ويرسلها، **والسوبر أدمن يُسجّل رقمها هنا لا يُصدره**.
 */
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { pGet, pPost, can, AdminError, type PlatformUser }
  from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcUser } from "@/components/Icons";

const T: Dict = {
  back: { ar: "← رجوع", en: "← Back" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  subscription: { ar: "الاشتراك", en: "Subscription" },
  plan: { ar: "الباقة", en: "Plan" },
  state: { ar: "الحالة", en: "State" },
  period: { ar: "الفترة", en: "Period" },
  companies: { ar: "الشركات", en: "Companies" },
  employees: { ar: "الموظفون", en: "Employees" },
  runs: { ar: "آخر المسيرات", en: "Recent runs" },
  invoices: { ar: "الفواتير", en: "Invoices" },
  invoiceNo: { ar: "الرقم الداخليّ", en: "Internal no." },
  zatcaNo: { ar: "الفاتورة الزكاتية", en: "ZATCA invoice" },
  total: { ar: "الإجمالي", en: "Total" },
  due: { ar: "الاستحقاق", en: "Due" },
  status: { ar: "الحالة", en: "Status" },
  record: { ar: "تسجيل الزكاتية", en: "Record ZATCA" },
  markPaid: { ar: "تعليم مدفوعة", en: "Mark paid" },
  notRecorded: { ar: "لم تُسجَّل", en: "Not recorded" },
  askNo: {
    ar: "رقم الفاتورة الزكاتية الصادرة من معتمد المحاسبيّ:",
    en: "ZATCA invoice number:",
  },
  askDate: { ar: "تاريخ إصدارها (YYYY-MM-DD):", en: "Issue date:" },
  confirmPaid: { ar: "تعليم الفاتورة مدفوعة — أمتأكّد؟",
                 en: "Mark as paid?" },
  recorded: { ar: "سُجّلت", en: "Recorded" },
  hint: {
    ar: "⚠️ الفواتير تصدر من «معتمد المحاسبيّ» — وتُسجَّل هنا للعميل",
    en: "Invoices are issued by the accounting system",
  },
  noInvoices: { ar: "لا فواتير", en: "No invoices" },
};

type Invoice = {
  id: number; invoice_no: string; total: string;
  status: string; status_label: string;
  due?: string | null; paid_at?: string | null;
  zatca_invoice_no?: string; zatca_issued_at?: string | null;
};
type Detail = {
  account: { id: number; slug: string; name: string;
             is_sandbox: boolean };
  subscription: { state_label: string; plan: string | null;
                  period_start?: string; period_end?: string } | null;
  companies: { id: number; code: string; name: string;
               employees: number }[];
  recent_runs: { run_no: string; period: string; status: string;
                 employees: number }[];
  invoices: Invoice[];
};

export default function AccountDetailPage() {
  const { L } = useT(T);
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const [me, setMe] = useState<PlatformUser | null>(null);
  const [d, setD] = useState<Detail | null>(null);
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState("");
  const [acting, setActing] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setBusy(true);
    setErr("");
    try {
      const [u, data] = await Promise.all([
        pGet<PlatformUser>("/platform/auth/me").catch(() => null),
        pGet<Detail>(`/platform/accounts/${id}/`),
      ]);
      setMe(u);
      setD(data);
    } catch (e) {
      setErr(e instanceof AdminError ? e.message : String(e));
    } finally { setBusy(false); }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const recordZatca = async (inv: Invoice) => {
    const no = prompt(L("askNo"), inv.zatca_invoice_no || "");
    if (!no?.trim()) return;
    const at = prompt(L("askDate"), inv.zatca_issued_at || "");
    setActing(inv.id);
    setErr("");
    try {
      await pPost(`/platform/invoices/${inv.id}/zatca/`, {
        zatca_invoice_no: no.trim(),
        ...(at?.trim() ? { zatca_issued_at: at.trim() } : {}),
      });
      await load();
    } catch (e) {
      setErr(e instanceof AdminError ? e.message : String(e));
    } finally { setActing(null); }
  };

  const markPaid = async (inv: Invoice) => {
    if (!confirm(L("confirmPaid"))) return;
    setActing(inv.id);
    setErr("");
    try {
      await pPost(`/platform/invoices/${inv.id}/mark-paid/`, {});
      await load();
    } catch (e) {
      setErr(e instanceof AdminError ? e.message : String(e));
    } finally { setActing(null); }
  };

  if (busy) return (
    <div className="card" style={{ padding: 40, textAlign: "center",
                                   color: "var(--ink-3)" }}>
      {L("loading")}
    </div>
  );

  return (
    <div className="stack">
      <button className="btn btn-sm btn-ghost"
              onClick={() => router.push("/accounts")}>
        {L("back")}
      </button>

      {err && (
        <div className="card" style={{ borderColor: "var(--danger)",
                                       color: "var(--danger)" }}>
          <IcAlert size={17} /> {err}
        </div>
      )}

      {d && (
        <>
          <div className="card" style={{ padding: 20 }}>
            <div className="row" style={{ gap: 12,
                                          alignItems: "center" }}>
              <IcUser size={22} />
              <div>
                <h1 style={{ margin: 0, fontSize: "1.2rem" }}>
                  {d.account.name}
                </h1>
                <div className="muted" style={{ fontSize: ".82rem" }}>
                  {d.account.slug}
                  {d.account.is_sandbox ? " · تجريبيّ" : ""}
                </div>
              </div>
            </div>
          </div>

          {d.subscription && (
            <div className="card" style={{ padding: 18 }}>
              <h3 style={{ margin: "0 0 10px", fontSize: "1rem" }}>
                {L("subscription")}
              </h3>
              <div className="row" style={{ gap: 26,
                                            flexWrap: "wrap" }}>
                <Field label={L("plan")}
                       value={d.subscription.plan || "—"} />
                <Field label={L("state")}
                       value={d.subscription.state_label} />
                <Field label={L("period")}
                       value={`${d.subscription.period_start || "—"} — ${
                         d.subscription.period_end || "—"}`} numeric />
              </div>
            </div>
          )}

          {d.companies.length > 0 && (
            <div className="card" style={{ overflow: "hidden" }}>
              <div style={{ padding: "14px 18px 0" }}>
                <h3 style={{ margin: 0, fontSize: "1rem" }}>
                  {L("companies")}
                </h3>
              </div>
              <table className="table">
                <tbody>
                  {d.companies.map((c) => (
                    <tr key={c.id}>
                      <td style={{ fontWeight: 500 }}>{c.name}</td>
                      <td className="muted num"
                          style={{ width: 110 }}>{c.code}</td>
                      <td style={{ width: 130 }}>
                        <span className="num">{c.employees}</span>{" "}
                        <span className="muted"
                              style={{ fontSize: ".8rem" }}>
                          {L("employees")}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ── الفواتير ── */}
          <div className="card" style={{ overflow: "hidden" }}>
            <div style={{ padding: "14px 18px 0" }}>
              <h3 style={{ margin: 0, fontSize: "1rem" }}>
                {L("invoices")}
              </h3>
              <div className="muted" style={{ fontSize: ".78rem",
                                              marginTop: 4 }}>
                {L("hint")}
              </div>
            </div>

            {d.invoices.length === 0 ? (
              <div style={{ padding: 30, textAlign: "center",
                            color: "var(--ink-3)" }}>
                {L("noInvoices")}
              </div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>{L("zatcaNo")}</th>
                    <th style={{ width: 150 }}>{L("invoiceNo")}</th>
                    <th style={{ width: 110 }}>{L("total")}</th>
                    <th style={{ width: 110 }}>{L("status")}</th>
                    <th style={{ width: 190 }} />
                  </tr>
                </thead>
                <tbody>
                  {d.invoices.map((inv) => (
                    <tr key={inv.id}>
                      <td>
                        {inv.zatca_invoice_no ? (
                          <>
                            <span className="num">
                              {inv.zatca_invoice_no}
                            </span>
                            {inv.zatca_issued_at && (
                              <div className="muted num"
                                   style={{ fontSize: ".72rem" }}>
                                {inv.zatca_issued_at}
                              </div>
                            )}
                          </>
                        ) : (
                          <span className="badge badge-warn">
                            {L("notRecorded")}
                          </span>
                        )}
                      </td>
                      <td>
                        <span className="num muted"
                              style={{ fontSize: ".82rem" }}>
                          {inv.invoice_no}
                        </span>
                      </td>
                      <td><span className="num">{inv.total}</span></td>
                      <td>
                        <span className={`badge ${
                          inv.status === "paid" ? "badge-ok"
                                                : "badge-warn"}`}>
                          {inv.status_label}
                        </span>
                      </td>
                      <td style={{ textAlign: "end" }}>
                        <div className="row" style={{ gap: 5,
                                                      justifyContent: "flex-end" }}>
                          {can(me, "invoice.mark_paid") && (
                            <button className="btn btn-sm btn-ghost"
                                    disabled={acting === inv.id}
                                    onClick={() => recordZatca(inv)}>
                              {L("record")}
                            </button>
                          )}
                          {can(me, "invoice.mark_paid")
                            && inv.status !== "paid" && (
                            <button className="btn btn-sm"
                                    disabled={acting === inv.id}
                                    onClick={() => markPaid(inv)}>
                              {L("markPaid")}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {d.recent_runs.length > 0 && (
            <div className="card" style={{ overflow: "hidden" }}>
              <div style={{ padding: "14px 18px 0" }}>
                <h3 style={{ margin: 0, fontSize: "1rem" }}>
                  {L("runs")}
                </h3>
              </div>
              <table className="table">
                <tbody>
                  {d.recent_runs.map((r) => (
                    <tr key={r.run_no}>
                      <td><span className="num">{r.run_no}</span></td>
                      <td className="muted num">{r.period}</td>
                      <td>{r.status}</td>
                      <td style={{ width: 90 }}>
                        <span className="num">{r.employees}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}


function Field({ label, value, numeric }: {
  label: string; value: string; numeric?: boolean;
}) {
  return (
    <div>
      <div className="muted" style={{ fontSize: ".76rem",
                                      marginBottom: 3 }}>
        {label}
      </div>
      <div className={numeric ? "num" : ""}>{value}</div>
    </div>
  );
}
