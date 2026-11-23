"""Valida el inventario de muflas y genera archivos para campo y mapas."""

import csv
import html
import json
import re
import sys
from pathlib import Path

import folium
import qrcode
from PIL import Image, ImageDraw, ImageFont


CARPETA_PROYECTO = Path(__file__).resolve().parent
ARCHIVO_CSV = CARPETA_PROYECTO / "data" / "muflas.csv"
ARCHIVO_NAPS = CARPETA_PROYECTO / "data" / "naps_ejemplo.csv"
ARCHIVO_TRAMOS = CARPETA_PROYECTO / "data" / "tramos_ejemplo.csv"
CARPETA_QR = CARPETA_PROYECTO / "salidas" / "qr"
CARPETA_MAPAS = CARPETA_PROYECTO / "salidas" / "mapas"

COLUMNAS = [
    "id_mufla",
    "tipo",
    "barrio",
    "direccion_referencia",
    "numero_poste",
    "latitud",
    "longitud",
    "cable_entrada",
    "cable_salida",
    "fibras_empalmadas",
    "estado",
    "fecha_instalacion",
    "fecha_ultimo_trabajo",
    "tecnico_responsable",
    "url_foto",
    "observaciones",
]
CAMPOS_OBLIGATORIOS = (
    "id_mufla",
    "tipo",
    "barrio",
    "direccion_referencia",
    "latitud",
    "longitud",
    "estado",
)
TIPOS_VALIDOS = {"aerea", "subterranea", "pedestal"}
ESTADOS_VALIDOS = {"activa", "mantenimiento", "retirada"}


def generar_siguiente_id(zona, ids_existentes):
    """Genera el siguiente ID de la zona usando los consecutivos encontrados."""
    zona = zona.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{3}", zona):
        raise ValueError("La zona debe tener exactamente 3 letras o números.")

    patron = re.compile(r"^MF-CALI-{}-(\d{{4}})$".format(re.escape(zona)))
    consecutivos = [
        int(coincidencia.group(1))
        for id_mufla in ids_existentes
        if (coincidencia := patron.fullmatch(id_mufla.strip()))
    ]
    siguiente = max(consecutivos, default=0) + 1
    if siguiente > 9999:
        raise ValueError("Se agotaron los consecutivos de cuatro dígitos para la zona.")
    return "MF-CALI-{}-{:04d}".format(zona, siguiente)


def leer_inventario():
    """Lee el CSV y devuelve sus filas con validaciones de contenido."""
    if not ARCHIVO_CSV.exists():
        raise ValueError("No se encontró el archivo de inventario: {}".format(ARCHIVO_CSV))

    with ARCHIVO_CSV.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        if lector.fieldnames is None:
            raise ValueError("El CSV está vacío o no tiene encabezados.")

        faltantes = [columna for columna in COLUMNAS if columna not in lector.fieldnames]
        if faltantes:
            raise ValueError(
                "Faltan columnas en muflas.csv: {}.".format(", ".join(faltantes))
            )
        filas = list(lector)

    if not filas:
        raise ValueError("El inventario no contiene muflas.")

    errores = []
    ids_vistos = set()
    patron_id = re.compile(r"^MF-CALI-[A-Z0-9]{3}-\d{4}$")
    filas_validas = []

    for numero_fila, fila in enumerate(filas, start=2):
        fila_valida = True
        for campo in CAMPOS_OBLIGATORIOS:
            if not (fila.get(campo) or "").strip():
                errores.append("Fila {}: el campo obligatorio '{}' está vacío.".format(
                    numero_fila, campo
                ))
                fila_valida = False

        id_mufla = (fila.get("id_mufla") or "").strip()
        if id_mufla:
            if id_mufla in ids_vistos:
                errores.append(
                    "Fila {}: el ID '{}' está duplicado.".format(numero_fila, id_mufla)
                )
                fila_valida = False
            ids_vistos.add(id_mufla)
            if not patron_id.fullmatch(id_mufla):
                errores.append(
                    "Fila {}: el ID '{}' no cumple el formato "
                    "MF-CALI-ZON-0001.".format(numero_fila, id_mufla)
                )
                fila_valida = False

        tipo = (fila.get("tipo") or "").strip().lower()
        if tipo and tipo not in TIPOS_VALIDOS:
            errores.append(
                "Fila {}: tipo '{}' no válido. Use aerea, subterranea o pedestal."
                .format(numero_fila, tipo)
            )
            fila_valida = False

        estado = (fila.get("estado") or "").strip().lower()
        if estado and estado not in ESTADOS_VALIDOS:
            errores.append(
                "Fila {}: estado '{}' no válido. Use activa, mantenimiento o retirada."
                .format(numero_fila, estado)
            )
            fila_valida = False

        coordenadas = {}
        for campo, minimo, maximo in (
            ("latitud", 2, 5),
            ("longitud", -78, -75),
        ):
            try:
                valor = float((fila.get(campo) or "").strip())
                if not minimo <= valor <= maximo:
                    errores.append(
                        "Fila {}: {} debe estar entre {} y {}.".format(
                            numero_fila, campo, minimo, maximo
                        )
                    )
                    fila_valida = False
                coordenadas[campo] = valor
            except ValueError:
                if (fila.get(campo) or "").strip():
                    errores.append(
                        "Fila {}: '{}' debe ser un número.".format(numero_fila, campo)
                    )
                    fila_valida = False

        if fila_valida:
            fila = {campo: (fila.get(campo) or "").strip() for campo in COLUMNAS}
            fila.update(coordenadas)
            filas_validas.append(fila)

    if errores:
        raise ValueError("Errores en muflas.csv:\n- " + "\n- ".join(errores))
    return filas_validas


def leer_red_de_ejemplo(filas_muflas):
    """Lee y valida NAPs y recorridos de demostración del proyecto."""
    for archivo in (ARCHIVO_NAPS, ARCHIVO_TRAMOS):
        if not archivo.exists():
            raise ValueError("No se encontró el archivo de red de ejemplo: {}".format(archivo))

    def leer_csv(archivo, columnas):
        with archivo.open("r", encoding="utf-8-sig", newline="") as entrada:
            lector = csv.DictReader(entrada)
            faltantes = [columna for columna in columnas if columna not in (lector.fieldnames or [])]
            if faltantes:
                raise ValueError(
                    "Faltan columnas en {}: {}.".format(
                        archivo.name, ", ".join(faltantes)
                    )
                )
            return list(lector)

    registros_nap = leer_csv(
        ARCHIVO_NAPS,
        (
            "id_nap",
            "cluster",
            "latitud",
            "longitud",
            "mufla_alimentadora",
            "observaciones",
        ),
    )
    registros_tramo = leer_csv(
        ARCHIVO_TRAMOS,
        (
            "id_tramo",
            "cable",
            "origen",
            "destino",
            "tipo_cable",
            "trazado_geojson",
            "observaciones",
        ),
    )
    if not registros_nap or not registros_tramo:
        raise ValueError("Los archivos de la red de ejemplo no deben estar vacíos.")

    nodos = {fila["id_mufla"]: (fila["longitud"], fila["latitud"]) for fila in filas_muflas}
    naps = []
    for numero_fila, registro in enumerate(registros_nap, start=2):
        id_nap = (registro.get("id_nap") or "").strip()
        if not id_nap or id_nap in nodos:
            raise ValueError(
                "Fila {} de naps_ejemplo.csv: ID vacío o duplicado '{}'.".format(
                    numero_fila, id_nap
                )
            )
        try:
            latitud = float(registro["latitud"])
            longitud = float(registro["longitud"])
        except ValueError:
            raise ValueError(
                "Fila {} de naps_ejemplo.csv: latitud y longitud deben ser números."
                .format(numero_fila)
            )
        if not 2 <= latitud <= 5 or not -78 <= longitud <= -75:
            raise ValueError(
                "Fila {} de naps_ejemplo.csv: coordenadas fuera del rango de Cali."
                .format(numero_fila)
            )
        mufla = (registro.get("mufla_alimentadora") or "").strip()
        if mufla not in nodos:
            raise ValueError(
                "Fila {} de naps_ejemplo.csv: la mufla alimentadora '{}' no existe."
                .format(numero_fila, mufla)
            )
        nap = {
            "id_nap": id_nap,
            "cluster": (registro.get("cluster") or "").strip(),
            "latitud": latitud,
            "longitud": longitud,
            "mufla_alimentadora": mufla,
            "observaciones": (registro.get("observaciones") or "").strip(),
        }
        nodos[id_nap] = (longitud, latitud)
        naps.append(nap)

    tramos = []
    ids_tramo = set()
    for numero_fila, registro in enumerate(registros_tramo, start=2):
        id_tramo = (registro.get("id_tramo") or "").strip()
        origen = (registro.get("origen") or "").strip()
        destino = (registro.get("destino") or "").strip()
        if not id_tramo or id_tramo in ids_tramo:
            raise ValueError(
                "Fila {} de tramos_ejemplo.csv: ID de tramo vacío o duplicado '{}'."
                .format(numero_fila, id_tramo)
            )
        ids_tramo.add(id_tramo)
        if origen not in nodos or destino not in nodos:
            raise ValueError(
                "Fila {} de tramos_ejemplo.csv: origen o destino no existe "
                "('{}' -> '{}').".format(numero_fila, origen, destino)
            )
        try:
            coordenadas = json.loads(registro["trazado_geojson"])
            if len(coordenadas) < 2:
                raise ValueError
            coordenadas = [[float(x), float(y)] for x, y in coordenadas]
        except (TypeError, ValueError, json.JSONDecodeError):
            raise ValueError(
                "Fila {} de tramos_ejemplo.csv: trazado_geojson debe ser una "
                "lista de al menos dos pares [longitud, latitud].".format(numero_fila)
            )
        if coordenadas[0] != list(nodos[origen]) or coordenadas[-1] != list(nodos[destino]):
            raise ValueError(
                "Fila {} de tramos_ejemplo.csv: el trazado debe iniciar y terminar "
                "en las coordenadas de sus nodos.".format(numero_fila)
            )
        for longitud, latitud in coordenadas:
            if not 2 <= latitud <= 5 or not -78 <= longitud <= -75:
                raise ValueError(
                    "Fila {} de tramos_ejemplo.csv: el trazado tiene coordenadas "
                    "fuera del rango de Cali.".format(numero_fila)
                )
        tramos.append(
            {
                "id_tramo": id_tramo,
                "cable": (registro.get("cable") or "").strip(),
                "origen": origen,
                "destino": destino,
                "tipo_cable": (registro.get("tipo_cable") or "").strip(),
                "coordenadas": coordenadas,
                "observaciones": (registro.get("observaciones") or "").strip(),
            }
        )
    return naps, tramos


def crear_codigo_qr(fila):
    """Crea un QR de Google Maps y añade el ID debajo para imprimir la etiqueta."""
    url = "https://www.google.com/maps?q={},{}".format(
        fila["latitud"], fila["longitud"]
    )
    codigo = qrcode.QRCode(box_size=8, border=3)
    codigo.add_data(url)
    codigo.make(fit=True)
    imagen_qr = codigo.make_image(fill_color="black", back_color="white").convert("RGB")

    margen = 18
    alto_texto = 42
    etiqueta = Image.new(
        "RGB",
        (imagen_qr.width + margen * 2, imagen_qr.height + margen * 2 + alto_texto),
        "white",
    )
    etiqueta.paste(imagen_qr, (margen, margen))
    dibujo = ImageDraw.Draw(etiqueta)
    try:
        fuente = ImageFont.truetype("arial.ttf", 20)
    except OSError:
        fuente = ImageFont.load_default()

    texto = fila["id_mufla"]
    caja = dibujo.textbbox((0, 0), texto, font=fuente)
    ancho_texto = caja[2] - caja[0]
    x = (etiqueta.width - ancho_texto) // 2
    dibujo.text((x, imagen_qr.height + margen + 8), texto, fill="black", font=fuente)
    etiqueta.save(CARPETA_QR / "{}.png".format(fila["id_mufla"]))


def crear_kml(filas, naps, tramos, destino):
    """Escribe en KML muflas, NAPs y tramos de la red de ejemplo."""
    lineas = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
        "<name>RED FICTICIA - NO USAR EN CAMPO</name>",
    ]
    for fila in filas:
        nombre = "{} - {}".format(fila["id_mufla"], fila["tipo"])
        detalles = "<br/>".join(
            "{}: {}".format(html.escape(campo), html.escape(str(fila[campo])))
            for campo in COLUMNAS
            if fila[campo] != ""
        )
        lineas.extend(
            [
                "<Placemark>",
                "<name>{}</name>".format(html.escape(nombre)),
                "<description><![CDATA[{}]]></description>".format(detalles),
                "<Point><coordinates>{},{},0</coordinates></Point>".format(
                    fila["longitud"], fila["latitud"]
                ),
                "</Placemark>",
            ]
        )
    for nap in naps:
        lineas.extend(
            [
                "<Placemark>",
                "<name>{}</name>".format(html.escape(nap["id_nap"])),
                "<description><![CDATA[<b>NAP FICTICIA</b><br/>Cluster: {}<br/>"
                "Mufla alimentadora: {}<br/>{}]]></description>".format(
                    html.escape(nap["cluster"]),
                    html.escape(nap["mufla_alimentadora"]),
                    html.escape(nap["observaciones"]),
                ),
                "<Point><coordinates>{},{},0</coordinates></Point>".format(
                    nap["longitud"], nap["latitud"]
                ),
                "</Placemark>",
            ]
        )
    for tramo in tramos:
        coordenadas = " ".join(
            "{},{},0".format(longitud, latitud)
            for longitud, latitud in tramo["coordenadas"]
        )
        lineas.extend(
            [
                "<Placemark>",
                "<name>{} - {}</name>".format(
                    html.escape(tramo["id_tramo"]), html.escape(tramo["cable"])
                ),
                "<description><![CDATA[<b>TRAZADO FICTICIO</b><br/>"
                "Origen: {}<br/>Destino: {}<br/>Tipo: {}<br/>{}]]></description>"
                .format(
                    html.escape(tramo["origen"]),
                    html.escape(tramo["destino"]),
                    html.escape(tramo["tipo_cable"]),
                    html.escape(tramo["observaciones"]),
                ),
                "<LineString><tessellate>1</tessellate><coordinates>{}"
                "</coordinates></LineString>".format(coordenadas),
                "</Placemark>",
            ]
        )
    lineas.append("</Document></kml>")
    destino.write_text("\n".join(lineas), encoding="utf-8")


def crear_geojson(filas, naps, tramos, destino):
    """Escribe muflas, NAPs y tramos como entidades GeoJSON."""
    elementos = []
    for fila in filas:
        propiedades = {
            "elemento": "mufla",
            **{
                campo: fila[campo]
                for campo in COLUMNAS
                if campo not in ("latitud", "longitud")
            },
        }
        elementos.append(
            {
                "type": "Feature",
                "properties": propiedades,
                "geometry": {
                    "type": "Point",
                    "coordinates": [fila["longitud"], fila["latitud"]],
                },
            }
        )
    for nap in naps:
        elementos.append(
            {
                "type": "Feature",
                "properties": {
                    "elemento": "NAP",
                    "id_nap": nap["id_nap"],
                    "cluster": nap["cluster"],
                    "mufla_alimentadora": nap["mufla_alimentadora"],
                    "observaciones": nap["observaciones"],
                    "dato": "FICTICIO - NO USAR EN CAMPO",
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [nap["longitud"], nap["latitud"]],
                },
            }
        )
    for tramo in tramos:
        elementos.append(
            {
                "type": "Feature",
                "properties": {
                    "elemento": "tramo_ficticio",
                    "id_tramo": tramo["id_tramo"],
                    "cable": tramo["cable"],
                    "origen": tramo["origen"],
                    "destino": tramo["destino"],
                    "tipo_cable": tramo["tipo_cable"],
                    "observaciones": tramo["observaciones"],
                    "dato": "FICTICIO - NO USAR EN CAMPO",
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": tramo["coordenadas"],
                },
            }
        )

    contenido = {"type": "FeatureCollection", "features": elementos}
    destino.write_text(
        json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def crear_mapa_web(filas, naps, tramos, destino):
    """Crea un mapa de demostración con muflas, NAPs y tramos ficticios."""
    ubicaciones = [
        (fila["latitud"], fila["longitud"]) for fila in filas
    ] + [(nap["latitud"], nap["longitud"]) for nap in naps]
    latitud_centro = sum(latitud for latitud, _ in ubicaciones) / len(ubicaciones)
    longitud_centro = sum(longitud for _, longitud in ubicaciones) / len(ubicaciones)
    mapa = folium.Map(location=[latitud_centro, longitud_centro], zoom_start=15)
    capa_muflas = folium.FeatureGroup(name="Muflas (ejemplo)", show=True)
    capa_naps = folium.FeatureGroup(name="Cluster CL-CALI-FLO-01 (ficticio)", show=True)
    capa_tramos = folium.FeatureGroup(name="Trazados ficticios", show=True)

    for fila in filas:
        url = "https://www.google.com/maps?q={},{}".format(
            fila["latitud"], fila["longitud"]
        )
        datos = "<br>".join(
            "<b>{}</b>: {}".format(
                html.escape(campo), html.escape(str(fila[campo]))
            )
            for campo in COLUMNAS
            if fila[campo] != ""
        )
        popup = '{}<br><a href="{}" target="_blank" rel="noopener">'
        popup = popup.format(datos, html.escape(url, quote=True)) + "Cómo llegar</a>"
        folium.Marker(
            [fila["latitud"], fila["longitud"]],
            tooltip=fila["id_mufla"],
            popup=folium.Popup(popup, max_width=350),
            icon=folium.Icon(color="blue", icon="link"),
        ).add_to(capa_muflas)
    for nap in naps:
        popup = (
            "<b>{}</b><br/>Cluster ficticio: {}<br/>Mufla alimentadora: {}<br/>{}"
        ).format(
            html.escape(nap["id_nap"]),
            html.escape(nap["cluster"]),
            html.escape(nap["mufla_alimentadora"]),
            html.escape(nap["observaciones"]),
        )
        folium.CircleMarker(
            [nap["latitud"], nap["longitud"]],
            radius=7,
            color="#16803c",
            fill=True,
            fill_opacity=0.9,
            tooltip=nap["id_nap"],
            popup=folium.Popup(popup, max_width=300),
        ).add_to(capa_naps)
    for tramo in tramos:
        color = "#d97706" if tramo["tipo_cable"] == "troncal" else "#16803c"
        popup = (
            "<b>{}</b><br/>TRAZADO FICTICIO<br/>Cable: {}<br/>{} → {}"
            "<br/>Tipo: {}<br/>{}"
        ).format(
            html.escape(tramo["id_tramo"]),
            html.escape(tramo["cable"]),
            html.escape(tramo["origen"]),
            html.escape(tramo["destino"]),
            html.escape(tramo["tipo_cable"]),
            html.escape(tramo["observaciones"]),
        )
        folium.PolyLine(
            [(latitud, longitud) for longitud, latitud in tramo["coordenadas"]],
            color=color,
            weight=5 if tramo["tipo_cable"] == "troncal" else 3,
            opacity=0.85,
            tooltip="{}: {} → {}".format(
                tramo["cable"], tramo["origen"], tramo["destino"]
            ),
            popup=folium.Popup(popup, max_width=350),
        ).add_to(capa_tramos)

    capa_tramos.add_to(mapa)
    capa_muflas.add_to(mapa)
    capa_naps.add_to(mapa)
    folium.LayerControl(collapsed=False).add_to(mapa)
    aviso = """
    <div style="position:fixed;top:10px;left:50px;z-index:9999;
                background:#7f1d1d;color:white;padding:10px 14px;
                border:2px solid white;border-radius:5px;font-weight:bold;
                box-shadow:0 1px 5px #555;">
      CLUSTER FICTICIO — NO REPRESENTA LA RED REAL — NO USAR EN CAMPO
    </div>
    """
    mapa.get_root().html.add_child(folium.Element(aviso))

    mapa.save(str(destino))


def main():
    """Valida el CSV y genera todos los entregables en la carpeta salidas/."""
    try:
        filas = leer_inventario()
        naps, tramos = leer_red_de_ejemplo(filas)
        CARPETA_QR.mkdir(parents=True, exist_ok=True)
        CARPETA_MAPAS.mkdir(parents=True, exist_ok=True)

        for fila in filas:
            crear_codigo_qr(fila)
        crear_kml(filas, naps, tramos, CARPETA_MAPAS / "muflas.kml")
        crear_geojson(filas, naps, tramos, CARPETA_MAPAS / "muflas.geojson")
        crear_mapa_web(filas, naps, tramos, CARPETA_MAPAS / "mapa.html")
    except (OSError, ValueError) as error:
        print("No se pudieron generar las salidas:\n{}".format(error), file=sys.stderr)
        return 1

    print(
        "Proceso completado: {} muflas, {} NAPs y {} tramos ficticios.".format(
            len(filas), len(naps), len(tramos)
        )
    )
    print("Códigos QR: {}".format(CARPETA_QR))
    print("Mapas: {}".format(CARPETA_MAPAS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
