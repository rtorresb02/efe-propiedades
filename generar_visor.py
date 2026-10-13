#!/usr/bin/env python3
"""
EFE · Generar Visor v5
- KML polígonos embebidos (477KB — carga rápido)
- Propiedades en JSON separados (fetch — no congela browser)
- Filtro región funcionando
- Actualización automática lunes via Windows Task Scheduler
Uso: python generar_visor.py
"""
import sqlite3, json, csv, re, unicodedata, math, random, zipfile
from datetime import datetime
from pathlib import Path

BASE     = Path(__file__).parent
FILE_DB  = (Path(r"C:\BD_EFE_Rosana\base_datos_local.db")
            if Path(r"C:\BD_EFE_Rosana").exists()
            else BASE / "datos" / "efe_propiedades.db")
FILE_CSV = BASE / "datos" / "estaciones_efe.csv"
FILE_KMZ = BASE / "datos" / "Estaciones.kmz"

LINEAS={"Alameda":"Metrotren Nos","Lo Valledor":"Metrotren Nos","Pedro Aguirre Cerda":"Metrotren Nos","Lo Espejo Paradero":"Metrotren Nos","Lo Errazuriz":"Metrotren Nos","Freire (Nos-Estacion Central)":"Metrotren Nos","San Bernardo":"Metrotren Nos","Maestranza":"Metrotren Nos","Cinco Pinos":"Metrotren Nos","Lo Blanco":"Metrotren Nos","Nos Paradero":"Metrotren Nos","Estacion Central":"Metrotren Nos","Renca Paradero":"Rancagua Express","Las Industrias":"Rancagua Express","Quilicura":"Rancagua Express","Batuco":"Rancagua Express","Valle Grande":"Rancagua Express","Colina":"Rancagua Express","Hospital":"Rancagua Express","Paine":"Rancagua Express","Buin Zoo":"Rancagua Express","Buin":"Rancagua Express","Linderos":"Rancagua Express","Rancagua":"Rancagua Express","Graneros":"Rancagua Express","San Francisco de Mostazal":"Rancagua Express","Rengo":"Rancagua Express","Americo Vespucio":"Tren Melipilla","Tres Poniente":"Tren Melipilla","Ciudad Satelite":"Tren Melipilla","Padre Hurtado":"Tren Melipilla","Malloco":"Tren Melipilla","Talagante":"Tren Melipilla","El Monte":"Tren Melipilla","Melipilla":"Tren Melipilla"}
REGION_SHORT={"Región Metropolitana de Santiago":"Metropolitana","Región de Valparaíso":"Valparaíso","Región del Bío-Bío":"Bío-Bío","Región del Maule":"Maule","Región de La Araucanía":"La Araucanía","Región del Libertador Bernardo O'Higgins":"O'Higgins","Región del Libertador General Bernardo O'Higgins":"O'Higgins","Región de Los Lagos":"Los Lagos","Región de Ñuble":"Ñuble"}
TIPO_MAP={"Casa":"c","Departamento":"d","Local Comercial":"l","Oficina":"l"}
OP_MAP={"Venta":"v","Arriendo":"a"}
RADIO_ID={"0-800m":"r1","800m-3km":"r2","3-5km":"r3","Mayor 5km":"r4"}
RNG=random.Random(42)
DIST_R={"r1":(100,800),"r2":(800,3000),"r3":(3000,5000),"r4":(5000,10000)}

def rand_pt(lat,lng,dmin,dmax):
    d=RNG.uniform(dmin,dmax); a=RNG.uniform(0,6.28318)
    return round(lat+d/111320*math.sin(a),5),round(lng+d/(111320*math.cos(math.radians(lat)))*math.cos(a),5)

print("="*55)
print("  EFE · Generador de Visor v5")
print("="*55)

# 1. Estaciones
estaciones=[]
for enc in ["utf-8","latin-1","cp1252"]:
    try:
        with open(FILE_CSV,encoding=enc,newline="") as f:
            s=f.read(512); f.seek(0); sep=";" if ";" in s else ","
            for row in csv.DictReader(f,delimiter=sep):
                try:
                    r=row["Region"].strip()
                    _linea=row.get("Linea","").strip() or LINEAS.get(row["NOMBRE"].strip(),"Tren Sur")
                    _tramo=row.get("Tramo","").strip() or _linea
                    _estado=row.get("Estado","").strip() or "Servicio Regular"
                    estaciones.append({"nombre":row["NOMBRE"].strip(),"lat":float(row["LAT"].replace(",",".")),"lng":float(row["LONG"].replace(",",".")),"comuna":row["Comuna"].strip(),"region":r,"linea":_linea,"tramo":_tramo,"estado":_estado,"region_short":REGION_SHORT.get(r,r[:15])})
                except: pass
        break
    except UnicodeDecodeError: pass
print(f"  Estaciones: {len(estaciones)}")



est_coords={e["nombre"]:(e["lat"],e["lng"]) for e in estaciones}

# 2. Propiedades desde BD → guardar en JSON separados
db_path=str(FILE_DB)
if not db_path.endswith((".db",".sqlite")): db_path+=".db"
SP={}
if Path(db_path).exists():
    conn=sqlite3.connect(db_path); conn.row_factory=sqlite3.Row
    try:
        rows=conn.execute("SELECT estacion,tipo,operacion,radio,radio_lbl,distancia_m,precio,m2,uf_m2,lat,lng,url,fuente,fecha_scrape FROM propiedades_reales WHERE url IS NOT NULL ORDER BY estacion,tipo,operacion,distancia_m").fetchall()
        print(f"  Propiedades BD: {len(rows):,}")
        for row in rows:
            est=row["estacion"]; tipo=TIPO_MAP.get(row["tipo"],"d"); op=OP_MAP.get(row["operacion"],"v")
            rlbl=row["radio_lbl"] or row["radio"] or "800m-3km"
            rid=RADIO_ID.get(rlbl,row["radio"] or "r2")
            lat,lng=row["lat"],row["lng"]
            if not lat or not lng:
                e_lat,e_lng=est_coords.get(est,(-33.45,-70.65))
                lat,lng=rand_pt(e_lat,e_lng,*DIST_R.get(rid,(200,3000)))
            dist=row["distancia_m"] or 999
            fuente_s="PI" if "portal" in (row["fuente"] or "") else "TT"
            # Filtrar props con coords reales que estén >15km de su estación
            if row["lat"] and row["lng"]:
                e_lat,e_lng=est_coords.get(est,(-33.45,-70.65))
                real_dist=math.sqrt((float(row["lat"])-e_lat)**2+(float(row["lng"])-e_lng)**2)*111000
                if real_dist > 15000: continue
            if est not in SP: SP[est]=[]
            SP[est].append([round(float(lat),5),round(float(lng),5),tipo,op,rid,row["m2"] or 0,round(float(row["uf_m2"]),1) if row["uf_m2"] else 0,row["precio"] or "Consultar",row["url"] or "",fuente_s,int(dist),(row["fecha_scrape"] or "")])
    except Exception as e:
        print(f"  BD error: {e}")
    conn.close()
else:
    print(f"  BD no encontrada — usando datos sintéticos")

total=sum(len(v) for v in SP.values())
print(f"  Props procesadas: {total:,}")

# Guardar JSON separados
(BASE/"efe_propiedades.json").write_text(json.dumps(SP,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
(BASE/"efe_estaciones.json").write_text(json.dumps(estaciones,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
print(f"  ✓ efe_propiedades.json: {(BASE/'efe_propiedades.json').stat().st_size//1024} KB")
print(f"  ✓ efe_estaciones.json:  {(BASE/'efe_estaciones.json').stat().st_size//1024} KB")

# 3. KML polígonos
kml_polys=[]
if FILE_KMZ.exists():
    from xml.etree import ElementTree as ET
    with zipfile.ZipFile(str(FILE_KMZ),'r') as z:
        kml_content=z.read('doc.kml').decode('utf-8')
    root=ET.fromstring(kml_content); ns={'kml':'http://www.opengis.net/kml/2.2'}
    def get_col(name):
        n=name.lower()
        if 'anden' in n: return '#185FA5',0.6,'#0d3d6b'
        if 'acceso' in n: return '#1a8c3a',0.5,'#0f5c25'
        if 'mesanina' in n: return '#e89200',0.5,'#a06000'
        if 'peatonal' in n: return '#8b44d4',0.4,'#5c2c9a'
        if 'edificio' in n: return '#e03020',0.5,'#a01010'
        if 'faja' in n: return '#c8b800',0.3,'#8a7d00'
        return '#555555',0.3,'#333333'
    for pm in root.findall('.//kml:Placemark',ns):
        name_el=pm.find('kml:name',ns)
        name=(name_el.text or "").strip() if name_el is not None else ""
        outer=pm.find('.//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates',ns)
        if outer is not None:
            coords_raw=outer.text.strip().split()
            coords=[]
            for c in coords_raw:
                parts=c.split(',')
                if len(parts)>=2:
                    try: coords.append([float(parts[1]),float(parts[0])])
                    except: pass
            if coords:
                fill,opac,stroke=get_col(name)
                kml_polys.append({"n":name,"c":coords,"f":fill,"o":opac,"s":stroke})
    print(f"  ✓ KML polígonos: {len(kml_polys)}")
else:
    print(f"  KML no encontrado en {FILE_KMZ}")

kml_js=json.dumps(kml_polys,ensure_ascii=False,separators=(",",":"))
fecha=datetime.now().strftime("%d/%m/%Y %H:%M")
regions=sorted(set(e["region_short"] for e in estaciones))
reg_opts="".join(f'<option value="{r}">{r}</option>' for r in regions)

# 4. HTML liviano — carga SP/ST via fetch, KML inline
html="""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>EFE · Propiedades Georreferenciadas</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Ubuntu:wght@400;500;700&display=swap"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}html,body{height:100%;font-family:'Ubuntu',Arial,sans-serif;overflow:hidden}
#map{position:absolute;inset:0;z-index:0}
#top{position:absolute;top:10px;left:50px;right:285px;z-index:1000;display:flex;align-items:center;gap:8px;background:rgba(255,255,255,.98);padding:8px 14px;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,.25)}
.tl{font-size:13px;font-weight:700;color:#1a3a5c;white-space:nowrap}
#stSel{width:100%;font-size:13px;padding:5px 8px;border:1.5px solid #b0c8e8;border-radius:5px;background:#f5f9ff;color:#1a3a5c;cursor:text;outline:none;box-sizing:border-box}
#stDrop{display:none;position:absolute;top:100%;left:0;right:0;max-height:320px;overflow-y:auto;background:#fff;border:1.5px solid #b0c8e8;border-top:none;border-radius:0 0 5px 5px;z-index:2000;box-shadow:0 4px 10px rgba(0,0,0,.15)}
#stDrop div{padding:6px 10px;font-size:13px;cursor:pointer;color:#1a3a5c}
#stDrop div:hover{background:#e6f1fb}
#regSel{font-size:13px;padding:5px 8px;border:1.5px solid #b0c8e8;border-radius:5px;background:#f5f9ff;color:#1a3a5c;cursor:pointer;max-width:150px}
#btnAll{font-size:13px;font-weight:700;padding:5px 14px;background:#185FA5;color:#fff;border:none;border-radius:5px;cursor:pointer}
#btnAll:hover{background:#0d4a8a}
#bnr{position:absolute;top:62px;left:50%;transform:translateX(-50%);z-index:1000;background:#1a8c3a;color:#fff;padding:5px 22px;border-radius:20px;font-size:13px;font-weight:700;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,.25);display:none}
#loader{position:absolute;inset:0;z-index:2000;background:rgba(15,30,60,.85);display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;gap:14px}
.spin{width:44px;height:44px;border:5px solid rgba(255,255,255,.2);border-top-color:#5ba4f5;border-radius:50%;animation:sp .8s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
#lmsg{font-size:13px;font-weight:700}
#pnl{position:absolute;top:10px;right:10px;width:268px;z-index:1000;background:rgba(255,255,255,.98);border-radius:8px;box-shadow:0 2px 14px rgba(0,0,0,.22);overflow-y:auto;max-height:calc(100vh - 20px)}
.ps{padding:10px 14px;border-bottom:1px solid #e8edf5}.ps:last-child{border-bottom:none}
.pt{font-size:13px;font-weight:700;color:#666;text-transform:uppercase;letter-spacing:.07em;margin-bottom:7px}
.rr,.cr{display:flex;align-items:center;gap:7px;font-size:13px;color:#333;margin-bottom:5px;cursor:pointer;padding:2px 4px;border-radius:3px;user-select:none}
.rr:hover,.cr:hover{background:#f0f6ff}
.rr input,.cr input{cursor:pointer;accent-color:#185FA5;width:14px;height:14px;flex-shrink:0}
.dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.bi{width:16px;height:12px;border-radius:3px;flex-shrink:0;border-width:2px;border-style:solid}
.cnt{margin-left:auto;font-size:13px;color:#aaa;font-weight:600;min-width:30px;text-align:right}
#leg{position:absolute;bottom:28px;left:10px;z-index:1000;background:rgba(255,255,255,.97);border-radius:7px;padding:10px 14px;box-shadow:0 2px 8px rgba(0,0,0,.18);font-size:13px;min-width:148px}
.lt{font-size:13px;font-weight:700;color:#666;text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px;margin-top:7px}.lt:first-child{margin-top:0}
.lr{display:flex;align-items:center;gap:6px;color:#333;margin-bottom:4px}
#bxl{position:absolute;bottom:28px;right:282px;z-index:1000;background:#1a8c3a;color:#fff;border:none;border-radius:6px;padding:8px 16px;font-size:13px;font-weight:700;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.22)}
#bxl:hover{background:#136b2c}
#fch{position:absolute;bottom:8px;left:50%;transform:translateX(-50%);z-index:999;background:rgba(0,0,0,.5);color:#fff;padding:2px 14px;border-radius:8px;font-size:13px;pointer-events:none}
.est-mk{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:3px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,.5);font-size:13px;cursor:pointer;transition:transform .15s}
.est-mk:hover{transform:scale(1.2)}
.leaflet-control-zoom{margin-top:10px!important;margin-left:10px!important}
</style></head><body>
<div id="loader"><div class="spin"></div><div id="lmsg">Cargando propiedades...</div></div>
<div id="map"></div>
<div id="top">
  <span class="tl">Estaciones EFE:</span>
  <div style="position:relative;flex:1"><input id="stSel" placeholder="Escribe para buscar..." autocomplete="off"/><div id="stDrop"></div></div>
  <span class="tl">Región:</span>
  <select id="regSel"><option value="">Todas</option>"""+reg_opts+"""</select>
  <button id="btnAll" onclick="verTodas()">Ver todas</button>
</div>
<div id="bnr"></div>
<div id="fch">"""+fecha+""" · v7-kml</div>
<div id="pnl">
  <div class="ps"><div class="pt">Mapa Base</div>
    <label class="rr"><input type="radio" name="bm" value="estandar"> Estandar</label>
    <label class="rr"><input type="radio" name="bm" value="satelite" checked> Satelite</label>
    <label class="rr"><input type="radio" name="bm" value="nocturno"> Nocturno</label>
    <label class="rr"><input type="radio" name="bm" value="topografico"> Topografico</label>
  </div>
  <div class="ps"><div class="pt">Capas</div>
    <label class="cr"><input type="checkbox" id="chkSt" checked> 🚉 Estaciones EFE</label>
    <label class="cr"><input type="checkbox" id="chkKml" checked> 🏗️ Planos KML estaciones</label>
    <label class="cr"><input type="checkbox" id="chkPoi" checked> 📍 Puntos de Interés (800m)</label>
    <label class="cr"><input type="checkbox" id="chkTerr"> 🗺️ Terrenos EFE (DOT)</label>
  </div>
  <div class="ps" id="psTerr" style="display:none">
    <div class="pt" id="ptTerrToggle" style="cursor:pointer;display:flex;justify-content:space-between;align-items:center;user-select:none">
      <span>Terrenos · Categoría</span><span id="terrArrow" style="transition:transform .15s">▸</span>
    </div>
    <div id="terrBody" style="display:none">
      <label class="cr"><input type="checkbox" class="ct_" data-c="Terrenos de atractivo comercial" checked><span class="dot" style="background:#e8a000"></span>Atractivo comercial</label>
      <label class="cr"><input type="checkbox" class="ct_" data-c="Operacional" checked><span class="dot" style="background:#185FA5"></span>Operacional</label>
      <label class="cr"><input type="checkbox" class="ct_" data-c="Estrategia" checked><span class="dot" style="background:#8b44d4"></span>Estrategia</label>
      <label class="cr"><input type="checkbox" class="ct_" data-c="Terrenos prescindibles" checked><span class="dot" style="background:#e03020"></span>Prescindibles</label>
      <label class="cr"><input type="checkbox" class="ct_" data-c="" checked><span class="dot" style="background:#888"></span>Sin categoría</label>
    </div>
  </div>
  <div class="ps"><div class="pt">Estado Estación</div>
    <label class="cr"><input type="checkbox" class="ce_" data-e="Servicio Regular" checked><span class="dot" style="background:#1a8c3a"></span>Servicio Regular</label>
    <label class="cr"><input type="checkbox" class="ce_" data-e="No Operativo" checked><span class="dot" style="background:#999"></span>No Operativo</label>
  </div>
  <div class="ps"><div class="pt">Radios Distancia</div>
    <label class="cr"><input type="checkbox" class="cr_" data-r="r1" checked><span class="bi" style="background:#1a8c3a33;border-color:#1a8c3a"></span>&lt;=800m Peatonal</label>
    <label class="cr"><input type="checkbox" class="cr_" data-r="r2" checked><span class="bi" style="background:#e8920033;border-color:#e89200"></span>800m-3km Media</label>
    <label class="cr"><input type="checkbox" class="cr_" data-r="r3"><span class="bi" style="background:#c8b80033;border-color:#c8b800"></span>3-5km Intermedia</label>
    <label class="cr"><input type="checkbox" class="cr_" data-r="r4"><span class="bi" style="background:transparent;border-color:#c8b800;border-style:dashed"></span>&gt;5km Periférica</label>
  </div>
  <div class="ps"><div class="pt">Propiedades</div>
    <label class="cr"><input type="checkbox" class="cp_" data-t="c" data-o="v" checked><span class="dot" style="background:#2a7ae8"></span>venta casa<span class="cnt" id="cnt-cv">0</span></label>
    <label class="cr"><input type="checkbox" class="cp_" data-t="d" data-o="v" checked><span class="dot" style="background:#8b44d4"></span>venta departamento<span class="cnt" id="cnt-dv">0</span></label>
    <label class="cr"><input type="checkbox" class="cp_" data-t="l" data-o="v" checked><span class="dot" style="background:#e03020"></span>venta local comercial<span class="cnt" id="cnt-lv">0</span></label>
    <label class="cr"><input type="checkbox" class="cp_" data-t="c" data-o="a" checked><span class="dot" style="background:#5aaff0"></span>arriendo casa<span class="cnt" id="cnt-ca">0</span></label>
    <label class="cr"><input type="checkbox" class="cp_" data-t="d" data-o="a" checked><span class="dot" style="background:#b07ae0"></span>arriendo departamento<span class="cnt" id="cnt-da">0</span></label>
    <label class="cr"><input type="checkbox" class="cp_" data-t="l" data-o="a" checked><span class="dot" style="background:#f07060"></span>arriendo local comercial<span class="cnt" id="cnt-la">0</span></label>
  </div>
  <div class="ps"><div class="pt">Leyenda KML</div>
    <div class="lr"><span class="dot" style="background:#185FA5"></span>Andén</div>
    <div class="lr"><span class="dot" style="background:#1a8c3a"></span>Accesos</div>
    <div class="lr"><span class="dot" style="background:#e89200"></span>Mesanina</div>
    <div class="lr"><span class="dot" style="background:#8b44d4"></span>Peatonal</div>
    <div class="lr"><span class="dot" style="background:#e03020"></span>Edificio</div>
  </div>
</div>
<div id="leg">
  <div class="lt">Tipo Propiedad</div>
  <div class="lr"><span class="dot" style="background:#2a7ae8"></span>Casa</div>
  <div class="lr"><span class="dot" style="background:#8b44d4"></span>Departamento</div>
  <div class="lr"><span class="dot" style="background:#e03020"></span>Local Comercial</div>
  <div class="lt">Borde = Banda</div>
  <div class="lr"><span class="dot" style="background:#ddd;outline:2.5px solid #1a8c3a;outline-offset:1px"></span>&lt;=800m</div>
  <div class="lr"><span class="dot" style="background:#ddd;outline:2.5px solid #e89200;outline-offset:1px"></span>800m-3km</div>
  <div class="lr"><span class="dot" style="background:#ddd;outline:2.5px solid #c8b800;outline-offset:1px"></span>3-5km</div>
  <div class="lr"><span class="dot" style="background:#ddd;outline:2.5px dashed #c8b800;outline-offset:1px"></span>&gt;5km</div>
  <div class="lt" style="border-top:1px solid #eee;padding-top:6px;margin-top:2px">Venta / Arriendo</div>
  <div style="font-size:13px;color:#666;line-height:1.5">Tono oscuro = Venta<br>Tono claro = Arriendo</div>
  <div class="lt" id="ltTerr" style="border-top:1px solid #eee;padding-top:6px;margin-top:2px;display:none">Terrenos EFE</div>
  <div id="legTerr" style="display:none">
    <div class="lr"><span class="dot" style="background:#e8a000"></span>Atractivo comercial</div>
    <div class="lr"><span class="dot" style="background:#185FA5"></span>Operacional</div>
    <div class="lr"><span class="dot" style="background:#8b44d4"></span>Estrategia</div>
    <div class="lr"><span class="dot" style="background:#e03020"></span>Prescindibles</div>
  </div>
</div>
<button id="bxl" onclick="exportXL()">&#11015; Exportar Excel</button>
<script>
const KML_POLYS="""+kml_js+""";
const TILES={estandar:L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",{attribution:"© Esri",maxZoom:19}),satelite:L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",{attribution:"© Esri",maxZoom:19}),nocturno:L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",{attribution:"© Esri",maxZoom:16}),topografico:L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",{attribution:"© Esri",maxZoom:19})};
const TF={cv:"#2a7ae8",dv:"#8b44d4",lv:"#e03020",ca:"#5aaff0",da:"#b07ae0",la:"#f07060"};
const RS={r1:"#1a8c3a",r2:"#e89200",r3:"#c8b800",r4:"#c8b800"};
const RA={r1:.14,r2:.09,r3:.06,r4:.03};
const RR={r1:800,r2:3000,r3:5000,r4:12000};
const RD={r1:null,r2:null,r3:null,r4:"8 6"};
const RL={r1:"≤800m",r2:"800m-3km",r3:"3-5km",r4:">5km"};
const TL={c:"Casa",d:"Departamento",l:"Local Comercial"};
const OL={v:"Venta",a:"Arriendo"};
const LC={"Metrotren Nos":"#185FA5","Rancagua Express":"#4a8a1a","Tren Melipilla":"#993556","Tren Sur":"#BA7517","Tren Valparaíso":"#533AB7","Tren Concepción":"#0F6E56","Tren Coronel":"#993C1D","Tren Temuco":"#3B6D11","Tren Los Lagos":"#0C447C","Ramal Constitución":"#854F0B","Ramal Talcahuano":"#5F5E5A"};
let SP={},ST=[],POI={},curSt="",curReg="";
let aR=new Set(["r1","r2"]),aP=new Set(["cv","dv","lv","ca","da","la"]),aE=new Set(["Servicio Regular","No Operativo"]);
let aT=new Set(["Terrenos de atractivo comercial","Operacional","Estrategia","Terrenos prescindibles",""]);
let TERR=null,terrLoading=false;
const TC={"Terrenos de atractivo comercial":"#e8a000","Operacional":"#185FA5","Estrategia":"#8b44d4","Terrenos prescindibles":"#e03020"};
function colTerr(cat){return TC[cat]||"#888888";}
let curT=TILES.satelite;
const mapRenderer=L.svg({padding:0.5});
const map=L.map("map",{center:[-33.65,-70.72],zoom:8,renderer:mapRenderer,layers:[curT]});
setTimeout(()=>map.invalidateSize(),100);
function forceRedraw(){if(mapRenderer._redraw)mapRenderer._redraw();}
const lP=L.layerGroup().addTo(map),lS=L.layerGroup().addTo(map),lR=L.layerGroup().addTo(map),lK=L.layerGroup().addTo(map),lPOI=L.layerGroup().addTo(map),lTerr=L.layerGroup();
const stSel=document.getElementById("stSel"),regSel=document.getElementById("regSel");

async function cargar(){
  document.getElementById("lmsg").textContent="Cargando propiedades...";
  try{
    const[r1,r2,r3]=await Promise.all([fetch("efe_estaciones.json?v="+Date.now()).then(r=>r.json()),fetch("efe_propiedades.json?v="+Date.now()).then(r=>r.json()),fetch("pois_estaciones.json?v="+Date.now()).then(r=>r.json()).catch(()=>({}))]);
    ST=r1;SP=r2;POI=r3;
    document.getElementById("loader").style.display="none";
    poblarSt("");
    const tot=Object.values(SP).reduce((a,v)=>a+v.length,0);
    document.getElementById("fch").textContent=`"""+fecha+"""  ·  ${ST.length} estaciones  ·  ${tot.toLocaleString("es-CL")} propiedades reales`;
    renderAll();
    map.on("moveend zoomend",()=>{if(!curSt&&!curReg)renderProps();});
    window.setTimeout(()=>map.fire("moveend"),800);
  }catch(e){
    document.getElementById("lmsg").textContent="Error cargando datos: "+e.message;
    console.error(e);
  }
}

let STL=[];
function poblarSt(regF){
  STL=(regF?ST.filter(s=>s.region_short===regF):ST).sort((a,b)=>a.nombre.localeCompare(b.nombre,"es"));
}

function selStation(nom){
  const s=ST.find(x=>x.nombre===nom);
  if(!s)return;
  curSt=s.nombre;
  stSel.value=s.nombre;
  document.getElementById("stDrop").style.display="none";
  map.setView([s.lat,s.lng],15,{animate:false});
  renderAll();
  forceRedraw();
  setTimeout(()=>{renderProps();map.invalidateSize();forceRedraw();},50);
  setTimeout(()=>{renderProps();forceRedraw();},350);
}
const stDropEl=document.getElementById("stDrop");
function showDrop(list){
  stDropEl.innerHTML="";
  if(list.length===0){stDropEl.style.display="none";return;}
  list.slice(0,200).forEach(s=>{
    const d=document.createElement("div");
    d.textContent=s.nombre;
    d.onclick=()=>selStation(s.nombre);
    stDropEl.appendChild(d);
  });
  stDropEl.style.display="block";
}
stSel.oninput=()=>{
  const val=stSel.value.trim().toLowerCase();
  if(!val){showDrop(STL);curSt="";renderAll();return;}
  showDrop(STL.filter(s=>s.nombre.toLowerCase().includes(val)));
};
stSel.onfocus=()=>{showDrop(stSel.value.trim()?STL.filter(s=>s.nombre.toLowerCase().includes(stSel.value.trim().toLowerCase())):STL);};
document.addEventListener("click",(e)=>{if(!e.target.closest("#stSel")&&!e.target.closest("#stDrop"))stDropEl.style.display="none";});
regSel.onchange=()=>{
  curReg=regSel.value;curSt="";poblarSt(curReg);renderAll();
  if(curReg){const sts=ST.filter(s=>s.region_short===curReg);if(sts.length){const lats=sts.map(s=>s.lat),lngs=sts.map(s=>s.lng);map.fitBounds([[Math.min(...lats),Math.min(...lngs)],[Math.max(...lats),Math.max(...lngs)]],{padding:[60,60],animate:false});}}
  else map.setView([-33.65,-70.72],8,{animate:false});
  forceRedraw();
  setTimeout(()=>{renderProps();forceRedraw();},50);
  setTimeout(()=>{renderProps();forceRedraw();},350);
};

document.querySelectorAll("input[name=bm]").forEach(r=>r.onchange=()=>{map.removeLayer(curT);curT=TILES[r.value];map.addLayer(curT);curT.bringToBack();});
document.getElementById("chkSt").onchange=function(){this.checked?lS.addTo(map):map.removeLayer(lS)};
document.getElementById("chkKml").onchange=function(){if(this.checked){lK.addTo(map);renderKML();}else{map.removeLayer(lK);}forceRedraw();};
document.getElementById("chkPoi").onchange=function(){renderPOI();};
document.getElementById("chkTerr").onchange=function(){
  document.getElementById("psTerr").style.display=this.checked?"block":"none";
  document.getElementById("ltTerr").style.display=this.checked?"block":"none";
  document.getElementById("legTerr").style.display=this.checked?"block":"none";
  if(this.checked){cargarTerrenos();lTerr.addTo(map);}else{map.removeLayer(lTerr);}
};
document.getElementById("ptTerrToggle").onclick=function(){
  const body=document.getElementById("terrBody"),arrow=document.getElementById("terrArrow");
  const open=body.style.display==="block";
  body.style.display=open?"none":"block";
  arrow.style.transform=open?"rotate(0deg)":"rotate(90deg)";
};
document.querySelectorAll(".ct_").forEach(c=>c.onchange=function(){this.checked?aT.add(this.dataset.c):aT.delete(this.dataset.c);renderTerrenos();});
document.querySelectorAll(".cr_").forEach(c=>{if(c.checked)aR.add(c.dataset.r);else aR.delete(c.dataset.r);c.onchange=function(){this.checked?aR.add(this.dataset.r):aR.delete(this.dataset.r);renderRings();};});
document.querySelectorAll(".cp_").forEach(c=>c.onchange=function(){const k=this.dataset.t+this.dataset.o;this.checked?aP.add(k):aP.delete(k);renderProps();setTimeout(forceRedraw,30);});
document.querySelectorAll(".ce_").forEach(c=>c.onchange=function(){this.checked?aE.add(this.dataset.e):aE.delete(this.dataset.e);renderSt();forceRedraw();});

function normStr(s){return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'').trim();}
function renderKML(){
  lK.clearLayers();
  // Mostrar todos los planos KML siempre (sin filtrar por estacion)
  KML_POLYS.forEach(p=>{
    L.polygon(p.c,{fillColor:p.f,fillOpacity:p.o,color:p.s,weight:1.5,renderer:mapRenderer})
     .bindTooltip(p.n,{sticky:true}).addTo(lK);
  });
  forceRedraw();
}
function renderPOI(){
  lPOI.clearLayers();
  if(!document.getElementById("chkPoi").checked) return;
  if(!curSt) return;
  const pois=POI[curSt]||[];
  pois.forEach(p=>{
    if(!p.lat||!p.lng) return;
    L.marker([p.lat,p.lng],{icon:L.divIcon({className:"",html:`<div style="font-size:18px;filter:drop-shadow(0 1px 2px rgba(0,0,0,.5))">${p.emoji||"📍"}</div>`,iconSize:[24,24],iconAnchor:[12,12]})})
    .bindTooltip(`${p.emoji||"📍"} ${p.nombre} <br><small>${p.categoria}</small>`,{sticky:true})
    .addTo(lPOI);
  });
  forceRedraw();
}
async function cargarTerrenos(){
  if(TERR||terrLoading) return renderTerrenos();
  terrLoading=true;
  try{
    const r=await fetch("terrenos_efe.geojson?v="+Date.now());
    TERR=await r.json();
  }catch(e){console.error("Error cargando terrenos:",e);TERR={type:"FeatureCollection",features:[]};}
  terrLoading=false;
  renderTerrenos();
}
function fmtNum(n){return n?Number(n).toLocaleString("es-CL",{maximumFractionDigits:2}):"0";}
function renderTerrenos(){
  lTerr.clearLayers();
  if(!TERR||!document.getElementById("chkTerr").checked) return;
  L.geoJSON(TERR,{
    filter:feat=>aT.has(feat.properties.categoria||""),
    style:feat=>{const c=colTerr(feat.properties.categoria);return{color:c,weight:1.5,fillColor:c,fillOpacity:.35,renderer:mapRenderer};},
    onEachFeature:(feat,layer)=>{
      const p=feat.properties;
      const val=p.valor_comercial_musd?`<tr><td style="padding:3px 6px;color:#888">Valor comercial</td><td style="padding:3px 6px;text-align:right">${fmtNum(p.valor_comercial_musd)} MUSD</td></tr>`:"";
      const tas=p.tasacion_2025_musd?`<tr style="background:#f4f8ff"><td style="padding:3px 6px;color:#888">Tasación 2025</td><td style="padding:3px 6px;text-align:right">${fmtNum(p.tasacion_2025_musd)} MUSD</td></tr>`:"";
      layer.bindPopup(`<div style="font-family:Arial;min-width:240px"><div style="font-size:13px;font-weight:700;color:#1a3a5c">🗺️ ${p.nombre}</div><div style="font-size:12px;font-weight:700;color:${colTerr(p.categoria)};margin:3px 0">${p.categoria||"Sin categoría"}</div><div style="font-size:12px;color:#666;margin-bottom:8px">${p.clasificacion||""}</div><table style="font-size:12px;width:100%;border-collapse:collapse"><tr><td style="padding:3px 6px;color:#888">Tipo bien</td><td style="padding:3px 6px;text-align:right">${p.tipo_bien||"N/D"}</td></tr><tr style="background:#f4f8ff"><td style="padding:3px 6px;color:#888">Estado dominio</td><td style="padding:3px 6px;text-align:right">${p.estado_dom||"N/D"}</td></tr><tr><td style="padding:3px 6px;color:#888">Tramo / Línea</td><td style="padding:3px 6px;text-align:right">${p.tramo||p.linea||"N/D"}</td></tr><tr style="background:#f4f8ff"><td style="padding:3px 6px;color:#888">Comuna</td><td style="padding:3px 6px;text-align:right">${p.comuna||"N/D"} · ${p.region||""}</td></tr><tr><td style="padding:3px 6px;color:#888">Superficie</td><td style="padding:3px 6px;text-align:right">${fmtNum(p.area_ha)} ha</td></tr>${val}${tas}</table></div>`,{maxWidth:280});
    }
  }).addTo(lTerr);
}
function renderSt(){
  lS.clearLayers();
  let show=curSt?ST.filter(s=>s.nombre===curSt):ST;
  if(curReg&&!curSt)show=show.filter(s=>s.region_short===curReg);
  show=show.filter(s=>aE.has(s.estado||"Servicio Regular"));
  show.forEach(s=>{
    const col=LC[s.linea]||"#555";
    const opac=(s.estado==="No Operativo")?"0.5":"1";
    L.marker([s.lat,s.lng],{icon:L.divIcon({className:"",html:`<div class="est-mk" style="background:${col};opacity:${opac}">🚉</div>`,iconSize:[32,32],iconAnchor:[16,16]}),zIndexOffset:1000})
    .bindPopup(`<div style="font-family:Arial;min-width:210px"><div style="font-size:13px;font-weight:700;color:#1a3a5c">🚉 ${s.nombre}</div><div style="font-size:12px;color:${s.estado==="No Operativo"?"#999":"#1a8c3a"};font-weight:700;margin:3px 0">${s.estado||"Servicio Regular"}</div><div style="font-size:13px;color:${col};font-weight:700;margin:3px 0">${s.tramo||s.linea}</div><div style="font-size:13px;color:#666;margin-bottom:10px">${s.comuna} · ${s.region_short}</div><button onclick="goSt('${s.nombre}')" style="background:${col};color:#fff;border:none;border-radius:6px;padding:8px;width:100%;font-size:13px;font-weight:700;cursor:pointer">🔍 Ver ${(SP[s.nombre]||[]).length} propiedades</button></div>`,{maxWidth:230}).addTo(lS);
  });
}
function renderRings(){
  lR.clearLayers();
  let show=curSt?ST.filter(s=>s.nombre===curSt):ST;
  if(curReg&&!curSt)show=show.filter(s=>s.region_short===curReg);
  ["r4","r3","r2","r1"].forEach(rid=>{if(!aR.has(rid))return;show.forEach(s=>{L.circle([s.lat,s.lng],{radius:RR[rid],color:RS[rid],weight:1.8,dashArray:RD[rid],fillColor:RS[rid],fillOpacity:RA[rid],opacity:.75,interactive:false,renderer:mapRenderer}).addTo(lR);});});
  lR.bringToBack();
  forceRedraw();
}
function renderProps(){
  lP.clearLayers();
  let names;
  if(curSt)names=[curSt];
  else if(curReg)names=ST.filter(s=>s.region_short===curReg).map(s=>s.nombre);
  else{const b=map.getBounds().pad(0.1);names=ST.filter(s=>b.contains([s.lat,s.lng])).map(s=>s.nombre);}
  const cnts={cv:0,dv:0,lv:0,ca:0,da:0,la:0};
  names.forEach(nom=>{(SP[nom]||[]).forEach(p=>{
    const[lat,lng,tipo,op,radio,m2,uf_m2,precio,url,fuente,dist]=p;
    const k=tipo+op;if(!aP.has(k)||!aR.has(radio))return;
    cnts[k]++;const isPI=fuente==="PI";
    L.circleMarker([lat,lng],{radius:5,color:RS[radio],weight:1.8,fillColor:TF[k],fillOpacity:.88,renderer:mapRenderer})
    .bindPopup(`<div style="font-family:Arial;min-width:230px"><div style="font-size:13px;font-weight:700;color:#1a3a5c">${TL[tipo]} en ${OL[op]}</div><div style="font-size:13px;color:#555;margin:4px 0 8px">🚉 <b>${nom}</b> · ${RL[radio]} · ${dist.toLocaleString("es-CL")} m</div><table style="font-size:13px;width:100%;border-collapse:collapse"><tr style="background:#f4f8ff"><td style="padding:3px 6px;color:#888">Precio</td><td style="padding:3px 6px;font-weight:700;color:#1a6b3c;text-align:right">${precio}</td></tr><tr><td style="padding:3px 6px;color:#888">Superficie</td><td style="padding:3px 6px;text-align:right">${m2||"N/D"} m²</td></tr><tr style="background:#f4f8ff"><td style="padding:3px 6px;color:#888">UF/m²</td><td style="padding:3px 6px;text-align:right">${uf_m2||"N/D"}</td></tr><tr style="background:#f4f8ff"><td style="padding:3px 6px;color:#888">Fuente</td><td style="padding:3px 6px;text-align:right;font-weight:700;color:${isPI?"#1a6b9e":"#1a8c3a"}">${isPI?"PortalInmobiliario":"TocToc"}</td></tr></table></div>`,{maxWidth:270}).addTo(lP);
  });});
  Object.entries(cnts).forEach(([k,v])=>{const e=document.getElementById("cnt-"+k);if(e)e.textContent=v.toLocaleString("es-CL");});
  const tot=Object.values(cnts).reduce((a,c)=>a+c,0);
  const b=document.getElementById("bnr");b.style.display="block";
  b.textContent=curSt?`${curSt}  ·  ${tot.toLocaleString("es-CL")} propiedades`:`${curReg||"Propiedades visibles"}  ·  ${tot.toLocaleString("es-CL")}`;
  forceRedraw();
  setTimeout(forceRedraw,50);
}
function renderAll(){renderSt();renderRings();renderProps();if(document.getElementById("chkKml").checked)renderKML();renderPOI();}
window.verTodas=()=>{
  curSt="";curReg="";stSel.value="";regSel.value="";poblarSt("");
  map.setView([-33.65,-70.72],8,{animate:false});renderAll();forceRedraw();
  setTimeout(()=>{renderProps();forceRedraw();},50);
  setTimeout(()=>{renderProps();forceRedraw();},350);
};
window.goSt=function(nom){
  map.closePopup();curSt=nom;stSel.value=nom;
  const s=ST.find(x=>x.nombre===nom);
  if(s)map.setView([s.lat,s.lng],15,{animate:false});
  renderAll();forceRedraw();
  setTimeout(()=>{renderProps();forceRedraw();},50);
  setTimeout(()=>{renderProps();forceRedraw();},350);
};
window.exportXL=function(){
  const wb=XLSX.utils.book_new();
  const HDR=["Estación","Línea","Tipo","Operación","Radio","Dist.(m)","Precio","m²","UF/m²","Fuente","Fecha scraping","Link publicación"];
  const okUrl=u=>(u&&u.startsWith("http")&&!u.includes("redirectedFromVip")&&(u.includes("/MLC-")||u.includes("toctoc.com/propiedades")))?u:"";
  let names=curSt?[curSt]:Object.keys(SP);if(curReg&&!curSt)names=ST.filter(s=>s.region_short===curReg).map(s=>s.nombre);
  [["r1","0-800m"],["r2","800m-3km"],["r3","3-5km"],["r4","Mayor 5km"]].forEach(([rid,rl])=>{
    const rows=[HDR];
    names.forEach(nom=>{const st=ST.find(s=>s.nombre===nom)||{};(SP[nom]||[]).filter(p=>p[4]===rid).forEach(p=>{rows.push([nom,st.linea||"",TL[p[2]],OL[p[3]],rl,p[10],p[7],p[5],p[6],p[9]==="PI"?"PortalInmobiliario":"TocToc",p[11]||"",okUrl(p[8])?{t:"s",v:"🔗 Ver publicación",l:{Target:okUrl(p[8])}}:""]);});});
    const ws=XLSX.utils.aoa_to_sheet(rows);ws["!cols"]=[{wch:22},{wch:18},{wch:14},{wch:10},{wch:12},{wch:9},{wch:18},{wch:7},{wch:9},{wch:18},{wch:14},{wch:22}];
    XLSX.utils.book_append_sheet(wb,ws,rl);
  });
  XLSX.writeFile(wb,`EFE_${(curSt||curReg||"Todas").replace(/[^a-zA-Z0-9]/g,"_")}_${new Date().toISOString().slice(0,10)}.xlsx`);
};
cargar();
window.addEventListener("load",()=>{setTimeout(()=>{map.invalidateSize();renderProps();forceRedraw();},200);});
</script></body></html>"""

(BASE/"visor_EFE_propiedades.html").write_text(html,encoding="utf-8")
sz=(BASE/"visor_EFE_propiedades.html").stat().st_size
print(f"\n  ✅ visor_EFE_propiedades.html ({sz//1024} KB)")
print(f"  ✅ efe_propiedades.json")
print(f"  ✅ efe_estaciones.json")
if (BASE/"terrenos_efe.geojson").exists():
    print(f"  ✅ terrenos_efe.geojson: {(BASE/'terrenos_efe.geojson').stat().st_size//1024} KB")
else:
    print(f"  ⚠️  terrenos_efe.geojson NO está en esta carpeta — la capa 'Terrenos EFE (DOT)' no cargará.")
    print(f"      Copia ese archivo junto a visor_EFE_propiedades.html.")
print(f"\n  Ejecuta: python iniciar_visor.py")
