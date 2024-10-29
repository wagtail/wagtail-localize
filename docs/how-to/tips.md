# Snippets and Synchronization

Imagine you have a page with related tags added via snippets, and you want to query all pages with a specific tag.

When synchronous translation is enabled, the tag will refer to the default language. However, if the user turns off
synchronous translation, the tag will refer to the page’s language. This could mean the user references a translated tag
within the translated page, causing the query to miss some pages tagged with the original tag.

To solve this, you can query both the default language and the current language, then filter based on the active
language.

```python
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from wagtail.snippets.models import register_snippet
from wagtail.models import TranslatableMixin, Page


@register_snippet
class Tag(TranslatableMixin, models.Model):
    tag = models.CharField(_("Tag"), max_length=255)

    def __str__(self):
        return self.tag

class BlogPage(Page):
    my_tag = models.ForeignKey(
        "snippets.Tag",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        if self.my_tag:
            default_tag = self.my_tag.get_translation(self.my_tag.get_default_locale())
            context['pages'] = BlogPage.objects.live().filter(Q(locale=self.locale), Q(my_tag=default_tag) | Q(my_tag=self.my_tag)).distinct()
            return context
```
