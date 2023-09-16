from signoffs.signoffs import (
    IrrevokableSignoff,
    RevokableSignoff,
    SignoffRenderer,
    SignoffUrlsManager,
)

from .models.signets import ArticleSignet

publication_request_signoff = RevokableSignoff.register(
    id="article.publication_request_signoff",
    signetModel=ArticleSignet,
    label="Submit for Publication",
    urls=SignoffUrlsManager(
        revoke_url_name="article:revoke_publication_request",
    ),
    render=SignoffRenderer(
        form_context=dict(
            help_text="Publication Request",
            submit_label="Save",
        )
    ),
)


publication_approval_signoff = IrrevokableSignoff.register(
    id="article.publication_approval_signoff",
    signetModel=ArticleSignet,
    label="Publish Article",
    render=SignoffRenderer(
        form_context=dict(
            help_text="Publication Approval",
        )
    ),
)
