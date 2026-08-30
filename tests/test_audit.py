"""حرّاس سجل عمليات المنشأة (ق-44)."""
from datetime import date
from decimal import Decimal as D

import pytest

from apps.accounts.models import Account, Company
from apps.accounts.services.provisioning import provision_account
from apps.core.models_audit import AuditAction, AuditEntry
from apps.core.services.audit import (
    history_for, log_action, log_change, log_create, log_delete,
    object_type_of, serialize_entry, snapshot,
)
from apps.core.tenancy.context import account_scope
from apps.employees.services.hiring import (
    create_employment, create_person, set_salary_structure,
)
from apps.payroll.models import PayComponent, PayrollRunType, PayrollSettings
from apps.payroll.services.engine import (
    approve_run, calculate_run, create_run, submit_run,
)
from apps.payroll.services.gosi_seed import sync_gosi_rates

IBAN = "SA6080000247608010330101"


@pytest.fixture
def env(db):
    sync_gosi_rates()
    r = provision_account(slug="aud-test", display_name_ar="حساب",
                          company_name_ar="شركة", is_sandbox=True)
    with account_scope(r.account_id):
        acc = Account.objects.get(id=r.account_id)
        comp = Company.objects.get(id=r.company_id)
        comps = {c.code: c for c in PayComponent.objects.filter(company=comp)}
        st = PayrollSettings.objects.get(company=comp)
        st.eosb_wage_basis = "flagged"
        st.save()

        p, _ = create_person(
            account=acc, first_name_ar="سعد", family_name_ar="القحطاني",
            gender="male", nationality_code="SA", id_type="national_id",
            id_number="1099887766", mobile="0509887766", force=True)
        emp, _, _ = create_employment(
            person=p, company=comp, employee_no="201",
            join_date=date(2021, 1, 1), iban=IBAN,
            salary_lines=[(comps["BASIC"], D("9000"))])
        yield {"account_id": r.account_id, "acc": acc, "comp": comp,
               "emp": emp, "person": p, "comps": comps, "settings": st}


# ══════════ اللقطة والمقارنة ══════════

@pytest.mark.django_db(transaction=True)
def test_snapshot_skips_noise(env):
    """الحقول التقنية لا تُسجَّل — ضجيج بلا فائدة تدقيقية."""
    with account_scope(env["account_id"]):
        snap = snapshot(env["emp"])
        assert "id" not in snap
        assert "created_at" not in snap
        assert "employee_no" in snap


@pytest.mark.django_db(transaction=True)
def test_no_entry_when_nothing_changed(env):
    """لا يُسجَّل شيء إن لم يتغيّر شيء — فلا ضجيج."""
    with account_scope(env["account_id"]):
        before = snapshot(env["emp"])
        entry = log_change(instance=env["emp"], before=before,
                           actor=env["person"])
        assert entry is None


@pytest.mark.django_db(transaction=True)
def test_change_records_before_and_after(env):
    with account_scope(env["account_id"]):
        before = snapshot(env["emp"])
        env["emp"].is_gosi_registered = True
        env["emp"].save()
        entry = log_change(instance=env["emp"], before=before,
                           actor=env["person"], label="201")
        assert entry is not None
        assert "is_gosi_registered" in entry.changes
        assert entry.changes["is_gosi_registered"]["from"] is False
        assert entry.changes["is_gosi_registered"]["to"] is True


@pytest.mark.django_db(transaction=True)
def test_actor_name_stored_as_text(env):
    """الاسم يُحفظ نصًا فيبقى بعد حذف الشخص."""
    with account_scope(env["account_id"]):
        entry = log_create(instance=env["emp"], actor=env["person"])
        assert entry.actor_name == env["person"].display_name


@pytest.mark.django_db(transaction=True)
def test_system_actor_when_none(env):
    with account_scope(env["account_id"]):
        entry = log_create(instance=env["emp"], actor=None)
        assert entry.actor_name == "النظام"


@pytest.mark.django_db(transaction=True)
def test_delete_keeps_label_and_snapshot(env):
    """الحذف يحفظ الوصف واللقطة — يبقى مفهومًا بعد الاختفاء."""
    with account_scope(env["account_id"]):
        entry = log_delete(instance=env["emp"], actor=env["person"],
                           label="201 — سعد القحطاني")
        assert entry.action == AuditAction.DELETE
        assert "201" in entry.object_label
        assert entry.changes.get("employee_no") == "201"


# ══════════ العرض في مكان التعديل (ق-44) ══════════

@pytest.mark.django_db(transaction=True)
def test_history_scoped_to_object(env):
    """السجل يُعرض في شاشة السجل الذي يخصّه لا في مكان منفصل."""
    with account_scope(env["account_id"]):
        log_create(instance=env["emp"], actor=env["person"])
        log_action(instance=env["emp"], action=AuditAction.UPDATE,
                   actor=env["person"], summary="تعديل")

        other, _ = create_person(
            account=env["acc"], first_name_ar="آخر",
            family_name_ar="شخص", gender="male", nationality_code="SA",
            id_type="national_id", id_number="1055443322",
            mobile="0505443322", force=True)
        log_create(instance=other, actor=env["person"])

        assert len(history_for(env["emp"])) == 2
        assert len(history_for(other)) == 1


@pytest.mark.django_db(transaction=True)
def test_serialize_entry_readable(env):
    with account_scope(env["account_id"]):
        before = snapshot(env["emp"])
        env["emp"].include_in_wps = True
        env["emp"].save()
        entry = log_change(instance=env["emp"], before=before,
                           actor=env["person"])
        d = serialize_entry(entry,
                            field_labels={"include_in_wps": "حماية الأجور"})
        assert d["actor"] == env["person"].display_name
        assert d["changes"][0]["field_label"] == "حماية الأجور"


# ══════════ الربط بالعمليات الحقيقية ══════════

@pytest.mark.django_db(transaction=True)
def test_payroll_approval_logged(env):
    """اعتماد المسير يُسجَّل تلقائيًا."""
    with account_scope(env["account_id"]):
        run = create_run(company=env["comp"],
                         run_type=PayrollRunType.REGULAR,
                         year=2026, month=3)
        calculate_run(run)
        run.refresh_from_db()
        submit_run(run)
        run.refresh_from_db()
        approve_run(run, env["person"])
        run.refresh_from_db()

        entries = history_for(run)
        assert len(entries) == 1
        assert entries[0].action == AuditAction.APPROVE
        assert entries[0].actor_name == env["person"].display_name
        assert "اعتماد مسير" in entries[0].summary_ar


@pytest.mark.django_db(transaction=True)
def test_salary_structure_logged(env):
    """تعديل الراتب أخطر تغيير — يُسجَّل بقيمته."""
    with account_scope(env["account_id"]):
        structure = set_salary_structure(
            employment=env["emp"],
            lines=[(env["comps"]["BASIC"], D("12000"))],
            effective_from=date(2026, 6, 1),
            approved_by=env["person"])
        entries = history_for(structure)
        assert len(entries) == 1
        assert "12000" in entries[0].summary_ar
        assert entries[0].changes["lines"]["from"] == "9000.00"
        assert entries[0].changes["lines"]["to"] == "12000.00"


# ══════════ المتانة ══════════

@pytest.mark.django_db(transaction=True)
def test_logging_never_breaks_operation(env):
    """
    فشل التسجيل لا يوقف العملية — فقدان قيد أهون من فشل اعتماد.
    """
    with account_scope(env["account_id"]):
        # كائن بلا account_id يُفشل التسجيل
        class Broken:
            pk = 1
            account_id = 999999
            company_id = None

            def __str__(self):
                return "broken"

        entry = log_action(instance=Broken(), action=AuditAction.UPDATE,
                           actor=None, summary="اختبار")
        assert entry is None      # فشل بصمت لا برفع خطأ


@pytest.mark.django_db(transaction=True)
def test_object_type_mapping(env):
    with account_scope(env["account_id"]):
        assert object_type_of(env["emp"]) == "employment"
        assert object_type_of(env["person"]) == "person"


# ══════════ العزل ══════════

@pytest.mark.django_db(transaction=True)
def test_audit_isolated_between_accounts(env, rls_enforced_late):
    """شركة لا ترى سجل أخرى."""
    other = provision_account(slug="aud-other", display_name_ar="آخر",
                              company_name_ar="أخرى", is_sandbox=True)
    with account_scope(env["account_id"]):
        log_create(instance=env["emp"], actor=env["person"])

    rls_enforced_late()
    with account_scope(other.account_id):
        assert AuditEntry.objects.count() == 0
