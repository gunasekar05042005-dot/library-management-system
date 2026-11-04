from flask import Blueprint, render_template

from .auth import admin_required
from .db import get_db
from .services.stats import admin_stats

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_required
def dashboard():
    return render_template("admin_dashboard.html", stats=admin_stats(get_db()))
