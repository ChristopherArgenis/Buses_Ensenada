# Buses_Ensenada
Mapeo de las Rutas de Autobuses de la Cuidad de Ensenada, B.C, México

🗺️ **Ver el mapa:** https://christopherargenis.github.io/Buses_Ensenada/

## Estaciones
| Estación | Color | Estado |
|---|---|---|
| Roja | 🔴 | Ampliación Indeco (trazada) |
| Azul | 🔵 | El Sauzal (trazada); Maneadero y Valle de Guadalupe pendientes |
| Amarilla | 🟡 | Pendiente |
| Naranja | 🟠 | Pendiente |

## Mapa
El mapa está publicado con GitHub Pages en https://christopherargenis.github.io/Buses_Ensenada/
(se genera desde `docs/index.html`, con Leaflet + OpenStreetMap). Para verlo localmente:

```bash
cd docs && python3 -m http.server 8000
```

Los datos viven en `docs/datos/`: `estaciones.json` (catálogo) y `rutas/*.geojson` (trazos).
