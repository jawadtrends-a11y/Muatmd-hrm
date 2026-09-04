"use client";

/** طلباتي — متابعة حالة كل ما قدّمته (ق-58). */
import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet, apiPost, openForView, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcDoc, IcPlus } from "@/components/Icons";
import ApprovalChain, { type ChainRow, stamp }
  from "@/components/ApprovalChain";

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
  submittedAt: { ar: "وقت التقديم", en: "Submitted" },
  closedAt: { ar: "وقت الإغلاق", en: "Closed" },
  attachment: { ar: "المرفق", en: "Attachment" },
  openAttachment: { ar: "فتح المرفق", en: "Open" },
  loadFailed: { ar: "تعذّر تحميل التفاصيل", en: "Could not load details" },
  delegations: { ar: "إنابات تنتظر قرارك", en: "Delegation requests" },
  delegHint: {
    ar: "طلب منك أن تنوب عنه أثناء غيابه",
    en: "Asked you to cover while away",
  },
  yourDeputy: { ar: "نائبك", en: "Your deputy" },
  cancelRequest: { ar: "إلغاء الطلب", en: "Cancel request" },
  cancelHint: {
    ar: "ما دام لم ينظر فيه أحد",
    en: "While no one has decided yet",
  },
  acceptDeleg: { ar: "أقبل الإنابة", en: "Accept" },
  declineDeleg: { ar: "أعتذر", en: "Decline" },
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
  submitted_at?: string | null;
  closed_at?: string | null;
  attachment_url?: string;
  approvals?: ChainRow[];
  /** ق-75: نائبك أثناء غيابك وحالته */
  delegation?: {
    deputy: string; status: string; status_label: string;
    starts_on: string; ends_on: string;
  } | null;
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

type Deleg = {
  id: number;
  absentee: string;
  starts_on: string;
  ends_on: string;
  status: string;
};


export default function TrackRequestsPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Req[]>([]);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  /**
   * ق-71: الموظف يرى أين وصل طلبه — الصف يتمدّد بالنقر.
   * والتفاصيل تُجلب عند الفتح لا مع القائمة.
   */
  /** ق-75: إنابات تنتظر قراري — أقبل أو أعتذر */
  const [delegs, setDelegs] = useState<Deleg[]>([]);
  const [acting, setActing] = useState(false);
  const [cancelErr, setCancelErr] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Req | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  function toggle(id: number) {
    if (openId === id) { setOpenId(null); setDetail(null); return; }
    setOpenId(id);
    setDetail(null);
    setLoadingDetail(true);
    apiGet<Req>(`/leaves/requests/${id}/`)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoadingDetail(false));
  }

  function loadDelegs() {
    apiGet<{ incoming: Deleg[] }>("/me/delegations/")
      .then((d) => setDelegs(
        (d.incoming || []).filter((x) => x.status === "pending")))
      .catch(() => setDelegs([]));
  }

  useEffect(() => {
    apiGet<Req[]>("/me/requests/")
      .then((d) => { setRows(d); setBusy(false); })
      .catch(() => { setDenied(true); setBusy(false); });
    loadDelegs();
  }, []);

  /**
   * ق-81: مقدّم الطلب يسحبه ما لم ينظر فيه أحد.
   *
   * فالخطأ في التقديم وارد والرأي يتغيّر — لكن بعد أول قرار
   * يكون معتمِد قد نظر، وسحبه بعده يُهدر قراره.
   */
  async function cancelRequest(id: number) {
    setActing(true);
    try {
      await apiPost(`/requests/${id}/cancel/`, {});
      setOpenId(null);
      apiGet<Req[]>("/me/requests/").then(setRows).catch(() => {});
    } catch (e) {
      setCancelErr((e as ApiError).message);
      setTimeout(() => setCancelErr(""), 5000);
    } finally {
      setActing(false);
    }
  }

  /** ق-75: النائب يقبل الإنابة أو يعتذر — وبالاعتذار تمضي الإجازة */
  async function decideDeleg(id: number, accept: boolean) {
    setActing(true);
    try {
      await apiPost(`/delegations/${id}/decide/`, { accept });
      loadDelegs();
    } catch {
      /* الرسالة تظهر في الشاشة التالية */
    } finally {
      setActing(false);
    }
  }

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

      {cancelErr && (
        <div style={{
          background: "var(--danger-soft)", color: "var(--danger)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
          fontSize: ".88rem",
        }}>
          {cancelErr}
        </div>
      )}

      {/* ق-75: إنابات تنتظر قرارك — أول ما يُرى، فهي تنتظر إجراءً */}
      {delegs.length > 0 && (
        <div className="stack" style={{ gap: 10 }}>
          <div className="row">
            <IcAlert size={18} />
            <h2 style={{ fontSize: "1.02rem" }}>
              {L("delegations")}
              <span className="badge badge-warn"
                style={{ marginInlineStart: 8 }}>
                <span className="num">{delegs.length}</span>
              </span>
            </h2>
          </div>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
            gap: 12,
          }}>
            {delegs.map((d) => (
              <div key={d.id} className="card" style={{
                padding: 18, borderInlineStartWidth: 4,
                borderInlineStartColor: "var(--teal)",
              }}>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>
                  {d.absentee}
                </div>
                <div className="muted" style={{
                  fontSize: ".86rem", marginBottom: 12,
                }}>
                  {L("delegHint")}
                  <div style={{ marginTop: 4 }}>
                    <span className="num">{d.starts_on}</span>
                    {" — "}
                    <span className="num">{d.ends_on}</span>
                  </div>
                </div>
                <div className="row">
                  <button className="btn btn-sm btn-primary" disabled={acting}
                    onClick={() => decideDeleg(d.id, true)}>
                    {L("acceptDeleg")}
                  </button>
                  <button className="btn btn-sm btn-ghost" disabled={acting}
                    onClick={() => decideDeleg(d.id, false)}>
                    {L("declineDeleg")}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
                  <>
                  <tr key={r.id} onClick={() => toggle(r.id)}
                    style={{ cursor: "pointer" }}>
                    <td style={{ textAlign: "end" }}>
                      <span className="num" style={{ color: "var(--teal)" }}>
                        {r.request_no}
                      </span>
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

                  {openId === r.id && (
                    <tr key={`${r.id}-detail`}>
                      <td colSpan={6} style={{
                        background: "var(--paper-2)", padding: "14px 18px",
                      }}>
                        {loadingDetail ? (
                          <span className="muted">{L("loading")}</span>
                        ) : detail ? (
                          <div className="stack" style={{ gap: 12 }}>
                            <div className="row" style={{
                              gap: 20, flexWrap: "wrap", fontSize: ".85rem",
                            }}>
                              <div>
                                <div className="muted" style={{ fontSize: ".76rem" }}>
                                  {L("submittedAt")}
                                </div>
                                <span className="num">
                                  {stamp(detail.submitted_at || detail.created_at)}
                                </span>
                              </div>
                              {detail.closed_at && (
                                <div>
                                  <div className="muted" style={{ fontSize: ".76rem" }}>
                                    {L("closedAt")}
                                  </div>
                                  <span className="num">
                                    {stamp(detail.closed_at)}
                                  </span>
                                </div>
                              )}
                              {detail.attachment_url && (
                                <div>
                                  <div className="muted" style={{ fontSize: ".76rem" }}>
                                    {L("attachment")}
                                  </div>
                                  <button
                                    onClick={() => openForView(detail.attachment_url!)}
                                    style={{
                                      background: "none", border: "none",
                                      padding: 0, color: "var(--teal)",
                                      fontWeight: 500, font: "inherit",
                                      cursor: "pointer",
                                    }}>
                                    {L("openAttachment")}
                                  </button>
                                </div>
                              )}
                            </div>
                            {detail.delegation && (
                              <div style={{
                                fontSize: ".85rem",
                                paddingTop: 10,
                                borderTop: "1px solid var(--line)",
                              }}>
                                <span className="muted">{L("yourDeputy")}: </span>
                                <span style={{ fontWeight: 500 }}>
                                  {detail.delegation.deputy}
                                </span>
                                <span className={`badge ${
                                  detail.delegation.status === "accepted"
                                    ? "badge-teal"
                                    : detail.delegation.status === "declined"
                                      ? "badge-danger" : "badge-warn"
                                }`} style={{ marginInlineStart: 8 }}>
                                  {detail.delegation.status_label}
                                </span>
                              </div>
                            )}
                            <ApprovalChain rows={detail.approvals ?? []} />

                            {/* ق-81: السحب ما لم ينظر فيه أحد */}
                            {detail.status === "pending"
                             && !(detail.approvals || []).some(
                                  (a) => a.decision) && (
                              <div style={{
                                paddingTop: 10,
                                borderTop: "1px solid var(--line)",
                              }}>
                                <button className="btn btn-sm btn-ghost"
                                  disabled={acting}
                                  style={{ color: "var(--danger)" }}
                                  onClick={() => cancelRequest(detail.id)}>
                                  {L("cancelRequest")}
                                </button>
                                <span className="muted" style={{
                                  fontSize: ".78rem",
                                  marginInlineStart: 8,
                                }}>
                                  {L("cancelHint")}
                                </span>
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="muted">{L("loadFailed")}</span>
                        )}
                      </td>
                    </tr>
                  )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
