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
from kivymd.uix.boxlayout  import MDBoxLayout
from kivymd.uix.button     import MDFillRoundFlatIconButton, MDFlatButton
from kivymd.uix.label      import MDLabel, MDIcon
from kivymd.uix.list       import OneLineAvatarListItem, IconLeftWidget
from kivymd.uix.card       import MDCard, MDSeparator
from kivymd.uix.dialog     import MDDialog
from kivymd.uix.textfield  import MDTextField
from kivymd.uix.scrollview import MDScrollView
from kivy.properties       import StringProperty, ListProperty
from kivy.metrics          import dp

from reportlab.lib.pagesizes import A4
from reportlab.lib           import colors
from reportlab.platypus      import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle, HRFlowable)
from reportlab.lib.styles    import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units     import cm


# ══════════════════════════════════════════════════════════════════════════════
# RUTAS Y LOGGING
# ══════════════════════════════════════════════════════════════════════════════

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "historial.json")
CONFIG_FILE  = os.path.join(BASE_DIR, "config.json")
USERS_FILE   = os.path.join(BASE_DIR, "usuarios.json")
FACTURAS_DIR = os.path.join(BASE_DIR, "facturas")
LOG_FILE     = os.path.join(BASE_DIR, "taximetro.log")
os.makedirs(FACTURAS_DIR, exist_ok=True)

logger = logging.getLogger("Taximetro")
logger.setLevel(logging.INFO)

if not logger.handlers:
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    fh  = logging.FileHandler(LOG_FILE, encoding="utf-8", delay=False)
    fh.setFormatter(fmt)
    ch  = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.propagate = False

logger.info(f"Logger iniciado. Log: {LOG_FILE}")


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
    clave: str; nombre: str; icon_name: str
    descripcion: str; cargo_fijo: float
    multiplicador: float; color_name: str


SERVICIOS = [
    TipoServicio("economico",  "Economico",    "car",              "Tarifa estandar",             0.0,  1.0, "White"),
    TipoServicio("xl",         "XL / Familiar","account-group",    "Vehiculo de mayor capacidad", 2.00, 1.4, "Blue"),
    TipoServicio("compartido", "Compartido",   "account-multiple", "Viaje compartido",            0.0,  0.6, "Teal"),
    TipoServicio("pet",        "Pet Friendly", "paw",              "Mascotas permitidas",         1.50, 1.0, "Orange"),
    TipoServicio("flash",      "Flash",        "lightning-bolt",   "Recogida prioritaria",        3.00, 1.2, "Amber"),
]

COLORES = {
    "White":  [1.0, 1.0, 1.0, 1],
    "Blue":   [0.25,0.55,1.0, 1],
    "Teal":   [0.0, 0.75,0.75,1],
    "Orange": [1.0, 0.6, 0.1, 1],
    "Amber":  [1.0, 0.82,0.0, 1],
}

SERVICIOS_MAP = {s.clave: s for s in SERVICIOS}


@dataclass
class Trayecto:
    id: str; fecha_inicio: str
    fecha_fin: str = ""; segundos_parado: float = 0.0
    segundos_movimiento: float = 0.0; importe_total: float = 0.0
    conductor: str = ""; servicio: str = "economico"
    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d):
        d.setdefault("servicio", "economico"); return cls(**d)


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
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._tarifa.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando config: {e}")
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
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([t.to_dict() for t in self._trayectos], f, indent=2, ensure_ascii=False)
            logger.info("Historial guardado.")
        except Exception as e:
            logger.error(f"Error guardando historial: {e}")
    def agregar(self, t):
        self._trayectos.append(t); self.guardar()
    @property
    def trayectos(self): return self._trayectos


class GestorAuth:
    def __init__(self):
        self._usuarios = self._cargar()
        if not self._usuarios: self._crear_default()
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
        logger.info("Usuario por defecto: admin / 1234")
    def autenticar(self, u, p):
        return u in self._usuarios and self._usuarios[u]["hash"] == self._hash(p)
    def cambiar_password(self, u, nueva):
        if u in self._usuarios:
            self._usuarios[u]["hash"] = self._hash(nueva)
            self._guardar(); return True
        return False


# ══════════════════════════════════════════════════════════════════════════════
# GENERADOR PDF
# ══════════════════════════════════════════════════════════════════════════════

def generar_factura_pdf(trayecto, servicio, tarifa):
    ruta = os.path.join(FACTURAS_DIR, f"factura_{trayecto.id}.pdf")
    doc  = SimpleDocTemplate(ruta, pagesize=A4,
               rightMargin=2*cm, leftMargin=2*cm,
               topMargin=2*cm,   bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story  = []

    s_tit = ParagraphStyle("t", parent=styles["Title"],
                fontSize=22, textColor=colors.HexColor("#1a1a2e"), spaceAfter=6)
    s_sub = ParagraphStyle("s", parent=styles["Normal"],
                fontSize=11, textColor=colors.HexColor("#555"), spaceAfter=4)
    s_pie = ParagraphStyle("p", parent=styles["Normal"],
                fontSize=8,  textColor=colors.grey, alignment=1)

    def fmt(iso):
        try:    return datetime.fromisoformat(iso).strftime("%d/%m/%Y  %H:%M:%S")
        except: return iso

    ts = int(trayecto.segundos_parado + trayecto.segundos_movimiento)
    dur = f"{ts//3600:02d}h {(ts%3600)//60:02d}m {ts%60:02d}s"

    story += [
        Paragraph("TAXIMETRO DIGITAL", s_tit),
        Paragraph("Factura de Trayecto", s_sub),
        HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a1a2e"), spaceAfter=12),
    ]

    def tabla(datos, cols):
        t = Table(datos, colWidths=cols)
        t.setStyle(TableStyle([
            ("BACKGROUND",     (0,0),(-1,0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR",      (0,0),(-1,0), colors.white),
            ("FONTNAME",       (0,0),(-1,0), "Helvetica-Bold"),
            ("FONTSIZE",       (0,0),(-1,-1), 9),
            ("FONTNAME",       (0,1),(0,-1),  "Helvetica-Bold"),
            ("TEXTCOLOR",      (0,1),(0,-1),  colors.HexColor("#1a1a2e")),
            ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.HexColor("#f5f5f5"), colors.white]),
            ("GRID",           (0,0),(-1,-1), 0.5, colors.HexColor("#ccc")),
            ("TOPPADDING",     (0,0),(-1,-1), 5),
            ("BOTTOMPADDING",  (0,0),(-1,-1), 5),
            ("LEFTPADDING",    (0,0),(-1,-1), 8),
            ("ALIGN",          (1,0),(1,-1),  "RIGHT"),
        ]))
        return t

    story.append(tabla([
        ["CONCEPTO", "DETALLE"],
        ["Nro. Trayecto",        trayecto.id],
        ["Tipo de Servicio",     servicio.nombre],
        ["Inicio",               fmt(trayecto.fecha_inicio)],
        ["Fin",                  fmt(trayecto.fecha_fin)],
        ["Duracion total",       dur],
        ["Tiempo movimiento",    f"{int(trayecto.segundos_movimiento)}s"],
        ["Tiempo parado",        f"{int(trayecto.segundos_parado)}s"],
    ], [6*cm, 10*cm]))

    story += [Spacer(1, 14),
              HRFlowable(width="100%", thickness=1, color=colors.HexColor("#aaa"), spaceAfter=8),
              Paragraph("Desglose de tarifas", s_sub)]

    cm_mov    = trayecto.segundos_movimiento * tarifa.precio_movimiento * servicio.multiplicador
    cm_parado = trayecto.segundos_parado     * tarifa.precio_parado     * servicio.multiplicador

    story.append(tabla([
        ["Concepto",                                    "Importe"],
        ["Bajada de bandera",                           f"{tarifa.precio_bajada_bandera:.2f} EUR"],
        [f"Cargo fijo ({servicio.nombre})",             f"{servicio.cargo_fijo:.2f} EUR"],
        [f"Movimiento x{servicio.multiplicador}",       f"{cm_mov:.2f} EUR"],
        [f"Parado x{servicio.multiplicador}",           f"{cm_parado:.2f} EUR"],
    ], [10*cm, 6*cm]))

    story += [Spacer(1, 18),
              HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a1a2e"), spaceAfter=10)]

    tt = Table([["TOTAL A PAGAR", f"{trayecto.importe_total:.2f} EUR"]], colWidths=[10*cm, 6*cm])
    tt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR",     (0,0),(-1,-1), colors.white),
        ("FONTNAME",      (0,0),(-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,-1), 14),
        ("ALIGN",         (1,0),(1,0),   "RIGHT"),
        ("TOPPADDING",    (0,0),(-1,-1), 10),
        ("BOTTOMPADDING", (0,0),(-1,-1), 10),
        ("LEFTPADDING",   (0,0),(-1,-1), 12),
        ("RIGHTPADDING",  (0,0),(-1,-1), 12),
    ]))
    story += [tt, Spacer(1, 24),
              HRFlowable(width="100%", thickness=1, color=colors.HexColor("#aaa"), spaceAfter=6),
              Paragraph("Gracias por utilizar Taximetro Digital · Factura generada automaticamente", s_pie)]

    doc.build(story)
    logger.info(f"Factura PDF generada: {ruta}")
    return ruta


# ══════════════════════════════════════════════════════════════════════════════
# WIDGET: ítem de servicio
# ══════════════════════════════════════════════════════════════════════════════

class ServiceListItem(OneLineAvatarListItem):
    icon_name     = StringProperty("car")
    service_name  = StringProperty("")
    service_color = ListProperty([1, 1, 1, 1])


# ══════════════════════════════════════════════════════════════════════════════
# KV
#
# Cálculo de alturas para ventana 440×680 (padding=6 v/h, spacing=5):
#   Encabezado  : 44
#   Separador   :  1
#   Label tipo  : 22
#   Lista×5     : 280  (56 × 5)
#   Separador   :  1
#   Card info   : 148
#   Fila botones: 44
#   Fila botones: 44
#   Btn factura : 44
#   ──────────────────
#   Subtotal    : 628
#   Spacing ×8  :  40
#   Padding ×2  :  12
#   TOTAL       : 680  ✓
# ══════════════════════════════════════════════════════════════════════════════

KV = '''
#:import dp kivy.metrics.dp

# ── Ítem de servicio: altura fija dp(56), separador inferior blanco ───────────
<ServiceListItem>:
    text: root.service_name
    theme_text_color: "Custom"
    text_color: 1, 1, 1, 1
    size_hint_y: None
    height: dp(56)
    canvas.before:
        Color:
            rgba: 0.12, 0.12, 0.18, 1
        Rectangle:
            pos: self.pos
            size: self.size
    canvas.after:
        Color:
            rgba: 1, 1, 1, 0.18
        Rectangle:
            pos: self.x, self.y
            size: self.width, dp(1)
    IconLeftWidget:
        icon: root.icon_name
        theme_text_color: "Custom"
        text_color: root.service_color

# ── Layout raíz: fondo negro, todo visible, sin scroll externo ───────────────
MDBoxLayout:
    orientation: "vertical"
    padding: [dp(8), dp(6), dp(8), dp(6)]
    spacing: dp(5)
    canvas.before:
        Color:
            rgba: 0.07, 0.07, 0.12, 1
        Rectangle:
            pos: self.pos
            size: self.size

    # 1. ENCABEZADO ── h=44 ───────────────────────────────────────────────────
    MDBoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: dp(44)
        spacing: dp(8)

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
            height: dp(34)
            md_bg_color: 0.8, 0.2, 0.2, 1
            pos_hint: {"center_y": .5}
            on_release: app.cerrar_sesion()

    # 2. SEPARADOR ── h=1 ─────────────────────────────────────────────────────
    MDBoxLayout:
        size_hint_y: None
        height: dp(1)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 0.3
            Rectangle:
                pos: self.pos
                size: self.size

    # 3. LABEL TIPO DE SERVICIO ── h=22 ───────────────────────────────────────
    MDLabel:
        text: "Tipo de Servicio"
        font_style: "Subtitle1"
        size_hint_y: None
        height: dp(22)
        theme_text_color: "Custom"
        text_color: 1, 1, 1, 0.9

    # 4. LISTA DE SERVICIOS ── h=280 (5×56), SIN ScrollView ──────────────────
    # Usamos un MDBoxLayout con size_hint_y:None para que ocupe exactamente
    # el espacio calculado. Los ítems se añaden en on_start() con height=dp(56).
    MDBoxLayout:
        id: service_list
        orientation: "vertical"
        size_hint_y: None
        height: dp(280)
        spacing: 0
        padding: 0
        canvas.before:
            Color:
                rgba: 0.12, 0.12, 0.18, 1
            Rectangle:
                pos: self.pos
                size: self.size

    # 5. SEPARADOR ── h=1 ─────────────────────────────────────────────────────
    MDBoxLayout:
        size_hint_y: None
        height: dp(1)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 0.3
            Rectangle:
                pos: self.pos
                size: self.size

    # 6. CARD INFO ── h=148 ───────────────────────────────────────────────────
    MDCard:
        orientation: "vertical"
        padding: [dp(10), dp(6), dp(10), dp(4)]
        spacing: dp(2)
        size_hint_y: None
        height: dp(148)
        radius: [dp(12)]
        elevation: 4
        md_bg_color: 0.12, 0.12, 0.22, 1

        # Fila estado ── h≈24
        MDBoxLayout:
            orientation: "horizontal"
            size_hint_y: None
            height: dp(24)
            spacing: dp(6)
            MDIcon:
                icon: "navigation"
                size_hint: None, None
                size: dp(18), dp(18)
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 0.7
            MDLabel:
                id: lbl_estado
                text: "ESPERANDO..."
                font_style: "Button"
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 0.85

        # Precio ── h≈40
        MDLabel:
            id: lbl_precio
            text: "0.00 EUR"
            font_style: "H4"
            halign: "center"
            size_hint_y: None
            height: dp(40)
            theme_text_color: "Custom"
            text_color: 1.0, 0.82, 0.0, 1

        # Fila inicio / fin ── h≈20
        MDBoxLayout:
            orientation: "horizontal"
            size_hint_y: None
            height: dp(20)
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

        # Fila mov / parado / cronómetro ── h≈20
        MDBoxLayout:
            orientation: "horizontal"
            size_hint_y: None
            height: dp(20)
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
                id: lbl_cronometro
                text: "00h 00m 00s"
                font_style: "Caption"
                theme_text_color: "Custom"
                text_color: 1, 1, 1, 0.6
                halign: "center"

        # Resumen / mensajes ── h≈16
        MDLabel:
            id: lbl_resumen
            text: ""
            font_style: "Caption"
            halign: "center"
            size_hint_y: None
            height: dp(16)
            theme_text_color: "Custom"
            text_color: 0.4, 0.9, 0.5, 1

        # Servicio activo ── h≈14
        MDLabel:
            id: lbl_servicio
            text: "Servicio: Economico"
            font_style: "Caption"
            halign: "center"
            size_hint_y: None
            height: dp(14)
            theme_text_color: "Custom"
            text_color: 1, 1, 1, 0.5

    # 7. FILA: ACTIVAR / PARAR ── h=44 ───────────────────────────────────────
    MDBoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: dp(44)
        spacing: dp(8)

        MDFillRoundFlatIconButton:
            icon: "play-circle-outline"
            text: "Activar"
            font_size: "13sp"
            md_bg_color: 0.13, 0.70, 0.37, 1
            text_color: 1, 1, 1, 1
            size_hint_x: 1
            height: dp(44)
            on_release: app.iniciar_taximetro()

        MDFillRoundFlatIconButton:
            icon: "pause-circle-outline"
            text: "Parar"
            font_size: "13sp"
            md_bg_color: 0.95, 0.76, 0.05, 1
            text_color: 0.10, 0.10, 0.10, 1
            size_hint_x: 1
            height: dp(44)
            on_release: app.pausar_taximetro()

    # 8. FILA: HISTORIAL / FINALIZAR ── h=44 ─────────────────────────────────
    MDBoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: dp(44)
        spacing: dp(8)

        MDFillRoundFlatIconButton:
            icon: "history"
            text: "Historial"
            font_size: "13sp"
            md_bg_color: 1.0, 0.6, 0.1, 1
            text_color: 0, 0, 0, 1
            size_hint_x: 1
            height: dp(44)
            on_release: app.ver_historial()

        MDFillRoundFlatIconButton:
            icon: "stop-circle-outline"
            text: "Finalizar"
            font_size: "13sp"
            md_bg_color: 0.88, 0.20, 0.18, 1
            text_color: 1, 1, 1, 1
            size_hint_x: 1
            height: dp(44)
            on_release: app.finalizar_taximetro()

    # 9. BOTÓN FACTURA PDF — ancho completo ── h=44 ───────────────────────────
    MDFillRoundFlatIconButton:
        icon: "file-pdf-box"
        text: "Generar Factura PDF"
        font_size: "13sp"
        md_bg_color: 0.20, 0.35, 0.75, 1
        text_color: 1, 1, 1, 1
        size_hint_x: 1
        size_hint_y: None
        height: dp(44)
        on_release: app.generar_factura()
'''


# ══════════════════════════════════════════════════════════════════════════════
# APLICACION PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class TaximetroApp(MDApp):

    _activo = _pausado = False
    _segundos_parado = _segs_movimiento = _importe = 0.0
    _clock_event = _servicio_actual = _trayecto_actual = None
    _ultimo_trayecto = _dialog_login = _usuario_actual = None

    def build(self):
        self.theme_cls.theme_style     = "Dark"
        self.theme_cls.primary_palette = "Amber"
        self._gestor_config    = GestorConfig()
        self._gestor_historial = GestorHistorial()
        self._gestor_auth      = GestorAuth()
        self._servicio_actual  = SERVICIOS_MAP["economico"]
        return Builder.load_string(KV)

    def on_start(self):
        container = self.root.ids.service_list
        for servicio in SERVICIOS:
            item = ServiceListItem(
                icon_name     = servicio.icon_name,
                service_name  = servicio.nombre,
                service_color = COLORES.get(servicio.color_name, [1,1,1,1]),
            )
            item.bind(on_release=lambda x, s=servicio: self._seleccionar_servicio(s))
            container.add_widget(item)
        logger.info("App iniciada correctamente.")
        Clock.schedule_once(lambda dt: self.mostrar_login(), 0.5)

    # ── Login ─────────────────────────────────────────────────────────────────

    def mostrar_login(self):
        self.user_field = MDTextField(hint_text="Usuario",
            helper_text="Ingrese su usuario", helper_text_mode="on_focus")
        self.pass_field = MDTextField(hint_text="Contrasena", password=True,
            helper_text="Ingrese su contrasena", helper_text_mode="on_focus")
        self._dialog_login = MDDialog(
            title="Iniciar Sesión", type="custom",
            content_cls=MDBoxLayout(
                self.user_field, self.pass_field,
                orientation="vertical", spacing="12dp",
                size_hint_y=None, height="120dp"),
            buttons=[MDFlatButton(text="ENTRAR",
                                  on_release=lambda x: self.validar_login())])
        self._dialog_login.open()

    def validar_login(self):
        u, p = self.user_field.text.strip(), self.pass_field.text.strip()
        if self._gestor_auth.autenticar(u, p):
            self._usuario_actual = u
            self._dialog_login.dismiss()
            self.root.ids.lbl_resumen.text = f"Bienvenido {u}"
            logger.info(f"Login exitoso: {u}")
        else:
            self.pass_field.error = True
            self.root.ids.lbl_resumen.text = "Usuario o contrasena incorrectos"
            logger.warning(f"Login fallido: {u}")

    def cerrar_sesion(self):
        self._usuario_actual = None
        self.root.ids.lbl_resumen.text = "Sesion cerrada"
        logger.info("Sesion cerrada.")
        Clock.schedule_once(lambda dt: self.mostrar_login(), 0.5)

    # ── Servicio ──────────────────────────────────────────────────────────────

    def _seleccionar_servicio(self, s):
        if self._activo and not self._pausado:
            return
        self._servicio_actual = s
        self.root.ids.lbl_servicio.text = f"Servicio: {s.nombre}"
        logger.info(f"Servicio: {s.nombre}")

    # ── Taxímetro ─────────────────────────────────────────────────────────────

    def iniciar_taximetro(self):
        tarifa = self._gestor_config.tarifa
        if self._trayecto_actual is None:
            ahora = datetime.now()
            self._trayecto_actual = Trayecto(
                id=ahora.strftime("%Y%m%d_%H%M%S"),
                fecha_inicio=ahora.isoformat(),
                servicio=self._servicio_actual.clave)
            self._importe = tarifa.precio_bajada_bandera + self._servicio_actual.cargo_fijo
            self.root.ids.lbl_inicio.text  = f"Inicio: {ahora.strftime('%H:%M:%S')}"
            self.root.ids.lbl_fin.text     = "Fin: --:--:--"
            self.root.ids.lbl_resumen.text = ""
        self._activo = True
        self._pausado = False
        self.root.ids.lbl_estado.text = "EN MOVIMIENTO..."
        if self._clock_event is None:
            self._clock_event = Clock.schedule_interval(self._tick, 1.0)
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
            self._trayecto_actual.fecha_fin           = ahora.isoformat()
            self._trayecto_actual.segundos_parado     = self._segundos_parado
            self._trayecto_actual.segundos_movimiento = self._segs_movimiento
            self._trayecto_actual.importe_total       = round(self._importe, 2)
            self._gestor_historial.agregar(self._trayecto_actual)
            self._ultimo_trayecto = self._trayecto_actual
            self.root.ids.lbl_fin.text    = f"Fin: {ahora.strftime('%H:%M:%S')}"
            self.root.ids.lbl_estado.text = "FINALIZADO"
            self.root.ids.lbl_resumen.text = (
                f"Total: {self._importe:.2f} EUR | "
                f"Mov: {int(self._segs_movimiento)}s | "
                f"Parado: {int(self._segundos_parado)}s")
            logger.info(f"Trayecto finalizado: {self._importe:.2f} EUR")
            self._trayecto_actual = None
            self._segundos_parado = self._segs_movimiento = self._importe = 0.0
            self._activo = self._pausado = False
            Clock.schedule_once(self._resetear_ui, 6.0)
        except Exception as e:
            logger.error(f"Error finalizando: {e}")
            self.root.ids.lbl_resumen.text = f"Error: {e}"

    def _tick(self, dt):
        if self._trayecto_actual is None:
            return
        tarifa = self._gestor_config.tarifa
        mult   = self._servicio_actual.multiplicador
        if self._pausado:
            self._segundos_parado += 1
            self._importe += tarifa.precio_parado * mult
        else:
            self._segs_movimiento += 1
            self._importe += tarifa.precio_movimiento * mult
        self.root.ids.lbl_precio.text = f"{self._importe:.2f} EUR"
        total = int(self._segs_movimiento + self._segundos_parado)
        h, rem = divmod(total, 3600)
        m, s   = divmod(rem, 60)
        self.root.ids.lbl_cronometro.text   = f"{h:02d}h {m:02d}m {s:02d}s"
        self.root.ids.lbl_t_movimiento.text = f"Mov: {int(self._segs_movimiento)}s"
        self.root.ids.lbl_t_parado.text     = f"Parado: {int(self._segundos_parado)}s"

    # ── Historial ─────────────────────────────────────────────────────────────

    def ver_historial(self):
        contenido = MDBoxLayout(orientation="vertical", spacing="10dp", padding="10dp", size_hint_y=None)
        contenido.bind(minimum_height=contenido.setter("height"))
        trayectos = self._gestor_historial.trayectos
        if not trayectos:
            contenido.add_widget(MDLabel(text="No hay trayectos registrados.",halign="center", size_hint_y=None, height="40dp"))
        else:
            for t in reversed(trayectos):
                # Usamos una tarjeta para que cada trayecto sea visualmente independiente
                card = MDCard(orientation="vertical", padding=dp(12), size_hint_y=None, 
                              height=dp(100), md_bg_color=[0.15, 0.15, 0.25, 1], radius=[dp(10)])
            
                info = (f"[b]ID: {t.id}[/b]\n"
                                    f"Servicio: {t.servicio.upper()} | [color=FFD700]Total: {t.importe_total:.2f}€[/color]\n"
                                    f"Mov: {int(t.segundos_movimiento)}s | Parado: {int(t.segundos_parado)}s")
                            
                card.add_widget(MDLabel(text=info, markup=True, theme_text_color="Custom", 
                                                    text_color=[1,1,1,1], font_style="Caption"))
                contenido.add_widget(card)
        # ScrollView con altura limitada para forzar al Dialog a expandirse
        scroll = MDScrollView(size_hint_y=None, height=dp(400))
        scroll.add_widget(contenido)
        
        self._dialog_historial = MDDialog(
            title="Historial de Trayectos",
            type="custom",
            content_cls=scroll,
            size_hint=(0.9, None),
            height=dp(520), 
            buttons=[MDFlatButton(text="CERRAR", on_release=lambda x: self._dialog_historial.dismiss())]
        )
        self._dialog_historial.open()

    # ── Factura PDF ───────────────────────────────────────────────────────────

    def generar_factura(self):
        if self._ultimo_trayecto is None:
            self.root.ids.lbl_resumen.text = "Finaliza un trayecto primero."
            return
        s = SERVICIOS_MAP.get(self._ultimo_trayecto.servicio, SERVICIOS_MAP["economico"])
        try:
            ruta = generar_factura_pdf(self._ultimo_trayecto, s, self._gestor_config.tarifa)
            self.root.ids.lbl_resumen.text = f"PDF: facturas/{os.path.basename(ruta)}"
            logger.info(f"Factura generada: {ruta}")
        except Exception as e:
            self.root.ids.lbl_resumen.text = f"Error PDF: {e}"
            logger.error(f"Error PDF: {e}")

    # ── Reset UI ──────────────────────────────────────────────────────────────

    def _resetear_ui(self, *args):
        ids = self.root.ids
        ids.lbl_precio.text       = "0.00 EUR"
        ids.lbl_estado.text       = "ESPERANDO..."
        ids.lbl_cronometro.text   = "00h 00m 00s"
        ids.lbl_t_movimiento.text = "Mov: 0s"
        ids.lbl_t_parado.text     = "Parado: 0s"
        ids.lbl_inicio.text       = "Inicio: --:--:--"
        ids.lbl_fin.text          = "Fin: --:--:--"
        ids.lbl_resumen.text      = ""


# ══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    TaximetroApp().run()