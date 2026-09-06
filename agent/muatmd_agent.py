"""
وسيط معتمد لأجهزة البصمة (ق-86).

يقرأ من جهاز ZKTeco في شبكة الشركة ويرفع البصمات لنظام معتمد.

ولا تضيع بصمة مهما انقطع: الجهاز يخزّنها، والوسيط يحفظ آخر ما
رفع، والنظام يتجاهل المكرّرة. فلو توقّف أسبوعًا قرأ عند عودته كل
ما تراكم.

التشغيل:
    python muatmd_agent.py            # يعمل دائمًا
    python muatmd_agent.py --once     # دورة واحدة ثم يخرج
    python muatmd_agent.py --test     # يفحص الاتصال ويخرج
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("ينقص requests — ثبّته: pip install requests")

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
STATE_PATH = APP_DIR / "state.json"
LOG_PATH = APP_DIR / "agent.log"

DEFAULT_CONFIG = {
    "system_url": "https://hr.muatmd.sa",
    "device_code": "",
    "device_key": "",
    "zk_host": "192.168.1.201",
    "zk_port": 4370,
    "zk_password": 0,
    "interval_seconds": 300,
    "batch_size": 400,
}

log = logging.getLogger("muatmd.agent")


def setup_logging():
    """
    سجل في ملف وعلى الشاشة — فمن يشكّ يقرأ الملف.

    والترميز يُفرض utf-8: طرفية ويندوز الافتراضية (cp1252) لا
    تطبع العربية، فتسقط الرسالة بـUnicodeEncodeError ويضيع الخطأ
    الحقيقي تحتها.
    """
    stream = sys.stdout
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:      # noqa: BLE001
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(stream),
        ],
    )


def load_config():
    """
    يقرأ الإعداد، ويُنشئ قالبًا إن لم يوجد.

    فمن يشغّله أول مرة يجد ملفًا يملؤه، لا خطأً يبحث عن سببه.
    """
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False),
            encoding="utf-8")
        raise SystemExit(
            f"أُنشئ ملف الإعداد: {CONFIG_PATH}\n"
            "املأ رمز الجهاز ومفتاحه وعنوان جهاز البصمة، ثم أعد "
            "التشغيل.")

    cfg = {**DEFAULT_CONFIG,
           **json.loads(CONFIG_PATH.read_text(encoding="utf-8"))}

    missing = [k for k in ("device_code", "device_key", "zk_host")
               if not cfg.get(k)]
    if missing:
        raise SystemExit(
            f"ينقص الإعداد: {'، '.join(missing)} — املأها في "
            f"{CONFIG_PATH}")
    return cfg


def load_state():
    """آخر بصمة رُفعت — منها يبدأ لا من أول السجل."""
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            log.warning("ملف الحالة تالف — سنقرأ آخر ثلاثين يومًا")
    return {}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False),
                          encoding="utf-8")


def read_device(cfg, since):
    """
    يقرأ البصمات من الجهاز.

    ويقرأ السجل كاملًا ثم يفلتر بالتاريخ: أجهزة ZKTeco لا تدعم
    الفلترة عند القراءة، والسجل بضعة آلاف لا أكثر.
    """
    try:
        from zk import ZK
    except ImportError:
        raise SystemExit("ينقص pyzk — ثبّته: pip install pyzk")

    zk = ZK(cfg["zk_host"], port=int(cfg["zk_port"]),
            password=int(cfg.get("zk_password") or 0), timeout=15)
    conn = None
    try:
        conn = zk.connect()
        # الجهاز يبقى يسجّل أثناء القراءة — فلا نعطّله
        records = conn.get_attendance() or []
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:      # noqa: BLE001
                pass

    rows = []
    for r in records:
        at = r.timestamp
        if since and at <= since:
            continue
        rows.append({
            "employee_no": str(r.user_id).strip(),
            "punched_at": at.isoformat(),
            "external_ref": f"{r.user_id}-{at.isoformat()}",
        })

    rows.sort(key=lambda x: x["punched_at"])
    return rows


def push(cfg, rows):
    """يرفع دفعة للنظام — والرد يفصّل ما قُبل وما تكرّر."""
    url = cfg["system_url"].rstrip("/") + "/api/attendance/ingest/"
    res = requests.post(
        url, json={"punches": rows},
        headers={
            "X-Device-Code": cfg["device_code"],
            "X-Device-Key": cfg["device_key"],
        },
        timeout=60)
    if res.status_code != 200:
        raise RuntimeError(f"{res.status_code}: {res.text[:200]}")
    return res.json()


def test_connection(cfg):
    """يفحص الطرفين قبل التشغيل — فمن يضبط يتأكد قبل أن ينتظر."""
    ok = True

    url = cfg["system_url"].rstrip("/") + "/api/attendance/ingest/ping/"
    try:
        res = requests.get(url, headers={
            "X-Device-Code": cfg["device_code"],
            "X-Device-Key": cfg["device_key"],
        }, timeout=20)
        if res.status_code == 200:
            log.info("النظام: متصل — %s", res.json().get("name_ar", ""))
        else:
            ok = False
            log.error("النظام: %s — %s", res.status_code, res.text[:120])
    except Exception as e:      # noqa: BLE001
        ok = False
        log.error("النظام: تعذّر الاتصال — %s", e)

    try:
        from zk import ZK
        zk = ZK(cfg["zk_host"], port=int(cfg["zk_port"]),
                password=int(cfg.get("zk_password") or 0), timeout=10)
        conn = zk.connect()
        log.info("الجهاز: متصل — %s سجلًا", len(conn.get_attendance() or []))
        conn.disconnect()
    except Exception as e:      # noqa: BLE001
        ok = False
        log.error("الجهاز: تعذّر الاتصال — %s", e)

    return ok


def run_once(cfg, state):
    """دورة واحدة: يقرأ ويرفع ويحفظ موضعه."""
    last = state.get("last_punch_at")
    since = datetime.fromisoformat(last) if last else (
        datetime.now() - timedelta(days=30))

    rows = read_device(cfg, since)
    if not rows:
        log.info("لا بصمات جديدة")
        return 0

    size = int(cfg.get("batch_size") or 400)
    total = 0

    for i in range(0, len(rows), size):
        chunk = rows[i:i + size]
        res = push(cfg, chunk)
        total += res.get("accepted", 0)

        # الموضع يُحفظ بعد كل دفعة نجحت: من ينقطع في المنتصف
        # يكمل من حيث وصل لا من البداية
        state["last_punch_at"] = chunk[-1]["punched_at"]
        save_state(state)

        log.info("دفعة: %s مقبولة · %s مكرّرة%s",
                 res.get("accepted"), res.get("duplicated"),
                 f" · مجهولون: {res['unknown_employees']}"
                 if res.get("unknown_employees") else "")

    return total


def main():
    parser = argparse.ArgumentParser(description="وسيط معتمد للبصمات")
    parser.add_argument("--once", action="store_true",
                        help="دورة واحدة ثم الخروج")
    parser.add_argument("--test", action="store_true",
                        help="فحص الاتصال ثم الخروج")
    args = parser.parse_args()

    setup_logging()
    cfg = load_config()

    if args.test:
        sys.exit(0 if test_connection(cfg) else 1)

    state = load_state()

    if args.once:
        run_once(cfg, state)
        return

    interval = int(cfg.get("interval_seconds") or 300)
    log.info("الوسيط يعمل — كل %s ثانية", interval)

    while True:
        try:
            run_once(cfg, state)
        except KeyboardInterrupt:
            log.info("توقّف بطلب المستخدم")
            return
        except Exception as e:      # noqa: BLE001
            # خطأ دورة لا يوقف الخدمة: الشبكة تنقطع والجهاز يُفصل،
            # والبصمات تبقى محفوظة حتى تعود
            log.error("فشلت الدورة — سنعيد بعد %ss: %s", interval, e)
        time.sleep(interval)


if __name__ == "__main__":
    main()
