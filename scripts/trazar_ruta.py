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
# Caja que cubre Ensenada, El Sauzal, Maneadero y Valle de Guadalupe (sur, oeste, norte, este).
BBOX = (31.66, -116.78, 32.13, -116.40)
OVERPASS = "https://overpass.kumi.systems/api/interpreter"

VIAS_PRINCIPALES = {"motorway", "trunk", "primary"}

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


ENLACE = "(enlace sin nombre)"


def descarga_calles():
    if CACHE.exists():
        osm = json.loads(CACHE.read_text())
        # Complementos: otros osm/*.json (p. ej. rampas y retornos sin nombre de una zona).
        vistos = {w["id"] for w in osm["elements"]}
        for extra in sorted(CACHE.parent.glob("*.json")):
            if extra == CACHE:
                continue
            for w in json.loads(extra.read_text())["elements"]:
                if w["id"] not in vistos:
                    osm["elements"].append(w)
                    vistos.add(w["id"])
        return osm
    s, w, n, e = BBOX
    q = f'[out:json][timeout:180];way["highway"]["name"]({s},{w},{n},{e});out body geom;'
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
        nn = nom  # las aristas guardan el nombre OSM exacto
        if not nom:
            # Tramo sin nombre: los enlaces (rampas, retornos) se pueden recorrer
            # libremente como puente; el resto, como calle sin nombre.
            nn = ENLACE if w["tags"].get("highway", "").endswith("_link") else ""
        nombres_osm.setdefault(normaliza(nom), set()).add(nom)
        # Sentido único: solo se respeta en carreteras y vías principales, donde
        # OSM separa cada carril (ej. Calle Primera en El Sauzal). En calles
        # locales se ignora porque suele estar mal etiquetado.
        tags = w["tags"]
        principal = tags.get("highway", "").replace("_link", "") in VIAS_PRINCIPALES
        sentido = tags.get("oneway", "no")
        if tags.get("junction") == "roundabout" and sentido == "no":
            sentido = "yes"
        adelante = not (principal and sentido == "-1")
        atras = not (principal and sentido in ("yes", "true", "1"))
        # Los nodos se identifican por coordenada (las esquinas comparten la misma).
        geom = [(round(g["lat"], 7), round(g["lon"], 7)) for g in w["geometry"]]
        for p1, p2 in zip(geom, geom[1:]):
            n1, n2 = p1, p2
            coords[n1], coords[n2] = p1, p2
            aristas.setdefault(n1, [])
            aristas.setdefault(n2, [])
            d = dist(p1, p2)
            if adelante:
                aristas[n1].append((n2, d, nn))
            if atras:
                aristas[n2].append((n1, d, nn))
    # Conexiones virtuales: rampas y enlaces sin nombre no vienen en la descarga,
    # así que se unen puntos de calles distintas a menos de SALTO metros, o de
    # SALTO_PUNTAS metros si uno es punta suelta (fin de una calle que no
    # conecta con nada): ahí es donde suele faltar un tramo sin nombre.
    SALTO, SALTO_PUNTAS = 15, 30
    grado = {}
    for a, ady in aristas.items():
        for b, _, _ in ady:
            grado.setdefault(a, set()).add(b)
            grado.setdefault(b, set()).add(a)
    punta = {n for n, vec in grado.items() if len(vec) == 1}
    celdas = {}
    for n, p in coords.items():
        celdas.setdefault((int(p[0] * 2500), int(p[1] * 2500)), []).append(n)
    for (ci, cj), lista in celdas.items():
        vecinos = [m for di in (-1, 0, 1) for dj in (-1, 0, 1) for m in celdas.get((ci + di, cj + dj), [])]
        for a in lista:
            for b in vecinos:
                if a < b:
                    d = dist(coords[a], coords[b])
                    limite = SALTO_PUNTAS if a in punta or b in punta else SALTO
                    if 0 < d <= limite and b not in {v for v, _, _ in aristas[a]}:
                        aristas[a].append((b, d, None))
                        aristas[b].append((a, d, None))
    return coords, aristas, nombres_osm


def resuelve_nombre(calle, nombres_osm):
    """Devuelve el conjunto de nombres OSM normalizados que corresponden a `calle`."""
    objetivo = normaliza(calle)
    def originales(claves):
        return {o for k in claves for o in nombres_osm[k]}
    exactos = {n for n in nombres_osm if n == objetivo}
    if exactos:
        return originales(exactos)
    # Coincidencia flexible: singular/plural y contención.
    def raiz(x):
        return re.sub(r"(es|s)$", "", x)
    flex = {n for n in nombres_osm if raiz(n) == raiz(objetivo)}
    if flex:
        return originales(flex)
    return originales({n for n in nombres_osm if objetivo and (objetivo in n.split() or objetivo in n)})


def resuelve_pasos(lista, nombres_osm, max_tramo):
    """Convierte los pasos de la captura en conjuntos de nombres OSM.

    Un paso con "osm": null no existe en OSM: se omite y la calle siguiente se
    alcanza con un puente más largo. "osm": "<nombre>" o [lista] fija nombres exactos.
    """
    pasos, puentes, extra = [], [], 0
    for p in lista:
        if "osm" in p and p["osm"] is None:
            extra = 800
            continue
        pasos.append(p)
        puentes.append(max(max_tramo, extra))
        extra = 0
    todos = {o for v in nombres_osm.values() for o in v}
    conjuntos = []
    for p in pasos:
        if p.get("osm"):
            c = set(p["osm"] if isinstance(p["osm"], list) else [p["osm"]]) & todos
        else:
            c = resuelve_nombre(p["calle"], nombres_osm)
        conjuntos.append(c)
        estado = ", ".join(sorted(c)) or "NO ENCONTRADA"
        print(f"  {p['calle']:<28} -> {estado}")
    if not all(conjuntos):
        raise SystemExit("Hay calles sin coincidencia en OpenStreetMap; revisa los nombres.")
    return pasos, puentes, conjuntos


def nodo_cercano(punto, conjunto, coords, aristas):
    candidatos = [n for n, ady in aristas.items() if any(nm in conjunto for _, _, nm in ady)]
    return min(candidatos, key=lambda n: dist(coords[n], punto))


def traza(lista, origen, coords, aristas, nombres_osm, fin=None, max_tramo=80):
    """Camino más corto que recorre las calles de `lista` en orden, desde el nodo
    `origen`. Termina al llegar a la última calle, o en el punto de ella más
    cercano a `fin` (lat, lon) si se indica."""
    pasos, puentes, conjuntos = resuelve_pasos(lista, nombres_osm, max_tramo)
    ultimo = len(pasos) - 1
    destino = nodo_cercano(fin, conjuntos[ultimo], coords, aristas) if fin else None
    if not any(nm in conjuntos[0] for _, _, nm in aristas.get(origen, [])):
        origen = nodo_cercano(coords[origen], conjuntos[0], coords, aristas)

    # Dijkstra sobre estados (nodo, i, puente): solo se avanza por la calle i,
    # o se cambia a la calle i+1. Se permite un tramo "puente" corto por calles
    # no listadas para tolerar huecos de nombre en OSM.
    INF = float("inf")
    mejor = {(origen, 0, 0.0): 0.0}
    previo = {}
    cola = [(0.0, origen, 0, 0.0)]
    final = None
    while cola:
        d, u, i, puente = heapq.heappop(cola)
        if mejor.get((u, i, puente), INF) < d:
            continue
        if i == ultimo and d > 0 and (u == destino if destino else
                                      any(nm in conjuntos[i] for _, _, nm in aristas[u])):
            final = (u, i, puente)
            break
        for v, w, nm in aristas[u]:
            for j in (i, i + 1):
                if j > ultimo:
                    continue
                if nm in conjuntos[j]:
                    nuevo = (v, j, 0.0)
                elif j == i and nm == ENLACE:
                    nuevo = (v, i, puente)  # los enlaces sin nombre no gastan puente
                elif j == i and puente + w <= (puentes[i + 1] if i < ultimo else max_tramo):
                    nuevo = (v, i, round(puente + w, 1))
                else:
                    continue
                # Las conexiones virtuales (nm None) cuestan más: solo se usan si no
                # hay un camino real.
                nd = d + (w * 4 if nm is None else w)
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
    # Resumen del recorrido: calles consecutivas con su longitud.
    tramos = []
    for a, b in zip(camino, camino[1:]):
        w, nm = min(((w, nm) for v, w, nm in aristas[a] if v == b), key=lambda x: x[0])
        nom = nm or ("(conexión virtual)" if nm is None else "(calle sin nombre)")
        if tramos and tramos[-1][0] == nom:
            tramos[-1][1] += w
        else:
            tramos.append([nom, w])
    print("Recorrido trazado:")
    for nom, w in tramos:
        print(f"  {w:7.0f} m  {nom}")
    metros = sum(dist(coords[a], coords[b]) for a, b in zip(camino, camino[1:]))
    return camino, metros


def main():
    ruta_captura = Path(sys.argv[1])
    captura = json.loads(ruta_captura.read_text())
    print("Cargando calles de OpenStreetMap…")
    coords, aristas, nombres_osm = construye_grafo(descarga_calles())
    print(f"  {len(coords)} nodos, {len(nombres_osm)} nombres de calle")
    inicio = captura["inicio"]["coordenadas"]
    origen = min(coords, key=lambda n: dist(coords[n], inicio))

    print("IDA — coincidencias de calles:")
    camino_ida, m_ida = traza(captura["ida"], origen, coords, aristas, nombres_osm,
                              fin=captura.get("fin_ida"))
    a_geo = lambda camino: [[coords[n][1], coords[n][0]] for n in camino]
    ida = a_geo(camino_ida)

    # Regreso: si la captura trae "regreso_pasos", se traza aparte (desde donde
    # terminó la ida hasta la terminal); si no, es la ida en reversa.
    if captura.get("regreso_pasos"):
        print("REGRESO — coincidencias de calles:")
        camino_reg, m_reg = traza(captura["regreso_pasos"], camino_ida[-1], coords, aristas, nombres_osm,
                                  fin=inicio)
        regreso = a_geo(camino_reg)
    else:
        regreso, m_reg = ida[::-1], m_ida

    base = {"id": captura["id"], "nombre": captura["nombre"], "estacion": captura["estacion"]}
    geo = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "properties": {**base, "sentido": "ida", "km": round(m_ida / 1000, 2)},
             "geometry": {"type": "LineString", "coordinates": ida}},
            {"type": "Feature",
             "properties": {**base, "sentido": "regreso", "km": round(m_reg / 1000, 2),
                            "nota": captura.get("regreso")},
             "geometry": {"type": "LineString", "coordinates": regreso}},
        ],
    }
    salida = RAIZ / "docs" / "datos" / "rutas" / f"{captura['id']}.geojson"
    salida.write_text(json.dumps(geo, ensure_ascii=False))
    print(f"Listo: {salida.relative_to(RAIZ)}  ({m_ida/1000:.2f} km de ida, {m_reg/1000:.2f} km de regreso)")


if __name__ == "__main__":
    main()
