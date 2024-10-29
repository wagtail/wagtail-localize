# Snippets and Synchronization
Imagine you have a page with related tags added via snippets, and you want to query all pages with a specific tag.

When synchronous translation is enabled, the tag will refer to the default language. However, if the user turns off
synchronous translation, the tag will refer to the page’s language. This could mean the user references a translated tag
within the translated page, causing the query to miss some pages tagged with the original tag.

To solve this, you can query both the default language and the current language, then filter based on the active
language.

```python
def get_something(request, tag):
  lang = request.LANGUAGE_CODE
  default_tag = tag.get_translation(tag.get_default_locale())
  pages = SomePage.objects.live().filter(
    Q(locale__language_code=lang),
    Q(tags=default_tag) | Q(tags=tag)
  ).distinct()
```
