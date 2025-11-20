import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import plotly.express as px
import time

# --- 1. CONFIGURACIÓN GLOBAL Y ESTILOS ---
st.set_page_config(
    page_title="Area Arqueros ERP", 
    layout="wide", 
    initial_sidebar_state="expanded",
    page_icon="🏹"
)

# CSS Optimizado para Modo Claro/Oscuro y UX
st.markdown("""
    <style>
        /* Botones de acción principales */
        .stButton>button {
            border-radius: 6px;
            height: 45px;
            font-weight: 600;
            border: 1px solid rgba(255,255,255,0.1);
            background-color: #1f2c56;
            color: white;
            transition: all 0.3s;
        }
        .stButton>button:hover {
            background-color: #2c3e50;
            border-color: white;
            color: #ffffff;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }
        /* Métricas destacadas */
        div[data-testid="stMetricValue"] {
            font-size: 1.6rem !important;
            font-weight: 700;
        }
        /* Alertas personalizadas */
        .audit-log {
            font-size: 0.8rem;
            color: #666;
            border-top: 1px solid #eee;
            padding-top: 5px;
        }
    </style>
    """, unsafe_allow_html=True)

# --- 2. GESTOR DE CONEXIÓN (PATRÓN SINGLETON) ---
@st.cache_resource
def get_client():
    """Conexión única cacheada a Google"""
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds).open("BaseDatos_ClubArqueros")
    except Exception as e:
        st.error(f"❌ Error crítico de conexión: {e}")
        st.stop()

def get_df(sheet_name):
    """Obtiene datos como DataFrame de forma segura"""
    try:
        ws = get_client().worksheet(sheet_name)
        return pd.DataFrame(ws.get_all_records())
    except:
        return pd.DataFrame()

def save_row(sheet_name, data):
    """Guarda una fila nueva"""
    get_client().worksheet(sheet_name).append_row(data)

def update_cell_logic(sheet_name, id_row, col_idx, value):
    """Actualiza una celda específica buscando por ID"""
    ws = get_client().worksheet(sheet_name)
    try:
        cell = ws.find(str(id_row))
        ws.update_cell(cell.row, col_idx, value)
        return True
    except:
        return False

# --- 3. LÓGICA DE NEGOCIO ---

def auditar_movimiento(accion, detalle):
    """(Opcional) Podría guardar logs en una hoja separada"""
    # Por ahora imprimimos en consola o lo dejamos para futura expansión
    pass

def confirmar_pago_seguro(id_pago):
    """Cambia estado a Confirmado solo si el usuario tiene permisos"""
    # Asumiendo columna 9 es 'estado' (Ajustar según tu hoja real)
    return update_cell_logic("pagos", id_pago, 9, "Confirmado")

def actualizar_tarifas_bulk(df_edited):
    """Reescribe la hoja de tarifas completa"""
    ws = get_client().worksheet("tarifas")
    ws.clear()
    ws.update([df_edited.columns.values.tolist()] + df_edited.values.tolist())

# --- 4. SISTEMA DE SEGURIDAD (LOGIN) ---
if "auth" not in st.session_state:
    st.session_state.update({"auth": False, "user": None, "rol": None})

def login():
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔐 Area Arqueros</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar", use_container_width=True):
                # USUARIOS CONFIGURABLES
                CREDS = {
                    "admin": {"p": "admin2024", "r": "Administrador"},
                    "profe": {"p": "entrenador", "r": "Profesor"},
                    "conta": {"p": "finanzas", "r": "Contador"}
                }
                if u in CREDS and CREDS[u]["p"] == p:
                    st.session_state.update({"auth": True, "user": u, "rol": CREDS[u]["r"]})
                    st.rerun()
                else:
                    st.error("Acceso denegado")

if not st.session_state["auth"]:
    login()
    st.stop()

# --- 5. UI PRINCIPAL ---
user, rol = st.session_state["user"], st.session_state["rol"]

with st.sidebar:
    try:
        st.image("logo.png", use_container_width=True)
    except:
        st.header("🛡️ AREA ARQUEROS")
    
    st.info(f"👤 **{user.upper()}**\nRol: {rol}")
    
    menu_opts = ["Dashboard"]
    if rol in ["Administrador", "Profesor"]:
        menu_opts.extend(["Perfil Alumno", "Asistencia", "Nuevo Alumno"])
    if rol in ["Administrador", "Contador"]:
        menu_opts.extend(["Contabilidad", "Configurar Tarifas"])
    
    nav = st.radio("Navegación", menu_opts)
    st.divider()
    if st.button("Cerrar Sesión"):
        st.session_state.update({"auth": False})
        st.rerun()

# --- 6. MÓDULOS FUNCIONALES ---

# === DASHBOARD INTELIGENTE ===
if nav == "Dashboard":
    st.title("📊 Tablero de Comando")
    
    df_s = get_df("socios")
    df_a = get_df("asistencias")
    
    # KPIs Principales
    c1, c2, c3 = st.columns(3)
    activos = len(df_s[df_s['activo']==1]) if not df_s.empty else 0
    c1.metric("Alumnos Activos", activos)
    
    # Gráficos
    g1, g2 = st.columns(2)
    
    with g1:
        st.subheader("Composición y Bajas")
        if not df_s.empty:
            df_s['Estado'] = df_s['activo'].map({1: 'Activo', 0: 'Baja'})
            fig = px.pie(df_s, names='Estado', hole=0.4, color_discrete_sequence=['#1f2c56', '#e74c3c'])
            st.plotly_chart(fig, use_container_width=True)
            
    with g2:
        st.subheader("Asistencia Hoy (Tiempo Real)")
        if not df_a.empty:
            today_str = date.today().strftime("%Y-%m-%d")
            # Asegurar formato string
            df_a['fecha'] = df_a['fecha'].astype(str)
            today_data = df_a[df_a['fecha'] == today_str]
            
            if not today_data.empty:
                view_mode = st.radio("Agrupar por:", ["sede", "turno"], horizontal=True, label_visibility="collapsed")
                counts = today_data[view_mode].value_counts().reset_index()
                counts.columns = [view_mode, 'cantidad']
                fig2 = px.bar(counts, x=view_mode, y='cantidad', color='cantidad', title=f"Total Hoy: {len(today_data)}")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("Aún no hay registros de hoy.")
    
    st.subheader("📅 Permanencia")
    if not df_s.empty:
        df_s['fecha_alta'] = pd.to_datetime(df_s['fecha_alta'], errors='coerce')
        df_s['meses_antiguedad'] = ((pd.Timestamp.now() - df_s['fecha_alta']).dt.days / 30).fillna(0).astype(int)
        actives = df_s[df_s['activo']==1]
        fig3 = px.histogram(actives, x="meses_antiguedad", nbins=20, title="Distribución de Antigüedad (Meses)", color_discrete_sequence=['#27ae60'])
        st.plotly_chart(fig3, use_container_width=True)

# === PERFIL 360 ===
elif nav == "Perfil Alumno":
    st.title("👤 Perfil 360°")
    df = get_df("socios")
    
    if not df.empty:
        df['label'] = df['id'].astype(str) + " | " + df['nombre'] + " " + df['apellido']
        sel = st.selectbox("Buscar Alumno:", df['label'])
        
        if sel:
            uid = int(sel.split(" | ")[0])
            p = df[df['id'] == uid].iloc[0]
            
            # Header
            h1, h2 = st.columns([1, 4])
            with h1: st.markdown("# 👤")
            with h2:
                st.markdown(f"## {p['nombre']} {p['apellido']}")
                st.caption(f"ID: {uid} | DNI: {p['dni']} | Alta: {p['fecha_alta']}")
                tags = f"**Plan:** {p['plan']} | **Sede:** {p['sede']} | **Grupo:** {p.get('grupo','-')}"
                if p['activo'] == 1: st.success(tags) 
                else: st.error(f"BAJA - {tags}")

            t1, t2, t3 = st.tabs(["📝 Datos & Notas", "📈 Estadísticas", "📞 Contacto"])
            
            with t1:
                # Notas editables
                prev_notes = p.get('notas', '')
                new_notes = st.text_area("Notas Internas (Médicas/Admin):", prev_notes)
                if new_notes != prev_notes and st.button("Guardar Nota"):
                    # Actualizar solo la columna de notas (Col 12 aprox)
                    update_cell_logic("socios", uid, 12, new_notes)
                    st.success("Nota actualizada")
            
            with t2:
                # Stats de Asistencia
                df_asist = get_df("asistencias")
                if not df_asist.empty:
                    my_asist = df_asist[df_asist['id_socio'] == uid]
                    c_total = len(my_asist)
                    st.metric("Clases Totales Asistidas", c_total)
                    
                    if c_total > 0:
                        st.markdown("#### Historial Reciente")
                        st.dataframe(my_asist[['fecha', 'sede', 'turno']].tail(10), use_container_width=True)
            
            with t3:
                st.write(f"📧 **Email:** {p.get('email', 'No cargado')}")
                st.write(f"📱 **WhatsApp:** {p.get('whatsapp', '-')}")
                st.write(f"👕 **Talle:** {p.get('talle', '-')}")

# === CONTABILIDAD BLINDADA ===
elif nav == "Contabilidad":
    st.title("📒 Centro Contable")
    
    # Cargar Tarifas para selectores
    df_tar = get_df("tarifas")
    tarifas_opts = df_tar['concepto'].tolist() if not df_tar.empty else []
    
    tb1, tb2, tb3 = st.tabs(["💰 Ingresos (Cobros)", "✅ Confirmaciones", "📉 Balance & Gastos"])
    
    # 1. REGISTRAR COBRO (Paso 1)
    with tb1:
        st.subheader("Registrar Nuevo Pago")
        df_s = get_df("socios")
        if not df_s.empty:
            activos = df_s[df_s['activo']==1]
            sel_alu = st.selectbox("Seleccionar Alumno", activos['id'].astype(str) + " - " + activos['nombre'] + " " + activos['apellido'])
            
            with st.form("cobro_form"):
                c1, c2 = st.columns(2)
                concepto = c1.selectbox("Concepto / Tarifa", tarifas_opts + ["Otro"])
                
                # Precio sugerido
                precio_sug = 0.0
                if not df_tar.empty and concepto in tarifas_opts:
                    try: precio_sug = float(df_tar[df_tar['concepto']==concepto]['valor'].values[0])
                    except: pass
                
                monto = c2.number_input("Monto ($)", value=precio_sug, step=100.0)
                metodo = st.selectbox("Medio de Pago", ["Efectivo", "Transferencia", "MercadoPago"])
                
                if st.form_submit_button("Registrar (Pendiente)"):
                    # Estructura: id, fecha, id_socio, nombre_socio, monto, concepto, metodo, comentario, estado, usuario
                    row = [
                        int(datetime.now().timestamp()),
                        str(date.today()),
                        int(sel_alu.split(" - ")[0]),
                        sel_alu.split(" - ")[1],
                        monto,
                        concepto,
                        metodo,
                        "", # comentario
                        "Pendiente",
                        user # Usuario auditor
                    ]
                    save_row("pagos", row)
                    st.success("Pago registrado. Requiere confirmación.")

    # 2. CONFIRMACIÓN (Paso 2 - Solo Admin/Conta)
    with tb2:
        st.subheader("Auditoría de Pagos")
        df_p = get_df("pagos")
        if not df_p.empty and "estado" in df_p.columns:
            pendientes = df_p[df_p['estado'] == "Pendiente"]
            if not pendientes.empty:
                st.dataframe(pendientes[['fecha_pago', 'nombre_socio', 'monto', 'concepto', 'usuario_registro']])
                
                pago_id = st.selectbox("Seleccionar ID para confirmar:", pendientes['id'])
                if st.button("✅ Confirmar Pago Definitivo"):
                    if rol in ["Administrador", "Contador"]:
                        # Asumiendo columna estado es la 9 (I)
                        confirmar_pago_seguro(pago_id)
                        st.success("Pago confirmado y blindado.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("No tienes permisos para confirmar.")
            else:
                st.success("Todo al día. No hay pagos pendientes.")
        else:
            st.warning("Configura la columna 'estado' en Google Sheets.")

    # 3. BALANCE
    with tb3:
        c1, c2 = st.columns(2)
        d_desde = c1.date_input("Desde", date(date.today().year, 1, 1))
        d_hasta = c2.date_input("Hasta", date.today())
        
        if st.button("Calcular Balance"):
            df_p = get_df("pagos")
            df_g = get_df("gastos")
            
            # Filtrar y convertir fechas
            t_ing = 0
            t_egr = 0
            
            if not df_p.empty:
                df_p['dt'] = pd.to_datetime(df_p['fecha_pago'], errors='coerce').dt.date
                # Solo sumamos CONFIRMADOS para balance real
                conf = df_p[(df_p['dt'] >= d_desde) & (df_p['dt'] <= d_hasta) & (df_p['estado'] == 'Confirmado')]
                t_ing = pd.to_numeric(conf['monto'], errors='coerce').sum()
                
            if not df_g.empty:
                df_g['dt'] = pd.to_datetime(df_g['fecha'], errors='coerce').dt.date
                gas = df_g[(df_g['dt'] >= d_desde) & (df_g['dt'] <= d_hasta)]
                t_egr = pd.to_numeric(gas['monto'], errors='coerce').sum()
            
            st.metric("Resultado Neto", f"${t_ing - t_egr:,.2f}", delta=f"Ingresos: ${t_ing:,.0f}")
            
            # Gráfico Evolutivo
            st.bar_chart({"Ingresos": t_ing, "Egresos": t_egr})

# === CONFIGURACIÓN TARIFAS ===
elif nav == "Configurar Tarifas":
    st.title("⚙️ Tarifas del Club")
    
    df = get_df("tarifas")
    if df.empty:
        df = pd.DataFrame({"concepto": ["Cuota Base"], "valor": [15000]})
        
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    
    if st.button("Guardar Cambios"):
        actualizar_tarifas_bulk(edited)
        st.success("Tarifas actualizadas")

# === NUEVO ALUMNO ===
elif nav == "Nuevo Alumno":
    st.title("📝 Alta de Alumno")
    with st.form("alta"):
        c1, c2 = st.columns(2)
        nom = c1.text_input("Nombre")
        ape = c2.text_input("Apellido")
        
        df_tar = get_df("tarifas")
        planes = df_tar['concepto'].tolist() if not df_tar.empty else ["General"]
        
        c3, c4 = st.columns(2)
        dni = c3.text_input("DNI")
        email = c4.text_input("Email") # Nuevo campo solicitado
        
        c5, c6 = st.columns(2)
        sede = c5.selectbox("Sede", ["Sede C1", "Sede Saa"])
        grupo = c6.selectbox("Grupo", ["Inicial", "Intermedio", "Avanzado", "Arqueras"])
        
        talle = st.selectbox("Talle", ["10", "12", "14", "XS", "S", "M", "L", "XL"])
        plan = st.selectbox("Plan Inicial", planes)
        
        if st.form_submit_button("Crear Ficha"):
            if nom and ape and dni:
                uid = int(datetime.now().timestamp())
                # Estructura completa: id, fecha, nom, ape, dni, nac, tutor, wsp, email, sede, plan, notas, vendedor, activo, talle, grupo
                row = [
                    uid, str(date.today()), nom, ape, dni, "", "", "", 
                    email, sede, plan, "", user, 1, talle, grupo
                ]
                save_row("socios", row)
                st.success(f"Alumno {nom} registrado.")

# === ASISTENCIA RAPIDA ===
elif nav == "Asistencia":
    st.title("✅ Tomar Lista")
    col1, col2 = st.columns(2)
    sede = col1.selectbox("Sede", ["Sede C1", "Sede Saa"])
    grupo = col2.selectbox("Grupo", ["Inicial", "Intermedio", "Avanzado", "Arqueras"])
    
    df = get_df("socios")
    if not df.empty and 'grupo' in df.columns:
        # Filtrar
        filtro = df[(df['sede'] == sede) & (df['grupo'] == grupo) & (df['activo'] == 1)]
        
        if not filtro.empty:
            with st.form("asist_form"):
                st.write(f"Alumnos: {len(filtro)}")
                # Grid de checkboxes
                cols = st.columns(3)
                checks = {}
                for i, (idx, r) in enumerate(filtro.iterrows()):
                    checks[r['id']] = cols[i%3].checkbox(f"{r['nombre']} {r['apellido']}", key=r['id'])
                
                if st.form_submit_button("Guardar Presentes"):
                    cnt = 0
                    for uid, present in checks.items():
                        if present:
                            # id, fecha, hora, id_socio, nombre, sede, turno/grupo, estado
                            nom = filtro.loc[filtro['id']==uid, 'nombre'].values[0]
                            ape = filtro.loc[filtro['id']==uid, 'apellido'].values[0]
                            row = [
                                str(date.today()), datetime.now().strftime("%H:%M"),
                                uid, f"{nom} {ape}", sede, grupo, "Presente"
                            ]
                            save_row("asistencias", row)
                            cnt += 1
                    st.success(f"✅ {cnt} Asistencias guardadas")
        else:
            st.warning("No hay alumnos en este grupo/sede.")
