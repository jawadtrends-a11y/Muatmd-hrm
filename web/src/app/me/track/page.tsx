"use client";

/** طلباتي — متابعة حالة كل ما قدّمته (ق-58). */
import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcDoc, IcPlus } from "@/components/Icons";

const T: Dict = {
  title: { ar: "طلباتي", en: "My requests" },
  subtitle: {
    ar: "حالة كل ما قدّمته من خدمات",
    en: "Status of everything you submitted",
  },
  newRequest: { ar: "طلب جديد", en: "New request" },
  requestNo: { ar: "رقم الطلب", en: "Request No." },
  type: { ar: "النوع", en: "Type" },
  details: { ar: "التفاصيل", en: "Details" },
  status: { ar: "الحالة", en: "Status" },
  step: { ar: "الدرجة", en: "Step" },
  submitted: { ar: "تاريخ التقديم", en: "Submitted" },
  all: { ar: "الكل", en: "All" },
  pending: { ar: "قيد الاعتماد", en: "Pending" },
  approved: { ar: "معتمدة", en: "Approved" },
  rejected: { ar: "مرفوضة", en: "Rejected" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لم تقدّم أي طلب بعد", en: "No requests yet" },
  emptyHint: {
    ar: "ابدأ من «خدماتي»",
    en: "Start from My Services",
  },
  noProfile: { ar: "لا ملف موظف مرتبط بحسابك", en: "No profile linked" },
};

type Req = {
  id: number; request_no: string; type: string; type_label: string;
  status: string; status_label: string; current_step: number;
  created_at: string; note: string;
  payload: Record<string, unknown>;
};

const TONE: Record<string, string> = {
  pending: "badge-warn", approved: "badge-ok",
  rejected: "badge-danger", cancelled: "badge", draft: "badge",
};

function summarize(r: Req): string {
  const p = r.payload || {};

  // ق-65: طلب التعديل يعرض الحقول المتغيّرة صراحةً
  if (Array.isArray(p.changes)) {
    const ch = p.changes as { label: string; from: string; to: string }[];
    return ch.map((c) => `${c.label}: ${c.from || "—"} ← ${c.to}`).join(" · ");
  }

  const bits: string[] = [];
  if (p.start_date) bits.push(String(p.start_date));
  if (p.work_date) bits.push(String(p.work_date));
  if (p.travel_date) bits.push(String(p.travel_date));
  if (p.days) bits.push(`${p.days} يوم`);
  if (p.amount) bits.push(`${p.amount} ريال`);
  if (p.hours) bits.push(`${p.hours} ساعة`);
  if (p.destination) bits.push(String(p.destination));
  if (p.asset_name) bits.push(String(p.asset_name));
  if (p.certificate_type) bits.push(String(p.certificate_type));
  return bits.join(" · ") || "—";
}

export default function TrackRequestsPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Req[]>([]);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    apiGet<Req[]>("/me/requests/")
      .then((d) => { setRows(d); setBusy(false); })
      .catch(() => { setDenied(true); setBusy(false); });
  }, []);

  const visible = filter ? rows.filter((r) => r.status === filter) : rows;

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
        <Link href="/me/requests" className="btn btn-primary">
          <IcPlus size={17} />
          {L("newRequest")}
        </Link>
      </div>

      <div className="row" style={{ gap: 6 }}>
        {["", "pending", "approved", "rejected"].map((s) => (
          <button key={s || "all"}
            className={`btn btn-sm ${filter === s ? "btn-primary" : ""}`}
            onClick={() => setFilter(s)}>
            {L(s || "all")}
          </button>
        ))}
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {busy ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            {L("loading")}
          </div>
        ) : visible.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
            <IcDoc size={24} />
            <div style={{ marginTop: 8 }}>{L("empty")}</div>
            <div style={{ fontSize: ".88rem", marginTop: 4 }}>
              {L("emptyHint")}
            </div>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <colgroup>
                <col style={{ width: "160px" }} />
                <col style={{ width: "160px" }} />
                <col />
                <col style={{ width: "130px" }} />
                <col style={{ width: "90px" }} />
                <col style={{ width: "150px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th style={{ textAlign: "end" }}>{L("requestNo")}</th>
                  <th>{L("type")}</th>
                  <th>{L("details")}</th>
                  <th>{L("status")}</th>
                  <th style={{ textAlign: "end" }}>{L("step")}</th>
                  <th style={{ textAlign: "end" }}>{L("submitted")}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => (
                  <tr key={r.id}>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{r.request_no}</span>
                    </td>
                    <td>{r.type_label}</td>
                    <td className="muted truncate">{summarize(r)}</td>
                    <td>
                      <span className={`badge ${TONE[r.status] || "badge"}`}>
                        {r.status_label}
                      </span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      {r.status === "pending"
                        ? <span className="num">{r.current_step}</span> : "—"}
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">
                        {(r.created_at || "").slice(0, 10)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
