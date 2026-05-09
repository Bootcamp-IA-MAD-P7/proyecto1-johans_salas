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