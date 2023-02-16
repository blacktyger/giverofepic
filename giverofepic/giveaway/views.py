from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect

from django.views import generic

from giveaway.models import Link


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
        print(context)
        return context

