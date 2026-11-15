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
  El Sauzal, Maneadero y Valle de Guadalupe (se nombran solo por destino, sin "Ruta X:").
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
- **Rojo / Ampliación Indeco**: trazada y **verificada por el usuario**, 11.03 km de ida;
  regresa por las mismas calles.
  Equivalencias en OSM: Castañedo → Calle Castaño; "Alhelí" (bajando desde Nogales) → Calle
  de los Alhelíes; "Av. Alhelíes" (de Castaño a Pino) → Calle Alhelíes. "Albatros" no existe
  en OSM: el tramo entre Blvd. Kumiai y Cisne es Flamingo (confirmado).

- **Azul / El Sauzal**: trazada (11.04 km ida, 10.54 km regreso), por verificar con el usuario.
  Centro: Sexta → Gastélum → Novena → 20 de Noviembre → Décima → Clark Flores → Carretera
  Tijuana–Ensenada (Libre) → Calle Primera (en El Sauzal es la carretera federal, de dos carriles
  separados) → retorno en la Carretera Tecate–El Sauzal → Calle Diez → Calle Tres (ahí espera)
  → Calle Nueve → Calle Primera, y regresa por las mismas calles por el carril de vuelta.
  "Calle 3" en OSM es "Calle Tres".

## Trazado (scripts/trazar_ruta.py)
- Respeta sentido único solo en vías motorway/trunk/primary (y sus enlaces); en calles locales lo ignora.
- La descarga solo trae calles con nombre; los huecos se cubren con conexiones virtuales
  (15 m en general, 30 m si un extremo es punta suelta).
- Captura: `ida` (pasos), `regreso_pasos` opcional (si no, el regreso es la ida en reversa),
  `fin_ida` opcional ([lat, lon]).

## Reglas
- No inventar coordenadas ni calles: lo no confirmado va como `null` o "por confirmar".
- Coordenadas en JSON del catálogo: `[lat, lon]`. En GeoJSON: `[lon, lat]` (estándar).
- Textos en español.
