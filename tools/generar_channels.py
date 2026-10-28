"""Genera epg/canales.json: qué fuente de EPG usa cada canal de la M3U.

Uso: py generar_channels.py ar.m3u guides.json epg/canales.json

guides.json es el índice de iptv-org (https://iptv-org.github.io/api/guides.json).
Solo hace falta volver a ejecutarlo si cambia la lista de canales.
"""
import json, re, sys, collections

M3U, GUIDES, OUT = sys.argv[1:4]

# Variantes regionales sin guía propia: usan la programación de la señal nacional.
ALIAS = {
    "TelefeBuenosAires.ar": "Telefe.ar",
    "TelefeInterior.ar": "Telefe.ar",
    "TelefeSalta.ar": "Telefe.ar",
    "TelefeTucuman.ar": "Telefe.ar",
}

# Equivalencias con epgshare01 (epg_ripper_AR1), que usa otros IDs. Se usa si el
# canal no está en mi.tv, o como respaldo cuando mi.tv no devuelve programación.
EPGSHARE = {
    "AXNLatinAmerica.us": "Canal.AXN.(Argentina).ar",
    "Cinecanal.us": "Canal.Cinecanal.(Argentina).ar",
    "DisneyChannelLatinAmerica.ar": "Canal.Disney.Channel.(Argentina).ar",
    "DisneyJrLatinAmerica.ar": "Canal.Disney.Junior.(Argentina).ar",
    "ElGourmet.ar": "Canal.Elgourmet.ar",
    "ESPNLatinAmerica.us": "Canal.ESPN.(Argentina).ar",
    "ESPN3LatinAmerica.us": "Canal.ESPN.3.(Argentina).ar",
    "Pakapaka.ar": "Canal.Pakapaka.ar",
    "SonyChannel.ar": "Canal.Sony.(Argentina).ar",
    "Space.ar": "Canal.Space.(Argentina).ar",
    "StarChannelLatinAmerica.us": "Canal.Star.Channel.(Argentina).ar",
    "TelevisionPublica.ar": "Canal.Televisión.Pública.(Argentina).ar",
    "TNTLatinAmerica.us": "Canal.TNT.(Argentina).ar",
    "TNTNovelas.us": "Canal.TNT.Novelas.(Argentina).ar",
}

mitv = collections.defaultdict(list)
for g in json.load(open(GUIDES, encoding="utf-8")):
    if g.get("channel") and g["site"] == "mi.tv":
        mitv[g["channel"]].append(g["site_id"])

canales, sin = {}, []
m3u = open(M3U, encoding="utf-8").read()
for tvg_id, nombre in re.findall(r'tvg-id="([^"]*)"[^\n]*,(.+)', m3u):
    base = tvg_id.split("@")[0]
    ids = mitv.get(base) or mitv.get(ALIAS.get(base, ""))
    # Preferimos la página argentina de mi.tv si el canal está en varios países.
    ids = sorted(ids or [], key=lambda s: not s.startswith("ar#"))
    if ids:
        canales[tvg_id] = {"nombre": nombre.strip(), "fuente": "mi.tv", "id": ids[0]}
        if base in EPGSHARE:
            canales[tvg_id]["respaldo"] = EPGSHARE[base]
    elif base in EPGSHARE:
        canales[tvg_id] = {"nombre": nombre.strip(), "fuente": "epgshare", "id": EPGSHARE[base]}
    else:
        sin.append(nombre.strip())

json.dump(canales, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{len(canales)} canales con guía -> {OUT}")
print(f"{len(sin)} sin guía: {', '.join(sin)}")
