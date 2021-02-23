# Settings models

These models are responsible for storing settings that are configured by a user.

```mermaid
graph TD


A[LocaleSynchronization] --> B[wagtail.Locale]

style B stroke-dasharray: 5 5
```

::: wagtail_localize.models
    selection:
        members:
            - LocaleSynchronization
        filters:
            - "!^save$"
