
def verificar_limites(id_enfermera, horas_nuevas, turno_contrato):
    """Usa datos reales de la base de datos"""
    from db_manager import obtener_horas_acumuladas
    df = obtener_horas_acumuladas()
    horas_actuales = df.loc[df["ID"] == id_enfermera, "Horas_Acumuladas"].sum()
    limite = 1470 if turno_contrato == "Noche" else 1642.5
    return (horas_actuales + horas_nuevas) <= limite

def verificar_disponibilidad(id_enfermera, fecha):
    """Verifica disponibilidad considerando asignaciones existentes"""
    from db_manager import obtener_horas_historicas
    
    df = obtener_horas_historicas(id_enfermera)
    if df.empty:
        return True
        
    # Verificar descanso de 12h
    ultima_fecha = pd.to_datetime(df['Fecha'].max())
    return (pd.to_datetime(fecha) - ultima_fecha) >= timedelta(hours=12)
