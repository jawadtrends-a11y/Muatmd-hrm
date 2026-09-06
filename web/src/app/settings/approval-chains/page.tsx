"use client";

/**
 * سلاسل الاعتماد (ق-71).
 *
 * السلسلة تُختار بنوع الطلب ودور مُقدِّمه: مدير الإدارة لا يعتمد
 * طلبه بنفسه، والمشرف لا يمرّ بمن دونه.
 *
 * والدرجات تُعرض ولا تُعدَّل هنا: تغيير من يعتمد ماذا يمسّ طلبات
 * قائمة في منتصف سلسلتها.
 */
import { useCallback, useEffect, useState } from "react";

import { apiDelete, apiGet, apiPost, apiPut, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import ConfirmDialog from "@/components/ConfirmDialog";
import { IcAlert, IcCheck, IcOrg, IcX } from "@/components/Icons";

const T: Dict = {
  title: { ar: "سلاسل الاعتماد", en: "Approval chains" },
  subtitle: {
    ar: "من يعتمد كل نوع من الطلبات وبأي ترتيب",
    en: "Who approves each request type, and in what order",
  },
  type: { ar: "نوع الطلب", en: "Request type" },
  name: { ar: "السلسلة", en: "Chain" },
  steps: { ar: "الدرجات", en: "Steps" },
  priority: { ar: "الأولوية", en: "Priority" },
  active: { ar: "نشطة", en: "Active" },
  inactive: { ar: "معطّلة", en: "Inactive" },
  edit: { ar: "تعديل", en: "Edit" },
  save: { ar: "حفظ", en: "Save" },
  cancel: { ar: "إلغاء", en: "Cancel" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  empty: { ar: "لا سلاسل", en: "No chains" },
  noAccess: { ar: "لا تملك هذه الصلاحية", en: "Not permitted" },
  mandatory: { ar: "إلزامية", en: "Mandatory" },
  optional: { ar: "اختيارية", en: "Optional" },
  ack: { ar: "درجة علم", en: "Acknowledgement" },
  sameDept: { ar: "في نفس الإدارة", en: "Same department" },
  stepsHint: {
    ar: "التعديل يسري على الطلبات الجديدة — والقائمة تُكمل بسلسلتها "
        + "كما بدأت",
    en: "Changes apply to new requests; existing ones keep their chain",
  },
  moveUp: { ar: "لأعلى", en: "Move up" },
  moveDown: { ar: "لأسفل", en: "Move down" },
  del: { ar: "حذف", en: "Delete" },
  addStep: { ar: "أضف درجة", en: "Add step" },
  tDirect: { ar: "المدير المباشر", en: "Direct manager" },
  tDept: { ar: "مدير الإدارة", en: "Department manager" },
  tRole: { ar: "دور محدَّد", en: "Specific role" },
  tPerson: { ar: "موظف بعينه", en: "Specific employee" },
  pickPerson: { ar: "اختر الموظف", en: "Pick employee" },
  rHr: { ar: "مدير الموارد البشرية", en: "HR manager" },
  rHrStaff: { ar: "موظف الموارد البشرية", en: "HR staff" },
  rCeo: { ar: "المدير العام", en: "CEO" },
  rOwner: { ar: "مالك الحساب", en: "Account owner" },
  confirmDelStep: {
    ar: "حذف هذه الدرجة؟ الطلبات الجديدة لن تمرّ بها.",
    en: "Delete this step? New requests will skip it.",
  },
  noStepsWarn: {
    ar: "لا درجات في هذه السلسلة — الطلبات ستُعتمد بلا مراجعة",
    en: "No steps: requests will be approved without review",
  },
  condition: { ar: "الشرط", en: "Condition" },
  submitterRole: { ar: "دور المُقدِّم", en: "Submitter role" },
  showSteps: { ar: "عرض السلسلة", en: "Show chain" },
  hideSteps: { ar: "إخفاء", en: "Hide" },
  viewFlow: { ar: "مخطّط", en: "Flow" },
  viewList: { ar: "قائمة", en: "List" },
  submitted: { ar: "الطلب يُقدَّم", en: "Request submitted" },
  approved: { ar: "يعتمد", en: "approves" },
  finalApproved: { ar: "معتمَد نهائيًّا", en: "Fully approved" },
  rejectNote: {
    ar: "الرفض في أي درجة يُنهي الطلب ويعيده لمقدّمه",
    en: "Rejection at any step ends the request",
  },
};

type Step = {
  id: number;
  step_order: number;
  approver_type: string;
  approver_type_label: string;
  approver_role_code: string;
  approver_person_name: string | null;
  is_mandatory: boolean;
  same_department: boolean;
  is_acknowledgement: boolean;
};

type Chain = {
  id: number;
  request_type: string;
  request_type_label: string;
  name_ar: string;
  condition: Record<string, unknown>;
  priority: number;
  is_active: boolean;
  steps: Step[];
};

/**
 * مخطّط السلسلة: الدرجات متتابعة، وأين ينتهي القبول والرفض.
 *
 * فمن يضبط سلسلة يرى مسارها لا قائمة أسماء — والرفض في أي درجة
 * يُنهي الطلب (ق-71).
 */
function ChainFlow({ chain, L }: {
  chain: Chain;
  L: (k: string, f?: string) => string;
}) {
  const box = (bg: string, fg: string) => ({
    padding: "10px 16px",
    borderRadius: "var(--radius-sm)",
    background: bg,
    color: fg,
    fontSize: ".88rem",
    fontWeight: 500,
    textAlign: "center" as const,
    minWidth: 170,
  });

  const arrow = (label: string, color: string) => (
    <div style={{
      display: "grid", placeItems: "center", padding: "2px 0",
    }}>
      <div style={{
        width: 1, height: 14, background: "var(--line)",
      }} />
      <span style={{
        fontSize: ".72rem", color, padding: "1px 0",
      }}>
        {label}
      </span>
      <div style={{
        width: 1, height: 14, background: "var(--line)",
      }} />
    </div>
  );

  return (
    <div style={{ display: "grid", placeItems: "center", padding: 8 }}>
      <div style={box("var(--paper-2)", "var(--ink-3)")}>
        {L("submitted")}
      </div>

      {chain.steps.map((s, i) => (
        <div key={s.id} style={{ display: "grid", placeItems: "center" }}>
          {arrow(i === 0 ? "" : L("approved"), "var(--teal)")}
          <div style={box(
            s.is_acknowledgement ? "var(--paper-2)" : "var(--teal-soft)",
            s.is_acknowledgement ? "var(--ink-2)" : "var(--teal)")}>
            <div>{s.approver_person_name || s.approver_type_label}</div>
            {s.is_acknowledgement && (
              <div style={{ fontSize: ".72rem", opacity: .75 }}>
                {L("ack")}
              </div>
            )}
          </div>
        </div>
      ))}

      {arrow(L("approved"), "var(--teal)")}
      <div style={box("var(--teal)", "#fff")}>
        {L("finalApproved")}
      </div>

      <div style={{
        marginTop: 16, fontSize: ".8rem", color: "var(--danger)",
        display: "flex", alignItems: "center", gap: 6,
      }}>
        <span style={{
          width: 8, height: 8, borderRadius: "50%",
          background: "var(--danger)",
        }} />
        {L("rejectNote")}
      </div>
    </div>
  );
}


export default function ApprovalChainsPage() {
  const { L } = useT(T);
  const [rows, setRows] = useState<Chain[]>([]);
  const [busy, setBusy] = useState(true);
  const [denied, setDenied] = useState(false);
  const [canEdit, setCanEdit] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  /** المخطّط يُظهر المسار، والقائمة تُظهر التفاصيل */
  const [asFlow, setAsFlow] = useState(true);
  const [newType, setNewType] = useState("direct_manager");
  const [newRole, setNewRole] = useState("hr_manager");
  const [newAck, setNewAck] = useState(false);
  const [newPerson, setNewPerson] = useState("");
  const [emps, setEmps] = useState<{
    id: number; employee_no: string; name_ar: string;
    person_id?: number;
  }[]>([]);
  const [askDel, setAskDel] = useState<{
    chain: number; step: number;
  } | null>(null);

  const load = useCallback(() => {
    apiGet<Chain[]>("/leaves/chains/")
      .then((d) => { setRows(d); setBusy(false); })
      .catch((e: ApiError) => {
        setDenied(e.status === 403);
        setBusy(false);
      });
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    apiGet<{ permissions: string[] }>("/me/workspace/")
      .then((d) =>
        setCanEdit((d.permissions || []).includes("leaves.manage")))
      .catch(() => setCanEdit(false));
    apiGet<{ id: number; employee_no: string; name_ar: string;
             person_id?: number }[]>("/employees/")
      .then(setEmps).catch(() => setEmps([]));
  }, []);

  async function stepAction(
    chainId: number, method: "POST" | "PUT" | "DELETE",
    body: Record<string, unknown>,
  ) {
    setErr("");
    try {
      const url = `/leaves/chains/${chainId}/steps/`;
      if (method === "POST") await apiPost(url, body);
      else if (method === "PUT") await apiPut(url, body);
      // apiDelete بلا جسم — فالمعرّف في المسار
      else await apiDelete(`${url}?step_id=${body.step_id}`);
      load();
    } catch (e) {
      setErr((e as ApiError).message);
      setTimeout(() => setErr(""), 6000);
    }
  }

  async function save(id: number) {
    setSaving(true);
    setErr("");
    try {
      await apiPut(`/leaves/chains/${id}/`, draft);
      setEditing(null);
      load();
    } catch (e) {
      setErr((e as ApiError).message);
    } finally {
      setSaving(false);
    }
  }

  if (denied) {
    return (
      <div className="card" style={{
        padding: 36, textAlign: "center", color: "var(--ink-3)",
      }}>
        <IcAlert size={22} />
        <div style={{ marginTop: 8 }}>{L("noAccess")}</div>
      </div>
    );
  }

  return (
    <div className="stack">
      <ConfirmDialog
        open={askDel !== null}
        tone="danger"
        confirmLabel={L("del")}
        message={L("confirmDelStep")}
        onCancel={() => setAskDel(null)}
        onConfirm={() => {
          const a = askDel;
          setAskDel(null);
          if (a) stepAction(a.chain, "DELETE", { step_id: a.step });
        }}
      />

      <div>
        <h1>{L("title")}</h1>
        <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
          {L("subtitle")}
        </div>
      </div>

      {err && (
        <div style={{
          background: "var(--danger-soft)", color: "var(--danger)",
          padding: "10px 14px", borderRadius: "var(--radius-sm)",
          fontSize: ".9rem",
        }}>
          {err}
        </div>
      )}

      {busy ? (
        <div className="card" style={{
          padding: 40, textAlign: "center", color: "var(--ink-3)",
        }}>
          {L("loading")}
        </div>
      ) : rows.length === 0 ? (
        <div className="card" style={{
          padding: 40, textAlign: "center", color: "var(--ink-3)",
        }}>
          <IcOrg size={22} />
          <div style={{ marginTop: 8 }}>{L("empty")}</div>
        </div>
      ) : (
        <div className="stack" style={{ gap: 10 }}>
          {rows.map((c) => (
            <div key={c.id} className="card" style={{
              opacity: c.is_active ? 1 : .6,
            }}>
              <div className="spread" style={{
                padding: "14px 18px", cursor: "pointer",
              }} onClick={() =>
                setOpen(open === c.id ? null : c.id)}>
                <div>
                  {editing === c.id ? (
                    <input className="input" style={{ maxWidth: 300 }}
                      value={String(draft.name_ar ?? "")}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => setDraft((d) => ({
                        ...d, name_ar: e.target.value,
                      }))} />
                  ) : (
                    <div style={{ fontWeight: 600 }}>{c.name_ar}</div>
                  )}
                  <div className="muted" style={{
                    fontSize: ".8rem", marginTop: 3,
                  }}>
                    {c.request_type_label}
                    {" · "}
                    {c.steps.length} {L("steps")}
                    {c.condition?.submitter_role ? (
                      <> · {L("submitterRole")}:{" "}
                        <span className="num">
                          {String(c.condition.submitter_role)}
                        </span>
                      </>
                    ) : null}
                  </div>
                </div>

                <div className="row" style={{ gap: 8 }}>
                  {/* زر صريح: الضغط على البطاقة وحده لا يُرى،
                      ومن يعدّل اسمها لا يُفتح شيء */}
                  <button className="btn btn-sm btn-ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpen(open === c.id ? null : c.id);
                    }}>
                    {open === c.id ? L("hideSteps") : L("showSteps")}
                  </button>

                  <span className={c.is_active
                    ? "badge badge-ok" : "badge"}>
                    {c.is_active ? L("active") : L("inactive")}
                  </span>

                  {canEdit && (editing === c.id ? (
                    <div className="row" style={{ gap: 4 }}
                      onClick={(e) => e.stopPropagation()}>
                      <button className="btn btn-sm btn-primary"
                        disabled={saving} onClick={() => save(c.id)}>
                        <IcCheck size={15} />
                        {L("save")}
                      </button>
                      <button className="btn btn-sm btn-ghost"
                        onClick={() => setEditing(null)}>
                        <IcX size={15} />
                      </button>
                    </div>
                  ) : (
                    <button className="btn btn-sm btn-ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDraft({
                          name_ar: c.name_ar,
                          is_active: c.is_active,
                          priority: c.priority,
                        });
                        setEditing(c.id);
                      }}>
                      {L("edit")}
                    </button>
                  ))}
                </div>
              </div>

              {editing === c.id && (
                <div className="row" style={{
                  padding: "0 18px 14px", gap: 18,
                }}>
                  <label className="row" style={{
                    gap: 7, cursor: "pointer",
                  }}>
                    <input type="checkbox"
                      checked={!!draft.is_active}
                      onChange={(e) => setDraft((d) => ({
                        ...d, is_active: e.target.checked,
                      }))}
                      style={{ width: 17, height: 17,
                               accentColor: "var(--teal)" }} />
                    <span style={{ fontSize: ".88rem" }}>{L("active")}</span>
                  </label>

                  <div className="row" style={{ gap: 7 }}>
                    <span className="muted" style={{ fontSize: ".88rem" }}>
                      {L("priority")}
                    </span>
                    <input className="input num" style={{ width: 80 }}
                      value={String(draft.priority ?? "")}
                      onChange={(e) => setDraft((d) => ({
                        ...d, priority: e.target.value,
                      }))} />
                  </div>
                </div>
              )}

              {open === c.id && (
                <div style={{
                  borderTop: "1px solid var(--line)",
                  padding: "12px 18px",
                }}>
                  <div className="muted" style={{
                    fontSize: ".8rem", marginBottom: 10,
                  }}>
                    {L("stepsHint")}
                  </div>

                  <div className="row" style={{
                    gap: 6, marginBottom: 12,
                  }}>
                    <button className={`btn btn-sm ${
                      asFlow ? "btn-primary" : "btn-ghost"}`}
                      onClick={() => setAsFlow(true)}>
                      {L("viewFlow")}
                    </button>
                    <button className={`btn btn-sm ${
                      !asFlow ? "btn-primary" : "btn-ghost"}`}
                      onClick={() => setAsFlow(false)}>
                      {L("viewList")}
                    </button>
                  </div>

                  {asFlow ? (
                    <ChainFlow chain={c} L={L} />
                  ) : (
                  <>
                  {c.steps.map((s) => (
                    <div key={s.id} className="row" style={{
                      gap: 10, padding: "8px 0",
                      borderBottom: "1px solid var(--line)",
                    }}>
                      <span className="num" style={{
                        width: 26, height: 26, borderRadius: "50%",
                        background: s.is_acknowledgement
                          ? "var(--paper-2)" : "var(--teal-soft)",
                        color: s.is_acknowledgement
                          ? "var(--ink-3)" : "var(--teal)",
                        display: "grid", placeItems: "center",
                        fontSize: ".8rem", flexShrink: 0,
                      }}>
                        {s.step_order}
                      </span>

                      <div className="grow">
                        <span style={{ fontSize: ".9rem" }}>
                          {s.approver_person_name
                            || s.approver_type_label}
                        </span>
                        {s.approver_role_code && (
                          <span className="num muted" style={{
                            fontSize: ".78rem", marginInlineStart: 6,
                          }}>
                            {s.approver_role_code}
                          </span>
                        )}
                      </div>

                      <div className="row" style={{ gap: 5 }}>
                        {s.is_acknowledgement && (
                          <span className="badge" style={{
                            fontSize: ".72rem",
                          }}>
                            {L("ack")}
                          </span>
                        )}
                        {s.same_department && (
                          <span className="badge" style={{
                            fontSize: ".72rem",
                          }}>
                            {L("sameDept")}
                          </span>
                        )}
                        <span className="muted" style={{
                          fontSize: ".76rem",
                        }}>
                          {s.is_mandatory
                            ? L("mandatory") : L("optional")}
                        </span>

                        {canEdit && (
                          <div className="row" style={{ gap: 3 }}>
                            <button className="btn btn-sm btn-ghost"
                              title={L("moveUp")}
                              disabled={s.step_order === 1}
                              onClick={() => stepAction(c.id, "PUT", {
                                step_id: s.id, move: "up",
                              })}>
                              ↑
                            </button>
                            <button className="btn btn-sm btn-ghost"
                              title={L("moveDown")}
                              disabled={s.step_order === c.steps.length}
                              onClick={() => stepAction(c.id, "PUT", {
                                step_id: s.id, move: "down",
                              })}>
                              ↓
                            </button>
                            <button className="btn btn-sm btn-ghost"
                              style={{ color: "var(--danger)" }}
                              onClick={() => setAskDel({
                                chain: c.id, step: s.id,
                              })}>
                              {L("del")}
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}

                  {canEdit && (
                    <div className="row" style={{
                      gap: 8, paddingTop: 12, flexWrap: "wrap",
                    }}>
                      <select className="select"
                        style={{ maxWidth: 210 }}
                        value={newType}
                        onChange={(e) => setNewType(e.target.value)}>
                        <option value="direct_manager">
                          {L("tDirect")}
                        </option>
                        <option value="department_head">
                          {L("tDept")}
                        </option>
                        <option value="role">{L("tRole")}</option>
                        <option value="specific_person">{L("tPerson")}</option>
                      </select>

                      {newType === "specific_person" && (
                        <select className="select"
                          style={{ maxWidth: 250 }}
                          value={newPerson}
                          onChange={(e) => setNewPerson(e.target.value)}>
                          <option value="">— {L("pickPerson")} —</option>
                          {emps.map((e) => (
                            <option key={e.id}
                              value={e.person_id ?? e.id}>
                              {e.employee_no} — {e.name_ar}
                            </option>
                          ))}
                        </select>
                      )}

                      {newType === "role" && (
                        <select className="select"
                          style={{ maxWidth: 210 }}
                          value={newRole}
                          onChange={(e) => setNewRole(e.target.value)}>
                          <option value="hr_manager">{L("rHr")}</option>
                          <option value="hr_staff">{L("rHrStaff")}</option>
                          <option value="ceo">{L("rCeo")}</option>
                          <option value="owner">{L("rOwner")}</option>
                        </select>
                      )}

                      <label className="row" style={{
                        gap: 6, cursor: "pointer",
                      }}>
                        <input type="checkbox" checked={newAck}
                          onChange={(e) => setNewAck(e.target.checked)}
                          style={{ width: 16, height: 16,
                                   accentColor: "var(--teal)" }} />
                        <span style={{ fontSize: ".85rem" }}>
                          {L("ack")}
                        </span>
                      </label>

                      <button className="btn btn-sm btn-primary"
                        onClick={() => stepAction(c.id, "POST", {
                          approver_type: newType,
                          approver_role_code:
                            newType === "role" ? newRole : "",
                          approver_person_id:
                            newType === "specific_person" ? newPerson : null,
                          is_acknowledgement: newAck,
                        })}>
                        {L("addStep")}
                      </button>
                    </div>
                  )}

                  {c.steps.length === 0 && (
                    <div style={{
                      background: "var(--danger-soft)",
                      color: "var(--danger)",
                      padding: "10px 14px", marginTop: 10,
                      borderRadius: "var(--radius-sm)",
                      fontSize: ".85rem",
                    }}>
                      {L("noStepsWarn")}
                    </div>
                  )}
                  </>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
