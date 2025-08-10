
# 🩺 Planificador de Turnos de Enfermería – SERMAS

Aplicación web interactiva para asignar turnos de enfermería en hospitales públicos del Servicio Madrileño de Salud (SERMAS). Permite automatizar la planificación teniendo en cuenta criterios reales como jornadas, turnos contratados, fechas de no disponibilidad y límites legales de horas.

## 🚀 Funcionalidades

- Introducción **manual y simple** de la demanda semanal por turnos.
- Selección de **rango de fechas** personalizado (planificación mensual, trimestral, etc.).
- **Carga de plantilla de personal** en formato Excel.
- Asignación automática:
  - Turnos respetando contrato, unidad, jornada y ausencias.
  - Límite de **8 jornadas consecutivas**.
  - Control del máximo de horas anuales (1667,5 h diurno, 1490 h nocturno).
- **Persistencia de datos** en base de datos SQLite local:
  - Registro de asignaciones anteriores.
  - Acumulación de horas por enfermera.
- Descarga de:
  - 📋 Planilla asignada.
  - ⚠️ Turnos sin cubrir.
  - 📊 Resumen mensual de horas.

## 🧾 Estructura esperada del archivo de plantilla de personal

| ID     | Unidad_Asignada | Jornada   | Turno_Contrato | Fechas_No_Disponibilidad     |
|--------|------------------|-----------|----------------|------------------------------|
| E001   | Medicina Interna | Completa  | Mañana         | 2025-01-05, 2025-01-06       |
| E002   | UCI              | Parcial   | Noche          |                              |

- `Fechas_No_Disponibilidad`: fechas separadas por coma (puede dejarse vacío).
- `Turno_Contrato`: solo uno permitido por persona.

## 🖥️ Cómo ejecutar

```bash
streamlit run app.py
```

> ⚠️ Requiere `db_manager.py` en el mismo directorio.

## 📂 Archivos clave

- `app.py` → interfaz y lógica principal.
- `db_manager.py` → conexión y gestión de SQLite.
- `planilla.xlsx` → plantilla de personal de entrada.
- `asignaciones.db` → base de datos local con horas y asignaciones.

## 📌 Ejemplo de uso

1. Introduce la demanda semanal para cada turno.
2. Selecciona el rango de fechas a planificar.
3. Sube el archivo de personal.
4. Ejecuta la asignación y descarga los archivos generados.

## 📃 Licencia

Este proyecto está protegido por derechos de autor. Su uso y distribución están restringidos salvo autorización de la autora.
