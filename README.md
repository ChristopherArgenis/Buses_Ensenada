# Buses_Ensenada
Mapeo de las Rutas de Autobuses de la Cuidad de Ensenada, B.C, México

## Estaciones
| Estación | Color | Estado |
|---|---|---|
| Roja | 🔴 | En captura (terminal en Calle Sexta) |
| Azul | 🔵 | 3 rutas: El Sauzal, Maneadero, Valle de Guadalupe |
| Amarilla | 🟡 | Pendiente |
| Naranja | 🟠 | Pendiente |

## Mapa
El mapa está en `docs/index.html` (Leaflet + OpenStreetMap). Para verlo localmente:

```bash
cd docs && python3 -m http.server 8000
```

Los datos viven en `docs/datos/`: `estaciones.json` (catálogo) y `rutas/*.geojson` (trazos).
