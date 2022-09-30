"""
    Register some signoffs for testing with
    Will be auto-discovered without need to import this module.
"""
from signoffs.signoffs import BaseSignoff, SimpleSignoff, RevokableSignoff, SignoffLogic


class TestSignoff(BaseSignoff):
    signetModel = 'signoffs.Signet'
    label = 'This is agreeable'


agree_signoff = SimpleSignoff.register(id='testapp.agree')
consent_signoff = RevokableSignoff.register(id='testapp.consent',
                                            logic=SignoffLogic(perm='auth.can_sign', revoke_perm='auth.can_revoke'))

accept_signoff = SimpleSignoff.register(id='testapp.accept',
                                        signetModel='testapp.ReportSignet',
                                        label='I Accept', logic=SignoffLogic(perm='auth.can_accept'))

report_signoff = RevokableSignoff.register(id='testapp.report_signoff',
                                           signetModel='testapp.ReportSignet',
                                           revokeModel='testapp.RevokeReportSignet',
                                           label='Reviewed', logic=SignoffLogic(perm='auth.can_review'))

hr_signoff = BaseSignoff.register(id='testapp.hr_signoff',
                                  signetModel='testapp.VacationSignet',
                                  label='Vacation Approved', logic=SignoffLogic(perm='auth.can_approve_hr'))

mngr_signoff = BaseSignoff.register(id='testapp.mngr_signoff',
                                    signetModel='testapp.VacationSignet',
                                    label='Vacation Approved', logic=SignoffLogic(perm='auth.can_approve_mngr'))
