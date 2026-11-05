from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context


def today():
    """Today's date in the library's own timezone (config TIMEZONE, default Asia/Kolkata),
    so 'overdue' flips at local midnight no matter where the server runs."""
    if has_app_context():
        return datetime.now(ZoneInfo(current_app.config["TIMEZONE"])).date()
    return date.today()
