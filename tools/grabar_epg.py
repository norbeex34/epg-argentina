"""Descarga la programación y genera la guía XMLTV + la M3U enlazada.

Uso: py grabar_epg.py [--dias 4] [--url-guia https://tuservidor/guia.xml.gz]

Lee epg/canales.json (creado por generar_channels.py) y escribe:
  epg/guia.xml.gz   la guía XMLTV, con los mismos IDs que la M3U
  epg/ar_epg.m3u    la lista original con url-tvg apuntando a la guía
Solo usa la librería estándar de Python.
"""
import argparse, gzip, html, json, re, sys, time, urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
M3U_URL = "https://iptv-org.github.io/iptv/countries/ar.m3u"
EPGSHARE_URL = "https://epgshare01.online/epgshare01/epg_ripper_AR1.xml.gz"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"


def descargar(url, reintentos=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    for i in range(reintentos):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:
            if i == reintentos - 1:
                print(f"  ! {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2 * (i + 1))


# --- mi.tv -----------------------------------------------------------------
# La página asíncrona de mi.tv lista los programas de un día con la hora en UTC.
ITEM = re.compile(
    r'<span class="time">([^<]+)</span>\s*<h2>(.*?)</h2>'
    r'(?:.*?<span class="sub-title">(.*?)</span>)?'
    r'(?:.*?<p class="synopsis">(.*?)</p>)?', re.S)


def limpiar(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def leer_hora(texto):
    """'21:30' o, en las páginas de Colombia, '9:30pm'."""
    t = texto.strip().lower()
    hh, mm = map(int, t.rstrip("apm").split(":"))
    if t.endswith("pm") and hh != 12:
        hh += 12
    elif t.endswith("am") and hh == 12:
        hh = 0
    return hh, mm


def grabar_mitv(site_id, dias):
    pais, canal = site_id.split("#")
    programas = []
    hoy = datetime.now(timezone.utc).date()
    # Empezamos ayer (UTC): la noche argentina ya cae en el día siguiente en UTC,
    # y mi.tv a veces deja días sin cargar.
    for d in range(-1, dias):
        fecha = hoy + timedelta(days=d)
        crudo = descargar(f"https://mi.tv/{pais}/async/channel/{canal}/{fecha:%Y-%m-%d}/0")
        if not crudo:
            continue
        dia = datetime.combine(fecha, datetime.min.time(), timezone.utc)
        anterior = None
        # Cada <li> es un programa; separarlos evita que el regex mezcle sinopsis.
        for li in crudo.decode("utf-8", "replace").split("<li")[1:]:
            m = ITEM.search(li)
            if not m:
                continue
            hh, mm = leer_hora(m.group(1))
            inicio = dia.replace(hour=hh, minute=mm)
            # Si la hora retrocede dentro de la página, el programa ya es del día siguiente.
            if anterior and inicio < anterior:
                inicio += timedelta(days=1)
                dia += timedelta(days=1)
            anterior = inicio
            programas.append({"inicio": inicio, "titulo": limpiar(m.group(2)),
                              "categoria": limpiar(m.group(3)), "desc": limpiar(m.group(4))})
    # Quitamos duplicados entre días y cerramos cada programa con el inicio del siguiente.
    unicos = {p["inicio"]: p for p in programas}
    programas = [unicos[k] for k in sorted(unicos)]
    # Tope de 4 h: si mi.tv dejó un día vacío, mejor un hueco que un programa de 24 h.
    for a, b in zip(programas, programas[1:]):
        a["fin"] = min(b["inicio"], a["inicio"] + timedelta(hours=4))
    if programas:
        programas[-1]["fin"] = programas[-1]["inicio"] + timedelta(hours=1)
    return programas


def hora_xmltv(dt):
    return dt.strftime("%Y%m%d%H%M%S +0000")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=4)
    ap.add_argument("--url-guia", default="guia.xml.gz",
                    help="URL (o ruta) que se escribe en url-tvg de la M3U")
    args = ap.parse_args()

    canales = json.load(open(RAIZ / "epg" / "canales.json", encoding="utf-8"))
    tv = ET.Element("tv", {"generator-info-name": "grabar_epg.py"})
    for tvg_id, c in canales.items():
        canal = ET.SubElement(tv, "channel", id=tvg_id)
        ET.SubElement(canal, "display-name").text = c["nombre"]

    # mi.tv: varios canales a la vez, sin pasarnos para no saturar el sitio.
    mitv = {k: c for k, c in canales.items() if c["fuente"] == "mi.tv"}
    print(f"mi.tv: {len(mitv)} canales, {args.dias} días...")
    with ThreadPoolExecutor(max_workers=4) as ex:
        resultados = dict(zip(mitv, ex.map(lambda c: grabar_mitv(c["id"], args.dias), mitv.values())))
    total = 0
    share = {}
    for tvg_id, programas in resultados.items():
        for p in programas:
            prog = ET.SubElement(tv, "programme", start=hora_xmltv(p["inicio"]),
                                 stop=hora_xmltv(p["fin"]), channel=tvg_id)
            ET.SubElement(prog, "title", lang="es").text = p["titulo"]
            if p["desc"]:
                ET.SubElement(prog, "desc", lang="es").text = p["desc"]
            if p["categoria"]:
                ET.SubElement(prog, "category", lang="es").text = p["categoria"]
        total += len(programas)
        if not programas:
            respaldo = canales[tvg_id].get("respaldo")
            if respaldo:
                share.setdefault(respaldo, []).append(tvg_id)
            print(f"  - sin datos: {canales[tvg_id]['nombre']}" + (" (usa epgshare01)" if respaldo else ""))
    print(f"  {total} programas")

    # epgshare01: copiamos los programas cambiando su ID por el tvg-id de la M3U.
    # Un mismo canal de epgshare puede alimentar varias entradas de la M3U (HD/SD).
    for k, c in canales.items():
        if c["fuente"] == "epgshare":
            share.setdefault(c["id"], []).append(k)
    if share:
        crudo = descargar(EPGSHARE_URL)
        n = 0
        if crudo:
            for prog in ET.fromstring(gzip.decompress(crudo)).iter("programme"):
                for tvg_id in share.get(prog.get("channel"), []):
                    copia = ET.fromstring(ET.tostring(prog))
                    copia.set("channel", tvg_id)
                    tv.append(copia)
                    n += 1
        print(f"epgshare01: {len(share)} canales, {n} programas")

    salida = RAIZ / "epg"
    ET.indent(tv)
    with gzip.open(salida / "guia.xml.gz", "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(tv, encoding="utf-8"))

    m3u = descargar(M3U_URL).decode("utf-8")
    m3u = re.sub(r"^#EXTM3U[^\n]*", f'#EXTM3U url-tvg="{args.url_guia}"', m3u, count=1)
    (salida / "ar_epg.m3u").write_text(m3u, encoding="utf-8")
    print(f"Listo: {salida / 'guia.xml.gz'} y {salida / 'ar_epg.m3u'}")


if __name__ == "__main__":
    main()
