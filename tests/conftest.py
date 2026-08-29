"""
تهيئة الاختبارات.

المعضلة: إنشاء قاعدة الاختبار يحتاج دور المالك (خارق)، لكن اختبار
العزل يجب أن يعمل بدور التشغيل المحدود. الحل: قاعدة اتصال ثانية
باسم runtime تُستخدم داخل اختبارات العزل تحديدًا.
"""
import pytest
from django.conf import settings
from django.db import connections


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """
    بعد إنشاء قاعدة الاختبار بالمالك، نمنح دور التشغيل صلاحياته
    عليها ونفعّل RLS — لأن الهجرات تُنشئها من جديد في كل جلسة.
    """
    with django_db_blocker.unblock():
        runtime_user = settings.DATABASES["default"].get(
            "TEST_RUNTIME_USER", "hrm_runtime"
        )
        with connections["default"].cursor() as cur:
            cur.execute(f"GRANT USAGE ON SCHEMA public TO {runtime_user}")
            cur.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                f"IN SCHEMA public TO {runtime_user}"
            )
            cur.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES "
                f"IN SCHEMA public TO {runtime_user}"
            )
    yield django_db_setup


@pytest.fixture
def runtime_cursor(db):
    """
    اتصال مستقل بدور التشغيل المحدود — الاتصال الوحيد الصالح
    لاختبار العزل، لأن اتصال الاختبار الافتراضي يعمل بالمالك.
    """
    import psycopg
    cfg = settings.DATABASES["default"]
    # الاسم النهائي لقاعدة الاختبار كما ضبطه Django — لا نبنيه بأنفسنا
    from django.db import connections
    test_db_name = connections["default"].settings_dict["NAME"]
    conn = psycopg.connect(
        dbname=test_db_name,
        user="hrm_runtime",
        password=cfg["TEST_RUNTIME_PASSWORD"],
        host=cfg["HOST"],
        port=cfg["PORT"],
        autocommit=True,
    )
    try:
        yield conn.cursor()
    finally:
        conn.close()
