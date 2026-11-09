# SIGEV — Sistema Integral de Gestión de Inventario y Ventas

SIGEV es una aplicación web local para registrar productos, recepciones de mercancía y ventas, y consultar inventario y reportes. Utiliza Python, Flask y SQLite.

## Funciones

- **Panel:** productos activos, ventas, importes y alertas de reposición.
- **Productos:** alta, búsqueda y edición del catálogo.
- **Recepción:** entradas de unidades y actualización de existencias.
- **Ventas:** registro de varias líneas, validación de inventario y prevención de duplicados.
- **Inventario:** saldos, movimientos y mínimos de reposición.
- **Reportes:** ventas por fechas, artículos vendidos y alertas.

## Requisitos

Windows 10 u 11, Python **3.12** con el lanzador `py`, PowerShell y un navegador moderno. Para clonar el repositorio privado necesitas autorización en GitHub y Git instalado.

## Instalación en Windows

Abre PowerShell y ejecuta:

```powershell
mkdir "$HOME\Dev\Proyectos" -Force | Out-Null
cd "$HOME\Dev\Proyectos"
git clone https://github.com/3UR12/SIGEV.git
cd SIGEV
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Si ya tienes el repositorio, usa `git pull --ff-only origin main` en lugar de volver a clonarlo. No necesitas activar el entorno virtual.

## Iniciar con una base de datos nueva

```powershell
cd "$HOME\Dev\Proyectos\SIGEV"
Remove-Item Env:SIGEV_DATABASE -ErrorAction SilentlyContinue
$env:SIGEV_PORT = "5055"
.\.venv\Scripts\python.exe run.py
```

Abre **http://127.0.0.1:5055**. La aplicación crea la base de trabajo `instance\sigev.sqlite3` cuando sea necesario. Para detenerla, presiona **Ctrl + C**.

## Iniciar con datos de ejemplo

La demostración utiliza una base distinta a la de trabajo.

```powershell
cd "$HOME\Dev\Proyectos\SIGEV"
.\.venv\Scripts\python.exe scripts\create_demo_db.py
$env:SIGEV_DATABASE = (Resolve-Path ".\instance\sigev-demo.sqlite3").Path
$env:SIGEV_PORT = "5113"
.\.venv\Scripts\python.exe run.py
```

Abre **http://127.0.0.1:5113**. Si el script informa que la base de ejemplo ya existe, puedes usarla sin volver a crearla. La información de ejemplo tiene fechas de octubre y noviembre de 2026; por ello, los indicadores de «hoy» pueden variar según la fecha actual.

Para restablecer **solo la base demostrativa**, detén primero el servidor y ejecuta:

```powershell
.\.venv\Scripts\python.exe scripts\create_demo_db.py --reset
```

Esta opción elimina las modificaciones realizadas en la demostración. No borra `instance\sigev.sqlite3`.

Para regresar a la base de trabajo:

```powershell
Remove-Item Env:SIGEV_DATABASE -ErrorAction SilentlyContinue
Remove-Item Env:SIGEV_PORT -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe run.py
```

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Archivos principales

| Ruta | Uso |
| --- | --- |
| `app/` | Aplicación Flask, páginas HTML, CSS y JavaScript. |
| `app/db.py` | Base de datos SQLite y su esquema. |
| `app/services.py` | Operaciones de productos, inventario y ventas. |
| `scripts/create_demo_db.py` | Creación y restablecimiento de datos de prueba. |
| `tests/` | Pruebas automatizadas. |
| `run.py` | Inicio local del servidor. |
| `requirements.txt` | Dependencias de Python. |

Las bases dentro de `instance/` y el entorno `.venv/` no se publican en Git.

## Problemas frecuentes

- **No se reconoce `py -3.12`:** instala Python 3.12 y su lanzador para Windows.
- **Falta Flask:** vuelve a ejecutar la instalación de `requirements.txt` con el Python del entorno virtual.
- **Puerto ocupado:** detén la instancia anterior o establece `SIGEV_PORT` en otro puerto disponible.
- **La demostración aparece vacía:** comprueba `SIGEV_DATABASE` y que exista `instance\sigev-demo.sqlite3`.
- **No puedes clonar:** verifica que tu cuenta de GitHub tenga acceso al repositorio privado.

## Seguridad y alcance

SIGEV está destinado a **ejecución local** en `127.0.0.1`. La versión actual no implementa autenticación, roles, protección CSRF ni despliegue HTTPS. **No debe exponerse a Internet ni utilizarse como servicio compartido** sin incorporar y comprobar esos controles. No subas bases con datos reales, credenciales ni información personal al repositorio.

Al tratarse de bases de datos locales (.sqlite3), se aconseja automatizar copias de seguridad cifradas periódicas y evitar almacenar cadenas de conexión o configuraciones sensibles en texto plano dentro del código fuente mediante el uso de variables de entorno seguras (.env).
