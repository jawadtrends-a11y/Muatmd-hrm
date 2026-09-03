"use client";

/**
 * جرس الإشعارات.
 *
 * ما ينتظر انتباه المستخدم يجب أن يراه أينما كان — لا أن يفتح
 * شاشة ليكتشفه. والعدد يُحدَّث كل دقيقة، فالإشعار الذي يصل بعد
 * دقيقة ليس متأخرًا.
 */
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { apiGet, apiPost } from "@/lib/api";
import { useT, type Dict } from "@/lib/prefs";

const T: Dict = {
  title: { ar: "الإشعارات", en: "Notifications" },
  empty: { ar: "لا إشعارات", en: "No notifications" },
  markAll: { ar: "تعليم الكل مقروءًا", en: "Mark all read" },
};

type Notif = {
  id: number;
  title: string;
  body: string;
  link_url: string;
  is_read: boolean;
  created_at: string;
};

function ago(iso: string, lang: string): string {
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return lang === "en" ? "now" : "الآن";
  if (mins < 60) return lang === "en" ? `${mins}m` : `منذ ${mins} د`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return lang === "en" ? `${hrs}h` : `منذ ${hrs} س`;
  const days = Math.floor(hrs / 24);
  return lang === "en" ? `${days}d` : `منذ ${days} ي`;
}

export default function NotificationBell() {
  const { L, lang } = useT(T);
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [rows, setRows] = useState<Notif[]>([]);
  const boxRef = useRef<HTMLDivElement>(null);

  function load() {
    apiGet<{ unread: number; rows: Notif[] }>("/me/notifications/")
      .then((d) => { setUnread(d.unread); setRows(d.rows); })
      .catch(() => { setUnread(0); setRows([]); });
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, []);

  // النقر خارج اللوحة يُغلقها
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  async function markAll() {
    await apiPost("/me/notifications/read/", { all: true }).catch(() => null);
    load();
  }

  async function openOne(n: Notif) {
    if (!n.is_read) {
      await apiPost("/me/notifications/read/", { ids: [n.id] })
        .catch(() => null);
    }
    setOpen(false);
    load();
    if (n.link_url) router.push(n.link_url);
  }

  return (
    <div ref={boxRef} style={{ position: "relative" }}>
      <button
        onClick={() => { setOpen(!open); if (!open) load(); }}
        aria-label={L("title")}
        style={{
          background: "none", border: "none", cursor: "pointer",
          padding: 6, position: "relative", color: "var(--ink-2)",
          display: "flex", alignItems: "center",
        }}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="1.8"
          strokeLinecap="round" strokeLinejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unread > 0 && (
          <span style={{
            position: "absolute", top: 2, insetInlineEnd: 2,
            minWidth: 16, height: 16, padding: "0 4px",
            borderRadius: 8, background: "var(--danger)",
            color: "#fff", fontSize: ".68rem", fontWeight: 600,
            display: "flex", alignItems: "center", justifyContent: "center",
          }} className="num">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="card" style={{
          position: "absolute", top: "calc(100% + 8px)", insetInlineEnd: 0,
          width: 340, maxHeight: 420, overflowY: "auto", zIndex: 70,
          padding: 0,
        }}>
          <div className="spread" style={{
            padding: "12px 14px", borderBottom: "1px solid var(--line)",
            position: "sticky", top: 0, background: "var(--paper)",
          }}>
            <span style={{ fontWeight: 600 }}>{L("title")}</span>
            {unread > 0 && (
              <button className="btn btn-sm btn-ghost" onClick={markAll}>
                {L("markAll")}
              </button>
            )}
          </div>

          {rows.length === 0 ? (
            <div style={{
              padding: 32, textAlign: "center", color: "var(--ink-3)",
              fontSize: ".88rem",
            }}>
              {L("empty")}
            </div>
          ) : rows.map((n) => (
            <button key={n.id} onClick={() => openOne(n)} style={{
              display: "block", width: "100%", textAlign: "start",
              padding: "11px 14px", border: "none", cursor: "pointer",
              borderBottom: "1px solid var(--line)", font: "inherit",
              background: n.is_read ? "transparent" : "var(--teal-soft)",
            }}>
              <div className="spread" style={{ alignItems: "flex-start" }}>
                <span style={{
                  fontWeight: n.is_read ? 500 : 600, fontSize: ".9rem",
                }}>
                  {n.title}
                </span>
                <span className="muted" style={{
                  fontSize: ".72rem", flexShrink: 0,
                  marginInlineStart: 8,
                }}>
                  {ago(n.created_at, lang)}
                </span>
              </div>
              <div className="muted" style={{
                fontSize: ".82rem", marginTop: 3, lineHeight: 1.5,
              }}>
                {n.body}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
