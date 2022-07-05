"""
Some concrete signoff models for the test app
    Demonstrates how to define custom signoffs and approvals using the contrib.approvals models as a basis.
"""
from django.db import models
from django_fsm import FSMField, transition

from signoffs.models import (
    AbstractSignet, AbstractRevokedSignet, Signet,
    SignoffOneToOneField, SignoffSet,
    Stamp,
    ApprovalField,
    AbstractFsmApprovalProcess,
)
from signoffs.approvals import ApprovalSignoff, SimpleApproval
from signoffs.approvals import signing_order as so
from signoffs.signoffs import SignoffRenderer
from signoffs.registry import register

Signet = Signet  # pass-through


# Models for Signoff tests


class Report(models.Model):
    """ A model with a related set of signoffs """
    contents = models.TextField()

    signoffs = SignoffSet('testapp.report_signoff')


class ReportSignet(AbstractSignet):
    """ Persistence layer for Report Signoffs """
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='signatories')


class RevokeReportSignet(AbstractRevokedSignet):
    """ Persistence layer for tracking revoked signoffs """
    signet = models.OneToOneField(ReportSignet, on_delete=models.CASCADE, related_name='revoked')


class Vacation(models.Model):
    """ A model with both a single Signoff Field and a  set of relatetd signoffs """
    employee = models.CharField(max_length=128)

    employee_signoff = SignoffOneToOneField(Signet, on_delete=models.SET_NULL,
                                            signoff_type='testapp.agree',
                                            null=True, related_name='+')
    signoffset = SignoffSet('testapp.hr_signoff')


class VacationSignet(AbstractSignet):
    """ Persistence layer for Vacation Signoffs """
    vacation = models.ForeignKey(Vacation, on_delete=models.CASCADE, related_name='signatories')


# Models for Approval tests


@register(id='testapp.leave_approval')
class LeaveApproval(SimpleApproval):
    """ An approval representing a Leave of Absence approval process with a defined SigningOrder """
    stampModel = Stamp
    label = 'Approve Leave of Absence Request'

    employee_signoff_type = ApprovalSignoff.register(id='testapp.leave_approval.employee_signoff',
                                                     label='Apply for Leave',
                                                     render=SignoffRenderer(form_context=dict(
                                                         help_text='Employee leave application signoff')
                                                     ))
    hr_signoff_type = ApprovalSignoff.register(id='testapp.leave_approval.hr_signoff',
                                               label='Request Approved by HR',
                                               render=SignoffRenderer(form_context=dict(
                                                   help_text='HR leave application approval')
                                               ))
    mngmt_signoff_type = ApprovalSignoff.register(id='testapp.leave_approval.mngmt_signoff',
                                                  label='Approve Leave',
                                                  render=SignoffRenderer(form_context=dict(
                                                      help_text='Final leave application approval')
                                                  ))

    signing_order = so.SigningOrder(
        employee_signoff_type,
        so.AtLeastN(hr_signoff_type, n=1),
        mngmt_signoff_type
    )


class LeaveRequest(models.Model):
    """ A model defining valid set of relations to demonstrate / test ApprovalField """
    # a One-to-One "forward" approval relation (managed by the Approval business logic) (see approval tests)
    approval = ApprovalField(LeaveApproval)


# Models for FSM Approval Process tests


class Building(models.Model):
    """ A model representing a building or construction site """
    name = models.CharField(max_length=64)
    # ... property_id, address, etc.


# TODO: add permissions to each signoff and to test fixture users

# A suite of signoffs defined to represent the different types of signatures in a Building Permit approval process.
S = ApprovalSignoff
applicant_signoff = S.register('testapp.construction_permit.signoff.applicant',
                               label='Apply for Permit',
                               render=SignoffRenderer(form_context=dict(
                                   help_text='Building permit application - applicant signoff')
                               ))
planning_signoff = S.register('testapp.construction_permit.signoff.planning',
                              label='Application Meets By-lawas',
                              render=SignoffRenderer(form_context=dict(
                                  help_text='Building permit application - planning signoff')
                              ))
permit_approval = S.register('testapp.construction_permit.signoff.permit',
                             label='Approve Building Permit'
                             )
electrical_signoff = S.register('testapp.construction_permit.signoff.electrical',
                                label='Application / Installation Meets Electrical Code'
                                )
plumbing_signoff = S.register('testapp.construction_permit.signoff.plumbing',
                              label='Application / Installation Meets Plumbing Code'
                              )
inspection_approval = S.register('testapp.construction_permit.signoff.inspection',
                                 label='Construction Inspected',
                                 render=SignoffRenderer(form_context=dict(
                                     help_text='Construction Inspection - construction meets applicable standards')
                                 ))


class AbstractBuildingPermitApproval(SimpleApproval):
    """ Abstract base class for Building Permit Approvals defining the business logic for signing the approval """

    def sign_approval(self, user, last=False):
        """ Sign the first or last of the next available signoffs for given user """
        next = self.next_signoffs(for_user=user)
        if next and not self.is_approved() and not self.has_signed(user):
            index = -1 if last else 0
            next[index].sign(user)
            self.approve_if_ready()


@register(id='testapp.building_permit.permit_application')
class BuildingPermitApplication(AbstractBuildingPermitApproval):
    """ Building Permit Application Approval Type """

    signing_order = so.SigningOrder(
        applicant_signoff
    )


@register(id='testapp.building_permit.permit_approval')
class BuildingPermitApproval(AbstractBuildingPermitApproval):
    """ Building Permit Application Approval Type """

    signing_order = so.SigningOrder(
        planning_signoff,
        electrical_signoff,
        permit_approval
    )


@register(id='testapp.building_permit.interim_inspection_approval')
class InterimInspectionApproval(AbstractBuildingPermitApproval):
    """ Building Permit Interim Inspection Approval Type """

    signing_order = so.SigningOrder(
        so.InParallel(
            so.OneOrMore(electrical_signoff),
            so.OneOrMore(plumbing_signoff),
        ),
        inspection_approval,
    )


@register(id='testapp.building_permit.final_inspection_approval')
class FinalInspectionApproval(AbstractBuildingPermitApproval):
    """ Building Permit Final Inspection Approval Type """

    signing_order = so.SigningOrder(
        so.InParallel(
            so.Optional(electrical_signoff),
            so.Optional(plumbing_signoff),
        ),
        inspection_approval,
    )


class ConstructionPermittingProcess(AbstractFsmApprovalProcess):
    """ Defines a 5-stage Approval Process for applying, permitting, and inspecting building permits """
    class States(models.TextChoices):
        INITIATED = 'Initiated'
        APPLIED = 'Applied'
        PERMITTED = 'Permitted'
        INSPECTED = 'Inspected'
        APPROVED = 'Approved'

    # Model state + relation to the building permit is for
    state = FSMField(choices=States.choices, default=States.INITIATED)
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='permits')

    # Four OnetoOne fields defining the approvals needed in the process
    apply = ApprovalField(BuildingPermitApplication)
    permit = ApprovalField(BuildingPermitApproval)
    interim_inspection = ApprovalField(InterimInspectionApproval)
    final_inspection = ApprovalField(FinalInspectionApproval)

    # Approval / FSM transitions defining state transitions and their side effects.

    @apply.callback.on_approval
    @transition(field=state, source=States.INITIATED, target=States.APPLIED)
    def applied(self, approval):
        print("Applied", self.state, approval)

    @permit.callback.on_approval
    @transition(field=state, source=States.APPLIED, target=States.PERMITTED)
    def permitted(self, approval):
        print("Permitted", self.state, approval)

    @interim_inspection.callback.on_approval
    @transition(field=state, source=States.PERMITTED, target=States.INSPECTED)
    def inspected(self, approval):
        print("Interim Inspected", self.state, approval)

    @final_inspection.callback.on_approval
    @transition(field=state, source=States.INSPECTED, target=States.APPROVED)
    def authorized(self, approval):
        print("Final Inspection Approved", self.state, approval)
