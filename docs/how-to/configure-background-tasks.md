# Configuring background tasks

In Wagtail Localize, it's possible to perform bulk actions such as submitting an entire page tree for translation or create a new locale by copying all the content from an existing one.

While these are powerful features, they can be quite slow on large sites (where you might be submitting >100 pages at a time) and this can even cause timeouts.

To mitigate this, Wagtail Localize provides a mechanism to allow you to configure these tasks to be run in a background worker instead.

Currently, Wagtail Localize supports [Django RQ](https://github.com/rq/django-rq) out of the box, and you can implement support for others as documented below

## Configuring Django RQ

Wagtail Localize has built-in support for Django RQ. So if you already have Django RQ installed, you can configure it with the following setting:

```python
WAGTAILLOCALIZE_JOBS = {
    "BACKEND": "bakerydemo.queue.DjangoRQJobBackend",
    "OPTIONS": {"QUEUE": "default"},
}
```

The `OPTIONS` => `QUEUE` key configures the Django RQ queue to push tasks to.

## Configuring a different queueing system

To configure any other queueing system, create a subclass of `wagtail_localize.tasks.BaseJobBackend` somewhere in your project and override the `__init__` and `enqueue` methods:

```python
class MyJobBackend(BaseJobBackend):
    def __init__(self, options):
        # Any set up code goes here. Note that the 'options' parameter contains the value of WAGTAILLOCALIZE_JOBS["OPTIONS"]

    def enqueue(self, func, args, kwargs):
        # func is a function object to call
        # args is a list of positional arguments to pass into the function when it's called
        # kwargs is is a list of keyword arguments to pass into the function when it's called
```

When you've implemented that class, hook it in to Wagtail Localize using the `WAGTAILLOCALIZE_JOBS` setting:

```python
WAGTAILLOCALIZE_JOBS = {
    "BACKEND": "python.path.to.MyJobBackend",
    "OPTIONS": {
        # Any options can go here
    },
}
```
