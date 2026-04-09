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

estado_descarga = {
    "activa": False, "pausada": False, "cancelada": False,
    "progreso": 0, "total": 0, "actual": "", "log": [],
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
        raise Exception("No se encontró msedge.exe")
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
    raise Exception("Edge no respondió")

def log(msg):
    print(msg)
    estado_descarga["log"].append(msg)
    if len(estado_descarga["log"]) > 300:
        estado_descarga["log"] = estado_descarga["log"][-300:]

# ── APIs ────────────────────────────────────────────────────

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

@app.route("/api/fechas-region/<dp>")
def api_fechas_region(dp):
    """
    Obtiene la fecha más antigua disponible en la región consultando
    la primera estación que devuelva fechas. Así el rango de fechas
    es real y viene de SENAMHI, no hardcodeado.
    """
    url = f"https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/?dp={dp}"
    try:
        r = req.get(url, headers=HEADERS, timeout=15)
        match = re.search(r'var\s+PruebaTest\s*=\s*(\[.*?\])\s*;', r.text, re.DOTALL)
        if not match:
            return jsonify({"fi": "", "ff": ""})
        raw = re.sub(r':\s*(-?)\.(\d+)', r': \g<1>0.\2', match.group(1))
        est_raw = json.loads(raw)
    except Exception as e:
        return jsonify({"fi": "", "ff": "", "error": str(e)})

    fecha_min_global = None
    fecha_max_global = None

    # Consultar las primeras 5 estaciones para encontrar el rango real
    for est in est_raw[:5]:
        cod     = est.get("cod","")
        estado  = est.get("estado","DIFERIDO")
        ico     = est.get("ico","M")
        cate    = est.get("cate","CO")
        cod_old = est.get("cod_old","")
        url_graf = (f"https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php"
                    f"?cod={cod}&estado={estado}&tipo_esta={ico}&cate={cate}&cod_old={cod_old}")
        try:
            rg = req.get(url_graf, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(rg.text, "html.parser")
            select = soup.find("select", {"name": "CBOFiltro"})
            if not select:
                continue
            opciones = [o.get("value","") for o in select.find_all("option") if len(o.get("value",""))==6 and o.get("value","").isdigit()]
            if not opciones:
                continue
            # Convertir YYYYMM → YYYY-MM
            fi = f"{opciones[0][:4]}-{opciones[0][4:]}"
            ff = f"{opciones[-1][:4]}-{opciones[-1][4:]}"
            if fecha_min_global is None or fi < fecha_min_global:
                fecha_min_global = fi
            if fecha_max_global is None or ff > fecha_max_global:
                fecha_max_global = ff
        except Exception:
            continue

    return jsonify({
        "fi": fecha_min_global or "",
        "ff": fecha_max_global or "",
    })

@app.route("/api/fechas")
def api_fechas():
    """Obtiene todas las fechas disponibles de una estación específica."""
    cod     = request.args.get("cod","")
    estado  = request.args.get("estado","DIFERIDO")
    ico     = request.args.get("ico","M")
    cate    = request.args.get("cate","CO")
    cod_old = request.args.get("cod_old","")
    url = (f"https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php"
           f"?cod={cod}&estado={estado}&tipo_esta={ico}&cate={cate}&cod_old={cod_old}")
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

def descargar_con_playwright(estaciones_a_descargar, dp):
    global estado_descarga
    estado_descarga.update({
        "activa": True, "pausada": False, "cancelada": False,
        "progreso": 0, "total": len(estaciones_a_descargar), "log": [],
    })
    nombre_region = REGIONES.get(dp, {}).get("nombre", dp)
    ok_total, err_total = 0, 0

    try:
        from playwright.sync_api import sync_playwright
        proceso_edge = lanzar_edge()
        time.sleep(2)

        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{PUERTO_DEBUG}")
            context = browser.contexts[0]

            for idx, est in enumerate(estaciones_a_descargar):
                if estado_descarga["cancelada"]:
                    log("⛔ Cancelado por el usuario"); break
                while estado_descarga["pausada"]:
                    time.sleep(0.5)
                    if estado_descarga["cancelada"]: break
                if estado_descarga["cancelada"]: break

                cod        = est["cod"]
                cod_old    = est.get("cod_old","")
                nom        = est["nom"].strip()
                tipo       = est["tipo"]
                ico        = est["ico"]
                estado_est = est["estado"]
                cate       = est["cate"]
                fechas     = est.get("fechas", [])

                tipo_carpeta = TIPO_LABELS.get(tipo, tipo)
                nom_carpeta  = "".join(c for c in nom if c.isalnum() or c in " _-").strip()
                carpeta = os.path.join("datos_senamhi", nombre_region, tipo_carpeta, nom_carpeta)
                os.makedirs(carpeta, exist_ok=True)

                estado_descarga["actual"]   = f"[{idx+1}/{len(estaciones_a_descargar)}] {nom}"
                estado_descarga["progreso"] = idx
                log(f"\n{'='*48}")
                log(f"[{idx+1}/{len(estaciones_a_descargar)}] {nom} ({cod})")
                log(f"Tipo: {tipo_carpeta}")
                log(f"{'='*48}")

                if not fechas:
                    log("  ⚠️ Sin fechas, saltando"); continue

                url_grafico = (
                    f"https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php"
                    f"?cod={cod}&estado={estado_est}&tipo_esta={ico}&cate={cate}&cod_old={cod_old}"
                )
                page = context.new_page()
                try:
                    page.goto(url_grafico, wait_until="domcontentloaded")
                    time.sleep(2)
                    for sel in ['a:has-text("Tabla")', '#tabla-tab', '.nav-link:has-text("Tabla")']:
                        try:
                            el = page.locator(sel).first
                            if el.is_visible(timeout=2000):
                                el.click(); break
                        except: pass
                    time.sleep(1)
                    log("  ⏳ Esperando captcha...")
                    for _ in range(60):
                        tokens = page.evaluate("""
                            () => Array.from(document.querySelectorAll('input[name="cf-turnstile-response"]'))
                                      .map(el => el.value)
                        """)
                        if tokens and tokens[0] and len(tokens[0]) > 20:
                            log("  ✅ Captcha resuelto"); break
                        time.sleep(0.5)

                    ok_est, err_est = 0, 0
                    for item in fechas:
                        if estado_descarga["cancelada"]: break
                        while estado_descarga["pausada"]:
                            time.sleep(0.5)
                            if estado_descarga["cancelada"]: break
                        if estado_descarga["cancelada"]: break

                        filtro_valor = item["value"]
                        label        = item["label"]
                        archivo      = f"{cod}_{label}.csv"
                        ruta         = os.path.join(carpeta, archivo)

                        if os.path.exists(ruta) and os.path.getsize(ruta) > 50:
                            log(f"  ⏭️  {label} ya existe")
                            ok_est += 1; continue

                        try:
                            page.select_option('select[name="CBOFiltro"]', filtro_valor)
                            time.sleep(2)
                            frame = None
                            for _ in range(30):
                                try:
                                    f = page.frame(name="contenedor")
                                    if f:
                                        c = f.content()
                                        if "dataTable" in c or "tableHidden" in c:
                                            frame = f; break
                                except: pass
                                time.sleep(0.5)
                            if not frame:
                                log(f"  ❌ {label}: sin datos"); err_est += 1; continue

                            csv_text = frame.evaluate("""
                                () => {
                                    const csv=[];
                                    const th=document.getElementById('tableHidden');
                                    const td=document.getElementById('dataTable');
                                    const ct=document.getElementById('container');
                                    if(ct){const d=ct.getElementsByTagName('div');
                                        if(d.length>=2)csv.push(d[0].innerText.trim()+','+d[1].innerText.trim());}
                                    for(const t of [th,td]){if(!t)continue;
                                        for(const r of t.getElementsByTagName('tr')){
                                            const c=r.querySelectorAll('td,th');
                                            csv.push(Array.from(c).map(x=>x.innerText.trim()).join(','));}}
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

                    log(f"\n  📊 {nom}: ✅{ok_est} OK  ❌{err_est} errores")
                except Exception as e:
                    log(f"  ❌ Error crítico en {nom}: {e}")
                finally:
                    page.close()

                estado_descarga["progreso"] = idx + 1

            browser.close()
        if proceso_edge:
            proceso_edge.terminate()

    except Exception as e:
        log(f"\n❌ Error global: {e}")
    finally:
        estado_descarga["activa"] = False
        estado_descarga["actual"] = ""
        log(f"\n🎉 FINALIZADO — ✅{ok_total} archivos  ❌{err_total} errores")

@app.route("/api/descargar-region", methods=["POST"])
def api_descargar_region():
    if estado_descarga["activa"]:
        return jsonify({"error": "Ya hay una descarga en curso"}), 400
    data       = request.json or {}
    dp         = data.get("dp","")
    estaciones = data.get("estaciones",[])
    if not estaciones:
        return jsonify({"error": "Sin estaciones"}), 400
    threading.Thread(target=descargar_con_playwright, args=(estaciones, dp), daemon=True).start()
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
.sec{padding:11px 14px;border-bottom:1px solid #eef1f5}
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
.grupo-header{padding:5px 12px;background:#f0f4f8;border-bottom:1px solid #e0e0e0;display:flex;align-items:center;gap:6px}
.grupo-header span{font-size:.7rem;font-weight:700}
.est{padding:7px 12px;cursor:pointer;border-bottom:1px solid #f5f5f5;display:flex;align-items:center;gap:7px;transition:background .1s}
.est:hover{background:#f0f8ff}
.est input[type=checkbox]{width:14px;height:14px;cursor:pointer;flex-shrink:0}
.dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.en{font-size:.81rem;font-weight:600;line-height:1.3}
.et{font-size:.67rem;color:#888}
.frow{display:flex;gap:6px}
.frow>div{flex:1}
.frow label{font-size:.7rem;color:#6b7a8d;display:block;margin-bottom:3px}
.fechas-info{font-size:.7rem;color:#2980b9;margin-top:4px;min-height:14px}
.btns{display:flex;flex-direction:column;gap:5px;margin-top:8px}
.btn{width:100%;padding:10px;border:none;border-radius:8px;font-size:.84rem;font-weight:700;cursor:pointer;transition:opacity .2s}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn:hover:not(:disabled){opacity:.88}
.btn-region{background:linear-gradient(135deg,#1a5276,#2980b9);color:white}
.btn-sel{background:linear-gradient(135deg,#004a8f,#0099d6);color:white}
.btn-pausar{background:#e67e22;color:white;display:none}
.btn-cancelar{background:#c0392b;color:white;display:none}
.prog-wrap{padding:10px 14px;border-top:1px solid #eee;display:none}
.prog-label{font-size:.71rem;color:#555;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.prog-bar{width:100%;height:8px;background:#e0e0e0;border-radius:4px;overflow:hidden}
.prog-fill{height:100%;background:linear-gradient(90deg,#0099d6,#004a8f);border-radius:4px;transition:width .4s}
.prog-txt{font-size:.69rem;color:#888;margin-top:3px;text-align:right}
.log-wrap{padding:8px 14px;border-top:1px solid #eee;display:none;flex-direction:column}
.log-wrap h3{font-size:.67rem;text-transform:uppercase;color:#6b7a8d;margin-bottom:5px}
.log-box{background:#1a1a2e;color:#a8d8ea;font-size:.68rem;font-family:monospace;padding:8px;border-radius:6px;height:90px;overflow-y:auto;line-height:1.55}
.modal-bg{position:fixed;inset:0;background:rgba(0,0,0,.5);display:none;align-items:center;justify-content:center;z-index:9999}
.modal-bg.show{display:flex}
.modal{background:white;border-radius:14px;padding:26px;max-width:400px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,.2)}
.modal h2{font-size:1rem;margin-bottom:10px;color:#004a8f}
.modal p{font-size:.84rem;color:#444;margin-bottom:18px;line-height:1.55;white-space:pre-line}
.modal-btns{display:flex;gap:10px;justify-content:flex-end}
.modal-btns button{padding:8px 18px;border:none;border-radius:8px;font-size:.84rem;font-weight:600;cursor:pointer}
.btn-conf{background:#004a8f;color:white}
.btn-canc-m{background:#eee;color:#333}
#map{flex:1}
.leg{background:white;padding:8px 12px;border-radius:9px;box-shadow:0 2px 8px rgba(0,0,0,.15);font-size:.75rem;line-height:1.8}
.li{display:flex;align-items:center;gap:6px}
.ld{width:10px;height:10px;border-radius:50%}
.spin{display:inline-block;width:12px;height:12px;border:2px solid #ccc;border-top-color:#0099d6;border-radius:50%;animation:sp .7s linear infinite;vertical-align:middle;margin-right:4px}
@keyframes sp{to{transform:rotate(360deg)}}
</style>
</head>
<body>

<div class="modal-bg" id="modal">
  <div class="modal">
    <h2 id="m-titulo"></h2>
    <p id="m-texto"></p>
    <div class="modal-btns">
      <button class="btn-canc-m" onclick="cerrarModal()">Cancelar</button>
      <button class="btn-conf" id="m-confirmar">Confirmar</button>
    </div>
  </div>
</div>

<header>
  <h1>🌦️ SENAMHI — Descarga Masiva de Datos Hidrometeorológicos</h1>
  <p>① Región → ② Tipo → ③ Selecciona estaciones → ④ Ajusta fechas → ⑤ Descargar</p>
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

    <div class="sec" style="padding-bottom:4px">
      <h3>③ Estaciones — <span id="conteo" style="color:#0099d6">elige una región</span>
        <span id="sel-count" style="color:#e67e22;margin-left:5px"></span>
      </h3>
    </div>
    <div class="lista-wrap" id="lista">
      <div style="padding:20px;color:#aaa;text-align:center;font-size:.81rem">Selecciona una región para ver las estaciones en el mapa</div>
    </div>

    <div class="sec">
      <h3>④ Rango de fechas <span id="fechas-badge" style="color:#27ae60;font-size:.65rem;font-weight:normal"></span></h3>
      <div class="frow">
        <div><label>Desde (YYYY-MM)</label><input type="text" id="fi" placeholder="cargando..."></div>
        <div><label>Hasta (YYYY-MM)</label><input type="text" id="ff" placeholder="cargando..."></div>
      </div>
      <div class="fechas-info" id="fechas-info">Selecciona una región para ver las fechas disponibles</div>

      <div class="btns">
        <button class="btn btn-region" id="btnRegion" disabled>⬇️ Descargar región completa</button>
        <button class="btn btn-sel"    id="btnSel"    disabled>☑️ Descargar seleccionadas</button>
        <button class="btn btn-pausar"  id="btnPausar">⏸️ Pausar</button>
        <button class="btn btn-cancelar" id="btnCancelar">⛔ Cancelar</button>
      </div>
    </div>

    <div class="prog-wrap" id="progWrap">
      <div class="prog-label" id="progLabel">Iniciando...</div>
      <div class="prog-bar"><div class="prog-fill" id="progFill" style="width:0%"></div></div>
      <div class="prog-txt" id="progTxt">0 / 0</div>
    </div>

    <div class="log-wrap" id="logWrap">
      <h3>📋 Log en tiempo real</h3>
      <div class="log-box" id="logBox"></div>
    </div>

  </div>
  <div id="map"></div>
</div>

<script>
const COLS={M:"#27ae60",MA:"#2980b9",H:"#e67e22",HA:"#8e44ad"};
const LABS={M:"Met. Convencional",MA:"Met. Automática",H:"Hid. Convencional",HA:"Hid. Automática"};
const TIPO_FULL={
  M:"Estación Meteorológica Convencional", MA:"Estación Meteorológica Automática",
  H:"Estación Hidrológica Convencional",   HA:"Estación Hidrológica Automática"
};

let mapa,markers=[],estData=[],dpActual="";
let tiposOn=new Set(["M","MA","H","HA"]);
let checkboxes={};
let pollingInterval=null;

// ── Mapa ─────────────────────────────────────────────────
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

// ── Regiones ─────────────────────────────────────────────
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

  // Limpiar estado previo
  document.getElementById("conteo").textContent="cargando...";
  document.getElementById("lista").innerHTML=
    "<div style='padding:20px;color:#aaa;text-align:center'><span class='spin'></span> Cargando estaciones...</div>";
  document.getElementById("fi").value="";
  document.getElementById("ff").value="";
  document.getElementById("fi").placeholder="consultando...";
  document.getElementById("ff").placeholder="consultando...";
  document.getElementById("fechas-info").textContent="⏳ Consultando fechas disponibles en SENAMHI...";
  document.getElementById("fechas-badge").textContent="";
  document.getElementById("btnRegion").disabled=true;
  document.getElementById("btnSel").disabled=true;

  // Cargar estaciones y fechas en paralelo
  const [resEst, resFechas] = await Promise.all([
    fetch(`/api/estaciones/${dpActual}`),
    fetch(`/api/fechas-region/${dpActual}`)
  ]);
  const dataEst    = await resEst.json();
  const dataFechas = await resFechas.json();

  // Mostrar fechas reales de SENAMHI
  if(dataFechas.fi && dataFechas.ff){
    document.getElementById("fi").value       = dataFechas.fi;
    document.getElementById("ff").value       = dataFechas.ff;
    document.getElementById("fi").placeholder = "YYYY-MM";
    document.getElementById("ff").placeholder = "YYYY-MM";
    document.getElementById("fechas-info").textContent =
      `📅 Rango disponible en SENAMHI: ${dataFechas.fi} → ${dataFechas.ff}`;
    document.getElementById("fechas-badge").textContent = "(fechas obtenidas automáticamente de SENAMHI)";
  } else {
    document.getElementById("fi").placeholder = "YYYY-MM";
    document.getElementById("ff").placeholder = "YYYY-MM";
    document.getElementById("fechas-info").textContent =
      "⚠️ No se pudo obtener el rango automáticamente. Ingresa las fechas manualmente.";
  }

  if(dataEst.error||!dataEst.estaciones||!dataEst.estaciones.length){
    document.getElementById("conteo").textContent="0 estaciones";
    document.getElementById("lista").innerHTML=`<div style='padding:16px;color:#c0392b;font-size:.82rem'>❌ ${dataEst.error||"Sin estaciones"}</div>`;
    return;
  }
  estData=dataEst.estaciones;
  renderizar();
  document.getElementById("btnRegion").disabled=false;
});

// ── Renderizar ────────────────────────────────────────────
function renderizar(){
  markers.forEach(m=>mapa.removeLayer(m));markers=[];checkboxes={};
  const lista=document.getElementById("lista");lista.innerHTML="";let visibles=0;
  const grupos={};
  estData.forEach(e=>{if(!tiposOn.has(e.tipo))return;if(!grupos[e.tipo])grupos[e.tipo]=[];grupos[e.tipo].push(e);});

  Object.entries(grupos).forEach(([tipo,ests])=>{
    const header=document.createElement("div");header.className="grupo-header";
    const cbAll=document.createElement("input");cbAll.type="checkbox";cbAll.style.cursor="pointer";
    const lbl=document.createElement("span");
    lbl.style.color=COLS[tipo];lbl.textContent=`${TIPO_FULL[tipo]} (${ests.length})`;
    header.appendChild(cbAll);header.appendChild(lbl);
    cbAll.addEventListener("change",()=>{
      ests.forEach(e=>{if(checkboxes[e.cod])checkboxes[e.cod].checked=cbAll.checked;});
      actualizarSel();
    });
    lista.appendChild(header);

    ests.forEach(est=>{
      visibles++;
      const color=COLS[est.tipo]||"#999";
      const icono=L.divIcon({className:"",
        html:`<div style="width:12px;height:12px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.4)"></div>`,
        iconSize:[12,12],iconAnchor:[6,6]});
      const m=L.marker([est.lat,est.lon],{icon:icono}).addTo(mapa);
      m.bindPopup(`<div style="min-width:175px">
        <b style="font-size:.88rem">${est.nom}</b><br>
        <span style="font-size:.76rem;color:#555">Código: <b>${est.cod}</b><br>${LABS[est.tipo]}<br>${est.estado}</span><br>
        <button onclick="toggleCheck('${est.cod}')"
          style="margin-top:7px;padding:5px 0;width:100%;background:#004a8f;color:white;
                 border:none;border-radius:6px;cursor:pointer;font-size:.76rem;font-weight:600">
          ☑️ Seleccionar / deseleccionar</button></div>`);
      markers.push(m);

      const item=document.createElement("div");item.className="est";item.dataset.cod=est.cod;
      const cb=document.createElement("input");cb.type="checkbox";cb.dataset.cod=est.cod;
      cb.addEventListener("change",actualizarSel);checkboxes[est.cod]=cb;
      const dot=document.createElement("div");dot.className="dot";dot.style.background=color;
      const info=document.createElement("div");
      info.innerHTML=`<div class="en">${est.nom}</div><div class="et">${LABS[est.tipo]} · ${est.cod}</div>`;
      item.appendChild(cb);item.appendChild(dot);item.appendChild(info);
      item.addEventListener("click",(ev)=>{
        if(ev.target===cb)return;
        cb.checked=!cb.checked;actualizarSel();
        mapa.setView([est.lat,est.lon],11);m.openPopup();
      });
      lista.appendChild(item);
    });
  });
  document.getElementById("conteo").textContent=`${visibles} de ${estData.length} estaciones`;
}

function toggleCheck(cod){if(checkboxes[cod]){checkboxes[cod].checked=!checkboxes[cod].checked;actualizarSel();}}
function actualizarSel(){
  const n=Object.values(checkboxes).filter(c=>c.checked).length;
  document.getElementById("sel-count").textContent=n>0?`(${n} marcadas)`:"";
  document.getElementById("btnSel").disabled=n===0;
}

document.querySelectorAll(".tbtn").forEach(btn=>{
  btn.addEventListener("click",()=>{
    const t=btn.dataset.t;tiposOn.has(t)?tiposOn.delete(t):tiposOn.add(t);
    btn.classList.toggle("on",tiposOn.has(t));if(estData.length)renderizar();
  });
});

// ── Modal ────────────────────────────────────────────────
function mostrarModal(titulo,texto,onOk){
  document.getElementById("m-titulo").textContent=titulo;
  document.getElementById("m-texto").textContent=texto;
  document.getElementById("modal").classList.add("show");
  document.getElementById("m-confirmar").onclick=()=>{cerrarModal();onOk();};
}
function cerrarModal(){document.getElementById("modal").classList.remove("show");}

// ── Botones descarga ──────────────────────────────────────
document.getElementById("btnRegion").addEventListener("click",()=>{
  const visibles=estData.filter(e=>tiposOn.has(e.tipo));
  const fi=document.getElementById("fi").value;
  const ff=document.getElementById("ff").value;
  const nomReg=document.getElementById("selReg").selectedOptions[0]?.text||dpActual;
  mostrarModal(
    "⬇️ Descargar región completa",
    `Región: ${nomReg}\nEstaciones visibles: ${visibles.length}\nFechas: ${fi} → ${ff}\n\nEste proceso puede tardar varios minutos. El navegador Edge se abrirá automáticamente.`,
    ()=>iniciarDescarga(visibles)
  );
});

document.getElementById("btnSel").addEventListener("click",()=>{
  const sel=estData.filter(e=>checkboxes[e.cod]&&checkboxes[e.cod].checked);
  const fi=document.getElementById("fi").value;
  const ff=document.getElementById("ff").value;
  mostrarModal(
    "☑️ Descargar estaciones seleccionadas",
    `Estaciones seleccionadas: ${sel.length}\nFechas: ${fi} → ${ff}\n\nEl navegador Edge se abrirá automáticamente.`,
    ()=>iniciarDescarga(sel)
  );
});

async function iniciarDescarga(estaciones){
  const fi=document.getElementById("fi").value.trim();
  const ff=document.getElementById("ff").value.trim();
  if(!/^\d{4}-\d{2}$/.test(fi)||!/^\d{4}-\d{2}$/.test(ff)){
    alert("Formato de fecha incorrecto. Usa YYYY-MM (ej: 2017-01)");return;
  }

  mostrarProgreso(true);
  document.getElementById("progLabel").textContent="Consultando fechas de cada estación en SENAMHI...";

  const estConFechas=[];
  for(const est of estaciones){
    const params=new URLSearchParams({
      cod:est.cod,estado:est.estado,ico:est.ico,cate:est.cate,cod_old:est.cod_old||""
    });
    try{
      const res=await fetch("/api/fechas?"+params);
      const data=await res.json();
      // Filtrar por rango elegido por el usuario
      const fechas=(data.fechas||[]).filter(f=>f.label>=fi&&f.label<=ff);
      if(fechas.length>0)estConFechas.push({...est,fechas});
    }catch(e){console.warn("Error fechas",est.cod,e);}
  }

  if(!estConFechas.length){
    alert("No se encontraron fechas en el rango seleccionado para ninguna estación.");
    mostrarProgreso(false);return;
  }

  const res=await fetch("/api/descargar-region",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({dp:dpActual,estaciones:estConFechas})
  });
  const data=await res.json();
  if(data.error){alert("Error: "+data.error);mostrarProgreso(false);return;}

  document.getElementById("btnPausar").style.display="block";
  document.getElementById("btnCancelar").style.display="block";
  document.getElementById("btnRegion").disabled=true;
  document.getElementById("btnSel").disabled=true;
  pollingInterval=setInterval(actualizarProgreso,1000);
}

function mostrarProgreso(v){
  document.getElementById("progWrap").style.display=v?"block":"none";
  document.getElementById("logWrap").style.display=v?"flex":"none";
}

async function actualizarProgreso(){
  const d=await fetch("/api/estado-descarga").then(r=>r.json());
  const pct=d.total>0?Math.round((d.progreso/d.total)*100):0;
  document.getElementById("progFill").style.width=pct+"%";
  document.getElementById("progTxt").textContent=`${d.progreso} / ${d.total} estaciones`;
  document.getElementById("progLabel").textContent=d.actual||"Procesando...";
  const box=document.getElementById("logBox");
  box.textContent=d.log.join("\n");box.scrollTop=box.scrollHeight;
  const btnP=document.getElementById("btnPausar");
  btnP.textContent=d.pausada?"▶️ Reanudar":"⏸️ Pausar";
  btnP.style.background=d.pausada?"#27ae60":"#e67e22";
  if(!d.activa&&d.progreso>0){
    clearInterval(pollingInterval);
    document.getElementById("btnPausar").style.display="none";
    document.getElementById("btnCancelar").style.display="none";
    document.getElementById("btnRegion").disabled=false;
    document.getElementById("progLabel").textContent="✅ Descarga finalizada";
    document.getElementById("btnSel").disabled=
      Object.values(checkboxes).filter(c=>c.checked).length===0;
  }
}

document.getElementById("btnPausar").addEventListener("click",async()=>{
  await fetch("/api/pausar",{method:"POST"});
});
document.getElementById("btnCancelar").addEventListener("click",()=>{
  mostrarModal(
    "⛔ Cancelar descarga",
    "¿Estás segura que deseas cancelar?\nLos archivos ya descargados se conservarán.",
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