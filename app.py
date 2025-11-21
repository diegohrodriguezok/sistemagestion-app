import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date, timedelta
import plotly.express as px
import plotly.graph_objects as go
import time
from fpdf import FPDF
import base64
import pytz
import uuid
import bcrypt

# --- 1. CONFIGURACIÓN GLOBAL ---
st.set_page_config(
    page_title="Area Arqueros ERP", 
    layout="wide", 
    initial_sidebar_state="expanded",
    page_icon="logo.png"
)

# --- CARGAR CSS ---
def local_css(file_name):
    try:
        with open(file_name) as f: st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except: pass

local_css("style.css")

# --- UTILIDADES DE TIEMPO (ARG) ---
def get_now_ar():
    try:
        tz = pytz.timezone('America/Argentina/Buenos_Aires')
        return datetime.now(tz)
    except: return datetime.now()

def get_today_ar():
    return get_now_ar().date()

def traducir_dia(fecha_dt):
    dias = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
    return dias[fecha_dt.weekday()]

# --- 2. MOTOR DE DATOS ---
@st.cache_resource
def get_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds).open("BaseDatos_ClubArqueros")
    except Exception as e:
        st.error(f"❌ Error crítico de conexión: {e}")
        st.stop()

def get_df(sheet_name):
    """Lectura robusta de datos con normalización"""
    try:
        ws = get_client().worksheet(sheet_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty:
            df.columns = df.columns.str.strip().str.lower()
            # Garantizar columnas mínimas para evitar KeyError
            cols_required = {
                'socios': ['id', 'nombre', 'apellido', 'dni', 'sede', 'grupo', 'plan', 'activo'],
                'pagos': ['id', 'id_socio', 'monto', 'mes_cobrado', 'estado'],
                'entrenamientos_plantilla': ['id', 'sede', 'dia', 'horario', 'grupo'],
                'inscripciones': ['id_socio', 'id_entrenamiento'],
                'usuarios': ['user', 'pass_hash', 'rol', 'nombre_completo', 'sedes_acceso', 'activo']
            }
            if sheet_name in cols_required:
                for col in cols_required[sheet_name]:
                    if col not in df.columns: df[col] = ""
        return df
    except: return pd.DataFrame()

def save_row(sheet_name, data):
    try: get_client().worksheet(sheet_name).append_row(data)
    except: pass

def save_rows_bulk(sheet_name, data_list):
    try: 
        get_client().worksheet(sheet_name).append_rows(data_list)
        return True
    except: return False

def generate_id():
    return int(f"{int(time.time())}{uuid.uuid4().int % 1000}")

def log_action(id_ref, accion, detalle, user):
    try:
        row = [str(get_now_ar()), user, str(id_ref), accion, detalle]
        save_row("logs", row)
    except: pass

# --- LÓGICA DE NEGOCIO ---
def update_full_socio(id_socio, d, user_admin, original_data=None):
    sh = get_client()
    ws = sh.worksheet("socios")
    try:
        cell = ws.find(str(id_socio))
        r = cell.row
        # Mapeo estricto de columnas
        ws.update_cell(r, 3, d['nombre'])
        ws.update_cell(r, 4, d['apellido'])
        ws.update_cell(r, 5, d['dni'])
        ws.update_cell(r, 6, str(d['nacimiento']))
        ws.update_cell(r, 7, d['tutor'])    
        ws.update_cell(r, 8, d['whatsapp']) 
        ws.update_cell(r, 9, d['email'])    
        ws.update_cell(r, 10, d['sede'])
        ws.update_cell(r, 11, d['plan'])
        ws.update_cell(r, 12, d['notas'])
        ws.update_cell(r, 14, d['activo'])
        ws.update_cell(r, 15, d['talle'])
        ws.update_cell(r, 16, d['grupo']) 
        ws.update_cell(r, 17, d['peso'])    
        ws.update_cell(r, 18, d['altura'])
        
        cambios = []
        if original_data:
            for k, v in d.items():
                if str(v) != str(original_data.get(k, '')): cambios.append(f"{k}: {v}")
        if cambios: log_action(id_socio, "Edición Perfil", " | ".join(cambios), user_admin)
        return True
    except: return False

def update_plan_socio(id_socio, nuevo_plan):
    sh = get_client()
    ws = sh.worksheet("socios")
    try:
        cell = ws.find(str(id_socio))
        ws.update_cell(cell.row, 11, nuevo_plan) 
        return True
    except: return False

def registrar_pago_existente(id_pago, metodo, user_cobrador, estado_final, nuevo_monto=None, nuevo_concepto=None, nota_conciliacion=""):
    ws = get_client().worksheet("pagos")
    try:
        cell = ws.find(str(id_pago))
        r = cell.row
        ws.update_cell(r, 2, str(get_today_ar())) 
        ws.update_cell(r, 7, metodo)
        ws.update_cell(r, 8, nota_conciliacion) 
        ws.update_cell(r, 9, estado_final) 
        ws.update_cell(r, 10, user_cobrador)
        if nuevo_monto: ws.update_cell(r, 5, nuevo_monto)
        if nuevo_concepto: ws.update_cell(r, 6, nuevo_concepto)
        log_action(id_pago, "Cobro Deuda", f"Cobrado por {user_cobrador}. Estado: {estado_final}", user_cobrador)
        return True
    except: return False

def confirmar_pago_seguro(id_pago, user, nota=""):
    ws = get_client().worksheet("pagos")
    try:
        cell = ws.find(str(id_pago))
        r = cell.row
        ws.update_cell(r, 9, "Confirmado")
        if nota: ws.update_cell(r, 8, nota) 
        log_action(id_pago, "Confirmar Pago", f"Validado. Nota: {nota}", user)
        return True
    except: return False

def actualizar_tarifas_bulk(df_edited):
    ws = get_client().worksheet("tarifas")
    ws.clear()
    ws.update([df_edited.columns.values.tolist()] + df_edited.values.tolist())

def get_config_value(key, default_val):
    try:
        df = get_df("config")
        if not df.empty and 'clave' in df.columns:
            res = df[df['clave'] == key]
            if not res.empty: return int(res.iloc[0]['valor'])
    except: pass
    return default_val

def set_config_value(key, value):
    sh = get_client()
    try: ws = sh.worksheet("config")
    except: 
        ws = sh.add_worksheet("config", 100, 2)
        ws.append_row(["clave", "valor"])
    try:
        cell = ws.find(key)
        ws.update_cell(cell.row, 2, str(value))
    except: ws.append_row([key, str(value)])
    return True

def calcular_edad(fecha_nac):
    try:
        if isinstance(fecha_nac, str): fecha_nac = datetime.strptime(fecha_nac, '%Y-%m-%d').date()
        hoy = get_today_ar()
        return hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
    except: return "?"

def generar_pdf(datos):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="AREA ARQUEROS - COMPROBANTE", ln=1, align='C')
    pdf.ln(10)
    
    def safe_txt(txt): return str(txt).encode('latin-1', 'replace').decode('latin-1')
    
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Fecha: {safe_txt(datos['fecha'])}", ln=1)
    pdf.cell(200, 10, txt=f"Alumno: {safe_txt(datos['alumno'])}", ln=1)
    pdf.cell(200, 10, txt=f"Concepto: {safe_txt(datos['concepto'])}", ln=1)
    pdf.cell(200, 10, txt=f"Mes: {safe_txt(datos.get('mes', '-'))}", ln=1)
    pdf.cell(200, 10, txt=f"Medio de Pago: {safe_txt(datos['metodo'])}", ln=1)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt=f"TOTAL ABONADO: ${datos['monto']}", ln=1, align='C')
    if datos.get('nota'):
        pdf.ln(5)
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(200, 10, txt=f"Nota: {safe_txt(datos['nota'])}", ln=1, align='C')
    pdf.ln(15)
    pdf.set_font("Arial", size=10)
    pdf.cell(200, 10, txt="Gracias por formar parte de Area Arqueros.", ln=1, align='C')
    return pdf.output(dest="S").encode("latin-1", errors='replace')

def inicializar_cronograma_base():
    data_list = []
    # C1
    grupos_c1 = ["Infantil 1", "Prejuvenil 1", "Juvenil 1", "Juvenil 2"]
    for d in ["Lunes", "Viernes"]:
        for h in ["18:00 - 19:00", "19:00 - 20:00"]:
            for g in grupos_c1: data_list.append([generate_id(), "Sede C1", d, h, g, "Sin Asignar", 10]); time.sleep(0.001)
    for g in ["Infantil 1", "Prejuvenil 1"]: data_list.append([generate_id(), "Sede C1", "Miércoles", "17:00 - 18:00", g, "Sin Asignar", 10]); time.sleep(0.001)
    for h in ["18:00 - 19:00", "19:00 - 20:00"]:
        for g in grupos_c1: data_list.append([generate_id(), "Sede C1", "Miércoles", h, g, "Sin Asignar", 10]); time.sleep(0.001)
    # SAA
    dias_saa = ["Lunes", "Miércoles", "Jueves"]
    gr_saa_18 = ["Infantil 1", "Infantil 2", "Prejuvenil 1", "Prejuvenil 2", "Juvenil 1", "Juvenil 2"]
    gr_saa_19 = ["Juvenil 1", "Juvenil 2", "Amateur 1", "Amateur 2", "Senior 1", "Senior 2"]
    for d in dias_saa:
        for g in gr_saa_18: data_list.append([generate_id(), "Sede Saa", d, "18:00 - 19:00", g, "Sin Asignar", 10]); time.sleep(0.001)
        for g in gr_saa_19: data_list.append([generate_id(), "Sede Saa", d, "19:00 - 20:00", g, "Sin Asignar", 10]); time.sleep(0.001)
    save_rows_bulk("entrenamientos_plantilla", data_list)

# --- SEGURIDAD RESTAURADA ---
def check_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except: return False

def crear_usuario_real(user, password, rol, nombre, sedes):
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    # id, user, pass_hash, rol, nombre, sedes, activo
    row = [generate_id(), user, hashed, rol, nombre, sedes, 1]
    save_row("usuarios", row)
    return True

# --- 3. LOGIN ---
if "auth" not in st.session_state:
    st.session_state.update({"auth": False, "user": None, "rol": None, "sedes": []})
if "view_profile_id" not in st.session_state: st.session_state["view_profile_id"] = None
if "cobro_alumno_id" not in st.session_state: st.session_state["cobro_alumno_id"] = None

def login_page():
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        try: st.image("logo.png", width=150)
        except: st.markdown("<h2 style='text-align: center;'>🔐 Area Arqueros</h2>", unsafe_allow_html=True)
        
        # 1. Check de Usuarios
        df_users = get_df("usuarios")
        
        if df_users.empty:
            st.warning("⚠️ Base de usuarios vacía. Cree el Administrador.")
            with st.form("init_admin"):
                nu = st.text_input("User Admin"); np = st.text_input("Pass", type="password")
                if st.form_submit_button("Inicializar"):
                    crear_usuario_real(nu, np, "Administrador", "Super Admin", "Todas")
                    st.success("Creado. Recargue."); time.sleep(2); st.rerun()
            return

        with st.form("login_form"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar"):
                login_ok = False
                # Intento DB
                if not df_users.empty and 'user' in df_users.columns:
                    user_match = df_users[df_users['user'] == u]
                    if not user_match.empty:
                        stored_hash = user_match.iloc[0]['pass_hash']
                        if check_password(p, stored_hash):
                            udata = user_match.iloc[0]
                            # Manejo robusto de sedes
                            try:
                                sedes_acc = str(udata['sedes_acceso']).split(",")
                                if udata['sedes_acceso'] == "Todas": sedes_acc = SEDES
                            except: sedes_acc = []
                            
                            st.session_state.update({"auth": True, "user": udata['nombre_completo'], "rol": udata['rol'], "sedes": sedes_acc})
                            login_ok = True
                            st.rerun()
                        else: st.error("Contraseña incorrecta")
                    else: st.error("Usuario no encontrado")
                
                # Fallback Secrets
                if not login_ok:
                    try:
                        BACKUP = st.secrets["users"]
                        if u in BACKUP and str(BACKUP[u]["p"]) == p:
                            st.session_state.update({"auth": True, "user": u, "rol": BACKUP[u]["r"], "sedes": SEDES})
                            st.warning("⚠️ Modo Respaldo")
                            time.sleep(1); st.rerun()
                        else: st.error("Credenciales inválidas")
                    except: st.error("Error de acceso.")

def logout():
    st.session_state["logged_in"] = False
    st.session_state["auth"] = False
    st.rerun()

if not st.session_state["auth"]:
    login_page(); st.stop()

# --- 4. MENÚ ---
user, rol = st.session_state["user"], st.session_state["rol"]

with st.sidebar:
    try: st.image("logo.png", width=220)
    except: st.header("🛡️ AREA ARQUEROS")
    st.info(f"👤 **{user}**\nRol: {rol}")
    
    menu_opts = ["Dashboard"]
    if rol in ["Administrador", "Profesor", "Entrenador"]:
        menu_opts.extend(["Alumnos", "Entrenamientos", "Asistencia"])
    if rol in ["Administrador", "Contador"]:
        menu_opts.extend(["Contabilidad", "Configuración"])
    if rol == "Administrador":
        menu_opts.append("Usuarios")
    
    nav = st.radio("Navegación", menu_opts)
    if nav != st.session_state.get("last_nav"):
        st.session_state["view_profile_id"] = None
        st.session_state["cobro_alumno_id"] = None
        st.session_state["last_nav"] = nav
    st.divider()
    if st.button("Cerrar Sesión"):
        st.session_state.update({"auth": False, "view_profile_id": None, "cobro_alumno_id": None})
        st.rerun()

# CONSTANTES GLOBALES
SEDES = ["Sede C1", "Sede Saa"]
GRUPOS_GEN = ["Infantil", "Prejuvenil", "Juvenil", "Adulto", "Senior", "Amateur"]
TALLES = ["10", "12", "14", "XS", "S", "M", "L", "XL"]
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# --- 5. MÓDULOS ---

# === DASHBOARD ===
if nav == "Dashboard":
    st.title("📊 Estadísticas")
    c1, c2 = st.columns(2)
    fecha_inicio = c1.date_input("Desde", date.today().replace(day=1))
    fecha_fin = c2.date_input("Hasta", date.today())
    
    df_pagos = get_df("pagos")
    df_gastos = get_df("gastos")
    df_s = get_df("socios")
    
    ingresos = 0
    egresos = 0
    if not df_pagos.empty:
        df_pagos['dt'] = pd.to_datetime(df_pagos['fecha_pago'], errors='coerce').dt.date
        p_filt = df_pagos[(df_pagos['dt'] >= fecha_inicio) & (df_pagos['dt'] <= fecha_fin)]
        ingresos = pd.to_numeric(p_filt['monto'], errors='coerce').fillna(0).sum()
    if not df_gastos.empty:
        df_gastos['dt'] = pd.to_datetime(df_gastos['fecha'], errors='coerce').dt.date
        g_filt = df_gastos[(df_gastos['dt'] >= fecha_inicio) & (df_gastos['dt'] <= fecha_fin)]
        egresos = pd.to_numeric(g_filt['monto'], errors='coerce').fillna(0).sum()
    balance = ingresos - egresos
    
    k1, k2, k3 = st.columns(3)
    k1.metric("Ingresos", f"${ingresos:,.0f}")
    k2.metric("Gastos", f"${egresos:,.0f}")
    k3.metric("Neto", f"${balance:,.0f}", delta_color="normal")
    
    if not df_s.empty:
        st.markdown("---")
        c_g1, c_g2 = st.columns([2,1])
        with c_g1:
            df_s['Estado'] = df_s['activo'].map({1: 'Activo', 0: 'Baja'})
            fig = px.pie(df_s, names='Estado', hole=0.4, title="Estado Alumnos", color_discrete_sequence=['#1f2c56', '#dc3545'])
            st.plotly_chart(fig, use_container_width=True)

# === ALUMNOS ===
elif nav == "Alumnos":
    if st.session_state["view_profile_id"] is None:
        st.title("👥 Gestión de Alumnos")
        tab_dir, tab_new = st.tabs(["📂 Directorio", "➕ Nuevo Alumno"])
        
        with tab_dir:
            df = get_df("socios")
            if not df.empty:
                with st.expander("🔍 Filtros de Búsqueda", expanded=True):
                    c1, c2, c3, c4 = st.columns(4)
                    f_sede = c1.selectbox("Sede", ["Todas"] + sorted(df['sede'].astype(str).unique().tolist()))
                    f_plan = c2.selectbox("Plan", ["Todos"] + sorted(df['plan'].astype(str).unique().tolist()))
                    f_grupo = c3.selectbox("Categoría", ["Todos"] + sorted(df['grupo'].astype(str).unique().tolist()))
                    f_act = c4.selectbox("Estado", ["Activos", "Inactivos", "Todos"])
                
                df_fil = df.copy()
                if f_sede != "Todas": df_fil = df_fil[df_fil['sede'] == f_sede]
                if f_plan != "Todos": df_fil = df_fil[df_fil['plan'] == f_plan]
                if f_grupo != "Todos": df_fil = df_fil[df_fil['grupo'] == f_grupo]
                if f_act == "Activos": df_fil = df_fil[df_fil['activo'] == 1]
                elif f_act == "Inactivos": df_fil = df_fil[df_fil['activo'] == 0]
                
                st.caption(f"Resultados: {len(df_fil)}")
                
                rows_per_page = 20
                total_pages = (len(df_fil) // rows_per_page) + 1
                page = st.number_input("Página", 1, total_pages, 1) if total_pages > 1 else 1
                start = (page-1)*rows_per_page
                end = start + rows_per_page
                
                for idx, row in df_fil.iloc[start:end].iterrows():
                    status_emoji = "🟢" if row['activo'] == 1 else "🔴"
                    label = f"{status_emoji} {row['nombre']} {row['apellido']} | DNI: {row['dni']} | {row['sede']} | {row.get('plan','-')}"
                    if st.button(label, key=f"row_{row['id']}", use_container_width=True):
                        st.session_state["view_profile_id"] = row['id']
                        st.rerun()
        
        with tab_new:
            st.subheader("Alta Completa")
            with st.form("alta"):
                c1, c2 = st.columns(2)
                nom = c1.text_input("Nombre")
                ape = c2.text_input("Apellido")
                dni = c1.text_input("DNI")
                nac = c2.date_input("Nacimiento", date(2000,1,1))
                
                sede = st.selectbox("Sede", SEDES)
                grupo_gen = st.selectbox("Categoría/Nivel", GRUPOS_GEN)
                
                df_tar = get_df("tarifas")
                planes = df_tar['concepto'].tolist() if not df_tar.empty else ["General"]
                plan = st.selectbox("Plan", planes)
                talle = st.selectbox("Talle", TALLES)
                
                tutor = st.text_input("Tutor")
                wsp = st.text_input("WhatsApp")
                email = st.text_input("Email")
                c3, c4 = st.columns(2)
                peso = c3.number_input("Peso", 0.0)
                alt = c4.number_input("Altura", 0)
                
                if st.form_submit_button("Guardar"):
                    if nom and ape:
                        uid = generate_id()
                        row = [uid, str(get_today_ar()), nom, ape, dni, str(nac), tutor, wsp, email, sede, plan, "", user, 1, talle, grupo_gen, peso, alt]
                        save_row("socios", row)
                        st.success("Alumno registrado.")
                        log_action(uid, "Alta", "Nuevo Alumno", user)
                    else: st.error("Faltan datos.")

    else:
        uid = st.session_state["view_profile_id"]
        df = get_df("socios")
        if not df.empty and not df[df['id'] == uid].empty:
            p = df[df['id'] == uid].iloc[0]
            if st.button("⬅️ Volver"):
                st.session_state["view_profile_id"] = None
                st.rerun()
            st.title(f"👤 {p['nombre']} {p['apellido']}")
            if p.get('whatsapp'):
                link = f"https://wa.me/{str(p['whatsapp']).strip()}"
                st.link_button("📱 WhatsApp", link)

            t1, t2, t3 = st.tabs(["✏️ Datos", "📅 Asistencia", "🔒 Historial"])
            
            with t1:
                if rol == "Administrador":
                    with st.form("edit_p"):
                        c1, c2 = st.columns(2)
                        n_nom = c1.text_input("Nombre", p['nombre'])
                        n_ape = c2.text_input("Apellido", p['apellido'])
                        n_dni = c1.text_input("DNI", p['dni'])
                        n_sede = c2.selectbox("Sede", SEDES, index=SEDES.index(p['sede']) if p['sede'] in SEDES else 0)
                        df_tar = get_df("tarifas")
                        pl = df_tar['concepto'].tolist() if not df_tar.empty else ["General"]
                        idx = pl.index(p['plan']) if p['plan'] in pl else 0
                        n_plan = st.selectbox("Plan", pl, index=idx)
                        n_notas = st.text_area("Notas", p.get('notas',''))
                        n_act = st.checkbox("Activo", value=True if p['activo']==1 else False)
                        if st.form_submit_button("Guardar Cambios"):
                            d_upd = p.to_dict()
                            d_upd.update({'nombre': n_nom, 'apellido': n_ape, 'dni': n_dni, 'sede': n_sede, 'plan': n_plan, 'notas': n_notas, 'activo': 1 if n_act else 0})
                            update_full_socio(uid, d_upd, user, original_data=p.to_dict())
                            st.success("Actualizado.")
                            time.sleep(1); st.rerun()
                else: st.info("Modo Lectura")
            
            with t2:
                df_a = get_df("asistencias")
                if not df_a.empty:
                    mis_a = df_a[df_a['id_socio'] == uid]
                    if not mis_a.empty:
                        mis_a['fecha_dt'] = pd.to_datetime(mis_a['fecha'], errors='coerce')
                        mis_a['Dia'] = mis_a['fecha_dt'].dt.day_name().map({
                            'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles', 
                            'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
                        })
                        fig = px.pie(mis_a, names='Dia', title='Días de Entrenamiento', color_discrete_sequence=px.colors.qualitative.Pastel)
                        st.plotly_chart(fig, use_container_width=True)
                        st.dataframe(mis_a[['fecha', 'sede', 'grupo_turno', 'estado']], use_container_width=True)
                    else: st.info("Sin asistencias.")
            
            with t3:
                st.subheader("Pagos")
                df_pagos_hist = get_df("pagos")
                if not df_pagos_hist.empty:
                    mis_pagos = df_pagos_hist[df_pagos_hist['id_socio'] == uid]
                    if not mis_pagos.empty: st.dataframe(mis_pagos[['fecha_pago', 'monto', 'concepto', 'mes_cobrado', 'estado']], use_container_width=True)
                st.subheader("Auditoría")
                df_l = get_df("logs")
                if not df_l.empty and 'id_ref' in df_l.columns:
                    mis_l = df_l[df_l['id_ref'].astype(str) == str(uid)]
                    st.dataframe(mis_l, use_container_width=True)
        else:
            st.error("Alumno no encontrado.")
            if st.button("Volver"):
                st.session_state["view_profile_id"] = None
                st.rerun()

# === ENTRENAMIENTOS ===
elif nav == "Entrenamientos":
    st.title("⚽ Configurar Grupos")
    tab_asig, tab_ver, tab_adm = st.tabs(["➕ Inscribir", "📅 Ver", "🔧 Admin"])
    
    with tab_asig:
        st.subheader("Inscripción")
        df_soc = get_df("socios")
        df_plant = get_df("entrenamientos_plantilla")
        df_insc = get_df("inscripciones")
        
        if not df_plant.empty and not df_soc.empty:
            activos = df_soc[df_soc['activo']==1]
            alu = st.selectbox("Alumno", activos['id'].astype(str) + " - " + activos['nombre'] + " " + activos['apellido'])
            uid_alu = int(alu.split(" - ")[0])
            nom_alu = alu.split(" - ")[1]
            
            c1, c2, c3 = st.columns(3)
            sede = c1.selectbox("Sede", sorted(df_plant['sede'].unique()))
            dias = df_plant[df_plant['sede']==sede]['dia'].unique()
            dia = c2.selectbox("Día", dias)
            horas = df_plant[(df_plant['sede']==sede)&(df_plant['dia']==dia)]['horario'].unique()
            hora = c3.selectbox("Horario", horas)
            
            grupos = df_plant[(df_plant['sede']==sede)&(df_plant['dia']==dia)&(df_plant['horario']==hora)]
            st.markdown("---")
            for idx, row in grupos.iterrows():
                inscr = len(df_insc[df_insc['id_entrenamiento']==row['id']]) if not df_insc.empty else 0
                cupo = int(row['cupo_max']) - inscr
                with st.container():
                    col_inf, col_btn = st.columns([4,1])
                    col_inf.markdown(f"""<div class="training-card"><b>{row['grupo']}</b> | Coach: {row['entrenador_asignado']} | Cupos: {cupo}</div>""", unsafe_allow_html=True)
                    if cupo > 0:
                        if col_btn.button("Inscribir", key=f"ins_{row['id']}"):
                            conflicto = False
                            if not df_insc.empty:
                                mis_ins = df_insc[df_insc['id_socio'] == uid_alu]
                                if not mis_ins.empty:
                                    merged = pd.merge(mis_ins, df_plant, left_on='id_entrenamiento', right_on='id')
                                    choque = merged[(merged['dia'] == dia) & (merged['horario'] == row['horario'])]
                                    if not choque.empty: conflicto = True
                            
                            if not conflicto:
                                row_ins = [generate_id(), uid_alu, nom_alu, row['id'], f"{row['grupo']} ({dia})"]
                                save_row("inscripciones", row_ins)
                                st.success("Inscrito")
                                time.sleep(1); st.rerun()
                            else: st.error("⚠️ Conflicto de Horario")
                    else: col_btn.error("Lleno")

    with tab_ver:
        st.subheader("Vista Semanal")
        df_p = get_df("entrenamientos_plantilla")
        if not df_p.empty:
            sede_v = st.selectbox("Sede Visual", sorted(df_p['sede'].unique()), key="sv")
            df_sede = df_p[df_p['sede']==sede_v]
            st.dataframe(df_sede[['dia', 'horario', 'grupo', 'entrenador_asignado']], use_container_width=True)

    with tab_adm:
        if rol == "Administrador":
            if st.button("Inicializar Estructura"):
                if get_df("entrenamientos_plantilla").empty:
                    inicializar_cronograma_base()
                    st.success("Creado")
                else: st.warning("Ya existe")

# === ASISTENCIA ===
elif nav == "Asistencia":
    st.title("✅ Tomar Lista")
    df_plant = get_df("entrenamientos_plantilla")
    df_insc = get_df("inscripciones")
    df_soc = get_df("socios")
    
    hoy_dia = traducir_dia(get_today_ar())
    st.info(f"Fecha: {hoy_dia} {get_today_ar()}")
    
    if not df_plant.empty:
        # Filtro Seguridad: Solo grupos del usuario si no es admin
        clases_hoy = df_plant[df_plant['dia'] == hoy_dia]
        
        if not clases_hoy.empty:
            sede = st.selectbox("Sede", sorted(clases_hoy['sede'].unique()))
            clases_sede = clases_hoy[clases_hoy['sede']==sede]
            
            for idx, c in clases_sede.iterrows():
                with st.expander(f"⏰ {c['horario']} - {c['grupo']}"):
                    # Alumnos inscritos
                    alumnos = df_insc[df_insc['id_entrenamiento']==c['id']] if not df_insc.empty else pd.DataFrame()
                    
                    with st.form(f"as_{c['id']}"):
                        checks = {}
                        motivos = {}
                        if not alumnos.empty:
                            st.write("Inscritos:")
                            for j, (i, a) in enumerate(alumnos.iterrows()):
                                c1, c2 = st.columns([1,2])
                                checks[a['id_socio']] = c1.checkbox(a['nombre_alumno'], value=True, key=f"k_{c['id']}_{a['id_socio']}")
                                motivos[a['id_socio']] = c2.text_input("Motivo (si ausente)", key=f"m_{c['id']}_{a['id_socio']}")
                        
                        # Agregar Invitado
                        st.markdown("---")
                        invitado = None
                        if not df_soc.empty:
                            activos = df_soc[df_soc['activo']==1]
                            inv_sel = st.selectbox("Agregar Invitado/Recupero", ["--"] + activos['id'].astype(str).tolist() + " - " + activos['nombre'], key=f"inv_{c['id']}")
                            if inv_sel != "--": invitado = inv_sel
                        
                        if st.form_submit_button("Guardar"):
                            # Guardar fijos
                            for u, p in checks.items():
                                nom = alumnos[alumnos['id_socio']==u].iloc[0]['nombre_alumno']
                                estado = "Presente" if p else "Ausente"
                                nota = "" if p else motivos[u]
                                save_row("asistencias", [str(get_today_ar()), datetime.now().strftime("%H:%M"), u, nom, sede, c['grupo'], estado, nota])
                            
                            # Guardar invitado
                            if invitado:
                                u_inv = int(invitado.split(" - ")[0])
                                n_inv = invitado.split(" - ")[1]
                                save_row("asistencias", [str(get_today_ar()), datetime.now().strftime("%H:%M"), u_inv, n_inv, sede, c['grupo'], "Presente", "Invitado"])
                            st.success("Guardado")
        else: st.info("No hay clases hoy.")

# === CONTABILIDAD ===
elif nav == "Contabilidad":
    st.title("📒 Contabilidad")
    
    with st.sidebar:
        st.markdown("### 🔍 Filtros")
        f_sede = st.multiselect("Sede", ["Sede C1", "Sede Saa"], default=["Sede C1", "Sede Saa"])
        f_mes = st.selectbox("Mes", ["Todos"] + MESES)
        f_rango1 = st.date_input("Desde", date(date.today().year, 1, 1))
        f_rango2 = st.date_input("Hasta", date.today())
        
    tab_cuotas, tab_ocasional, tab_rep = st.tabs(["📋 Gestión Pagos", "🛍️ Ocasionales", "📊 Caja"])
    
    with tab_cuotas:
        dia_corte = int(get_config_value("dia_corte", 19))
        hoy = get_today_ar()
        idx_m = hoy.month - 1
        if hoy.day >= dia_corte:
            t_idx = (idx_m + 1) % 12
            yr = hoy.year + 1 if idx_m == 11 else hoy.year
        else:
            t_idx = idx_m
            yr = hoy.year
        mes_target = f"{MESES[t_idx]} {yr}"
        st.caption(f"Período: **{mes_target}**")
        
        # AUTO-GENERACIÓN
        df_pag = get_df("pagos")
        df_soc = get_df("socios")
        df_tar = get_df("tarifas")
        
        pagos_gen = []
        if not df_pag.empty and 'mes_cobrado' in df_pag.columns:
            pagos_mes = df_pag[(df_pag['mes_cobrado'] == mes_target) & (df_pag['concepto'].astype(str).str.contains("Cuota"))]
            pagos_gen = pagos_mes['id_socio'].unique()
            
        if not df_soc.empty:
            pendientes = df_soc[(df_soc['activo']==1) & (~df_soc['id'].isin(pagos_gen))]
            if not pendientes.empty:
                filas = []
                for idx, row_s in pendientes.iterrows():
                    pr = 15000
                    if not df_tar.empty and row_s['plan'] in df_tar['concepto'].values:
                        pr = df_tar[df_tar['concepto']==row_s['plan']]['valor'].values[0]
                    row_p = [generate_id(), str(get_today_ar()), row_s['id'], f"{row_s['nombre']} {row_s['apellido']}", pr, "Cuota Mensual", "Pendiente", f"Plan: {row_s['plan']}", "Pendiente", "System", mes_target]
                    filas.append(row_p)
                if save_rows_bulk("pagos", filas):
                    st.markdown(f"""<div class="auto-gen-box"><h4>🔄 Auto-Generación</h4><p>{len(filas)} cuotas creadas para {mes_target}.</p></div>""", unsafe_allow_html=True)
                    time.sleep(2)
                    st.rerun()

        # COBRO
        if st.session_state["cobro_alumno_id"]:
            uid = st.session_state["cobro_alumno_id"]
            df_soc = get_df("socios")
            alu = df_soc[df_soc['id']==uid].iloc[0]
            st.subheader(f"Cobrando a: {alu['nombre']}")
            if st.button("Cancelar"):
                st.session_state["cobro_alumno_id"] = None
                st.rerun()
            
            # Formulario Cobro
            df_tar = get_df("tarifas")
            lst = df_tar['concepto'].tolist() if not df_tar.empty else ["General"]
            idx_p = lst.index(alu['plan']) if alu['plan'] in lst else 0
            
            c1, c2 = st.columns(2)
            conc = c1.selectbox("Concepto", lst, index=idx_p)
            pr = 0.0
            if not df_tar.empty:
                m = df_tar[df_tar['concepto']==conc]
                if not m.empty:
                    try: pr = float(str(m.iloc[0]['valor']).replace('$',''))
                    except: pass
            mon = c2.number_input("Monto", value=pr)
            
            c3, c4 = st.columns(2)
            met = c3.selectbox("Medio", ["Efectivo", "Transferencia", "MercadoPago"])
            mes_p = c4.selectbox("Mes", [mes_target] + [f"{m} {yr}" for m in MESES])
            
            nota = st.text_input("Nota")
            conf = st.checkbox("Confirmar Auto", value=True)
            
            deuda_id = None
            if not df_pag.empty:
                 check = df_pag[(df_pag['id_socio']==uid) & (df_pag['mes_cobrado']==mes_p) & (df_pag['estado']=='Pendiente')]
                 if not check.empty: deuda_id = check.iloc[0]['id']

            if st.button("✅ PAGAR", type="primary", use_container_width=True):
                if conc != alu['plan']: update_plan_socio(uid, conc)
                st_pago = "Confirmado" if conf else "Pendiente"
                
                if deuda_id:
                    registrar_pago_existente(deuda_id, met, user, st_pago, mon, conc, nota)
                else:
                    row = [generate_id(), str(get_today_ar()), uid, f"{alu['nombre']} {alu['apellido']}", mon, conc, met, nota, st_pago, user, mes_p]
                    save_row("pagos", row)
                
                st.success("Registrado")
                d_pdf = {"fecha":str(get_today_ar()), "alumno":f"{alu['nombre']} {alu['apellido']}", "monto":mon, "concepto":conc, "metodo":met, "mes":mes_p, "nota":nota}
                pdf_b = generar_pdf(d_pdf)
                b64 = base64.b64encode(pdf_b).decode()
                href = f'<a href="data:application/octet-stream;base64,{b64}" download="Recibo.pdf"><button>Descargar Recibo</button></a>'
                st.markdown(href, unsafe_allow_html=True)
                time.sleep(4)
                st.session_state["cobro_alumno_id"] = None
                st.rerun()

        else:
            st.subheader("Listado de Cobro")
            col_s, col_r = st.columns([3,1])
            search = col_s.text_input("Buscar")
            rows = col_r.selectbox("Filas", [25, 50])
            
            df_s = get_df("socios")
            df_p = get_df("pagos")
            
            if not df_s.empty:
                df_show = df_s[df_s['activo']==1]
                if search:
                    df_show = df_show[df_show.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
                
                total_rows = len(df_show)
                total_pages = (total_rows // rows) + 1 if rows > 0 else 1
                page = st.number_input("Página", 1, total_pages, 1)
                start = (page - 1) * rows
                end = start + rows
                subset = df_show.iloc[start:end]
                
                cols = st.columns([3, 2, 2, 2])
                cols[0].markdown("**Alumno**")
                cols[1].markdown("**Sede**")
                cols[2].markdown(f"**Estado ({mes_target})**")
                cols[3].markdown("**Acción**")
                st.markdown("---")
                
                for idx, row in subset.iterrows():
                    st_mes = "⚪ Sin Generar"
                    if not df_p.empty:
                        pm = df_p[(df_p['id_socio']==row['id']) & (df_p['mes_cobrado']==mes_target)]
                        if not pm.empty:
                            if "Confirmado" in pm['estado'].values: st_mes = "✅"
                            else: st_mes = "🔴"
                    
                    c1, c2, c3, c4 = st.columns([3,2,1,1])
                    c1.write(f"**{row['nombre']} {row['apellido']}**")
                    c2.caption(row['sede'])
                    c3.write(st_mes)
                    if c4.button("Cobrar", key=f"pay_{row['id']}"):
                        st.session_state["cobro_alumno_id"] = row['id']
                        st.rerun()
                    st.divider()
            else: st.info("No hay alumnos.")

    with tab_ocasional:
        st.subheader("Cobro Ocasional")
        df_s = get_df("socios")
        if not df_s.empty:
            activos = df_s[df_s['activo']==1]
            sel = st.selectbox("Alumno", activos['id'].astype(str) + " - " + activos['nombre'] + " " + activos['apellido'], key="ocasional")
            with st.form("pay_ocasional"):
                c1, c2 = st.columns(2)
                monto = c1.number_input("Monto", step=100)
                concepto = st.selectbox("Concepto", ["Matrícula", "Indumentaria", "Torneo", "Campus", "Otro"])
                metodo = st.selectbox("Medio", ["Efectivo", "Transferencia", "MercadoPago"])
                nota = st.text_input("Nota")
                if st.form_submit_button("Registrar"):
                    row = [generate_id(), str(get_today_ar()), int(sel.split(" - ")[0]), sel.split(" - ")[1], monto, concepto, metodo, nota, "Confirmado", user, "-"]
                    save_row("pagos", row)
                    st.success("Registrado.")
    
    with tab_rep:
        st.markdown("### Caja Diaria")
        df_p = get_df("pagos")
        if not df_p.empty:
            td = str(get_today_ar())
            ch = df_p[(df_p['fecha_pago']==td) & (df_p['estado']=='Confirmado')]
            tot = pd.to_numeric(ch['monto'], errors='coerce').sum()
            st.metric("Total Hoy", f"${tot:,.0f}")
            st.dataframe(ch)

elif nav == "Configuración":
    st.title("⚙️ Configuración")
    tab1, tab2 = st.tabs(["Parámetros", "Tarifas"])
    with tab1:
        d = int(get_config_value("dia_corte", 19))
        nd = st.slider("Día Corte", 1, 28, d)
        v = int(get_config_value("dia_vencimiento", 10))
        nv = st.slider("Día Vencimiento", 1, 28, v)
        if st.button("Guardar"):
            set_config_value("dia_corte", nd)
            set_config_value("dia_vencimiento", nv)
            st.success("Guardado")
    with tab2:
        df = get_df("tarifas")
        ed = st.data_editor(df, num_rows="dynamic")
        if st.button("Guardar Tarifas"):
            actualizar_tarifas_bulk(ed)
            st.success("Guardado")
elif nav == "Usuarios":
    st.title("🔐 Gestión Usuarios")
    if rol == "Administrador":
        with st.form("nu"):
            u = st.text_input("Usuario")
            p = st.text_input("Clave", type="password")
            n = st.text_input("Nombre")
            r = st.selectbox("Rol", ["Administrador", "Entrenador", "Contador"])
            s = st.multiselect("Sedes", SEDES)
            if st.form_submit_button("Crear"):
                h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
                save_row("usuarios", [generate_id(), u, h, r, n, ",".join(s), 1])
                st.success("Creado")
