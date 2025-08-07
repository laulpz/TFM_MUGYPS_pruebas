import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from pathlib import Path
import matplotlib.pyplot as plt
from db_manager import descargar_bd_desde_drive

st.set_page_config(page_title="Resumen Mensual", layout="wide")
st.title("📊 Visualizador de Resumen Mensual de Asignaciones")

FILE_ID = "1zqAyIB1BLfCc2uH1v29r-clARHoh2o_s"
descargar_bd_desde_drive(FILE_ID)

try:
    conn = sqlite3.connect("turnos.db")
    query = "SELECT * FROM resumen_mensual"
    df = pd.read_sql_query(query, conn)
except Exception as e:
    st.error(f"Error al leer la base de datos: {e}")
    st.stop()

if df.empty:
    st.warning("No hay datos registrados en la tabla resumen_mensual.")
    st.stop()

st.sidebar.header("Filtros")
años = sorted(df["Año"].unique(), reverse=True)
año = st.sidebar.selectbox("Año", años)

meses = sorted(df[df["Año"] == año]["Mes"].unique())
mes = st.sidebar.selectbox("Mes", meses)

unidades = df["Unidad"].unique().tolist()
unidad = st.sidebar.selectbox("Unidad", ["Todas"] + unidades)

turnos = df["Turno"].unique().tolist()
turno = st.sidebar.selectbox("Turno", ["Todos"] + turnos)

jornadas = df["Jornada"].unique().tolist()
jornada = st.sidebar.selectbox("Tipo de Jornada", ["Todas"] + jornadas)

df = df[(df["Año"] == año) & (df["Mes"] == mes)]

if unidad != "Todas":
    df = df[df["Unidad"] == unidad]

if turno != "Todos":
    df = df[df["Turno"] == turno]

if jornada != "Todas":
    df = df[df["Jornada"] == jornada]

st.subheader("📄 Resumen filtrado")
st.dataframe(df)

def to_excel_bytes(df):
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

st.download_button(
    label="⬇️ Descargar resumen filtrado",
    data=to_excel_bytes(df),
    file_name="Resumen_Mensual_Filtrado.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# ✅ Totales por profesional
st.subheader("📊 Totales por profesional")
totales = df.groupby("ID").agg({
    "Horas_Asignadas": "sum",
    "Jornadas_Asignadas": "sum"
}).reset_index()
st.dataframe(totales)

# ✅ Gráficos de distribución
st.subheader("📈 Distribución por unidad")
unidad_agg = df.groupby("Unidad")["Horas_Asignadas"].sum()
fig1, ax1 = plt.subplots()
unidad_agg.plot(kind="bar", ax=ax1)
ax1.set_ylabel("Horas asignadas")
ax1.set_title("Horas por unidad")
st.pyplot(fig1)

st.subheader("📊 Distribución por turno")
turno_agg = df.groupby("Turno")["Horas_Asignadas"].sum()
fig2, ax2 = plt.subplots()
turno_agg.plot(kind="bar", ax=ax2, color="orange")
ax2.set_ylabel("Horas asignadas")
ax2.set_title("Horas por turno")
st.pyplot(fig2)

# ✅ Vista individual por profesional
st.subheader("👤 Detalle por profesional")
profesional = st.selectbox("Seleccione un ID", df["ID"].unique())
df_prof = df[df["ID"] == profesional]
st.dataframe(df_prof)

# Evolución mensual del profesional
evolucion = df_prof.groupby(["Año", "Mes"])["Horas_Asignadas"].sum().reset_index()
evolucion["Periodo"] = evolucion["Mes"].astype(str) + "/" + evolucion["Año"].astype(str)
evolucion = evolucion.sort_values(["Año", "Mes"])

st.line_chart(evolucion.set_index("Periodo")["Horas_Asignadas"])
