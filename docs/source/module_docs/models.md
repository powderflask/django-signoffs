# signoffs.models

[//]: # (Collects documentation for all signoffs imports in signoffs.models)

```{eval-rst}
.. automodule:: signoffs.core.models
    :members: AbstractSignet, AbstractRevokedSignet,
    AbstractApprovalSignet, AbstractApprovalStamp
    :noindex:

.. automodule:: signoffs.core.models.fields
    :members: SignoffField, SignoffSet, SignoffSingle,
    ApprovalSignoffSet, ApprovalSignoffSingle,
    RelatedSignoffDescriptor as RelatedSignoff
    ApprovalField,
    RelatedApprovalDescriptor as RelatedApproval
    :noindex:
    
.. automodule:: signoffs.contrib.signets.models
    :members: Signet, RevokedSignet
    :noindex:
    
.. automodule:: signoffs.contrib.approvals.models
    :members: Signet as ApprovalSignet,
    RevokedSignet as RevokedApprovalSignet,
    Stamp
    :noindex:
```