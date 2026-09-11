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
    try {
      setShown(await apiGet<Record<string, unknown>>(`/letters/${id}/`));
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
                        <button className="btn btn-sm btn-ghost"
                                onClick={() => open(r.letter_id!)}>
                          <IcDownload size={15} />
                          {L("view")}
                        </button>
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

      {shown && (
        <LetterView data={shown} L={L} onClose={() => setShown(null)} />
      )}
    </div>
  );
}


/* ══ عرض الخطاب وطباعته (ق-128) ══ */

function LetterView({ data, L, onClose }: {
  data: Record<string, unknown>;
  L: (k: string, f?: string) => string;
  onClose: () => void;
}) {
  const print = () => {
    // ⚠️ نافذةٌ مستقلّة: طباعة الصفحة كلّها تطبع القائمة والقوائم
    // الجانبية — والخطاب وثيقةٌ تخرج وحدها.
    const w = window.open("", "_blank", "width=800,height=900");
    if (!w) return;
    w.document.write(`<!DOCTYPE html><html dir="rtl" lang="ar"><head>
      <meta charset="utf-8"><title>${String(data.letter_no || "")}</title>
      <style>
        body { font-family: system-ui, "Segoe UI", Tahoma, sans-serif;
               padding: 48px 56px; line-height: 2; color: #14202b; }
        .no { text-align: end; font-size: 13px; color: #667; }
        h1 { font-size: 20px; text-align: center; margin: 28px 0 8px; }
        .to { margin: 18px 0; font-weight: 600; }
        .body { white-space: pre-wrap; font-size: 15px; }
        .foot { margin-top: 56px; font-size: 13px; color: #667;
                border-top: 1px solid #dde; padding-top: 10px; }
      </style></head><body>
      <div class="no">${String(data.letter_no || "")} — ${String(data.issued_on || "")}</div>
      <h1>${String(data.heading_ar || "")}</h1>
      <div class="to">${String(data.addressee_ar || "")}</div>
      <div class="body">${String(data.body_ar || "")}</div>
      <div class="foot">${String(data.valid_until
        ? "صالح حتى " + data.valid_until : "")}</div>
      </body></html>`);
    w.document.close();
    w.focus();
    w.print();
  };

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(16,28,38,.5)",
      display: "grid", placeItems: "center", padding: 20, zIndex: 80,
      overflowY: "auto",
    }}>
      <div className="card" style={{ padding: 28, maxWidth: 640,
                                     width: "100%", maxHeight: "88vh",
                                     overflowY: "auto" }}
           onClick={(e) => e.stopPropagation()}>
        <div className="spread">
          <span className="muted num" style={{ fontSize: ".82rem" }}>
            {String(data.letter_no || "")}
          </span>
          <span className="muted" style={{ fontSize: ".82rem" }}>
            {String(data.issued_on || "")}
          </span>
        </div>

        <h2 style={{ textAlign: "center", margin: "18px 0 6px",
                     fontSize: "1.15rem" }}>
          {String(data.heading_ar || "")}
        </h2>
        <div style={{ fontWeight: 600, margin: "14px 0" }}>
          {String(data.addressee_ar || "")}
        </div>
        <div style={{ whiteSpace: "pre-wrap", lineHeight: 2,
                      fontSize: ".95rem" }}>
          {String(data.body_ar || "")}
        </div>

        {data.valid_until ? (
          <div className="muted" style={{ marginTop: 24,
                                          fontSize: ".82rem" }}>
            {L("validUntil")}: {String(data.valid_until)}
          </div>
        ) : null}

        <div className="row" style={{ gap: 8, marginTop: 22 }}>
          <button className="btn btn-primary" onClick={print}>
            {L("print")}
          </button>
          <button className="btn" onClick={onClose}>{L("close")}</button>
        </div>
      </div>
    </div>
  );
}
