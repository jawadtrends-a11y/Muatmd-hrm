"use client";

/**
 * عميل الـAPI — يطابق نمط المحاسبي.
 *
 * ⚠️⚠️ ق-٢٨٧: **التبويبات تتشارك الجلسة** (تنبيه جواد): كان التوكن في
 * `sessionStorage` — **خاصٌّ بكل تبويب**، فمن فتح تبويبًا ثانيًا وجد
 * نفسه خارجًا وأعاد التسجيل. وهو إرباكٌ لا أمان.
 *
 * ⚠️ **والبديل ليس بقاءً أبديًّا**: `localStorage` **بمدّة أربع وعشرين
 * ساعة** (قرار جواد) — فنظامٌ يعرض رواتب لا يبقى مفتوحًا أسبوعًا على
 * جهازٍ مشترك. والانتهاء يُفحص عند كل قراءة، فلا يُرسَل رمزٌ ميّت.
 *
 * وApiError تفرّق 401 عن الشبكة عن الخادم فتعرض الواجهة رسالة مفيدة
 * لا "حدث خطأ".
 */

const TOKEN_KEY = "muatmd_hr_token";
const TOKEN_EXP_KEY = "muatmd_hr_token_exp";
const TOKEN_TTL_MS = 24 * 60 * 60 * 1000;
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

export class ApiError extends Error {
  status: number;
  code: string;
  detail: unknown;

  constructor(status: number, message: string, code = "", detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }

  get isAuth() {
    return this.status === 401;
  }
  get isForbidden() {
    return this.status === 403;
  }
  get isNetwork() {
    return this.status === 0;
  }
  /** 428 — يحتاج تأكيدًا صريحًا (ق-46) */
  get needsConfirm() {
    return this.status === 428;
  }
  /** 409 — تعارض حالة: مسير غير معتمد، اشتراك منتهٍ… */
  get isConflict() {
    return this.status === 409;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const exp = Number(localStorage.getItem(TOKEN_EXP_KEY) || 0);
    // ⚠️ **المنتهي يُمسح لا يُرسَل** — فلا 401 متكرّرة ولا رمزٌ ميّت
    if (exp && Date.now() > exp) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(TOKEN_EXP_KEY);
      return null;
    }
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(TOKEN_EXP_KEY, String(Date.now() + TOKEN_TTL_MS));
    } else {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(TOKEN_EXP_KEY);
    }
  } catch {
    /* الوضع الخاص */
  }
}

function headers(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = {
    "Content-Type": "application/json",
    ...extra,
  };
  const t = getToken();
  if (t) h["Authorization"] = `Bearer ${t}`;

  /**
   * لغة الواجهة تُرسل مع كل طلب (ق-64).
   *
   * فالخادم يرجع أسماء الأقسام والمكوّنات والبنوك جاهزة بلغة
   * المستخدم — والاختيار في الخادم لا في عشرين شاشة.
   */
  if (typeof document !== "undefined") {
    const lang = document.documentElement.lang || "ar";
    h["Accept-Language"] = lang;
  }

  return h;
}

async function parse(res: Response) {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text.slice(0, 300) };
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  extraHeaders?: Record<string, string>,
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: headers(extraHeaders),
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "include",
    });
  } catch (e) {
    throw new ApiError(0, "تعذّر الاتصال بالخادم — تحقق من الشبكة",
      "network", e);
  }

  const data = await parse(res);

  if (!res.ok) {
    const d = data as { detail?: string; code?: string } | null;
    throw new ApiError(
      res.status,
      d?.detail || `خطأ ${res.status}`,
      d?.code || "",
      data,
    );
  }

  return data as T;
}

/**
 * رفع ملف (ق-70).
 *
 * لا يمر بـrequest لأن FormData يحتاج ألا يُضبط Content-Type —
 * المتصفح يضعه بنفسه مع الحدّ الفاصل، وضبطه يدويًا يفسد الطلب.
 */
export async function apiUpload<T = unknown>(
  path: string,
  file: File,
  field = "file",
  /** ق-172: حقولٌ تُرسل مع الملفّ — كنوع الإجازة وعلَم التنفيذ */
  extra?: Record<string, string>,
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const form = new FormData();
  for (const [k, v] of Object.entries(extra || {})) {
    form.append(k, v);
  }
  form.append(field, file);

  const h: Record<string, string> = {};
  const t = getToken();
  if (t) h["Authorization"] = `Bearer ${t}`;
  if (typeof document !== "undefined") {
    h["Accept-Language"] = document.documentElement.lang || "ar";
  }

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST", headers: h, body: form, credentials: "include",
    });
  } catch (e) {
    throw new ApiError(0, "تعذّر الاتصال بالخادم — تحقق من الشبكة",
      "network", e);
  }

  const data = await parse(res);
  if (!res.ok) {
    const d = data as { detail?: string; code?: string } | null;
    throw new ApiError(res.status, d?.detail || `خطأ ${res.status}`,
      d?.code || "", data);
  }
  return data as T;
}


export const apiGet = <T = unknown>(path: string) => request<T>("GET", path);
export const apiPost = <T = unknown>(path: string, body?: unknown,
  headers?: Record<string, string>) => request<T>("POST", path, body, headers);
export const apiPut = <T = unknown>(path: string, body?: unknown,
  headers?: Record<string, string>) => request<T>("PUT", path, body, headers);
export const apiPatch = <T = unknown>(path: string, body?: unknown) =>
  request<T>("PATCH", path, body);
// ق-131: الحذف قد يحتاج جسمًا — كنزع وسمٍ بعينه من موظف
export const apiDelete = <T = unknown>(path: string, body?: unknown) =>
  request<T>("DELETE", path, body);

/** بناء استعلام يتجاهل الفارغ */
export function qs(params: Record<string, unknown>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** تنزيل ملف (تصدير التقارير) */
export async function downloadFile(path: string, filename?: string) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const res = await fetch(url, { headers: headers(), credentials: "include" });
  if (!res.ok) {
    const d = await parse(res);
    throw new ApiError(res.status,
      (d as { detail?: string })?.detail || "تعذّر التنزيل");
  }

  const blob = await res.blob();
  const name =
    filename ||
    res.headers.get("Content-Disposition")?.match(/filename="?([^"]+)"?/)?.[1] ||
    "download";

  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

/** فتح ملف للعرض أو الطباعة (القسائم) */
export async function openForView(path: string) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const res = await fetch(url, { headers: headers(), credentials: "include" });
  if (!res.ok) throw new ApiError(res.status, "تعذّر فتح الملف");
  const blobUrl = URL.createObjectURL(await res.blob());
  window.open(blobUrl, "_blank");
  setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
}
