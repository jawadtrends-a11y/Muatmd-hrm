"use client";
/**
 * عرض نصّ الخطاب بتنسيقه (ق-197).
 *
 * ⚠️⚠️ **والشاشة كانت تُظهر الوسم نصًّا** (بلاغ جواد): فالنصّ
 * يحمل `<p align="center">` — **ويُعرض حرفيًّا**.
 *
 * ⚠️ **ويقرأ ما يقرؤه مولّد PDF نفسه** — **فما يراه الكاتب هو
 * ما يُطبع**.
 */
import React from "react";

const ALIGN: Record<string, "right" | "center" | "left" | "justify"> = {
  right: "right", center: "center", left: "left", justify: "justify",
};
const SIZE: Record<string, string> = {
  small: ".85rem", normal: ".95rem", large: "1.15rem",
};

/** ⚠️ **ووسومٌ ثلاثة لا غير** — فما عداها يُعرض نصًّا */
function inline(text: string): React.ReactNode[] {
  const parts = text.split(/(<\/?[biu]>|<br\s*\/?>)/);
  const out: React.ReactNode[] = [];
  const open: string[] = [];

  parts.forEach((p, i) => {
    if (/^<br\s*\/?>$/.test(p)) { out.push(<br key={i} />); return; }
    const m = p.match(/^<(\/?)([biu])>$/);
    if (m) {
      if (m[1]) open.pop();
      else open.push(m[2]);
      return;
    }
    if (!p) return;
    let node: React.ReactNode = p;
    [...open].reverse().forEach((t) => {
      node = t === "b" ? <strong>{node}</strong>
        : t === "i" ? <em>{node}</em> : <u>{node}</u>;
    });
    out.push(<React.Fragment key={i}>{node}</React.Fragment>);
  });
  return out;
}

export default function LetterBody({ body }: { body: string }) {
  const raw = body || "";
  const nodes: React.ReactNode[] = [];
  const re = /<p([^>]*)>([\s\S]*?)<\/p>/g;
  let pos = 0;
  let m: RegExpExecArray | null;
  let k = 0;

  const plain = (chunk: string) => {
    chunk.split("\n").forEach((line) => {
      if (line.trim()) {
        nodes.push(
          <p key={`p${k++}`}
             style={{ margin: "0 0 12px", lineHeight: 2.1 }}>
            {inline(line.trim())}
          </p>,
        );
      }
    });
  };

  while ((m = re.exec(raw)) !== null) {
    if (m.index > pos) plain(raw.slice(pos, m.index));
    const attrs = m[1] || "";
    const a = attrs.match(/align="([a-z]+)"/)?.[1] || "";
    const sz = attrs.match(/size="([a-z]+)"/)?.[1] || "";
    nodes.push(
      <p key={`t${k++}`} style={{
        margin: "0 0 12px", lineHeight: 2.1,
        textAlign: ALIGN[a] || undefined,
        fontSize: SIZE[sz] || undefined,
      }}>
        {inline((m[2] || "").trim())}
      </p>,
    );
    pos = m.index + m[0].length;
  }
  if (pos < raw.length) plain(raw.slice(pos));

  return <div>{nodes}</div>;
}
