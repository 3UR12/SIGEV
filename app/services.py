"""Reglas de negocio y operaciones transaccionales de SIGEV."""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, Mapping


class BusinessRuleError(ValueError):
    """Error de una regla de negocio que puede mostrarse al usuario."""


class DuplicateCodeError(BusinessRuleError):
    """El código normalizado ya pertenece a un producto."""


class OperationConflictError(BusinessRuleError):
    """Un código de venta ya existe con productos o cantidades diferentes."""


CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,49}$")
PANAMA_TIMEZONE = timezone(timedelta(hours=-5), name="America/Panama")


def today_iso() -> str:
    return datetime.now(PANAMA_TIMEZONE).date().isoformat()


def normalize_date(value: str) -> str:
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except (TypeError, ValueError):
        raise BusinessRuleError("La fecha debe usar el formato AAAA-MM-DD.") from None


def normalize_code(value: str) -> str:
    code = (value or "").strip().upper()
    if not CODE_RE.fullmatch(code):
        raise BusinessRuleError(
            "El código debe contener entre 1 y 50 caracteres: letras, números, punto, guion o guion bajo."
        )
    return code


def normalize_operation_id(value: str) -> str:
    operation_id = (value or "").strip().upper()
    if not operation_id or len(operation_id) > 80:
        raise BusinessRuleError("El código de venta es obligatorio y debe tener hasta 80 caracteres.")
    return operation_id


def parse_positive_int(value: object, field: str) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise BusinessRuleError(f"{field} debe ser un número entero.") from None
    if number <= 0:
        raise BusinessRuleError(f"{field} debe ser mayor que cero.")
    return number


def parse_nonnegative_int(value: object, field: str) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise BusinessRuleError(f"{field} debe ser un número entero.") from None
    if number < 0:
        raise BusinessRuleError(f"{field} no puede ser negativo.")
    return number


def parse_price_cents(value: object) -> int:
    raw = str(value or "").strip().replace(",", ".")
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError):
        raise BusinessRuleError("El precio debe ser un importe válido.") from None
    cents = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if cents <= 0:
        raise BusinessRuleError("El precio debe ser mayor que cero.")
    return cents


def _product_payload(data: Mapping[str, object]) -> tuple[str, str, str, int, int, int]:
    code = normalize_code(str(data.get("codigo", "")))
    name = " ".join(str(data.get("nombre", "")).split())
    if not name:
        raise BusinessRuleError("El nombre del producto es obligatorio.")
    description = str(data.get("descripcion", "")).strip()
    price = parse_price_cents(data.get("precio", ""))
    minimum = parse_nonnegative_int(data.get("stock_minimo", 0), "El stock mínimo de reposición")
    active = 1 if str(data.get("activo", "1")) in {"1", "true", "on"} else 0
    return code, name, description, price, minimum, active


def create_product(db: sqlite3.Connection, data: Mapping[str, object]) -> int:
    code, name, description, price, minimum, active = _product_payload(data)
    try:
        cursor = db.execute(
            """INSERT INTO productos
               (codigo, nombre, descripcion, precio_centavos, stock_minimo, activo)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (code, name, description, price, minimum, active),
        )
        db.commit()
    except sqlite3.IntegrityError as error:
        db.rollback()
        if "productos.codigo" in str(error).lower() or "unique" in str(error).lower():
            raise DuplicateCodeError("Ya existe un producto con ese código.") from None
        raise
    return int(cursor.lastrowid)


def update_product(db: sqlite3.Connection, product_id: int, data: Mapping[str, object]) -> None:
    code, name, description, price, minimum, active = _product_payload(data)
    try:
        cursor = db.execute(
            """UPDATE productos
               SET codigo = ?, nombre = ?, descripcion = ?, precio_centavos = ?,
                   stock_minimo = ?, activo = ?, actualizado_en = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (code, name, description, price, minimum, active, product_id),
        )
        if cursor.rowcount != 1:
            raise BusinessRuleError("Producto no encontrado.")
        db.commit()
    except sqlite3.IntegrityError as error:
        db.rollback()
        if "productos.codigo" in str(error).lower() or "unique" in str(error).lower():
            raise DuplicateCodeError("Ya existe un producto con ese código.") from None
        raise
    except Exception:
        db.rollback()
        raise


def record_inventory_entry(
    db: sqlite3.Connection,
    product_id: object,
    quantity: object,
    observation: str = "",
    entry_date: str | None = None,
) -> int:
    product_id_int = parse_positive_int(product_id, "El producto")
    quantity_int = parse_positive_int(quantity, "La cantidad")
    when = normalize_date(entry_date or today_iso())
    observation = (observation or "").strip()
    try:
        db.execute("BEGIN IMMEDIATE")
        product = db.execute(
            "SELECT id, stock_actual, activo FROM productos WHERE id = ?", (product_id_int,)
        ).fetchone()
        if product is None:
            raise BusinessRuleError("Producto no encontrado.")
        if not product["activo"]:
            raise BusinessRuleError("No se puede registrar una entrada para un producto inactivo.")
        entry = db.execute(
            """INSERT INTO entradas_inventario (producto_id, cantidad, fecha, observacion)
               VALUES (?, ?, ?, ?)""",
            (product_id_int, quantity_int, when, observation),
        )
        new_stock = product["stock_actual"] + quantity_int
        db.execute("UPDATE productos SET stock_actual = ? WHERE id = ?", (new_stock, product_id_int))
        db.execute(
            """INSERT INTO movimientos_inventario
               (producto_id, tipo, cantidad, origen, fecha, stock_resultante, entrada_id, detalle_venta_id)
               VALUES (?, 'ENTRADA', ?, 'ENTRADA_INVENTARIO', ?, ?, ?, NULL)""",
            (product_id_int, quantity_int, when, new_stock, entry.lastrowid),
        )
        db.commit()
        return int(entry.lastrowid)
    except Exception:
        db.rollback()
        raise


def _normalized_lines(lines: Iterable[Mapping[str, object]]) -> list[dict[str, int]]:
    aggregate: defaultdict[int, int] = defaultdict(int)
    had_line = False
    for line in lines:
        had_line = True
        product_id = parse_positive_int(line.get("producto_id"), "El producto")
        quantity = parse_positive_int(line.get("cantidad"), "La cantidad")
        aggregate[product_id] += quantity
    if not had_line or not aggregate:
        raise BusinessRuleError("La venta debe contener al menos un producto.")
    return [{"producto_id": product_id, "cantidad": quantity} for product_id, quantity in sorted(aggregate.items())]


def _sale_signature(db: sqlite3.Connection, sale_id: int) -> list[tuple[int, int]]:
    rows = db.execute(
        "SELECT producto_id, cantidad FROM detalle_ventas WHERE venta_id = ? ORDER BY producto_id", (sale_id,)
    ).fetchall()
    return [(int(row["producto_id"]), int(row["cantidad"])) for row in rows]


def confirm_sale(
    db: sqlite3.Connection,
    operation_id: str,
    lines: Iterable[Mapping[str, object]],
    sale_date: str | None = None,
) -> tuple[int, bool]:
    """Confirma una venta atómica y devuelve (id_venta, creada_ahora).

    Si se reintenta exactamente una operación ya confirmada, devuelve la venta existente sin
    generar otro descuento. Un reintento con detalle distinto se rechaza.
    """
    operation = normalize_operation_id(operation_id)
    normalized_lines = _normalized_lines(lines)
    when = normalize_date(sale_date or today_iso())
    try:
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute(
            "SELECT id FROM ventas WHERE identificador_operacion = ?", (operation,)
        ).fetchone()
        if existing is not None:
            expected = [(line["producto_id"], line["cantidad"]) for line in normalized_lines]
            if _sale_signature(db, int(existing["id"])) != expected:
                raise OperationConflictError(
                    "La venta ya fue confirmada con productos o cantidades diferentes; no se aplicaron cambios."
                )
            db.commit()
            return int(existing["id"]), False

        products: dict[int, sqlite3.Row] = {}
        for line in normalized_lines:
            product = db.execute(
                """SELECT id, codigo, nombre, precio_centavos, stock_actual, activo
                   FROM productos WHERE id = ?""",
                (line["producto_id"],),
            ).fetchone()
            if product is None:
                raise BusinessRuleError("Uno de los productos seleccionados no existe.")
            if not product["activo"]:
                raise BusinessRuleError(f"El producto {product['codigo']} está inactivo.")
            if product["stock_actual"] < line["cantidad"]:
                raise BusinessRuleError(
                    f"Existencias insuficientes para {product['codigo']}: disponibles {product['stock_actual']}, solicitadas {line['cantidad']}."
                )
            products[line["producto_id"]] = product

        total = sum(products[line["producto_id"]]["precio_centavos"] * line["cantidad"] for line in normalized_lines)
        sale = db.execute(
            """INSERT INTO ventas (identificador_operacion, fecha, estado, total_centavos)
               VALUES (?, ?, 'CONFIRMADA', ?)""",
            (operation, when, total),
        )
        sale_id = int(sale.lastrowid)
        for line in normalized_lines:
            product = products[line["producto_id"]]
            unit_price = int(product["precio_centavos"])
            quantity = line["cantidad"]
            subtotal = unit_price * quantity
            detail = db.execute(
                """INSERT INTO detalle_ventas
                   (venta_id, producto_id, cantidad, precio_unitario_centavos, subtotal_centavos)
                   VALUES (?, ?, ?, ?, ?)""",
                (sale_id, line["producto_id"], quantity, unit_price, subtotal),
            )
            update = db.execute(
                """UPDATE productos SET stock_actual = stock_actual - ?
                   WHERE id = ? AND stock_actual >= ?""",
                (quantity, line["producto_id"], quantity),
            )
            if update.rowcount != 1:
                raise BusinessRuleError("Las existencias cambiaron durante la confirmación; intente nuevamente.")
            resulting_stock = int(product["stock_actual"]) - quantity
            db.execute(
                """INSERT INTO movimientos_inventario
                   (producto_id, tipo, cantidad, origen, fecha, stock_resultante, entrada_id, detalle_venta_id)
                   VALUES (?, 'SALIDA_VENTA', ?, 'VENTA', ?, ?, NULL, ?)""",
                (line["producto_id"], quantity, when, resulting_stock, detail.lastrowid),
            )
        db.commit()
        return sale_id, True
    except Exception:
        db.rollback()
        raise


def dashboard_metrics(db: sqlite3.Connection) -> sqlite3.Row:
    return db.execute(
        """SELECT
             (SELECT COUNT(*) FROM productos WHERE activo = 1) AS productos_activos,
             (SELECT COUNT(*) FROM productos WHERE stock_actual <= stock_minimo) AS bajo_minimo,
             (SELECT COUNT(*) FROM ventas WHERE fecha = ?) AS ventas_hoy,
             (SELECT COALESCE(SUM(total_centavos), 0) FROM ventas WHERE fecha = ?) AS total_hoy""",
        (today_iso(), today_iso()),
    ).fetchone()


def dashboard_activity(db: sqlite3.Connection) -> dict[str, object]:
    """Resume actividad reciente con información persistida, sin métricas simuladas."""
    latest_sales = db.execute(
        """SELECT id, identificador_operacion, fecha, total_centavos
           FROM ventas
           ORDER BY fecha DESC, id DESC
           LIMIT 5"""
    ).fetchall()
    replenishment = db.execute(
        """SELECT codigo, nombre, stock_actual, stock_minimo,
                  CASE
                      WHEN stock_actual < stock_minimo THEN 'POR_DEBAJO'
                      ELSE 'EN_MINIMO'
                  END AS nivel_reposicion
           FROM productos
           WHERE activo = 1 AND stock_actual <= stock_minimo
           ORDER BY (stock_actual - stock_minimo), codigo
           LIMIT 5"""
    ).fetchall()
    recent_movements = db.execute(
        """SELECT m.tipo, m.cantidad, m.fecha, m.stock_resultante, p.codigo, p.nombre
           FROM movimientos_inventario m
           JOIN productos p ON p.id = m.producto_id
           ORDER BY m.id DESC
           LIMIT 5"""
    ).fetchall()
    return {
        "metrics": dashboard_metrics(db),
        "latest_sales": latest_sales,
        "replenishment": replenishment,
        "recent_movements": recent_movements,
    }


def sales_report(db: sqlite3.Connection, start: str | None, end: str | None) -> dict[str, object]:
    requested_start = start
    requested_end = end
    start = normalize_date(start or "0001-01-01")
    end = normalize_date(end or "9999-12-31")
    if start > end:
        raise BusinessRuleError("La fecha inicial no puede ser posterior a la fecha final.")
    summary = db.execute(
        """SELECT COUNT(*) AS ventas, COALESCE(SUM(total_centavos), 0) AS total_centavos
           FROM ventas WHERE fecha BETWEEN ? AND ?""",
        (start, end),
    ).fetchone()
    by_product = db.execute(
        """SELECT p.codigo, p.nombre, SUM(d.cantidad) AS unidades,
                  SUM(d.subtotal_centavos) AS importe_centavos
           FROM detalle_ventas d
           JOIN ventas v ON v.id = d.venta_id
           JOIN productos p ON p.id = d.producto_id
           WHERE v.fecha BETWEEN ? AND ?
           GROUP BY p.id, p.codigo, p.nombre
           ORDER BY importe_centavos DESC, p.codigo""",
        (start, end),
    ).fetchall()
    return {
        "start": start,
        "end": end,
        "requested_start": requested_start,
        "requested_end": requested_end,
        "all_dates": not requested_start and not requested_end,
        "summary": summary,
        "by_product": by_product,
    }


def inventory_report(db: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    stock = db.execute(
        """SELECT id, codigo, nombre, stock_actual, stock_minimo, activo,
                  CASE WHEN stock_actual <= stock_minimo THEN 1 ELSE 0 END AS bajo_minimo,
                  CASE
                      WHEN stock_actual < stock_minimo THEN 'POR_DEBAJO'
                      WHEN stock_actual = stock_minimo THEN 'EN_MINIMO'
                      ELSE 'DISPONIBLE'
                  END AS nivel_reposicion
           FROM productos ORDER BY codigo"""
    ).fetchall()
    movements = db.execute(
        """SELECT m.*, p.codigo, p.nombre
           FROM movimientos_inventario m
           JOIN productos p ON p.id = m.producto_id
           ORDER BY m.id DESC LIMIT 100"""
    ).fetchall()
    return {"stock": stock, "movements": movements}
