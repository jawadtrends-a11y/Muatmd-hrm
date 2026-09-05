"""تهيئة Celery — الطوابير الخمسة المعزولة (الوثيقة المعمارية 2)."""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("muatmd_hrm")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.task_routes = {
    "apps.notifications.*": {"queue": "realtime"},
    "apps.payroll.*":       {"queue": "payroll"},
    "apps.attendance.*":    {"queue": "attendance"},
    "*.exports.*":          {"queue": "exports"},
}
app.conf.task_default_queue = "maintenance"

# ══ المهام المجدولة (ق-48، ق-49) ══
app.conf.beat_schedule = {
    # ملفات BioTime كل خمس دقائق (ق-85).
    #
    # فالجهاز يصدّرها دوريًّا، والانتظار ساعة يعني موظفًا يبصم
    # ولا يرى بصمته. وخمس دقائق تكفي: القراءة رخيصة والمجلد
    # فارغ غالبًا.
    "pull-biotime-files": {
        "task": "attendance.pull_biotime_files",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "maintenance"},
    },
    # لقطة الموظفين — أساس الفوترة بالذروة (ق-49)
    # بلا هذه اللقطة تصير الفوترة على عدد يوم الفاتورة وهو
    # قابل للتحايل بإيقاف موظفين قبلها وإعادتهم بعدها
    "snapshot-headcount": {
        "task": "billing.snapshot_headcount",
        "schedule": crontab(hour=0, minute=5),
        "options": {"queue": "maintenance"},
    },
    # تحديث حالات الاشتراكات — التجربة والمهلة والقراءة
    "evaluate-subscriptions": {
        "task": "billing.evaluate_subscriptions",
        "schedule": crontab(hour=1, minute=0),
        "options": {"queue": "maintenance"},
    },
    # التنبيه قبل الانتهاء — 5 أيام للشهري و15 للسنوي (ق-48)
    "renewal-alerts": {
        "task": "billing.send_renewal_alerts",
        "schedule": crontab(hour=8, minute=0),
        "options": {"queue": "realtime"},
    },
    # التجديد التلقائي لمن فعّله (ق-48)
    "auto-renewals": {
        "task": "billing.run_auto_renewals",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "maintenance"},
    },
}
app.conf.timezone = "Asia/Riyadh"


@app.task(bind=True)
def debug_task(self):
    return f"Celery يعمل — المهمة {self.request.id}"
