# ============================================================
#   SCRAPER SENAMHI - Mapa interactivo + Descarga CSV
#   Curso: Minería de Datos - UPeU
# ============================================================
# INSTALACIÓN: pip install requests flask beautifulsoup4
# USO: ejecuta el script → se abre el navegador automáticamente
# ============================================================

import os, time, threading, webbrowser, re, json
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
        return jsonify({"error": "No se encontró PruebaTest en el HTML", "estaciones": []})

    raw = match.group(1)
    # Fix: corregir -.XXXX → -0.XXXX (JSON inválido de SENAMHI)
    raw = re.sub(r':\s*(-?)\.(\d+)', r': \g<1>0.\2', raw)

    try:
        estaciones_raw = json.loads(raw)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"JSON inválido: {e}", "estaciones": []})

    estaciones = []
    for e in estaciones_raw:
        estado = e.get("estado", "")
        ico    = e.get("ico", "M")
        if estado == "AUTOMATICA":
            tipo = "HA" if ico == "H" else "MA"
        else:
            tipo = "H" if ico == "H" else "M"
        estaciones.append({
            "cod":     e.get("cod", ""),
            "cod_old": e.get("cod_old", ""),
            "nom":     e.get("nom", "").strip(),
            "lat":     e.get("lat", 0),
            "lon":     e.get("lon", 0),
            "tipo":    tipo,
            "cate":    e.get("cate", ""),
            "estado":  estado,
        })
    return jsonify({"estaciones": estaciones, "total": len(estaciones)})

# ── API: obtener fechas disponibles de una estación ────────
@app.route("/api/fechas")
def api_fechas():
    cod     = request.args.get("cod", "")
    estado  = request.args.get("estado", "DIFERIDO")
    tipo    = request.args.get("tipo_esta", "M")
    cate    = request.args.get("cate", "CO")
    cod_old = request.args.get("cod_old", "")

    url = (f"https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php"
           f"?cod={cod}&estado={estado}&tipo_esta={tipo}&cate={cate}&cod_old={cod_old}")
    try:
        r = req.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        select = soup.find("select", {"name": "CBOFiltro"})
        if not select:
            return jsonify({"fechas": [], "error": "No se encontró el selector de fechas"})
        fechas = []
        for opt in select.find_all("option"):
            v = opt.get("value", "")  # formato: 202102
            if len(v) == 6 and v.isdigit():
                # Convertir 202102 → 2021-02
                fechas.append(f"{v[:4]}-{v[4:]}")
        return jsonify({"fechas": sorted(fechas), "url_graf": url})
    except Exception as e:
        return jsonify({"fechas": [], "error": str(e)})

# ── API: descargar CSV con POST + sesión ───────────────────
@app.route("/api/descargar")
def api_descargar():
    dp      = request.args.get("dp", "")
    codigo  = request.args.get("cod", "")
    cod_old = request.args.get("cod_old", "")
    nombre  = request.args.get("nom", codigo)
    estado  = request.args.get("estado", "DIFERIDO")
    tipo    = request.args.get("tipo_esta", "M")
    cate    = request.args.get("cate", "CO")
    fecha_i = request.args.get("fecha_inicio", "2021-01")
    fecha_f = request.args.get("fecha_fin", "2026-01")

    def rango(ini, fin):
        fechas, a, m = [], *map(int, ini.split("-"))
        af, mf = map(int, fin.split("-"))
        while (a, m) <= (af, mf):
            fechas.append(f"{a}-{m:02d}")
            m += 1
            if m > 12:
                m, a = 1, a + 1
        return fechas

    fechas = rango(fecha_i, fecha_f)
    nom_carpeta = "".join(c for c in nombre if c.isalnum() or c in " _-").strip()
    carpeta = os.path.join("datos_senamhi", dp, nom_carpeta)
    os.makedirs(carpeta, exist_ok=True)

    ok, err, exist = 0, 0, 0

    # Usar una sesión para mantener cookies
    sesion = req.Session()
    sesion.headers.update(HEADERS)

    # Primero visitar la página de la estación para obtener cookies
    url_graf = (f"https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php"
                f"?cod={codigo}&estado={estado}&tipo_esta={tipo}&cate={cate}&cod_old={cod_old}")
    try:
        sesion.get(url_graf, timeout=15)
    except Exception:
        pass

    for fecha in fechas:
        archivo = f"{codigo}_{fecha}.csv"
        ruta = os.path.join(carpeta, archivo)

        if os.path.exists(ruta) and os.path.getsize(ruta) > 50:
            exist += 1
            continue

        # Convertir fecha YYYY-MM → YYYYMM para CBOFiltro
        cbo = fecha.replace("-", "")

        # POST al endpoint real con todos los campos del formulario
        post_url = ("https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/"
                    "_dt_est_tp_0s3n@mH1.php")
        post_data = {
            "estaciones": codigo,
            "CBOFiltro":  cbo,
            "t_e":        tipo,
            "estado":     estado,
            "cod_old":    cod_old,
            "cate_esta":  cate,
            "exportar":   "csv",
            # cf-turnstile-response vacío — algunos servidores lo permiten sin captcha
            "cf-turnstile-response": "",
        }

        descargado = False
        try:
            r = sesion.post(post_url, data=post_data, timeout=20,
                           headers={**HEADERS, "Referer": url_graf,
                                    "Content-Type": "application/x-www-form-urlencoded"})
            if r.status_code == 200 and len(r.content) > 50:
                txt = r.text[:400]
                if ("," in txt or ";" in txt) and "<html" not in txt.lower() and "captcha" not in txt.lower():
                    with open(ruta, "wb") as f:
                        f.write(r.content)
                    ok += 1
                    descargado = True
        except Exception:
            pass

        if not descargado:
            err += 1
        time.sleep(0.3)

    return jsonify({
        "carpeta":    carpeta,
        "total":      len(fechas),
        "exitosos":   ok,
        "existian":   exist,
        "errores":    err,
        "captcha":    ok == 0 and err > 0,
        "url_manual": f"https://www.senamhi.gob.pe/main.php?dp={dp}&p=estaciones",
    })

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
header h1{font-size:1.15rem;font-weight:700}
header p{font-size:.78rem;opacity:.85;margin-top:2px}
.app{display:flex;height:calc(100vh - 60px)}
.panel{width:320px;background:white;display:flex;flex-direction:column;border-right:1px solid #dce3ed;overflow:hidden;flex-shrink:0}
.sec{padding:13px 15px;border-bottom:1px solid #eef1f5}
.sec h3{font-size:.7rem;text-transform:uppercase;letter-spacing:.07em;color:#6b7a8d;margin-bottom:8px}
select,input[type=text]{width:100%;padding:8px 10px;border:1.5px solid #d0d9e4;border-radius:7px;font-size:.87rem;outline:none;transition:border-color .2s}
select:focus,input:focus{border-color:#0099d6}
.tipos{display:flex;flex-wrap:wrap;gap:5px;margin-top:4px}
.tbtn{padding:5px 9px;border-radius:18px;border:1.5px solid #ccc;background:white;cursor:pointer;font-size:.73rem;transition:all .15s}
.tbtn[data-t="M"].on{background:#27ae60;color:white;border-color:#27ae60}
.tbtn[data-t="MA"].on{background:#2980b9;color:white;border-color:#2980b9}
.tbtn[data-t="H"].on{background:#e67e22;color:white;border-color:#e67e22}
.tbtn[data-t="HA"].on{background:#8e44ad;color:white;border-color:#8e44ad}
.lista-wrap{flex:1;overflow-y:auto}
.est{padding:9px 13px;cursor:pointer;border-bottom:1px solid #f0f4f8;display:flex;align-items:center;gap:8px;transition:background .1s}
.est:hover{background:#f0f8ff}
.est.sel{background:#e6f4ff;border-left:3px solid #0099d6}
.dot{width:11px;height:11px;border-radius:50%;flex-shrink:0}
.en{font-size:.85rem;font-weight:600;line-height:1.3}
.et{font-size:.7rem;color:#888;margin-top:1px}
.frow{display:flex;gap:7px}
.frow>div{flex:1}
.frow label{font-size:.72rem;color:#6b7a8d;display:block;margin-bottom:3px}
#btnDl{width:100%;padding:11px;margin-top:10px;background:linear-gradient(135deg,#004a8f,#0099d6);color:white;border:none;border-radius:8px;font-size:.9rem;font-weight:600;cursor:pointer;transition:opacity .2s}
#btnDl:hover{opacity:.88}
#btnDl:disabled{opacity:.4;cursor:not-allowed}
#btnAbrir{width:100%;padding:9px;margin-top:6px;background:#27ae60;color:white;border:none;border-radius:8px;font-size:.85rem;font-weight:600;cursor:pointer;display:none}
#btnAbrir:hover{opacity:.88}
#status{padding:10px 14px;font-size:.8rem;line-height:1.6;display:none;border-top:1px solid #eee}
#status.ok{background:#f0fff4;color:#276749}
#status.err{background:#fff5f5;color:#c0392b}
#status.warn{background:#fffbf0;color:#7d6608}
#status.load{background:#f0f8ff;color:#2471a3}
#map{flex:1}
.leg{background:white;padding:9px 13px;border-radius:9px;box-shadow:0 2px 8px rgba(0,0,0,.15);font-size:.77rem;line-height:1.9}
.li{display:flex;align-items:center;gap:6px}
.ld{width:11px;height:11px;border-radius:50%}
.spin{display:inline-block;width:13px;height:13px;border:2px solid #ccc;border-top-color:#0099d6;border-radius:50%;animation:sp .7s linear infinite;vertical-align:middle;margin-right:5px}
@keyframes sp{to{transform:rotate(360deg)}}
.fechas-info{font-size:.72rem;color:#0099d6;margin-top:4px}
</style>
</head>
<body>
<header>
  <h1>🌦️ SENAMHI — Descarga Masiva de Datos Hidrometeorológicos</h1>
  <p>① Región → ② Tipo → ③ Clic en estación → ④ Fechas → ⑤ Descargar</p>
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
    <div class="sec" style="padding-bottom:6px">
      <h3>③ Estaciones — <span id="conteo" style="color:#0099d6">elige una región</span></h3>
    </div>
    <div class="lista-wrap" id="lista">
      <div style="padding:20px;color:#aaa;text-align:center;font-size:.83rem">Selecciona una región para ver las estaciones</div>
    </div>
    <div class="sec">
      <h3>④ Rango de fechas</h3>
      <div class="frow">
        <div><label>Desde (YYYY-MM)</label><input type="text" id="fi" value="2021-01"></div>
        <div><label>Hasta (YYYY-MM)</label><input type="text" id="ff" value="2026-01"></div>
      </div>
      <div class="fechas-info" id="fechas-info"></div>
      <button id="btnDl" disabled>⬇️ Intentar descarga automática</button>
      <button id="btnAbrir">🌐 Abrir estación en SENAMHI</button>
    </div>
    <div id="status"></div>
  </div>
  <div id="map"></div>
</div>
<script>
const COLS={M:"#27ae60",MA:"#2980b9",H:"#e67e22",HA:"#8e44ad"};
const LABS={M:"Met. Convencional",MA:"Met. Automática",H:"Hid. Convencional",HA:"Hid. Automática"};
let mapa,markers=[],estData=[],selEst=null,dpActual="";
let tiposOn=new Set(["M","MA","H","HA"]);

mapa=L.map("map").setView([-9,-75],5);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:"© OpenStreetMap"}).addTo(mapa);
const leg=L.control({position:"bottomright"});
leg.onAdd=()=>{
  const d=L.DomUtil.create("div","leg");
  d.innerHTML="<b style='font-size:.8rem'>Tipo de estación</b><br>"+
    Object.entries(LABS).map(([t,l])=>`<div class="li"><div class="ld" style="background:${COLS[t]}"></div>${l}</div>`).join("");
  return d;
};
leg.addTo(mapa);

fetch("/api/regiones").then(r=>r.json()).then(data=>{
  const sel=document.getElementById("selReg");
  Object.entries(data).sort((a,b)=>a[1].nombre.localeCompare(b[1].nombre)).forEach(([dp,info])=>{
    const o=document.createElement("option");
    o.value=dp;o.textContent=info.nombre;sel.appendChild(o);
  });
});

document.getElementById("selReg").addEventListener("change",async function(){
  dpActual=this.value;
  if(!dpActual)return;
  const regiones=await fetch("/api/regiones").then(r=>r.json());
  mapa.setView([regiones[dpActual].lat,regiones[dpActual].lon],7);
  estado("load","<span class='spin'></span> Cargando estaciones...");
  document.getElementById("conteo").textContent="cargando...";
  document.getElementById("lista").innerHTML="<div style='padding:20px;color:#aaa;text-align:center'>⏳ Obteniendo datos...</div>";
  const res=await fetch(`/api/estaciones/${dpActual}`);
  const data=await res.json();
  if(data.error||!data.estaciones||!data.estaciones.length){
    estado("err","❌ "+(data.error||"Sin estaciones"));
    document.getElementById("conteo").textContent="0 estaciones";
    return;
  }
  estData=data.estaciones;
  renderizar();
  estado("ok",`✅ ${estData.length} estaciones cargadas. Haz clic en una para seleccionarla.`);
});

function renderizar(){
  markers.forEach(m=>mapa.removeLayer(m));
  markers=[];
  const lista=document.getElementById("lista");
  lista.innerHTML="";
  let visibles=0;
  estData.forEach(est=>{
    const t=est.tipo;
    if(!tiposOn.has(t))return;
    visibles++;
    const color=COLS[t]||"#999";
    const icono=L.divIcon({
      className:"",
      html:`<div style="width:13px;height:13px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 1px 5px rgba(0,0,0,.45);cursor:pointer"></div>`,
      iconSize:[13,13],iconAnchor:[6,6]
    });
    const m=L.marker([est.lat,est.lon],{icon:icono}).addTo(mapa);
    m.bindPopup(`
      <div style="min-width:200px">
        <b style="font-size:.95rem">${est.nom}</b><br>
        <span style="color:#555;font-size:.8rem">
          Código: <b>${est.cod}</b><br>
          Tipo: ${LABS[t]||t} · Cat: ${est.cate}<br>
          Estado: ${est.estado}
        </span><br>
        <button onclick="selDesdePopup('${est.cod}')"
          style="margin-top:8px;padding:6px 0;width:100%;background:#004a8f;color:white;
                 border:none;border-radius:7px;cursor:pointer;font-size:.82rem;font-weight:600">
          ✔ Seleccionar esta estación
        </button>
      </div>`);
    m.on("click",()=>seleccionarEst(est));
    markers.push(m);
    const item=document.createElement("div");
    item.className="est";item.dataset.cod=est.cod;
    item.innerHTML=`<div class="dot" style="background:${color}"></div><div><div class="en">${est.nom}</div><div class="et">${LABS[t]||t} · ${est.cod}</div></div>`;
    item.addEventListener("click",()=>{seleccionarEst(est);mapa.setView([est.lat,est.lon],11);m.openPopup();});
    lista.appendChild(item);
  });
  document.getElementById("conteo").textContent=`${visibles} de ${estData.length} estaciones`;
  if(!visibles)lista.innerHTML="<div style='padding:16px;color:#aaa;font-size:.83rem'>Ninguna con los tipos seleccionados.</div>";
}

async function seleccionarEst(est){
  selEst=est;
  document.getElementById("btnDl").disabled=false;
  document.getElementById("btnAbrir").style.display="block";
  document.querySelectorAll(".est").forEach(el=>el.classList.toggle("sel",el.dataset.cod===est.cod));

  // Obtener fechas disponibles de esta estación
  document.getElementById("fechas-info").textContent="⏳ Consultando fechas disponibles...";
  const tipo_esta = (est.tipo==="M"||est.tipo==="MA") ? "M" : "H";
  const params = new URLSearchParams({cod:est.cod,estado:est.estado,tipo_esta,cate:est.cate,cod_old:est.cod_old||""});
  try {
    const res = await fetch("/api/fechas?"+params);
    const data = await res.json();
    if(data.fechas && data.fechas.length>0){
      const fi=data.fechas[0], ff=data.fechas[data.fechas.length-1];
      document.getElementById("fi").value=fi;
      document.getElementById("ff").value=ff;
      document.getElementById("fechas-info").textContent=
        `📅 ${data.fechas.length} meses disponibles: ${fi} → ${ff}`;
    } else {
      document.getElementById("fechas-info").textContent="⚠️ No se pudieron obtener las fechas automáticamente";
    }
  } catch(e){
    document.getElementById("fechas-info").textContent="";
  }

  estado("ok",`📍 Seleccionada: <b>${est.nom}</b> (${est.cod})<br><small>${LABS[est.tipo]} · ${est.estado}</small>`);
}
function selDesdePopup(cod){const est=estData.find(e=>e.cod===cod);if(est)seleccionarEst(est);}

document.querySelectorAll(".tbtn").forEach(btn=>{
  btn.addEventListener("click",()=>{
    const t=btn.dataset.t;
    tiposOn.has(t)?tiposOn.delete(t):tiposOn.add(t);
    btn.classList.toggle("on",tiposOn.has(t));
    if(estData.length)renderizar();
  });
});

// Botón: abrir la estación directamente en el sitio de SENAMHI
document.getElementById("btnAbrir").addEventListener("click",()=>{
  if(!selEst)return;
  const tipo_esta=(selEst.tipo==="M"||selEst.tipo==="MA")?"M":"H";
  const url=`https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/map_red_graf.php`+
    `?cod=${selEst.cod}&estado=${selEst.estado}&tipo_esta=${tipo_esta}`+
    `&cate=${selEst.cate}&cod_old=${selEst.cod_old||""}`;
  window.open(url,"_blank");
});

// Botón: intentar descarga automática
document.getElementById("btnDl").addEventListener("click",async()=>{
  if(!selEst)return;
  const fi=document.getElementById("fi").value.trim();
  const ff=document.getElementById("ff").value.trim();
  if(!/^\d{4}-\d{2}$/.test(fi)||!/^\d{4}-\d{2}$/.test(ff)){
    estado("err","❌ Formato incorrecto. Usa YYYY-MM (ej: 2021-01)");return;
  }
  document.getElementById("btnDl").disabled=true;
  estado("load",`<span class='spin'></span> Intentando descarga de <b>${selEst.nom}</b> (${fi} → ${ff})...`);

  const tipo_esta=(selEst.tipo==="M"||selEst.tipo==="MA")?"M":"H";
  const params=new URLSearchParams({
    dp:dpActual,cod:selEst.cod,cod_old:selEst.cod_old||"",
    nom:selEst.nom,estado:selEst.estado,tipo_esta,
    cate:selEst.cate,fecha_inicio:fi,fecha_fin:ff
  });

  try{
    const res=await fetch("/api/descargar?"+params);
    const data=await res.json();
    if(data.exitosos>0||data.existian>0){
      estado("ok",
        `✅ Descarga completada:<br>
         • <b>${data.exitosos}</b> archivos nuevos descargados<br>
         • <b>${data.existian}</b> ya existían<br>
         • <b>${data.errores}</b> no disponibles<br>
         📁 <code>${data.carpeta}</code>`);
    } else {
      // El sitio usa Cloudflare Turnstile (captcha) — no se puede automatizar
      estado("warn",
        `🔒 El sitio SENAMHI protege la descarga con captcha (Cloudflare Turnstile).<br><br>
         <b>Para descargar manualmente:</b><br>
         1. Haz clic en <b>"🌐 Abrir estación en SENAMHI"</b><br>
         2. En el selector <b>"Ir :"</b> elige el mes<br>
         3. Haz clic en <b>"Exportar a CSV"</b><br>
         4. Repite para cada mes que necesites<br><br>
         <small>Las fechas disponibles ya están cargadas arriba (${fi} → ${ff})</small>`);
    }
  }catch(e){estado("err","❌ Error: "+e.message);}
  document.getElementById("btnDl").disabled=false;
});

function estado(cls,html){const el=document.getElementById("status");el.className=cls;el.innerHTML=html;el.style.display="block";}
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