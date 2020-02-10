# Routing

In this section we will configure Django and Wagtail Localize to serve the whole site on a language prefix. For example, your homepage will be served from `https://www.example.com/en-us/`. We will also configure browser language detection using Django’s `LocaleMiddleware`.

## `i18n_patterns` (Django)

This adds a language prefix to all URLs. We need to add the Wagtail URLs and the search view into this.


## `LocaleMiddleware` (Django)

This middleware will detect the browser’s language. This language is used to redirect the user to their language section when they are not in one, so `https://www.example.com/about/` will redirect to `https://www.example.com/en-us/about/` for users with a browser language set to US english.

Note that users can still manually set the URL to a different language and this won’t redirect them. Only URLs without a language will be redirected.


## `TranslatablePageRoutingMixin` (Wagtail Localize)

This mixin gets applied to the `HomePage` and routes the request through the relevant homepage for the current language.




At the end of this section, the user should be able to see content in multiple languages on the frontend.
