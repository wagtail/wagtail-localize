# Overridable segments models

These models are responsible for storing details about overridable segments in a translation source and storing the overridden data as well.

Overriding segments within an object allows non-text data to be modified for each locale.

```mermaid
graph TD


A[OverridableSegment] --> C[TranslationSource]
A[OverridableSegment] --> D[TranslationContext]
B[SegmentOverride] --> D
B[SegmentOverride] --> E[wagtail.Locale]

style C stroke-dasharray: 5 5
style D stroke-dasharray: 5 5
style E stroke-dasharray: 5 5
```

::: wagtail_localize.models
    selection:
        members:
            - SegmentOverride
            - OverridableSegment
        filters:
            - "!^save$"
