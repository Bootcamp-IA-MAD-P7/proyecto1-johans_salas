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