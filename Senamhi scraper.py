# ============================================================
#   SCRAPER SENAMHI - Mapa interactivo + Descarga CSV
#   Curso: Minería de Datos - UPeU
# ============================================================
# INSTALACIÓN:
#   pip install requests flask beautifulsoup4 playwright
#   python -m playwright install chromium
# ============================================================

import os, time, threading, webbrowser, re, json, subprocess, urllib.request
import requests as req
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, Response

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":    "https://www.senamhi.gob.pe/",
}

REGIONES = {
    "amazonas":      {"nombre": "Amazonas",       "lat": -4.5,  "lon": -77.5},
    "ancash":        {"nombre": "Áncash",          "lat": -9.5,  "lon": -77.5},
    "apurimac":      {"nombre": "Apurímac",        "lat": -14.0, "lon": -73.0},
    "arequipa":      {"nombre": "Arequipa",        "lat": -15.8, "lon": -72.0},
    "ayacucho":      {"nombre": "Ayacucho",        "lat": -13.5, "lon": -74.0},
    "cajamarca":     {"nombre": "Cajamarca",       "lat": -7.0,  "lon": -78.5},
    "cusco":         {"nombre": "Cusco",           "lat": -13.5, "lon": -71.5},
    "huancavelica":  {"nombre": "Huancavelica",    "lat": -12.8, "lon": -75.0},
    "huanuco":       {"nombre": "Huánuco",         "lat": -9.5,  "lon": -76.0},
    "ica":           {"nombre": "Ica",             "lat": -14.5, "lon": -75.5},
    "junin":         {"nombre": "Junín",           "lat": -11.5, "lon": -75.0},
    "la-libertad":   {"nombre": "La Libertad",     "lat": -8.0,  "lon": -78.5},
    "lambayeque":    {"nombre": "Lambayeque",      "lat": -6.5,  "lon": -79.5},
    "lima":          {"nombre": "Lima / Callao",   "lat": -11.5, "lon": -76.5},
    "loreto":        {"nombre": "Loreto",          "lat": -4.5,  "lon": -75.0},
    "madre-de-dios": {"nombre": "Madre de Dios",   "lat": -11.5, "lon": -70.5},
    "moquegua":      {"nombre": "Moquegua",        "lat": -16.5, "lon": -70.9},
    "pasco":         {"nombre": "Pasco",           "lat": -10.5, "lon": -75.5},
    "piura":         {"nombre": "Piura",           "lat": -5.5,  "lon": -80.0},
    "puno":          {"nombre": "Puno",            "lat": -14.5, "lon": -70.0},
    "san-martin":    {"nombre": "San Martín",      "lat": -6.5,  "lon": -76.5},
    "tacna":         {"nombre": "Tacna",           "lat": -17.5, "lon": -70.3},
    "tumbes":        {"nombre": "Tumbes",          "lat": -3.5,  "lon": -80.5},
    "ucayali":       {"nombre": "Ucayali",         "lat": -9.5,  "lon": -74.0},
}

TIPO_LABELS = {
    "M":  "Estación Meteorológica Convencional",
    "MA": "Estación Meteorológica Automática",
    "H":  "Estación Hidrológica Convencional",
    "HA": "Estación Hidrológica Automática",
}

EDGE_PATHS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
PUERTO_DEBUG = 9222
PERFIL_EDGE  = r'C:\edge-debug-profile'

# Estado global de descarga (para pausar/cancelar)
estado_descarga = {
    "activa":    False,
    "pausada":   False,
    "cancelada": False,
    "progreso":  0,
    "total":     0,
    "actual":    "",
    "log":       [],
}

def edge_corriendo():
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PUERTO_DEBUG}/json/version', timeout=2)
        return True
    except:
        return False

def lanzar_edge():
    if edge_corriendo():
        return None
    edge_path = next((p for p in EDGE_PATHS if os.path.exists(p)), None)
    if not edge_path:
        raise Exception("No se encontró msedge.exe en el sistema")
    proceso = subprocess.Popen([
        edge_path,
        f'--remote-debugging-port={PUERTO_DEBUG}',
        '--remote-debugging-address=127.0.0.1',
        f'--user-data-dir={PERFIL_EDGE}',
        '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(1)
        if edge_corriendo():
            return proceso
    raise Exception("Edge no respondió en el tiempo esperado")

# ── APIs ───────────────────────────────────────────────────

@app.route("/api/regiones")
def api_regiones():
    return jsonify(REGIONES)

@app.route("/api/estaciones/<dp>")
def api_estaciones(dp):
    url = f"https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/?dp={dp}"
    try:
        r = req.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        return jsonify({"error": str(e), "estaciones": []})

    match = re.search(r'var\s+PruebaTest\s*=\s*(\[.*?\])\s*;', r.text, re.DOTALL)
    if not match:
        return jsonify({"error": "No se encontró PruebaTest", "estaciones": []})

    raw = match.group(1)
    raw = re.sub(r':\s*(-?)\.(\d+)', r': \g<1>0.\2', raw)

    try:
        est_raw = json.loads(raw)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"JSON inválido: {e}", "estaciones": []})

    estaciones = []
    for e in est_raw:
        estado = e.get("estado", "")
        ico    = e.get("ico", "M")
        tipo   = ("HA" if ico=="H" else "MA") if estado=="AUTOMATICA" else ("H" if ico=="H" else "M")
        estaciones.append({
            "cod": e.get("cod",""), "cod_old": e.get("cod_old",""),
            "nom": e.get("nom","").strip(), "lat": e.get("lat",0),
            "lon": e.get("lon",0), "tipo": tipo,
            "cate": e.get("cate",""), "estado": estado, "ico": ico,
        })
    return jsonify({"estaciones": estaciones, "total": len(estaciones)})

@app.route("/api/fechas")
def api_fechas():
    cod     = request.args.get("cod","")
    est     = request.args.get("estado","DIFERIDO")
    ico     = request.args.get("ico","M")
    cate    = request.args.get("cate","CO")
    cod_old = request.args.get("cod_old","")
    url = (f"https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php"
           f"?cod={cod}&estado={est}&tipo_esta={ico}&cate={cate}&cod_old={cod_old}")
    try:
        r = req.get(url, headers=HEADERS, timeout=15)
        soup   = BeautifulSoup(r.text, "html.parser")
        select = soup.find("select", {"name": "CBOFiltro"})
        if not select:
            return jsonify({"fechas": []})
        fechas = []
        for opt in select.find_all("option"):
            v = opt.get("value","")
            if len(v)==6 and v.isdigit():
                fechas.append({"label": f"{v[:4]}-{v[4:]}", "value": v})
        return jsonify({"fechas": fechas})
    except Exception as e:
        return jsonify({"fechas": [], "error": str(e)})

@app.route("/api/estado-descarga")
def api_estado_descarga():
    return jsonify(estado_descarga)

@app.route("/api/pausar", methods=["POST"])
def api_pausar():
    estado_descarga["pausada"] = not estado_descarga["pausada"]
    return jsonify({"pausada": estado_descarga["pausada"]})

@app.route("/api/cancelar", methods=["POST"])
def api_cancelar():
    estado_descarga["cancelada"] = True
    estado_descarga["pausada"]   = False
    return jsonify({"ok": True})

def log(msg):
    print(msg)
    estado_descarga["log"].append(msg)
    if len(estado_descarga["log"]) > 200:
        estado_descarga["log"] = estado_descarga["log"][-200:]

def descargar_con_playwright(estaciones_a_descargar, dp):
    """
    Descarga todos los CSV de una lista de estaciones usando Playwright + Edge.
    Estructura: datos_senamhi/REGION/TIPO/NOMBRE/cod_YYYY-MM.csv
    """
    global estado_descarga
    estado_descarga.update({
        "activa": True, "pausada": False, "cancelada": False,
        "progreso": 0, "log": []
    })

    nombre_region = REGIONES.get(dp, {}).get("nombre", dp)

    # Contar total de trabajos (estaciones × fechas) — estimado
    total_est = len(estaciones_a_descargar)
    estado_descarga["total"] = total_est
    ok_total, err_total = 0, 0

    try:
        from playwright.sync_api import sync_playwright

        proceso_edge = lanzar_edge()
        time.sleep(2)

        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{PUERTO_DEBUG}")
            context = browser.contexts[0]

            for idx, est in enumerate(estaciones_a_descargar):
                # ── Verificar cancelación ──────────────────
                if estado_descarga["cancelada"]:
                    log("⛔ Descarga cancelada por el usuario")
                    break

                # ── Esperar si está pausada ────────────────
                while estado_descarga["pausada"]:
                    time.sleep(0.5)
                    if estado_descarga["cancelada"]:
                        break

                if estado_descarga["cancelada"]:
                    break

                cod     = est["cod"]
                cod_old = est.get("cod_old","")
                nom     = est["nom"].strip()
                tipo    = est["tipo"]
                ico     = est["ico"]
                estado_est = est["estado"]
                cate    = est["cate"]
                fechas  = est.get("fechas", [])

                tipo_carpeta = TIPO_LABELS.get(tipo, tipo)
                nom_carpeta  = "".join(c for c in nom if c.isalnum() or c in " _-").strip()
                carpeta = os.path.join("datos_senamhi", nombre_region, tipo_carpeta, nom_carpeta)
                os.makedirs(carpeta, exist_ok=True)

                estado_descarga["actual"]   = f"[{idx+1}/{total_est}] {nom}"
                estado_descarga["progreso"] = idx

                log(f"\n{'='*50}")
                log(f"[{idx+1}/{total_est}] {nom} ({cod}) — {tipo_carpeta}")
                log(f"{'='*50}")

                if not fechas:
                    log(f"  ⚠️ Sin fechas disponibles, saltando")
                    continue

                url_grafico = (
                    f"https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php"
                    f"?cod={cod}&estado={estado_est}&tipo_esta={ico}&cate={cate}&cod_old={cod_old}"
                )

                page = context.new_page()
                try:
                    page.goto(url_grafico, wait_until="domcontentloaded")
                    time.sleep(2)

                    # Ir a pestaña Tabla
                    for sel in ['a:has-text("Tabla")', '#tabla-tab', '.nav-link:has-text("Tabla")']:
                        try:
                            el = page.locator(sel).first
                            if el.is_visible(timeout=2000):
                                el.click(); break
                        except:
                            pass
                    time.sleep(1)

                    # Esperar token Turnstile
                    log("  ⏳ Esperando captcha...")
                    for _ in range(60):
                        tokens = page.evaluate("""
                            () => Array.from(
                                document.querySelectorAll('input[name="cf-turnstile-response"]')
                            ).map(el => el.value)
                        """)
                        if tokens and tokens[0] and len(tokens[0]) > 20:
                            log("  ✅ Captcha resuelto")
                            break
                        time.sleep(0.5)

                    ok_est, err_est = 0, 0

                    for item in fechas:
                        # Verificar cancelación en cada fecha
                        if estado_descarga["cancelada"]:
                            break
                        while estado_descarga["pausada"]:
                            time.sleep(0.5)
                            if estado_descarga["cancelada"]:
                                break
                        if estado_descarga["cancelada"]:
                            break

                        filtro_valor = item["value"]
                        label        = item["label"]
                        archivo      = f"{cod}_{label}.csv"
                        ruta         = os.path.join(carpeta, archivo)

                        if os.path.exists(ruta) and os.path.getsize(ruta) > 50:
                            log(f"  ⏭️  {label} ya existe")
                            ok_est += 1
                            continue

                        try:
                            page.select_option('select[name="CBOFiltro"]', filtro_valor)
                            time.sleep(2)

                            frame = None
                            for _ in range(30):
                                try:
                                    f = page.frame(name="contenedor")
                                    if f:
                                        contenido = f.content()
                                        if "dataTable" in contenido or "tableHidden" in contenido:
                                            frame = f; break
                                except:
                                    pass
                                time.sleep(0.5)

                            if not frame:
                                log(f"  ❌ {label}: sin datos en iframe")
                                err_est += 1
                                continue

                            csv_text = frame.evaluate("""
                                () => {
                                    const csv = [];
                                    const th = document.getElementById('tableHidden');
                                    const td = document.getElementById('dataTable');
                                    const ct = document.getElementById('container');
                                    if (ct) {
                                        const divs = ct.getElementsByTagName('div');
                                        if (divs.length >= 2)
                                            csv.push(divs[0].innerText.trim()+','+divs[1].innerText.trim());
                                    }
                                    for (const tbl of [th, td]) {
                                        if (!tbl) continue;
                                        for (const row of tbl.getElementsByTagName('tr')) {
                                            const cols = row.querySelectorAll('td,th');
                                            csv.push(Array.from(cols).map(c=>c.innerText.trim()).join(','));
                                        }
                                    }
                                    return csv.join('\\n');
                                }
                            """)

                            if csv_text and len(csv_text) > 20:
                                with open(ruta, "w", encoding="utf-8-sig") as f:
                                    f.write(csv_text)
                                log(f"  ✅ {label} → {archivo}")
                                ok_est += 1; ok_total += 1
                            else:
                                log(f"  ⚠️  {label}: vacío")
                                err_est += 1; err_total += 1

                        except Exception as e:
                            log(f"  ❌ {label}: {e}")
                            err_est += 1; err_total += 1

                    log(f"\n  📊 {nom}: {ok_est} OK, {err_est} errores")

                except Exception as e:
                    log(f"  ❌ Error en estación {nom}: {e}")
                finally:
                    page.close()

                estado_descarga["progreso"] = idx + 1

            browser.close()

        if proceso_edge:
            proceso_edge.terminate()

    except Exception as e:
        log(f"\n❌ Error crítico: {e}")
    finally:
        estado_descarga["activa"]  = False
        estado_descarga["actual"]  = ""
        log(f"\n🎉 Proceso finalizado — {ok_total} archivos descargados, {err_total} errores")

@app.route("/api/descargar-region", methods=["POST"])
def api_descargar_region():
    """Descarga todas las estaciones de una región o las seleccionadas."""
    if estado_descarga["activa"]:
        return jsonify({"error": "Ya hay una descarga en curso"}), 400

    data       = request.json or {}
    dp         = data.get("dp", "")
    estaciones = data.get("estaciones", [])  # lista con fechas ya incluidas

    if not estaciones:
        return jsonify({"error": "No hay estaciones para descargar"}), 400

    # Lanzar descarga en hilo separado para no bloquear Flask
    t = threading.Thread(
        target=descargar_con_playwright,
        args=(estaciones, dp),
        daemon=True
    )
    t.start()

    return jsonify({"ok": True, "total": len(estaciones)})

@app.route("/")
def index():
    return Response(HTML, mimetype="text/html")

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>SENAMHI - Descarga de Datos</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#f0f4f8;height:100vh;overflow:hidden}
header{background:linear-gradient(135deg,#004a8f,#0099d6);color:white;padding:13px 20px;box-shadow:0 2px 8px rgba(0,0,0,.25)}
header h1{font-size:1.1rem;font-weight:700}
header p{font-size:.75rem;opacity:.85;margin-top:2px}
.app{display:flex;height:calc(100vh - 58px)}
.panel{width:330px;background:white;display:flex;flex-direction:column;border-right:1px solid #dce3ed;overflow:hidden;flex-shrink:0}
.sec{padding:12px 14px;border-bottom:1px solid #eef1f5}
.sec h3{font-size:.68rem;text-transform:uppercase;letter-spacing:.07em;color:#6b7a8d;margin-bottom:7px}
select,input[type=text]{width:100%;padding:7px 10px;border:1.5px solid #d0d9e4;border-radius:7px;font-size:.85rem;outline:none;transition:border-color .2s}
select:focus,input:focus{border-color:#0099d6}
.tipos{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}
.tbtn{padding:4px 8px;border-radius:16px;border:1.5px solid #ccc;background:white;cursor:pointer;font-size:.7rem;transition:all .15s}
.tbtn[data-t="M"].on{background:#27ae60;color:white;border-color:#27ae60}
.tbtn[data-t="MA"].on{background:#2980b9;color:white;border-color:#2980b9}
.tbtn[data-t="H"].on{background:#e67e22;color:white;border-color:#e67e22}
.tbtn[data-t="HA"].on{background:#8e44ad;color:white;border-color:#8e44ad}
.lista-wrap{flex:1;overflow-y:auto}
.est{padding:7px 12px;cursor:pointer;border-bottom:1px solid #f0f4f8;display:flex;align-items:center;gap:7px;transition:background .1s}
.est:hover{background:#f0f8ff}
.est.sel{background:#e6f4ff;border-left:3px solid #0099d6}
.est input[type=checkbox]{width:15px;height:15px;cursor:pointer;flex-shrink:0}
.dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.en{font-size:.82rem;font-weight:600;line-height:1.3}
.et{font-size:.68rem;color:#888}
.frow{display:flex;gap:6px}
.frow>div{flex:1}
.frow label{font-size:.7rem;color:#6b7a8d;display:block;margin-bottom:3px}
.fechas-info{font-size:.7rem;color:#2980b9;margin-top:4px;min-height:14px}

/* Botones principales */
.btns{display:flex;flex-direction:column;gap:6px;margin-top:8px}
.btn{width:100%;padding:10px;border:none;border-radius:8px;font-size:.85rem;font-weight:700;cursor:pointer;transition:opacity .2s}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn-region{background:linear-gradient(135deg,#1a5276,#2980b9);color:white}
.btn-sel{background:linear-gradient(135deg,#004a8f,#0099d6);color:white}
.btn-pausar{background:#e67e22;color:white;display:none}
.btn-cancelar{background:#c0392b;color:white;display:none}
.btn:hover:not(:disabled){opacity:.88}

/* Barra de progreso */
.prog-wrap{padding:10px 14px;border-top:1px solid #eee;display:none}
.prog-label{font-size:.72rem;color:#555;margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.prog-bar{width:100%;height:8px;background:#e0e0e0;border-radius:4px;overflow:hidden}
.prog-fill{height:100%;background:linear-gradient(90deg,#0099d6,#004a8f);border-radius:4px;transition:width .3s}
.prog-txt{font-size:.7rem;color:#888;margin-top:3px;text-align:right}

/* Log */
.log-wrap{padding:8px 14px;border-top:1px solid #eee;display:none;flex-direction:column}
.log-wrap h3{font-size:.68rem;text-transform:uppercase;color:#6b7a8d;margin-bottom:5px}
.log-box{background:#1e1e1e;color:#d4d4d4;font-size:.7rem;font-family:monospace;padding:8px;border-radius:6px;height:100px;overflow-y:auto;line-height:1.5}

/* Modal */
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.5);display:none;align-items:center;justify-content:center;z-index:9999}
.modal-bg.show{display:flex}
.modal{background:white;border-radius:14px;padding:28px;max-width:420px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,.2)}
.modal h2{font-size:1rem;margin-bottom:10px;color:#004a8f}
.modal p{font-size:.85rem;color:#444;margin-bottom:18px;line-height:1.5}
.modal-btns{display:flex;gap:10px;justify-content:flex-end}
.modal-btns button{padding:9px 18px;border:none;border-radius:8px;font-size:.85rem;font-weight:600;cursor:pointer}
.btn-confirmar{background:#004a8f;color:white}
.btn-cancelar-modal{background:#eee;color:#333}

#map{flex:1}
.leg{background:white;padding:8px 12px;border-radius:9px;box-shadow:0 2px 8px rgba(0,0,0,.15);font-size:.75rem;line-height:1.8}
.li{display:flex;align-items:center;gap:6px}
.ld{width:10px;height:10px;border-radius:50%}
.spin{display:inline-block;width:12px;height:12px;border:2px solid #ccc;border-top-color:#0099d6;border-radius:50%;animation:sp .7s linear infinite;vertical-align:middle;margin-right:4px}
@keyframes sp{to{transform:rotate(360deg)}}
</style>
</head>
<body>

<!-- Modal de confirmación -->
<div class="modal-bg" id="modal">
  <div class="modal">
    <h2 id="modal-titulo">Confirmar descarga</h2>
    <p id="modal-texto"></p>
    <div class="modal-btns">
      <button class="btn-cancelar-modal" onclick="cerrarModal()">Cancelar</button>
      <button class="btn-confirmar" id="modal-confirmar">Descargar</button>
    </div>
  </div>
</div>

<header>
  <h1>🌦️ SENAMHI — Descarga Masiva de Datos Hidrometeorológicos</h1>
  <p>① Región → ② Tipo → ③ Selecciona estaciones → ④ Fechas → ⑤ Descargar</p>
</header>

<div class="app">
  <div class="panel">

    <div class="sec">
      <h3>① Región</h3>
      <select id="selReg"><option value="">— Selecciona una región —</option></select>
    </div>

    <div class="sec">
      <h3>② Tipo de estación</h3>
      <div class="tipos">
        <button class="tbtn on" data-t="M">🟢 Met. Conv.</button>
        <button class="tbtn on" data-t="MA">🔵 Met. Auto.</button>
        <button class="tbtn on" data-t="H">🟠 Hid. Conv.</button>
        <button class="tbtn on" data-t="HA">🟣 Hid. Auto.</button>
      </div>
    </div>

    <div class="sec" style="padding-bottom:5px">
      <h3>③ Estaciones — <span id="conteo" style="color:#0099d6">elige una región</span>
        <span id="sel-count" style="color:#e67e22;margin-left:6px"></span>
      </h3>
    </div>
    <div class="lista-wrap" id="lista">
      <div style="padding:20px;color:#aaa;text-align:center;font-size:.82rem">Selecciona una región para ver las estaciones</div>
    </div>

    <div class="sec">
      <h3>④ Rango de fechas</h3>
      <div class="frow">
        <div><label>Desde (YYYY-MM)</label><input type="text" id="fi" value="2021-01"></div>
        <div><label>Hasta (YYYY-MM)</label><input type="text" id="ff" value="2026-01"></div>
      </div>
      <div class="fechas-info" id="fechas-info"></div>

      <div class="btns">
        <button class="btn btn-region" id="btnRegion" disabled>
          ⬇️ Descargar región completa
        </button>
        <button class="btn btn-sel" id="btnSel" disabled>
          ☑️ Descargar seleccionadas
        </button>
        <button class="btn btn-pausar" id="btnPausar">⏸️ Pausar</button>
        <button class="btn btn-cancelar" id="btnCancelar">⛔ Cancelar descarga</button>
      </div>
    </div>

    <div class="prog-wrap" id="progWrap">
      <div class="prog-label" id="progLabel">Iniciando...</div>
      <div class="prog-bar"><div class="prog-fill" id="progFill" style="width:0%"></div></div>
      <div class="prog-txt" id="progTxt">0 / 0</div>
    </div>

    <div class="log-wrap" id="logWrap">
      <h3>📋 Log de descarga</h3>
      <div class="log-box" id="logBox"></div>
    </div>

  </div>

  <div id="map"></div>
</div>

<script>
const COLS={M:"#27ae60",MA:"#2980b9",H:"#e67e22",HA:"#8e44ad"};
const LABS={M:"Met. Convencional",MA:"Met. Automática",H:"Hid. Convencional",HA:"Hid. Automática"};
const TIPO_FULL={M:"Estación Meteorológica Convencional",MA:"Estación Meteorológica Automática",
                 H:"Estación Hidrológica Convencional",HA:"Estación Hidrológica Automática"};

let mapa, markers=[], estData=[], dpActual="";
let tiposOn=new Set(["M","MA","H","HA"]);
let checkboxes={};   // cod → {var, est}
let pollingInterval=null;
let accionModal=null;

// ── Mapa ────────────────────────────────────────────────────
mapa=L.map("map").setView([-9,-75],5);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:"© OpenStreetMap"}).addTo(mapa);
const leg=L.control({position:"bottomright"});
leg.onAdd=()=>{
  const d=L.DomUtil.create("div","leg");
  d.innerHTML="<b style='font-size:.78rem'>Tipo de estación</b><br>"+
    Object.entries(LABS).map(([t,l])=>`<div class="li"><div class="ld" style="background:${COLS[t]}"></div>${l}</div>`).join("");
  return d;
};
leg.addTo(mapa);

// ── Regiones ────────────────────────────────────────────────
fetch("/api/regiones").then(r=>r.json()).then(data=>{
  const sel=document.getElementById("selReg");
  Object.entries(data).sort((a,b)=>a[1].nombre.localeCompare(b[1].nombre)).forEach(([dp,info])=>{
    const o=document.createElement("option");o.value=dp;o.textContent=info.nombre;sel.appendChild(o);
  });
});

document.getElementById("selReg").addEventListener("change",async function(){
  dpActual=this.value;if(!dpActual)return;
  const regiones=await fetch("/api/regiones").then(r=>r.json());
  mapa.setView([regiones[dpActual].lat,regiones[dpActual].lon],7);
  document.getElementById("conteo").textContent="cargando...";
  document.getElementById("lista").innerHTML=
    "<div style='padding:20px;color:#aaa;text-align:center'><span class='spin'></span> Obteniendo estaciones...</div>";
  document.getElementById("btnRegion").disabled=true;
  document.getElementById("btnSel").disabled=true;

  const res=await fetch(`/api/estaciones/${dpActual}`);
  const data=await res.json();
  if(data.error||!data.estaciones||!data.estaciones.length){
    document.getElementById("conteo").textContent="0 estaciones";
    document.getElementById("lista").innerHTML=`<div style='padding:16px;color:#c0392b;font-size:.82rem'>❌ ${data.error||"Sin estaciones"}</div>`;
    return;
  }
  estData=data.estaciones;
  renderizar();
  document.getElementById("btnRegion").disabled=false;
  document.getElementById("fechas-info").textContent="📅 Las fechas se obtienen por estación al descargar";
});

// ── Renderizar estaciones ───────────────────────────────────
function renderizar(){
  markers.forEach(m=>mapa.removeLayer(m));markers=[];checkboxes={};
  const lista=document.getElementById("lista");lista.innerHTML="";
  let visibles=0;

  // Agrupar por tipo para mostrar encabezados
  const grupos={};
  estData.forEach(est=>{
    if(!tiposOn.has(est.tipo))return;
    if(!grupos[est.tipo])grupos[est.tipo]=[];
    grupos[est.tipo].push(est);
  });

  Object.entries(grupos).forEach(([tipo,ests])=>{
    // Encabezado de grupo con "seleccionar todos"
    const header=document.createElement("div");
    header.style.cssText="padding:6px 12px;background:#f8f9fa;border-bottom:1px solid #eee;display:flex;align-items:center;gap:6px;cursor:pointer";
    const cbAll=document.createElement("input");cbAll.type="checkbox";cbAll.style.cursor="pointer";
    const lbl=document.createElement("span");
    lbl.style.cssText=`font-size:.72rem;font-weight:700;color:${COLS[tipo]}`;
    lbl.textContent=`${TIPO_FULL[tipo]} (${ests.length})`;
    header.appendChild(cbAll);header.appendChild(lbl);
    cbAll.addEventListener("change",()=>{
      ests.forEach(e=>{if(checkboxes[e.cod])checkboxes[e.cod].checked=cbAll.checked;});
      actualizarContadorSel();
    });
    lista.appendChild(header);

    ests.forEach(est=>{
      visibles++;
      const color=COLS[est.tipo]||"#999";

      // Marcador mapa
      const icono=L.divIcon({className:"",
        html:`<div style="width:12px;height:12px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.4)"></div>`,
        iconSize:[12,12],iconAnchor:[6,6]});
      const m=L.marker([est.lat,est.lon],{icon:icono}).addTo(mapa);
      m.bindPopup(`<div style="min-width:180px">
        <b style="font-size:.9rem">${est.nom}</b><br>
        <span style="font-size:.78rem;color:#555">Código: <b>${est.cod}</b><br>
        ${LABS[est.tipo]} · ${est.estado}</span><br>
        <button onclick="toggleCheck('${est.cod}')"
          style="margin-top:7px;padding:5px 0;width:100%;background:#004a8f;color:white;
                 border:none;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:600">
          ☑️ Seleccionar / deseleccionar</button></div>`);
      markers.push(m);

      // Item con checkbox
      const item=document.createElement("div");item.className="est";item.dataset.cod=est.cod;
      const cb=document.createElement("input");cb.type="checkbox";cb.dataset.cod=est.cod;
      cb.addEventListener("change",actualizarContadorSel);
      checkboxes[est.cod]=cb;
      const dot=document.createElement("div");dot.className="dot";dot.style.background=color;
      const info=document.createElement("div");
      info.innerHTML=`<div class="en">${est.nom}</div><div class="et">${LABS[est.tipo]} · ${est.cod}</div>`;
      item.appendChild(cb);item.appendChild(dot);item.appendChild(info);
      item.addEventListener("click",(ev)=>{
        if(ev.target===cb)return;
        cb.checked=!cb.checked;actualizarContadorSel();
        mapa.setView([est.lat,est.lon],11);m.openPopup();
      });
      lista.appendChild(item);
    });
  });

  document.getElementById("conteo").textContent=`${visibles} de ${estData.length} estaciones`;
}

function toggleCheck(cod){
  if(checkboxes[cod]){checkboxes[cod].checked=!checkboxes[cod].checked;actualizarContadorSel();}
}

function actualizarContadorSel(){
  const n=Object.values(checkboxes).filter(cb=>cb.checked).length;
  const el=document.getElementById("sel-count");
  el.textContent=n>0?`(${n} seleccionadas)`:"";
  document.getElementById("btnSel").disabled=n===0;
}

document.querySelectorAll(".tbtn").forEach(btn=>{
  btn.addEventListener("click",()=>{
    const t=btn.dataset.t;tiposOn.has(t)?tiposOn.delete(t):tiposOn.add(t);
    btn.classList.toggle("on",tiposOn.has(t));
    if(estData.length)renderizar();
  });
});

// ── Modal ───────────────────────────────────────────────────
function mostrarModal(titulo, texto, onConfirmar){
  document.getElementById("modal-titulo").textContent=titulo;
  document.getElementById("modal-texto").textContent=texto;
  document.getElementById("modal").classList.add("show");
  accionModal=onConfirmar;
  document.getElementById("modal-confirmar").onclick=()=>{cerrarModal();onConfirmar();};
}
function cerrarModal(){document.getElementById("modal").classList.remove("show");}

// ── Botón: Descargar región completa ───────────────────────
document.getElementById("btnRegion").addEventListener("click",()=>{
  const n=estData.filter(e=>tiposOn.has(e.tipo)).length;
  const fi=document.getElementById("fi").value;
  const ff=document.getElementById("ff").value;
  mostrarModal(
    "⬇️ Descargar región completa",
    `Se descargarán TODAS las estaciones visibles (${n}) de ${(document.getElementById("selReg").selectedOptions[0]||{}).text||dpActual}, desde ${fi} hasta ${ff}.\n\nEste proceso puede tardar bastante tiempo.`,
    ()=>iniciarDescarga(estData.filter(e=>tiposOn.has(e.tipo)))
  );
});

// ── Botón: Descargar seleccionadas ─────────────────────────
document.getElementById("btnSel").addEventListener("click",()=>{
  const seleccionadas=estData.filter(e=>checkboxes[e.cod]&&checkboxes[e.cod].checked);
  const fi=document.getElementById("fi").value;
  const ff=document.getElementById("ff").value;
  mostrarModal(
    "☑️ Descargar seleccionadas",
    `Se descargarán ${seleccionadas.length} estaciones seleccionadas, desde ${fi} hasta ${ff}.`,
    ()=>iniciarDescarga(seleccionadas)
  );
});

// ── Iniciar descarga ────────────────────────────────────────
async function iniciarDescarga(estaciones){
  const fi=document.getElementById("fi").value.trim();
  const ff=document.getElementById("ff").value.trim();
  if(!/^\d{4}-\d{2}$/.test(fi)||!/^\d{4}-\d{2}$/.test(ff)){
    alert("Formato de fecha incorrecto. Usa YYYY-MM");return;
  }

  // Obtener fechas de cada estación y filtrar por rango
  mostrarProgreso(true);
  document.getElementById("progLabel").textContent="Consultando fechas disponibles...";

  const estConFechas=[];
  for(const est of estaciones){
    const params=new URLSearchParams({
      cod:est.cod,estado:est.estado,ico:est.ico,cate:est.cate,cod_old:est.cod_old||""
    });
    try{
      const res=await fetch("/api/fechas?"+params);
      const data=await res.json();
      const fechas=(data.fechas||[]).filter(f=>f.label>=fi&&f.label<=ff);
      if(fechas.length>0) estConFechas.push({...est,fechas});
    }catch(e){
      console.warn("Error fechas",est.cod,e);
    }
  }

  if(!estConFechas.length){
    alert("No se encontraron fechas disponibles en el rango seleccionado.");
    mostrarProgreso(false);return;
  }

  // Enviar al backend
  const res=await fetch("/api/descargar-region",{
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({dp:dpActual, estaciones:estConFechas})
  });
  const data=await res.json();
  if(data.error){alert("Error: "+data.error);mostrarProgreso(false);return;}

  // Mostrar controles de pausa/cancelar
  document.getElementById("btnPausar").style.display="block";
  document.getElementById("btnCancelar").style.display="block";
  document.getElementById("btnRegion").disabled=true;
  document.getElementById("btnSel").disabled=true;

  // Iniciar polling de progreso
  pollingInterval=setInterval(actualizarProgreso,1000);
}

// ── Progreso ────────────────────────────────────────────────
function mostrarProgreso(visible){
  document.getElementById("progWrap").style.display=visible?"block":"none";
  document.getElementById("logWrap").style.display=visible?"flex":"none";
}

async function actualizarProgreso(){
  const res=await fetch("/api/estado-descarga");
  const d=await res.json();

  const pct=d.total>0?Math.round((d.progreso/d.total)*100):0;
  document.getElementById("progFill").style.width=pct+"%";
  document.getElementById("progTxt").textContent=`${d.progreso} / ${d.total} estaciones`;
  document.getElementById("progLabel").textContent=d.actual||"Procesando...";

  // Log
  const box=document.getElementById("logBox");
  box.textContent=d.log.join("\n");
  box.scrollTop=box.scrollHeight;

  // Botón pausar
  const btnP=document.getElementById("btnPausar");
  btnP.textContent=d.pausada?"▶️ Reanudar":"⏸️ Pausar";
  btnP.style.background=d.pausada?"#27ae60":"#e67e22";

  // Terminó
  if(!d.activa&&d.progreso>0){
    clearInterval(pollingInterval);
    document.getElementById("btnPausar").style.display="none";
    document.getElementById("btnCancelar").style.display="none";
    document.getElementById("btnRegion").disabled=false;
    document.getElementById("btnSel").disabled=Object.values(checkboxes).filter(c=>c.checked).length===0;
    document.getElementById("progLabel").textContent="✅ Descarga finalizada";
  }
}

// ── Pausar / Cancelar ───────────────────────────────────────
document.getElementById("btnPausar").addEventListener("click",async()=>{
  await fetch("/api/pausar",{method:"POST"});
});

document.getElementById("btnCancelar").addEventListener("click",()=>{
  mostrarModal(
    "⛔ Cancelar descarga",
    "¿Estás seguro que deseas cancelar la descarga en curso? Los archivos ya descargados se conservarán.",
    async()=>{await fetch("/api/cancelar",{method:"POST"});}
  );
});
</script>
</body>
</html>"""

def abrir():
    time.sleep(1.3)
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    print("="*52)
    print("  SENAMHI — Mapa interactivo de estaciones")
    print("="*52)
    print("  Abriendo en: http://127.0.0.1:5000")
    print("  Para detener: Ctrl + C")
    print("="*52)
    threading.Thread(target=abrir, daemon=True).start()
    app.run(debug=False, port=5000)