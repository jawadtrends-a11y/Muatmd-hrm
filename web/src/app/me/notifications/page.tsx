"use client";
/**
 * إشعاراتي — أرشيف للمراجعة لا تنبيهًا.
 *
 * الجرس يعرض ما يستحقّ الانتباه الآن ويختفي؛ وهذه تبقى: من فاته
 * إعلان قبل شهر يجده، ويقرأ نصّه كاملًا بمرفقاته.
 */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";
import { IcAlert, IcCheck, IcDoc } from "@/components/Icons";

const T: Dict = {
  title: { ar: "إشعاراتي", en: "My notifications" },
  subtitle: { ar: "كل ما وصلك — للمراجعة في أي وقت",
              en: "Everything you received — review any time" },
  markAll: { ar: "تعليم الكل مقروءًا", en: "Mark all read" },
  empty: { ar: "لا إشعارات بعد", en: "No notifications yet" },
  loading: { ar: "جارٍ التحميل…", en: "Loading…" },
  more: { ar: "عرض المزيد", en: "Show more" },
  unread: { ar: "غير مقروء", en: "Unread" },
  all: { ar: "الكل", en: "All" },
  announcements: { ar: "الإعلانات", en: "Announcements" },
  attach: { ar: "مرفقات", en: "Attachments" },
  general: { ar: "إعلان عام", en: "General" },
  event: { ar: "فعالية", en: "Event" },
  meeting: { ar: "اجتماع", en: "Meeting" },
  congrats: { ar: "تهنئة", en: "Congratulations" },
  condolence: { ar: "تعزية", en: "Condolence" },
  decision: { ar: "قرار إداري", en: "Decision" },
};

const KIND_COLOR: Record<string, string> = {
  general: "var(--ink-3)",
  event: "var(--teal)",
  meeting: "var(--teal)",
  congrats: "var(--ok)",
  condolence: "var(--ink-2)",
  decision: "var(--copper)",
};

type Att = { id: number; name: string; size: string };
type Row = {
  id: number; title: string; body: string;
  event_key: string; kind: string; link_url: string;
  is_read: boolean; created_at: string; attachments: Att[];
};

function when(iso: string, lang: string) {
  const d = new Date(iso);
  return d.toLocaleDateString(lang === "en" ? "en-GB" : "ar-SA", {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function MyNotificationsPage() {
  const { L, lang } = useT(T);
  const [rows, setRows] = useState<Row[]>([]);
  const [page, setPage] = useState(1);
  const [more, setMore] = useState(false);
  const [unread, setUnread] = useState(0);
  const [busy, setBusy] = useState(true);
  const [onlyAnn, setOnlyAnn] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(async (p: number, filter: boolean) => {
    setBusy(true);
    try {
      const q = filter ? "&event_key=announcement.published" : "";
      const d = await apiGet<{
        rows: Row[]; unread: number; has_more: boolean;
      }>(`/me/notifications/archive/?page=${p}${q}`);
      setRows((old) => (p === 1 ? d.rows : [...old, ...d.rows]));
      setUnread(d.unread);
      setMore(d.has_more);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => { load(1, onlyAnn); setPage(1); }, [onlyAnn, load]);

  const markAll = async () => {
    await apiPost("/me/notifications/read/", { all: true }).catch(() => null);
    setRows((r) => r.map((x) => ({ ...x, is_read: true })));
    setUnread(0);
  };

  return (
    <div className="stack">
      <div className="spread">
        <div>
          <h1 style={{ margin: 0 }}>{L("title")}</h1>
          <div className="muted" style={{ fontSize: ".88rem", marginTop: 2 }}>
            {L("subtitle")}
          </div>
        </div>
        {unread > 0 && (
          <button className="btn btn-sm" onClick={markAll}>
            <IcCheck size={15} /> {L("markAll")}
          </button>
        )}
      </div>

      <div className="row" style={{ gap: 6 }}>
        <button className={`btn btn-sm ${!onlyAnn ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setOnlyAnn(false)}>{L("all")}</button>
        <button className={`btn btn-sm ${onlyAnn ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setOnlyAnn(true)}>{L("announcements")}</button>
      </div>

      {err && (
        <div className="card" style={{ borderColor: "var(--danger)" }}>
          <IcAlert /> {err}
        </div>
      )}

      {busy && rows.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: "center",
                                       color: "var(--ink-3)" }}>
          {L("loading")}
        </div>
      ) : rows.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: "center",
                                       color: "var(--ink-3)" }}>
          {L("empty")}
        </div>
      ) : (
        <div className="stack" style={{ gap: 10 }}>
          {rows.map((n) => (
            <div key={n.id} className="card" style={{
              padding: 18,
              borderInlineStartWidth: 3,
              borderInlineStartStyle: "solid",
              borderInlineStartColor: n.kind
                ? (KIND_COLOR[n.kind] || "var(--line)") : "var(--line)",
              background: n.is_read ? undefined : "var(--teal-soft)",
            }}>
              <div className="spread" style={{ alignItems: "flex-start" }}>
                <div style={{ fontWeight: 600 }}>{n.title}</div>
                <span className="muted" style={{ fontSize: ".76rem",
                                                 flexShrink: 0,
                                                 marginInlineStart: 10 }}>
                  {when(n.created_at, lang)}
                </span>
              </div>
              {n.kind && (
                <div style={{ fontSize: ".74rem", marginTop: 4,
                              color: KIND_COLOR[n.kind] || "var(--ink-3)" }}>
                  {L(n.kind, n.kind)}
                </div>
              )}
              <div style={{ marginTop: 8, fontSize: ".92rem",
                            lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
                {n.body}
              </div>
              {n.attachments.length > 0 && (
                <div style={{ marginTop: 12, paddingTop: 10,
                              borderTop: "1px solid var(--line)" }}>
                  <div className="muted" style={{ fontSize: ".78rem",
                                                  marginBottom: 6 }}>
                    {L("attach")}
                  </div>
                  <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
                    {n.attachments.map((a) => (
                      <a key={a.id} className="btn btn-sm"
                         href={`/api/files/${a.id}/`} target="_blank"
                         rel="noopener noreferrer">
                        <IcDoc size={14} /> {a.name}
                        <span className="muted" style={{ fontSize: ".74rem" }}>
                          {a.size}
                        </span>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
          {more && (
            <button className="btn" disabled={busy}
                    onClick={() => { const p = page + 1; setPage(p); load(p, onlyAnn); }}>
              {busy ? L("loading") : L("more")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
