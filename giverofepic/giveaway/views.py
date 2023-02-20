from pprint import pprint

from django.utils import timezone
from django.views import generic

from giveaway.models import Link
from wallet.epic_sdk.utils import logger


class ClaimLinkView(generic.DetailView):
    model = Link
    template_name = 'website/home.html'
    slug_field = 'code'
    slug_url_kwarg = 'code'

    def get_object(self, queryset=None):
        code = self.kwargs.get("code")
        return self.model.validate(code=code)

    def get_context_data(self, **kwargs):
        context = super(ClaimLinkView, self).get_context_data(**kwargs)

        if self.object['error']:
            logger.warning(self.object['message'])
            return context

        link = self.object['result']
        context['link'] = link.__dict__
        context['now'] = timezone.now()

        if link.personal and link.address:
            logger.info(f"Personal link with address provided")
            logger.info(link.request_transaction())
            context['js_function'] = "sendTransaction()"

        if not link.personal:
            logger.info(f"In Blanco link ({link.event}) without specified receiver")

        pprint(context)
        return context
