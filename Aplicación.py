import streamlit as st
import pandas as pd
from datetime import datetime
import os
# Configuración de la interfaz móvil
st.set_page_config(page_title="Control de Eficiencia", page_icon=" ")
# Archivo local para el historial
DATA_FILE = "historial_produccion.csv"
def cargar_datos():
 if os.path.exists(DATA_FILE):
 return pd.read_csv(DATA_FILE)
 return pd.DataFrame(columns=["Fecha", "Meta", "Logrado", "Eficiencia (%)"])
def guardar_datos(meta, logrado, ef):
 df = cargar_datos()
 nuevo = pd.DataFrame([{
 "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
 "Meta": meta,
 "Logrado": logrado,
 "Eficiencia (%)": f"{ef:.2f}%"
 }])
 df = pd.concat([df, nuevo], ignore_index=True)
 df.to_csv(DATA_FILE, index=False)
# --- MENÚ LATERAL ---
st.sidebar.title("Navegación")
opcion = st.sidebar.radio("Ir a:", ["Calculadora", "Historial de Turnos", "Ayuda"])
if opcion == "Calculadora":
 st.header(" Nueva Entrada")
 with st.container():
 meta = st.number_input("Meta de Unidades", min_value=1, value=1000)
 logrado = st.number_input("Unidades Producidas", min_value=0, value=0)
 if st.button("Calcular y Guardar"):
 eficiencia = (logrado / meta) * 100
 st.metric("Eficiencia del Turno", f"{eficiencia:.2f}%")
 guardar_datos(meta, logrado, eficiencia)
 st.success(" ¡Registro guardado exitosamente!")
elif opcion == "Historial de Turnos":
 st.header(" Historial Guardado")
 historial = cargar_datos()
 if not historial.empty:
 st.dataframe(historial, use_container_width=True)
 if st.button("Limpiar todo el historial"):
 if os.path.exists(DATA_FILE):
 os.remove(DATA_FILE)
 st.rerun()
 else:
 st.info("Aún no hay datos registrados.")
elif opcion == "Ayuda":
 st.header(" Instrucciones")
 st.write("1. Usa la **Calculadora** para registrar cada turno.")
 st.write("2. Al presionar guardar, los datos se almacenan automáticamente.")
 st.write("3. En **Historial**, puedes ver tu rendimiento acumulado.")