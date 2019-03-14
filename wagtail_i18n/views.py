
from django.http import Http404, HttpResponse
from django.utils import translation

from wagtail.core import hooks
from wagtail.core.models import Page

from .models import Language, Translatable


def serve(request, path):
    # we need a valid Site object corresponding to this request (set in wagtail.core.middleware.SiteMiddleware)
    # in order to proceed
    if not request.site:
        raise Http404

    path_components = [component for component in path.split('/') if component]
    site_root = request.site.root_page.specific

    # If the site root is translatable, reroute based on language
    if isinstance(site_root, Translatable):
        language_code = translation.get_supported_language_variant(request.LANGUAGE_CODE)

        try:
            language = Language.objects.get(code=language_code)
            site_root = site_root.get_translation(language)
        except Language.DoesNotExist:
            pass
        except Page.DoesNotExist:
            pass

    page, args, kwargs = site_root.route(request, path_components)

    for fn in hooks.get_hooks('before_serve_page'):
        result = fn(page, request, args, kwargs)
        if isinstance(result, HttpResponse):
            return result

    return page.serve(request, *args, **kwargs)
