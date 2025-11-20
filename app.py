import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión Club de Arqueros", layout="wide", page_icon="⚽")

# --- CONEXIÓN A GOOGLE SHEETS ---
def get_connection():
    """Conecta a Google Sheets usando st.secrets"""
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Intentamos cargar las credenciales desde los secretos de Streamlit
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        # IMPORTANTE: Reemplaza este nombre con el nombre exacto de tu Hoja de Cálculo
        sheet = client.open("BaseDatos_ClubArqueros") 
        return sheet
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        st.stop()

# Función para inicializar hojas si están vacías
def init_sheets(sh):
    try:
        # Intentar abrir hoja de socios, si no existe, crearla (o manejar error)
        try:
            w_socios = sh.worksheet("socios")
        except:
            w_socios = sh.add_worksheet(title="socios", rows=100, cols=20)
            w_socios.append_row(["id", "fecha_alta", "nombre", "apellido", "dni", "fecha_nacimiento", "tutor", "whatsapp", "email", "sede", "frecuencia", "notas", "vendedor", "activo"])

        try:
            w_pagos = sh.worksheet("pagos")
        except:
            w_pagos = sh.add_worksheet(title="pagos", rows=100, cols=20)
            w_pagos.append_row(["id", "fecha_pago", "id_socio", "nombre_socio", "monto", "concepto", "metodo", "comentarios"])

        try:
            w_asistencias = sh.worksheet("asistencias")
        except:
            w_asistencias = sh.add_worksheet(title="asistencias", rows=100, cols=20)
            w_asistencias.append_row(["fecha", "hora", "id_socio", "nombre_socio", "sede", "turno", "presente"])
            
    except Exception as e:
        st.error(f"Error inicializando hojas: {e}")

# Funciones CRUD para Sheets
def get_data(sheet_name):
    sh = get_connection()
    worksheet = sh.worksheet(sheet_name)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def add_row(sheet_name, row_data):
    sh = get_connection()
    worksheet = sh.worksheet(sheet_name)
    worksheet.append_row(row_data)
    return True

# --- INTERFAZ GRÁFICA ---

st.title("⚽ Sistema Cloud: Club de Arqueros")

# Verificar conexión al inicio
try:
    sh = get_connection()
    init_sheets(sh) # Asegurar que existan las pestañas
except:
    st.warning("⚠️ Configura las credenciales en .streamlit/secrets.toml para empezar.")
    st.stop()

# Menú lateral
menu = st.sidebar.selectbox(
    "Menú Principal", 
    ["Inicio / Dashboard", "Nuevo Socio", "Gestión de Socios", "Registrar Asistencia", "Caja y Pagos"]
)

SEDES = ["Sede C1", "Sede Saa"]
TURNOS = ["17:00 - 18:00", "18:00 - 19:00", "19:00 - 20:00"]

# --- 1. DASHBOARD ---
if menu == "Inicio / Dashboard":
    st.header("📊 Estado del Club (Nube)")
    df_socios = get_data("socios")
    df_pagos = get_data("pagos")
    
    if not df_socios.empty:
        # Filtrar activos (Sheets devuelve strings, convertimos a int/bool si es necesario)
        socios_activos = df_socios[df_socios["activo"] == 1]
        st.metric("Socios Activos", len(socios_activos))
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Socios por Sede")
            if not socios_activos.empty:
                st.bar_chart(socios_activos['sede'].value_counts())
        
        with col2:
            st.subheader("Ingresos")
            if not df_pagos.empty:
                # Limpieza de datos para asegurar que sean números
                df_pagos['monto'] = pd.to_numeric(df_pagos['monto'], errors='coerce')
                st.metric("Total Recaudado Histórico", f"${df_pagos['monto'].sum():,.2f}")
    else:
        st.info("Base de datos vacía. Registra tu primer socio.")

# --- 2. NUEVO SOCIO ---
elif menu == "Nuevo Socio":
    st.header("📝 Alta de Nuevo Arquero")
    with st.form("form_alta"):
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre")
            apellido = st.text_input("Apellido")
            dni = st.text_input("DNI")
            nacimiento = st.date_input("Fecha Nacimiento", min_value=date(1980,1,1))
        with col2:
            sede = st.selectbox("Sede", SEDES)
            plan = st.selectbox("Plan", [1, 2, 3])
            whatsapp = st.text_input("WhatsApp")
            email = st.text_input("Email")
        
        submitted = st.form_submit_button("Guardar en Nube")
        
        if submitted and dni:
            # Generar ID simple (timestamp)
            new_id = int(datetime.now().timestamp())
            row = [new_id, str(date.today()), nombre, apellido, dni, str(nacimiento), "", whatsapp, email, sede, plan, "", "", 1]
            add_row("socios", row)
            st.success("✅ Guardado en Google Sheets!")

# --- 3. GESTIÓN DE SOCIOS ---
elif menu == "Gestión de Socios":
    st.header("👥 Directorio")
    df = get_data("socios")
    st.dataframe(df, use_container_width=True)

# --- 4. ASISTENCIA ---
elif menu == "Registrar Asistencia":
    st.header("✅ Asistencia")
    df_socios = get_data("socios")
    
    col1, col2 = st.columns(2)
    sede_sel = col1.selectbox("Sede", SEDES)
    turno_sel = col2.selectbox("Turno", TURNOS)
    
    if not df_socios.empty:
        socios_sede = df_socios[df_socios["sede"] == sede_sel]
        
        with st.form("asist"):
            seleccionados = []
            for idx, s in socios_sede.iterrows():
                if st.checkbox(f"{s['nombre']} {s['apellido']}", key=s['id']):
                    seleccionados.append(s)
            
            if st.form_submit_button("Guardar Asistencia"):
                for s in seleccionados:
                    row = [str(date.today()), datetime.now().strftime("%H:%M"), s['id'], f"{s['nombre']} {s['apellido']}", sede_sel, turno_sel, "Presente"]
                    add_row("asistencias", row)
                st.success("Asistencias subidas a la nube.")

# --- 5. PAGOS ---
elif menu == "Caja y Pagos":
    st.header("💰 Caja")
    df_socios = get_data("socios")
    
    if not df_socios.empty:
        lista = df_socios.apply(lambda x: f"{x['id']} - {x['nombre']} {x['apellido']}", axis=1)
        elegido = st.selectbox("Socio", lista)
        
        monto = st.number_input("Monto", step=100)
        concepto = st.selectbox("Concepto", ["Cuota", "Matrícula", "Ropa"])
        
        if st.button("Registrar Pago"):
            id_s = elegido.split(" - ")[0]
            nombre_s = elegido.split(" - ")[1]
            # ID_PAGO, FECHA, ID_SOCIO, NOMBRE, MONTO, CONCEPTO, METODO, COMENTARIO
            row = [int(datetime.now().timestamp()), str(date.today()), id_s, nombre_s, monto, concepto, "Efectivo", ""]
            add_row("pagos", row)
            st.success("Pago registrado.")
            
    # Mostrar últimos pagos
    st.subheader("Historial en Vivo")
    st.dataframe(get_data("pagos").tail(5), use_container_width=True)
