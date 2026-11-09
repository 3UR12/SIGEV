from __future__ import annotations

import sqlite3

import pytest

from scripts.create_demo_db import create_demo_database


def test_demo_database_is_real_reproducible_and_never_overwritten(tmp_path):
    database = tmp_path / "sigev-demo.sqlite3"
    created = create_demo_database(database)
    assert created == database.resolve()

    db = sqlite3.connect(database)
    db.row_factory = sqlite3.Row
    assert db.execute("SELECT COUNT(*) FROM productos").fetchone()[0] == 18
    assert db.execute("SELECT COUNT(*) FROM entradas_inventario").fetchone()[0] == 23
    assert db.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] == 14
    assert db.execute("SELECT COUNT(DISTINCT fecha) FROM ventas").fetchone()[0] == 14
    assert db.execute("SELECT COUNT(*) FROM detalle_ventas").fetchone()[0] == 31
    assert db.execute("SELECT COUNT(*) FROM movimientos_inventario").fetchone()[0] == 54
    stocks = {
        row["codigo"]: row["stock_actual"]
        for row in db.execute("SELECT codigo, stock_actual FROM productos").fetchall()
    }
    assert stocks == {
        "SIG-001": 27,
        "SIG-002": 16,
        "SIG-003": 75,
        "SIG-004": 40,
        "SIG-005": 16,
        "SIG-006": 27,
        "SIG-007": 9,
        "SIG-008": 31,
        "SIG-009": 13,
        "SIG-010": 22,
        "SIG-011": 10,
        "SIG-012": 20,
        "SIG-013": 4,
        "SIG-014": 8,
        "SIG-015": 8,
        "SIG-016": 10,
        "SIG-017": 16,
        "SIG-018": 55,
    }

    levels = {
        row["codigo"]: row["nivel"]
        for row in db.execute(
            """SELECT codigo,
                      CASE WHEN stock_actual < stock_minimo THEN 'BAJO'
                           WHEN stock_actual = stock_minimo THEN 'MINIMO'
                           ELSE 'DISPONIBLE' END AS nivel
               FROM productos"""
        ).fetchall()
    }
    db.close()

    with pytest.raises(FileExistsError):
        create_demo_database(database)

    assert levels["SIG-005"] == "BAJO"
    assert levels["SIG-007"] == "MINIMO"
    assert levels["SIG-001"] == "DISPONIBLE"
