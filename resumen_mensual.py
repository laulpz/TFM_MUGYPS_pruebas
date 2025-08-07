import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from pathlib import Path

DB_PATH = Path("turnos.db")

def cargar_resumen_mensual():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM resumen_mensual", conn)
    conn.close()
    return df

def to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Resumen")
    return output.getvalue()

st.set_page_config(page_title="Resumen Mensual – SERMAS", layout="wide")
st.title("📊 Visualizador de Resumen Mensual por Profesional")

df = cargar_resumen_mensual()

if df.empty:
    st.warning("⚠️ No hay datos registrados en la tabla resumen_mensual.")
    st.stop()

# Conversión de tipos
df["Año"] = df["Año"].astype(int)
df["Mes"] = df["Mes"].astype(int)

# Filtros
st.sidebar.header("🔍 Filtros")

years = sorted(df["Año"].unique())
months = sorted(df["Mes"].unique())
unidades = df["Unidad"].unique().tolist()
turnos = df["Turno"].unique().tolist()
jornadas = df["Jornada"].unique().tolist()

año_sel = st.sidebar.multiselect("Año", years, default=years)
mes_sel = st.sidebar.multiselect("Mes", months, default=months)
unidad_sel = st.sidebar.multiselect("Unidad", unidades, default=unidades)
turno_sel = st.sidebar.multiselect("Turno", turnos, default=turnos)
jornada_sel = st.sidebar.multiselect("Jornada", jornadas, default=jornadas)

# Aplicar filtros
df_filtrado = df[
    (df["Año"].isin(año_sel)) &
    (df["Mes"].isin(mes_sel)) &
    (df["Unidad"].isin(unidad_sel)) &
    (df["Turno"].isin(turno_sel)) &
    (df["Jornada"].isin(jornada_sel))
]

st.markdown("### 📋 Datos filtrados")
st.dataframe(df_filtrado, use_container_width=True)

st.download_button(
    label="⬇️ Descargar resumen filtrado en Excel",
    data=to_excel_bytes(df_filtrado),
    file_name="Resumen_Mensual_Filtrado.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
