# Revoke Endpoints
When an approval is completed (approved), it can be revoked by a user with the right permissions (if one exists),
in which case, a GET request will be sent to the specified revoke url which is where the revocation will need to be processed.

Specify the desired revoke url by overwriting the `urls` parameter of an approval class as shown.

```{code-block} python
from signoffs.approvals import ApprovalUrlsManager

@register("MyApproval")
class MyApproval(SimpleApproval):
    urls = ApprovalUrlsManager(revoke_url_name='my_revoke_url')
    ...
```