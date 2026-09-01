"use client";

/** خطاباتي — الشهادات الصادرة لي (ق-58). */
import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcDoc, IcDownload, IcPlus } from "@/components/Icons";

const T: Dict = {
  title: { ar: "خطاباتي", en: "My letters" },
  subtitle: {
    ar: "الشهادات والخطابات الصادرة لك — صالحة 30 يومًا من الإصدار",
    en: "Certificates issued to you — valid 30 days",
  },
  newRequest: { ar: "طلب خطاب", en: "Request a letter" },
  requestNo: { ar: "رقم الطلب", en: "Request No." },
  type: { ar: "نوع الخطاب", en: "Type" },
  addressedTo: { ar: "موجّه إلى", en: "Addressed to" },
  issued: { ar: "تاريخ الإصدار", en: "Issued" },
  validUntil: { ar: "صالح حتى", en: "Valid until" },
  status: { ar: "الحالة", en: "Status" },
  download: { ar: "تحميل", en: "Download" },
  expired: { ar: "منتهي", en: "Expired" },
  withSalary: { ar: "بالراتب", en: "With salary" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا خطابات", en: "No letters" },
  emptyHint: { ar: "اطلب خطابًا من «خدماتي»", en: "Request one from services" },
  noProfile: { ar: "لا ملف موظف مرتبط بحسابك", en: "No profile linked" },
};

type Letter = {
  id: number; request_no: string; certificate_type: string;
  addressed_to: string; include_salary: boolean;
  status: string; status_label: string;
  issued_at: string; valid_until: string;
  expired: boolean; downloadable: boolean;
};

const TYPE_LABELS: Record<string, string> = {
  employment: "شهادة تعريف بالعمل",
  salary: "شهادة راتب",
  experience: "شهادة خبرة",
  bank: "خطاب لبنك",
  embassy: "خطاب لسفارة",
};

const TONE: Record<string, string> = {
  pending: "badge-warn", approved: "badge-ok", rejected: "badge-danger",
};

export default function MyLettersPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Letter[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    apiGet<Letter[]>("/me/letters/")
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
      <div className="spread">
        <div>
          <h1>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        <Link href="/me/requests?type=certificate" className="btn btn-primary">
          <IcPlus size={17} />
          {L("newRequest")}
        </Link>
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
              <col style={{ width: "160px" }} />
              <col style={{ width: "200px" }} />
              <col />
              <col style={{ width: "130px" }} />
              <col style={{ width: "130px" }} />
              <col style={{ width: "130px" }} />
              <col style={{ width: "110px" }} />
            </colgroup>
            <thead>
              <tr>
                <th style={{ textAlign: "end" }}>{L("requestNo")}</th>
                <th>{L("type")}</th>
                <th>{L("addressedTo")}</th>
                <th style={{ textAlign: "end" }}>{L("issued")}</th>
                <th style={{ textAlign: "end" }}>{L("validUntil")}</th>
                <th>{L("status")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} style={{ opacity: r.expired ? 0.6 : 1 }}>
                  <td style={{ textAlign: "end" }}>
                    <span className="num">{r.request_no}</span>
                  </td>
                  <td>
                    {TYPE_LABELS[r.certificate_type] || r.certificate_type}
                    {r.include_salary && (
                      <span className="badge badge-teal"
                        style={{ marginInlineStart: 6, fontSize: ".72rem" }}>
                        {L("withSalary")}
                      </span>
                    )}
                  </td>
                  <td className="muted truncate">{r.addressed_to || "—"}</td>
                  <td style={{ textAlign: "end" }}>
                    <span className="num">{r.issued_at || "—"}</span>
                  </td>
                  <td style={{ textAlign: "end" }}>
                    {r.valid_until ? (
                      <span className="num" style={{
                        color: r.expired ? "var(--danger)" : undefined,
                      }}>
                        {r.valid_until}
                      </span>
                    ) : "—"}
                  </td>
                  <td>
                    <span className={`badge ${TONE[r.status] || "badge"}`}>
                      {r.expired ? L("expired") : r.status_label}
                    </span>
                  </td>
                  <td style={{ textAlign: "end" }}>
                    {r.downloadable && (
                      <button className="btn btn-sm btn-ghost">
                        <IcDownload size={15} />
                        {L("download")}
                      </button>
                    )}
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
