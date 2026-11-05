import math

PER_PAGE = 15


def page_info(args, total, per_page=PER_PAGE):
    """Return (page, pages, offset, per_page); an out-of-range ?page= is clamped."""
    pages = max(math.ceil(total / per_page), 1)
    page = min(max(args.get("page", 1, type=int), 1), pages)
    return page, pages, (page - 1) * per_page, per_page
