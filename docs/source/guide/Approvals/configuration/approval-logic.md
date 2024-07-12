# Permissions
Specify the required permissions for revoking. To disable revokability, pass `revoke_perm=False` to the approval in the register method, or defined as a property in the class definition. 
#fixme *either link to appropriate section or....*

## Add Approving and/or Revoking Permissions
```{code-block} python
from signoffs.approvals import ApprovalLogic, SimpleApproval
from signoffs.registry import register

# This approval can be revoked by a user with the specified permission
@register("MyApproval")
class MyApproval(SimpleApproval):
    logic = ApprovalLogic(revoke_perm='a_model.another_perm')
    ...
    
# Alternatively, we can create an approval that isn't able to be revoked (via the api)
@register("MyIrrevokableApproval")
class MyIrrevokableApproval(SimpleApproval):
    logic = ApprovalLogic(revoke_perm=False)
    ...
```
```{TIP}
Since an approval is considered approved when the signing order is complete, there is no parameter to specify a permission
to approve. Instead, specify signing permissions in the signoffs directly.
See [Signoff Permissions](../../Signoffs/configuration/signoff-logic.md) for more info.
```