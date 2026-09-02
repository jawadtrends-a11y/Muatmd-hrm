"use client";

/**
 * صورة محمية بالمصادقة.
 *
 * وسم img لا يرسل ترويسة Authorization، فرابط /api/files/3/ يُردّ
 * 401 وتظهر الصورة مكسورة. فنجلبها بالرمز ونعرضها من الذاكرة.
 *
 * والبديل — رابط موقّت أو كوكي — يفتح الملف لمن يعرف المسار،
 * وق-61 ينصّ: من يعرف المسار لا يصل، ومن له حق الوصول يصل.
 */
import { useEffect, useState } from "react";

import { API_BASE, getToken } from "@/lib/api";

export default function AuthImage({
  src, alt = "", style, className,
}: {
  /** مسار الملف كما يرسله الخادم — مثل /files/3/ */
  src: string | null | undefined;
  alt?: string;
  style?: React.CSSProperties;
  className?: string;
}) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!src) { setUrl(null); return; }
    let alive = true;
    let objectUrl: string | null = null;

    const headers: Record<string, string> = {};
    const t = getToken();
    if (t) headers["Authorization"] = `Bearer ${t}`;

    fetch(src.startsWith("http") ? src : `${API_BASE}${src}`,
          { headers, credentials: "include" })
      .then((r) => (r.ok ? r.blob() : Promise.reject(r.status)))
      .then((b) => {
        if (!alive) return;
        objectUrl = URL.createObjectURL(b);
        setUrl(objectUrl);
      })
      .catch(() => { if (alive) setUrl(null); });

    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);

  if (!url) return null;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt={alt} style={style} className={className} />;
}
