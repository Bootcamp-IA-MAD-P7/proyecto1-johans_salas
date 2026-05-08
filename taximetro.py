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