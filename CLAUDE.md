# Contexto del proyecto: Buses Ensenada

Mapeo de las rutas de autobús de Ensenada, B.C., México. No hay datos oficiales:
las rutas se capturan a partir de lo que el usuario conoce (calles en orden) y se
trazan sobre OpenStreetMap.

## Hechos confirmados por el usuario
- Hay **4 estaciones**, cada una con su color: **Rojo, Azul, Amarillo, Naranja**.
  Cada estación tiene sus propias rutas; algunas rutas se parecen entre estaciones.
- **Enfoque actual: Rojo y Azul.** Amarillo y Naranja quedan para después.
- **Rojo**: el usuario los usa más. Parada en Calle Sexta: `31.868357, -116.624647`.
- **Azul**: solo 3 rutas, extensas, todas salen del centro:
  1. Ruta 1: El Sauzal
  2. Ruta 2: Maneadero
  3. Ruta 3: Valle de Guadalupe
- **Transportes El Vigía = terminal Azul**: Calle Sexta 566, Zona Centro, 22800.
  Coordenada: `31.867472, -116.623460`.
- Rojo y Azul tienen **salidas separadas** y sus rutas **no comparten destino**
  (ninguna ruta Roja va a El Sauzal, Maneadero ni Valle de Guadalupe).

## Estructura
- `docs/` → sitio estático (GitHub Pages). `docs/index.html` es el mapa (Leaflet + OSM).
- `docs/datos/estaciones.json` → catálogo de estaciones, terminales y rutas.
- `docs/datos/capturas/<id>.json` → ruta dictada por el usuario (calles en orden).
  Campo opcional `osm` por paso: nombre(s) exactos en OSM, o `null` si la calle no existe en OSM.
- `docs/datos/rutas/<id>.geojson` → trazo generado (LineString de ida y de regreso).
- `osm/calles_ensenada.json` → calles con nombre de OSM (Overpass). Se descarga del espejo
  `overpass.kumi.systems`: `overpass-api.de` corta la conexión desde la nube y desde Colab.
- `scripts/trazar_ruta.py <captura>` → genera el GeoJSON e imprime el recorrido calle por calle.

## Rutas
- **Rojo / Ampliación Indeco**: trazada, 11.03 km de ida; regresa por las mismas calles.
  Equivalencias en OSM: Castañedo → Calle Castaño; "Alhelí" (bajando desde Nogales) → Calle
  de los Alhelíes; "Av. Alhelíes" (de Castaño a Pino) → Calle Alhelíes. "Albatros" no existe
  en OSM: el trazo usa Flamingo entre Blvd. Kumiai y Cisne (por confirmar).

## Reglas
- No inventar coordenadas ni calles: lo no confirmado va como `null` o "por confirmar".
- Coordenadas en JSON del catálogo: `[lat, lon]`. En GeoJSON: `[lon, lat]` (estándar).
- Textos en español.
