import streamlit as st
import pandas as pd
import ast
from datetime import datetime, timedelta
from io import BytesIO
from db_manager import guardar_asignaciones, guardar_resumen_mensual

def ejecutar_asignador():
    st.set_page_config(page_title="Asignador de Turnos de Enfermería – Criterios SERMAS", layout="wide")
    st.markdown("""
    ### Instrucciones
    1. **Suba la plantilla de personal** (`.xlsx`) con las columnas:
       - `ID` (código de empleado)
       - `Unidad_Asignada`
       - `Jornada` (`Completa`/`Parcial`)
       - `Turno_Contrato` (`Mañana`, `Tarde` o `Noche`)
       - `Fechas_No_Disponibilidad` (lista `YYYY-MM-DD` separadas por comas)
    2. **Suba la demanda de turnos** (`.xlsx`) con las columnas:
       - `Fecha`, `Unidad`, `Turno` (`Mañana`/`Tarde`/`Noche`), `Personal_Requerido`
    3. Pulse **Asignar turnos**.
    """)

    SHIFT_HOURS = {"Mañana": 7.5, "Tarde": 7.5, "Noche": 10}
    BASE_MAX_HOURS = {"Mañana": 1642.5, "Tarde": 1642.5, "Noche": 1470}
    BASE_MAX_JORNADAS = {"Mañana": 219, "Tarde": 219, "Noche": 147}

    st.sidebar.header("📂 Suba los archivos de entrada")
    file_staff = st.sidebar.file_uploader("Plantilla de personal (.xlsx)", type=["xlsx"])
    file_demand = st.sidebar.file_uploader("Demanda de turnos (.xlsx)", type=["xlsx"])

    if file_staff and file_demand:
        staff = pd.read_excel(file_staff)
        demand = pd.read_excel(file_demand)

        staff.columns = staff.columns.str.strip()
        demand.columns = demand.columns.str.strip()

        def parse_dates(cell):
            if pd.isna(cell):
                return []
            try:
                return [d.strip() for d in ast.literal_eval(str(cell))]
            except Exception:
                return [d.strip() for d in str(cell).split(',')]

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
        st.subheader("📆 Demanda de turnos")
        st.dataframe(demand)

        st.sidebar.header("⚙️ Ejecutar asignación")
        if st.sidebar.button("🚀 Asignar turnos"):
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
            st.success("✅ Asignación completada")
            st.subheader("📋 Planilla generada")
            st.dataframe(df_assign)

            if not df_assign.empty:
                guardar_asignaciones(df_assign)

            if not df_assign.empty:
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
                    "Unidad": "Unidad Asignada",
                    "Turno": "Turno_Contrato",
                    "Fecha": "Jornadas Asignadas",
                    "Horas_Acumuladas": "Horas Asignadas"
                })

                st.subheader("📊 Resumen mensual por profesional")
                st.dataframe(resumen_mensual)

                
                guardar_resumen_mensual(resumen_mensual)
st.download_button(
                    label="⬇️ Descargar resumen mensual",
                    data=to_excel_bytes(resumen_mensual),
                    file_name="Resumen_Mensual_Profesional.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )


            def to_excel_bytes(df):
                output = BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False)
                return output.getvalue()

            st.download_button(
                label="⬇️ Descargar planilla (Excel)",
                data=to_excel_bytes(df_assign),
                file_name="Planilla_Asignada.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            if uncovered:
                df_uncov = pd.DataFrame(uncovered)
                st.subheader("⚠️ Turnos sin cubrir")
                st.dataframe(df_uncov)
                st.download_button(
                    label="⬇️ Descargar turnos sin cubrir",
                    data=to_excel_bytes(df_uncov),
                    file_name="Turnos_Sin_Cubrir.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.info("🔄 Por favor, suba los dos archivos (personal y demanda) para comenzar.")

