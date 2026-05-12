# ══════════════════════════════════════════════════════════════════════════════
#PROYECTO NRO. 1
#Taxímetro Digital - Aplicación Principal
#Creado por: Johans Enrique Salas Rodríguez
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
#LIBRERÍAS
# ══════════════════════════════════════════════════════════════════════════════

from dataclasses import dataclass, field, asdict
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import time
import logging
import json
import hashlib
import os
from typing import Optional


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
# MODELADO DE DATOS
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
    emoji: str
    descripcion: str
    cargo_fijo: float   # € extra al iniciar (bajada de bandera adicional)
    multiplicador: float  # factor sobre tarifas por segundo (1.0 = sin cambio)
    color: str          # color del badge en la GUI

    def cargo_extra_display(self) -> str:
        partes = []
        if self.cargo_fijo > 0:
            partes.append(f"+{self.cargo_fijo:.2f}€ fijo")
        if self.multiplicador >= 1.0:
            partes.append(f"x{self.multiplicador} tarifa")
        elif self.multiplicador < 1.0:
            partes.append(f"x{self.multiplicador} tarifa (descuento)")
        return " · ".join(partes) if partes else "Sin cargo extra"
    
# Catálogo de servicios disponibles
SERVICIOS: list[TipoServicio] = [
    TipoServicio(
        clave="economico",
        nombre="Económico",
        emoji="🚗",
        descripcion="Tarifa estándar sin recargos",
        cargo_fijo=0.0,
        multiplicador=1.0,
        color="#888888",
    ),
    TipoServicio(
        clave="xl",
        nombre="XL / Familiar",
        emoji="👨‍👩‍👧",
        descripcion="Vehículo de mayor capacidad",
        cargo_fijo=2.00,
        multiplicador=1.4,
        color="#1e90ff",
    ),
    TipoServicio(
        clave="compartido",
        nombre="Compartido",
        emoji="👥",
        descripcion="Viaje compartido, precio reducido",
        cargo_fijo=0.0,
        multiplicador=0.6,
        color="#00c896",
    ),
    TipoServicio(
        clave="pet",
        nombre="Pet Friendly",
        emoji="🐾",
        descripcion="Mascotas permitidas",
        cargo_fijo=1.50,
        multiplicador=1.0,
        color="#ff9f43",
    ),
    TipoServicio(
        clave="flash",
        nombre="Flash",
        emoji="⚡",
        descripcion="Recogida prioritaria más rápida",
        cargo_fijo=3.00,
        multiplicador=1.2,
        color="#f5c518",
    ),
]

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
# MOTOR DEL TAXÍMETRO
# ══════════════════════════════════════════════════════════════════════════════

class MotorTaximetro:
    """Núcleo de cálculo del taxímetro (independiente de la GUI)."""

    def __init__(self, tarifa: Tarifa, servicio: "TipoServicio" = None):
        self.tarifa = tarifa
        self.servicio = servicio or SERVICIOS_MAP["economico"]
        self._activo = False
        self._en_movimiento = False
        self._segundos_parado = 0.0
        self._segundos_movimiento = 0.0
        self._importe = 0.0
        self._inicio: Optional[datetime] = None
        self._hilo: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.on_tick = None  # Callback para actualizar la GUI

    @property
    def activo(self) -> bool:
        return self._activo

    @property
    def en_movimiento(self) -> bool:
        return self._en_movimiento

    @property
    def importe(self) -> float:
        return self._importe

    @property
    def segundos_parado(self) -> float:
        return self._segundos_parado

    @property
    def segundos_movimiento(self) -> float:
        return self._segundos_movimiento

    def iniciar(self):
        if self._activo:
            return
        self._activo = True
        self._en_movimiento = False
        self._segundos_parado = 0.0
        self._segundos_movimiento = 0.0
        # Bajada de bandera base + cargo fijo del servicio
        self._importe = self.tarifa.precio_bajada_bandera + self.servicio.cargo_fijo
        self._inicio = datetime.now()
        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self._hilo.start()
        logger.info(f"Trayecto iniciado. Servicio: {self.servicio.nombre} "
                    f"(cargo_fijo={self.servicio.cargo_fijo}€, "
                    f"multiplicador=x{self.servicio.multiplicador})")

    def _bucle(self):
        INTERVALO = 0.1  # segundos
        mul = self.servicio.multiplicador
        while self._activo:
            time.sleep(INTERVALO)
            with self._lock:
                if self._en_movimiento:
                    self._segundos_movimiento += INTERVALO
                    self._importe += self.tarifa.precio_movimiento * mul * INTERVALO
                else:
                    self._segundos_parado += INTERVALO
                    self._importe += self.tarifa.precio_parado * mul * INTERVALO
            if self.on_tick:
                self.on_tick()

    def toggle_movimiento(self):
        with self._lock:
            self._en_movimiento = not self._en_movimiento
        estado = "movimiento" if self._en_movimiento else "parado"
        logger.info(f"Estado cambiado a: {estado}")

    def finalizar(self) -> Trayecto:
        self._activo = False
        fin = datetime.now()
        trayecto = Trayecto(
            id=self._inicio.strftime("%Y%m%d%H%M%S"),
            fecha_inicio=self._inicio.strftime("%d/%m/%Y %H:%M:%S"),
            fecha_fin=fin.strftime("%d/%m/%Y %H:%M:%S"),
            segundos_parado=round(self._segundos_parado, 1),
            segundos_movimiento=round(self._segundos_movimiento, 1),
            importe_total=round(self._importe, 2),
            servicio=self.servicio.clave,
        )
        logger.info(f"Trayecto finalizado. Servicio: {self.servicio.nombre}. "
                    f"Importe: {trayecto.importe_total:.2f}€")
        return trayecto
    

# ══════════════════════════════════════════════════════════════════════════════
# INTERFAZ GRÁFICA
# ══════════════════════════════════════════════════════════════════════════════

COLORES = {
    "bg":        "#0d0d0d",
    "panel":     "#1a1a1a",
    "borde":     "#2a2a2a",
    "amarillo":  "#f5c518",
    "verde":     "#00c896",
    "rojo":      "#ff4757",
    "azul":      "#1e90ff",
    "texto":     "#f0f0f0",
    "subtexto":  "#888888",
    "blanco":    "#ffffff",
}

FUENTE_DISPLAY = ("Courier New", 48, "bold")
FUENTE_TITULO  = ("Courier New", 14, "bold")
FUENTE_NORMAL  = ("Courier New", 11)
FUENTE_PEQUENA = ("Courier New", 9)

class VentanaLogin(tk.Toplevel):
    """Ventana modal de autenticación."""

    def __init__(self, parent, gestor_auth: GestorAuth, callback):
        super().__init__(parent)
        self.gestor_auth = gestor_auth
        self.callback = callback
        self.resultado = False

        self.title("🚕 Taxímetro — Acceso")
        self.configure(bg=COLORES["bg"])
        self.resizable(False, False)
        self.grab_set()

        self._construir()
        self.after(100, self._centrar)

    def _centrar(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _construir(self):
        frame = tk.Frame(self, bg=COLORES["bg"], padx=40, pady=30)
        frame.pack()

        tk.Label(frame, text="🚕", font=("Courier New", 40),
                 bg=COLORES["bg"], fg=COLORES["amarillo"]).pack(pady=(0, 5))
        tk.Label(frame, text="TAXÍMETRO DIGITAL", font=("Courier New", 16, "bold"),
                 bg=COLORES["bg"], fg=COLORES["amarillo"]).pack()
        tk.Label(frame, text="Identificación requerida", font=FUENTE_PEQUENA,
                 bg=COLORES["bg"], fg=COLORES["subtexto"]).pack(pady=(0, 20))

        # Usuario
        tk.Label(frame, text="USUARIO", font=FUENTE_PEQUENA,
                 bg=COLORES["bg"], fg=COLORES["subtexto"]).pack(anchor="w")
        self.entry_user = tk.Entry(frame, font=FUENTE_NORMAL, bg=COLORES["panel"],
                                   fg=COLORES["texto"], insertbackground=COLORES["amarillo"],
                                   relief="flat", width=24, bd=0)
        self.entry_user.pack(pady=(2, 10), ipady=6, ipadx=8)
        self.entry_user.insert(0, "admin")

        # Contraseña
        tk.Label(frame, text="CONTRASEÑA", font=FUENTE_PEQUENA,
                 bg=COLORES["bg"], fg=COLORES["subtexto"]).pack(anchor="w")
        self.entry_pass = tk.Entry(frame, font=FUENTE_NORMAL, bg=COLORES["panel"],
                                   fg=COLORES["texto"], insertbackground=COLORES["amarillo"],
                                   relief="flat", width=24, bd=0, show="●")
        self.entry_pass.pack(pady=(2, 5), ipady=6, ipadx=8)
        self.entry_pass.bind("<Return>", lambda e: self._login())

        self.lbl_error = tk.Label(frame, text="", font=FUENTE_PEQUENA,
                                   bg=COLORES["bg"], fg=COLORES["rojo"])
        self.lbl_error.pack(pady=(0, 10))

        tk.Label(frame, text="Usuario por defecto: admin / 1234",
                 font=FUENTE_PEQUENA, bg=COLORES["bg"], fg=COLORES["subtexto"]).pack(pady=(0,10))

        btn = tk.Button(frame, text="ENTRAR", font=FUENTE_TITULO,
                        bg=COLORES["amarillo"], fg=COLORES["bg"],
                        relief="flat", cursor="hand2", width=20,
                        command=self._login)
        btn.pack(ipady=8)

    def _login(self):
        usuario = self.entry_user.get().strip()
        password = self.entry_pass.get()
        if self.gestor_auth.autenticar(usuario, password):
            self.resultado = True
            self.destroy()
            self.callback(usuario)
        else:
            self.lbl_error.config(text="⚠ Credenciales incorrectas")
            self.entry_pass.delete(0, tk.END)


class AppTaximetro(tk.Tk):
    """Ventana principal de la aplicación."""

    def __init__(self):
        super().__init__()
        self.withdraw()  # Ocultar hasta login

        # Gestores
        self.gestor_config   = GestorConfig()
        self.gestor_historial = GestorHistorial()
        self.gestor_auth     = GestorAuth()

        # Motor (se recrea en cada trayecto)
        self.motor = MotorTaximetro(self.gestor_config.tarifa)
        self.motor.on_tick = self._actualizar_display

        self.conductor_actual = ""
        self.servicio_actual: TipoServicio = SERVICIOS_MAP["economico"]

        # Mostrar login
        VentanaLogin(self, self.gestor_auth, self._post_login)
        self.wait_window(self.children.get(list(self.children.keys())[-1], self))

    def _post_login(self, usuario: str):
        self.conductor_actual = usuario
        self.deiconify()
        self._construir_ui()
        logger.info(f"Sesión iniciada por '{usuario}'.")

    def _construir_ui(self):
        self.title("🚕 Taxímetro Digital")
        self.configure(bg=COLORES["bg"])
        self.resizable(False, False)
        self._centrar(540, 820)

        # ── Header ──────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=COLORES["amarillo"])
        header.pack(fill="x")
        tk.Label(header, text="🚕 TAXÍMETRO DIGITAL",
                 font=("Courier New", 15, "bold"),
                 bg=COLORES["amarillo"], fg=COLORES["bg"]).pack(side="left", padx=16, pady=10)
        tk.Label(header, text=f"👤 {self.conductor_actual}",
                 font=FUENTE_PEQUENA, bg=COLORES["amarillo"],
                 fg=COLORES["bg"]).pack(side="right", padx=16)

        # ── Display principal ────────────────────────────────────────────────
        panel_display = tk.Frame(self, bg=COLORES["panel"], pady=20)
        panel_display.pack(fill="x", padx=16, pady=(16, 0))

        self.lbl_estado = tk.Label(panel_display, text="● ESPERANDO",
                                   font=FUENTE_TITULO, bg=COLORES["panel"],
                                   fg=COLORES["subtexto"])
        self.lbl_estado.pack()

        self.lbl_importe = tk.Label(panel_display, text="0,00 €",
                                    font=FUENTE_DISPLAY, bg=COLORES["panel"],
                                    fg=COLORES["amarillo"])
        self.lbl_importe.pack(pady=8)

        # Estadísticas
        stats_frame = tk.Frame(panel_display, bg=COLORES["panel"])
        stats_frame.pack()

        self.lbl_parado = self._stat_label(stats_frame, "PARADO", "0s", COLORES["rojo"])
        self.lbl_parado.pack(side="left", padx=20)
        self.lbl_movimiento = self._stat_label(stats_frame, "MOVIMIENTO", "0s", COLORES["verde"])
        self.lbl_movimiento.pack(side="left", padx=20)

        # ── Selector de tipo de servicio ─────────────────────────────────────
        srv_outer = tk.Frame(self, bg=COLORES["bg"])
        srv_outer.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(srv_outer, text="TIPO DE SERVICIO",
                 font=FUENTE_PEQUENA, bg=COLORES["bg"],
                 fg=COLORES["subtexto"]).pack(anchor="w", pady=(0, 6))

        srv_grid = tk.Frame(srv_outer, bg=COLORES["bg"])
        srv_grid.pack(fill="x")

        self._btns_servicio: dict[str, tk.Button] = {}
        for i, srv in enumerate(SERVICIOS):
            btn = tk.Button(
                srv_grid,
                text=f"{srv.emoji}\n{srv.nombre}",
                font=("Courier New", 8, "bold"),
                bg=COLORES["panel"],
                fg=COLORES["subtexto"],
                activebackground=srv.color,
                relief="flat", cursor="hand2",
                width=8, height=3,
                command=lambda s=srv: self._seleccionar_servicio(s),
            )
            btn.grid(row=0, column=i, padx=3, pady=0, sticky="ew")
            srv_grid.columnconfigure(i, weight=1)
            self._btns_servicio[srv.clave] = btn

        # Badge de info del servicio seleccionado
        self.lbl_srv_info = tk.Label(
            srv_outer, text="🚗  Económico  ·  Sin cargo extra",
            font=FUENTE_PEQUENA, bg=COLORES["bg"], fg=COLORES["subtexto"])
        self.lbl_srv_info.pack(anchor="w", pady=(6, 0))

        # Marcar económico como seleccionado por defecto
        self._seleccionar_servicio(SERVICIOS_MAP["economico"])

        # ── Separador ────────────────────────────────────────────────────────
        tk.Frame(self, bg=COLORES["borde"], height=1).pack(fill="x", padx=16, pady=(12, 0))

        # ── Botones principales ──────────────────────────────────────────────
        btn_frame = tk.Frame(self, bg=COLORES["bg"])
        btn_frame.pack(padx=16, pady=16, fill="x")

        self.btn_iniciar = self._boton(btn_frame, "▶  INICIAR", COLORES["verde"],
                                        COLORES["bg"], self._iniciar, ancho=22)
        self.btn_iniciar.pack(side="left", padx=(0, 8), ipady=12, fill="x", expand=True)

        self.btn_toggle = self._boton(btn_frame, "⏸  PARADO", COLORES["azul"],
                                       COLORES["blanco"], self._toggle, ancho=22)
        self.btn_toggle.pack(side="left", padx=(0, 8), ipady=12, fill="x", expand=True)
        self.btn_toggle.config(state="disabled")

        self.btn_fin = self._boton(btn_frame, "⏹  FINALIZAR", COLORES["rojo"],
                                    COLORES["blanco"], self._finalizar, ancho=22)
        self.btn_fin.pack(side="left", ipady=12, fill="x", expand=True)
        self.btn_fin.config(state="disabled")

        # ── Separador ────────────────────────────────────────────────────────
        tk.Frame(self, bg=COLORES["borde"], height=1).pack(fill="x", padx=16)

        # ── Historial ────────────────────────────────────────────────────────
        hist_header = tk.Frame(self, bg=COLORES["bg"])
        hist_header.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(hist_header, text="HISTORIAL DE TRAYECTOS",
                 font=FUENTE_TITULO, bg=COLORES["bg"],
                 fg=COLORES["subtexto"]).pack(side="left")

        self._boton(hist_header, "⚙ Tarifas", COLORES["panel"], COLORES["texto"],
                    self._abrir_config, ancho=10).pack(side="right", ipady=4, ipadx=4)
        self._boton(hist_header, "🔑 Cambiar clave", COLORES["panel"], COLORES["texto"],
                    self._cambiar_password, ancho=14).pack(side="right", padx=6, ipady=4, ipadx=4)

        # Tabla
        cols = ("Servicio", "Fecha", "Duración", "Importe")
        self.tabla = ttk.Treeview(self, columns=cols, show="headings", height=7)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=COLORES["panel"],
                        foreground=COLORES["texto"], fieldbackground=COLORES["panel"],
                        rowheight=26, font=FUENTE_PEQUENA)
        style.configure("Treeview.Heading", background=COLORES["borde"],
                        foreground=COLORES["amarillo"], font=FUENTE_PEQUENA)

        for col in cols:
            self.tabla.heading(col, text=col)
        self.tabla.column("Servicio", width=100)
        self.tabla.column("Fecha",    width=155)
        self.tabla.column("Duración", width=75)
        self.tabla.column("Importe",  width=80)

        self.tabla.pack(padx=16, pady=(0, 8), fill="x")

        # Totales
        total_frame = tk.Frame(self, bg=COLORES["bg"])
        total_frame.pack(fill="x", padx=16, pady=(0, 16))
        self.lbl_total = tk.Label(total_frame,
                                   text=f"Total recaudado: {self.gestor_historial.total_recaudado():.2f} €",
                                   font=FUENTE_NORMAL, bg=COLORES["bg"],
                                   fg=COLORES["amarillo"])
        self.lbl_total.pack(side="right")

        self._refrescar_historial()

    # ── Helpers visuales ──────────────────────────────────────────────────────

    def _centrar(self, w, h):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _boton(self, parent, texto, bg, fg, cmd, ancho=12):
        return tk.Button(parent, text=texto, font=FUENTE_NORMAL,
                         bg=bg, fg=fg, activebackground=bg,
                         relief="flat", cursor="hand2", width=ancho, command=cmd)

    def _stat_label(self, parent, titulo, valor, color):
        frame = tk.Frame(parent, bg=COLORES["panel"])
        tk.Label(frame, text=titulo, font=FUENTE_PEQUENA,
                 bg=COLORES["panel"], fg=COLORES["subtexto"]).pack()
        lbl = tk.Label(frame, text=valor, font=("Courier New", 13, "bold"),
                       bg=COLORES["panel"], fg=color)
        lbl.pack()
        frame.valor_label = lbl
        return frame

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _seleccionar_servicio(self, srv: TipoServicio):
        """Selecciona un tipo de servicio y actualiza la UI."""
        if self.motor.activo:
            return  # No se puede cambiar con trayecto en curso
        self.servicio_actual = srv
        # Resetear todos los botones
        for clave, btn in self._btns_servicio.items():
            s = SERVICIOS_MAP[clave]
            btn.config(bg=COLORES["panel"], fg=COLORES["subtexto"])
        # Resaltar el seleccionado
        self._btns_servicio[srv.clave].config(bg=srv.color, fg=COLORES["bg"])
        # Actualizar badge de info
        extras = []
        if srv.cargo_fijo > 0:
            extras.append(f"+{srv.cargo_fijo:.2f}€ al inicio")
        if srv.multiplicador > 1.0:
            extras.append(f"tarifa x{srv.multiplicador}")
        elif srv.multiplicador < 1.0:
            extras.append(f"tarifa x{srv.multiplicador} (descuento)")
        info = f"{srv.emoji}  {srv.nombre}  ·  {srv.descripcion}"
        if extras:
            info += f"  ·  {', '.join(extras)}"
        self.lbl_srv_info.config(text=info, fg=srv.color if srv.clave != "economico" else COLORES["subtexto"])
        logger.info(f"Servicio seleccionado: {srv.nombre}")

    def _iniciar(self):
        self.motor = MotorTaximetro(self.gestor_config.tarifa, self.servicio_actual)
        self.motor.on_tick = self._actualizar_display
        self.motor.iniciar()

        self.btn_iniciar.config(state="disabled")
        self.btn_toggle.config(state="normal")
        self.btn_fin.config(state="normal")
        # Bloquear cambio de servicio durante el trayecto
        for btn in self._btns_servicio.values():
            btn.config(state="disabled")
        self._actualizar_estado()

    def _toggle(self):
        self.motor.toggle_movimiento()
        self._actualizar_estado()

    def _finalizar(self):
        trayecto = self.motor.finalizar()
        trayecto.conductor = self.conductor_actual
        self.gestor_historial.agregar(trayecto)

        self.btn_iniciar.config(state="normal")
        self.btn_toggle.config(state="disabled")
        self.btn_fin.config(state="disabled")
        # Desbloquear selector de servicio
        for btn in self._btns_servicio.values():
            btn.config(state="normal")
        # Restaurar estilo del seleccionado
        self._seleccionar_servicio(self.servicio_actual)

        self.lbl_estado.config(text="● ESPERANDO", fg=COLORES["subtexto"])
        self._refrescar_historial()

        srv = SERVICIOS_MAP.get(trayecto.servicio, SERVICIOS_MAP["economico"])
        extras_txt = ""
        if srv.cargo_fijo > 0:
            extras_txt += f"\n   Cargo fijo {srv.nombre}: +{srv.cargo_fijo:.2f} €"
        if srv.multiplicador != 1.0:
            extras_txt += f"\n   Multiplicador aplicado: x{srv.multiplicador}"

        messagebox.showinfo("Trayecto finalizado",
                            f"✅ Trayecto completado\n\n"
                            f"{srv.emoji}  Servicio: {srv.nombre}\n"
                            f"🕐 Inicio:      {trayecto.fecha_inicio}\n"
                            f"🕐 Fin:         {trayecto.fecha_fin}\n"
                            f"⏸  Parado:     {trayecto.segundos_parado:.0f}s\n"
                            f"▶  Movimiento: {trayecto.segundos_movimiento:.0f}s"
                            f"{extras_txt}\n\n"
                            f"💶 TOTAL:  {trayecto.importe_total:.2f} €")

    def _actualizar_display(self):
        """Llamado desde el hilo del motor cada tick."""
        self.after(0, self._refrescar_labels)

    def _refrescar_labels(self):
        if not self.motor.activo:
            return
        self.lbl_importe.config(text=f"{self.motor.importe:.2f} €".replace(".", ","))
        self.lbl_parado.valor_label.config(
            text=f"{self.motor.segundos_parado:.0f}s")
        self.lbl_movimiento.valor_label.config(
            text=f"{self.motor.segundos_movimiento:.0f}s")

    def _actualizar_estado(self):
        if self.motor.en_movimiento:
            self.lbl_estado.config(text="▶ EN MOVIMIENTO", fg=COLORES["verde"])
            self.btn_toggle.config(text="⏸  PARAR", bg=COLORES["rojo"])
        else:
            self.lbl_estado.config(text="⏸ PARADO", fg=COLORES["rojo"])
            self.btn_toggle.config(text="▶  MOVER", bg=COLORES["verde"])

    def _refrescar_historial(self):
        for row in self.tabla.get_children():
            self.tabla.delete(row)
        for t in reversed(self.gestor_historial.trayectos[-20:]):
            duracion = t.segundos_parado + t.segundos_movimiento
            srv = SERVICIOS_MAP.get(t.servicio, SERVICIOS_MAP["economico"])
            self.tabla.insert("", "end", values=(
                f"{srv.emoji} {srv.nombre}",
                t.fecha_inicio,
                f"{duracion:.0f}s",
                f"{t.importe_total:.2f} €"
            ))
        self.lbl_total.config(
            text=f"Total recaudado: {self.gestor_historial.total_recaudado():.2f} €")

    # ── Configuración de tarifas ──────────────────────────────────────────────

    def _abrir_config(self):
        win = tk.Toplevel(self)
        win.title("⚙ Configuración de Tarifas")
        win.configure(bg=COLORES["bg"])
        win.resizable(False, False)
        win.grab_set()

        tarifa = self.gestor_config.tarifa
        campos = [
            ("Precio parado (€/s)",     tarifa.precio_parado),
            ("Precio movimiento (€/s)", tarifa.precio_movimiento),
            ("Bajada de bandera (€)",   tarifa.precio_bajada_bandera),
        ]
        entries = []
        for label, valor in campos:
            fr = tk.Frame(win, bg=COLORES["bg"], padx=20, pady=6)
            fr.pack(fill="x")
            tk.Label(fr, text=label, font=FUENTE_NORMAL,
                     bg=COLORES["bg"], fg=COLORES["texto"], width=26, anchor="w").pack(side="left")
            e = tk.Entry(fr, font=FUENTE_NORMAL, bg=COLORES["panel"],
                         fg=COLORES["texto"], width=10, relief="flat",
                         insertbackground=COLORES["amarillo"])
            e.insert(0, str(valor))
            e.pack(side="left", ipady=4, ipadx=4)
            entries.append(e)

        def guardar():
            try:
                p = float(entries[0].get())
                m = float(entries[1].get())
                b = float(entries[2].get())
                self.gestor_config.actualizar(p, m, b)
                messagebox.showinfo("✅ Guardado", "Tarifas actualizadas correctamente.")
                win.destroy()
            except ValueError:
                messagebox.showerror("Error", "Los valores deben ser números válidos.")

        tk.Button(win, text="GUARDAR", font=FUENTE_TITULO,
                  bg=COLORES["amarillo"], fg=COLORES["bg"],
                  relief="flat", command=guardar).pack(pady=12, ipadx=20, ipady=6)

    def _cambiar_password(self):
        nueva = simpledialog.askstring("Cambiar contraseña",
                                        "Nueva contraseña:", show="●", parent=self)
        if nueva:
            self.gestor_auth.cambiar_password(self.conductor_actual, nueva)
            messagebox.showinfo("✅ Listo", "Contraseña actualizada correctamente.")


# ══════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = AppTaximetro()
    app.mainloop()
