#!/usr/bin/env python3
"""Traza una ruta de autobús a partir de una lista de calles en orden.

Uso:
    python3 scripts/trazar_ruta.py docs/datos/capturas/<ruta>.json

Lee la captura (calles en orden), descarga (o reutiliza en caché) las calles de
Ensenada desde OpenStreetMap (Overpass) y busca el camino más corto que recorre
esas calles exactamente en ese orden. Escribe docs/datos/rutas/<id>.geojson.

Sin dependencias externas: solo biblioteca estándar.
"""
import heapq
import json
import math
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "osm" / "calles_ensenada.json"
# Caja que cubre la mancha urbana de Ensenada (sur, oeste, norte, este).
BBOX = (31.78, -116.70, 31.95, -116.52)
OVERPASS = "https://overpass-api.de/api/interpreter"

PREFIJOS = r"^(calle|c|av|avenida|blvd|boulevard|bulevar|privada|priv|carretera|carr|calz|calzada|circuito)\b\.?\s*"


def normaliza(nombre):
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[.,]", " ", s)
    s = s.strip()
    for _ in range(2):
        s = re.sub(PREFIJOS, "", s).strip()
    s = re.sub(r"\b(de|del|la|las|los|el)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def descarga_calles():
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    s, w, n, e = BBOX
    q = f'[out:json][timeout:180];way["highway"]["name"]({s},{w},{n},{e});out geom tags;'
    datos = urllib.parse.urlencode({"data": q}).encode()
    req = urllib.request.Request(OVERPASS, data=datos, headers={"User-Agent": "buses-ensenada/0.1"})
    with urllib.request.urlopen(req, timeout=240) as r:
        js = json.load(r)
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(js))
    return js


def dist(a, b):
    """Distancia en metros entre (lat, lon)."""
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def construye_grafo(osm):
    coords = {}                 # nodo -> (lat, lon)
    aristas = {}                # nodo -> [(vecino, metros, nombre_norm)]
    nombres_osm = {}            # nombre_norm -> nombre original
    for w in osm["elements"]:
        if w.get("type") != "way" or "geometry" not in w:
            continue
        nom = w["tags"].get("name", "")
        nn = normaliza(nom)
        nombres_osm.setdefault(nn, nom)
        # Sentido único: se registra pero se ignora por ahora (las calles locales
        # de Ensenada suelen estar mal etiquetadas). Se puede activar después.
        for (n1, g1), (n2, g2) in zip(zip(w["nodes"], w["geometry"]), zip(w["nodes"][1:], w["geometry"][1:])):
            p1, p2 = (g1["lat"], g1["lon"]), (g2["lat"], g2["lon"])
            coords[n1], coords[n2] = p1, p2
            d = dist(p1, p2)
            aristas.setdefault(n1, []).append((n2, d, nn))
            aristas.setdefault(n2, []).append((n1, d, nn))
    return coords, aristas, nombres_osm


def resuelve_nombre(calle, nombres_osm):
    """Devuelve el conjunto de nombres OSM normalizados que corresponden a `calle`."""
    objetivo = normaliza(calle)
    exactos = {n for n in nombres_osm if n == objetivo}
    if exactos:
        return exactos
    # Coincidencia flexible: singular/plural y contención.
    def raiz(x):
        return re.sub(r"(es|s)$", "", x)
    flex = {n for n in nombres_osm if raiz(n) == raiz(objetivo)}
    if flex:
        return flex
    return {n for n in nombres_osm if objetivo and (objetivo in n.split() or objetivo in n)}


def traza(captura, coords, aristas, nombres_osm, max_tramo=40):
    pasos = captura["ida"]
    conjuntos = []
    for p in pasos:
        c = resuelve_nombre(p["calle"], nombres_osm)
        conjuntos.append(c)
        estado = ", ".join(sorted(nombres_osm[x] for x in c)) or "NO ENCONTRADA"
        print(f"  {p['calle']:<28} -> {estado}")
    if not all(conjuntos):
        raise SystemExit("Hay calles sin coincidencia en OpenStreetMap; revisa los nombres.")

    # Nodo inicial: el más cercano al inicio que esté sobre la primera calle.
    ini = captura["inicio"]["coordenadas"]
    candidatos = [n for n, ady in aristas.items() if any(nm in conjuntos[0] for _, _, nm in ady)]
    origen = min(candidatos, key=lambda n: dist(coords[n], ini))

    # Dijkstra sobre estados (nodo, i): solo se avanza por la calle i, o se
    # cambia a la calle i+1. Se permite un pequeño tramo "puente" (max_tramo m)
    # por calles no listadas para tolerar huecos de nombre en OSM.
    INF = float("inf")
    mejor = {(origen, 0, 0.0): 0.0}
    previo = {}
    cola = [(0.0, origen, 0, 0.0)]
    final = None
    ultimo = len(pasos) - 1
    while cola:
        d, u, i, puente = heapq.heappop(cola)
        if mejor.get((u, i, puente), INF) < d:
            continue
        if i == ultimo and any(nm in conjuntos[i] for _, _, nm in aristas[u]) and d > 0:
            # Llegamos a la última calle; recorrer un poco sobre ella es suficiente.
            final = (u, i, puente)
            break
        for v, w, nm in aristas[u]:
            for j in (i, i + 1):
                if j > ultimo:
                    continue
                if nm in conjuntos[j]:
                    nuevo = (v, j, 0.0)
                elif j == i and puente + w <= max_tramo:
                    nuevo = (v, i, round(puente + w, 1))
                else:
                    continue
                nd = d + w
                if nd < mejor.get(nuevo, INF):
                    mejor[nuevo] = nd
                    previo[nuevo] = (u, i, puente)
                    heapq.heappush(cola, (nd, *nuevo))
    if final is None:
        alcanzado = max((k[1] for k in mejor), default=0)
        raise SystemExit(f"No se encontró camino. Se llegó hasta el paso {alcanzado}: "
                         f"{pasos[alcanzado]['calle']} -> {pasos[min(alcanzado+1, ultimo)]['calle']}")
    camino = []
    k = final
    while k in previo:
        camino.append(k[0])
        k = previo[k]
    camino.append(k[0])
    camino.reverse()
    return [coords[n] for n in camino], mejor[final]


def main():
    ruta_captura = Path(sys.argv[1])
    captura = json.loads(ruta_captura.read_text())
    print("Cargando calles de OpenStreetMap…")
    coords, aristas, nombres_osm = construye_grafo(descarga_calles())
    print(f"  {len(coords)} nodos, {len(nombres_osm)} nombres de calle")
    print("Coincidencias de calles:")
    puntos, metros = traza(captura, coords, aristas, nombres_osm)
    ida = [[lon, lat] for lat, lon in puntos]
    geo = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "properties": {"id": captura["id"], "nombre": captura["nombre"], "estacion": captura["estacion"],
                            "sentido": "ida", "km": round(metros / 1000, 2)},
             "geometry": {"type": "LineString", "coordinates": ida}},
            {"type": "Feature",
             "properties": {"id": captura["id"], "nombre": captura["nombre"], "estacion": captura["estacion"],
                            "sentido": "regreso", "nota": captura.get("regreso")},
             "geometry": {"type": "LineString", "coordinates": ida[::-1]}},
        ],
    }
    salida = RAIZ / "docs" / "datos" / "rutas" / f"{captura['id']}.geojson"
    salida.write_text(json.dumps(geo, ensure_ascii=False))
    print(f"Listo: {salida.relative_to(RAIZ)}  ({metros/1000:.2f} km de ida)")


if __name__ == "__main__":
    main()
