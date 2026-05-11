# Translation management models

These models are responsible for managing the translation of objects.

```mermaid
graph TD
A[TranslationSource] --> B[TranslatableObject]
C[Translation] --> A
D[TranslationLog] --> A
C --> E[wagtail.Locale]
A --> E
D --> E
A --> F[django.ContentType]
B --> F

style E stroke-dasharray: 5 5
style F stroke-dasharray: 5 5
```

::: wagtail_localize.models.TranslatableObject
    options:
      show_root_heading: true

::: wagtail_localize.models.TranslationSource
    options:
      show_root_heading: true

::: wagtail_localize.models.Translation
    options:
      show_root_heading: true

::: wagtail_localize.models.TranslationLog
    options:
      show_root_heading: true
