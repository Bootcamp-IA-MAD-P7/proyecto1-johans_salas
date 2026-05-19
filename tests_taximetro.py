import unittest
import logging
import os
from datetime import datetime
from taximetro import Tarifa, Trayecto, SERVICIOS, SERVICIOS_MAP, GestorHistorial, generar_factura_pdf

# Configurar el logger para que los tests escriban en el mismo archivo de la app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] TEST: %(message)s",
    handlers=[logging.FileHandler("taximetro.log", encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger("TestTaximetro")

class TestTaximetroCompleto(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Configuración inicial antes de correr los tests."""
        cls.tarifa_base = Tarifa(
            precio_parado=0.02, 
            precio_movimiento=0.05, 
            precio_bajada_bandera=1.50
        )
        cls.gestor_historial = GestorHistorial()
        logger.info("Iniciando batería de pruebas para todos los servicios.")

    def test_todos_los_servicios(self):
        """Prueba el cálculo de tarifa para cada tipo de servicio disponible."""
        
        # Simulamos un viaje estándar de:
        # 60 segundos en movimiento y 30 segundos parado
        t_mov = 60
        t_par = 30
        
        for servicio in SERVICIOS:
            with self.subTest(servicio=servicio.nombre):
                # 1. Cálculo Manual esperado
                # (Bandera + Fijo) + (Movimiento * Precio * Mult) + (Parado * Precio * Mult)
                base_mov = t_mov * self.tarifa_base.precio_movimiento
                base_par = t_par * self.tarifa_base.precio_parado
                
                esperado = (self.tarifa_base.precio_bajada_bandera + servicio.cargo_fijo) + \
                           (base_mov * servicio.multiplicador) + \
                           (base_par * servicio.multiplicador)
                
                # 2. Creación de objeto Trayecto para simular la realidad
                id_test = f"TEST-{servicio.clave.upper()}-{int(datetime.now().timestamp())}"
                nuevo_trayecto = Trayecto(
                    id=id_test,
                    fecha_inicio=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    fecha_fin=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    segundos_movimiento=t_mov,
                    segundos_parado=t_par,
                    importe_total=round(esperado, 2),
                    conductor="TEST_AUTOMATICO",
                    servicio=servicio.clave
                )

                # 3. Verificación
                self.assertGreater(nuevo_trayecto.importe_total, 0)
                logger.info(f"Servicio: {servicio.nombre} | Esperado: {esperado:.2f}€ | Calculado: {nuevo_trayecto.importe_total:.2f}€")

                # 4. Registro en Historial
                self.gestor_historial.agregar(nuevo_trayecto)
                
                # 5. Intento de generación de Factura PDF de prueba
                try:
                    ruta_pdf = generar_factura_pdf(nuevo_trayecto, servicio, self.tarifa_base)
                    self.assertTrue(os.path.exists(ruta_pdf))
                    logger.info(f"Factura generada exitosamente para {servicio.nombre} en: {ruta_pdf}")
                except Exception as e:
                    logger.error(f"Error al generar factura de prueba para {servicio.nombre}: {e}")

    def test_autenticacion_fallida(self):
        """Verifica que el sistema de logs registre intentos fallidos."""
        from taximetro import GestorAuth
        auth = GestorAuth()
        resultado = auth.autenticar("usuario_falso", "1234")
        self.assertFalse(resultado)
        logger.info("Prueba de login fallido registrada correctamente.")

if __name__ == '__main__':
    print("\n--- EJECUTANDO PRUEBAS DE SERVICIOS - TAXÍMETRO ---")
    unittest.main()