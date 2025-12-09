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
    # Se elimina la URI y el debug.
    
    engine = create_engine(uri)

    # Eliminamos el bloque problemático de verificación.
    # Si la conexión falla, el error será capturado por el sql_executor_node.
    
    return engine

@st.cache_resource(show_spinner=False)
def get_sql_database() -> SQLDatabase:
    """Envuelve el engine en un SQLDatabase de LangChain, con manejo de case sensitivity."""
    engine = get_engine()
    db = SQLDatabase(
        engine, 
        include_tables=ALLOWED_TABLES,
        # Solución para el problema de case sensitivity de Linux, crucial para que funcione en Streamlit Cloud.
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
