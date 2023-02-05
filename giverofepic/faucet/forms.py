from captcha import fields, widgets
from django import forms

class ReceiveForm(forms.Form):
    captcha = fields.ReCaptchaField(
        widget=widgets.ReCaptchaV3(attrs={'required_score': 0.85}))