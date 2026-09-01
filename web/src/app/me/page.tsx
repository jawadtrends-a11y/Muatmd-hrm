"use client";

/**
 * قسائم راتبي (ق-58).
 *
 * القسائم فقط — الأرصدة في «إجازاتي»، والطلبات في «طلباتي».
 */
import { useEffect, useState } from "react";

import { apiGet, openForView } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "قسائم راتبي", en: "My payslips" },
  subtitle: {
    ar: "قسائم الرواتب المعتمدة",
    en: "Approved payslips",
  },
  period: { ar: "الفترة", en: "Period" },
  net: { ar: "الصافي", en: "Net" },
  paidAt: { ar: "تاريخ الصرف", en: "Paid on" },
  company: { ar: "الشركة", en: "Company" },
  view: { ar: "عرض", en: "View" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا قسائم بعد", en: "No payslips yet" },
  emptyHint: {
    ar: "تظهر القسيمة بعد اعتماد مسير الشهر",
    en: "Appears after the monthly run is approved",
  },
  noProfile: {
    ar: "لا ملف موظف مرتبط بحسابك",
    en: "No employee profile linked",
  },
};

type Payslip = {
  payslip_id: number;
  period: string;
  net_pay: string;
  payment_date: string | null;
  company: string;
};

function money(v: string) {
  const n = Number(v);
  return Number.isFinite(n)
    ? n.toLocaleString("en-US", { minimumFractionDigits: 2,
                                  maximumFractionDigits: 2 })
    : v;
}

export default function MyPayslipsPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Payslip[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    apiGet<Payslip[]>("/me/payslips/")
      .then((d) => { setRows(d); setBusy(false); })
      .catch(() => { setDenied(true); setBusy(false); });
  }, []);

  if (denied) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        <IcAlert size={22} />
        <div style={{ marginTop: 8 }}>{L("noProfile")}</div>
      </div>
    );
  }

  return (
    <div className="stack">
      <div>
        <h1>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {L("subtitle")}
        </div>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : rows.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            <IcDoc size={24} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
            <div style={{ fontSize: ".88rem", marginTop: 4 }}>
              {L("emptyHint")}
            </div>
          </div>
        ) : (
          <table className="table">
            <colgroup>
              <col style={{ width: "140px" }} />
              <col style={{ width: "160px" }} />
              <col style={{ width: "150px" }} />
              <col />
              <col style={{ width: "110px" }} />
            </colgroup>
            <thead>
              <tr>
                <th style={{ textAlign: "end" }}>{L("period")}</th>
                <th style={{ textAlign: "end" }}>{L("net")}</th>
                <th style={{ textAlign: "end" }}>{L("paidAt")}</th>
                <th>{L("company")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
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
                    <button className="btn btn-sm btn-ghost"
                      onClick={() => openForView(`/payslips/${p.payslip_id}/`)}>
                      {L("view")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
