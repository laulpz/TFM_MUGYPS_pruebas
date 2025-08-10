import streamlit as st
from generador_demanda import generar_demanda_interactiva

st.set_page_config(page_title="Generador de Demanda", layout="wide")
st.title("🗓️ Generador de Demanda de Turnos")
generar_demanda_interactiva()
