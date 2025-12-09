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
    # Usamos .get para manejar si db_credentials no existe
    creds = st.secrets.get("db_credentials", {}) 
    uri = (
        f"mysql+pymysql://{creds.get('DB_USER')}:{creds.get('DB_PASS')}"
        f"@{creds.get('DB_HOST')}/{creds.get('DB_NAME')}"
    )
    
    engine = create_engine(uri)
    
    # Se eliminan los bloques de st.write y verificación (SELECT 1;)
    
    return engine

@st.cache_resource(show_spinner=False)
def get_sql_database() -> SQLDatabase:
    """Envuelve el engine en un SQLDatabase de LangChain, con manejo de case sensitivity."""
    engine = get_engine()
    db = SQLDatabase(
        engine, 
        include_tables=ALLOWED_TABLES,
        # Fija el problema de la sensibilidad a mayúsculas/minúsculas en Linux
        schema=None,
        view_support=True,
    )
    return db


def load_schema_text() -> str:
    """Lee el schema.txt desde la raíz del proyecto."""
    schema_path = pathlib.Path("schema.txt")
    if not schema_path.exists():
        return "" 
    return schema_path.read_text(encoding="utf-8")

