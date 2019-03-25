from django import forms
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from wagtail.admin.widgets import AdminPageChooser

from wagtail_i18n.models import Region


class RegionForm(forms.ModelForm):
    required_css_class = 'required'

    class Meta:
        model = Region
        fields = ['name', 'slug', 'languages']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['languages'].queryset = self.fields['languages'].queryset.filter(is_active=True)
