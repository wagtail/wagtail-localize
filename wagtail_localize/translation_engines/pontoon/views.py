from django.shortcuts import render, redirect

from .models import PontoonSyncLog, PontoonResource
from .sync import get_sync_manager


def dashboard(request):
    sync_manager = get_sync_manager()
    return render(
        request,
        "wagtail_localize_pontoon/dashboard.html",
        {
            "resources": PontoonResource.objects.all(),
            "logs": PontoonSyncLog.objects.order_by("-time"),
            "sync_running": sync_manager.is_running(),
            "sync_queued": sync_manager.is_queued(),
        },
    )


def force_sync(request):
    sync_manager = get_sync_manager()
    if not sync_manager.is_queued():
        sync_manager.trigger()

    return redirect("wagtail_localize_pontoon:dashboard")
