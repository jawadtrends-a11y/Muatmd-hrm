"use client";

/**
 * الخدمة الذاتية — ما يراه الموظف عن نفسه.
 *
 * قسائمي · رصيد إجازاتي · طلباتي — في شاشة واحدة.
 */
import { useEffect, useState } from "react";

import { apiGet, openForView, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcDoc, IcLeave, IcAlert } from "@/components/Icons";

const T: Dict = {
  title: { ar: "خدماتي", en: "My Services" },
  payslips: { ar: "قسائم راتبي", en: "My Payslips" },
  balances: { ar: "رصيد إجازاتي", en: "My Leave Balance" },
  requests: { ar: "طلباتي", en: "My Requests" },
  period: { ar: "الفترة", en: "Period" },
  net: { ar: "الصافي", en: "Net" },
  paidAt: { ar: "تاريخ الصرف", en: "Paid on" },
  view: { ar: "عرض", en: "View" },
  leaveType: { ar: "نوع الإجازة", en: "Leave type" },
  available: { ar: "المتاح", en: "Available" },
  consumed: { ar: "المستهلك", en: "Used" },
  requestNo: { ar: "رقم الطلب", en: "Request No." },
  type: { ar: "النوع", en: "Type" },
  status: { ar: "الحالة", en: "Status" },
  days: { ar: "الأيام", en: "Days" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا سجلات", en: "No records" },
  noProfile: {
    ar: "لا ملف موظف مرتبط بحسابك — راجع مدير الموارد البشرية",
    en: "No employee profile linked to your account",
  },
  pending: { ar: "بانتظار القرار", en: "Pending" },
};

type Payslip = {
  payslip_id: number;
  period: string;
  net_pay: string;
  payment_date: string | null;
  company: string;
};

type Balance = {
  code: string;
  name_ar: string;
  available: string;
  consumed: string;
};

type Req = {
  id: number;
  request_no: string;
  type_label: string;
  status: string;
  status_label: string;
  payload: Record<string, unknown>;
};

const TONE: Record<string, string> = {
  pending: "badge-warn",
  approved: "badge-ok",
  rejected: "badge-danger",
};

function money(v: string) {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("en-US", { minimumFractionDigits: 2,
                                  maximumFractionDigits: 2 })
    : v;
}

export default function MyServicesPage() {
  const { L } = useT(T);
  const [payslips, setPayslips] = useState<Payslip[]>([]);
  const [balances, setBalances] = useState<Balance[]>([]);
  const [requests, setRequests] = useState<Req[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [busy, setBusy] = useState(true);
  const [noProfile, setNoProfile] = useState(false);

  useEffect(() => {
    Promise.all([
      apiGet<Payslip[]>("/me/payslips/").catch(() => []),
      apiGet<{
        balances: Balance[];
        pending_count: number;
        recent: Req[];
      }>("/me/leaves/").catch((e: ApiError) => {
        if (e.status === 404) setNoProfile(true);
        return null;
      }),
    ]).then(([slips, leaves]) => {
      setPayslips(slips);
      if (leaves) {
        setBalances(leaves.balances || []);
        setRequests(leaves.recent || []);
        setPendingCount(leaves.pending_count || 0);
      }
      setBusy(false);
    });
  }, []);

  if (busy) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
        {L("loading")}
      </div>
    );
  }

  if (noProfile && payslips.length === 0) {
    return (
      <div className="card" style={{
        padding: 32, textAlign: "center", color: "var(--copper)",
      }}>
        <IcAlert size={24} />
        <div style={{ marginTop: 10 }}>{L("noProfile")}</div>
      </div>
    );
  }

  return (
    <div className="stack">
      <h1>{L("title")}</h1>

      {/* ══ رصيد الإجازات ══ */}
      {balances.length > 0 && (
        <section className="stack" style={{ gap: 10 }}>
          <div className="row">
            <IcLeave size={18} />
            <h2 style={{ fontSize: "1.05rem" }}>{L("balances")}</h2>
            {pendingCount > 0 && (
              <span className="badge badge-warn">
                <span className="num">{pendingCount}</span> {L("pending")}
              </span>
            )}
          </div>

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 12,
          }}>
            {balances.map((b) => (
              <div key={b.code} className="card" style={{ padding: "14px 16px" }}>
                <div className="muted" style={{ fontSize: ".82rem", marginBottom: 4 }}>
                  {b.name_ar}
                </div>
                <div style={{ fontSize: "1.5rem", fontWeight: 600,
                              color: "var(--teal)" }}>
                  <span className="num">{b.available}</span>
                </div>
                <div className="muted" style={{ fontSize: ".78rem", marginTop: 2 }}>
                  {L("consumed")}: <span className="num">{b.consumed}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ══ القسائم ══ */}
      <section className="stack" style={{ gap: 10 }}>
        <div className="row">
          <IcDoc size={18} />
          <h2 style={{ fontSize: "1.05rem" }}>{L("payslips")}</h2>
        </div>

        <div className="card" style={{ overflow: "hidden" }}>
          {payslips.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)" }}>
              {L("empty")}
            </div>
          ) : (
            <table className="table">
              <colgroup>
                <col style={{ width: "130px" }} />
                <col style={{ width: "160px" }} />
                <col style={{ width: "140px" }} />
                <col />
                <col style={{ width: "110px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th style={{ textAlign: "end" }}>{L("period")}</th>
                  <th style={{ textAlign: "end" }}>{L("net")}</th>
                  <th style={{ textAlign: "end" }}>{L("paidAt")}</th>
                  <th />
                  <th />
                </tr>
              </thead>
              <tbody>
                {payslips.map((p) => (
                  <tr key={p.payslip_id}>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{p.period}</span>
                    </td>
                    <td style={{ textAlign: "end", fontWeight: 600 }}>
                      <span className="num">{money(p.net_pay)}</span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      {p.payment_date
                        ? <span className="num">{p.payment_date}</span> : "—"}
                    </td>
                    <td className="muted truncate">{p.company}</td>
                    <td style={{ textAlign: "end" }}>
                      <button
                        className="btn btn-sm btn-ghost"
                        onClick={() => openForView(`/payslips/${p.payslip_id}/`)}
                      >
                        {L("view")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* ══ الطلبات ══ */}
      <section className="stack" style={{ gap: 10 }}>
        <h2 style={{ fontSize: "1.05rem" }}>{L("requests")}</h2>
        <div className="card" style={{ overflow: "hidden" }}>
          {requests.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)" }}>
              {L("empty")}
            </div>
          ) : (
            <table className="table">
              <colgroup>
                <col style={{ width: "160px" }} />
                <col style={{ width: "150px" }} />
                <col style={{ width: "190px" }} />
                <col style={{ width: "80px" }} />
                <col style={{ width: "140px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th style={{ textAlign: "end" }}>{L("requestNo")}</th>
                  <th>{L("type")}</th>
                  <th style={{ textAlign: "end" }}>{L("period")}</th>
                  <th style={{ textAlign: "end" }}>{L("days")}</th>
                  <th>{L("status")}</th>
                </tr>
              </thead>
              <tbody>
                {requests.map((r) => (
                  <tr key={r.id}>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{r.request_no}</span>
                    </td>
                    <td>{r.type_label}</td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">
                        {(r.payload.start_date as string) || "—"}
                      </span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">
                        {String(r.payload.days ?? "—")}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${TONE[r.status] || "badge"}`}>
                        {r.status_label}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}
