import streamlit as st
import pandas as pd
import ast
from datetime import datetime, timedelta, date
from io import BytesIO
from db_manager import (
    init_db, guardar_asignaciones, guardar_resumen_mensual,
    descargar_bd_desde_drive, subir_bd_a_drive
)

st.set_page_config(page_title="Asignador", layout="wide")
st.title("📋 Asignador de Turnos (Excel o Generador Manual)")

FILE_ID = "1zqAyIB1BLfCc2uH1v29r-clARHoh2o_s"
descargar_bd_desde_drive(FILE_ID)
init_db()

SHIFT_HOURS = {"Mañana": 7.5, "Tarde": 7.5, "Noche": 10}
BASE_MAX_HOURS = {"Mañana": 1642.5, "Tarde": 1642.5, "Noche": 1470}
BASE_MAX_JORNADAS = {"Mañana": 219, "Tarde": 219, "Noche": 147}
dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
turnos = ["Mañana", "Tarde", "Noche"]

st.sidebar.header("📂 Suba la plantilla de personal")
file_staff = st.sidebar.file_uploader("Plantilla de personal (.xlsx)", type=["xlsx"])

metodo = st.sidebar.selectbox("📈 Método para ingresar demanda:", ["Desde Excel", "Generar manualmente"])

if file_staff:
    staff = pd.read_excel(file_staff)
    staff.columns = staff.columns.str.strip()

    def parse_dates(cell):
        if pd.isna(cell): return []
        try: return [d.strip() for d in ast.literal_eval(str(cell))]
        except: return [d.strip() for d in str(cell).split(',')]

    staff["Fechas_No_Disponibilidad"] = staff["Fechas_No_Disponibilidad"].apply(parse_dates)

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
        fecha_fin = col2.date_input("Fecha de fin", value=date(2025, 1, 7))

        demanda_por_dia = {}
        for dia in dias_semana:
            st.markdown(f"**{dia}**")
            cols = st.columns(3)
            demanda_por_dia[dia] = {}
            for i, turno in enumerate(turnos):
                demanda_por_dia[dia][turno] = cols[i].number_input(
                    label=f"{turno}", min_value=0, max_value=20, value=3, key=f"{dia}_{turno}"
                )

        if fecha_fin <= fecha_inicio:
            st.warning("⚠️ La fecha fin debe ser posterior a la fecha inicio.")
            st.stop()

        fechas = [fecha_inicio + timedelta(days=i) for i in range((fecha_fin - fecha_inicio).days + 1)]
        demanda = []
        for fecha in fechas:
            dia_cast = dias_semana[fecha.weekday()]
            for turno in turnos:
                demanda.append({
                    "Fecha": fecha.strftime("%Y-%m-%d"),
                    "Unidad": unidad,
                    "Turno": turno,
                    "Personal_Requerido": demanda_por_dia[dia_cast][turno]
                })
        demand = pd.DataFrame(demanda)
        st.subheader("📆 Demanda generada")
        st.dataframe(demand)

    if demand is not None and st.button("🚀 Ejecutar asignación"):
        staff_hours = {row.ID: 0 for _, row in staff.iterrows()}
        staff_dates = {row.ID: [] for _, row in staff.iterrows()}
        assignments, uncovered = [], []

        demand_sorted = demand.sort_values(by="Fecha")

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
                    fechas = staff_dates[nurse_id]
                    if not fechas:
                        return True
                    last_date = max(fechas)
                    if (datetime.strptime(fecha, "%Y-%m-%d") - datetime.strptime(last_date, "%Y-%m-%d")).days == 1:
                        consec = 1
                        check_date = datetime.strptime(last_date, "%Y-%m-%d")
                        while True:
                            check_date -= timedelta(days=1)
                            if check_date.strftime("%Y-%m-%d") in fechas:
                                consec += 1
                                if consec >= 8:
                                    return False
                            else:
                                break
                    return True

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
                    if assigned_count >= req:
                        break
                    assignments.append({
                        "Fecha": fecha,
                        "Unidad": unidad,
                        "Turno": turno,
                        "ID_Enfermera": cand.ID,
                        "Jornada": cand.Jornada,
                        "Horas_Acumuladas": SHIFT_HOURS[turno],
                        "Confirmado": 0
                    })
                    staff_hours[cand.ID] += SHIFT_HOURS[turno]
                    staff_dates[cand.ID].append(fecha)
                    assigned_count += 1

            if assigned_count < req:
                uncovered.append({"Fecha": fecha, "Unidad": unidad, "Turno": turno, "Faltan": req - assigned_count})

        df_assign = pd.DataFrame(assignments)
        df_assign = df_assign.drop(columns=["Confirmado"], errors="ignore")
        st.success("✅ Asignación completada")
        st.dataframe(df_assign)

        guardar_asignaciones(df_assign)

        df_assign["Fecha"] = pd.to_datetime(df_assign["Fecha"])
        df_assign["Año"] = df_assign["Fecha"].dt.year
        df_assign["Mes"] = df_assign["Fecha"].dt.month

        resumen_mensual = df_assign.groupby(
            ["ID_Enfermera", "Unidad", "Turno", "Jornada", "Año", "Mes"],
            as_index=False
        ).agg({
            "Horas_Acumuladas": "sum",
            "Fecha": "count"
        }).rename(columns={
            "ID_Enfermera": "ID",
            "Fecha": "Jornadas_Asignadas",
            "Horas_Acumuladas": "Horas_Asignadas"
        })

        guardar_resumen_mensual(resumen_mensual)
        subir_bd_a_drive(FILE_ID)

        st.subheader("📊 Resumen mensual")
        st.dataframe(resumen_mensual)

        def to_excel_bytes(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False)
            return output.getvalue()

        st.download_button("⬇️ Descargar planilla asignada", data=to_excel_bytes(df_assign), file_name="Planilla_Asignada.xlsx")
        st.download_button("⬇️ Descargar resumen mensual", data=to_excel_bytes(resumen_mensual), file_name="Resumen_Mensual.xlsx")

        if uncovered:
            df_uncov = pd.DataFrame(uncovered)
            st.subheader("⚠️ Turnos sin cubrir")
            st.dataframe(df_uncov)
            st.download_button("⬇️ Descargar turnos sin cubrir", data=to_excel_bytes(df_uncov), file_name="Turnos_Sin_Cubrir.xlsx")
