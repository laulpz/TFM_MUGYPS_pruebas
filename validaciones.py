def verificar_limites_anuales(id_enfermera, horas_adicionales, turno_contrato):
    """Verifica que no se excedan los límites anuales"""
    from db_manager import obtener_horas_historicas
    
    df = obtener_horas_historicas(id_enfermera)
    horas_actuales = df['Horas'].sum() if not df.empty else 0
    
    if turno_contrato == "Noche":
        return horas_actuales + horas_adicionales <= 1470
    else:
        return horas_actuales + horas_adicionales <= 1642.5

def verificar_disponibilidad(id_enfermera, fecha):
    """Verifica disponibilidad considerando asignaciones existentes"""
    from db_manager import obtener_horas_historicas
    
    df = obtener_horas_historicas(id_enfermera)
    if df.empty:
        return True
        
    # Verificar descanso de 12h
    ultima_fecha = pd.to_datetime(df['Fecha'].max())
    return (pd.to_datetime(fecha) - ultima_fecha) >= timedelta(hours=12)
