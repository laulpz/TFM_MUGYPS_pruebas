import sqlite3
import pandas as pd
import gdown
import shutil
from pathlib import Path
from datetime import datetime, timedelta

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
        CREATE TABLE IF NOT EXISTS asignaciones (
            Fecha TEXT,
            Unidad TEXT,
            Turno TEXT,
            ID_Enfermera TEXT,
            Jornada TEXT,
            Horas REAL
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

def guardar_asignaciones(df):
    required_columns = ["Fecha", "Unidad", "Turno", "ID_Enfermera", "Jornada", "Horas"]
    conn = sqlite3.connect(DB_PATH)
    try:
        # Validación de columnas
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise ValueError(f"Faltan columnas: {missing}")
        
        # Insertar evitando duplicados
        cursor = conn.cursor()
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT OR IGNORE INTO asignaciones 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (row["Fecha"], row["Unidad"], row["Turno"], 
                 row["ID_Enfermera"], row["Jornada"], row["Horas"]))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
        

def cargar_asignaciones():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM asignaciones", conn)
    conn.close()
    return df

def guardar_resumen_mensual(df):
    conn = sqlite3.connect(DB_PATH)
    try:
        # 1. Cargar datos existentes
        existing = pd.read_sql_query("SELECT * FROM resumen_mensual", conn)
        
        # 2. Combinar con nuevos datos (sumando horas y jornadas)
        if not existing.empty:
            merged = pd.concat([existing, df]).groupby(
                ["ID", "Unidad", "Turno", "Jornada", "Año", "Mes"]
            ).agg({
                "Horas_Asignadas": "sum",
                "Jornadas_Asignadas": "sum"
            }).reset_index()
        else:
            merged = df
            
        # 3. Reemplazar completamente la tabla
        merged.to_sql("resumen_mensual", conn, if_exists="replace", index=False)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
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

def obtener_horas_acumuladas():
    """Obtiene el total de horas trabajadas por cada enfermera"""
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT 
            ID_Enfermera as ID, 
            SUM(Horas) as Horas_Acumuladas
        FROM asignaciones 
        GROUP BY ID_Enfermera
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df  # Ejemplo: DataFrame con columnas [ID, Horas_Acumuladas]

def obtener_horas_historicas(id_enfermera=None):
    """Obtiene todas las asignaciones históricas"""
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM asignaciones"
    if id_enfermera:
        query += f" WHERE ID_Enfermera = '{id_enfermera}'"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# Nueva función para obtener acumulados
def obtener_acumulados_anuales():
    conn = sqlite3.connect(DB_PATH)
    query = '''
        SELECT 
            ID_Enfermera,
            strftime('%Y', Fecha) as Año,
            SUM(Horas) as Horas_Acumuladas,
            COUNT(*) as Jornadas_Acumuladas
        FROM asignaciones
        GROUP BY ID_Enfermera, strftime('%Y', Fecha)
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df
