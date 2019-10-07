def find_available_slug(parent, requested_slug):
    existing_slugs = set(
        parent.get_children()
        .filter(slug__startswith=requested_slug)
        .values_list("slug", flat=True)
    )
    slug = requested_slug
    number = 1

    while slug in existing_slugs:
        slug = requested_slug + "-" + str(number)
        number += 1

    return slug
