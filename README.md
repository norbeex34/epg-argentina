# EPG Argentina

Guía de programación (XMLTV) para la lista de canales de Argentina de
[iptv-org](https://iptv-org.github.io/iptv/countries/ar.m3u). Se actualiza
sola todos los días con GitHub Actions.

## Uso

En tu reproductor (TiviMate, Kodi, Jellyfin...):

- **Lista M3U** (ya trae la guía enlazada):
  `https://raw.githubusercontent.com/norbeex34/epg-argentina/main/epg/ar_epg.m3u`
- **Guía EPG** (si tu reproductor la pide aparte):
  `https://raw.githubusercontent.com/norbeex34/epg-argentina/main/epg/guia.xml.gz`

## Cómo funciona

- `tools/grabar_epg.py` descarga 4 días de programación de **mi.tv** y, para
  los canales que mi.tv no tiene, de **epgshare01**. Escribe la guía con los
  mismos `tvg-id` que la lista, así el reproductor los enlaza solo.
- `epg/canales.json` dice qué fuente usa cada canal. Se regenera con
  `tools/generar_channels.py` si cambia la lista (necesita `ar.m3u` y el
  índice `https://iptv-org.github.io/api/guides.json`).
- `.github/workflows/actualizar-epg.yml` lo ejecuta cada día a las 06:00 UTC.
  También se puede lanzar a mano desde la pestaña *Actions*.

Unos 60 de los 209 canales tienen guía; el resto son canales locales que no
aparecen en ninguna fuente pública.
