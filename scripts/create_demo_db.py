"""Crea una base demostrativa independiente mediante los servicios reales de SIGEV."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.db import get_db
from app.services import confirm_sale, create_product, record_inventory_entry


DEMO_DATABASE = PROJECT_ROOT / "instance" / "sigev-demo.sqlite3"

DEMO_PRODUCTS = [
    ("SIG-001", "Resma de papel carta 75 g/m²", "Paquete de 500 hojas blancas tamaño carta.", "6.95", "10"),
    ("SIG-002", "Resma de papel legal 75 g/m²", "Paquete de 500 hojas blancas tamaño legal.", "8.25", "6"),
    ("SIG-003", "Bolígrafo retráctil azul 1.0 mm", "Unidad con tinta azul y punta media de 1.0 mm.", "0.85", "20"),
    ("SIG-004", "Lápiz de grafito HB con borrador", "Unidad de madera con mina HB y borrador integrado.", "0.55", "15"),
    ("SIG-005", "Marcador permanente negro punta fina", "Unidad de tinta negra resistente al agua y punta fina.", "1.75", "18"),
    ("SIG-006", "Cuaderno espiral carta 100 páginas", "Cuaderno rayado tamaño carta con espiral metálico.", "3.90", "6"),
    ("SIG-007", "Libreta ejecutiva A5 80 hojas", "Libreta rayada A5 con cubierta rígida y cinta separadora.", "5.75", "9"),
    ("SIG-008", "Carpeta plástica oficio con broche", "Carpeta azul tamaño oficio con broche de presión.", "2.25", "8"),
    ("SIG-009", "Archivador de palanca carta 3 pulgadas", "Archivador tamaño carta con lomo de 3 pulgadas.", "4.95", "4"),
    ("SIG-010", "Notas adhesivas 76 × 76 mm", "Bloc de 100 hojas adhesivas color amarillo.", "1.60", "10"),
    ("SIG-011", "Grapadora metálica de escritorio", "Grapadora para hasta 20 hojas, compatible con grapas 26/6.", "8.90", "3"),
    ("SIG-012", "Grapas 26/6 caja de 5,000", "Caja con 5,000 grapas galvanizadas estándar 26/6.", "3.50", "10"),
    ("SIG-013", "Tóner láser negro 1,600 páginas", "Cartucho negro con rendimiento estimado de 1,600 páginas.", "39.50", "5"),
    ("SIG-014", "Calculadora de escritorio 12 dígitos", "Calculadora de sobremesa con pantalla de 12 dígitos.", "12.75", "8"),
    ("SIG-015", "Memoria USB 32 GB USB 3.0", "Unidad flash de 32 GB con interfaz USB 3.0.", "9.95", "4"),
    ("SIG-016", "Etiquetas adhesivas A4, 21 por hoja", "Paquete de 100 hojas A4 con 21 etiquetas blancas por hoja.", "12.50", "5"),
    ("SIG-017", "Caja de archivo corrugado tamaño oficio", "Caja reforzada para expedientes y documentos tamaño oficio.", "3.25", "6"),
    ("SIG-018", "Cinta adhesiva transparente 18 mm × 30 m", "Rollo de cinta transparente para empaque liviano y oficina.", "1.20", "12"),
]

INITIAL_RECEIPTS = {
    "SIG-001": 40,
    "SIG-002": 24,
    "SIG-003": 80,
    "SIG-004": 60,
    "SIG-005": 30,
    "SIG-006": 25,
    "SIG-007": 18,
    "SIG-008": 30,
    "SIG-009": 16,
    "SIG-010": 36,
    "SIG-011": 12,
    "SIG-012": 20,
    "SIG-013": 8,
    "SIG-014": 10,
    "SIG-015": 15,
    "SIG-016": 12,
    "SIG-017": 20,
    "SIG-018": 40,
}

ADDITIONAL_RECEIPTS = [
    ("SIG-003", 25, "2026-11-02", "Reposición de bolígrafos para la semana"),
    ("SIG-006", 12, "2026-11-03", "Reposición de cuadernos tamaño carta"),
    ("SIG-008", 15, "2026-11-05", "Reposición de carpetas tamaño oficio"),
    ("SIG-012", 10, "2026-11-06", "Reposición de grapas estándar"),
    ("SIG-018", 20, "2026-11-04", "Reposición de cinta adhesiva para despacho"),
]

DEMO_SALES = [
    ("DEMO-VENTA-013", "2026-10-26", [("SIG-016", 2), ("SIG-018", 5)]),
    ("DEMO-VENTA-014", "2026-10-27", [("SIG-017", 4), ("SIG-003", 8)]),
    ("DEMO-VENTA-001", "2026-10-28", [("SIG-001", 5), ("SIG-003", 10)]),
    ("DEMO-VENTA-002", "2026-10-29", [("SIG-006", 3), ("SIG-004", 8)]),
    ("DEMO-VENTA-003", "2026-10-30", [("SIG-010", 6), ("SIG-008", 4)]),
    ("DEMO-VENTA-004", "2026-10-31", [("SIG-013", 2), ("SIG-002", 3)]),
    ("DEMO-VENTA-005", "2026-11-01", [("SIG-011", 2), ("SIG-012", 4)]),
    ("DEMO-VENTA-006", "2026-11-02", [("SIG-005", 5), ("SIG-003", 12), ("SIG-015", 2)]),
    ("DEMO-VENTA-007", "2026-11-03", [("SIG-001", 8), ("SIG-009", 3)]),
    ("DEMO-VENTA-008", "2026-11-04", [("SIG-007", 4), ("SIG-014", 2)]),
    ("DEMO-VENTA-009", "2026-11-05", [("SIG-008", 10), ("SIG-010", 8)]),
    ("DEMO-VENTA-010", "2026-11-06", [("SIG-013", 2), ("SIG-006", 7)]),
    ("DEMO-VENTA-011", "2026-11-07", [("SIG-002", 5), ("SIG-004", 12), ("SIG-012", 6)]),
    ("DEMO-VENTA-012", "2026-11-08", [("SIG-015", 5), ("SIG-005", 9), ("SIG-007", 5)]),
]


def create_demo_database(database_path: Path) -> Path:
    """Crea una base nueva; nunca reemplaza un archivo existente."""
    database_path = database_path.resolve()
    if database_path.exists():
        raise FileExistsError(f"La base ya existe: {database_path}")
    database_path.parent.mkdir(parents=True, exist_ok=True)

    app = create_app(
        {
            "DATABASE": str(database_path),
            "SECRET_KEY": "sigev-demostracion-local",
            "TESTING": True,
        }
    )
    with app.app_context():
        db = get_db()
        products = {}
        for code, name, description, price, minimum in DEMO_PRODUCTS:
            products[code] = create_product(
                db,
                {
                    "codigo": code,
                    "nombre": name,
                    "descripcion": description,
                    "precio": price,
                    "stock_minimo": minimum,
                    "activo": "1",
                },
            )

        for code, quantity in INITIAL_RECEIPTS.items():
            record_inventory_entry(
                db,
                products[code],
                quantity,
                "Recepción inicial del catálogo de demostración",
                "2026-10-25",
            )

        event_dates = sorted(
            {receipt[2] for receipt in ADDITIONAL_RECEIPTS}
            | {sale[1] for sale in DEMO_SALES}
        )
        for event_date in event_dates:
            for code, quantity, receipt_date, observation in ADDITIONAL_RECEIPTS:
                if receipt_date == event_date:
                    record_inventory_entry(db, products[code], quantity, observation, receipt_date)
            for operation_id, sale_date, lines in DEMO_SALES:
                if sale_date == event_date:
                    confirm_sale(
                        db,
                        operation_id,
                        [
                            {"producto_id": products[code], "cantidad": quantity}
                            for code, quantity in lines
                        ],
                        sale_date,
                    )

    return database_path


def reset_demo_database() -> Path:
    """Restaura únicamente la ruta fija de demostración tras verificarla."""
    resolved = DEMO_DATABASE.resolve()
    expected = (PROJECT_ROOT / "instance" / "sigev-demo.sqlite3").resolve()
    if resolved != expected:
        raise RuntimeError("La ruta de demostración no coincide con la ruta segura esperada.")
    if resolved.exists():
        resolved.unlink()
    return create_demo_database(resolved)


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea la base de demostración independiente de SIGEV.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="elimina y reconstruye solo instance/sigev-demo.sqlite3",
    )
    args = parser.parse_args()
    try:
        path = reset_demo_database() if args.reset else create_demo_database(DEMO_DATABASE)
    except FileExistsError as error:
        print(error)
        print("Use --reset para restaurar exclusivamente la base de demostración.")
        return 2
    print(f"Base de demostración creada: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
