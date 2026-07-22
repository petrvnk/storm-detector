# Technical Design

> Stav dokumentu: architektura a produktové požadavky pro další feature po v0.0.5. Tento dokument je pouze návrh a handover; neimplementuje kód, nevydává release a nemění běžící Home Assistant.

**Feature:** Živá radarová vrstva s překryvem detekovaných bouřkových jader Radar Hail Risk.

**Cíl:** V custom Lovelace kartě nahradit čistě schematický radarový náhled reálnými RainViewer radarovými dlaždicemi pro stejný časový snímek, nad nimi zobrazit všechna publikovaná `storm_cores` a zvýraznit jádro, které řídí aktuální rizikový stav.

**Bezpečnostní princip:** Radarová bouřková aktivita není potvrzené krupobití. Hail wording se smí objevit jen tam, kde ho už dnes dovoluje `evidence_kind` a aktuální radarová evidence; samotná radarová vrstva ani zobrazení jádra nesmí tvrdit, že kroupy skutečně padají.

---

## 1. Problem Summary

Současná verze `v0.0.5` už umí detekovat více bouřkových jader z RainViewer radarových dat a custom karta vykresluje schematický kruhový náhled:

- karta `custom_components/radar_hail_risk/frontend/radar-hail-risk-card.js` čte atribut `storm_cores`, vykreslí všechna renderovatelná jádra jako body a jedno vybrané jádro zvýrazní;
- backend analyzuje RainViewer metadata a dlaždice v `custom_components/radar_hail_risk/rainviewer.py`;
- výchozí monitoring radius je 80 km (`DEFAULT_ANALYSIS_RADIUS_KM = 80`);
- riziková semantika je oddělena přes `level` a `evidence_kind` a blesky bez aktuální radarové podpory nesmí tvrdit kroupy;
- při stale radar datech backend záměrně zahazuje předchozí core hodnoty a publikuje fail-closed stav `unavailable` / stale místo falešně klidového stavu.

Uživatelský problém: schematický náhled říká, kde jsou jádra vůči domovu, ale neukazuje skutečný radarový kontext. Uživatel nevidí, zda je vybrané jádro součástí větší srážkové oblasti, zda jsou vedle něj další srážky, ani jestli sekundární jádra vizuálně odpovídají reálné radarové vrstvě. To snižuje důvěru v kartu a nutí uživatele otevírat externí radar.

Feature má proto zobrazit aktuální radarovou srážkovou vrstvu jako vizuální základ a na ni překrýt detekovaná jádra Radar Hail Risk. Klíčové není přidat obecnou mapovou aplikaci, ale udělat lokální, bezpečný a časově synchronizovaný radarový kontext pro existující risk card.

### Aktuální stav podle inspekce repozitáře

- Git stav: větev `main`, tag/describe `v0.0.5`, bez lokálních změn před vznikem tohoto dokumentu.
- Manifest i `pyproject.toml` deklarují verzi `0.0.5`.
- Integrace je Home Assistant custom integration s HACS metadata, minimální HA `2024.10.0`.
- Frontend karta je samostatný vanilla Web Component bez bundleru a bez JS runtime dependency.
- Frontend statická cesta je servírovaná přes `/radar_hail_risk` z `__init__.py`, takže karta se nepíše do `/config/www`.
- Backend pipeline:
  - `coordinator.py` získá lokaci z HA configu nebo entity;
  - stáhne RainViewer metadata a color lookup;
  - volá `analyze_recent_frames(...)` s `analysis_radius_km`, počtem snímků, zoomem, dBZ thresholdy a `min_core_pixels`;
  - publikuje výsledek přes hlavní level sensor a jeho atributy.
- `rainviewer.py`:
  - používá RainViewer metadata endpointy `/weather-maps-api/v1/radar` a `/weather-maps.json`;
  - skládá tile URL ve tvaru `{host}{path}/512/{z}/{x}/{y}/2/1_1.png`;
  - defaultně pracuje se 512px dlaždicemi a zoomem 7;
  - vybírá nejnovější validní analyzovaný frame jako user-facing current risk;
  - starší framy používá pro motion/trend, ne pro aktuální overlay;
  - `storm_cores` jsou kompaktní top-N souhrny komponent s `distance_km`, `bearing_degrees`, `latitude`, `longitude`, `centroid_latitude`, `centroid_longitude`, `area_km2`, `pixel_count`, `max_dbz`, `threshold_dbz`.
- Současná karta:
  - pro `clear` a `unavailable` ukazuje kompaktní stav bez detailů;
  - pro radarové režimy ukazuje schematický radar a facts;
  - vybrané jádro určuje aproximací podle vzdálenosti, což je pro mapový overlay málo explicitní;
  - stale stav záměrně schová předchozí hodnoty.
- Testy už pokrývají bezpečnostní wording, stale fallback, vykreslení všech `storm_cores` v aktuální kartě a zvýraznění vybraného jádra.

### Externí zdrojové omezení RainViewer

Podle aktuální RainViewer dokumentace:

- Weather Maps API vrací poslední přibližně 2 hodiny radarových frameů v 10minutových intervalech.
- Frame má `time` a `path`; `time` je čas generování mapového framu v UTC, ne garantovaný přesný čas všech zdrojových radarů uvnitř kompozitu.
- Tile URL používá `{host}{path}/{size}/{z}/{x}/{y}/{color}/{options}.png`.
- `size` může být 256 nebo 512.
- dokumentace uvádí max zoom 7 pro dlaždice;
- API je free pro osobní/vzdělávací použití, dostupnost dat není garantována;
- RainViewer žádá uvedení zdroje dat s odkazem na `https://www.rainviewer.com/`.

Důsledek pro feature: frontend nesmí nezávisle vybírat jiný RainViewer frame než backend, musí viditelně uvést atribuci a nesmí stavět bezpečnostní tvrzení na samotném vykreslení srážkové vrstvy.

## 2. Goal

### Produktový cíl

Uživatel v Home Assistant kartě vidí:

1. skutečnou RainViewer radarovou srážkovou vrstvu v okolí monitorované lokace;
2. domov / monitorovanou lokaci uprostřed náhledu;
3. 80km monitoring radius;
4. všechna backendem publikovaná bouřková jádra pro stejný radarový frame;
5. jedno jasně zvýrazněné risk-driving jádro, které odpovídá `selected_core_*` a řídí `level` / `evidence_kind`;
6. čas radarového snímku a stáří dat;
7. viditelnou atribuci RainViewer;
8. bezpečnostní poznámku, že radarová aktivita není potvrzené krupobití.

### Technický cíl

Zavést stabilní backend → frontend kontrakt pro radarový overlay tak, aby karta nepotřebovala sama volat RainViewer metadata API a nemohla zobrazit radarový frame z jiného času než core overlay.

### Scope

V rozsahu této feature:

- rozšířit datový kontrakt publikovaný hlavním `sensor.radar_hail_risk_level` atributem;
- vykreslit RainViewer tile mosaic v existující custom kartě;
- překrýt core markery v Web Mercator souřadnicích nad stejnou tile projekcí;
- zachovat aktuální schematický fallback;
- zachovat fail-closed stale/unavailable semantiku;
- přidat testy backend kontraktu, frontend renderingu, fallbacků a bezpečnostního wording;
- aktualizovat dokumentaci a příklad Lovelace karty až v implementačním PR/batchi.

### Non-goals

Mimo rozsah:

- veřejný release, tag, push, deploy nebo změna běžícího Home Assistantu;
- nová predikce krup, kalibrovaná pravděpodobnost krup nebo ground-truth dataset;
- obecná interaktivní mapa s panningem, zoomem, geocoderem a historií;
- animace posledních 2 hodin radarových snímků;
- zobrazení polygonů přesného tvaru radarových komponent; pro v0.0.6 stačí centroid/marker/halo nad reálnou radarovou vrstvou;
- integrace Open-Meteo nebo dalšího meteorologického zdroje do detekční cesty;
- automatické úpravy dashboardů, resources nebo automations v uživatelově Home Assistantu.

## 3. Assumptions

1. Další feature bude pravděpodobně vydaná jako `v0.0.6`, ale tento dokument samotný release nepřipravuje.
2. Monitorovaná lokace je stále jedna config entry / jedna lokace, typicky `hass.config` nebo `zone.home`.
3. 80km radius zůstává výchozí produktový rozsah. Pokud uživatel změní `analysis_radius_km`, overlay použije stejnou hodnotu jako backend analýza.
4. Pro první verzi overlaye stačí neinteraktivní lokální radarový viewport. Uživatel nepotřebuje ručně posouvat mapu.
5. Frontend karta poběží bez build pipeline a bez npm bundlingu, stejně jako současná karta.
6. RainViewer dlaždice lze v HA frontend zobrazovat jako běžné `<img>` / CSS image zdroje bez čtení pixelů v canvasu. Pokud konkrétní HA instance nebo síť externí obrázky blokuje, karta musí spadnout zpět na schematický náhled.
7. Projektový MIT license kryje kód repozitáře, nikoli práva k RainViewer radarovým datům. Atribuce a podmínky RainViewer se musí řešit samostatně.
8. Současný `storm_cores` atribut je kompatibilní kontrakt pro starou kartu. Nový overlay může přidat strukturovanější atribut, ale nesmí rozbít existující atributy.
9. Dlaždicový zoom pro live overlay má respektovat RainViewer dokumentovaný max native zoom 7. Současná option range v kódu dovoluje 6-9; pro overlay doporučuji clamp na 7 a otevřít samostatnou otázku, zda nesnížit i backend option maximum.
10. Core marker má pro vizuální umístění používat centroid komponenty, zatímco textová vzdálenost zůstává `distance_km` k nejbližšímu bodu komponenty vůči domovu. Tím se marker lépe trefí do srážkové oblasti a současně se nezmění riziková vzdálenost.

## 4. Proposed Solution

### Doporučená architektura

Použít existující vanilla custom card a přidat do ní lehký Web Mercator tile mosaic renderer pro RainViewer dlaždice. Backend přidá explicitní `radar_overlay` atribut s přesným frame kontraktem. Frontend vykreslí pouze dlaždice a core overlay pro tento backendem analyzovaný frame.

```text
RainViewer Weather Maps API
  -> backend fetch metadata + color table
  -> backend analyze newest valid frame + recent frames for motion
  -> backend publishes level sensor attrs:
       frame_time
       storm_cores
       selected_core_*
       radar_overlay { frame, viewport, cores, selected_core_id, attribution }
  -> existing custom card reads HA state only
       if radar_overlay.status == ok and synchronized:
           render RainViewer tile mosaic + core SVG/HTML overlay
       else:
           render current schematic or compact unavailable fallback
```

### Hlavní rozhodnutí

1. **Frontend nebude volat RainViewer metadata API.** Metadata a výběr framu patří backendu, protože právě backend rozhodl, která jádra a rizikový stav jsou aktuální.
2. **Frontend bude načítat pouze tile images pro backendem zvolený frame.** Tile URL template dostane z `radar_overlay.frame.tile_url_template`.
3. **Žádný Leaflet/OpenLayers dependency pro první verzi.** Potřebujeme lokální radar card, ne plnou mapovou aplikaci. Vanilla renderer má menší bundle, menší bezpečnostní plochu a zapadá do současného single-file card modelu.
4. **Žádná základní OSM mapa v první verzi.** Reálná požadovaná base layer je radarová srážková vrstva. Podklad bude neutrální tmavý grid/radius, aby odpadla OSM atribuce, další síťové požadavky a vizuální šum. OSM/Carto base map může být pozdější opt-in.
5. **Schematický renderer zůstane jako fallback.** Pokud chybí overlay kontrakt, selžou tiles, jsou data stale, nebo HA frontend blokuje externí obrázky, karta nesmí zůstat prázdná.

### Komponenty a odpovědnosti

#### Backend: `rainviewer.py`

Odpovědnosti:

- zachovat existující detekci jader;
- přidat do výsledku informace nutné pro overlay frame:
  - RainViewer `host`;
  - frame `path`;
  - frame `time`;
  - tile size, color scheme id, options, display/native zoom;
- generovat stabilní core IDs pro daný frame;
- explicitně označit risk-driving core (`selected: true`, `role: risk_driver`);
- garantovat, že vybrané jádro je v overlay `cores` i v případě, že by v běžném top-N seznamu bylo mimo limit;
- zachovat stávající `storm_cores` kompatibilní atribut.

Poznámka: v současném kódu `analyze_recent_frames` zná `metadata.host` a selected frame, ale `RadarAnalysis` je nepublikuje. Implementace má rozšířit dataclass nebo přidat pomocnou strukturu tak, aby `coordinator.py` nemusel znovu vybírat frame a riskovat drift.

#### Backend: `coordinator.py`

Odpovědnosti:

- sestavit `radar_overlay` pouze z aktuální, nestale radarové analýzy;
- vložit atribut do payloadu hlavního level sensoru;
- pokud je radar stale/unavailable/degraded bez analýzy, publikovat `radar_overlay.status` jako `stale`, `unavailable` nebo `degraded`, ale bez renderovatelných tile URL a core markerů;
- nepřepisovat bezpečnostní `level`, `evidence_kind`, `is_stale`, `source_status`;
- při stale radar datech zahodit overlay stejně jako dnes zahazuje core hodnoty.

#### Frontend: `radar-hail-risk-card.js`

Odpovědnosti:

- preferovat `attrs.radar_overlay` před starým schematickým výpočtem;
- ověřit synchronizaci:
  - `radar_overlay.status === "ok"`;
  - `radar_overlay.frame.time === attrs.frame_time`;
  - každý renderovaný core má stejné `frame_time`;
  - `source_status.radar === "ok"` a `is_stale !== true`;
- vypočítat tile grid okolo monitorované lokace pomocí Web Mercator projekce;
- vykreslit RainViewer tiles jako image layer;
- vykreslit core markery jako SVG/HTML overlay ve stejné projekci;
- udržet aktuální facts a bezpečnostní wording;
- při tile load error přepnout radar modul do degradovaného vizuálního fallbacku, nikoli měnit risk level;
- fallbackovat na současný schematic radar, pokud `radar_overlay` není použitelný.

#### Testy

Odpovědnosti:

- zabránit časové desynchronizaci;
- zabránit regresi bezpečnostních textů;
- chránit stale/unavailable fail-closed chování;
- chránit výkonové limity tile count / attribute size;
- ověřit, že karta nespouští vlastní RainViewer metadata fetch.

### Komunikace mezi částmi

Backend komunikuje s frontendem výhradně přes Home Assistant entity state attributes. Nezavádět websocket service, custom API endpoint ani dashboard mutation pro první verzi.

Důvod:

- karta už dnes čte všechna potřebná data z `sensor.radar_hail_risk_level` atributů;
- HA automaticky doručuje state změny do Lovelace;
- entity atributy jsou snadno testovatelné ve stávajících Node frontend testech;
- žádná další auth/security plocha.

### Proč tento přístup

- Minimalizuje změny v produktu i infrastruktuře.
- Řeší největší riziko feature: frame/core time mismatch.
- Zachovává offline/degraded fallback bez bezpečnostního regresu.
- Nezavádí těžkou mapovou knihovnu kvůli relativně malému lokálnímu viewportu.
- Je kompatibilní se současnou single-file kartou a testovacím stylem repozitáře.

## 5. Alternatives & Trade-offs

### Alternativa A: Frontend si sám stáhne RainViewer metadata a vybere nejnovější frame

**Výhody:** jednodušší backend změna, karta by mohla později animovat frame history.

**Nevýhody:** vysoké riziko desynchronizace. Backend může analyzovat frame `T`, zatímco frontend po refreshi metadata dostane frame `T+10min`; core markery by ležely nad jinou radarovou vrstvou. To je pro důvěru i bezpečnost nepřijatelné.

**Verdikt:** zamítnout pro první verzi. Frontend nesmí volat metadata API.

### Alternativa B: Leaflet nebo OpenLayers v custom kartě

**Výhody:** hotové slippy-map chování, pan/zoom, layer management, attribution control.

**Nevýhody:** nová dependency, větší bundle, nutnost vendoringu/licenční evidence, složitější HA card lifecycle, mobilní ovládání a výkon. Pokud by se použil CDN script, vzniká zbytečné security/SRI/CSP riziko.

**Verdikt:** odložit. Smysl má až pro budoucí detailní interaktivní mapu, ne pro Simple Home radar card.

### Alternativa C: Backend proxy / předkomponovaný PNG endpoint

Backend by ze stejných RainViewer tiles vytvořil jeden PNG/JPEG obraz s core overlay a karta by jen zobrazila `<img>`.

**Výhody:** žádný CORS problém ve frontend, přesná kontrola cache, může skrýt browser-side tile URL.

**Nevýhody:** výrazně více backend práce, CPU/memory, nový HA HTTP endpoint, cache invalidace, větší riziko blokování event loopu/Pillow pipeline, obtížnější interaktivita a responzivní overlay. Backend už dnes analyzuje radar a nemá se stát map tile serverem.

**Verdikt:** fallback architektura pouze pokud přímé `<img>` tiles selžou ve významné části HA instalací.

### Alternativa D: Native Home Assistant map card + `device_tracker` selected core

**Výhody:** žádný custom map renderer.

**Nevýhody:** native HA map nezobrazí RainViewer overlay ani všechna `storm_cores` bez dalších custom entity/tracker objektů. Dnes existuje jen disabled diagnostic tracker pro selected core.

**Verdikt:** nevhodné pro požadavek “actual radar precipitation data + all cores”.

### Alternativa E: Canvas rendering a vlastní pixel sampling ve frontend

**Výhody:** možnost efektů, blendingu a budoucího lokálního image processingu.

**Nevýhody:** vyžaduje CORS-clean images, větší CPU na mobilu, bezpečnostní a kompatibilní rizika. Backend už pixel sampling dělá.

**Verdikt:** zamítnout. Frontend má pouze zobrazovat, ne analyzovat.

### Doporučení

Implementovat **vanilla Web Mercator tile mosaic renderer** uvnitř stávající custom card, řízený backendovým `radar_overlay` atributem. Zachovat schematický fallback a nepřidávat mapovou knihovnu ani backend image proxy v první fázi.

## 6. Data Models / APIs / Contracts

### Stávající kontrakt, který se musí zachovat

Hlavní level sensor i po feature zachová minimálně tyto atributy:

```text
summary
evidence_kind
is_stale
source_status
frame_time
frame_age_seconds
selected_core_distance_km
selected_core_latitude
selected_core_longitude
selected_core_threshold_dbz
selected_core_max_dbz
selected_core_area_km2
selected_core_pixel_count
storm_cores
core_count
storm_motion_bearing
storm_motion_speed_kmh
storm_approaching
storm_eta_minutes
dbz_trend
distance_trend
confidence_score
confidence_level
```

### Nový backend atribut

Přidat nový atribut na hlavní level sensor:

```python
ATTR_RADAR_OVERLAY = "radar_overlay"
```

Hodnota je JSON-serializable dict. Doporučený tvar:

```json
{
  "schema_version": 1,
  "status": "ok",
  "provider": "RainViewer",
  "mode": "rainviewer_tile_mosaic",
  "attribution": {
    "label": "Weather data by RainViewer",
    "url": "https://www.rainviewer.com/"
  },
  "frame": {
    "time": 1784044800,
    "time_iso": "2026-07-14T12:00:00Z",
    "age_seconds": 120,
    "generated_time": 1784044860,
    "host": "https://tilecache.rainviewer.com",
    "path": "/v2/radar/1784044800",
    "tile_url_template": "https://tilecache.rainviewer.com/v2/radar/1784044800/512/{z}/{x}/{y}/2/1_1.png",
    "tile_size": 512,
    "display_zoom": 7,
    "max_native_zoom": 7,
    "color_scheme_id": 2,
    "options": "1_1"
  },
  "viewport": {
    "center_latitude": 49.9387,
    "center_longitude": 17.9026,
    "location_source": "hass.config",
    "radius_km": 80,
    "warning_radius_km": 25,
    "urgent_radius_km": 15
  },
  "thresholds": {
    "near_watch_dbz": 45,
    "watch_dbz": 50,
    "warning_dbz": 55,
    "urgent_dbz": 60,
    "min_core_pixels": 2
  },
  "selected_core_id": "1784044800:core:3",
  "cores": [
    {
      "id": "1784044800:core:3",
      "frame_time": 1784044800,
      "index": 3,
      "selected": true,
      "role": "risk_driver",
      "risk_band": "warning",
      "threshold_dbz": 55,
      "max_dbz": 57,
      "distance_km": 12.4,
      "bearing_degrees": 184.2,
      "latitude": 49.827000,
      "longitude": 17.895000,
      "centroid_latitude": 49.820500,
      "centroid_longitude": 17.906100,
      "render_latitude": 49.820500,
      "render_longitude": 17.906100,
      "area_km2": 18.7,
      "pixel_count": 12
    }
  ],
  "limits": {
    "core_count_total": 5,
    "core_count_rendered": 5,
    "core_limit": 12,
    "selected_core_forced_included": false
  }
}
```

### Povolené `radar_overlay.status`

```text
ok           - lze vykreslit tile mosaic i core overlay.
stale        - radarový frame je starší než stale timeout; nevykreslovat tiles ani cores.
unavailable  - chybí lokace, metadata, host/path, color lookup nebo žádný analyzovatelný frame.
degraded     - risk data mohou být publikovaná, ale vizuální overlay nemá kompletní frame kontrakt; použít fallback.
disabled     - volitelné budoucí nastavení vypne live overlay.
```

Při `status != "ok"` nesmí být publikována použitelná `tile_url_template` pro starý frame. Je lepší dát `frame: null` nebo frame bez URL než riskovat, že frontend omylem ukáže starý radar.

### Synchronizační invariants

Implementace musí dodržet:

1. `radar_overlay.frame.time == attrs.frame_time`.
2. `radar_overlay.frame.age_seconds == attrs.frame_age_seconds` nebo rozdíl maximálně 1 sekunda kvůli zaokrouhlení.
3. Každý `radar_overlay.cores[*].frame_time == radar_overlay.frame.time`.
4. Přesně jeden core má `selected: true`, pokud existuje `selected_core_id`.
5. `selected_core_id` ukazuje na existující core v `cores`.
6. Vybraný core odpovídá `selected_core_distance_km`, `selected_core_threshold_dbz`, `selected_core_max_dbz` v toleranci zaokrouhlení.
7. Frontend vykreslí overlay jen pokud všechny výše uvedené invarianty platí.
8. Frontend nesmí použít starý `radar_overlay` z předchozího renderu, pokud aktuální HA state říká stale/unavailable.

### Core position semantics

Každý core má dva typy pozice:

- `latitude` / `longitude`: nejbližší bod komponenty k monitorované lokaci; používá se pro rizikovou vzdálenost a kompatibilitu se současnými atributy.
- `centroid_latitude` / `centroid_longitude`: střed komponenty; používá se pro vizuální marker na reálné radarové vrstvě.
- `render_latitude` / `render_longitude`: explicitní pozice, kterou má použít frontend. Pro v0.0.6 nastavovat na centroid, fallback na nearest bod jen pokud centroid chybí.

Tím se oddělí “jak blízko je jádro” od “kde se má kreslit marker”.

### Frontend config additions

Rozšířit custom card config aditivně:

```yaml
type: custom:radar-hail-risk-card
title: Bouřky v okolí
radar_overlay: auto   # auto | off | always
home_label: Domov
```

Význam:

- `auto`: default; živý overlay jen v radarových storm/hail stavech, jinak compact clear/unavailable jako dnes.
- `off`: vždy používat současný schematic renderer.
- `always`: pokud jsou radarová data aktuální, zobrazit radarovou vrstvu i bez core risku; pro power users / debugging, ne pro Simple Home default.

Pro v0.0.6 není nutné přidávat UI editor; stačí YAML config.

### Tile projection contract

Frontend musí používat stejnou Web Mercator projekci jako backend:

```text
x_px = (lon + 180) / 360 * 2^z * tile_size
lat_rad = lat * pi / 180
y_px = (1 - asinh(tan(lat_rad)) / pi) / 2 * 2^z * tile_size
```

Tile grid:

- `display_zoom = min(radar_overlay.frame.display_zoom, radar_overlay.frame.max_native_zoom, 7)`;
- `tile_size = 512`;
- defaultně z=7 pro 80 km radius;
- spočítat center tile a tile span tak, aby viewport pokryl `radius_km` plus padding;
- hard cap: default max 9 tiles, absolutní max 25 tiles, jinak fallback na schematic a diagnostická poznámka v console/testu.

### Časová synchronizace mezi radar frame a core overlay

Přesný datový tok:

1. Coordinator začne update v čase `now_utc`.
2. Backend stáhne/cachuje RainViewer metadata.
3. `select_recent_frames(metadata, required_frames)` vrátí framy newest-to-oldest.
4. Backend analyzuje dostupné framy, ale pro user-facing stav vybere **nejnovější validní analyzovaný frame** `latest`.
5. `RadarAnalysis.frame_time = latest.frame_time`.
6. `RadarAnalysis.storm_cores = latest.storm_cores`.
7. Motion/trend mohou využít starší framy, ale nesmí změnit core list pro overlay.
8. Coordinator sestaví `radar_overlay.frame` ze stejného `latest.time`, `latest.path` a `metadata.host`, které byly použity pro analýzu.
9. Coordinator sestaví `radar_overlay.cores` výhradně z core komponent téhož `latest.frame_time`.
10. Home Assistant doručí nový state do custom karty.
11. Karta vykreslí tiles z `radar_overlay.frame.tile_url_template`; nezačne metadata fetch.
12. Karta promítne `radar_overlay.cores[*].render_latitude/render_longitude` stejnou projekcí na pixelové souřadnice tile mosaic.
13. Karta zobrazí timestamp `frame.time_iso` a `age_seconds`.

Zakázané chování:

- frontend nesmí “aktualizovat” tile path sám;
- frontend nesmí držet poslední ok tiles při stale state;
- frontend nesmí animovat historické RainViewer framy bez historických core listů pro každý frame;
- backend nesmí publikovat overlay URL, pokud `source_status.radar` není `ok`.

## 7. Implementation Notes

### Map/radar technologie a dependency choice

Doporučená volba pro v0.0.6:

- vanilla Web Component renderer v `radar-hail-risk-card.js`;
- Web Mercator helper funkce přímo ve frontend souboru;
- RainViewer XYZ tile images jako `<img>` nebo absolutně pozicované elementy;
- SVG overlay pro radius rings, home marker, core markers a labels;
- žádný Leaflet/OpenLayers, žádný CDN script, žádná npm build pipeline;
- žádný OSM base map v defaultu.

Tato volba je pragmatická, protože současná karta už je single-file custom element a požadovaný viewport je pevně centrovaný na jednu lokalitu.

### Backend poznámky

1. Přidat konstantu `ATTR_RADAR_OVERLAY` do `const.py`.
2. Rozšířit `RadarAnalysis` / `AnalyzedFrame` o `frame_path`, `frame_host`, případně `metadata_generated_time`.
3. Přidat helper pro bezpečnou tvorbu tile template:
   - akceptovat pouze `https://` host;
   - preferovat RainViewer host z metadata;
   - normalizovat path bez whitespace/control chars;
   - template má obsahovat pouze `{z}`, `{x}`, `{y}` placeholders.
4. Přidat helper pro overlay cores:
   - stabilní `id` z `frame_time`, indexu a zaokrouhlené pozice, nebo explicitního pořadí v latest frame;
   - `selected` flag podle `selected_core_*` dat, ne podle frontend vzdálenostní heuristiky;
   - `render_latitude/lon` = centroid, fallback nearest;
   - `risk_band` odvozený z thresholdů a distance gates;
   - core limit default 12, selected core forced-included.
5. V `coordinator.py` sestavit `radar_overlay` až po stale vyhodnocení. Pokud `radar_stale`, publikovat status `stale` bez renderovatelných tiles/cores.
6. Nechat existující `storm_cores` atribut pro backward compatibility. Nová karta může používat `radar_overlay.cores`; stará schema zůstane dostupná.
7. Drobný cleanup: `coordinator.py` má v jednom `normalize_optional_float(..., default=50.0)`, ale `_effective_config()` už mergeuje default 80. Při dotyku kódu sjednotit fallback na `DEFAULT_ANALYSIS_RADIUS_KM`, aby se starý 50km fallback nevrátil při budoucím refactoru.

### Frontend poznámky

1. V `render()` po načtení `attrs` vyhodnotit `overlay = this.validRadarOverlay(attrs, stale, source)`.
2. Pokud `overlay` existuje a mode je radarový, zavolat `this.liveRadar(overlay, mode, presentation)` místo `this.radar(...)`.
3. `validRadarOverlay` musí kontrolovat synchronizační invariants a status.
4. `liveRadar`:
   - spočítá Web Mercator px pro center a cores;
   - spočítá tile bounds;
   - vykreslí max 9 tile images defaultně;
   - nad ně přidá SVG s radius rings a markers;
   - zobrazí `Weather data by RainViewer` jako viditelný link;
   - zobrazí timestamp/stáří dat;
   - zachová safety note.
5. Tile image elementy:
   - `loading="lazy"`;
   - `decoding="async"`;
   - `referrerpolicy="no-referrer"` pokud HA/browser dovolí;
   - `alt=""` a `aria-hidden="true"`, protože vlastní `role="img"`/label patří celému radar modulu.
6. Pokud `onerror` na tiles překročí práh, nastavit interní `_radarTileErrorFrameTime` a příští render použít schematic fallback pro daný frame. Nesmí se změnit risk level.
7. Všechny texty escapeovat stejně jako současná karta. URL nevkládat z user configu; použít jen backend kontrakt po validaci.
8. Zachovat compact clear/unavailable. Simple Home default nemá ukazovat velkou mapu ve stavu `none`, pokud není `radar_overlay: always`.

### UX požadavky: Simple Home

Default karta má být “glanceable”:

- clear stav: kompaktní jako dnes, bez radarové vrstvy;
- unavailable/stale: kompaktní, bez posledních core hodnot a bez starých tiles;
- radar storm/watch/warning/urgent: hero + radar modul + 2-4 facts;
- lightning-only warning: neukazovat hail wording; pokud radar current bez core risku, defaultně zůstat u lightning UX a poznámky “Kroupy nejsou radarově potvrzené”;
- live overlay nesmí přidat ovládací prvky play/pause/pan/zoom v Simple Home defaultu;
- karta má pořád fungovat bez myši a bez hover tooltipů.

### UX požadavky: mobile

- Pro šířku 320-390 px musí být radar modul čitelný bez horizontálního scrollu.
- Doporučený aspect ratio mapy: 1:1 nebo 4:3 podle dostupné šířky; u současného card layoutu použít single-column na mobile.
- Minimální výška radar modulu: 220 px; maximální default výška: 320 px.
- Facts pod mapou ve 1 sloupci.
- Core markery minimálně 9 px tap/visual target pro secondary a 18-24 px halo pro selected.
- Text labely na mapě omezit: vždy home, selected core, RainViewer attribution; secondary core labels jen jako počet/fact mimo mapu.
- Žádné malé hover-only tooltips; detail selected core je v textu pod mapou.

### Vizuální hierarchie

Vrstvy odspodu nahoru:

1. card background / neutral dark panel;
2. RainViewer radar tile images, opacity cca 0.72-0.85 podle theme;
3. jemný 80km monitoring ring;
4. volitelně dashed warning/urgent rings 25/15 km, velmi nízká opacity;
5. home marker uprostřed;
6. secondary core halos/markers;
7. selected risk-driving core halo/pulse/marker;
8. selected label a distance summary;
9. attribution a timestamp;
10. safety note.

Core barvy:

```text
near-watch/storm 45-49 dBZ: žlutá / amber, nízká saturace
watch 50-54 dBZ: amber/orange
warning 55-59 dBZ: oranžová
urgent 60+ dBZ: červená
selected risk-driving core: barva podle aktuálního mode/accent, větší halo a vyšší z-index
```

Vybrané jádro:

- musí být největší a vizuálně dominantní;
- má mít halo/pulse, ale animace musí být respektovat `prefers-reduced-motion`;
- label používat “hlavní jádro”, nikoli “kroupy potvrzeny”;
- pokud `storm_approaching === true`, lze přidat jemnou šipku/trend badge, ale jen když backend ETA/approach považuje za spolehlivé;
- pokud `evidence_kind === radar_storm`, text zůstává “bouřkové jádro”, ne “kroupy”.

Secondary cores:

- malé markery, nižší opacity;
- všechny backendem renderované cores musí být vidět, pokud nejsou mimo viewport;
- překryvy řešit z-indexem a mírným rozptylem labels mimo marker, ne skrýváním core markerů;
- pokud je core count nad render cap, zobrazit fact “Zobrazeno 12 z N jader” a selected stále zahrnout.

### Attribution/licensing/CORS/cache/security

#### Attribution a licence

- Viditelně zobrazit: `Weather data by RainViewer` s linkem `https://www.rainviewer.com/`.
- Atribuce musí být v radar modulu, ne jen README.
- Pokud se později přidá OSM/Carto mapový podklad, musí přibýt samostatná OSM atribuce. V doporučené v0.0.6 variantě OSM nepoužívat.
- README / docs musí výslovně říkat, že RainViewer data mají vlastní podmínky a dostupnost není garantovaná.
- Projektový MIT license se vztahuje na kód, ne na radarová data.

#### CORS / CSP

- Používat image tags, ne canvas pixel reads. Tím se vyhneme CORS-clean požadavku.
- Nezavádět externí JS z CDN.
- Pokud HA instance nebo síť blokuje `https://tilecache.rainviewer.com`, karta musí zobrazit schematic fallback a safety note, nikoli prázdný panel.
- Backend proxy endpoint je až plán B, pokud se direct image loading ukáže jako prakticky nespolehlivý.

#### Cache

- Backend metadata TTL 120 s a color table TTL 24 h zachovat.
- Frontend nesmí metadata fetchovat.
- Tile URL obsahuje frame path/time; nepřidávat cache buster.
- Browser cache smí reuseovat tile images pro stejný frame.
- Nezobrazovat staré cached tiles, pokud aktuální HA state říká stale/unavailable; cache může existovat v browseru, ale karta je nesmí referencovat.
- Při jednom default radar modulu z=7 očekávat max 9 tile image requests na frame. Absolutní bezpečnostní cap 25.

#### Security

- `tile_url_template` generovat na backendu z RainViewer metadata, ne z user configu.
- Frontend ověří, že URL začíná `https://` a obsahuje jen očekávané `{z}/{x}/{y}` placeholdery; při invalid URL fallback.
- Textové hodnoty escapeovat.
- Nepoužívat `innerHTML` s neescapovanou URL ani uživatelskými texty.
- RainViewer tile requests mohou provozovateli zdroje odhalit mapové dlaždice kolem monitorované lokace. Dokumentace má uvést, že live overlay posílá další browser-side požadavky na RainViewer; backend už RainViewer kvůli analýze volá.
- Žádná data neposílat na jiné nové domény.

### Stale/unavailable/degraded fallbacks

| Situace | Backend stav | Frontend chování |
|---|---|---|
| Aktuální radar + cores | `radar_overlay.status=ok` | live radar overlay |
| Aktuální radar, žádné cores, `level=none` | `ok` nebo bez cores | Simple default compact clear; `always` může ukázat radar bez markerů |
| Lightning-only warning | radar může být ok/degraded | default lightning card, bez hail claim; radar overlay jen při explicitním `always` |
| Tile image load fail | backend ok | schematic fallback + nenápadná zpráva “Radarová vrstva se nepodařila načíst”; risk state beze změny |
| Metadata/tile path chybí | `unavailable/degraded` | schematic nebo compact unavailable podle risk state; žádný starý tile |
| Radar stale | `stale`, `is_stale=true` | compact unavailable; žádné cores, žádné ETA, žádné poslední tiles |
| Location invalid | `unavailable`, location error | compact unavailable, žádná mapa |
| Core/frame mismatch | kontrakt invalid | schematic fallback a console warning v dev/test; ne live overlay |
| Příliš mnoho tiles | kontrakt ok, frontend cap exceeded | schematic fallback; neblokovat kartu |

### Performance budgets

Backend:

- Žádné nové RainViewer metadata fetches kvůli frontend overlayi.
- Žádná nová backend image composition pipeline.
- `radar_overlay` sestavení do 5 ms pro běžný core list.
- Atribut `radar_overlay` do 10 KB typicky, hard budget 16 KB.
- Core render limit 12; selected forced-included.
- Zachovat existující per-update deadline 45 s pro radar analýzu; feature nesmí deadline prodloužit.

Frontend:

- Default z=7, 80 km radius: max 9 tile image requests na radar modul.
- Absolutní cap: 25 tile images; nad cap fallback.
- Žádný vlastní metadata fetch.
- DOM nodes pro radar modul pod 120.
- Synchronous render JS pod 50 ms na běžném mobilu / HA tablet; target pod 20 ms na desktopu.
- Decoded tile memory default pod cca 12 MB pro 9×512 RGBA tiles.
- Neanimovat radar tiles. Pulse animace selected marker musí být vypnutelná přes `prefers-reduced-motion`.
- Nepřerenderovávat mapu častěji než při HA state update nebo card resize.

## 8. Risks

1. **RainViewer usage terms pro distribuovanou HACS integraci.** Dokumentace říká personal/educational use. Pokud projekt míří k širšímu veřejnému použití, je nutné ověřit, zda použití odpovídá podmínkám.
2. **Max zoom konflikt.** RainViewer docs uvádí max zoom 7, zatímco stávající config dovoluje 6-9. Overlay má clampovat na 7; samostatně rozhodnout, zda upravit backend option spec.
3. **Browser-side privacy.** Backend už RainViewer volá, ale live overlay přidá tile requests z prohlížeče uživatele. To může odhalovat oblast zobrazení. Nutná dokumentace.
4. **CSP / síťové blokování externích obrázků.** Některé HA instalace mohou externí tile images blokovat. Schematic fallback je povinný.
5. **HA state attribute velikost.** Duplicita `storm_cores` a `radar_overlay.cores` může zvětšit state. Držet core cap a budget.
6. **Selected core explicitness.** Současná karta selected core odhaduje podle vzdálenosti. Pro přesný overlay je nutný backend `selected` flag; bez něj hrozí zvýraznění špatného jádra.
7. **Centroid vs nearest-point confusion.** Marker na centroidu může vizuálně ležet dál než textová vzdálenost k nejbližšímu bodu core. UI text musí říkat “hlavní jádro 12,4 km” bez implikace, že markerový střed je přesně 12,4 km.
8. **Radar frame time není přesný čas všech radarů.** RainViewer uvádí, že frame time je čas generování mapového framu, zatímco kompozit může obsahovat zdrojová data z různých časů. UI má říkat “Radarový snímek” / “stáří snímku”, ne přesný čas bouřky.
9. **Více karet v dashboardu násobí tile requests.** Dokumentovat a případně v budoucnu sdílet cache/session přes browser cache; pro v0.0.6 držet nízký tile count.
10. **Safety wording regressions.** Vizuálně silná radarová mapa může uživatele vést k tvrdším závěrům. Texty musí opakovat “možné” a “radarově indikované”, nikdy “potvrzené kroupy”.

### Open questions

1. Má být live radar overlay defaultně viditelný i ve stavu `watch` s near-watch 45-49 dBZ, nebo až od configured `watch_dbz`?
   - Doporučení: ano pro `radar_storm/watch`, protože produkt má ukazovat storm context, ale wording bez hail claimu.
2. Chce Petr do budoucna i OSM/Carto podklad pod RainViewer transparentními srážkami?
   - Doporučení pro v0.0.6: ne, jen radar + neutral grid.
3. Má karta zobrazit všechny fyzicky detekované komponenty, nebo “všechna publikovaná `storm_cores`” s capem?
   - Doporučení: všechna publikovaná renderovatelná cores s capem 12 a selected forced-included.
4. Má se snížit `CONF_RAINVIEWER_ZOOM` max z 9 na 7?
   - Doporučení: neblokovat feature, ale otevřít samostatný compatibility cleanup. Overlay vždy clampuje na 7.
5. Má backend přidat proxy endpoint, pokud direct image loading selže u testerů?
   - Doporučení: pouze po reálném důkazu problému.

## 9. Recommendation

Postavit feature jako malé, synchronizované rozšíření současné architektury:

- backend publikuje explicitní `radar_overlay` kontrakt pro přesně analyzovaný RainViewer frame;
- frontend karta používá tento kontrakt k vykreslení RainViewer tile mosaic a core overlay;
- žádný frontend metadata fetch, žádná nová mapová dependency, žádný backend image proxy v první verzi;
- schematický náhled zůstává fallback;
- safety semantika zůstává stejná: radarová aktivita není potvrzené krupobití, lightning-only není hail, stale radar nesmí ukazovat staré cores ani tiles.

Toto je nejmenší robustní řešení, které splní produktový požadavek a současně drží kompatibilitu s v0.0.5.

## 10. Handover for Coding Agent

### Co implementovat

Implementovat live radar overlay v existující integraci bez releasu/deploye:

1. nový backend atribut `radar_overlay` na level sensoru;
2. explicitní frame/core synchronizaci;
3. vanilla frontend tile mosaic renderer;
4. schematic fallback;
5. testy pro kontrakt, UX, safety a výkonové limity;
6. dokumentační update až v implementačním batchi.

### Navržené pořadí batchů

#### Batch 1: Backend contract RED/GREEN

Cíl: backend publikuje dostatečný a synchronizovaný overlay kontrakt.

Soubory:

- `custom_components/radar_hail_risk/const.py`
- `custom_components/radar_hail_risk/rainviewer.py`
- `custom_components/radar_hail_risk/coordinator.py`
- `custom_components/radar_hail_risk/sensor.py`
- nové nebo rozšířené testy v `tests/test_rainviewer_stage3.py`, `tests/test_stage5_coordinator_entities.py`, případně `tests/test_live_radar_overlay_contract.py`

Kroky:

1. Napsat failing test, že payload obsahuje `radar_overlay.status == "ok"` s frame time/path/host/tile template pro fake RainViewer metadata.
2. Napsat failing test, že `radar_overlay.frame.time == ATTR_FRAME_TIME` a všechny cores mají stejný `frame_time`.
3. Napsat failing test, že exactly one selected core exists and selected_core_id points to it.
4. Napsat failing test, že stale radar publikuje `radar_overlay.status == "stale"` bez tile URL a bez cores.
5. Implementovat constants/dataclass/helpery.
6. Sjednotit fallback `DEFAULT_ANALYSIS_RADIUS_KM`, pokud se dotknete dané části.
7. Spustit targeted pytest pro nové backend testy.

Edge cases:

- chybějící metadata host;
- invalid frame path;
- no analyzable frame;
- selected core mimo běžný core cap;
- near-watch core 45-49 dBZ;
- stale frame_age > stale timeout.

#### Batch 2: Frontend live overlay renderer RED/GREEN

Cíl: karta vykreslí live radar overlay jen při validním kontraktu.

Soubory:

- `custom_components/radar_hail_risk/frontend/radar-hail-risk-card.js`
- `tests/test_frontend_card.py`

Kroky:

1. Přidat failing Node test, že validní `radar_overlay` vytvoří tile image URLs z backend template.
2. Přidat failing test, že karta nevytváří žádný RainViewer metadata fetch / nepoužívá `api.rainviewer.com/public/weather-maps.json`.
3. Přidat failing test pro all core markers + selected marker nad live overlay.
4. Přidat failing test pro frame mismatch fallback na schematic.
5. Přidat failing test pro stale/unavailable hiding tiles and cores.
6. Implementovat Web Mercator helpers, tile grid, live overlay HTML/SVG.
7. Implementovat `radar_overlay: auto|off|always` config.
8. Zachovat starý schematic renderer jako fallback.
9. Spustit `pytest tests/test_frontend_card.py -q`.

Edge cases:

- missing centroid => fallback render position nearest lat/lon;
- invalid URL template;
- tile count cap exceeded;
- reduced motion preference;
- mobile media query.

#### Batch 3: UX, attribution, docs examples

Cíl: karta je bezpečná, čitelná a dokumentovaná.

Soubory:

- `README.md`
- `examples/radar-hail-risk-card.yaml`
- případně `examples/lovelace/weather-tab.yaml`
- `CHANGELOG.md` až v release batchi, ne v tomto architektonickém dokumentu bez implementace

Kroky:

1. Přidat viditelnou RainViewer atribuci do live overlay.
2. Přidat safety note: “Radarová aktivita není potvrzené krupobití” nebo ekvivalentní krátký text.
3. Dokumentovat browser-side RainViewer tile requests a fallback.
4. Aktualizovat příklad custom card o `radar_overlay: auto` pouze pokud je config explicitně potřeba.
5. Přidat test, že attribution text/link je v HTML při live overlay.
6. Přidat test, že lightning-only stále neobsahuje “Možné kroupy”.

#### Batch 4: Performance/security hardening

Cíl: feature nezhorší HA ani mobilní dashboard.

Soubory:

- frontend karta
- backend contract helpery
- testy podle potřeby

Kroky:

1. Přidat test tile count cap pro default 80 km / z=7.
2. Přidat test, že invalid/non-https tile template fallbackuje.
3. Přidat test attribute size/core cap na modelovém listu většího počtu cores.
4. Přidat test selected forced-included při core capu.
5. Spustit relevantní targeted testy a full test suite.
6. Spustit Ruff a compileall podle repozitářové praxe.

### Očekávané moduly/soubory

- `custom_components/radar_hail_risk/const.py` — nová konstanta atributu.
- `custom_components/radar_hail_risk/rainviewer.py` — frame metadata v analysis výsledku, tile template helper, overlay core summaries.
- `custom_components/radar_hail_risk/coordinator.py` — sestavení `radar_overlay` v payloadu.
- `custom_components/radar_hail_risk/sensor.py` — vystavení `radar_overlay` v `extra_state_attributes`.
- `custom_components/radar_hail_risk/frontend/radar-hail-risk-card.js` — live overlay renderer a fallback.
- `tests/test_frontend_card.py` — frontend rendering contract.
- `tests/test_live_radar_overlay_contract.py` nebo rozšíření stávajících backend testů — backend contract.
- `README.md` / examples — až po funkční implementaci a testech.

### Required interfaces/contracts

- `attrs.radar_overlay.schema_version == 1`
- `attrs.radar_overlay.status in {ok, stale, unavailable, degraded, disabled}`
- `attrs.radar_overlay.frame.time == attrs.frame_time` při `ok`
- `attrs.radar_overlay.frame.tile_url_template` s `{z}`, `{x}`, `{y}` placeholders při `ok`
- `attrs.radar_overlay.cores[*].frame_time == attrs.radar_overlay.frame.time`
- `attrs.radar_overlay.selected_core_id` ukazuje na core se `selected: true`
- `storm_cores` zůstává dostupný pro backward compatibility

### Edge cases to handle

- stale radar frame;
- no radar metadata;
- metadata fallback endpoint;
- no color lookup / no analyzed pixels;
- invalid location;
- lightning-only warning;
- selected core omitted by top-N cap;
- many cores in 80 km radius;
- invalid/missing centroid;
- external tile load blocked;
- mobile 320 px width;
- prefers-reduced-motion;
- frontend receives old state then new stale state.

### What to test

Backend:

- contract shape and JSON serializability;
- exact time sync;
- selected core explicitness;
- stale/unavailable contract clearing;
- source_status integration;
- RainViewer max zoom clamp for overlay;
- selected forced-included under core cap.

Frontend:

- live overlay renders tiles from backend template;
- no metadata fetch;
- all cores rendered;
- selected core visually distinct;
- attribution visible;
- stale/unavailable hides old values;
- frame mismatch fallback;
- lightning-only no hail claim;
- mobile CSS basics in generated HTML/CSS;
- invalid URL fallback.

Manual verification after implementation, without modifying production HA unless explicitly approved:

- run targeted pytest and full pytest;
- run Ruff;
- run compileall;
- optionally open a local/static fixture render or test HA instance only after explicit approval;
- do not tag, push, release, deploy, or mutate Petr’s Home Assistant as part of implementation.

### Measurable acceptance criteria

1. Hlavní level sensor má při aktuálním radarovém framu atribut `radar_overlay.status == "ok"`.
2. `radar_overlay.frame.time` přesně odpovídá `frame_time` a každý core v `radar_overlay.cores` má stejné `frame_time`.
3. Frontend karta nepoužívá RainViewer metadata API; tile URL vychází pouze z backend `tile_url_template`.
4. Při validním overlayi karta zobrazí reálné RainViewer radarové tiles, home marker, 80km radius a všechny renderované cores.
5. Přesně jedno risk-driving core je zvýrazněné a odpovídá `selected_core_*` atributům.
6. Viditelně se zobrazí atribuce `Weather data by RainViewer` s odkazem na RainViewer.
7. Safety text v kartě nebo radar modulu říká, že radarová aktivita není potvrzené krupobití / že jde o orientační radarové upozornění.
8. Lightning-only stav nikdy nezobrazí “Možné kroupy” ani `urgent` hail wording bez aktuální radarové podpory.
9. Stale/unavailable radar stav nezobrazí staré tiles, staré cores, ETA ani selected core hodnoty.
10. Pokud tile images selžou, karta spadne na schematický fallback a zachová risk state beze změny.
11. Default z=7 / 80 km viewport nevytvoří více než 9 tile image requests; absolutní cap je 25.
12. `radar_overlay` atribut je typicky pod 10 KB a v testu nepřekročí 16 KB.
13. Mobile šířka 320 px nemá horizontální scroll a facts se zalomí do jednoho sloupce.
14. Full test suite, frontend card tests a lint/compile checks projdou před jakýmkoliv release krokem.
15. Žádný implementační batch necommitne, nepushne, nevydá release a neupraví běžící Home Assistant bez explicitního souhlasu.
