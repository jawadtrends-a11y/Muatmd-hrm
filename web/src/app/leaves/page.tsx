"use client";

/**
 * شاشة الإجازات والطلبات.
 *
 * ثلاثة أقسام تظهر حسب الصلاحية لا بشاشات منفصلة (ق-53):
 *   • بانتظار اعتمادي — لمن يعتمد، وهي شاشته الأولى
 *   • كل الطلبات — لمدير الموارد
 *   • طلباتي — لكل موظف
 */
import { useCallback, useEffect, useState } from "react";

import { apiGet, apiPost, qs, openForView, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcLeave, IcX } from "@/components/Icons";
import ApprovalChain, { type ChainRow, stamp }
  from "@/components/ApprovalChain";

const T: Dict = {
  title: { ar: "الإجازات والطلبات", en: "Leaves & Requests" },
  pending: { ar: "بانتظار اعتمادي", en: "Awaiting my approval" },
  allRequests: { ar: "كل الطلبات", en: "All requests" },
  myRequests: { ar: "طلباتي", en: "My requests" },
  nothingPending: {
    ar: "لا شيء ينتظر قرارك",
    en: "Nothing awaits your decision",
  },
  empty: { ar: "لا طلبات", en: "No requests" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  employee: { ar: "الموظف", en: "Employee" },
  type: { ar: "النوع", en: "Type" },
  period: { ar: "الفترة", en: "Period" },
  days: { ar: "الأيام", en: "Days" },
  status: { ar: "الحالة", en: "Status" },
  requestNo: { ar: "رقم الطلب", en: "Request No." },
  approve: { ar: "اعتماد", en: "Approve" },
  reject: { ar: "رفض", en: "Reject" },
  comment: { ar: "ملاحظة (اختيارية)", en: "Comment (optional)" },
  confirm: { ar: "تأكيد", en: "Confirm" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  step: { ar: "الدرجة", en: "Step" },
  waitingSince: { ar: "منذ", en: "Since" },
  filterAll: { ar: "الكل", en: "All" },
  filterPending: { ar: "قيد الاعتماد", en: "Pending" },
  filterApproved: { ar: "معتمدة", en: "Approved" },
  filterRejected: { ar: "مرفوضة", en: "Rejected" },
  done: { ar: "تم", en: "Done" },
  submittedAt: { ar: "وقت التقديم", en: "Submitted" },
  closedAt: { ar: "وقت الإغلاق", en: "Closed" },
  attachment: { ar: "المرفق", en: "Attachment" },
  openAttachment: { ar: "فتح المرفق", en: "Open" },
  acknowledge: { ar: "اطّلعت", en: "Acknowledge" },
  delegations: { ar: "إنابات تنتظر قرارك", en: "Delegation requests" },
  delegHint: {
    ar: "طلب منك أن تنوب عنه أثناء غيابه",
    en: "Asked you to cover for them while away",
  },
  acceptDeleg: { ar: "أقبل الإنابة", en: "Accept" },
  declineDeleg: { ar: "أعتذر", en: "Decline" },
  ackHint: {
    ar: "إحاطة بغياب مديرك — لا موافقة",
    en: "Notice of your manager's absence — not an approval",
  },
  failed: { ar: "تعذّر تنفيذ القرار", en: "Could not save decision" },
};

type Req = {
  id: number;
  request_no: string;
  type: string;
  type_label: string;
  employee_no: string;
  employee_name: string;
  status: string;
  status_label: string;
  current_step: number;
  note: string;
  created_at: string;
  payload: Record<string, unknown>;
  my_step?: number;
  waiting_since?: string;
  submitted_at?: string | null;
  closed_at?: string | null;
  attachment_url?: string;
  approvals?: ChainRow[];
  /** ق-74: درجة علم — «اطّلعت» وحدها بلا رفض */
  is_acknowledgement?: boolean;
};

const STATUS_TONE: Record<string, string> = {
  pending: "badge-warn",
  approved: "badge-ok",
  rejected: "badge-danger",
  cancelled: "badge",
};

function payloadPeriod(p: Record<string, unknown>): string {
  const start = (p.start_date as string) || "";
  const end = (p.end_date as string) || "";
  if (!start) return "—";
  return end && end !== start ? `${start} — ${end}` : start;
}

function payloadDays(p: Record<string, unknown>): string {
  const d = p.days ?? p.charged_days;
  return d != null ? String(d) : "—";
}


/* ══ بطاقة طلب بانتظار الاعتماد — خارج المكوّن الرئيسي ══ */

function ApprovalCard({
  req, L, onDecide, busy,
}: {
  req: Req;
  L: (k: string, f?: string) => string;
  onDecide: (id: number, decision: "approved" | "rejected", comment: string) => void;
  busy: boolean;
}) {
  const [open, setOpen] = useState<"approved" | "rejected" | null>(null);
  const [comment, setComment] = useState("");

  return (
    <div className="card" style={{ padding: 16 }}>
      <div className="spread" style={{ marginBottom: 10 }}>
        <div>
          <div style={{ fontWeight: 600 }}>{req.employee_name}</div>
          <div className="muted" style={{ fontSize: ".85rem" }}>
            <span className="num">{req.employee_no}</span> · {req.type_label}
          </div>
        </div>
        <span className="badge badge-warn">
          {L("step")} <span className="num">{req.my_step ?? req.current_step}</span>
        </span>
      </div>

      <div className="row" style={{ flexWrap: "wrap", gap: 16, marginBottom: 12 }}>
        <div>
          <div className="muted" style={{ fontSize: ".78rem" }}>{L("period")}</div>
          <div><span className="num">{payloadPeriod(req.payload)}</span></div>
        </div>
        <div>
          <div className="muted" style={{ fontSize: ".78rem" }}>{L("days")}</div>
          <div><span className="num">{payloadDays(req.payload)}</span></div>
        </div>
        <div>
          <div className="muted" style={{ fontSize: ".78rem" }}>{L("requestNo")}</div>
          <div><span className="num">{req.request_no}</span></div>
        </div>
      </div>

      {req.note && (
        <div className="muted" style={{
          fontSize: ".88rem", marginBottom: 12, padding: "8px 10px",
          background: "var(--paper-2)", borderRadius: "var(--radius-sm)",
        }}>
          {req.note}
        </div>
      )}

      <div className="row" style={{
        gap: 14, flexWrap: "wrap", marginBottom: 12, fontSize: ".82rem",
      }}>
        <div>
          <div className="muted" style={{ fontSize: ".76rem" }}>
            {L("submittedAt")}
          </div>
          <span className="num">
            {stamp(req.submitted_at || req.created_at)}
          </span>
        </div>
        {req.attachment_url && (
          <div>
            <div className="muted" style={{ fontSize: ".76rem" }}>
              {L("attachment")}
            </div>
            {/* الرابط المباشر يُردّ 401: التبويب الجديد لا يحمل
                رمز المصادقة. فالملف يُجلب بالرمز ثم يُفتح. */}
            <button
              onClick={() => openForView(req.attachment_url!)}
              style={{
                background: "none", border: "none", padding: 0,
                color: "var(--teal)", fontWeight: 500, font: "inherit",
                cursor: "pointer",
              }}>
              {L("openAttachment")}
            </button>
          </div>
        )}
      </div>

      {/* ق-71: المعتمِد يرى المراحل قبل أن يقرّر */}
      {req.approvals && req.approvals.length > 0 && (
        <div style={{
          marginBottom: 12, paddingTop: 10,
          borderTop: "1px solid var(--line)",
        }}>
          <ApprovalChain rows={req.approvals} />
        </div>
      )}

      {open ? (
        <div className="stack" style={{ gap: 8 }}>
          <input
            className="input"
            placeholder={L("comment")}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            autoFocus
          />
          <div className="row">
            <button
              className={`btn btn-sm ${open === "approved" ? "btn-primary" : "btn-danger"}`}
              disabled={busy}
              onClick={() => onDecide(req.id, open, comment)}
            >
              {L("confirm")}
            </button>
            <button className="btn btn-sm btn-ghost"
              onClick={() => { setOpen(null); setComment(""); }}>
              {L("cancel")}
            </button>
          </div>
        </div>
      ) : req.is_acknowledgement ? (
        /* ق-74: درجة علم — إحاطة لا موافقة، فزر واحد بلا رفض.
           والقرار يُرسل approved لأن السلسلة تمضي به، والمعنى
           «اطّلعت» لا «وافقت». */
        <div className="row">
          <button className="btn btn-sm btn-primary" disabled={busy}
            onClick={() => onDecide(req.id, "approved", "")}>
            <IcCheck size={16} />
            {L("acknowledge")}
          </button>
          <span className="muted" style={{ fontSize: ".8rem" }}>
            {L("ackHint")}
          </span>
        </div>
      ) : (
        <div className="row">
          <button className="btn btn-sm btn-primary" disabled={busy}
            onClick={() => setOpen("approved")}>
            <IcCheck size={16} />
            {L("approve")}
          </button>
          <button className="btn btn-sm btn-danger" disabled={busy}
            onClick={() => setOpen("rejected")}>
            <IcX size={16} />
            {L("reject")}
          </button>
        </div>
      )}
    </div>
  );
}

/* ══ جدول الطلبات ══ */

function RequestsTable({
  rows, L, showEmployee,
}: {
  rows: Req[];
  L: (k: string, f?: string) => string;
  showEmployee: boolean;
}) {
  /**
   * ق-71: الصف يتمدّد بالنقر فيُظهر مراحل الاعتماد.
   *
   * والتفاصيل تُجلب عند الفتح لا مع القائمة — فجلب سلسلة كل طلب
   * مقدّمًا يعني عشرات الاستعلامات لجدول قد لا يُفتح منه صف واحد.
   */
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Req | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  function toggle(id: number) {
    if (openId === id) { setOpenId(null); setDetail(null); return; }
    setOpenId(id);
    setDetail(null);
    setLoadingDetail(true);
    apiGet<Req>(`/leaves/requests/${id}/`)
      .then((d) => setDetail(d))
      .catch(() => setDetail(null))
      .finally(() => setLoadingDetail(false));
  }

  if (rows.length === 0) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)" }}>
        {L("empty")}
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="table">
        <colgroup>
          <col style={{ width: "150px" }} />
          {showEmployee && <col style={{ width: "200px" }} />}
          <col style={{ width: "140px" }} />
          <col style={{ width: "190px" }} />
          <col style={{ width: "80px" }} />
          <col style={{ width: "130px" }} />
        </colgroup>
        <thead>
          <tr>
            <th style={{ textAlign: "end" }}>{L("requestNo")}</th>
            {showEmployee && <th>{L("employee")}</th>}
            <th>{L("type")}</th>
            <th style={{ textAlign: "end" }}>{L("period")}</th>
            <th style={{ textAlign: "end" }}>{L("days")}</th>
            <th>{L("status")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <>
            <tr key={r.id} onClick={() => toggle(r.id)}
              style={{ cursor: "pointer" }}>
              <td style={{ textAlign: "end" }}>
                <span className="num" style={{ color: "var(--teal)" }}>
                  {r.request_no}
                </span>
              </td>
              {showEmployee && <td className="truncate">{r.employee_name}</td>}
              <td>{r.type_label}</td>
              <td style={{ textAlign: "end" }}>
                <span className="num">{payloadPeriod(r.payload)}</span>
              </td>
              <td style={{ textAlign: "end" }}>
                <span className="num">{payloadDays(r.payload)}</span>
              </td>
              <td>
                <span className={`badge ${STATUS_TONE[r.status] || "badge"}`}>
                  {r.status_label}
                </span>
              </td>
            </tr>

            {openId === r.id && (
              <tr key={`${r.id}-detail`}>
                <td colSpan={showEmployee ? 6 : 5}
                  style={{ background: "var(--paper-2)", padding: "14px 18px" }}>
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
                            <span className="num">{stamp(detail.closed_at)}</span>
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
                                background: "none", border: "none", padding: 0,
                                color: "var(--teal)", fontWeight: 500,
                                font: "inherit", cursor: "pointer",
                              }}>
                              {L("openAttachment")}
                            </button>
                          </div>
                        )}
                      </div>
                      {detail.note && (
                        <div className="muted" style={{ fontSize: ".85rem" }}>
                          {detail.note}
                        </div>
                      )}
                      <ApprovalChain rows={detail.approvals ?? []} />
                    </div>
                  ) : (
                    <span className="muted">{L("failed")}</span>
                  )}
                </td>
              </tr>
            )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}


type Deleg = {
  id: number;
  request_no: string;
  absentee: string;
  deputy: string;
  starts_on: string;
  ends_on: string;
  status: string;
  status_label: string;
};


/* ══ الشاشة ══ */

export default function LeavesPage() {
  const { L } = useT(T);

  const [approvals, setApprovals] = useState<Req[]>([]);
  const [all, setAll] = useState<Req[]>([]);
  const [mine, setMine] = useState<Req[]>([]);
  /** ق-75: إنابات تنتظر قراري — أقبل أو أعتذر */
  const [delegations, setDelegations] = useState<Deleg[]>([]);
  const [canApprove, setCanApprove] = useState(false);
  const [canViewAll, setCanViewAll] = useState(false);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(true);
  const [acting, setActing] = useState(false);
  const [toast, setToast] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    const jobs: Promise<void>[] = [];

    jobs.push(
      apiGet<Req[]>("/me/approvals/")
        .then((d) => { setApprovals(d); setCanApprove(true); })
        .catch(() => setCanApprove(false)),
    );

    jobs.push(
      apiGet<Req[]>(`/leaves/requests/${qs({ status })}`)
        .then((d) => { setAll(d); setCanViewAll(true); })
        .catch(() => setCanViewAll(false)),
    );

    jobs.push(
      apiGet<Req[]>("/me/requests/")
        .then(setMine)
        .catch(() => setMine([])),
    );
    // ق-75: إنابات تنتظر قراري
    jobs.push(
      apiGet<{ incoming: Deleg[] }>("/me/delegations/")
        .then((d) => setDelegations(
          (d.incoming || []).filter((x) => x.status === "pending")))
        .catch(() => setDelegations([])),
    );

    await Promise.all(jobs);
    setBusy(false);
  }, [status]);

  useEffect(() => { load(); }, [load]);

  /** ق-75: النائب يقبل الإنابة أو يعتذر — وبالاعتذار تمضي الإجازة */
  async function decideDelegation(id: number, accept: boolean) {
    setActing(true);
    try {
      await apiPost(`/delegations/${id}/decide/`, { accept });
      await load();
    } catch (e) {
      setToast((e as ApiError).message);
      setTimeout(() => setToast(""), 4000);
    } finally {
      setActing(false);
    }
  }

  async function decide(
    id: number,
    decision: "approved" | "rejected",
    comment: string,
  ) {
    setActing(true);
    try {
      await apiPost(`/leaves/requests/${id}/decide/`, { decision, comment });
      setToast(L("done"));
      await load();
    } catch (e) {
      setToast((e as ApiError).message || L("failed"));
    } finally {
      setActing(false);
      setTimeout(() => setToast(""), 3000);
    }
  }

  return (
    <div className="stack">
      <div className="spread">
        <h1>{L("title")}</h1>
        {toast && (
          <span className="badge badge-teal">{toast}</span>
        )}
      </div>

      {busy ? (
        <div className="card" style={{
          padding: 40, textAlign: "center", color: "var(--ink-3)",
        }}>
          {L("loading")}
        </div>
      ) : (
        <>
          {/* ══ إنابات تنتظر قراري (ق-75) ══ */}
          {delegations.length > 0 && (
            <section className="stack" style={{ gap: 10 }}>
              <div className="row">
                <IcAlert size={18} className="" />
                <h2 style={{ fontSize: "1.05rem" }}>
                  {L("delegations")}
                  <span className="badge badge-warn"
                    style={{ marginInlineStart: 8 }}>
                    <span className="num">{delegations.length}</span>
                  </span>
                </h2>
              </div>
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(330px, 1fr))",
                gap: 12,
              }}>
                {delegations.map((d) => (
                  <div key={d.id} className="card" style={{ padding: 18 }}>
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
                      <button className="btn btn-sm btn-primary"
                        disabled={acting}
                        onClick={() => decideDelegation(d.id, true)}>
                        <IcCheck size={16} />
                        {L("acceptDeleg")}
                      </button>
                      <button className="btn btn-sm btn-ghost"
                        disabled={acting}
                        onClick={() => decideDelegation(d.id, false)}>
                        {L("declineDeleg")}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ══ بانتظار اعتمادي ══ */}
          {canApprove && (
            <section className="stack" style={{ gap: 10 }}>
              <div className="row">
                <IcAlert size={18} className="" />
                <h2 style={{ fontSize: "1.05rem" }}>
                  {L("pending")}
                  {approvals.length > 0 && (
                    <span className="badge badge-warn"
                      style={{ marginInlineStart: 8 }}>
                      <span className="num">{approvals.length}</span>
                    </span>
                  )}
                </h2>
              </div>

              {approvals.length === 0 ? (
                <div className="card" style={{
                  padding: 24, textAlign: "center", color: "var(--ink-3)",
                }}>
                  {L("nothingPending")}
                </div>
              ) : (
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(330px, 1fr))",
                  gap: 12,
                }}>
                  {approvals.map((r) => (
                    <ApprovalCard key={r.id} req={r} L={L}
                      onDecide={decide} busy={acting} />
                  ))}
                </div>
              )}
            </section>
          )}

          {/* ══ كل الطلبات ══ */}
          {canViewAll && (
            <section className="stack" style={{ gap: 10 }}>
              <div className="spread">
                <h2 style={{ fontSize: "1.05rem" }}>{L("allRequests")}</h2>
                <div className="row" style={{ gap: 6 }}>
                  {["", "pending", "approved", "rejected"].map((s) => (
                    <button
                      key={s || "all"}
                      className={`btn btn-sm ${status === s ? "btn-primary" : ""}`}
                      onClick={() => setStatus(s)}
                    >
                      {L(s === "" ? "filterAll"
                        : s === "pending" ? "filterPending"
                        : s === "approved" ? "filterApproved"
                        : "filterRejected")}
                    </button>
                  ))}
                </div>
              </div>
              <div className="card" style={{ overflow: "hidden" }}>
                <RequestsTable rows={all} L={L} showEmployee />
              </div>
            </section>
          )}

          {/* ══ طلباتي ══ */}
          <section className="stack" style={{ gap: 10 }}>
            <div className="row">
              <IcLeave size={18} />
              <h2 style={{ fontSize: "1.05rem" }}>{L("myRequests")}</h2>
            </div>
            <div className="card" style={{ overflow: "hidden" }}>
              <RequestsTable rows={mine} L={L} showEmployee={false} />
            </div>
          </section>
        </>
      )}
    </div>
  );
}
