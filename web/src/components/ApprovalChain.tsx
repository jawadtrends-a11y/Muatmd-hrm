"use client";

/**
 * مراحل الاعتماد (ق-71 بند 3).
 *
 * مقدّم الطلب وكل المعتمِدين يرون أين وصل الطلب — ما قبلهم وما
 * بعدهم. فالموظف لا يسأل «وين وصل طلبي؟»، والمعتمِد يعرف من قرّر
 * قبله ومن ينتظره بعده.
 *
 * والدرجة المتخطّاة لا تظهر أصلًا: الخادم لا ينشئ لها سجلًا حين
 * لا شاغل لها (ق-35)، فالترقيم قد يقفز — وهذا صحيح لا خلل.
 */
import { useT, type Dict } from "@/lib/prefs";

const T: Dict = {
  chain: { ar: "مراحل الاعتماد", en: "Approval steps" },
  approved: { ar: "معتمد", en: "Approved" },
  rejected: { ar: "مرفوض", en: "Rejected" },
  delegated: { ar: "محوّل", en: "Delegated" },
  current: { ar: "بانتظار إجراء", en: "Awaiting action" },
  upcoming: { ar: "لم يصله بعد", en: "Not reached yet" },
  passed: { ar: "مضت", en: "Passed" },
  step: { ar: "درجة", en: "Step" },
};

export type ChainRow = {
  step: number;
  approver: string;
  decision: string;
  state: string;
  comment?: string;
  decided_at?: string | null;
};

/** لون كل حالة ورمزها — التمييز باللون والرمز معًا لا باللون وحده */
const STATE_STYLE: Record<string, { color: string; mark: string }> = {
  approved: { color: "var(--ok, #1B8A5A)", mark: "✓" },
  rejected: { color: "var(--danger)", mark: "✕" },
  delegated: { color: "var(--copper)", mark: "↪" },
  current: { color: "var(--teal)", mark: "●" },
  upcoming: { color: "var(--ink-3)", mark: "○" },
  passed: { color: "var(--ink-3)", mark: "–" },
  closed: { color: "var(--ink-3)", mark: "–" },
};

/**
 * التاريخ والوقت معًا — لا التاريخ وحده.
 *
 * فمن يراجع سلسلة اعتماد يحتاج معرفة متى قرّر كل معتمِد بالضبط:
 * إجازة قُدّمت الساعة الثامنة واعتُمدت الثامنة والنصف تختلف عن
 * واحدة انتظرت ثلاثة أيام — واليوم وحده يخفي الفرق.
 */
export function stamp(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const date = `${String(d.getDate()).padStart(2, "0")}/`
    + `${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}`;
  const time = `${String(d.getHours()).padStart(2, "0")}:`
    + `${String(d.getMinutes()).padStart(2, "0")}`;
  return `${date} ${time}`;
}

export default function ApprovalChain({ rows }: { rows: ChainRow[] }) {
  const { L } = useT(T);
  if (!rows || rows.length === 0) return null;

  /**
   * الرفض يوقف السلسلة (ق-71): من بعد الرافض لا يُعرض أصلًا.
   *
   * فعرضه بعبارة «لم يصله» أو «أُغلق قبله» يثير سؤالًا بلا فائدة —
   * والطلب انتهى، والحالة المرفوضة تكفي.
   */
  const cut = rows.findIndex((r) => r.state === "rejected");
  const shown = cut === -1 ? rows : rows.slice(0, cut + 1);

  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="muted" style={{ fontSize: ".78rem", fontWeight: 500 }}>
        {L("chain")}
      </div>
      {shown.map((r) => {
        const st = STATE_STYLE[r.state] ?? STATE_STYLE.upcoming;
        const isCurrent = r.state === "current";
        return (
          <div key={r.step} className="row" style={{
            gap: 8, alignItems: "flex-start", fontSize: ".86rem",
          }}>
            <span style={{
              color: st.color, fontWeight: 700, minWidth: 14,
              lineHeight: 1.5,
            }}>
              {st.mark}
            </span>
            <div style={{ flex: 1 }}>
              <div style={{
                color: isCurrent ? "var(--ink)" : "var(--ink-2)",
                fontWeight: isCurrent ? 600 : 500,
              }}>
                {r.approver}
                <span className="muted" style={{
                  fontSize: ".78rem", marginInlineStart: 8,
                }}>
                  {L(r.state)}
                  {r.decided_at && (
                    <> · <span className="num">{stamp(r.decided_at)}</span></>
                  )}
                </span>
              </div>
              {r.comment && (
                <div className="muted" style={{
                  fontSize: ".8rem", marginTop: 2,
                }}>
                  {r.comment}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
