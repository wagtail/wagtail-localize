# wagtail-localize demo site

A demo Wagtail site used to develop and try out wagtail-localize.

## Running it

From the repository root, with a virtual environment active:

```sh
python -m pip install -e .
python demo/manage.py migrate
python demo/manage.py load_initial_data
npm ci
npm run build
python demo/manage.py runserver
```

The site is then at http://localhost:8000/ and the admin at http://localhost:8000/admin/, with the user `admin` and the password `changeme`.

`load_initial_data` is safe to run again. It skips the blog tree if it already exists; pass `--force` to rebuild it.

## What there is to see

The demo ships in English with one post translated into French, so that the translation features have something to act on out of the box:

- http://localhost:8000/en/blog/bread-circuses/ — the post in English
- http://localhost:8000/fr/blog/du-pain-et-des-jeux/ — the same post in French

There is no language switcher yet, so the French URL has to be typed.

`/fr/` and `/fr/blog/` exist as aliases of their English counterparts, because only the post itself was translated. That is what a partly translated site looks like.

`WAGTAIL_CONTENT_LANGUAGES` also includes German, Arabic and Spanish, with no content in them. `load_initial_data` only creates the French locale. To use one of the others, add it under Settings → Locales in the admin, then translate a page into it.

In the admin, the French post opens in the translation editor rather than the normal page form, and the `Person` snippet has a translate action. Opening the French version of a person shows the difference between a translated field and a synchronised one: the job title is translated, while the first and last names are inherited from the English version and can be overridden one by one.

## Machine translation

Machine translation requires a DeepL key, so the demo also runs without an account. Set `DEEPL_AUTH_KEY` in the environment before starting the server:

```sh
export DEEPL_AUTH_KEY="your-key-here"
```

Keys from DeepL's free tier end in `:fx`, and wagtail-localize picks the right API endpoint from that suffix. With a key set, the translation editor gains an action that translates the remaining segments in one step.
