from django.db import models

from signoffs.models import (
    SignoffSet, SignoffSingle, SignoffField,
    SignoffOneToOneField, Signet,
    AbstractSignet,
    Stamp,
    ApprovalField,
)

# basic signoff
from signoffs.signoffs import SimpleSignoff

# for approvals
from signoffs.approvals import ApprovalSignoff, SimpleApproval
from signoffs.approvals import signing_order as so
from signoffs.registry import register

# Create your models here.

# first need to register the signoffs
from signoffs.signoffs import SimpleSignoff, RevokableSignoff

# content must be signed before a user can read it
content_signoff = SimpleSignoff.register('exampleapp.read_content')
bikerack_signoff = SimpleSignoff.register('exampleapp.bikerack_signoff')


class Content(models.Model):    
    # some content for user to read
    contents = models.TextField()

    # field to indicate user has read it

    # why this not work?
    #signoff = SignoffField('exampleapp.read_content')
    # must use the object content_signoff instead of the key 'exampleapp.read_content'
    #signoff = SignoffField(content_signoff)

    # The following ended up with a field name mismatch
    #
    #signoffs = SignoffOneToOneField(Signet, on_delete=models.SET_NULL,
    #                                        signoff_type='exampleapp.read_content',
    #                                        null=True, related_name='+')

    # no fields have been created
    # signoffs = SignoffSingle('exampleapp.read_content')
    signoffs = SignoffSet('exampleapp.read_content')

class ContentSignet(AbstractSignet):
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name='reader')


# Simulates bike rack locations that needed to be checked off by any user
class VancouverBikeRack(models.Model):
    street_number = models.CharField(max_length=200)
    street_name = models.CharField(max_length=200)
    street_side = models.CharField(max_length=200)
    skytrain_station = models.CharField(max_length=200)
    bia = models.CharField(max_length=200)
    num_racks = models.CharField(max_length=200)
    year_installed = models.CharField(max_length=200)
    rack_type = models.CharField(max_length=200)
    storage_capacity = models.CharField(max_length=200)
    status = models.CharField(max_length=200)
    street_located = models.CharField(max_length=200)

    # one to one signoff - just need somebody to sign it
    signoff = SignoffField(bikerack_signoff)
    
    def __str__(self):        
        
        return ''.join( ['<tr>',
                         f'<td>{self.street_number}</td>',
                         f'<td>{self.street_name}</td>',
                         f'<td>{self.street_side}</td>',
                         f'<td>{self.signoff.signet.user if self.signoff.is_signed() else "Need Signing"}</td>',
                         '</tr>'] )

class NewBikeRackRequest(Stamp):
    street_number = models.CharField(max_length=200)
    street_name = models.CharField(max_length=200)
    street_side = models.CharField(max_length=200)
    skytrain_station = models.CharField(max_length=200)
    bia = models.CharField(max_length=200)
    num_racks = models.CharField(max_length=200)
    year_installed = models.CharField(max_length=200)
    rack_type = models.CharField(max_length=200)
    storage_capacity = models.CharField(max_length=200)
    status = models.CharField(max_length=200)
    street_located = models.CharField(max_length=200)

    
@register(id='exampleapp.new_bikerack_approval')
class NewBikeRackApproval(SimpleApproval):
    # Must provide a stampModel - this is where saving of stamp happens
    # Here we are using the abstract one
    stampModel = NewBikeRackRequest
    
    label = 'approval for new bikerack'

    requester_signoff_type = ApprovalSignoff.register(id='testapp.new_bikerack_approval.requester_signoff',
                                                     label='Request for new bikerack')

    manager_signoff_type = ApprovalSignoff.register(id='testapp.new_bikerack_approval.manager_signoff',
                                                     label='Approve new bikerack')

    signing_order = so.SigningOrder(
        requester_signoff_type,
        manager_signoff_type
    )
