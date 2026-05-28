"""Operational smoke tests — stdlib unittest only (Phase E4)."""

from __future__ import annotations

import os
import unittest

from operational_tests.harness import (
    SMOKE_ADMIN_PASSWORD,
    SMOKE_ADMIN_USERNAME,
    SMOKE_ANALYST_PASSWORD,
    SMOKE_ANALYST_USERNAME,
    configure_isolated_environment,
    create_test_application,
    extract_csrf,
    login_client,
    seed_analyst_operator,
    seed_review_officer_operator,
    SMOKE_REVIEW_OFFICER_PASSWORD,
    SMOKE_REVIEW_OFFICER_USERNAME,
)


class SmokeTestCase(unittest.TestCase):
    db_path: str
    app = None
    client = None
    application_id: int = 0

    @classmethod
    def setUpClass(cls):
        cls.db_path = configure_isolated_environment()
        from factory import initialize_application

        cls.app = initialize_application()
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.client = cls.app.test_client()

        from repositories.database import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor()
        cls.application_id = create_test_application(cursor)
        seed_analyst_operator(cursor)
        seed_review_officer_operator(cursor)
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        if cls.db_path and os.path.isfile(cls.db_path):
            try:
                os.remove(cls.db_path)
            except OSError:
                pass


class BootAndDiagnosticsTests(SmokeTestCase):
    def test_create_app_and_startup(self):
        from utils.startup import run_startup_integrity_checks

        status = run_startup_integrity_checks(log=False)
        self.assertTrue(status["ready"])
        self.assertTrue(status["tables_ok"])

    def test_integrity_checks_run(self):
        from repositories.database import get_db_connection
        from utils.integrity_checks import run_operational_integrity_checks

        conn = get_db_connection()
        cursor = conn.cursor()
        report = run_operational_integrity_checks(cursor, include_environment=False)
        conn.close()
        self.assertIn(report["overall"], ("ok", "warn"))
        self.assertGreater(report["counts"].get("ok", 0), 0)

    def test_diagnostics_report(self):
        from utils.diagnostics import build_operational_diagnostics, format_diagnostics_report

        report = build_operational_diagnostics(include_environment=False)
        text = format_diagnostics_report(report)
        self.assertIn("operational diagnostics", text)
        self.assertIn(report["overall"], ("ok", "warn", "fail"))

    def test_health_endpoints(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/health/ready").status_code, 200)


class AuthenticationTests(SmokeTestCase):
    def test_login_success_and_session(self):
        login_client(self.client, username=SMOKE_ADMIN_USERNAME, password=SMOKE_ADMIN_PASSWORD)
        response = self.client.get("/admin/overview")
        self.assertEqual(response.status_code, 200)

    def test_login_failure(self):
        response = self.client.get("/admin/login")
        csrf = extract_csrf(response.get_data(as_text=True))
        result = self.client.post(
            "/admin/login",
            data={"identity": SMOKE_ADMIN_USERNAME, "password": "wrong-password", "csrf_token": csrf},
        )
        self.assertEqual(result.status_code, 302)
        self.assertIn("/admin/login", result.headers.get("Location", ""))

    def test_logout(self):
        login_client(self.client, username=SMOKE_ADMIN_USERNAME, password=SMOKE_ADMIN_PASSWORD)
        overview = self.client.get("/admin/overview")
        csrf = extract_csrf(overview.get_data(as_text=True))
        self.client.post("/admin/logout", data={"csrf_token": csrf})
        redirected = self.client.get("/admin/overview")
        self.assertEqual(redirected.status_code, 302)


class RBACTests(SmokeTestCase):
    def test_analyst_denied_workflow_mutation(self):
        login_client(self.client, username=SMOKE_ANALYST_USERNAME, password=SMOKE_ANALYST_PASSWORD)
        detail = self.client.get(f"/admin/applications/{self.application_id}")
        csrf = extract_csrf(detail.get_data(as_text=True))
        result = self.client.post(
            f"/admin/applications/{self.application_id}/workflow",
            data={
                "csrf_token": csrf,
                "status": "Collection of documentation",
                "risk_level": "Low",
            },
        )
        self.assertEqual(result.status_code, 302)
        self.assertNotIn("workflow saved", result.get_data(as_text=True).lower())

    def test_analyst_can_view_analytics(self):
        login_client(self.client, username=SMOKE_ANALYST_USERNAME, password=SMOKE_ANALYST_PASSWORD)
        self.assertEqual(self.client.get("/admin/analytics").status_code, 200)

    def test_review_officer_can_update_applicant_profile(self):
        from repositories.applications import fetch_application

        login_client(
            self.client,
            username=SMOKE_REVIEW_OFFICER_USERNAME,
            password=SMOKE_REVIEW_OFFICER_PASSWORD,
        )
        detail = self.client.get(f"/admin/applications/{self.application_id}")
        csrf = extract_csrf(detail.get_data(as_text=True))
        response = self.client.post(
            f"/admin/applications/{self.application_id}/profile",
            data={
                "csrf_token": csrf,
                "owner_name": "Profile Updated Owner",
                "email": "profile.updated@test.local",
                "phone_number": "0712345678",
                "business_type": "Retail",
                "gender": "Other",
                "profile_context": "Smoke profile update",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        application = fetch_application(self.application_id)
        self.assertEqual(application["phone_number"], "0712345678")

    def test_analyst_denied_applicant_profile_mutation(self):
        login_client(self.client, username=SMOKE_ANALYST_USERNAME, password=SMOKE_ANALYST_PASSWORD)
        detail = self.client.get(f"/admin/applications/{self.application_id}")
        csrf = extract_csrf(detail.get_data(as_text=True))
        response = self.client.post(
            f"/admin/applications/{self.application_id}/profile",
            data={
                "csrf_token": csrf,
                "owner_name": "Should Fail",
                "email": "fail@test.local",
                "phone_number": "0712345678",
            },
        )
        self.assertIn(response.status_code, (302, 403))


class WorkflowTests(SmokeTestCase):
    def test_workflow_update_creates_audit(self):
        from repositories.database import get_db_connection

        login_client(self.client, username=SMOKE_ADMIN_USERNAME, password=SMOKE_ADMIN_PASSWORD)
        detail = self.client.get(f"/admin/applications/{self.application_id}")
        csrf = extract_csrf(detail.get_data(as_text=True))
        self.client.post(
            f"/admin/applications/{self.application_id}/workflow",
            data={
                "csrf_token": csrf,
                "status": "Collection of documentation",
                "risk_level": "Medium",
                "assigned_officer": "",
                "approval_notes": "Smoke workflow note",
            },
            follow_redirects=True,
        )

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM workflow_history WHERE application_id = ?",
            (self.application_id,),
        )
        count = cursor.fetchone()[0]
        cursor.execute(
            "SELECT status FROM applications WHERE id = ?",
            (self.application_id,),
        )
        status = cursor.fetchone()[0]
        conn.close()
        self.assertGreaterEqual(count, 1)
        self.assertEqual(status, "Collection of documentation")

    def test_invalid_status_rejected_by_validation(self):
        from services.workflow import validate_workflow_form
        from repositories.database import get_db_connection
        from repositories.applications import fetch_application

        app_row = fetch_application(self.application_id)
        workflow, error = validate_workflow_form({"status": "Not A Real Status"}, app_row)
        self.assertIsNone(workflow)
        self.assertIsNotNone(error)


class PublicApplicationPhoneTests(SmokeTestCase):
    def test_public_submission_persists_phone_number(self):
        from repositories.database import get_db_connection

        homepage = self.client.get("/")
        csrf = extract_csrf(homepage.get_data(as_text=True))
        response = self.client.post(
            "/apply",
            data={
                "csrf_token": csrf,
                "business_name": "Phone Smoke Business",
                "owner_name": "Phone Owner",
                "email": "phone.owner@test.local",
                "phone_number": "+254712345678",
                "revenue": "45000",
                "product": "Haraka Loan",
                "privacy_consent": "on",
            },
        )
        self.assertEqual(response.status_code, 302)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT phone_number FROM applications WHERE business_name = ? ORDER BY id DESC LIMIT 1",
            ("Phone Smoke Business",),
        )
        row = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["phone_number"], "+254712345678")

    def test_public_submission_requires_privacy_consent(self):
        from repositories.database import get_db_connection

        homepage = self.client.get("/")
        csrf = extract_csrf(homepage.get_data(as_text=True))
        response = self.client.post(
            "/apply",
            data={
                "csrf_token": csrf,
                "business_name": "No Consent Business",
                "owner_name": "No Consent Owner",
                "email": "noconsent@test.local",
                "phone_number": "+254712345679",
                "revenue": "12000",
                "product": "Haraka Loan",
            },
        )
        self.assertEqual(response.status_code, 302)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM applications WHERE business_name = ? ORDER BY id DESC LIMIT 1",
            ("No Consent Business",),
        )
        row = cursor.fetchone()
        conn.close()
        self.assertIsNone(row)


class UnderwritingTests(SmokeTestCase):
    def test_underwriting_save_and_history(self):
        from repositories.database import get_db_connection
        from repositories.applications import fetch_application
        from services.underwriting import persist_underwriting_update, underwriting_snapshot_from_form

        application = fetch_application(self.application_id)
        snapshot = underwriting_snapshot_from_form(
            {
                "underwriting_status": "in_review",
                "affordability_assessment": "satisfactory",
                "repayment_confidence": "satisfactory",
                "business_stability_review": "satisfactory",
                "documentation_quality_review": "satisfactory",
                "decision_summary": "Smoke review",
                "decision_reason": "Automated test",
            },
            "smoke_admin",
        )
        persist_underwriting_update(
            self.application_id,
            application,
            snapshot,
            "smoke_admin",
            context_notes="[governance:underwriting_escalation] smoke test",
        )

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM underwriting_decisions WHERE application_id = ?",
            (self.application_id,),
        )
        decisions = cursor.fetchone()[0]
        cursor.execute(
            "SELECT underwriting_status FROM applications WHERE id = ?",
            (self.application_id,),
        )
        status = cursor.fetchone()[0]
        conn.close()
        self.assertGreaterEqual(decisions, 1)
        self.assertEqual(status, "in_review")


class LoanServicingTests(SmokeTestCase):
    def test_loan_account_and_repayment(self):
        from repositories.applications import fetch_application
        from services.loans import (
            loan_snapshot_from_form,
            persist_loan_account_update,
            persist_repayment,
            validate_repayment_form,
        )

        application = fetch_application(self.application_id)
        snapshot = loan_snapshot_from_form(
            {
                "loan_lifecycle_status": "active",
                "loan_account_number": "SMOKE-001",
                "issued_amount": "10000",
                "outstanding_balance": "10000",
                "issue_date": "2026-01-01",
                "due_date": "2026-12-31",
                "installment_amount": "1000",
                "repayment_frequency": "monthly",
                "repayment_risk_level": "current",
            }
        )
        persist_loan_account_update(
            self.application_id,
            application,
            snapshot,
            "smoke_admin",
            context_notes="smoke loan activation",
        )

        application = fetch_application(self.application_id)
        repayment, err = validate_repayment_form(
            {"payment_date": "2026-02-01", "payment_amount": "1000"},
            application,
        )
        self.assertIsNone(err)
        balance_before = float(application["outstanding_balance"] or 0)
        result = persist_repayment(self.application_id, application, repayment, "smoke_admin")

        from repositories.database import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM repayments WHERE application_id = ?",
            (self.application_id,),
        )
        repay_count = cursor.fetchone()[0]
        conn.close()
        self.assertGreaterEqual(repay_count, 1)
        self.assertLess(result["balance_after"], balance_before)


class AnalyticsAndExportTests(SmokeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        login_client(cls.client, username=SMOKE_ADMIN_USERNAME, password=SMOKE_ADMIN_PASSWORD)

    def test_overview_analytics_reports(self):
        self.assertEqual(self.client.get("/admin/overview").status_code, 200)
        self.assertEqual(self.client.get("/admin/analytics").status_code, 200)
        self.assertEqual(self.client.get("/admin/reports").status_code, 200)
        self.assertEqual(self.client.get("/admin").status_code, 200)

    def test_export_applications_csv(self):
        response = self.client.get("/admin/export/applications")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)
        self.assertIn("attachment", response.headers.get("Content-Disposition", ""))


class CollectionsOperationsTests(SmokeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        login_client(cls.client, username=SMOKE_ADMIN_USERNAME, password=SMOKE_ADMIN_PASSWORD)
        from repositories.database import get_db_connection
        from services.loans import loan_snapshot_from_form, persist_loan_account_update
        from repositories.applications import fetch_application

        application = fetch_application(cls.application_id)
        snapshot = loan_snapshot_from_form(
            {
                "loan_lifecycle_status": "overdue",
                "loan_account_number": "SMOKE-COL-001",
                "issued_amount": "5000",
                "outstanding_balance": "4500",
                "issue_date": "2025-01-01",
                "due_date": "2025-06-01",
                "repayment_frequency": "monthly",
                "repayment_risk_level": "elevated",
            }
        )
        persist_loan_account_update(
            cls.application_id,
            application,
            snapshot,
            "smoke_admin",
            context_notes="smoke collections queue seed",
        )

    def test_collections_workspace_loads(self):
        login_client(self.client, username=SMOKE_ADMIN_USERNAME, password=SMOKE_ADMIN_PASSWORD)
        response = self.client.get("/admin/collections")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Intel. tier", response.data)

    def test_collections_recovery_export(self):
        response = self.client.get("/admin/export/collections/recovery-summary")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)

    def test_promise_create_and_workflow_audit(self):
        from repositories.applications import fetch_application
        from repositories.promises import fetch_active_promise
        from repositories.database import get_db_connection

        login_client(self.client, username=SMOKE_ADMIN_USERNAME, password=SMOKE_ADMIN_PASSWORD)
        detail = self.client.get(f"/admin/collections/{self.application_id}")
        csrf = extract_csrf(detail.get_data(as_text=True))
        response = self.client.post(
            f"/admin/collections/{self.application_id}/promises",
            data={
                "csrf_token": csrf,
                "promise_amount": "500",
                "promise_date": "2026-06-15",
                "commitment_notes": "Smoke test promise",
                "promise_context": "Smoke P3 commitment",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        conn = get_db_connection()
        cursor = conn.cursor()
        active = fetch_active_promise(cursor, self.application_id)
        cursor.execute(
            "SELECT COUNT(*) FROM workflow_history WHERE application_id = ? AND field_name LIKE 'promise_%'",
            (self.application_id,),
        )
        audit_count = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM recovery_promise_history WHERE application_id = ?",
            (self.application_id,),
        )
        history_count = cursor.fetchone()[0]
        conn.close()
        self.assertIsNotNone(active)
        self.assertEqual(float(active["promise_amount"]), 500.0)
        self.assertGreaterEqual(audit_count, 1)
        self.assertGreaterEqual(history_count, 1)

    def test_promise_active_export(self):
        response = self.client.get("/admin/export/promises/active")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)

    def test_collections_update_persists(self):
        from repositories.applications import fetch_application

        login_client(self.client, username=SMOKE_ADMIN_USERNAME, password=SMOKE_ADMIN_PASSWORD)
        detail = self.client.get(f"/admin/collections/{self.application_id}")
        self.assertEqual(detail.status_code, 200)
        csrf = extract_csrf(detail.get_data(as_text=True))
        response = self.client.post(
            f"/admin/collections/{self.application_id}/update",
            data={
                "csrf_token": csrf,
                "collections_status": "in_contact",
                "collections_priority": "high",
                "collections_assigned_to": "Smoke Officer",
                "collections_risk_level": "elevated",
                "collections_notes_summary": "Smoke test contact attempt",
                "collections_context": "Smoke collections governance context",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        application = fetch_application(self.application_id)
        self.assertEqual(application["collections_status"], "in_contact")
        self.assertEqual(application["collections_assigned_to"], "Smoke Officer")

        from repositories.database import get_db_connection
        from repositories.collections import fetch_collections_history_rows

        conn = get_db_connection()
        cursor = conn.cursor()
        history = fetch_collections_history_rows(cursor, self.application_id, limit=5)
        cursor.execute(
            "SELECT COUNT(*) FROM workflow_history WHERE application_id = ? AND field_name LIKE 'collections_%'",
            (self.application_id,),
        )
        audit_count = cursor.fetchone()[0]
        conn.close()
        self.assertGreaterEqual(len(history), 1)
        self.assertGreaterEqual(audit_count, 1)

    def test_analyst_cannot_mutate_collections(self):
        login_client(self.client, username=SMOKE_ANALYST_USERNAME, password=SMOKE_ANALYST_PASSWORD)
        detail = self.client.get(f"/admin/collections/{self.application_id}")
        csrf = extract_csrf(detail.get_data(as_text=True))
        response = self.client.post(
            f"/admin/collections/{self.application_id}/update",
            data={
                "csrf_token": csrf,
                "collections_status": "legal_escalation",
                "collections_priority": "urgent",
                "collections_risk_level": "legal",
                "collections_context": "should be denied",
            },
        )
        self.assertIn(response.status_code, (302, 403))


class NotificationOperationsTests(SmokeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        login_client(cls.client, username=SMOKE_ADMIN_USERNAME, password=SMOKE_ADMIN_PASSWORD)

    def test_01_notifications_center_loads(self):
        response = self.client.get("/admin/notifications")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Operational Notifications", response.data)

    def test_02_workflow_emits_operational_event(self):
        from repositories.applications import fetch_application
        from repositories.database import get_db_connection
        from services.workflow import validate_workflow_form
        from services.audit import persist_workflow_update, workflow_snapshot_from_row

        login_client(self.client, username=SMOKE_ADMIN_USERNAME, password=SMOKE_ADMIN_PASSWORD)
        application = fetch_application(self.application_id)
        workflow, _ = validate_workflow_form(
            {
                "status": application["status"],
                "sub_status": application["sub_status"] or "",
                "risk_level": "High",
                "assigned_officer": application["assigned_officer"] or "",
                "approval_notes": application["approval_notes"] or "",
                "flagged_fraud": "0",
            },
            application,
        )
        before = workflow_snapshot_from_row(application)
        if before["risk_level"] == "High":
            workflow["risk_level"] = "Critical"
        else:
            workflow["risk_level"] = "High"
        persist_workflow_update(
            self.application_id,
            application,
            workflow,
            "smoke_admin",
            context_notes="smoke G1 event test",
        )
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM operational_events WHERE application_id = ?",
            (self.application_id,),
        )
        events = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM operator_notifications WHERE application_id = ?",
            (self.application_id,),
        )
        notifications = cursor.fetchone()[0]
        conn.close()
        self.assertGreaterEqual(events, 1)
        self.assertGreaterEqual(notifications, 1)

    def test_03_notification_acknowledge(self):
        from repositories.database import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id FROM operator_notifications
            WHERE is_acknowledged = 0
            ORDER BY id DESC LIMIT 1
            """
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            self.skipTest("No unacknowledged notifications to test")
        notification_id = row[0]

        page = self.client.get("/admin/notifications")
        csrf = extract_csrf(page.get_data(as_text=True))
        response = self.client.post(
            f"/admin/notifications/{notification_id}/acknowledge",
            data={"csrf_token": csrf},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT is_acknowledged FROM operator_notifications WHERE id = ?",
            (notification_id,),
        )
        ack = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(ack, 1)

    def test_04_notifications_unresolved_export(self):
        response = self.client.get("/admin/export/notifications/unresolved")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.content_type)


def load_suite():
    loader = unittest.TestLoader()
    import operational_tests.smoke_tests as module

    return loader.loadTestsFromModule(module)


def run_smoke_tests(verbosity: int = 2) -> bool:
    suite = load_suite()
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys

    ok = run_smoke_tests()
    sys.exit(0 if ok else 1)
