"use client";

/**
 * إجازاتي (ق-58) — تبويبان منفصلان:
 *   • أرصدتي — بالتدرّج النظامي للمرضية (م/117)
 *   • تاريخ إجازاتي — السابقة والمستقبلية
 */
import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet, qs } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcLeave, IcPlus } from "@/components/Icons";

const T: Dict = {
  title: { ar: "إجازاتي", en: "My leaves" },
  balances: { ar: "أرصدتي", en: "My balances" },
  history: { ar: "تاريخ إجازاتي", en: "History" },
  available: { ar: "المتاح", en: "Available" },
  consumed: { ar: "المستهلك", en: "Used" },
  accrued: { ar: "المستحق", en: "Accrued" },
  opening: { ar: "الرصيد الافتتاحي", en: "Opening" },
  days: { ar: "يوم", en: "days" },
  tiers: { ar: "شرائح الأجر", en: "Pay tiers" },
  tierRange: { ar: "من اليوم", en: "Days" },
  toDay: { ar: "إلى", en: "to" },
  ofPay: { ar: "من الأجر", en: "of pay" },
  eventTypes: { ar: "إجازات تُمنح بالحدث", en: "Event-based leaves" },
  eventHint: {
    ar: "لا رصيد لها — تُطلب عند وقوع الحدث",
    en: "No balance — requested when the event occurs",
  },
  perEvent: { ar: "أيام للحدث", en: "days per event" },
  oncePerService: { ar: "مرة واحدة طوال الخدمة", en: "Once per service" },
  paid: { ar: "مدفوعة", en: "Paid" },
  unpaid: { ar: "بلا أجر", en: "Unpaid" },
  requestNo: { ar: "رقم الطلب", en: "Request No." },
  type: { ar: "النوع", en: "Type" },
  from: { ar: "من", en: "From" },
  to: { ar: "إلى", en: "To" },
  status: { ar: "الحالة", en: "Status" },
  upcoming: { ar: "قادمة", en: "Upcoming" },
  past: { ar: "سابقة", en: "Past" },
  newRequest: { ar: "طلب إجازة", en: "Request leave" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا سجلات", en: "No records" },
  noProfile: {
    ar: "لا ملف موظف مرتبط بحسابك",
    en: "No employee profile linked",
  },
  year: { ar: "السنة", en: "Year" },
};

type Tier = { from_day: number; to_day: number; pay_percentage: string };

type Balance = {
  code: string; name_ar: string; is_paid: boolean;
  days_per_year: string; opening: string; accrued: string;
  consumed: string; available: string; tiers: Tier[];
};

type EventType = {
  code: string; name_ar: string; days_per_event: string;
  is_paid: boolean; once_per_service: boolean;
};

type HistoryRow = {
  request_no: string; leave_type: string;
  start_date: string; end_date: string; days: string;
  status: string; status_label: string; is_future: boolean;
};

type Data = {
  balances: Balance[];
  event_types: EventType[];
  history: HistoryRow[];
};

const TONE: Record<string, string> = {
  pending: "badge-warn", approved: "badge-ok",
  rejected: "badge-danger", cancelled: "badge",
};

export default function MyLeavesPage() {
  const { L } = useT(T);
  const [tab, setTab] = useState<"balances" | "history">("balances");
  const [year, setYear] = useState(new Date().getFullYear());
  const [data, setData] = useState<Data | null>(null);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    let alive = true;
    setBusy(true);
    apiGet<Data>(`/me/leaves-detail/${qs({ year })}`)
      .then((d) => { if (alive) { setData(d); setBusy(false); } })
      .catch(() => { if (alive) { setDenied(true); setBusy(false); } });
    return () => { alive = false; };
  }, [year]);

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
        <h1>{L("title")}</h1>
        <Link href="/me/requests?type=leave" className="btn btn-primary">
          <IcPlus size={17} />
          {L("newRequest")}
        </Link>
      </div>

      <div className="row" style={{ gap: 4 }}>
        {(["balances", "history"] as const).map((t) => (
          <button key={t}
            className={`btn btn-sm ${tab === t ? "btn-primary" : "btn-ghost"}`}
            onClick={() => setTab(t)}>
            {L(t)}
          </button>
        ))}
        <div className="grow" />
        <div className="field" style={{ maxWidth: 120 }}>
          <input type="number" className="input" value={year}
            onChange={(e) => setYear(Number(e.target.value))} />
        </div>
      </div>

      {busy ? (
        <div className="card" style={{
          padding: 40, textAlign: "center", color: "var(--ink-3)",
        }}>
          {L("loading")}
        </div>
      ) : tab === "balances" ? (
        <div className="stack">
          {/* الأرصدة */}
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(290px, 1fr))",
            gap: 16,
          }}>
            {(data?.balances ?? []).map((b) => (
              <div key={b.code} className="card" style={{ padding: 20 }}>
                <div className="spread" style={{ marginBottom: 10 }}>
                  <h3 style={{ fontSize: "1rem" }}>{b.name_ar}</h3>
                  <span className={b.is_paid ? "badge badge-ok" : "badge"}>
                    {b.is_paid ? L("paid") : L("unpaid")}
                  </span>
                </div>

                <div style={{
                  fontSize: "2rem", fontWeight: 600, color: "var(--teal)",
                  marginBottom: 2,
                }}>
                  <span className="num">{b.available}</span>
                  <span className="muted" style={{
                    fontSize: ".9rem", fontWeight: 500,
                  }}>
                    {" "}{L("days")}
                  </span>
                </div>
                <div className="muted" style={{ fontSize: ".84rem", marginBottom: 12 }}>
                  {L("available")}
                </div>

                <div className="spread" style={{
                  padding: "6px 0", borderTop: "1px solid var(--line)",
                }}>
                  <span className="muted" style={{ fontSize: ".85rem" }}>
                    {L("accrued")}
                  </span>
                  <span className="num">{b.accrued}</span>
                </div>
                <div className="spread" style={{ padding: "6px 0" }}>
                  <span className="muted" style={{ fontSize: ".85rem" }}>
                    {L("consumed")}
                  </span>
                  <span className="num">{b.consumed}</span>
                </div>

                {b.tiers.length > 0 && (
                  <div style={{ marginTop: 14 }}>
                    <div className="muted" style={{
                      fontSize: ".82rem", marginBottom: 8,
                    }}>
                      {L("tiers")}
                    </div>
                    {b.tiers.map((t, i) => (
                      <div key={i} className="spread" style={{
                        padding: "5px 0", fontSize: ".88rem",
                      }}>
                        <span>
                          {L("tierRange")} <span className="num">{t.from_day}</span>
                          {" "}{L("toDay")}{" "}
                          <span className="num">{t.to_day}</span>
                        </span>
                        <span style={{
                          fontWeight: 600,
                          color: Number(t.pay_percentage) === 0
                            ? "var(--danger)"
                            : Number(t.pay_percentage) < 100
                            ? "var(--copper)" : "var(--ok)",
                        }}>
                          <span className="num">
                            {Number(t.pay_percentage).toFixed(0)}
                          </span>%
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* الأنواع بالحدث */}
          {(data?.event_types ?? []).length > 0 && (
            <div className="card" style={{ padding: 20 }}>
              <h3 style={{ fontSize: "1rem", marginBottom: 4 }}>
                {L("eventTypes")}
              </h3>
              <div className="muted" style={{ fontSize: ".84rem", marginBottom: 12 }}>
                {L("eventHint")}
              </div>
              <div className="row" style={{ flexWrap: "wrap", gap: 10 }}>
                {data!.event_types.map((t) => (
                  <div key={t.code} style={{
                    padding: "10px 14px", background: "var(--paper-2)",
                    borderRadius: "var(--radius-sm)", minWidth: 170,
                  }}>
                    <div style={{ fontWeight: 500 }}>{t.name_ar}</div>
                    <div className="muted" style={{ fontSize: ".84rem" }}>
                      <span className="num">{t.days_per_event}</span>{" "}
                      {L("perEvent")}
                      {t.once_per_service && (
                        <div style={{ fontSize: ".78rem", marginTop: 2 }}>
                          {L("oncePerService")}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="card" style={{ overflow: "hidden" }}>
          {(data?.history ?? []).length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
              <IcLeave size={24} />
              <div style={{ marginTop: 8 }}>{L("empty")}</div>
            </div>
          ) : (
            <table className="table">
              <colgroup>
                <col style={{ width: "160px" }} />
                <col style={{ width: "160px" }} />
                <col style={{ width: "130px" }} />
                <col style={{ width: "130px" }} />
                <col style={{ width: "80px" }} />
                <col style={{ width: "130px" }} />
                <col style={{ width: "100px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th style={{ textAlign: "end" }}>{L("requestNo")}</th>
                  <th>{L("type")}</th>
                  <th style={{ textAlign: "end" }}>{L("from")}</th>
                  <th style={{ textAlign: "end" }}>{L("to")}</th>
                  <th style={{ textAlign: "end" }}>{L("days")}</th>
                  <th>{L("status")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data!.history.map((h) => (
                  <tr key={h.request_no}>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{h.request_no}</span>
                    </td>
                    <td>{h.leave_type}</td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{h.start_date || "—"}</span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{h.end_date || "—"}</span>
                    </td>
                    <td style={{ textAlign: "end" }}>
                      <span className="num">{h.days || "—"}</span>
                    </td>
                    <td>
                      <span className={`badge ${TONE[h.status] || "badge"}`}>
                        {h.status_label}
                      </span>
                    </td>
                    <td>
                      {h.is_future && (
                        <span className="badge badge-teal">{L("upcoming")}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
