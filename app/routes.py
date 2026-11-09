"""Rutas HTTP y presentación de SIGEV."""

from __future__ import annotations

from uuid import uuid4

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .db import get_db
from .services import (
    BusinessRuleError,
    DuplicateCodeError,
    confirm_sale,
    create_product,
    dashboard_activity,
    inventory_report,
    record_inventory_entry,
    sales_report,
    today_iso,
    update_product,
)


bp = Blueprint("main", __name__)


@bp.get("/")
def dashboard():
    return render_template("dashboard.html", **dashboard_activity(get_db()))


@bp.route("/productos", methods=["GET", "POST"])
def products():
    db = get_db()
    if request.method == "POST":
        try:
            create_product(db, request.form)
            flash("Producto creado con existencias iniciales de 0 unidades.", "success")
            return redirect(url_for("main.products"))
        except (BusinessRuleError, DuplicateCodeError) as error:
            flash(str(error), "error")

    query = request.args.get("q", "").strip()
    if query:
        like = f"%{query}%"
        rows = db.execute(
            """SELECT * FROM productos
               WHERE codigo LIKE ? OR nombre LIKE ?
               ORDER BY codigo""",
            (like, like),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM productos ORDER BY codigo").fetchall()
    return render_template("products.html", products=rows, query=query)


@bp.route("/productos/<int:product_id>/editar", methods=["GET", "POST"])
def edit_product(product_id: int):
    db = get_db()
    product = db.execute("SELECT * FROM productos WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        abort(404)
    if request.method == "POST":
        try:
            update_product(db, product_id, request.form)
            flash("Producto actualizado. Las existencias no se modificaron.", "success")
            return redirect(url_for("main.products"))
        except (BusinessRuleError, DuplicateCodeError) as error:
            flash(str(error), "error")
            product = dict(product)
            product.update(request.form)
            product["activo"] = 1 if request.form.get("activo") else 0
    return render_template("product_edit.html", product=product)


@bp.route("/entradas", methods=["GET", "POST"])
def entries():
    db = get_db()
    if request.method == "POST":
        try:
            record_inventory_entry(
                db,
                request.form.get("producto_id"),
                request.form.get("cantidad"),
                request.form.get("observacion", ""),
                request.form.get("fecha") or today_iso(),
            )
            flash("Recepción registrada y existencias actualizadas.", "success")
            return redirect(url_for("main.entries"))
        except BusinessRuleError as error:
            flash(str(error), "error")

    active_products = db.execute(
        "SELECT id, codigo, nombre, stock_actual FROM productos WHERE activo = 1 ORDER BY codigo"
    ).fetchall()
    entries_rows = db.execute(
        """SELECT e.*, p.codigo, p.nombre
           FROM entradas_inventario e JOIN productos p ON p.id = e.producto_id
           ORDER BY e.id DESC LIMIT 100"""
    ).fetchall()
    return render_template(
        "entries.html", products=active_products, entries=entries_rows, today=today_iso()
    )


@bp.route("/ventas", methods=["GET", "POST"])
def sales():
    db = get_db()
    if request.method == "POST":
        lines = [
            {"producto_id": product_id, "cantidad": quantity}
            for product_id, quantity in zip(
                request.form.getlist("producto_id"), request.form.getlist("cantidad"), strict=False
            )
            if product_id or quantity
        ]
        try:
            sale_id, created = confirm_sale(
                db,
                request.form.get("identificador_operacion", ""),
                lines,
                request.form.get("fecha") or today_iso(),
            )
            if created:
                flash(f"Venta #{sale_id} confirmada. Existencias actualizadas.", "success")
            else:
                flash("Esta venta ya había sido confirmada; no se descontaron existencias nuevamente.", "info")
            return redirect(url_for("main.sales"))
        except BusinessRuleError as error:
            flash(str(error), "error")

    active_products = db.execute(
        """SELECT id, codigo, nombre, precio_centavos, stock_actual
           FROM productos WHERE activo = 1 ORDER BY codigo"""
    ).fetchall()
    recent_sales = db.execute(
        "SELECT * FROM ventas ORDER BY id DESC LIMIT 20"
    ).fetchall()
    return render_template(
        "sales.html",
        products=active_products,
        recent_sales=recent_sales,
        today=today_iso(),
        operation_id=f"OP-{uuid4().hex[:12].upper()}",
    )


@bp.get("/inventario")
def inventory():
    report = inventory_report(get_db())
    return render_template("inventory.html", **report)


@bp.get("/reportes")
def reports():
    start = request.args.get("desde", "")
    end = request.args.get("hasta", "")
    try:
        sale_data = sales_report(get_db(), start or None, end or None)
    except BusinessRuleError as error:
        flash(str(error), "error")
        sale_data = sales_report(get_db(), None, None)
    inventory_data = inventory_report(get_db())
    return render_template("reports.html", sales=sale_data, **inventory_data)
