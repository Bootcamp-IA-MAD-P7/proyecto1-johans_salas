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
    emoji: str
    descripcion: str
    cargo_fijo: float   # € extra al iniciar (bajada de bandera adicional)
    multiplicador: float  # factor sobre tarifas por segundo (1.0 = sin cambio)
    color: str          # color del badge en la GUI

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
            