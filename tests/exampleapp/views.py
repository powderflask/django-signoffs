from django.shortcuts import render
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse

from exampleapp.models import Content, ContentSignet, VancouverBikeRack

def index(request):
    return HttpResponse("Signoff example app")

@login_required
def content(request, content_id):
    # try to retrieve the signet for this user
    user = request.user

    # assume we have some content
    content = get_object_or_404(Content, id=content_id)

    # check if the item has been read
    try:
        sig = ContentSignet.objects.get(user = user,
                                        content = content,
                                        signoff_id = 'exampleapp.read_content')
        # display the content page
        return HttpResponse(f"Hello {request.user}, Displaying some user content")

    except ContentSignet.DoesNotExist:

        # we ask for signature
        return HttpResponse(f"Hello {request.user}, please sign before seeing the content<br/>" +
                            f"click here to sign: <a href='/sign/{content_id}'>sign</a>")


@login_required
def sign_content(request, content_id):
    # sign the request and redirect back to content
    user = request.user

    # retrieve the content
    content = Content.objects.get(id = content_id)

    # check if the item has been read
    sig, created = ContentSignet.objects.get_or_create(user = user,
                                                       content = content,
                                                       signoff_id = 'exampleapp.read_content')

    if created:
        return HttpResponse( f"Hello {request.user}, thank you for singing. <br>" +
                             f"Read the content at <a href='/content/{content_id}'>content</a>")
    else:
        return HttpResponse(f"Hello {request.user}, you already signed, nothing to do.")

@login_required
def bikeracks(request):
    # retrieve a list of bike racks
    racks = VancouverBikeRack.objects.all()

    def sign_rack(rack):
        if rack.signoff.is_signed():
            return rack.signoff.signet.user
        else:
            url = reverse('sign_bikerack', args=(rack.id, ))
            return f"<a href='{url}'>Need Signing</a>"

    output = [ '<tr>' +
               f'<td>{rack.street_number}</td>' +
               f'<td>{rack.street_name}</td>' +
               f'<td>{rack.street_side}</td>' +
               f'<td>{sign_rack(rack)}</td>' +
               '</tr>'
               for rack in racks ]

    return HttpResponse('<table>'+''.join(output) +'</table>')


@login_required
def sign_bikerack(request, rack_id):
    # signs a bikerack
    user = request.user

    rack = get_object_or_404(VancouverBikeRack, id = rack_id)
    url = reverse('bikeracks')
    if not rack.signoff.is_signed():
        rack.signoff.sign(user)
        return HttpResponse(f'rack id {rack_id} signed.  <a href="{url}">return to bikeracks</a>')
    else:
        return HttpResponse(f'rack {rack_id} already signed by {rack.signoff.signet.user}. <a href="{url}">return to bikeracks</a>')


from exampleapp.models import NewBikeRackApproval, NewBikeRackRequest
from signoffs.models import Stamp

@login_required
def request_new_bikerack(request):
    user = request.user

    # create a new bikerack request and sign under the current user
    approval = NewBikeRackApproval(
        street_name = 'sesame street',
        street_number = '123',
        street_side = ' ',
        skytrain_station = ' ',
        bia = ' ',
        num_racks = ' ',
        year_installed = ' ',
        rack_type = ' ',
        storage_capacity = ' ',
        status = ' ',
        street_located = ' '
    )

    # seems to require me to save first, not automatic
    approval.save()

    # this approval will require 2 signoffs, first signoff is the requester
    # obviously need lots of error checking in production system
    approval.next_signoffs()[0].sign(user)

    return HttpResponse(f'User {user.username} has requested a new bikerack: request id {approval.stamp.id}')

@login_required
def pending_bikerack_requests(request):
    user = request.user

    # Get a list of pending requests
    # seems like we need to go to the Stamp model, since there is no
    # way to get to the Stamp collection from Approval

    ''' old way
    qs = NewBikeRackRequest.objects.filter(approval_id='exampleapp.new_bikerack_approval', approved=False)
    details = '<br>'.join([str(s.id) + ' ' + s.street_name + ' ' + s.street_number for s in qs])
    '''

    details = '<br>'.join([
        str(approval.stamp.id) + ' ' + approval.stamp.street_name
        for approval in
        NewBikeRackApproval.get_stamp_queryset().filter(approved=False).approvals()
    ])

    return HttpResponse(f'Pending requests:<br> {details}')

@login_required
def approved_bikerack_requests(request):
    user = request.user

    # Get a list of approved requests
    # seems like we need to go to the Stamp model, since there is no
    # way to get to the Stamp collection from Approval

    ''' Old way
    qs = NewBikeRackRequest.objects.filter(approval_id='exampleapp.new_bikerack_approval', approved=True)
    details = '<br>'.join([str(s.id) + ' ' + s.street_name + ' ' + s.street_number + '  /signed by: ' +
                           str([sig.sigil for sig in s.approval.signoffs.all()]) for s in qs])
    '''

    details = '<br>'.join([
        str(approval.stamp.id) + ' ' + approval.stamp.street_name + '  /signed by: ' +
        str([sig.sigil for sig in approval.signoffs.all()])
        for approval in
        NewBikeRackApproval.get_stamp_queryset().filter(approved=True).approvals()
    ])

    return HttpResponse(f'Approved requests:<br> {details}')


@login_required
def sign_bikerack_requests(request, req_id):
    user = request.user

    # Get a list of pending requests
    bikerack_request = get_object_or_404(NewBikeRackRequest, id = req_id)

    # navigate back to the approval from stamp
    approval = bikerack_request.approval
    if approval.can_sign(user):
        approval.next_signoffs()[0].sign(user)
        approval.approve_if_ready()
        return HttpResponse(f'User {user.username} signed the request')
    else:
        return HttpResponse(f'User {user.username} cannot sign this request')


