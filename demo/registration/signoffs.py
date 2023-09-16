from signoffs.signoffs import IrrevokableSignoff, RevokableSignoff, SignoffUrlsManager

terms_signoff = IrrevokableSignoff.register(id="terms_signoff")
"""ToS signoff"""

newsletter_signoff = RevokableSignoff.register(
    id="newsletter_signoff",
    urls=SignoffUrlsManager(revoke_url_name="revoke_newsletter"),
)
"""Newsletter consent"""
