"""
Tests Unitarios - Taxímetro Digital
Cubre: MotorTaximetro, Tarifa, GestorAuth, GestorConfig, GestorHistorial
"""

import unittest
import time
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Importar módulos a testear
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from taximetro import (
    Tarifa, Trayecto, MotorTaximetro,
    GestorAuth, GestorConfig, GestorHistorial,
    CONFIG_FILE, HISTORY_FILE, USERS_FILE
)


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES: directorio temporal para no ensuciar el proyecto
# ══════════════════════════════════════════════════════════════════════════════

class BaseTest(unittest.TestCase):
    """Base con directorio temporal y parcheo de rutas de archivo."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # Parchear las rutas de archivo para usar el directorio temporal
        self._patches = [
            patch("taximetro.CONFIG_FILE",  os.path.join(self.tmp, "config.json")),
            patch("taximetro.HISTORY_FILE", os.path.join(self.tmp, "historial.json")),
            patch("taximetro.USERS_FILE",   os.path.join(self.tmp, "usuarios.json")),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# TESTS: Tarifa
# ══════════════════════════════════════════════════════════════════════════════

class TestTarifa(unittest.TestCase):

    def test_valores_por_defecto(self):
        t = Tarifa()
        self.assertAlmostEqual(t.precio_parado, 0.02)
        self.assertAlmostEqual(t.precio_movimiento, 0.05)
        self.assertAlmostEqual(t.precio_bajada_bandera, 1.50)

    def test_serializacion_roundtrip(self):
        t = Tarifa(precio_parado=0.03, precio_movimiento=0.07, precio_bajada_bandera=2.00)
        d = t.to_dict()
        t2 = Tarifa.from_dict(d)
        self.assertAlmostEqual(t2.precio_parado, 0.03)
        self.assertAlmostEqual(t2.precio_movimiento, 0.07)
        self.assertAlmostEqual(t2.precio_bajada_bandera, 2.00)

    def test_valores_personalizados(self):
        t = Tarifa(precio_parado=0.10, precio_movimiento=0.20, precio_bajada_bandera=3.00)
        self.assertAlmostEqual(t.precio_parado, 0.10)
        self.assertAlmostEqual(t.precio_movimiento, 0.20)


# ══════════════════════════════════════════════════════════════════════════════
# TESTS: Trayecto
# ══════════════════════════════════════════════════════════════════════════════

class TestTrayecto(unittest.TestCase):

    def _trayecto(self, **kwargs):
        defaults = dict(id="20260101120000", fecha_inicio="01/01/2026 12:00:00",
                        importe_total=5.25)
        defaults.update(kwargs)
        return Trayecto(**defaults)

    def test_creacion_basica(self):
        t = self._trayecto()
        self.assertEqual(t.id, "20260101120000")
        self.assertAlmostEqual(t.importe_total, 5.25)

    def test_serializacion_roundtrip(self):
        t = self._trayecto(segundos_parado=30.0, segundos_movimiento=120.0)
        d = t.to_dict()
        t2 = Trayecto.from_dict(d)
        self.assertEqual(t2.id, t.id)
        self.assertAlmostEqual(t2.segundos_parado, 30.0)
        self.assertAlmostEqual(t2.segundos_movimiento, 120.0)


# ══════════════════════════════════════════════════════════════════════════════
# TESTS: MotorTaximetro
# ══════════════════════════════════════════════════════════════════════════════

class TestMotorTaximetro(unittest.TestCase):

    def setUp(self):
        self.tarifa = Tarifa()
        self.motor = MotorTaximetro(self.tarifa)

    def tearDown(self):
        if self.motor.activo:
            self.motor.finalizar()

    def test_estado_inicial(self):
        self.assertFalse(self.motor.activo)
        self.assertFalse(self.motor.en_movimiento)
        self.assertAlmostEqual(self.motor.importe, 0.0)

    def test_iniciar_activa_motor(self):
        self.motor.iniciar()
        self.assertTrue(self.motor.activo)
        self.motor.finalizar()

    def test_importe_inicial_es_bajada_bandera(self):
        self.motor.iniciar()
        time.sleep(0.05)  # Pequeña espera para que empiece el bucle
        self.assertGreaterEqual(self.motor.importe, self.tarifa.precio_bajada_bandera)
        self.motor.finalizar()

    def test_toggle_movimiento(self):
        self.motor.iniciar()
        self.assertFalse(self.motor.en_movimiento)
        self.motor.toggle_movimiento()
        self.assertTrue(self.motor.en_movimiento)
        self.motor.toggle_movimiento()
        self.assertFalse(self.motor.en_movimiento)
        self.motor.finalizar()

    def test_acumula_segundos_parado(self):
        self.motor.iniciar()
        time.sleep(0.3)
        self.motor.finalizar()
        self.assertGreater(self.motor.segundos_parado, 0)

    def test_acumula_segundos_movimiento(self):
        self.motor.iniciar()
        self.motor.toggle_movimiento()
        time.sleep(0.3)
        self.motor.finalizar()
        self.assertGreater(self.motor.segundos_movimiento, 0)

    def test_finalizar_retorna_trayecto(self):
        self.motor.iniciar()
        time.sleep(0.1)
        trayecto = self.motor.finalizar()
        self.assertIsInstance(trayecto, Trayecto)
        self.assertGreater(trayecto.importe_total, 0)
        self.assertNotEqual(trayecto.fecha_inicio, "")

    def test_tarifa_parado_aplicada(self):
        """El importe parado debe aproximarse a bandera + (seg * precio_parado)."""
        self.motor.iniciar()
        time.sleep(1.0)
        trayecto = self.motor.finalizar()
        esperado = (self.tarifa.precio_bajada_bandera
                    + trayecto.segundos_parado * self.tarifa.precio_parado
                    + trayecto.segundos_movimiento * self.tarifa.precio_movimiento)
        self.assertAlmostEqual(trayecto.importe_total, esperado, delta=0.05)

    def test_callback_on_tick(self):
        self.motor.iniciar()
        time.sleep(0.5)
        self.motor.finalizar()
        self.assertFalse(self.motor.cola_tick.empty())

    def test_motor_no_activo_tras_finalizar(self):
        self.motor.iniciar()
        self.motor.finalizar()
        self.assertFalse(self.motor.activo)


# ══════════════════════════════════════════════════════════════════════════════
# TESTS: GestorAuth
# ══════════════════════════════════════════════════════════════════════════════

class TestGestorAuth(BaseTest):

    def setUp(self):
        super().setUp()
        with patch("taximetro.USERS_FILE", os.path.join(self.tmp, "usuarios.json")):
            self.auth = GestorAuth()

    def test_usuario_default_existe(self):
        with patch("taximetro.USERS_FILE", os.path.join(self.tmp, "usuarios.json")):
            auth = GestorAuth()
            self.assertTrue(auth.autenticar("admin", "1234"))

    def test_password_incorrecta(self):
        with patch("taximetro.USERS_FILE", os.path.join(self.tmp, "usuarios.json")):
            auth = GestorAuth()
            self.assertFalse(auth.autenticar("admin", "wrongpass"))

    def test_usuario_inexistente(self):
        with patch("taximetro.USERS_FILE", os.path.join(self.tmp, "usuarios.json")):
            auth = GestorAuth()
            self.assertFalse(auth.autenticar("noexiste", "1234"))

    def test_cambiar_password(self):
        ufile = os.path.join(self.tmp, "usuarios.json")
        with patch("taximetro.USERS_FILE", ufile):
            auth = GestorAuth()
            auth.cambiar_password("admin", "nueva_clave")
            auth2 = GestorAuth()
            self.assertTrue(auth2.autenticar("admin", "nueva_clave"))
            self.assertFalse(auth2.autenticar("admin", "1234"))


# ══════════════════════════════════════════════════════════════════════════════
# TESTS: GestorConfig
# ══════════════════════════════════════════════════════════════════════════════

class TestGestorConfig(BaseTest):

    def test_tarifa_por_defecto(self):
        cfile = os.path.join(self.tmp, "config.json")
        with patch("taximetro.CONFIG_FILE", cfile):
            gc = GestorConfig()
            self.assertAlmostEqual(gc.tarifa.precio_parado, 0.02)

    def test_persistencia_tarifas(self):
        cfile = os.path.join(self.tmp, "config.json")
        with patch("taximetro.CONFIG_FILE", cfile):
            gc = GestorConfig()
            gc.actualizar(0.05, 0.10, 2.00)

        with patch("taximetro.CONFIG_FILE", cfile):
            gc2 = GestorConfig()
            self.assertAlmostEqual(gc2.tarifa.precio_parado, 0.05)
            self.assertAlmostEqual(gc2.tarifa.precio_movimiento, 0.10)
            self.assertAlmostEqual(gc2.tarifa.precio_bajada_bandera, 2.00)

    def test_actualizar_tarifa(self):
        cfile = os.path.join(self.tmp, "config.json")
        with patch("taximetro.CONFIG_FILE", cfile):
            gc = GestorConfig()
            gc.actualizar(0.03, 0.08, 1.75)
            self.assertAlmostEqual(gc.tarifa.precio_parado, 0.03)


# ══════════════════════════════════════════════════════════════════════════════
# TESTS: GestorHistorial
# ══════════════════════════════════════════════════════════════════════════════

class TestGestorHistorial(BaseTest):

    def _trayecto(self, id_="t001", importe=5.0):
        return Trayecto(id=id_, fecha_inicio="01/01/2026 10:00:00",
                        fecha_fin="01/01/2026 10:15:00",
                        segundos_parado=30, segundos_movimiento=60,
                        importe_total=importe)

    def test_historial_vacio_inicial(self):
        hfile = os.path.join(self.tmp, "historial.json")
        with patch("taximetro.HISTORY_FILE", hfile):
            gh = GestorHistorial()
            self.assertEqual(len(gh.trayectos), 0)

    def test_agregar_trayecto(self):
        hfile = os.path.join(self.tmp, "historial.json")
        with patch("taximetro.HISTORY_FILE", hfile):
            gh = GestorHistorial()
            gh.agregar(self._trayecto("t001", 5.0))
            self.assertEqual(len(gh.trayectos), 1)

    def test_persistencia_historial(self):
        hfile = os.path.join(self.tmp, "historial.json")
        with patch("taximetro.HISTORY_FILE", hfile):
            gh = GestorHistorial()
            gh.agregar(self._trayecto("t001", 5.0))
            gh.agregar(self._trayecto("t002", 3.5))

        with patch("taximetro.HISTORY_FILE", hfile):
            gh2 = GestorHistorial()
            self.assertEqual(len(gh2.trayectos), 2)

    def test_total_recaudado(self):
        hfile = os.path.join(self.tmp, "historial.json")
        with patch("taximetro.HISTORY_FILE", hfile):
            gh = GestorHistorial()
            gh.agregar(self._trayecto("t001", 5.0))
            gh.agregar(self._trayecto("t002", 3.0))
            self.assertAlmostEqual(gh.total_recaudado(), 8.0)

    def test_total_recaudado_vacio(self):
        hfile = os.path.join(self.tmp, "historial.json")
        with patch("taximetro.HISTORY_FILE", hfile):
            gh = GestorHistorial()
            self.assertAlmostEqual(gh.total_recaudado(), 0.0)


# ══════════════════════════════════════════════════════════════════════════════
# RUNNER
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
