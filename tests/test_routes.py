from __future__ import annotations

import hashlib

import pytest

from app.db import get_db
from app.services import confirm_sale, create_product, record_inventory_entry


def test_dashboard_and_reports_render_without_mocked_metrics(client):
    dashboard = client.get("/")
    reports = client.get("/reportes")
    assert dashboard.status_code == 200
    assert b"Productos activos" in dashboard.data
    assert reports.status_code == 200
    assert b"No hay ventas en el rango seleccionado" in reports.data
    dashboard_text = dashboard.get_data(as_text=True)
    assert "Operación del MVP" not in dashboard_text
    assert "Acciones frecuentes" in dashboard_text


def test_product_form_creates_product_with_zero_stock(client, app):
    response = client.post(
        "/productos",
        data={
            "codigo": "web-001",
            "nombre": "Producto web",
            "precio": "3.25",
            "stock_minimo": "0",
            "activo": "1",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"existencias iniciales de 0" in response.data
    with app.app_context():
        product = get_db().execute("SELECT codigo, stock_actual FROM productos").fetchone()
        assert (product["codigo"], product["stock_actual"]) == ("WEB-001", 0)


def test_product_form_clarifies_required_optional_and_prevents_accidental_enter(client):
    page = client.get("/productos").get_data(as_text=True)
    assert "Campos obligatorios" in page
    assert "Descripción <span class=\"optional\">(opcional)</span>" in page
    assert "Stock mínimo de reposición" in page
    assert "no modifica las existencias actuales" in page
    assert "data-prevent-enter-submit" in page
    assert "/static/product-form.js" in page


def test_success_notification_is_dismissible_and_errors_remain_alerts(client):
    success = client.post(
        "/productos",
        data={"codigo": "NOTIF-001", "nombre": "Notificación", "precio": "1.00", "stock_minimo": "0"},
        follow_redirects=True,
    ).get_data(as_text=True)
    assert 'role="status"' in success
    assert 'data-auto-dismiss="6000"' in success
    assert 'aria-label="Cerrar notificación"' in success

    error = client.post(
        "/productos",
        data={"codigo": "", "nombre": "", "precio": "0", "stock_minimo": "0"},
    ).get_data(as_text=True)
    assert 'role="alert"' in error
    assert 'data-auto-dismiss' not in error


@pytest.mark.parametrize("endpoint", ["/", "/productos", "/entradas", "/ventas", "/inventario", "/reportes"])
def test_each_view_marks_only_its_current_navigation_item(client, endpoint):
    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.headers.get("Location") is None
    page = response.get_data(as_text=True)
    assert page.count('aria-current="page"') == 1


def test_reports_show_all_dates_without_internal_sentinel_values(client):
    all_dates = client.get("/reportes").get_data(as_text=True)
    assert "Rango aplicado: Todas las fechas" in all_dates
    assert "0001-01-01" not in all_dates
    assert "9999-12-31" not in all_dates

    filtered = client.get("/reportes?desde=2026-11-08&hasta=2026-11-08").get_data(as_text=True)
    assert "Rango aplicado: 08/11/2026 a 08/11/2026" in filtered


def test_inventory_uses_human_readable_movement_and_replenishment_labels(client, app):
    with app.app_context():
        db = get_db()
        at_minimum = create_product(
            db,
            {"codigo": "MIN-001", "nombre": "En mínimo", "precio": "2.00", "stock_minimo": "2", "activo": "1"},
        )
        below_minimum = create_product(
            db,
            {"codigo": "BAJO-001", "nombre": "Por debajo", "precio": "3.00", "stock_minimo": "2", "activo": "1"},
        )
        record_inventory_entry(db, at_minimum, 2, entry_date="2026-11-08")
        record_inventory_entry(db, below_minimum, 2, entry_date="2026-11-08")
        confirm_sale(db, "OP-UX-MOVIMIENTO", [{"producto_id": below_minimum, "cantidad": 1}], "2026-11-08")

    page = client.get("/inventario").get_data(as_text=True)
    assert "Entrada de mercancía" in page
    assert "Salida por venta" in page
    assert "En el mínimo" in page
    assert "Por debajo del mínimo" in page


def test_dashboard_lists_only_persisted_recent_activity(client, app):
    with app.app_context():
        db = get_db()
        product = create_product(
            db,
            {"codigo": "PANEL-001", "nombre": "Producto del panel", "precio": "7.25", "stock_minimo": "2", "activo": "1"},
        )
        record_inventory_entry(db, product, 3, entry_date="2026-11-08")
        confirm_sale(db, "PANEL-VENTA-001", [{"producto_id": product, "cantidad": 2}], "2026-11-08")

    page = client.get("/").get_data(as_text=True)
    assert "PANEL-VENTA-001" in page
    assert "B/. 14.50" in page
    assert "Producto del panel" in page
    assert "Por debajo" in page
    assert "Salida por venta" in page


def test_brand_favicon_and_responsive_table_metadata_are_rendered(client, app):
    with app.app_context():
        create_product(
            get_db(),
            {"codigo": "RESP-001", "nombre": "Producto adaptable", "precio": "2.50", "stock_minimo": "1", "activo": "1"},
        )
    dashboard = client.get("/").get_data(as_text=True)
    products = client.get("/productos").get_data(as_text=True)
    sales = client.get("/ventas").get_data(as_text=True)
    assert 'rel="icon" type="image/png"' in dashboard
    assert '<html lang="es-PA">' in dashboard
    assert dashboard.count("brand-snake.png") == 2
    assert "brand-mark.svg" not in dashboard
    assert "favicon.svg" not in dashboard
    assert 'class="responsive-table"' in products
    assert 'data-label="Existencias actuales"' in products
    assert 'aria-label="Producto de la venta"' in sales


def test_navigation_uses_tablet_grid_and_accessible_mobile_menu(client):
    page = client.get("/").get_data(as_text=True)
    styles = client.get("/static/styles.css").get_data(as_text=True)
    script = client.get("/static/navigation.js").get_data(as_text=True)

    assert 'class="nav-toggle"' in page
    assert 'aria-expanded="false"' in page
    assert 'aria-controls="main-navigation"' in page
    assert 'id="main-navigation"' in page
    assert "/static/navigation.js" in page
    assert "position: sticky" in styles
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in styles
    assert ".js .sidebar nav.is-open" in styles
    assert "@view-transition { navigation: auto; }" in styles
    assert "view-transition-name: sigev-sidebar" in styles
    assert "view-transition-name: sigev-content" in styles
    assert "prefers-reduced-motion: reduce" in styles
    assert "matchMedia('(max-width: 680px)')" in script
    assert "fetch(url" in script
    assert "document.startViewTransition" in script
    assert "history.pushState" in script
    assert "window.addEventListener('popstate'" in script
    assert "!reducedMotion.matches" in script
    assert "event.key === 'Escape'" in script


def test_reference_snake_brand_uses_the_original_png_directly(client):
    dashboard = client.get("/").get_data(as_text=True)
    source = client.get("/static/brand-snake.png").data

    assert hashlib.sha256(source).hexdigest() == "15810f7ff1443794f4983c292b78aee251f69ea9b937f94f0f758abe31d4a431"
    assert 'src="/static/brand-snake.png"' in dashboard
    assert 'href="/static/brand-snake.png"' in dashboard
    assert "brand-mark.svg" not in dashboard
    assert "favicon.svg" not in dashboard


def test_interface_uses_consistent_commercial_language(client, app):
    with app.app_context():
        create_product(
            get_db(),
            {"codigo": "LEX-001", "nombre": "Producto de referencia", "precio": "1.00", "stock_minimo": "1", "activo": "1"},
        )
    dashboard = client.get("/").get_data(as_text=True)
    entries = client.get("/entradas").get_data(as_text=True)
    sales = client.get("/ventas").get_data(as_text=True)
    reports = client.get("/reportes").get_data(as_text=True)

    assert "Operaciones habituales" in dashboard
    assert "Prototipo académico" not in dashboard
    assert "Demostración académica" not in dashboard
    assert "Datos almacenados localmente" not in dashboard
    assert "Ejecución local" not in dashboard
    assert "Alertas de reposición" in dashboard
    assert "Registre recepciones" in entries
    assert "Agregar producto" in sales
    assert "Ventas por rango de fechas" in reports
    assert '<strong class="money">B/. 0.00</strong>' in reports
    assert "Operación del MVP" not in dashboard + entries + sales + reports
