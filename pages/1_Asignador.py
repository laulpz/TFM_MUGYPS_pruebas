import streamlit as st
import pandas as pd
import ast
from datetime import datetime, timedelta, date
from io import BytesIO
from db_manager import (
    init_db, guardar_asignaciones, guardar_resumen_mensual,
    descargar_bd_desde_drive, subir_bd_a_drive, reset_db
)

#Títulos y descripción
st.set_page_config(page_title="Asignador", layout="wide")
st.title("📋 Asignador de Turnos (Excel o Generador Manual)")
st.markdown("""añadir descripción aqui """)

#Carga BBDD, debería cargarse desde estado anterior
FILE_ID = "1zqAyIB1BLfCc2uH1v29r-clARHoh2o_s"
descargar_bd_desde_drive(FILE_ID)
init_db()

#31/07: Comprobar estado para conservar el de la sesión anterior.
if "asignacion_completada" not in st.session_state:
    st.session_state.update({
        "asignacion_completada": False,
        "df_assign": None,
        "file_staff": None,
        "df_uncov": None
    })

#No sé si realmente es necesario
if "file_staff" not in st.session_state:
    st.session_state["file_staff"] = None

#Inicialización de variables
SHIFT_HOURS = {"Mañana": 7.5, "Tarde": 7.5, "Noche": 10}
BASE_MAX_HOURS = {"Mañana": 1642.5, "Tarde": 1642.5, "Noche": 1470}
BASE_MAX_JORNADAS = {"Mañana": 219, "Tarde": 219, "Noche": 147}
dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
turnos = ["Mañana", "Tarde", "Noche"]

#Subida plantilla de personal. 10/08 añadido if para st.session_state
st.sidebar.header("1️⃣📂 Suba la plantilla de personal")
file_staff = st.sidebar.file_uploader("El archivo debe contener las siguientes columnas: Plantilla de personal (.xlsx)", type=["xlsx"])
if file_staff:
    st.session_state["file_staff"] = file_staff
    
#Configurar la demanda de turnos
metodo = st.sidebar.selectbox("2️⃣📈 Método para ingresar demanda:", ["Generar manualmente","Desde Excel"])
demand = None
if metodo == "Desde Excel":
    file_demand = st.sidebar.file_uploader("Demanda de turnos (.xlsx)", type=["xlsx"])
    if file_demand:
        demand = pd.read_excel(file_demand)
        demand.columns = demand.columns.str.strip()
        st.subheader("📆 Demanda desde archivo")
        st.dataframe(demand)
elif metodo == "Generar manualmente":
    st.subheader("⚙️ Generador de Demanda Manual")
    unidad = st.selectbox("Unidad Hospitalaria", ["Medicina Interna", "UCI", "Urgencias", "Oncología", "Quirófano"])
    col1, col2 = st.columns(2)
    fecha_inicio = col1.date_input("Fecha de inicio", value=date(2025, 1, 1))
    fecha_fin = col2.date_input("Fecha de fin", value=date(2025, 1, 31))
    fechas = [fecha_inicio + timedelta(days=i) for i in range((fecha_fin - fecha_inicio).days + 1)]
    
    #Aviso rango de fechas erróneo
    if fecha_fin <= fecha_inicio:
        st.warning("⚠️ La fecha fin debe ser posterior a la fecha inicio.")
        st.stop()
        
    demanda_por_dia = {}
    for dia in dias_semana:
        st.markdown(f"**{dia}**")
        cols = st.columns(3)
        demanda_por_dia[dia] = {}
        valor_default = 8 if dia in dias_semana[:5] else 4
        for i, turno in enumerate(turnos):
            demanda_por_dia[dia][turno] = cols[i].number_input(
                label=f"{turno}", min_value=0, max_value=20, value=valor_default, key=f"{dia}_{turno}"
             )
    demanda = []
    for fecha in fechas:
        dia_cast = dias_semana[fecha.weekday()]
        for turno in turnos:
             demanda.append({
                 "Fecha": fecha.isoformat(),
                 "Unidad": unidad,
                 "Turno": turno,
                 "Personal_Requerido": demanda_por_dia[dia_cast][turno]
             })
    demand = pd.DataFrame(demanda)

#Ejecutar asignación
if file_staff is not None and st.button("🚀 Ejecutar asignación"):
    staff = pd.read_excel(file_staff)
    staff.columns = staff.columns.str.strip()

    def parse_dates(cell):
        if pd.isna(cell): return []
        try: return [d.strip() for d in ast.literal_eval(str(cell))]
        except: return [d.strip() for d in str(cell).split(',')]

    staff["Fechas_No_Disponibilidad"] = staff["Fechas_No_Disponibilidad"].apply(parse_dates)
    
    #Para jornadas parciales definir 80%
    staff_max_hours = {
        row.ID: BASE_MAX_HOURS[row.Turno_Contrato] * (0.8 if row.Jornada == "Parcial" else 1)
        for _, row in staff.iterrows()
    }
    staff_max_jornadas = {
        row.ID: BASE_MAX_JORNADAS[row.Turno_Contrato] * (0.8 if row.Jornada == "Parcial" else 1)
        for _, row in staff.iterrows()
    }

    st.subheader("👩‍⚕️ Personal cargado")
    st.dataframe(staff)

    #Aquí está obviando las horas anteriores. En código 31/07 algo así: 
    #df_prev = cargar_horas()
    #staff_hours = dict(zip(df_prev["ID"], df_prev["Horas_Acumuladas"])) if not df_prev.empty else {row.ID: 0 for _, row in staff.iterrows()}
    #staff_jornadas = dict.fromkeys(staff["ID"], 0)
    staff_hours = {row.ID: 0 for _, row in staff.iterrows()}
    staff_dates = {row.ID: [] for _, row in staff.iterrows()}
    assignments, uncovered = [], []

    if demand is None:
        st.warning("⚠️ No se ha cargado ninguna demanda de turnos.")
        st.stop()

    if not all(col in demand.columns for col in ["Fecha", "Unidad", "Turno", "Personal_Requerido"]):
        st.error("❌ La demanda debe contener las columnas: Fecha, Unidad, Turno, Personal_Requerido")
        st.stop()

    demand_sorted = demand.sort_values(by="Fecha")
    #st.subheader("📆 Demanda generada")
    #st.dataframe(demand)

    for _, dem in demand_sorted.iterrows():
        fecha = dem["Fecha"]
        unidad = dem["Unidad"]
        turno = dem["Turno"]
        req = dem["Personal_Requerido"]
        assigned_count = 0

        cands = staff[
            (staff["Unidad_Asignada"] == unidad) &
            (staff["Turno_Contrato"] == turno) &
            (~staff["Fechas_No_Disponibilidad"].apply(lambda lst: fecha in lst))
        ].copy()

        if not cands.empty:
            cands["Horas_Asignadas"] = cands["ID"].map(staff_hours)
            cands["Jornadas_Asignadas"] = cands["ID"].map(lambda x: len(staff_dates[x]))

            def jornada_ok(row):
                return len(staff_dates[row.ID]) < staff_max_jornadas[row.ID]
            
            def consecutive_ok(nurse_id):
                fechas_asignadas = staff_dates[nurse_id]
                if not fechas_asignadas: return True
                # Convertir todas las fechas a datetime.date y ordenarlas
                fechas_datetime = sorted([datetime.strptime(f, "%Y-%m-%d").date() for f in fechas_asignadas])
                fecha_actual = datetime.strptime(fecha, "%Y-%m-%d").date()
                # Verificar si la fecha_actual sería el 8vo día consecutivo
                consecutivos = 1
                for i in range(1, 8):
                    fecha_anterior = fecha_actual - timedelta(days=i)
                    if fecha_anterior in fechas_datetime:
                        consecutivos += 1
                    else: break
                return consecutivos < 8

            def descanso_12h_ok(nurse_id):
                fechas_previas = staff_dates[nurse_id]
                if not fechas_previas:
                    return True
                fecha_actual = datetime.strptime(fecha, "%Y-%m-%d")
                for fecha_ant in fechas_previas:
                    fecha_prev = datetime.strptime(fecha_ant, "%Y-%m-%d")
                    if abs((fecha_actual - fecha_prev).total_seconds()) < 12 * 3600:
                        return False
                return True

            def hours_ok(row):
                return staff_hours[row.ID] + SHIFT_HOURS[turno] <= staff_max_hours[row.ID]

            cands = cands[cands.apply(jornada_ok, axis=1)]
            cands = cands[cands["ID"].apply(consecutive_ok)]
            cands = cands[cands["ID"].apply(descanso_12h_ok)]
            cands = cands[cands.apply(hours_ok, axis=1)]
            cands = cands.sort_values(by="Horas_Asignadas")

        if not cands.empty:
            for _, cand in cands.iterrows():
                if assigned_count >= req: break
                assignments.append({
                    "Fecha": fecha,
                    "Unidad": unidad,
                    "Turno": turno,
                    "ID_Enfermera": cand.ID,
                    "Jornada": cand.Jornada,
                    "Horas": SHIFT_HOURS[turno], # staff_hours[cand.ID] + SHIFT_HOURS[turno]
                })
                staff_hours[cand.ID] += SHIFT_HOURS[turno]
                staff_dates[cand.ID].append(fecha)
                assigned_count += 1
        if assigned_count < req:
            uncovered.append({"Fecha": fecha, "Unidad": unidad, "Turno": turno, "Faltan": req - assigned_count})

    df_assign = pd.DataFrame(assignments)
 
    df_uncov = pd.DataFrame(uncovered) if uncovered else None 

    st.session_state.update({
        "asignacion_completada": True,
        "df_assign": df_assign,
        "df_uncov": pd.DataFrame(uncovered) if uncovered else None,
        "uncovered": uncovered  # Nueva línea
    })

    df_assign["Fecha"] = pd.to_datetime(df_assign["Fecha"])
    df_assign["Año"] = df_assign["Fecha"].dt.year
    df_assign["Mes"] = df_assign["Fecha"].dt.month

    st.session_state["resumen_mensual"] = (df_assign.assign(
        Año=df_assign["Fecha"].dt.year,
        Mes=df_assign["Fecha"].dt.month
).groupby(["ID_Enfermera", "Unidad", "Turno", "Jornada", "Año", "Mes"])
 .agg(Horas_Asignadas=("Horas", "sum"),
      Jornadas_Asignadas=("Fecha", "count"))
 .reset_index()
 .rename(columns={"ID_Enfermera": "ID"}))

if st.session_state["asignacion_completada"]:
    df_assign = st.session_state["df_assign"].drop(columns=["Confirmado"], errors="ignore")
    uncovered = st.session_state.get("uncovered", [])
    st.success("✅ Asignación completada")
    st.dataframe(df_assign)
    
    if uncovered:
          df_uncov = pd.DataFrame(uncovered)
          st.subheader("⚠️ Turnos sin cubrir")
          st.dataframe(pd.DataFrame(uncovered))
          st.download_button("⬇️ Descargar turnos sin cubrir", data=to_excel_bytes(df_uncov), file_name="Turnos_Sin_Cubrir.xlsx")

    st.markdown("### ✅ Confirmación de asignación")
    aprobacion = st.radio("¿Deseas aprobar esta asignación?", ["Pendiente", "Aprobar", "Rehacer"], index=0)
    
    if aprobacion == "Aprobar":
        # Debug: Mostrar estructura del DataFrame
        st.write("Debug - df_assign columns:", st.session_state["df_assign"].columns)
        st.write("Debug - df_assign dtypes:", st.session_state["df_assign"].dtypes)
    
        # Verificar columnas requeridas (asegurando que los nombres coincidan exactamente)
        required_cols = ["Fecha", "Unidad", "Turno", "ID_Enfermera", "Jornada", "Horas"]
        if not all(col in st.session_state["df_assign"].columns for col in required_cols):
            missing_cols = [col for col in required_cols if col not in st.session_state["df_assign"].columns]
            st.error(f"❌ Faltan columnas requeridas: {missing_cols}")
            st.stop()

        # Crear DataFrame para guardar (asegurando mayúsculas correctas)
        df_to_save = st.session_state["df_assign"][["Fecha", "Unidad", "Turno", "ID_Enfermera", "Jornada", "Horas"]].copy()
        df_to_save["Fecha"] = pd.to_datetime(df_to_save["Fecha"]).dt.strftime("%Y-%m-%d")

    
        # Guardar
        try:
            st.write("Columnas en df_to_save:", df_to_save.columns.tolist())
            st.write("Primeras filas:", df_to_save.head())
            guardar_asignaciones(df_to_save)
            guardar_resumen_mensual(st.session_state["resumen_mensual"])
            st.success("✅ Datos guardados correctamente")
            subir_bd_a_drive(FILE_ID)
            st.success("📥 Datos guardados en la base de datos correctamente.")
        except Exception as e:
            st.error(f"❌ Error al guardar: {str(e)}")

        if "resumen_mensual" not in st.session_state:
            st.error("No se encontró el resumen mensual")
            st.stop()

        #st.subheader("🧾 Resumen Asignación Mensual por profesional")

        def to_excel_bytes(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False)
            return output.getvalue()

        st.download_button("⬇️ Descargar planilla asignada", data=to_excel_bytes(st.session_state["df_assign"]), file_name="Planilla_Asignada.xlsx")
        st.download_button("⬇️ Descargar resumen mensual", data=to_excel_bytes(st.session_state["resumen_mensual"]), file_name="Resumen_Mensual_{datetime.now().strftime('%Y%m%d')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    elif aprobacion == "Rehacer":
        st.session_state["asignacion_completada"] = False
        st.rerun()
        #st.experimental_rerun()

    if st.button("🔄 Reiniciar aplicación"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Resetear base de datos"):
    reset_db()
    st.session_state.clear()
    st.sidebar.success("✅ Base de datos reiniciada correctamente.")
    #st.experimental_rerun() #VERSION 04/08: comprobar si es necesario, ahora me da error
    #for key in list(st.session_state.keys()): #VERSION 31/07. Está al final del todo. El mensaje de reinicio correcto desaparece rápido...
        #del st.session_state[key]
    st.rerun()
