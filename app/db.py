"""Conexión y esquema SQLite para SIGEV."""

from __future__ import annotations

import sqlite3

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY,
    codigo TEXT NOT NULL UNIQUE COLLATE NOCASE
        CHECK (codigo = upper(trim(codigo)) AND length(codigo) BETWEEN 1 AND 50),
    nombre TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
    descripcion TEXT NOT NULL DEFAULT '',
    precio_centavos INTEGER NOT NULL CHECK (precio_centavos > 0),
    stock_actual INTEGER NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
    stock_minimo INTEGER NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entradas_inventario (
    id INTEGER PRIMARY KEY,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE RESTRICT,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    fecha TEXT NOT NULL,
    observacion TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ventas (
    id INTEGER PRIMARY KEY,
    identificador_operacion TEXT NOT NULL UNIQUE COLLATE NOCASE
        CHECK (length(trim(identificador_operacion)) > 0),
    fecha TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado = 'CONFIRMADA'),
    total_centavos INTEGER NOT NULL CHECK (total_centavos > 0),
    confirmada_en TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS detalle_ventas (
    id INTEGER PRIMARY KEY,
    venta_id INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE RESTRICT,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario_centavos INTEGER NOT NULL CHECK (precio_unitario_centavos > 0),
    subtotal_centavos INTEGER NOT NULL
        CHECK (subtotal_centavos = cantidad * precio_unitario_centavos)
);

CREATE TABLE IF NOT EXISTS movimientos_inventario (
    id INTEGER PRIMARY KEY,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE RESTRICT,
    tipo TEXT NOT NULL CHECK (tipo IN ('ENTRADA', 'SALIDA_VENTA')),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    origen TEXT NOT NULL CHECK (origen IN ('ENTRADA_INVENTARIO', 'VENTA')),
    fecha TEXT NOT NULL,
    stock_resultante INTEGER NOT NULL CHECK (stock_resultante >= 0),
    entrada_id INTEGER REFERENCES entradas_inventario(id) ON DELETE RESTRICT,
    detalle_venta_id INTEGER REFERENCES detalle_ventas(id) ON DELETE RESTRICT,
    CHECK (
        (entrada_id IS NOT NULL AND detalle_venta_id IS NULL AND tipo = 'ENTRADA' AND origen = 'ENTRADA_INVENTARIO')
        OR
        (entrada_id IS NULL AND detalle_venta_id IS NOT NULL AND tipo = 'SALIDA_VENTA' AND origen = 'VENTA')
    )
);

CREATE INDEX IF NOT EXISTS idx_entradas_producto_fecha
    ON entradas_inventario(producto_id, fecha DESC);
CREATE INDEX IF NOT EXISTS idx_detalle_venta ON detalle_ventas(venta_id);
CREATE INDEX IF NOT EXISTS idx_movimientos_producto_fecha
    ON movimientos_inventario(producto_id, fecha DESC);
CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha);
"""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db = sqlite3.connect(current_app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 5000")
        g.db = db
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


def init_app(app) -> None:
    """Registra el comando de inicialización manual de base de datos."""
    import click

    @app.cli.command("init-db")
    def init_db_command() -> None:
        init_db()
        click.echo("Base de datos inicializada.")
