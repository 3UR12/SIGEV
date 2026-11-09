from __future__ import annotations

import pytest

from app.db import close_db, get_db
from app.services import (
    BusinessRuleError,
    DuplicateCodeError,
    confirm_sale,
    create_product,
    inventory_report,
    record_inventory_entry,
    sales_report,
    update_product,
)


def product_data(code: str, name: str, price: str, minimum: int = 0) -> dict[str, object]:
    return {
        "codigo": code,
        "nombre": name,
        "descripcion": "Producto de prueba",
        "precio": price,
        "stock_minimo": minimum,
        "activo": "1",
    }


def reference_inventory(db):
    p1 = create_product(db, product_data("P-001", "Producto uno", "12.50", 2))
    p2 = create_product(db, product_data("P-002", "Producto dos", "5.00", 1))
    record_inventory_entry(db, p1, 10, "Carga inicial", "2026-11-08")
    record_inventory_entry(db, p2, 4, "Carga inicial", "2026-11-08")
    return p1, p2


def test_creates_valid_product_normalizing_code_and_zero_stock(app):
    with app.app_context():
        db = get_db()
        product_id = create_product(db, product_data(" p-001 ", "  Café molido  ", "12.50", 3))
        product = db.execute("SELECT * FROM productos WHERE id = ?", (product_id,)).fetchone()
        assert product["codigo"] == "P-001"
        assert product["nombre"] == "Café molido"
        assert product["precio_centavos"] == 1250
        assert product["stock_actual"] == 0
        assert product["stock_minimo"] == 3


def test_rejects_duplicate_product_code_after_normalization(app):
    with app.app_context():
        db = get_db()
        create_product(db, product_data("P-001", "Uno", "1.00"))
        with pytest.raises(DuplicateCodeError):
            create_product(db, product_data(" p-001 ", "Otro", "2.00"))


@pytest.mark.parametrize(
    "operation",
    [
        lambda db, product: create_product(db, product_data("P-001", "Inválido", "0")),
        lambda db, product: record_inventory_entry(db, product, 0),
        lambda db, product: confirm_sale(db, "OP-CANTIDAD-0", [{"producto_id": product, "cantidad": 0}]),
    ],
)
def test_rejects_invalid_price_or_quantity(app, operation):
    with app.app_context():
        db = get_db()
        product = create_product(db, product_data("P-VALIDO", "Válido", "2.00"))
        with pytest.raises(BusinessRuleError):
            operation(db, product)


def test_inventory_entry_increases_stock_and_records_linked_movement(app):
    with app.app_context():
        db = get_db()
        product = create_product(db, product_data("P-001", "Uno", "12.50"))
        entry_id = record_inventory_entry(db, product, 10, "Carga inicial", "2026-11-08")
        stock = db.execute("SELECT stock_actual FROM productos WHERE id = ?", (product,)).fetchone()[0]
        movement = db.execute(
            "SELECT * FROM movimientos_inventario WHERE entrada_id = ?", (entry_id,)
        ).fetchone()
        assert stock == 10
        assert movement["tipo"] == "ENTRADA"
        assert movement["cantidad"] == 10
        assert movement["stock_resultante"] == 10
        assert movement["detalle_venta_id"] is None


def test_valid_multi_item_sale_updates_stock_total_details_and_movements(app):
    with app.app_context():
        db = get_db()
        p1, p2 = reference_inventory(db)
        sale_id, created = confirm_sale(
            db,
            "OP-REFERENCIA-001",
            [{"producto_id": p1, "cantidad": 2}, {"producto_id": p2, "cantidad": 1}],
            "2026-11-08",
        )
        sale = db.execute("SELECT * FROM ventas WHERE id = ?", (sale_id,)).fetchone()
        stock = {
            row["codigo"]: row["stock_actual"]
            for row in db.execute("SELECT codigo, stock_actual FROM productos").fetchall()
        }
        details = db.execute(
            "SELECT cantidad, precio_unitario_centavos, subtotal_centavos FROM detalle_ventas WHERE venta_id = ? ORDER BY id",
            (sale_id,),
        ).fetchall()
        movements = db.execute(
            "SELECT * FROM movimientos_inventario WHERE detalle_venta_id IS NOT NULL"
        ).fetchall()
        assert created is True
        assert sale["estado"] == "CONFIRMADA"
        assert sale["total_centavos"] == 3000
        assert stock == {"P-001": 8, "P-002": 3}
        assert [(row["cantidad"], row["precio_unitario_centavos"], row["subtotal_centavos"]) for row in details] == [
            (2, 1250, 2500),
            (1, 500, 500),
        ]
        assert len(movements) == 2
        assert all(movement["entrada_id"] is None for movement in movements)


def test_insufficient_stock_rejects_sale_without_writes(app):
    with app.app_context():
        db = get_db()
        p1, p2 = reference_inventory(db)
        with pytest.raises(BusinessRuleError, match="Existencias insuficientes"):
            confirm_sale(db, "OP-SIN-STOCK", [{"producto_id": p2, "cantidad": 5}], "2026-11-08")
        assert db.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] == 0
        assert db.execute("SELECT stock_actual FROM productos WHERE id = ?", (p1,)).fetchone()[0] == 10
        assert db.execute("SELECT stock_actual FROM productos WHERE id = ?", (p2,)).fetchone()[0] == 4
        assert db.execute("SELECT COUNT(*) FROM movimientos_inventario WHERE tipo = 'SALIDA_VENTA'").fetchone()[0] == 0


def test_sale_rolls_back_every_line_if_a_later_line_fails(app):
    with app.app_context():
        db = get_db()
        p1, p2 = reference_inventory(db)
        with pytest.raises(BusinessRuleError, match="P-002"):
            confirm_sale(
                db,
                "OP-ROLLBACK",
                [{"producto_id": p1, "cantidad": 2}, {"producto_id": p2, "cantidad": 5}],
                "2026-11-08",
            )
        states = db.execute("SELECT codigo, stock_actual FROM productos ORDER BY codigo").fetchall()
        assert [(row["codigo"], row["stock_actual"]) for row in states] == [("P-001", 10), ("P-002", 4)]
        assert db.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM detalle_ventas").fetchone()[0] == 0


def test_duplicate_confirmation_is_idempotent(app):
    with app.app_context():
        db = get_db()
        p1, p2 = reference_inventory(db)
        lines = [{"producto_id": p1, "cantidad": 2}, {"producto_id": p2, "cantidad": 1}]
        first_id, first_created = confirm_sale(db, "OP-IDEMPOTENTE", lines, "2026-11-08")
        second_id, second_created = confirm_sale(db, "op-idempotente", lines, "2026-11-08")
        stocks = db.execute("SELECT codigo, stock_actual FROM productos ORDER BY codigo").fetchall()
        assert first_id == second_id
        assert first_created is True
        assert second_created is False
        assert [(row["codigo"], row["stock_actual"]) for row in stocks] == [("P-001", 8), ("P-002", 3)]
        assert db.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM movimientos_inventario WHERE tipo = 'SALIDA_VENTA'").fetchone()[0] == 2


def test_sale_preserves_historical_unit_price_after_product_price_change(app):
    with app.app_context():
        db = get_db()
        product = create_product(db, product_data("P-001", "Uno", "12.50"))
        record_inventory_entry(db, product, 3, "Carga", "2026-11-08")
        sale_id, _ = confirm_sale(db, "OP-PRECIO-HIST", [{"producto_id": product, "cantidad": 1}], "2026-11-08")
        update_product(db, product, product_data("P-001", "Uno", "20.00"))
        detail = db.execute(
            "SELECT precio_unitario_centavos, subtotal_centavos FROM detalle_ventas WHERE venta_id = ?", (sale_id,)
        ).fetchone()
        current_price = db.execute("SELECT precio_centavos FROM productos WHERE id = ?", (product,)).fetchone()[0]
        assert detail["precio_unitario_centavos"] == 1250
        assert detail["subtotal_centavos"] == 1250
        assert current_price == 2000


def test_reports_are_calculated_from_persisted_sales_and_stock(app):
    with app.app_context():
        db = get_db()
        p1, p2 = reference_inventory(db)
        confirm_sale(
            db,
            "OP-REPORTE",
            [{"producto_id": p1, "cantidad": 2}, {"producto_id": p2, "cantidad": 1}],
            "2026-11-08",
        )
        report = sales_report(db, "2026-11-08", "2026-11-08")
        inventory = inventory_report(db)
        all_dates = sales_report(db, None, None)
        assert report["summary"]["ventas"] == 1
        assert report["summary"]["total_centavos"] == 3000
        assert report["all_dates"] is False
        assert all_dates["all_dates"] is True
        assert [(row["codigo"], row["importe_centavos"]) for row in report["by_product"]] == [
            ("P-001", 2500),
            ("P-002", 500),
        ]
        assert [(row["codigo"], row["stock_actual"]) for row in inventory["stock"]] == [
            ("P-001", 8),
            ("P-002", 3),
        ]


def test_data_persists_after_closing_and_reopening_database(app):
    with app.app_context():
        db = get_db()
        product = create_product(db, product_data("P-PERSISTE", "Persistente", "9.99"))
        record_inventory_entry(db, product, 2, "Persistencia", "2026-11-08")
        close_db()
        reopened = get_db()
        row = reopened.execute("SELECT codigo, stock_actual FROM productos WHERE id = ?", (product,)).fetchone()
        assert (row["codigo"], row["stock_actual"]) == ("P-PERSISTE", 2)
