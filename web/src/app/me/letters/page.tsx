"use client";

/** خطاباتي — الشهادات الصادرة لي (ق-58). */
import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet, openForView } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcDoc, IcDownload, IcPlus } from "@/components/Icons";

const T: Dict = {
  pdf: { ar: "تنزيل PDF", en: "PDF" },
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
  view: { ar: "عرض", en: "View" },
  print: { ar: "طباعة", en: "Print" },
  close: { ar: "إغلاق", en: "Close" },
  letterNo: { ar: "رقم الخطاب", en: "Letter no" },
  pendingManual: {
    ar: "تُصدر ورقيًّا من الموارد البشرية",
    en: "Issued manually by HR",
  },
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
  letter_id?: number | null; letter_no?: string;
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

  const [shown, setShown] = useState<Record<string, unknown> | null>(null);
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

  const open = async (id: number) => {
    // ⚠️ **والعرض PDF** — فمصدرٌ واحد للخطاب (ق-198)
    try {
      await openForView(`/letters/${id}/pdf/`);
    } catch {
      /* الخطأ يظهر في الشاشة نفسها */
    }
  };

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
                      r.letter_id ? (
                        <div className="row" style={{ gap: 5,
                               justifyContent: "flex-end" }}>
                          <button className="btn btn-sm btn-ghost"
                                  onClick={() => open(r.letter_id!)}>
                            {L("view")}
                          </button>
                          {/* ق-196: **وPDF بترويسته** — فخطابُ
                              التعريف يُحمَل للبنك ورقةً */}
                          <button className="btn btn-sm"
                                  onClick={() => openForView(
                                    `/letters/${r.letter_id}/pdf/`)}>
                            <IcDownload size={15} />
                            {L("pdf")}
                          </button>
                        </div>
                      ) : (
                        // ⚠️ لا خطابَ صادرًا: لا قالب مطابق —
                        // فتُصدر ورقيًّا، ولا نعِد بما لا يقع.
                        <span className="muted"
                              style={{ fontSize: ".78rem" }}>
                          {L("pendingManual")}
                        </span>
                      )
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


/* ══ عرض الخطاب وطباعته (ق-128) ══ */

// ق-198: **حُذف `LetterView`** (قرار جواد).
//
// ⚠️⚠️ **فمصدرٌ واحد للخطاب أأمن من اثنين يختلفان**: وكانت
// الشاشة **تطبع بقالب HTML خاصّ** — والمتصفّح يفهم `align` ولا
// يفهم `size`، **فيختلف المطبوع عن الـPDF**.
//
// **والعرض الآن PDF وحده** — بترويسته وتذييله (ق-١٩٦).
