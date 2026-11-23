# Inventario de muflas - La Flora, Cali

Proyecto piloto para que los técnicos consulten desde el celular la ubicación y
los datos de los cierres de empalme de fibra óptica. Las ubicaciones incluidas
al inicio son **datos de ejemplo**: deben verificarse y reemplazarse en campo
antes de usarse como información operativa.

## Estructura

```text
inventario-muflas/
├── data/
│   ├── muflas.csv
│   ├── naps_ejemplo.csv
│   └── tramos_ejemplo.csv
├── salidas/
│   ├── qr/
│   └── mapas/
├── generar_salidas.py
├── requirements.txt
└── README.md
```

## Requisitos

- Python 3.9 o posterior.
- Conexión a Internet para cargar el mapa base en Folium y abrir Google Maps.

## Instalación y generación

1. Abra una terminal en la carpeta del proyecto.
2. (Recomendado) Cree y active un entorno virtual:

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. Instale las dependencias:

   ```powershell
   py -m pip install -r requirements.txt
   ```

4. Genere los archivos:

   ```powershell
   py generar_salidas.py
   ```

Si hay datos inválidos, el programa mostrará los errores en español y no
generará las salidas. Las imágenes QR quedan en `salidas/qr/`; los mapas en
`salidas/mapas/`.

## Cómo agregar una mufla

1. Abra `data/muflas.csv` en una hoja de cálculo o editor de texto.
2. Añada una fila respetando el orden y los nombres de las columnas existentes.
   No elimine la fila de encabezados.
3. Complete los campos obligatorios: `id_mufla`, `tipo`, `barrio`,
   `direccion_referencia`, `latitud`, `longitud` y `estado`.
4. Use `aerea`, `subterranea` o `pedestal` en `tipo`; y `activa`,
   `mantenimiento` o `retirada` en `estado`.
5. Escriba latitud y longitud como números decimales. Para Cali, el programa
   verifica latitudes de 2 a 5 y longitudes de -78 a -75.
6. Para crear el siguiente ID de una zona, use la función
   `generar_siguiente_id(zona, ids_existentes)` de `generar_salidas.py`.
   Por ejemplo, la zona `FLO` produce IDs como `MF-CALI-FLO-0001`.
7. Guarde el CSV en UTF-8 y vuelva a ejecutar `py generar_salidas.py`.

El programa valida que los IDs sean únicos y tengan el formato
`MF-CALI-ZON-0001`, además de revisar los campos requeridos, tipos, estados y
coordenadas. Si se agrega una mufla real, quite cualquier observación que la
identifique como dato de ejemplo.

## Red de fibra de demostración

El proyecto incluye una topología inventada en `data/naps_ejemplo.csv` y
`data/tramos_ejemplo.csv`: un cluster ficticio (`CL-CALI-FLO-01`), seis NAPs,
enlaces a muflas y recorridos esquemáticos. Sirve únicamente para mostrar cómo
se vería una red en el mapa. No representa postes, ductos, empalmes, cableado
ni ubicaciones reales. El mapa lleva un aviso visible y los datos de salida
también quedan marcados como ficticios. **No usar para navegación,
instalaciones ni trabajos de campo.**

## Archivos generados

- **Códigos QR**: un PNG por mufla. Al escanearlo se abre la coordenada en
  Google Maps; el ID aparece debajo del código para identificar la etiqueta.
- **KML**: `salidas/mapas/muflas.kml`, con muflas, NAPs y enlaces ficticios.
- **GeoJSON**: `salidas/mapas/muflas.geojson`, con puntos y líneas de ejemplo.
- **Mapa web**: `salidas/mapas/mapa.html`, con capas para muflas, NAPs y
  trazados, popups y un aviso de datos ficticios. Para cargar el mapa base
  necesita conexión a Internet.

## Importar el KML en Google My Maps

1. Abra [Google My Maps](https://www.google.com/mymaps) e inicie sesión.
2. Cree un mapa nuevo o abra uno existente.
3. En una capa, seleccione **Importar**.
4. Elija `salidas/mapas/muflas.kml` desde su equipo.
5. Revise los nombres y descripciones importados y guarde el mapa.

## Usar el GeoJSON con QGIS y QField

1. En QGIS, seleccione **Capa > Añadir capa > Añadir capa vectorial**.
2. Seleccione `salidas/mapas/muflas.geojson` y añádalo al proyecto.
3. Revise que las ubicaciones y los atributos se vean correctamente.
4. Para QField, guarde el proyecto en un paquete compatible con QField
   (por ejemplo, con QFieldSync) e incluya el GeoJSON junto con el proyecto.
5. Sincronice o copie el paquete al dispositivo y ábralo en QField.

Antes de distribuir información a los técnicos, confirme en sitio las
coordenadas, direcciones y demás datos; las cinco filas iniciales son solo
ejemplos aproximados.
