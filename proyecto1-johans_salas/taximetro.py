# ══════════════════════════════════════════════════════════════════════════════
#PROYECTO NRO. 1
#Taxímetro Digital - Aplicación Principal
#Creado por: Johans Enrique Salas Rodríguez
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
#LIBRERÍAS
# ══════════════════════════════════════════════════════════════════════════════

import os
import json
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime

# Configuración de KivyMD y Kivy
from kivy.config import Config
# Configurar la ventana antes de que se cargue la App
Config.set('graphics', 'width', '450')
Config.set('graphics', 'height', '750')
Config.set('graphics', 'resizable', False)

from kivymd.app import MDApp
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.button import MDFillRoundFlatIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.list import OneLineAvatarListItem, ILeftBodyTouch
from kivymd.uix.selectioncontrol import MDCheckbox
from kivy.properties import StringProperty, NumericProperty, ListProperty
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "historial.json")
CONFIG_FILE  = os.path.join(BASE_DIR, "config.json")
USERS_FILE   = os.path.join(BASE_DIR, "usuarios.json")


# ══════════════════════════════════════════════════════════════════════════════
# MODELOS DE DATOS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Tarifa:
    """Tarifas configurables del taxímetro."""
    precio_parado: float = 0.02      # €/segundo parado
    precio_movimiento: float = 0.05  # €/segundo en movimiento
    precio_bajada_bandera: float = 1.50  # Precio inicial al arrancar

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(**d)
    
@dataclass
class TipoServicio:
    """Define un tipo de servicio con su lógica de precio."""
    clave: str          # identificador interno
    nombre: str         # texto visible
    icon_name: str
    descripcion: str
    cargo_fijo: float   # € extra al iniciar (bajada de bandera adicional)
    multiplicador: float  # factor sobre tarifas por segundo (1.0 = sin cambio)
    color_name: str          # color del badge en la GUI

    def cargo_extra_display(self) -> str:
        partes = []
        if self.cargo_fijo > 0:
            partes.append(f"+{self.cargo_fijo:.2f}€ fijo")
        if self.multiplicador != 1.0:
            partes.append(f"x{self.multiplicador} tarifa")
        if self.multiplicador < 1.0:
            partes.append(f"x{self.multiplicador} tarifa")
        return " · ".join(partes) if partes else "Sin cargo extra"
    
# Catálogo de servicios disponibles
SERVICIOS: list[TipoServicio] = [
    TipoServicio(
        clave="economico",
        nombre="Económico",
        icon_name="car-flatbed-type",
        descripcion="Tarifa estándar sin recargos",
        cargo_fijo=0.0,
        multiplicador=1.0,
        color_name="Gray",
    ),
    TipoServicio(
        clave="xl",
        nombre="XL / Familiar",
        icon_name="account-group",
        descripcion="Vehículo de mayor capacidad",
        cargo_fijo=2.00,
        multiplicador=1.4,
        color_name="Blue",
    ),
    TipoServicio(
        clave="compartido",
        nombre="Compartido",
        icon_name="account-multiple",
        descripcion="Viaje compartido, precio reducido",
        cargo_fijo=0.0,
        multiplicador=0.6,
        color_name="Teal",
    ),
    TipoServicio(
        clave="pet",
        nombre="Pet Friendly",
        icon_name="paw",
        descripcion="Mascotas permitidas",
        cargo_fijo=1.50,
        multiplicador=1.0,
        color_name="Orange",
    ),
    TipoServicio(
        clave="flash",
        nombre="Flash",
        icon_name="lightning-bolt",
        descripcion="Recogida prioritaria más rápida",
        cargo_fijo=3.00,
        multiplicador=1.2,
        color_name="Amber",
    ),
]

# Colores RGBA para KivyMD
COLORES = {
    "Gray": [0.5, 0.5, 0.5, 1],
    "Blue": [0.1, 0.4, 0.9, 1],
    "Teal": [0, 0.5, 0.5, 1],
    "Orange": [1, 0.5, 0, 1],
    "Amber": [1, 0.75, 0, 1],
}

# Mapa para acceso rápido por clave
SERVICIOS_MAP: dict[str, TipoServicio] = {s.clave: s for s in SERVICIOS}

@dataclass
class Trayecto:
    """Representa un trayecto completo."""
    id: str
    fecha_inicio: str
    fecha_fin: str = ""
    segundos_parado: float = 0.0
    segundos_movimiento: float = 0.0
    importe_total: float = 0.0
    conductor: str = ""
    servicio: str = "economico"   # clave del TipoServicio

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict):
        # Compatibilidad con trayectos guardados sin campo 'servicio'
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
        self._tarifa.precio_parado = parado
        self._tarifa.precio_movimiento = movimiento
        self._tarifa.precio_bajada_bandera = bandera
        self.guardar()
        logger.info(f"Tarifas actualizadas: parado={parado}, movimiento={movimiento}, bandera={bandera}")


class GestorHistorial:
    """Gestiona el historial de trayectos."""

    def __init__(self):
        self._trayectos: list[Trayecto] = self._cargar()

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
        logger.info(f"Trayecto {trayecto.id} guardado en historial. Total: {trayecto.importe_total:.2f}€")

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
        """Crea usuario admin por defecto: admin/1234"""
        self._usuarios["admin"] = {
            "hash": self._hash("1234"),
            "rol": "admin"
        }
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
# INTERFAZ DE USUARIO (KivyMD)
# ══════════════════════════════════════════════════════════════════════════════

# Diseño de la interfaz en lenguaje KV (declarativo, integrado)
KV = '''
#:import dp kivy.metrics.dp

<ServiceListItem>:
    text: root.service_name
    font_style: "H6"  # Letras más grandes para el nombre del servicio
    theme_text_color: "Custom"
    text_color: self.theme_cls.primary_color
    
    IconLeftWidget:
        icon: root.icon_name
        # REQUISITO: Iconos estándar de 24x24 px
        size_hint: None, None
        size: dp(24), dp(24)
        theme_text_color: "Custom"
        text_color: root.service_color if root.service_color else [0,0,0,1]

BoxLayout:
    orientation: 'vertical'
    padding: dp(20)
    spacing: dp(15)

    # --- ENCABEZADO ---
    MDBoxLayout:
        orientation: 'horizontal'
        size_hint_y: None
        height: dp(60)
        spacing: dp(10)
        padding: [0, dp(10), 0, dp(20)]

        MDIcon:
            icon: "taxi"
            # REQUISITO: Icono estándar de 24x24 px
            size_hint: None, None
            size: dp(24), dp(24)
            pos_hint: {"center_y": .5}
            theme_text_color: "Primary"

        MDLabel:
            text: "Taxímetro Digital"
            # REQUISITO: Letras generales más grandes
            font_style: "H4" 
            pos_hint: {"center_y": .5}
            theme_text_color: "Primary"

    MDSeparator:

    # --- SELECTOR DE SERVICIOS ---
    MDLabel:
        text: "Tipo de Servicio"
        font_style: "H6"
        theme_text_color: "Primary"
        size_hint_y: None
        height: dp(30)

    # Lista de servicios con iconos de 24x24
    ScrollView:
        MDList:
            id: service_list

    MDSeparator:

    # --- ESTADO Y TARIFAS ---
    MDCard:
        orientation: 'vertical'
        padding: dp(15)
        size_hint_y: None
        height: dp(120)
        radius: [dp(15), dp(15), dp(15), dp(15)] # Diseño Rounded
        elevation: 2
        
        MDBoxLayout:
            orientation: 'horizontal'
            spacing: dp(10)
            
            MDIcon:
                icon: "navigation"
                # REQUISITO: Icono estándar de 24x24 px
                size_hint: None, None
                size: dp(24), dp(24)
                theme_text_color: "Secondary"

            MDLabel:
                text: "Estado: Esperando..."
                font_style: "Button" # Más grande
                theme_text_color: "Secondary"

        MDLabel:
            text: "0.00 €"
            font_style: "H2" # Letras muy grandes para el precio
            halign: "center"
            theme_text_color: "Primary"


    # --- PANEL DE ACCIONES (Botones Grandes) ---
    MDBoxLayout:
        orientation: 'horizontal'
        spacing: dp(15)
        size_hint_y: None
        height: dp(80)
        padding: [0, dp(15), 0, 0]

        # Botón Activar (Play)
        # REQUISITO: Diseño Rounded y Iconos de 32x32 px
        MDFillRoundFlatIconButton:
            icon: "play-outline"
            text: "Activar"
            # Aumentar tamaño base de fuente del botón
            font_size: "18sp" 
            # Aumentar tamaño del icono dentro del botón
            icon_size: dp(32) 
            md_bg_color: 0.20, 0.66, 0.33, 1  # Verde Material (#34A853)
            size_hint_x: 1
            height: dp(60) # Botón más alto y redondeado

            on_release: app.iniciar_taximetro()

        # Botón Parar (Pause)
        MDFillRoundFlatIconButton:
            icon: "pause-outline"
            text: "Parar"
            font_size: "18sp"
            icon_size: dp(32)
            md_bg_color: 0.98, 0.74, 0.02, 1  # Amarillo Material (#FBBC05)
            text_color: 0.13, 0.13, 0.14, 1 # Texto oscuro
            size_hint_x: 1
            height: dp(60)

            on_release: app.pausar_taximetro()

        # Botón Finalizar (Stop)
        MDFillRoundFlatIconButton:
            icon: "stop-outline"
            text: "Finalizar"
            font_size: "18sp"
            icon_size: dp(32)
            md_bg_color: 0.92, 0.26, 0.21, 1  # Rojo Material (#EA4335)
            size_hint_x: 1
            height: dp(60)

            on_release: app.finalizar_taximetro()
'''

# Clases auxiliares para la UI
class ServiceListItem(OneLineAvatarListItem):
    icon_name = StringProperty()
    service_name = StringProperty()
    service_color = ListProperty()

class TaximetroApp(MDApp):
    def iniciar_taximetro(self):
        print("Taxímetro iniciado")

    def pausar_taximetro(self):
        print("Taxímetro pausado")

    def finalizar_taximetro(self):
        print("Trayecto finalizado")

    def build(self):
        # Configurar el tema visual de Material Design
        self.theme_cls.theme_style = "Light"  # O "Dark"
        self.theme_cls.primary_palette = "Blue"  # Color principal de la App
        return Builder.load_string(KV)

    def on_start(self):
        # Llenar la lista de servicios dinámicamente al iniciar
        service_list = self.root.ids.service_list
        for servicio in SERVICIOS:
            item = ServiceListItem(
                icon_name=servicio.icon_name,
                service_name=servicio.nombre,
                # Convertir nombre de color KivyMD a lista RGBA
                service_color=COLORES.get(
                    servicio.color_name,
                    [0, 0, 0, 1]
                    )
            )
            service_list.add_widget(item)

if __name__ == '__main__':
    TaximetroApp().run()