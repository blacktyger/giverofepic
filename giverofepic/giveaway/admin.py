from django.contrib import admin
from .models import *

from django.utils.html import format_html

@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):

    def image_tag(self, obj):
        if obj.qr_code:
            img_path = f"/static/img/qr_codes/{obj.code}.png"
            image = format_html(f'<img src="{img_path}" width="250px" height="250px" />')
        else:
            image = "-"

        return image

    image_tag.short_description = 'QR CODE IMAGE'

    search_fields = ['event', 'code', 'ready_url', 'transaction__tx_slate_id']
    readonly_fields = ['transaction', 'image_tag', 'ready_url', 'claim_date']
    fields = [f.name for f in Link._meta.fields if f.name not in
              ['timestamp', 'api_key', 'id']] + ['image_tag']
