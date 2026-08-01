"""Django bootstrap for the benchmark harness."""

import os
import sys


ENV_VAR = "WL_BENCHMARK_DB"


def bootstrap():
    """Configure Django against the database named by WL_BENCHMARK_DB.

    Idempotent: django.setup() is a no-op once the apps are loaded.
    """
    # The harness runs as a plain script, so neither the repo root nor src/ is
    # on the path.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in (repo_root, os.path.join(repo_root, "src")):
        if path not in sys.path:
            sys.path.insert(0, path)

    database = os.environ.get(ENV_VAR)
    if not database:
        raise RuntimeError(
            f"{ENV_VAR} is not set. Run the harness through benchmarks/run.py."
        )

    # benchmarks/settings.py, not the demo site's: it overlays DEBUG=False so
    # the measured code runs under the configuration a benchmark should use.
    # Only reachable once repo_root is on the path, above.
    os.environ["DJANGO_SETTINGS_MODULE"] = "benchmarks.settings"
    os.environ["DATABASE_URL"] = f"sqlite:///{database}"

    import django

    django.setup()
