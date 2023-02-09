from django.shortcuts import render

from django.views import generic

from giveaway.models import Link


class ClaimLinkView(generic.DetailView):
    model = Link
    template_name = 'website/home.html'

    def get_context_data(self, **kwargs):
        context = super(ClaimLinkView, self).get_context_data(**kwargs)
        return context
