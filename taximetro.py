# ══════════════════════════════════════════════════════════════════════════════
# PROYECTO NRO. 1
# Taxímetro Digital - Aplicación Principal
# Creado por: Johans Enrique Salas Rodríguez
# ══════════════════════════════════════════════════════════════════════════════

import os
import json
import logging
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime

# ── Kivy config ANTES de cualquier otro import de Kivy ──────────────────────
from kivy.config import Config
Config.set('graphics', 'width',     '440')
Config.set('graphics', 'height',    '680')
Config.set('graphics', 'resizable', False)

from kivymd.app            import MDApp
from kivy.lang             import Builder
from kivy.clock            import Clock
from kivy.uix.boxlayout    import BoxLayout
from kivymd.uix.boxlayout  import MDBoxLayout
from kivymd.uix.button     import MDFillRoundFlatIconButton
from kivymd.uix.label      import MDLabel, MDIcon
from kivymd.uix.list       import OneLineAvatarListItem, ILeftBodyTouch, IconLeftWidget
from kivymd.uix.card       import MDCard, MDSeparator
from kivy.properties       import StringProperty, ListProperty
from kivy.metrics          import dp

# ── PDF ──────────────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib           import colors
from reportlab.platypus      import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle, HRFlowable)
from reportlab.lib.styles    import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units     import cm

# ── INICIO DE SESIÓN ─────────────────────────────────────────────────────────
from kivymd.uix.dialog import MDDialog
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDFlatButton

# ── HISTORIAL DE TRAYECTOS ───────────────────────────────────────────────────
from kivymd.uix.scrollview import MDScrollView


# ══════════════════════════════════════════════════════════════════════════════
# RUTAS
# ══════════════════════════════════════════════════════════════════════════════

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "historial.json")
CONFIG_FILE  = os.path.join(BASE_DIR, "config.json")
USERS_FILE   = os.path.join(BASE_DIR, "usuarios.json")
FACTURAS_DIR = os.path.join(BASE_DIR, "facturas")
os.makedirs(FACTURAS_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════════════

LOG_FILE = os.path.join(BASE_DIR, "taximetro.log")

logger = logging.getLogger("Taximetro")
logger.setLevel(logging.INFO)

if not logger.handlers:

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8"
    )

    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()

    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    logger.addHandler(console_handler)

logger.info("Sistema de logging iniciado.")


# ══════════════════════════════════════════════════════════════════════════════
# MODELOS DE DATOS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Tarifa:
    precio_parado:         float = 0.02
    precio_movimiento:     float = 0.05
    precio_bajada_bandera: float = 1.50

    def to_dict(self):     return asdict(self)
    @classmethod
    def from_dict(cls, d): return cls(**d)


@dataclass
class TipoServicio:
    clave:         str
    nombre:        str
    icon_name:     str
    descripcion:   str
    cargo_fijo:    float
    multiplicador: float
    color_name:    str


SERVICIOS = [
    TipoServicio("economico",  "Economico",    "car",              "Tarifa estandar",            0.0,  1.0, "White"),
    TipoServicio("xl",         "XL / Familiar","account-group",    "Vehiculo de mayor capacidad", 2.00, 1.4, "Blue"),
    TipoServicio("compartido", "Compartido",   "account-multiple", "Viaje compartido",            0.0,  0.6, "Teal"),
    TipoServicio("pet",        "Pet Friendly", "paw",              "Mascotas permitidas",         1.50, 1.0, "Orange"),
    TipoServicio("flash",      "Flash",        "lightning-bolt",   "Recogida prioritaria",        3.00, 1.2, "Amber"),
]

COLORES = {
    "White":  [1.0,  1.0,  1.0,  1],
    "Blue":   [0.25, 0.55, 1.0,  1],
    "Teal":   [0.0,  0.75, 0.75, 1],
    "Orange": [1.0,  0.6,  0.1,  1],
    "Amber":  [1.0,  0.82, 0.0,  1],
}

SERVICIOS_MAP = {s.clave: s for s in SERVICIOS}


@dataclass
class Trayecto:
    id:                  str
    fecha_inicio:        str
    fecha_fin:           str   = ""
    segundos_parado:     float = 0.0
    segundos_movimiento: float = 0.0
    importe_total:       float = 0.0
    conductor:           str   = ""
    servicio:            str   = "economico"

    def to_dict(self):     return asdict(self)
    @classmethod
    def from_dict(cls, d):
        d.setdefault("servicio", "economico")
        return cls(**d)


# ══════════════════════════════════════════════════════════════════════════════
# GESTORES
# ══════════════════════════════════════════════════════════════════════════════

class GestorConfig:
    def __init__(self):
        self._tarifa = self._cargar()

    def _cargar(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return Tarifa.from_dict(json.load(f))
            except Exception as e:
                logger.warning(f"Config error: {e}")
        return Tarifa()

    def guardar(self):

        try:
            
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
             
                json.dump(
                    [t.to_dict() for t in self._trayectos],
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            logger.info("Historial guardado correctamente.")

        except Exception as e:

            logger.error(f"Error guardando historial: {e}")

    @property
    def tarifa(self): return self._tarifa


class GestorHistorial:
    def __init__(self):
        self._trayectos = self._cargar()

    def _cargar(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return [Trayecto.from_dict(t) for t in json.load(f)]
            except Exception as e:
                logger.warning(f"Historial error: {e}")
        return []

    def guardar(self):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in self._trayectos], f, indent=2, ensure_ascii=False)

    def agregar(self, trayecto):
        self._trayectos.append(trayecto)
        self.guardar()

    @property
    def trayectos(self): return self._trayectos


class GestorAuth:
    def __init__(self):
        self._usuarios = self._cargar()
        if not self._usuarios:
            self._crear_default()

    def _cargar(self):
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {}

    def _guardar(self):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._usuarios, f, indent=2)

    def _hash(self, p): return hashlib.sha256(p.encode()).hexdigest()

    def _crear_default(self):
        self._usuarios["admin"] = {"hash": self._hash("1234"), "rol": "admin"}
        self._guardar()

    def autenticar(self, usuario, password):
        if usuario in self._usuarios:
            return self._usuarios[usuario]["hash"] == self._hash(password)
        return False
    
    def cambiar_password(self, usuario, nueva_password):

        if usuario in self._usuarios:

            self._usuarios[usuario]["hash"] = (
             self._hash(nueva_password)
            )

            self._guardar()

            return True

        return False


# ══════════════════════════════════════════════════════════════════════════════
# GENERADOR DE FACTURAS PDF
# ══════════════════════════════════════════════════════════════════════════════

def generar_factura_pdf(trayecto: Trayecto, servicio: TipoServicio, tarifa: Tarifa) -> str:
    nombre_archivo = f"factura_{trayecto.id}.pdf"
    ruta = os.path.join(FACTURAS_DIR, nombre_archivo)

    doc = SimpleDocTemplate(
        ruta, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm,   bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()
    story  = []

    estilo_titulo = ParagraphStyle("titulo", parent=styles["Title"],
        fontSize=22, textColor=colors.HexColor("#1a1a2e"), spaceAfter=6)
    estilo_subtitulo = ParagraphStyle("subtitulo", parent=styles["Normal"],
        fontSize=11, textColor=colors.HexColor("#555555"), spaceAfter=4)

    story.append(Paragraph("TAXIMETRO DIGITAL", estilo_titulo))
    story.append(Paragraph("Factura de Trayecto", estilo_subtitulo))
    story.append(HRFlowable(width="100%", thickness=2,
                            color=colors.HexColor("#1a1a2e"), spaceAfter=12))

    def fmt_fecha(iso):
        try:    return datetime.fromisoformat(iso).strftime("%d/%m/%Y  %H:%M:%S")
        except: return iso

    total_segs = int(trayecto.segundos_parado + trayecto.segundos_movimiento)
    h = total_segs // 3600
    m = (total_segs % 3600) // 60
    s = total_segs % 60
    duracion_str = f"{h:02d}h {m:02d}m {s:02d}s"

    datos = [
        ["CONCEPTO",             "DETALLE"],
        ["Nro. de Trayecto",     trayecto.id],
        ["Tipo de Servicio",     servicio.nombre],
        ["Inicio del viaje",     fmt_fecha(trayecto.fecha_inicio)],
        ["Fin del viaje",        fmt_fecha(trayecto.fecha_fin)],
        ["Duracion total",       duracion_str],
        ["Tiempo en movimiento", f"{int(trayecto.segundos_movimiento)}s"],
        ["Tiempo parado",        f"{int(trayecto.segundos_parado)}s"],
    ]

    tabla = Table(datos, colWidths=[6*cm, 10*cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND",     (0,0),(-1,0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",      (0,0),(-1,0), colors.white),
        ("FONTNAME",       (0,0),(-1,0), "Helvetica-Bold"),
        ("FONTSIZE",       (0,0),(-1,0), 10),
        ("ALIGN",          (0,0),(-1,0), "CENTER"),
        ("FONTSIZE",       (0,1),(-1,-1), 9),
        ("FONTNAME",       (0,1),(0,-1),  "Helvetica-Bold"),
        ("TEXTCOLOR",      (0,1),(0,-1),  colors.HexColor("#1a1a2e")),
        ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.HexColor("#f5f5f5"), colors.white]),
        ("GRID",           (0,0),(-1,-1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING",     (0,0),(-1,-1), 6),
        ("BOTTOMPADDING",  (0,0),(-1,-1), 6),
        ("LEFTPADDING",    (0,0),(-1,-1), 8),
    ]))
    story.append(tabla)
    story.append(Spacer(1, 16))

    story.append(HRFlowable(width="100%", thickness=1,
                            color=colors.HexColor("#aaaaaa"), spaceAfter=8))
    story.append(Paragraph("Desglose de tarifas", estilo_subtitulo))

    coste_mov    = trayecto.segundos_movimiento * tarifa.precio_movimiento * servicio.multiplicador
    coste_parado = trayecto.segundos_parado     * tarifa.precio_parado     * servicio.multiplicador

    desglose = [
        ["Concepto",                              "Importe"],
        ["Bajada de bandera",                     f"{tarifa.precio_bajada_bandera:.2f} EUR"],
        [f"Cargo fijo ({servicio.nombre})",       f"{servicio.cargo_fijo:.2f} EUR"],
        [f"Tiempo movimiento x{servicio.multiplicador}", f"{coste_mov:.2f} EUR"],
        [f"Tiempo parado x{servicio.multiplicador}",     f"{coste_parado:.2f} EUR"],
    ]
    td = Table(desglose, colWidths=[10*cm, 6*cm])
    td.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), colors.HexColor("#2c2c54")),
        ("TEXTCOLOR",     (0,0),(-1,0), colors.white),
        ("FONTNAME",      (0,0),(-1,0), "Helvetica-Bold"),
        ("ALIGN",         (1,0),(1,-1), "RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#f5f5f5"), colors.white]),
        ("GRID",          (0,0),(-1,-1), 0.5, colors.HexColor("#cccccc")),
        ("FONTSIZE",      (0,0),(-1,-1), 9),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
    ]))
    story.append(td)
    story.append(Spacer(1, 20))

    story.append(HRFlowable(width="100%", thickness=2,
                            color=colors.HexColor("#1a1a2e"), spaceAfter=10))
    tt = Table([["TOTAL A PAGAR", f"{trayecto.importe_total:.2f} EUR"]],
               colWidths=[10*cm, 6*cm])
    tt.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",    (0,0),(-1,-1), colors.white),
        ("FONTNAME",     (0,0),(-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0),(-1,-1), 14),
        ("ALIGN",        (1,0),(1,0),   "RIGHT"),
        ("TOPPADDING",   (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING",  (0,0),(-1,-1), 12),
        ("RIGHTPADDING", (0,0),(-1,-1), 12),
    ]))
    story.append(tt)
    story.append(Spacer(1, 30))
    story.append(HRFlowable(width="100%", thickness=1,
                            color=colors.HexColor("#aaaaaa"), spaceAfter=6))
    story.append(Paragraph(
        "Gracias por utilizar Taximetro Digital · Factura generada automaticamente",
        ParagraphStyle("pie", parent=styles["Normal"],
                       fontSize=8, textColor=colors.grey, alignment=1)
    ))
    doc.build(story)
    logger.info(f"Factura PDF generada: {ruta}")
    return ruta


# ══════════════════════════════════════════════════════════════════════════════
# WIDGET PERSONALIZADO
# ══════════════════════════════════════════════════════════════════════════════

class ServiceListItem(OneLineAvatarListItem):
    icon_name     = StringProperty("car")
    service_name  = StringProperty("")
    service_color = ListProperty([1, 1, 1, 1])


# ══════════════════════════════════════════════════════════════════════════════
# KV — INTERFAZ MODO OSCURO
# ══════════════════════════════════════════════════════════════════════════════

KV = '''
#:import dp kivy.metrics.dp

<ServiceListItem>:
    text: root.service_name
    theme_text_color: "Custom"
    text_color: 1, 1, 1, 1
    canvas.before:
        Color:
            rgba: 0.12, 0.12, 0.18, 1
        Rectangle:
            pos: self.pos
            size: self.size
    IconLeftWidget:
        icon: root.icon_name
        theme_text_color: "Custom"
        text_color: root.service_color

MDBoxLayout:
    orientation: "vertical"
    padding: dp(6)
    spacing: dp(4)
    md_bg_color: 0.07, 0.07, 0.12, 1

    MDBoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: dp(46)
        spacing: dp(12)
        padding: [dp(4), 0, 0, 0]
        MDIcon:
            icon: "taxi"
            size_hint: None, None
            size: dp(36), dp(36)
            pos_hint: {"center_y": .5}
            theme_text_color: "Custom"
            text_color: 1.0, 0.82, 0.0, 1
        MDLabel:
            text: "Taximetro Digital"
            font_style: "H5"
            pos_hint: {"center_y": .5}
            theme_text_color: "Custom"
            text_color: 1, 1, 1, 1
        MDFillRoundFlatIconButton:
            text: "Salir"
            icon: "logout"
            size_hint_x: None
            width: dp(90)
            height: dp(36)
            md_bg_color: 0.8, 0.2, 0.2, 1
            on_release: app.cerrar_sesion()

    MDBoxLayout:
        size_hint_y: None
        height: dp(1)
        md_bg_color: 1, 1, 1, 0.3

    MDLabel:
        text: "Tipo de Servicio"
        font_style: "H6"
        size_hint_y: None
        height: dp(28)
        theme_text_color: "Custom"
        text_color: 1, 1, 1, 1

    ScrollView:
        size_hint_y: 0.24
        MDList:
            id: service_list
            canvas.before:
                Color:
                    rgba: 0.12, 0.12, 0.18, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

    MDBoxLayout:
        size_hint_y: None
        height: dp(1)
        md_bg_color: 1, 1, 1, 0.3

    MDCard:
        orientation: "vertical"
        padding: [dp(14), dp(8), dp(14), dp(8)]
        spacing: dp(2)
        size_hint_y: None
        height: dp(95)
        radius: [dp(16)]
        elevation: 4
        md_bg_color: 0.12, 0.12, 0.22, 1

        MDBoxLayout:
            orientation: "horizontal"
            size_hint_y: None
            height: dp(26)
            spacing: dp(8)
            MDIcon:
                icon: "navigation"
                size_hint: None, None
                size: dp(20), dp(20)
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 0.7
            MDLabel:
                id: lbl_estado
                text: "ESPERANDO..."
                font_style: "Button"
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 0.85

        MDLabel:
            id: lbl_precio
            text: "0.00 EUR"
            font_style: "H3"
            halign: "center"
            theme_text_color: "Custom"
            text_color: 1.0, 0.82, 0.0, 1

        MDLabel:
            id: lbl_servicio
            text: "Servicio: Economico"
            font_style: "Caption"
            halign: "center"
            theme_text_color: "Custom"
            text_color: 1, 1, 1, 0.65

        MDLabel:
            id: lbl_cronometro
            text: "00h 00m 00s"
            font_style: "Caption"
            halign: "center"
            theme_text_color: "Custom"
            text_color: 1, 1, 1, 0.65

    MDCard:
        orientation: "vertical"
        padding: [dp(14), dp(6), dp(14), dp(6)]
        size_hint_y: None
        height: dp(75)
        radius: [dp(12)]
        elevation: 2
        md_bg_color: 0.10, 0.10, 0.18, 1

        MDBoxLayout:
            orientation: "horizontal"
            spacing: dp(4)
            MDLabel:
                id: lbl_inicio
                text: "Inicio: --:--:--"
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 0.7
                halign: "center"
            MDLabel:
                id: lbl_fin
                text: "Fin: --:--:--"
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 0.7
                halign: "center"

        MDBoxLayout:
            orientation: "horizontal"
            spacing: dp(4)
            MDLabel:
                id: lbl_t_movimiento
                text: "Mov: 0s"
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: 0.20, 0.85, 0.45, 1
                halign: "center"
            MDLabel:
                id: lbl_t_parado
                text: "Parado: 0s"
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: 1.0, 0.82, 0.0, 1
                halign: "center"

        MDLabel:
            id: lbl_resumen
            text: ""
            font_style: "Caption"
            halign: "center"
            theme_text_color: "Custom"
            text_color: 0.4, 0.9, 0.5, 1

        MDBoxLayout:
            orientation: "vertical"
            spacing: dp(8)
            size_hint_y: None
            height: dp(120)
            padding: [0, dp(4), 0, 0]

            MDBoxLayout:
                orientation: "horizontal"
                spacing: dp(8)

                MDFillRoundFlatIconButton:
                    id: btn_activar
                    icon: "play-circle-outline"
                    text: "Activar"
                    font_size: "12sp"
                    icon_size: dp(20)
                    md_bg_color: 0.13, 0.70, 0.37, 1
                    text_color: 1, 1, 1, 1
                    size_hint_x: 1
                    height: dp(42)
                    on_release: app.iniciar_taximetro()

                MDFillRoundFlatIconButton:
                    id: btn_parar
                    icon: "pause-circle-outline"
                    text: "Parar"
                    font_size: "12sp"
                    icon_size: dp(20)
                    md_bg_color: 0.95, 0.76, 0.05, 1
                    text_color: 0.10, 0.10, 0.10, 1
                    size_hint_x: 1
                    height: dp(42)
                    on_release: app.pausar_taximetro()

            MDBoxLayout:
                orientation: "horizontal"
                spacing: dp(8)

                MDFillRoundFlatIconButton:
                    id: btn_historial
                    icon: "history"
                    text: "Historial"
                    font_size: "12sp"
                    icon_size: dp(20)
                    md_bg_color: 1.0, 0.6, 0.1, 1
                    text_color: 0, 0, 0, 1
                    size_hint_x: 1
                    height: dp(42)
                    on_release: app.ver_historial()

                MDFillRoundFlatIconButton:
                    id: btn_finalizar
                    icon: "stop-circle-outline"
                    text: "Finalizar"
                    font_size: "12sp"
                    icon_size: dp(20)
                    md_bg_color: 0.88, 0.20, 0.18, 1
                    text_color: 1, 1, 1, 1
                    size_hint_x: 1
                    height: dp(42)
                    on_release: app.finalizar_taximetro()

        MDFillRoundFlatIconButton:
            id: btn_factura
            icon: "file-pdf-box"
            text: "Generar Factura PDF"
            font_size: "13sp"
            icon_size: dp(22)
            md_bg_color: 0.20, 0.35, 0.75, 1
            text_color: 1, 1, 1, 1
            size_hint_y: None
            height: dp(40)
            on_release: app.generar_factura()  

'''


# ══════════════════════════════════════════════════════════════════════════════
# APLICACION PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class TaximetroApp(MDApp):

    _activo           = False
    _pausado          = False
    _segundos_parado  = 0.0
    _segs_movimiento  = 0.0
    _importe          = 0.0
    _clock_event      = None
    _servicio_actual  = None
    _trayecto_actual  = None
    _ultimo_trayecto  = None
    _dialog_login     = None
    _usuario_actual   = None

    def mostrar_login(self):

        self.user_field = MDTextField(
            hint_text="Usuario",
            helper_text="Ingrese usuario",
            helper_text_mode="on_focus"
        )

        self.pass_field = MDTextField(
            hint_text="Contraseña",
            password=True,
            helper_text="Ingrese contraseña",
            helper_text_mode="on_focus"
        )

        self._dialog_login = MDDialog(
            title="Iniciar Sesión",
            type="custom",
            content_cls=MDBoxLayout(
                self.user_field,
                self.pass_field,
                orientation="vertical",
                spacing="12dp",
                size_hint_y=None,
                height="120dp",
            ),
            buttons=[
                MDFlatButton(
                    text="LOGIN",
                    on_release=lambda x: self.validar_login()
                )
            ]
        )

        self._dialog_login.open()

    def validar_login(self):

        usuario = self.user_field.text.strip()

        password = self.pass_field.text.strip()

        if self._gestor_auth.autenticar(usuario, password):

            self._usuario_actual = usuario

            self._dialog_login.dismiss()

            self.root.ids.lbl_resumen.text = (
            f"Bienvenido {usuario}"
            )

            logger.info(f"Login exitoso: {usuario}")

        else:

            self.pass_field.error = True

            self.root.ids.lbl_resumen.text = (
                "Usuario o contraseña incorrectos"
            )

            logger.warning(
             f"Intento login fallido: {usuario}"
            )

    def cerrar_sesion(self):

        self._usuario_actual = None

        self.root.ids.lbl_resumen.text = (
        "Sesion cerrada"
        ) 

        logger.info("Sesion cerrada.")

        Clock.schedule_once(
            lambda dt: self.mostrar_login(),
            0.5
        )

    def build(self):
        self.theme_cls.theme_style     = "Dark"
        self.theme_cls.primary_palette = "Amber"
        self._gestor_config    = GestorConfig()
        self._gestor_historial = GestorHistorial()
        self._gestor_auth      = GestorAuth()
        self._servicio_actual  = SERVICIOS_MAP["economico"]
        return Builder.load_string(KV)

    def on_start(self):
        service_list = self.root.ids.service_list
        for servicio in SERVICIOS:
            item = ServiceListItem(
                icon_name     = servicio.icon_name,
                service_name  = servicio.nombre,
                service_color = COLORES.get(servicio.color_name, [1, 1, 1, 1]),
            )
            item.bind(on_release=lambda x, s=servicio: self._seleccionar_servicio(s))
            service_list.add_widget(item)
        logger.info("App iniciada correctamente.")
        Clock.schedule_once(lambda dt: self.mostrar_login(), 0.5)

    def _seleccionar_servicio(self, servicio):
        if self._activo:
            return
        self._servicio_actual = servicio
        self.root.ids.lbl_servicio.text = f"Servicio: {servicio.nombre}"
        logger.info(f"Servicio: {servicio.nombre}")

    def iniciar_taximetro(self):

        tarifa = self._gestor_config.tarifa

        # Si NO existe trayecto, crear uno nuevo
        if self._trayecto_actual is None:

            ahora = datetime.now()

            self._trayecto_actual = Trayecto(
                id=ahora.strftime("%Y%m%d_%H%M%S"),
                fecha_inicio=ahora.isoformat(),
                servicio=self._servicio_actual.clave,
            )

            self._importe = (
                tarifa.precio_bajada_bandera
                + self._servicio_actual.cargo_fijo
            )

            self.root.ids.lbl_inicio.text = (
                f"Inicio: {ahora.strftime('%H:%M:%S')}"
            )

            self.root.ids.lbl_fin.text = "Fin: --:--:--"

        # IMPORTANTE
        self._activo = True
        self._pausado = False

        self.root.ids.lbl_estado.text = "EN MOVIMIENTO..."

        # Crear clock SOLO si no existe
        if self._clock_event is None:

            self._clock_event = Clock.schedule_interval(
                self._tick,
                1.0
            )

        logger.info("Trayecto iniciado/reanudado.")

    def pausar_taximetro(self):

        if not self._activo:
            return

        self._pausado = True

        self.root.ids.lbl_estado.text = "PARADO"

        logger.info("Taximetro pausado.")

    def finalizar_taximetro(self):

        try:

            if self._trayecto_actual is None:
                return

            if self._clock_event:

                self._clock_event.cancel()

                self._clock_event = None

            ahora = datetime.now()

            self._trayecto_actual.fecha_fin = ahora.isoformat()

            self._trayecto_actual.segundos_parado = self._segundos_parado

            self._trayecto_actual.segundos_movimiento = self._segs_movimiento

            self._trayecto_actual.importe_total = round(
                self._importe,
                2
            )

            self._gestor_historial.agregar(
                self._trayecto_actual
            )

            self._ultimo_trayecto = self._trayecto_actual

            self.root.ids.lbl_fin.text = (
                f"Fin: {ahora.strftime('%H:%M:%S')}"
            )

            self.root.ids.lbl_estado.text = "FINALIZADO"

            self.root.ids.lbl_resumen.text = (
                f"Total: {self._importe:.2f} EUR"
            )

            logger.info(
                f"Trayecto finalizado correctamente."
            )

            self._trayecto_actual = None

            self._segundos_parado = 0.0

            self._segs_movimiento = 0.0

            self._importe = 0.0

            self._activo = False

            self._pausado = False

        except Exception as e:

            logger.error(f"Error finalizando trayecto: {e}")

            self.root.ids.lbl_resumen.text = (
                f"Error al finalizar: {e}"
            )

    def _tick(self, dt):

        if self._trayecto_actual is None:
            return

        tarifa = self._gestor_config.tarifa
        mult = self._servicio_actual.multiplicador

        if self._pausado:

            self._segundos_parado += 1

            self._importe += tarifa.precio_parado * mult

        else:

            self._segs_movimiento += 1

            self._importe += tarifa.precio_movimiento * mult

        self.root.ids.lbl_precio.text = f"{self._importe:.2f} EUR"

        total = int(self._segs_movimiento + self._segundos_parado)

        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60

        self.root.ids.lbl_cronometro.text = (
            f"{h:02d}h {m:02d}m {s:02d}s"
        )

        self.root.ids.lbl_t_movimiento.text = (
            f"Mov: {int(self._segs_movimiento)}s"
        )

        self.root.ids.lbl_t_parado.text = (
            f"Parado: {int(self._segundos_parado)}s"
        )

    def ver_historial(self):

        contenido = MDBoxLayout(
            orientation="vertical",
            spacing="10dp",
            size_hint_y=None
        )

        contenido.bind(
            minimum_height=contenido.setter("height")
        )

        trayectos = self._gestor_historial.trayectos

        if not trayectos:

            contenido.add_widget(

                MDLabel(
                    text="No hay trayectos registrados.",
                    halign="center"
                )
            )

        else:

            for t in reversed(trayectos):

                texto = (
                    f"[b]{t.id}[/b]\n"
                    f"Total: {t.importe_total:.2f} EUR\n"
                    f"Mov: {int(t.segundos_movimiento)}s\n"
                    f"Parado: {int(t.segundos_parado)}s"
                )

                contenido.add_widget(

                    MDLabel(
                        text=texto,
                        markup=True,
                        size_hint_y=None,
                        height="90dp"
                    )
                )

        scroll = MDScrollView()

        scroll.add_widget(contenido)

        dialog = MDDialog(
            title="Historial de Trayectos",
            type="custom",
            content_cls=scroll,
            size_hint=(0.9, 0.8),
        )

        dialog.open()

    def generar_factura(self):
        if self._ultimo_trayecto is None:
            self.root.ids.lbl_resumen.text = "Finaliza un trayecto primero."
            return
        servicio = SERVICIOS_MAP.get(self._ultimo_trayecto.servicio, SERVICIOS_MAP["economico"])
        tarifa   = self._gestor_config.tarifa
        try:
            ruta = generar_factura_pdf(self._ultimo_trayecto, servicio, tarifa)
            self.root.ids.lbl_resumen.text = f"Factura guardada:\n{os.path.basename(ruta)}"
        except Exception as e:
            self.root.ids.lbl_resumen.text = f"Error PDF: {e}"
            logger.error(f"Error PDF: {e}")

    def _resetear_ui(self, *args):
        self.root.ids.lbl_precio.text       = "0.00 EUR"
        self.root.ids.lbl_estado.text       = "ESPERANDO..."
        self.root.ids.lbl_cronometro.text   = "00h 00m 00s"
        self.root.ids.lbl_t_movimiento.text = "Mov: 0s"
        self.root.ids.lbl_t_parado.text     = "Parado: 0s"
        self.root.ids.lbl_inicio.text       = "Inicio: --:--:--"
        self.root.ids.lbl_fin.text          = "Fin: --:--:--"


# ══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    TaximetroApp().run()