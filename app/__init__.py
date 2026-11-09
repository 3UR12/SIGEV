"""Aplicación web local de SIGEV."""

from __future__ import annotations

import os
from datetime import date

from flask import Flask

from .db import close_db, init_app as init_db_app, init_db


def create_app(test_config: dict | None = None) -> Flask:
    """Crea una instancia configurable de la aplicación."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SIGEV_SECRET_KEY", "desarrollo-local-no-usar-en-produccion"),
        DATABASE=os.environ.get("SIGEV_DATABASE", os.path.join(app.instance_path, "sigev.sqlite3")),
    )

    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    init_db_app(app)

    with app.app_context():
        init_db()

    from .routes import bp

    app.register_blueprint(bp)
    app.teardown_appcontext(close_db)

    @app.template_filter("money")
    def money(cents: int | None) -> str:
        value = (cents or 0) / 100
        return f"B/. {value:,.2f}"

    @app.template_filter("date_pa")
    def date_pa(value: str | None) -> str:
        """Presenta fechas ISO de persistencia en el formato habitual de Panamá."""
        if not value:
            return "—"
        try:
            return date.fromisoformat(str(value)).strftime("%d/%m/%Y")
        except ValueError:
            return str(value)

    return app
