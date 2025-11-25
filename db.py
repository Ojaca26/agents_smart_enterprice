# db.py
from __future__ import annotations
from typing import List

import streamlit as st
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
import pathlib

# Vistas que el agente puede usar
ALLOWED_TABLES: List[str] = [
    "replica_VIEW_Dim_Concepto",
    "replica_VIEW_Dim_Empresa",
    "replica_VIEW_Dim_Ubicacion",
    "replica_VIEW_Fact_Costos",
    "replica_VIEW_Fact_Ingresos",
    "replica_VIEW_Fact_Solicitudes",
]


@st.cache_resource(show_spinner=False)
def get_engine():
    """Crea el engine SQLAlchemy usando las credenciales de Streamlit."""
    creds = st.secrets["db_credentials"]
    uri = (
        f"mysql+pymysql://{creds['DB_USER']}:{creds['DB_PASS']}"
        f"@{creds['DB_HOST']}/{creds['DB_NAME']}"
    )
    engine = create_engine(uri)
    return engine


@st.cache_resource(show_spinner=False)
def get_sql_database() -> SQLDatabase:
    """Envuelve el engine en un SQLDatabase de LangChain."""
    engine = get_engine()
    db = SQLDatabase(engine, include_tables=ALLOWED_TABLES)
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
