# ══════════════════════════════════════════════════════════════════════════════
# PROYECTO NRO. 1
# Taxímetro Digital - Aplicación Principal
# Creado por: Johans Enrique Salas Rodríguez
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# LIBRERÍAS
# ══════════════════════════════════════════════════════════════════════════════

import os
import json
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Configuración de KivyMD y Kivy
from kivy.config import Config
# Configurar la ventana ANTES de importar cualquier otro módulo de Kivy/KivyMD
Config.set('graphics', 'width', '450')
Config.set('graphics', 'height', '750')
Config.set('graphics', 'resizable', False)

from kivymd.app import MDApp
from kivy.lang import Builder
from kivy.clock import Clock                          # FIX: faltaba este import
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.boxlayout import MDBoxLayout          # FIX: import explícito
from kivymd.uix.button import MDFillRoundFlatIconButton
from kivymd.uix.label import MDLabel, MDIcon          # FIX: MDIcon también
from kivymd.uix.list import (                         # FIX: agregar IconLeftWidget
    OneLineAvatarListItem,
    ILeftBodyTouch,
    IconLeftWidget,
)
from kivymd.uix.card import MDCard, MDSeparator       # FIX: MDSeparator viene de card
from kivymd.uix.selectioncontrol import MDCheckbox
from kivy.properties import StringProperty, NumericProperty, ListProperty, ObjectProperty
from kivy.metrics import dp


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE LOGGING
# ══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("taximetro.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Taximetro")


# ══════════════════════════════════════════════════════════════════════════════
# RUTAS DE ARCHIVOS
# ══════════════════════════════════════════════════════════════════════════════

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "historial.json")
CONFIG_FILE  = os.path.join(BASE_DIR, "config.json")
USERS_FILE   = os.path.join(BASE_DIR, "usuarios.json")


# ══════════════════════════════════════════════════════════════════════════════
# MODELOS DE DATOS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Tarifa:
    """Tarifas configurables del taxímetro."""
    precio_parado: float      = 0.02   # €/segundo parado
    precio_movimiento: float  = 0.05   # €/segundo en movimiento
    precio_bajada_bandera: float = 1.50  # Precio inicial al arrancar

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(**d)


@dataclass
class TipoServicio:
    """Define un tipo de servicio con su lógica de precio."""
    clave: str
    nombre: str
    icon_name: str
    descripcion: str
    cargo_fijo: float
    multiplicador: float
    color_name: str

    def cargo_extra_display(self) -> str:
        partes = []
        if self.cargo_fijo > 0:
            partes.append(f"+{self.cargo_fijo:.2f}€ fijo")
        if self.multiplicador != 1.0:
            partes.append(f"x{self.multiplicador} tarifa")
        return " · ".join(partes) if partes else "Sin cargo extra"


# Catálogo de servicios disponibles
SERVICIOS: list = [
    TipoServicio("economico", "Económico",   "car",              "Tarifa estándar sin recargos",    0.0,  1.0, "Gray"),
    TipoServicio("xl",        "XL / Familiar","account-group",   "Vehículo de mayor capacidad",     2.00, 1.4, "Blue"),
    TipoServicio("compartido","Compartido",   "account-multiple", "Viaje compartido, precio reducido",0.0, 0.6, "Teal"),
    TipoServicio("pet",       "Pet Friendly", "paw",             "Mascotas permitidas",             1.50, 1.0, "Orange"),
    TipoServicio("flash",     "Flash",        "lightning-bolt",  "Recogida prioritaria más rápida", 3.00, 1.2, "Amber"),
]

# Colores RGBA para KivyMD
COLORES = {
    "Gray":   [0.5,  0.5,  0.5,  1],
    "Blue":   [0.1,  0.4,  0.9,  1],
    "Teal":   [0.0,  0.5,  0.5,  1],
    "Orange": [1.0,  0.5,  0.0,  1],
    "Amber":  [1.0,  0.75, 0.0,  1],
}

# Mapa para acceso rápido por clave
SERVICIOS_MAP: dict = {s.clave: s for s in SERVICIOS}


@dataclass
class Trayecto:
    """Representa un trayecto completo."""
    id: str
    fecha_inicio: str
    fecha_fin: str             = ""
    segundos_parado: float     = 0.0
    segundos_movimiento: float = 0.0
    importe_total: float       = 0.0
    conductor: str             = ""
    servicio: str              = "economico"

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict):
        d.setdefault("servicio", "economico")
        return cls(**d)


# ══════════════════════════════════════════════════════════════════════════════
# GESTORES
# ══════════════════════════════════════════════════════════════════════════════

class GestorConfig:
    """Gestiona la configuración de tarifas."""

    def __init__(self):
        self._tarifa = self._cargar()

    def _cargar(self) -> Tarifa:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info("Configuración cargada desde archivo.")
                return Tarifa.from_dict(data)
            except Exception as e:
                logger.warning(f"Error cargando config: {e}. Usando valores por defecto.")
        return Tarifa()

    def guardar(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._tarifa.to_dict(), f, indent=2)
        logger.info("Configuración guardada.")

    @property
    def tarifa(self) -> Tarifa:
        return self._tarifa

    def actualizar(self, parado: float, movimiento: float, bandera: float):
        self._tarifa.precio_parado      = parado
        self._tarifa.precio_movimiento  = movimiento
        self._tarifa.precio_bajada_bandera = bandera
        self.guardar()
        logger.info(f"Tarifas actualizadas: parado={parado}, movimiento={movimiento}, bandera={bandera}")


class GestorHistorial:
    """Gestiona el historial de trayectos."""

    def __init__(self):
        self._trayectos: list = self._cargar()

    def _cargar(self) -> list:
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return [Trayecto.from_dict(t) for t in data]
            except Exception as e:
                logger.warning(f"Error cargando historial: {e}")
        return []

    def guardar(self):
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in self._trayectos], f, indent=2, ensure_ascii=False)

    def agregar(self, trayecto: Trayecto):
        self._trayectos.append(trayecto)
        self.guardar()
        logger.info(f"Trayecto {trayecto.id} guardado. Total: {trayecto.importe_total:.2f}€")

    @property
    def trayectos(self) -> list:
        return self._trayectos

    def total_recaudado(self) -> float:
        return sum(t.importe_total for t in self._trayectos)


class GestorAuth:
    """Sistema de autenticación con contraseñas hasheadas."""

    def __init__(self):
        self._usuarios: dict = self._cargar()
        if not self._usuarios:
            self._crear_usuario_default()

    def _cargar(self) -> dict:
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando usuarios: {e}")
        return {}

    def _guardar(self):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._usuarios, f, indent=2)

    def _hash(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def _crear_usuario_default(self):
        self._usuarios["admin"] = {"hash": self._hash("1234"), "rol": "admin"}
        self._guardar()
        logger.info("Usuario por defecto creado: admin/1234")

    def autenticar(self, usuario: str, password: str) -> bool:
        if usuario in self._usuarios:
            ok = self._usuarios[usuario]["hash"] == self._hash(password)
            if ok:
                logger.info(f"Acceso concedido a '{usuario}'.")
            else:
                logger.warning(f"Contraseña incorrecta para '{usuario}'.")
            return ok
        logger.warning(f"Usuario '{usuario}' no encontrado.")
        return False

    def cambiar_password(self, usuario: str, nueva: str):
        if usuario in self._usuarios:
            self._usuarios[usuario]["hash"] = self._hash(nueva)
            self._guardar()
            logger.info(f"Contraseña cambiada para '{usuario}'.")


# ══════════════════════════════════════════════════════════════════════════════
# WIDGETS PERSONALIZADOS
# ══════════════════════════════════════════════════════════════════════════════

# FIX: La clase debe definirse ANTES de cargar el KV string para que
#      el parser KV encuentre la regla <ServiceListItem> correctamente.
class ServiceListItem(OneLineAvatarListItem):
    """Ítem de la lista de servicios con icono coloreado."""
    icon_name     = StringProperty("car")
    service_name  = StringProperty("")
    service_color = ListProperty([0, 0, 0, 1])


# ══════════════════════════════════════════════════════════════════════════════
# INTERFAZ DE USUARIO (KivyMD - lenguaje KV)
# ══════════════════════════════════════════════════════════════════════════════

KV = '''
#:import dp kivy.metrics.dp

# ── Regla de clase para el ítem de la lista ──────────────────────────────────
# FIX: "IconLeftWidget" es el widget correcto (no ILeftBodyTouch genérico)
<ServiceListItem>:
    text: root.service_name

    IconLeftWidget:
        icon: root.icon_name
        theme_text_color: "Custom"
        text_color: root.service_color

# ── Pantalla principal (raíz del árbol KV) ───────────────────────────────────
# FIX: El widget raíz es MDBoxLayout (no BoxLayout anónimo).
#      Esto permite que app.root.ids funcione correctamente.
MDBoxLayout:
    orientation: "vertical"
    padding: dp(20)
    spacing: dp(12)

    # ── ENCABEZADO ──────────────────────────────────────────────────────────
    MDBoxLayout:
        orientation: "horizontal"
        size_hint_y: None
        height: dp(56)
        spacing: dp(10)

        MDIcon:
            icon: "taxi"
            size_hint: None, None
            size: dp(32), dp(32)
            pos_hint: {"center_y": .5}
            theme_text_color: "Primary"

        MDLabel:
            text: "Taxímetro Digital"
            font_style: "H5"
            pos_hint: {"center_y": .5}
            theme_text_color: "Primary"

    # FIX: MDSeparator se importa desde kivymd.uix.card en Python,
    #      pero en KV se referencia por nombre de clase directamente.
    MDSeparator:

    # ── SELECTOR DE SERVICIOS ────────────────────────────────────────────────
    MDLabel:
        text: "Tipo de Servicio"
        font_style: "H6"
        theme_text_color: "Secondary"
        size_hint_y: None
        height: dp(28)

    ScrollView:
        size_hint_y: 0.35
        MDList:
            id: service_list   # FIX: id accesible desde app.root.ids.service_list

    MDSeparator:

    # ── TARJETA DE ESTADO Y PRECIO ───────────────────────────────────────────
    MDCard:
        orientation: "vertical"
        padding: dp(15)
        size_hint_y: None
        height: dp(130)
        radius: [dp(15)]
        elevation: 3

        MDBoxLayout:
            orientation: "horizontal"
            spacing: dp(8)
            size_hint_y: None
            height: dp(30)

            MDIcon:
                icon: "navigation"
                size_hint: None, None
                size: dp(24), dp(24)
                theme_text_color: "Secondary"

            MDLabel:
                id: lbl_estado          # FIX: id para actualizar estado
                text: "Esperando..."
                font_style: "Button"
                theme_text_color: "Secondary"

        MDLabel:
            id: lbl_precio             # FIX: id para actualizar precio
            text: "0.00 €"
            font_style: "H3"
            halign: "center"
            theme_text_color: "Primary"

        MDLabel:
            id: lbl_servicio           # FIX: id para mostrar servicio activo
            text: "Servicio: Económico"
            font_style: "Caption"
            halign: "center"
            theme_text_color: "Secondary"

    # ── BOTONES DE ACCIÓN ────────────────────────────────────────────────────
    MDBoxLayout:
        orientation: "horizontal"
        spacing: dp(12)
        size_hint_y: None
        height: dp(70)
        padding: [0, dp(8), 0, 0]

        MDFillRoundFlatIconButton:
            id: btn_activar
            icon: "play-outline"
            text: "Activar"
            font_size: "16sp"
            icon_size: dp(28)
            md_bg_color: 0.20, 0.66, 0.33, 1
            size_hint_x: 1
            height: dp(60)
            on_release: app.iniciar_taximetro()

        MDFillRoundFlatIconButton:
            id: btn_parar
            icon: "pause-outline"
            text: "Parar"
            font_size: "16sp"
            icon_size: dp(28)
            md_bg_color: 0.98, 0.74, 0.02, 1
            text_color: 0.13, 0.13, 0.14, 1
            size_hint_x: 1
            height: dp(60)
            on_release: app.pausar_taximetro()

        MDFillRoundFlatIconButton:
            id: btn_finalizar
            icon: "stop-outline"
            text: "Finalizar"
            font_size: "16sp"
            icon_size: dp(28)
            md_bg_color: 0.92, 0.26, 0.21, 1
            size_hint_x: 1
            height: dp(60)
            on_release: app.finalizar_taximetro()

    # ── RESUMEN DE SESIÓN ────────────────────────────────────────────────────
    MDLabel:
        id: lbl_resumen
        text: ""
        font_style: "Caption"
        halign: "center"
        theme_text_color: "Secondary"
        size_hint_y: None
        height: dp(30)
'''


# ══════════════════════════════════════════════════════════════════════════════
# APLICACIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class TaximetroApp(MDApp):
    """Aplicación principal del Taxímetro Digital."""

    # ── Estado interno del taxímetro ─────────────────────────────────────────
    _activo          = False      # True cuando está contando
    _segundos_parado = 0.0
    _segs_movimiento = 0.0
    _importe         = 0.0
    _clock_event     = None       # Referencia al Clock para poder cancelarlo
    _servicio_actual : TipoServicio = None
    _trayecto_actual : Trayecto     = None

    # ── Gestores ─────────────────────────────────────────────────────────────
    _gestor_config   : GestorConfig   = None
    _gestor_historial: GestorHistorial = None
    _gestor_auth     : GestorAuth      = None

    def build(self):
        self.theme_cls.theme_style    = "Light"
        self.theme_cls.primary_palette = "Blue"

        # Instanciar gestores
        self._gestor_config    = GestorConfig()
        self._gestor_historial = GestorHistorial()
        self._gestor_auth      = GestorAuth()

        # Servicio por defecto: económico
        self._servicio_actual = SERVICIOS_MAP["economico"]

        # FIX: Builder.load_string devuelve el widget raíz correctamente
        return Builder.load_string(KV)

    def on_start(self):
        """Poblar la lista de servicios al arrancar."""
        # FIX: self.root es el MDBoxLayout raíz; ids están disponibles aquí
        service_list = self.root.ids.service_list
        for servicio in SERVICIOS:
            item = ServiceListItem(
                icon_name     = servicio.icon_name,
                service_name  = servicio.nombre,
                service_color = COLORES.get(servicio.color_name, [0, 0, 0, 1]),
            )
            # Al pulsar un servicio, lo seleccionamos
            item.bind(on_release=lambda x, s=servicio: self._seleccionar_servicio(s))
            service_list.add_widget(item)

        logger.info("App iniciada correctamente.")

    # ── Lógica de selección de servicio ──────────────────────────────────────

    def _seleccionar_servicio(self, servicio: TipoServicio):
        if self._activo:
            logger.warning("No se puede cambiar el servicio con el taxímetro activo.")
            return
        self._servicio_actual = servicio
        self.root.ids.lbl_servicio.text = f"Servicio: {servicio.nombre}"
        logger.info(f"Servicio seleccionado: {servicio.nombre}")

    # ── Lógica principal del taxímetro ────────────────────────────────────────

    def iniciar_taximetro(self):
        """Inicia o reanuda el conteo."""
        if self._activo:
            return  # Ya está activo

        tarifa = self._gestor_config.tarifa

        # Si es un trayecto nuevo (no hay ninguno activo), crearlo
        if self._trayecto_actual is None:
            ahora = datetime.now()
            self._trayecto_actual = Trayecto(
                id           = ahora.strftime("%Y%m%d_%H%M%S"),
                fecha_inicio = ahora.isoformat(),
                servicio     = self._servicio_actual.clave,
            )
            # Aplicar bajada de bandera + cargo fijo del servicio
            bandera = (
                tarifa.precio_bajada_bandera
                + self._servicio_actual.cargo_fijo
            )
            self._importe = bandera
            logger.info(
                f"Nuevo trayecto iniciado. "
                f"Servicio: {self._servicio_actual.nombre}. "
                f"Bajada de bandera: {bandera:.2f}€"
            )

        self._activo = True
        self._actualizar_ui("En movimiento...", color=[0.20, 0.66, 0.33, 1])

        # FIX: Clock.schedule_interval para llamar a _tick cada 1 segundo
        self._clock_event = Clock.schedule_interval(self._tick, 1.0)
        logger.info("Taxímetro activado.")

    def pausar_taximetro(self):
        """Pausa el conteo (simula estar parado)."""
        if not self._activo:
            return
        self._activo = False
        if self._clock_event:
            self._clock_event.cancel()
            self._clock_event = None
        self._actualizar_ui("Parado", color=[0.98, 0.74, 0.02, 1])
        logger.info("Taxímetro pausado.")

    def finalizar_taximetro(self):
        """Finaliza el trayecto y lo guarda en el historial."""
        if self._trayecto_actual is None:
            logger.warning("No hay trayecto activo para finalizar.")
            return

        # Detener el clock si estaba activo
        if self._activo:
            self._activo = False
            if self._clock_event:
                self._clock_event.cancel()
                self._clock_event = None

        # Completar datos del trayecto
        ahora = datetime.now()
        self._trayecto_actual.fecha_fin          = ahora.isoformat()
        self._trayecto_actual.segundos_parado    = self._segundos_parado
        self._trayecto_actual.segundos_movimiento = self._segs_movimiento
        self._trayecto_actual.importe_total      = round(self._importe, 2)

        # Guardar en historial
        self._gestor_historial.agregar(self._trayecto_actual)

        # Mostrar resumen
        resumen = (
            f"Trayecto finalizado · {self._importe:.2f}€ · "
            f"{int(self._segs_movimiento)}s mov / {int(self._segundos_parado)}s parado"
        )
        self.root.ids.lbl_resumen.text = resumen
        self._actualizar_ui("Finalizado", color=[0.92, 0.26, 0.21, 1])
        logger.info(resumen)

        # Resetear estado
        self._trayecto_actual  = None
        self._segundos_parado  = 0.0
        self._segs_movimiento  = 0.0
        self._importe          = 0.0

        # Volver precio a cero tras breve pausa visual
        Clock.schedule_once(self._resetear_ui, 3.0)

    # ── Tick del reloj ────────────────────────────────────────────────────────

    def _tick(self, dt):
        """Llamado cada segundo por el Clock. Acumula tiempo e importe."""
        tarifa = self._gestor_config.tarifa
        mult   = self._servicio_actual.multiplicador

        # Por ahora siempre cuenta como "en movimiento".
        # Aquí podrías integrar GPS para detectar velocidad real.
        self._segs_movimiento += 1
        self._importe += tarifa.precio_movimiento * mult

        # Actualizar etiqueta de precio en la UI
        self.root.ids.lbl_precio.text = f"{self._importe:.2f} €"

    # ── Helpers de UI ─────────────────────────────────────────────────────────

    def _actualizar_ui(self, estado: str, color: list = None):
        """Actualiza la etiqueta de estado."""
        self.root.ids.lbl_estado.text = estado

    def _resetear_ui(self, *args):
        """Resetea el precio y el estado en pantalla."""
        self.root.ids.lbl_precio.text   = "0.00 €"
        self.root.ids.lbl_estado.text   = "Esperando..."
        self.root.ids.lbl_resumen.text  = ""


# ══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    TaximetroApp().run()