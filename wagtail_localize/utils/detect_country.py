import functools
import re

from django.conf import settings
from django.contrib.gis.geoip2 import GeoIP2, GeoIP2Exception
from django.utils.module_loading import import_string
from django.utils.translation import parse_accept_lang_header


locale_re = re.compile(r'^([\w]{2})-([\w]{2})$')


def accept_language_header(request):
    accept = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    for accept_lang, unused in parse_accept_lang_header(accept):
        match = locale_re.match(accept_lang)

        if match:
            return match.group(2).upper()


def cf_ipcountry_header(request):
    if 'CF-IPCountry' in request.headers:
        return request.headers['CF-IPCountry'].upper()


def geoip2(request):
    try:
        geoip2 = GeoIP2()
    except GeoIP2Exception:
        # GeoIP not configured
        return

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')

    country = geoip2.country(ip)

    if country:
        return country['country_code'].upper()


@functools.lru_cache()
def get_country_detectors():
    detectors = getattr(settings, 'WAGTAILLOCALIZE_COUNTRY_DETECTORS', [
        'wagtail_localize.utils.detect_country.accept_language_header',
        'wagtail_localize.utils.detect_country.cf_ipcountry_header',
        'wagtail_localize.utils.detect_country.geoip2',
    ])

    return [
        import_string(detector)
        for detector in detectors
    ]


def detect_country(request):
    for detector in get_country_detectors():
        country_code = detector(request)
        if country_code is not None:
            return country_code
