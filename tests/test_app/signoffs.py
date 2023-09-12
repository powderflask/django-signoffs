"""
    Register some signoffs for testing with
    Will be auto-discovered without need to import this module.
"""
from signoffs.signoffs import BaseSignoff, RevokableSignoff, SignoffLogic, SimpleSignoff


class TestSignoff(BaseSignoff):
    signetModel = "signoffs_signets.Signet"
    label = "This is agreeable"


agree_signoff = SimpleSignoff.register(id="test_app.agree")
consent_signoff = RevokableSignoff.register(
    id="test_app.consent",
    logic=SignoffLogic(perm="auth.can_sign", revoke_perm="auth.can_revoke"),
)

accept_signoff = SimpleSignoff.register(
    id="test_app.accept",
    signetModel="test_app.ReportSignet",
    label="I Accept",
    logic=SignoffLogic(perm="auth.can_accept"),
)

report_signoff = RevokableSignoff.register(
    id="test_app.report_signoff",
    signetModel="test_app.ReportSignet",
    revokeModel="test_app.RevokeReportSignet",
    label="Reviewed",
    logic=SignoffLogic(perm="auth.can_review"),
)

hr_signoff = BaseSignoff.register(
    id="test_app.hr_signoff",
    signetModel="test_app.VacationSignet",
    label="Vacation Approved",
    logic=SignoffLogic(perm="auth.can_approve_hr"),
)

mngr_signoff = BaseSignoff.register(
    id="test_app.mngr_signoff",
    signetModel="test_app.VacationSignet",
    label="Vacation Approved",
    logic=SignoffLogic(perm="auth.can_approve_mngr"),
)
