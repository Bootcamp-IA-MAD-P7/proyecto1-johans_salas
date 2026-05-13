# 🚕 Taxímetro Digital

Prototipo de taxímetro digital desarrollado en Python con interfaz gráfica, autenticación, logs, historial persistente y tests unitarios.

---

## 🗂️ Estructura del proyecto

```
taximetro/
├── taximetro.py      # Aplicación principal (GUI + lógica)
├── tests.py          # Tests unitarios (unittest)
├── taximetro.log     # Log generado automáticamente al ejecutar
├── historial.json    # Historial de trayectos (generado automáticamente)
├── config.json       # Configuración de tarifas (generado automáticamente)
├── usuarios.json     # Usuarios y contraseñas (generado automáticamente)
└── README.md
```

---

## 🚀 Instalación y ejecución

### Requisitos
- Python 3.10 o superior
- `tkinter` (incluido en la instalación estándar de Python)

### Ejecutar la aplicación
```bash
python taximetro.py
```

### Ejecutar los tests
```bash
python -m pytest tests.py -v
# o con unittest directamente:
python tests.py
```

---

## 🔐 Acceso

Al iniciar, se solicita usuario y contraseña.

| Usuario |Contraseña | Rol   |
|---------|-----------|-------|
| admin   | 1234      | Admin |

> Puedes cambiar la contraseña desde la propia aplicación (botón 🔑).

---

## 🛠️ Tecnologías utilizadas

| Tecnología      | Uso                                |
|-----------------|------------------------------------|
| Python 3.10+    | Lenguaje principal                 |
| tkinter         | Interfaz gráfica (GUI)             |
| threading       | Bucle del taxímetro en paralelo    |
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

> Las tarifas son configurables desde la app sin necesidad de tocar el código.

---

## 📝 Logs

Cada acción relevante debería quedar registrada en `taximetro.log`:

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