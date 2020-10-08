from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect

from wagtail_localize.models import Translation

from .models import Resource, SyncLog, SyncLogResource
from .sync import get_sync_manager


@user_passes_test(lambda u: u.is_superuser)
def dashboard(request):
    sync_manager = get_sync_manager()
    return render(
        request,
        "wagtail_localize_git/dashboard.html",
        {
            "resources": [
                (resource, [
                    (
                        locale,
                        Translation.objects.filter(object_id=resource.object_id, target_locale=locale).first(),
                        SyncLogResource.objects.filter(resource=resource, locale=locale).last(),
                    )

                    for locale in resource.logs.unique_locales()
                ])
                for resource in Resource.objects.all()
            ],
            "logs": SyncLog.objects.order_by("-time"),
            "sync_running": sync_manager.is_running(),
            "sync_queued": sync_manager.is_queued(),
        },
    )


@user_passes_test(lambda u: u.is_superuser)
def force_sync(request):
    sync_manager = get_sync_manager()
    if not sync_manager.is_queued():
        sync_manager.trigger()

    return redirect("wagtail_localize_git:dashboard")
