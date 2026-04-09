# SCRAPER SENAMHI

Herramienta desarrollada para la extracción automática de datos climáticos desde estaciones del SENAMHI mediante una interfaz interactiva con mapa del Perú.

---

## Instalación

Ejecuta los siguientes comandos en tu entorno:

```bash
pip install requests flask beautifulsoup4 playwright
python -m playwright install chromium
```

---

## ¿Cómo usar?

1. Ejecuta el script principal.
2. Se abrirá un navegador con el mapa del Perú.
3. Selecciona una **región** → se mostrarán las estaciones disponibles.
4. Haz clic en una **estación** para seleccionarla.
5. Ingresa:

   * Fecha de inicio
   * Fecha de fin
6. Presiona **"Descargar CSV"**.
7. El sistema abrirá automáticamente **Microsoft Edge** y descargará los datos.

---

## Integrantes

* Apaza Hilasaca Celia Patricia
* Machaca Mamani Jhenderson Aaron
