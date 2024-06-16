# Translatable ModelAdmin

Wagtail Localize supports translation of custom Wagtail's [ModelAdmin](https://docs.wagtail.org/en/stable/reference/contrib/modeladmin/index.html) registered models.

## Installation

Add `wagtail_localize.modeladmin` to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "wagtail_localize.modeladmin",
]
```

## How to use

When registering your custom models you can use the supplied `TranslatableModelAdmin` in place of Wagtail's `ModelAdmin` class.

```python
from wagtail_localize.modeladmin.options import TranslatableModelAdmin
from wagtail_modeladmin.options import modeladmin_register

from .models import MyTranslatableModel


class MyTranslatableModelAdmin(TranslatableModelAdmin):
    model = MyTranslatableModel


modeladmin_register(MyTranslatableModelAdmin)
```

That's it! You can translate your custom ModelAdmin models in the admin dashboard the same way you would Wagtail snippets.
