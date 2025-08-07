import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("turnos.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS horas (
            ID TEXT,
            Turno_Contrato TEXT,
            Horas_Acumuladas REAL,
            PRIMARY KEY (ID, Turno_Contrato)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS asignaciones (
            Fecha TEXT,
            Unidad TEXT,
            Turno TEXT,
            ID_Enfermera TEXT,
            Jornada TEXT,
            Horas_Acumuladas REAL
        )
    ''')
    conn.commit()
    conn.close()

def cargar_horas():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM horas", conn)
    conn.close()
    return df

def guardar_horas(df):
    conn = sqlite3.connect(DB_PATH)
    df.to_sql("horas", conn, if_exists="replace", index=False)
    conn.close()

def guardar_asignaciones(df):
    conn = sqlite3.connect(DB_PATH)
    df.to_sql("asignaciones", conn, if_exists="append", index=False)
    conn.close()

def cargar_asignaciones():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM asignaciones", conn)
    conn.close()
    return df

def reset_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS horas")
    c.execute("DROP TABLE IF EXISTS asignaciones")
    conn.commit()
    conn.close()
    init_db()
