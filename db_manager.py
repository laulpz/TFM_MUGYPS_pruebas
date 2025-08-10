import sqlite3
import pandas as pd
import gdown
import shutil
from pathlib import Path

DB_PATH = Path("turnos.db")

# === Sincronización con Google Drive ===
def descargar_bd_desde_drive(file_id):
    url = f"https://drive.google.com/uc?id={file_id}"
    output = str(DB_PATH)
    try:
        gdown.download(url, output, quiet=False)
        print("📥 Base de datos descargada desde Google Drive")
    except Exception as e:
        print("❌ No se pudo descargar la base de datos:", e)

def subir_bd_a_drive(file_id):
    print("🔁 Subida automática a Google Drive aún no implementada directamente. Usa el archivo generado y súbelo manualmente.")
    # Implementar subida con PyDrive si se requiere autenticación completa

# === Funciones de gestión local ===
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS resumen_mensual (
            ID TEXT,
            Unidad TEXT,
            Turno TEXT,
            Jornada TEXT,
            Año INTEGER,
            Mes INTEGER,
            Jornadas_Asignadas INTEGER,
            Horas_Asignadas REAL
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

def guardar_resumen_mensual(df):
    conn = sqlite3.connect(DB_PATH)
    df.to_sql("resumen_mensual", conn, if_exists="append", index=False)
    conn.close()

def reset_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS horas")
    c.execute("DROP TABLE IF EXISTS asignaciones")
    c.execute("DROP TABLE IF EXISTS resumen_mensual")
    conn.commit()
    conn.close()
    init_db()
