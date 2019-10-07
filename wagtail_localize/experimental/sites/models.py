from django.core.cache import cache
from django.db import models
from django.db.models import Case, Q, When
from django.utils.translation import ugettext_lazy as _

from wagtail_localize.models import Language, Region


MATCH_HOSTNAME_PORT = 0
MATCH_HOSTNAME_DEFAULT = 1
MATCH_DEFAULT = 2
MATCH_HOSTNAME = 3


class SiteManager(models.Manager):
    def get_by_natural_key(self, hostname, port):
        return self.get(hostname=hostname, port=port)


class Site(models.Model):
    hostname = models.CharField(
        verbose_name=_("hostname"), max_length=255, db_index=True
    )
    port = models.IntegerField(
        verbose_name=_("port"),
        default=80,
        help_text=_(
            "Set this to something other than 80 if you need a specific port number to appear in URLs"
            " (e.g. development on port 8000). Does not affect request handling (so port forwarding still works)."
        ),
    )
    site_name = models.CharField(
        verbose_name=_("site name"),
        max_length=255,
        null=True,
        blank=True,
        help_text=_("Human-readable name for the site."),
    )
    is_default_site = models.BooleanField(
        verbose_name=_("is default site"),
        default=False,
        help_text=_(
            "If true, this site will handle requests for all other hostnames that do not have a site entry of their own"
        ),
    )

    objects = SiteManager()

    class Meta:
        unique_together = ("hostname", "port")
        verbose_name = _("site")
        verbose_name_plural = _("sites")

    def natural_key(self):
        return (self.hostname, self.port)

    def __str__(self):
        if self.site_name:
            return self.site_name + (" [default]" if self.is_default_site else "")
        else:
            return (
                self.hostname
                + ("" if self.port == 80 else (":%d" % self.port))
                + (" [default]" if self.is_default_site else "")
            )

    @classmethod
    def find_for_request(cls, request):
        """
        Find the site object responsible for responding to this HTTP
        request object. Try:

        * unique hostname first
        * then hostname and port
        * if there is no matching hostname at all, or no matching
          hostname:port combination, fall back to the unique default site,
          or raise an exception

        NB this means that high-numbered ports on an extant hostname may
        still be routed to a different hostname which is set as the default
        """

        hostname = request.get_host().split(":")[0]
        port = request.get_port()

        sites = list(
            cls.objects.annotate(
                match=Case(
                    # annotate the results by best choice descending
                    # put exact hostname+port match first
                    When(hostname=hostname, port=port, then=MATCH_HOSTNAME_PORT),
                    # then put hostname+default (better than just hostname or just default)
                    When(
                        hostname=hostname,
                        is_default_site=True,
                        then=MATCH_HOSTNAME_DEFAULT,
                    ),
                    # then match default with different hostname. there is only ever
                    # one default, so order it above (possibly multiple) hostname
                    # matches so we can use sites[0] below to access it
                    When(is_default_site=True, then=MATCH_DEFAULT),
                    # because of the filter below, if it's not default then its a hostname match
                    default=MATCH_HOSTNAME,
                    output_field=models.IntegerField(),
                )
            )
            .filter(Q(hostname=hostname) | Q(is_default_site=True))
            .order_by("match")
        )

        if sites:
            # if theres a unique match or hostname (with port or default) match
            if len(sites) == 1 or sites[0].match in (
                MATCH_HOSTNAME_PORT,
                MATCH_HOSTNAME_DEFAULT,
            ):
                return sites[0]

            # if there is a default match with a different hostname, see if
            # there are many hostname matches. if only 1 then use that instead
            # otherwise we use the default
            if sites[0].match == MATCH_DEFAULT:
                return sites[len(sites) == 2]

        raise cls.DoesNotExist()

    @property
    def root_page(self):
        try:
            language = Language.get_active()
            return self.languages.get(language=language).root_page
        except (Language.DoesNotExist, SiteLanguage.DoesNotExist):
            language = Language.default()
            return self.languages.get(language=language).root_page

    @property
    def root_url(self):
        if self.port == 80:
            return "http://%s" % self.hostname
        elif self.port == 443:
            return "https://%s" % self.hostname
        else:
            return "http://%s:%d" % (self.hostname, self.port)

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude)
        # Only one site can have the is_default_site flag set
        try:
            default = Site.objects.get(is_default_site=True)
        except Site.DoesNotExist:
            pass
        except Site.MultipleObjectsReturned:
            raise
        else:
            if self.is_default_site and self.pk != default.pk:
                raise ValidationError(
                    {
                        "is_default_site": [
                            _(
                                "%(hostname)s is already configured as the default site."
                                " You must unset that before you can save this site as default."
                            )
                            % {"hostname": default.hostname}
                        ]
                    }
                )

    @staticmethod
    def get_site_root_paths():
        """
        Return a list of (id, root_path, root_url) tuples, most specific path
        first - used to translate url_paths into actual URLs with hostnames
        """
        result = cache.get("wagtail_site_root_paths")

        if result is None:
            result = []
            for site in Site.objects.order_by("-is_default_site", "hostname"):
                result.extend(
                    (
                        site.id,
                        site_language.root_page.url_path,
                        site.root_url,
                        site_language.language.code,
                    )
                    for site_language in site.languages.filter(is_active=True)
                )

            cache.set("wagtail_site_root_paths", result, 3600)

        return result


def default_region_id():
    return Region.objects.default_id()


class SiteLanguage(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="languages")
    region = models.ForeignKey(
        Region,
        verbose_name=_("region"),
        on_delete=models.CASCADE,
        related_name="+",
        default=default_region_id,
    )
    language = models.ForeignKey(
        Language, verbose_name=_("language"), on_delete=models.CASCADE, related_name="+"
    )
    root_page = models.ForeignKey(
        "wagtailcore.Page",
        verbose_name=_("root page"),
        on_delete=models.CASCADE,
        related_name="+",
    )
    is_active = models.BooleanField(_("is active"), default=True)
