import streamlit as st
import pandas as pd
import plotly.express as px

# Configuración de la página (título y diseño)
st.set_page_config(page_title="Mi Calculadora de Presupuesto", layout="centered")

# Título principal
st.title("💰 Calculadora de Presupuesto Personal")
st.write("Ingresa tus datos para ver cómo se distribuye tu dinero y cuánto puedes ahorrar.")

st.markdown("---")

# --- SECCIÓN 1: INGRESOS (Barra lateral) ---
st.sidebar.header("1. Tus Ingresos")
salario = st.sidebar.number_input("Salario Mensual Neto ($)", min_value=0.0, value=1000.0, step=50.0)
otros_ingresos = st.sidebar.number_input("Otros Ingresos ($)", min_value=0.0, value=0.0, step=50.0)

total_ingresos = salario + otros_ingresos

# Mostrar el total de ingresos en la barra lateral
st.sidebar.markdown(f"### Total Ingresos: **${total_ingresos:,.2f}**")


# --- SECCIÓN 2: GASTOS (Cuerpo principal) ---
st.header("2. Tus Gastos Mensuales")

# Creamos dos columnas para que se vea más organizado
col1, col2 = st.columns(2)

with col1:
    alquiler = st.number_input("🏡 Alquiler / Hipoteca", min_value=0.0, value=300.0)
    comida = st.number_input("🛒 Supermercado / Comida", min_value=0.0, value=200.0)
    servicios = st.number_input("💡 Servicios (Luz, Agua, Internet)", min_value=0.0, value=50.0)

with col2:
    transporte = st.number_input("🚌 Transporte / Gasolina", min_value=0.0, value=50.0)
    ocio = st.number_input("🎉 Ocio y Entretenimiento", min_value=0.0, value=100.0)
    otros = st.number_input("📦 Otros Gastos", min_value=0.0, value=50.0)

# Cálculo de totales
total_gastos = alquiler + comida + servicios + transporte + ocio + otros
ahorro = total_ingresos - total_gastos

# --- SECCIÓN 3: RESULTADOS Y GRÁFICOS ---
st.markdown("---")
st.header("3. Tu Análisis Financiero")

# Métricas grandes (KPIs)
kpi1, kpi2, kpi3 = st.columns(3)

kpi1.metric(label="Ingresos Totales", value=f"${total_ingresos:,.2f}")
kpi2.metric(label="Gastos Totales", value=f"${total_gastos:,.2f}", delta=f"-{total_gastos/total_ingresos:.1%}")
kpi3.metric(label="Ahorro Mensual", value=f"${ahorro:,.2f}", delta_color="normal" if ahorro > 0 else "inverse")

# Mensaje personalizado según el ahorro
if ahorro > 0:
    st.success(f"¡Felicidades! Estás ahorrando ${ahorro:,.2f} este mes.")
elif ahorro == 0:
    st.warning("Estás al límite. Tus ingresos son iguales a tus gastos.")
else:
    st.error(f"Cuidado, estás gastando ${abs(ahorro):,.2f} más de lo que ganas.")

# --- GRÁFICO DE TORTA ---
if total_gastos > 0:
    # Crear un "Diccionario" de datos para el gráfico
    datos_gastos = {
        "Categoría": ["Alquiler", "Comida", "Servicios", "Transporte", "Ocio", "Otros"],
        "Monto": [alquiler, comida, servicios, transporte, ocio, otros]
    }
    
    # Convertirlo a un formato que Plotly entienda (DataFrame)
    df_gastos = pd.DataFrame(datos_gastos)
    
    # Filtrar categorías que sean 0 para que no aparezcan en el gráfico
    df_gastos = df_gastos[df_gastos["Monto"] > 0]

    # Crear el gráfico
    fig = px.pie(
        df_gastos, 
        values='Monto', 
        names='Categoría', 
        title='Distribución de tus Gastos',
        hole=0.4, # Hace que sea un gráfico de dona
        color_discrete_sequence=px.colors.sequential.RdBu
    )
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Ingresa tus gastos para ver el gráfico.")