"""
واجهة إعداد وسيط معتمد (ق-86).

نافذة صغيرة تملأ ملف الإعداد وتفحص الاتصال — فمن يضبط الوسيط ليس
مبرمجًا، ولا يفتح ملفات JSON.
"""
import json
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, StringVar, Tk, X, messagebox, ttk

# مجلد الملف التنفيذي لا مجلد الاستخراج المؤقّت: PyInstaller
# يفكّ المحتوى في مجلد مؤقّت، و__file__ يشير إليه — فلا يجد
# البرنامج إعداده ولا يكتب سجلّه بجانب نفسه.
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"

FIELDS = [
    ("system_url", "رابط النظام", "https://hr.muatmd.sa"),
    ("device_code", "رمز الجهاز", ""),
    ("device_key", "مفتاح الجهاز", ""),
    ("zk_host", "عنوان جهاز البصمة", "192.168.1.201"),
    ("zk_port", "منفذ الجهاز", "4370"),
    ("zk_password", "كلمة مرور الجهاز", "0"),
    ("interval_seconds", "كل كم ثانية", "300"),
]


def load():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {}


class SetupWindow:
    def __init__(self, root):
        self.root = root
        root.title("إعداد وسيط معتمد")
        root.geometry("560x420")

        cfg = load()
        self.vars = {}

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill=BOTH, expand=True)

        ttk.Label(
            frame,
            text="املأ البيانات من شاشة أجهزة البصمة في النظام",
            font=("Segoe UI", 10),
        ).pack(anchor="e", pady=(0, 14))

        for key, label, default in FIELDS:
            row = ttk.Frame(frame)
            row.pack(fill=X, pady=4)

            ttk.Label(row, text=label, width=20, anchor="e").pack(
                side=RIGHT, padx=(8, 0))

            var = StringVar(value=str(cfg.get(key, default)))
            self.vars[key] = var

            show = "*" if key == "device_key" else ""
            ttk.Entry(row, textvariable=var, show=show).pack(
                side=RIGHT, fill=X, expand=True)

        self.status = ttk.Label(frame, text="", foreground="#555")
        self.status.pack(anchor="e", pady=(14, 6))

        buttons = ttk.Frame(frame)
        buttons.pack(fill=X, pady=(6, 0))

        ttk.Button(buttons, text="حفظ", command=self.save).pack(
            side=RIGHT, padx=4)
        ttk.Button(buttons, text="فحص الاتصال",
                   command=self.test).pack(side=RIGHT, padx=4)
        ttk.Button(buttons, text="إغلاق",
                   command=root.destroy).pack(side=LEFT, padx=4)

    def collect(self):
        cfg = {k: v.get().strip() for k, v in self.vars.items()}
        for num in ("zk_port", "zk_password", "interval_seconds"):
            try:
                cfg[num] = int(cfg[num] or 0)
            except ValueError:
                cfg[num] = 0
        cfg["batch_size"] = 400
        return cfg

    def save(self):
        cfg = self.collect()
        missing = [lbl for k, lbl, _ in FIELDS
                   if k in ("device_code", "device_key", "zk_host")
                   and not cfg.get(k)]
        if missing:
            messagebox.showwarning(
                "ينقص", "املأ: " + "، ".join(missing))
            return

        CONFIG_PATH.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False),
            encoding="utf-8")
        self.status.config(text="حُفظ الإعداد", foreground="#0a7")

    def test(self):
        """
        الفحص في خيط منفصل: النافذة تتجمّد لو انتظرت الشبكة، ومن
        يراها متجمّدة يظنّها معطّلة.
        """
        self.save()
        if not CONFIG_PATH.exists():
            return

        self.status.config(text="جارٍ الفحص…", foreground="#555")
        self.root.update_idletasks()

        def run():
            # الفحص يستدعي المنطق مباشرةً لا ملفًا خارجيًا: الملف
            # المحزّم لا يجد muatmd_agent.py بجانبه، فيرجع رمز
            # نجاح كاذبًا — ومن يضبط الوسيط يرى «سليم» ولا تصل
            # بصمة.
            import io
            import logging as _logging

            buf = io.StringIO()
            handler = _logging.StreamHandler(buf)
            handler.setFormatter(_logging.Formatter("%(message)s"))

            agent_log = _logging.getLogger("muatmd.agent")
            agent_log.addHandler(handler)
            agent_log.setLevel(_logging.INFO)

            try:
                from muatmd_agent import load_config, test_connection

                ok = test_connection(load_config())
            except Exception as e:
                ok = False
                buf.write(str(e))
            finally:
                agent_log.removeHandler(handler)

            out = buf.getvalue()
            self.root.after(0, lambda: self.show_result(ok, out))

        threading.Thread(target=run, daemon=True).start()

    def show_result(self, ok, out):
        if ok:
            self.status.config(text="الاتصال سليم بالطرفين",
                               foreground="#0a7")
        else:
            self.status.config(text="فشل الفحص — راجع التفاصيل",
                               foreground="#c33")
            messagebox.showerror("نتيجة الفحص", out[-1200:] or "بلا تفاصيل")


def main():
    root = Tk()
    SetupWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
