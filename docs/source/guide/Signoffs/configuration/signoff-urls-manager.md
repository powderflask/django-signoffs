# Save/Revoke Endpoints
When a signoff form is signed, a POST request is sent to the save_url if it is defined; otherwise, it is sent to the 
current URL. Similarly, when a signoff is revoked, a GET request is sent to the revoke_url if it exists; otherwise, 
it defaults to the current URL.

Define a save and/or revoke url endpoint:
```{code-block} python
from signoffs.signoffs import SignoffUrlsManager

signoff_urls = SignoffUrlsManager(save_url_name='my_save_url',
                                  revoke_url_name='my_revoke_url',
                                  )
							
my_signoff = SignoffClass.register(id='my_app.my_signoff',
                                   urls=my_urls,
                                   )
```

This allows you to specify custom endpoints for saving and revoking signoffs, providing flexibility in handling these 
actions within your application.