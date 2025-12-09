# db.py
from __future__ import annotations
from typing import List

import streamlit as st
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
import pathlib

# Vistas que el agente puede usar
ALLOWED_TABLES = [
    "tbl_dim_concepto",
    "tbl_dim_empresa",
    "tbl_dim_ubicacion",
    "tbl_fact_costos",
    "tbl_fact_ingresos",
    "tbl_fact_solicitudes",
]

@st.cache_resource(show_spinner=False)
def get_engine():
    """Crea el engine SQLAlchemy usando las credenciales de Streamlit."""
    creds = st.secrets["db_credentials"]
    uri = (
        f"mysql+pymysql://{creds['DB_USER']}:{creds['DB_PASS']}"
        f"@{creds['DB_HOST']}/{creds['DB_NAME']}"
    )
    # ELIMINAMOS: st.write("🔧 URI generada:", uri)

    engine = create_engine(uri)

    # ELIMINAMOS: Bloque de debug de verificación de base
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1;").fetchone()
    except Exception as e:
        # Dejamos un error discreto para que el desarrollador lo vea
        st.error(f"❌ Error crítico al conectar la base de datos: {str(e)}", icon="⚠️")

    return engine

@st.cache_resource(show_spinner=False)
def get_sql_database() -> SQLDatabase:
    """Envuelve el engine en un SQLDatabase de LangChain, con manejo de case sensitivity."""
    engine = get_engine()
    db = SQLDatabase(
        engine, 
        include_tables=ALLOWED_TABLES,
        # SOLUCIÓN CRÍTICA: Forzar la base de datos a manejar nombres de tabla en minúsculas
        # para evitar el conflicto de Linux/MariaDB (TBL_DIM_UBICACION vs tbl_dim_ubicacion).
        schema=None,
        view_support=True,
    )
    return db


def load_schema_text() -> str:
    """Lee el schema.txt desde la raíz del proyecto."""
    schema_path = pathlib.Path("schema.txt")
    if not schema_path.exists():
        raise FileNotFoundError(
            f"No se encontró schema.txt en {schema_path.resolve()}. "
            "Crea el archivo con la definición de las vistas."
        )
    return schema_path.read_text(encoding="utf-8")
