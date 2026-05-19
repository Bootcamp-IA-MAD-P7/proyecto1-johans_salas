# 🚕 Taxímetro Digital

Prototipo avanzado de taxímetro digital desarrollado en Python utilizando el framework **KivyMD**. Esta aplicación ofrece una interfaz moderna con diseño de materiales, gestión de múltiples tipos de servicios, generación de facturas en PDF y un sistema robusto de persistencia de datos.

---

## 🗂️ Estructura del Proyecto

```text
Proyecto1_Taximetro_js/
├── taximetro.py          	# Aplicación principal (GUI KivyMD + Lógica)
├── tests_taximetro.py     	# Batería de pruebas unitarias
├── start_project.bat 		# Script de automatización (VENV + Instalación)
├── taximetro.log         	# Registro detallado de eventos y errores
├── historial.json        	# Base de datos local de trayectos realizados
├── usuarios.json         	# Gestión de credenciales (Hash SHA-256)
├── error.txt         	    # Captura y visualización de errores
└── facturas/             	# Carpeta de destino de las facturas PDF

---

## 🚀 Instalación y Arranque Automático
Para facilitar el despliegue, se ha incluido un archivo .bat que configura el entorno por ti.

Asegúrate de tener Python 3.10 o superior instalado.

Ejecuta el archivo iniciar_proyecto.bat.

¿Qué hace este script?: Crea un ambiente virtual (venv), instala las dependencias (kivy, kivymd, reportlab) y lanza la aplicación automáticamente.

Ejecución Manual:
pip install kivy==2.2.1 kivymd==1.1.1 reportlab
python taximetro.py

---

## 🔐 Control de Acceso

El sistema cuenta con un diálogo de autenticación obligatorio al inicio.

| Usuario |Contraseña | Rol   |
|---------|-----------|-------|
| admin   | 1234      | Admin |


---

## 🛠️ Tecnologías utilizadas

| Tecnología      | Uso                                |
|-----------------|------------------------------------|
| Python 3.10+    | Lenguaje principal                 |
| ReportLab       | Generación de facturas en PDF      |
| logging         | Trazabilidad y logs                |
| unittest        | Tests unitarios                    |
| json            | Persistencia de datos              |
| hashlib SHA-256 | Hash de contraseñas                |
| dataclasses     | Modelos de datos (Tarifa, Trayecto)|


---


## ⚙️ Tarifas por defecto

| Concepto          | Tarifa          |
|-------------------|-----------------|
| Bajada de bandera | 1,50 €          |
| Parado            | 0,02 €/segundo  |
| En movimiento     | 0,05 €/segundo  |


---


## 🚕 Servicios y Tarifas

| Servicio      |Cargo Fijo | Multiplicador|
|---------------|-----------|--------------|
| Económico     | 0.00 €    | 1.0x         |
| XL / Familiar | 2.00 €    | 1.4x         |
| Compartido    | 0.00 €    | 0.6x         |
| Pet Friendly  | 1.50 €    | 1.0x         |
| Flash         | 3.00 €    | 1.2x         |


---

## 📝 Logs

Cada acción relevante debería quedar registrada en 'taximetro.log':

```

2026-04-16 10:23:01 [INFO] Taximetro: Sesión iniciada por 'admin'.
2026-04-16 10:23:05 [INFO] Taximetro: Trayecto iniciado.
2026-04-16 10:23:10 [INFO] Taximetro: Estado cambiado a: movimiento
2026-04-16 10:23:45 [INFO] Taximetro: Trayecto finalizado. Importe: 3.27€

```

---

## 🧪 Cobertura de tests

| Clase/Módulo      | Tests                                              |
|-------------------|----------------------------------------------------|
| `Tarifa`          | Valores por defecto, serialización                 |
| `Trayecto`        | Creación, serialización roundtrip                  |
| `MotorTaximetro`  | Estado inicial, inicio, toggle, tarifas, callbacks |
| `GestorAuth`      | Login correcto/incorrecto, cambio de contraseña    |
| `GestorConfig`    | Persistencia, actualización de tarifas             |
| `GestorHistorial` | Agregar, persistencia, total recaudado             |
