from django import forms

from wagtail_i18n.models import get_translatable_models, Locale


class CreateTranslationRequestForm(forms.Form):
    locales = forms.ModelMultipleChoiceField(queryset=Locale.objects.none(), widget=forms.CheckboxSelectMultiple)
    include_subtree = forms.BooleanField(required=False)

    def __init__(self, page, *args, **kwargs):
        super().__init__(*args, **kwargs)

        page_descendant_count = page.get_descendants().type(tuple(get_translatable_models())).count()
        if page_descendant_count > 0:
            self.fields['include_subtree'].help_text = f"This will add {page_descendant_count} additional pages to the request"
        else:
            self.fields['include_subtree'].widget = forms.HiddenInput()

        self.fields['locales'].queryset = Locale.objects.filter(is_active=True).exclude(id=page.locale_id)
