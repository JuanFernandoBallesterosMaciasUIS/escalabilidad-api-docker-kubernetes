"""
API REST de Productos (FastAPI + PostgreSQL).

Endpoints:
  GET  /productos?page=1&size=20  -> lista paginada
  GET  /productos/{id}            -> un producto
  POST /productos                 -> crea un producto
  GET  /health                    -> estado de la API

Al arrancar crea la tabla y, si esta vacia, inserta 10.000 productos.
"""
import os
import random

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/tienda"
)
TOTAL_REGISTROS = 10_000

# Pool de conexiones: se reutilizan conexiones a la BD entre peticiones
pool = ConnectionPool(DATABASE_URL, min_size=2, max_size=10, open=False)
app = FastAPI(title="API Productos")


class ProductoNuevo(BaseModel):
    nombre: str
    categoria: str
    precio: float
    stock: int


class Producto(ProductoNuevo):
    id: int


def fila_a_producto(fila) -> Producto:
    return Producto(
        id=fila[0], nombre=fila[1], categoria=fila[2],
        precio=float(fila[3]), stock=fila[4],
    )


def crear_tabla_y_datos():
    """Crea la tabla y carga 10.000 registros si esta vacia."""
    with pool.connection() as conn:
        # Bloqueo para que varias replicas no carguen datos al mismo tiempo
        conn.execute("SELECT pg_advisory_lock(1)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id        SERIAL PRIMARY KEY,
                nombre    VARCHAR(100) NOT NULL,
                categoria VARCHAR(50)  NOT NULL,
                precio    NUMERIC(10,2) NOT NULL,
                stock     INTEGER NOT NULL
            )
        """)
        total = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
        if total == 0:
            categorias = ["Hogar", "Tecnologia", "Ropa", "Deportes", "Libros"]
            filas = [
                (f"Producto {i}", random.choice(categorias),
                 round(random.uniform(1, 1000), 2), random.randint(0, 500))
                for i in range(1, TOTAL_REGISTROS + 1)
            ]
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO productos (nombre, categoria, precio, stock) "
                    "VALUES (%s, %s, %s, %s)", filas,
                )
        conn.execute("SELECT pg_advisory_unlock(1)")


@app.on_event("startup")
def al_iniciar():
    pool.open(wait=True, timeout=60)
    crear_tabla_y_datos()


@app.on_event("shutdown")
def al_cerrar():
    pool.close()


@app.get("/health")
def health():
    return {"estado": "ok", "host": os.getenv("HOSTNAME", "local")}


@app.get("/productos", response_model=list[Producto])
def listar_productos(page: int = 1, size: int = 20):
    size = min(max(size, 1), 100)
    offset = (max(page, 1) - 1) * size
    with pool.connection() as conn:
        filas = conn.execute(
            "SELECT id, nombre, categoria, precio, stock FROM productos "
            "ORDER BY id LIMIT %s OFFSET %s", (size, offset),
        ).fetchall()
    return [fila_a_producto(f) for f in filas]


@app.get("/productos/{producto_id}", response_model=Producto)
def obtener_producto(producto_id: int):
    with pool.connection() as conn:
        fila = conn.execute(
            "SELECT id, nombre, categoria, precio, stock FROM productos "
            "WHERE id = %s", (producto_id,),
        ).fetchone()
    if fila is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return fila_a_producto(fila)


@app.post("/productos", response_model=Producto, status_code=201)
def crear_producto(p: ProductoNuevo):
    with pool.connection() as conn:
        fila = conn.execute(
            "INSERT INTO productos (nombre, categoria, precio, stock) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, nombre, categoria, precio, stock",
            (p.nombre, p.categoria, p.precio, p.stock),
        ).fetchone()
    return fila_a_producto(fila)
