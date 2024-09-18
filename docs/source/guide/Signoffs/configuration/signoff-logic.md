# Permissions
Specify the required permissions for signing and revoking a signoff. To disable revokability, set `revoke_perm=False` 
in `SignoffLogic`.

## Add Signing and/or Revoking Permissions
```python
from signoffs.signoffs import SignoffLogic

# Define custom logic with specific permissions
custom_logic = SignoffLogic(perm='a_model.a_perm', revoke_perm='a_model.another_perm')

# Register the signoff with the custom logic
my_signoff = SignoffClass.register(id='my_app.my_signoff', logic=custom_logic)
```