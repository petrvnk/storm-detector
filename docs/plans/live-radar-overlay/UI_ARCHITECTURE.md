# UI Architecture – živý RainViewer overlay

> Stav dokumentu: implementační UX/UI architektura pro navazující frontend batch. Tento dokument je pouze handover; nemění produktový kód, testy, release ani běžící Home Assistant.

## 1. Účel a rozsah

Tento dokument definuje UI architekturu pro živý radarový modul v `custom_components/radar_hail_risk/frontend/radar-hail-risk-card.js`.

Cíl navazující implementace:

- zobrazit backendem vybranou RainViewer radarovou tile vrstvu;
- nad stejným časovým snímkem vykreslit všechna publikovaná/renderovatelná bouřková jádra;
- jednoznačně zvýraznit backendem vybrané risk-driving jádro;
- zachovat Simple Home jednoduchost, bezpečnostní wording a schematický fallback.

Mimo rozsah UI architektury:

- žádný frontend fetch RainViewer metadata endpointů;
- žádný Leaflet/OpenLayers/CDN jako default cesta;
- žádný backend proxy nebo image composition design jako default;
- žádné pan/zoom/play ovládání;
- žádná změna dashboardů, resources, automations, release procesu nebo HA konfigurace.

## 2. Zdroj pravdy a základní principy

Primární zdroj pravdy je backendový atribut `radar_overlay` na hlavním level sensoru. Frontend čte pouze Home Assistant entity state attributes, zejména:

- `evidence_kind`;
- `is_stale`;
- `source_status`;
- `frame_time` / `frame_age_seconds`;
- `selected_core_*` kompatibilní atributy;
- `storm_cores` pro starý schematic fallback;
- `radar_overlay` pro live tile overlay.

Frontend nesmí:

- volat RainViewer metadata API (`/weather-maps-api/v1/radar`, `/weather-maps.json` ani ekvivalenty);
- sám vybírat novější RainViewer frame;
- držet poslední OK tiles/cores při aktuálním stale/unavailable stavu;
- dopočítávat selected core vzdálenostní heuristikou pro live overlay.

Frontend smí:

- načíst pouze konkrétní tile image URL odvozené z backendem dodaného `radar_overlay.frame.tile_url_template`;
- validovat kontrakt před renderem;
- fallbackovat na existující schematic renderer;
- zobrazit diagnostickou nenápadnou zprávu u tile load failure bez změny risk levelu.

Bezpečnostní princip: radarová aktivita není potvrzené krupobití. Hail wording je povolený pouze tam, kde ho už dovoluje `evidence_kind`; samotná radarová mapa ani core marker nesmí tvrdit, že kroupy skutečně padají.

## 3. Komponentová struktura v existující Web Component kartě

Zachovat single-file vanilla Web Component. Navržené interní části jsou metody/sekce téhož souboru, ne nové runtime dependency.

### 3.1 Render orchestration

Odpovědnost: současná metoda `render()` zůstává kořenový orchestrátor.

Doporučené pořadí:

1. načíst hlavní level state a atributy;
2. vyhodnotit `stale`, `source_status`, `evidence_kind`, `level`;
3. určit display mode přes stávající `displayMode(...)`;
4. pro `clear` a `unavailable` ponechat compact card, pokud config není `radar_overlay: always` a není validní current radar;
5. sestavit facts a presentation;
6. zavolat overlay validator;
7. vybrat live renderer nebo schematic fallback;
8. vyrenderovat hero, radar modul, facts, safety note.

### 3.2 Overlay config resolver

Doplnit aditivní config:

```yaml
type: custom:radar-hail-risk-card
radar_overlay: auto   # auto | off | always
home_label: Domov
```

Chování:

- `auto` default: live overlay jen pro aktuální radarové storm/hail režimy (`radar_storm`, `radar_hail`, `radar_hail_with_lightning`) a ne pro compact clear/unavailable;
- `off`: vždy používat současný schematic renderer;
- `always`: pokud je `radar_overlay.status == ok` a data jsou nestale, ukázat live radar modul i bez core risku; vhodné pro power users/debugging, ne pro Simple Home default.

Resolver musí vracet jeden z režimů:

- `disabled_by_config`;
- `compact_only`;
- `eligible_for_live_overlay`;
- `force_live_overlay_if_valid`.

### 3.3 Contract validator: `validRadarOverlay(attrs, mode, stale, source, config)`

Odpovědnost: rozhodnout, zda lze bezpečně vykreslit live overlay.

Validator má kontrolovat:

- `attrs.radar_overlay` je objekt;
- `schema_version === 1`;
- `status === "ok"`;
- `source_status.radar === "ok"`;
- `attrs.is_stale !== true` a stale binary sensor není `on`;
- `radar_overlay.frame` existuje;
- `radar_overlay.frame.time === attrs.frame_time`;
- každý renderovaný core má `frame_time === radar_overlay.frame.time`;
- `tile_url_template` je HTTPS URL template s očekávanými `{z}`, `{x}`, `{y}` placeholdery;
- `frame.display_zoom` je clampnutelný na `<= max_native_zoom` a `<= 7`;
- `viewport.center_latitude`, `viewport.center_longitude`, `viewport.radius_km` jsou validní finite numbers;
- `selected_core_id`, pokud existuje, ukazuje na přesně jeden core se `selected: true`;
- nejsou potřeba RainViewer metadata navíc.

Pokud validace selže, výsledek je `null` + fallback reason pro interní debug/console test. UI nesmí ukázat starý live overlay.

### 3.4 Live renderer: `liveRadar(overlay, context)`

Odpovědnost: vykreslit jeden neinteraktivní radarový modul.

Vstupy:

- validovaný `overlay`;
- presentation/accent podle risk mode;
- selected core summary/facts;
- approaching/receding/ETA kontext;
- card config (`home_label`, overlay mode).

Výstup: HTML string s radar modulem a bezpečnými escaped texty.

Renderer nesmí měnit risk level ani rozhodovat, které jádro řídí risk. To je pouze backendový kontrakt.

### 3.5 Projection helpers

Implementovat malé helpery uvnitř frontend souboru:

- `projectWebMercator(lat, lon, zoom, tileSize)`;
- `tileBoundsForViewport(centerPx, radiusKm, lat, zoom, tileSize, maxTiles)`;
- `pointForLatLon(lat, lon, tileOriginPx, viewportPx)`;
- `radiusPixels(radiusKm, centerLat, zoom, tileSize)`.

Použít Web Mercator vzorec z architektonického dokumentu. Zoom pro overlay:

```text
display_zoom = min(frame.display_zoom, frame.max_native_zoom, 7)
tile_size = frame.tile_size || 512
```

Tile budget:

- target/default: max 9 tile image requests pro 80 km radius při z=7;
- hard cap: 25 tiles;
- pokud výpočet přesáhne hard cap, live renderer fallbackuje na schematic.

### 3.6 Tile layer renderer

Odpovědnost: absolutně/relativně pozicované image tiles tvoří spodní live radarovou vrstvu.

Požadavky na `<img>`:

- `src` vznikne pouze nahrazením `{z}`, `{x}`, `{y}` v backend template;
- `loading="lazy"`;
- `decoding="async"`;
- `referrerpolicy="no-referrer"`, pokud HA/browser dovolí;
- `alt=""`;
- `aria-hidden="true"`;
- žádný canvas pixel read.

Tile load error:

- první chyba nastaví interní stav pro daný `frame.time`, např. `_radarTileErrorFrameTime`;
- další render pro stejný frame použije schematic fallback;
- zobrazit nenápadný text typu „Radarová vrstva se nepodařila načíst“;
- risk level, facts a safety wording zůstanou podle HA state.

### 3.7 SVG/HTML overlay renderer

Vrstva nad tiles obsahuje:

1. 80 km monitoring ring podle `viewport.radius_km`;
2. volitelné warning/urgent rings (`warning_radius_km`, `urgent_radius_km`) s nízkou opacitou;
3. home marker uprostřed;
4. secondary core markers pro všechna publikovaná/renderovatelná jádra;
5. selected risk-driver marker/halo/label;
6. timestamp a attribution;
7. safety note.

Doporučení: radius rings a markers vykreslit jako SVG nad tile mosaic, protože to drží DOM nízko a dobře funguje pro testy. Textové facts mohou zůstat běžné HTML mimo SVG.

### 3.8 Schematic fallback renderer

Stávající `radar(...)` schematic renderer zůstává součástí karty.

Použít ho, když:

- `radar_overlay` chybí;
- config je `radar_overlay: off`;
- overlay kontrakt je invalidní;
- tile grid přesáhne hard cap;
- tile image loading selže;
- frontend obdrží frame/core mismatch;
- live overlay je v Simple Home `auto` neeligible, ale current risk stále vyžaduje radar context.

Schematic fallback nesmí zobrazit staré core hodnoty při stale/unavailable. Compact unavailable má stále vyhrát nad schematem, stejně jako dnes.

## 4. Datový tok

```text
Home Assistant state update
  -> RadarHailRiskCard.render()
  -> read attrs + level + stale binary sensor
  -> displayMode(level, evidence_kind, stale)
  -> overlay config resolver
  -> validRadarOverlay(attrs, mode, stale, source, config)
      -> null: compact/schematic fallback
      -> valid overlay: liveRadar(overlay, context)
  -> shadowRoot.innerHTML update
  -> tile onerror can mark frame as tile-error
  -> next render falls back to schematic for that frame
```

Důležité invarianty:

- tile/core frame times musí odpovídat (`radar_overlay.frame.time == attrs.frame_time` a `core.frame_time == frame.time`);
- frontend nevytváří žádný RainViewer metadata fetch;
- selected core je řízený backendem, ne frontend distance heuristikou;
- schematic zůstává fallback;
- stale/unavailable stav nikdy neukazuje staré tiles ani staré cores.

## 5. All-core overlay a selected-core semantika

### 5.1 All-core overlay

Live overlay vykresluje všechna jádra v `radar_overlay.cores`, která jsou renderovatelná:

- finite `render_latitude` / `render_longitude`, nebo fallback `centroid_latitude` / `centroid_longitude`, nebo až poslední fallback `latitude` / `longitude`;
- `frame_time` odpovídá aktuálnímu overlay framu;
- core leží v rozumných zeměpisných mezích;
- core je ve viewportu nebo na hraně viewportu po aplikaci paddingu.

Pokud backend publikuje `limits.core_count_total > limits.core_count_rendered`, UI má zobrazit fact „Zobrazeno X z N jader“. Selected core musí být vykreslený, pokud je v `cores` a má validní render pozici.

Secondary markers:

- malé, nižší z-index/opacity;
- bez hover-only detailu;
- typicky bez labelu přímo na mapě na mobilu;
- nesmí skrývat selected marker.

### 5.2 Selected risk-driver hierarchy

Selected core je určený backendovým kontraktem:

- `radar_overlay.selected_core_id`;
- core se stejným `id`;
- `selected: true`;
- `role: "risk_driver"`.

Frontend nesmí pro live overlay vybrat „nejbližší“ core podle `selected_core_distance_km`. Vzdálenostní heuristika smí zůstat pouze ve schematic fallbacku pro backward compatibility.

Marker pozice:

- primárně `render_latitude` / `render_longitude`;
- backend pro v0.0.6 nastaví render pozici na centroid komponenty;
- fallback na centroid, pak nearest-point `latitude` / `longitude` pouze kvůli kompatibilitě;
- textová vzdálenost zůstává `distance_km`, tedy vzdálenost nejbližšího bodu komponenty od domova.

Vizuální priorita:

- selected marker je největší a nejvýš ve stacku;
- má halo a volitelný pulse;
- label používá „hlavní jádro“ nebo „risk-driving jádro“, ne „potvrzené kroupy“;
- pokud `evidence_kind === radar_storm`, text zůstává bouřkový, ne krupobitný.

## 6. Layer hierarchy

Vrstvy odspodu nahoru:

1. neutral card/panel background;
2. RainViewer tile images s opacitou přibližně 0.72–0.85;
3. 80 km monitoring radius;
4. volitelné warning/urgent rings;
5. home marker;
6. secondary core markers;
7. selected risk-driver halo/marker;
8. selected label/distance summary;
9. attribution a timestamp;
10. safety note.

Neutral panel je záměrně bez OSM base mapy. Pokud se někdy přidá mapový podklad, bude to samostatný opt-in design s vlastní atribucí.

## 7. Simple Home rozhodovací pravidla

Simple Home default (`radar_overlay: auto`) má být glanceable:

- `clear`: compact card bez live overlaye;
- `unavailable`/`stale`: compact unavailable, bez starých tiles/cores/ETA;
- `lightning_only`: lightning UX, bez hail wording; live overlay jen při explicitním `always` a validním current radar overlayi;
- `radar_storm`, `radar_hail`, `radar_hail_with_lightning`: hero + radar modul + 2–4 facts;
- žádné pan/zoom/play controls;
- žádná závislost na hoveru nebo myši.

Pokud `radar_overlay: always`, karta může ukázat live radar bez core markerů ve stavu current radar/no cores, ale stále musí zobrazit bezpečnostní poznámku a atribuci.

## 8. Mobile a responsive architektura

Požadavky pro šířky 320–390 px:

- žádný horizontální scroll;
- radar modul v jednom sloupci;
- facts pod mapou v jednom sloupci;
- min výška radar modulu 220 px;
- max default výška 320 px;
- aspect ratio 1:1 nebo 4:3 podle šířky karty;
- secondary marker minimálně 9 px vizuální/tap target;
- selected halo 18–24 px;
- home label a selected label zůstávají čitelné;
- secondary labels se na mobilu typicky přesunou do facts/count summary.

CSS má zůstat lokální v komponentě. Nepřidávat globální styly ani build pipeline.

## 9. Accessibility a reduced motion

Radar modul jako celek:

- má mít semantic `role="img"` nebo ekvivalentní region semantics;
- má mít `aria-label` popisující mapu, např. „Radarový snímek RainViewer s bouřkovými jádry v okolí domova“;
- tile images jsou dekorativní: `alt=""` a `aria-hidden="true"`;
- facts a selected summary obsahují informace dostupné bez hoveru;
- karta musí být srozumitelná bez barev samotných: text/facts doplňují barvy;
- nesmí vyžadovat keyboard interaction pro základní čtení;
- pokud existuje focusovatelný attribution link, musí mít viditelný focus outline.

Reduced motion:

- respektovat `@media (prefers-reduced-motion: reduce)`;
- vypnout nebo výrazně zjemnit selected-core pulse;
- neanimovat RainViewer tiles;
- nepoužívat blikání pro urgent stav.

## 10. Fallback rules

| Situace | Live renderer | UI výsledek |
|---|---|---|
| Validní current radar + radar storm/hail mode | použít | live RainViewer overlay + cores |
| Validní current radar + no cores + `radar_overlay: auto` + clear | nepoužít | compact clear |
| Validní current radar + no cores + `radar_overlay: always` | použít | live radar bez core markerů |
| `radar_overlay.status != ok` | nepoužít | schematic nebo compact podle mode |
| `is_stale=true` / stale binary on | nepoužít | compact unavailable, žádné staré tiles/cores |
| frame/core time mismatch | nepoužít | schematic fallback + dev/test warning |
| invalid/non-HTTPS tile template | nepoužít | schematic fallback |
| tile load error | příští render nepoužít | schematic fallback + nenápadný error text |
| tile count > hard cap | nepoužít | schematic fallback |
| Lightning-only warning | defaultně nepoužít | lightning UX + „Kroupy nejsou radarově potvrzené“ |

## 11. Attribution, licence, privacy a security

UI musí viditelně zobrazit RainViewer atribuci přímo v radar modulu:

- label: `Weather data by RainViewer` nebo český ekvivalent s názvem RainViewer;
- URL: `https://www.rainviewer.com/`;
- link musí být viditelný bez hoveru a neztratit se na mobilu.

Dokumentace k feature má opakovat:

- RainViewer data terms a dostupnost jsou samostatné od MIT licence repozitáře;
- MIT licence kryje kód projektu, ne radarová data;
- live overlay přidá browser-side image requests na RainViewer tile host;
- žádná nová doména kromě RainViewer tiles nemá být přidána v default cestě.

Security pravidla pro frontend:

- URL template pochází z backendového kontraktu, ne z user configu;
- validovat HTTPS a placeholdery;
- texty escapovat;
- nečíst tiles přes canvas;
- nepřidávat externí JS/CDN;
- fallbackovat bezpečně při chybě.

## 12. Performance budget

Frontend budget:

- default 80 km / z=7: max 9 tile images;
- hard cap 25 tile images;
- DOM nodes radar modulu pod 120;
- synchronous render target pod 50 ms na běžném mobilu;
- decoded tile memory default pod cca 12 MB pro 9×512 RGBA tiles;
- žádný metadata fetch;
- žádná tile animace;
- rerender pouze při HA state update, relevantní resize nebo tile-error state.

Pokud budget nelze splnit, implementace má fallbackovat na schematic a neblokovat zbytek karty.

## 13. Handover pro coding agent

Implementovat v tomto pořadí:

1. Přidat testy pro `radar_overlay: auto|off|always` gating, no metadata fetch, valid frame/core sync a stale hiding.
2. Přidat `validRadarOverlay(...)` a URL/frame/core validator.
3. Přidat Web Mercator helpery a tile grid s capem.
4. Přidat `liveRadar(...)` renderer s tile layerem, SVG rings/markers, timestampem, attribution a safety note.
5. Přepojit `render()` tak, aby live renderer byl preferovaný jen při validním kontraktu a schematic zůstal fallback.
6. Doplnit mobile CSS, accessibility labely a reduced-motion pravidla.
7. Ověřit `pytest tests/test_frontend_card.py -q` a relevantní backend kontrakt testy.

Očekávaný hlavní soubor:

- `custom_components/radar_hail_risk/frontend/radar-hail-risk-card.js`.

Očekávané testy:

- `tests/test_frontend_card.py` pro HTML/CSS contract a safety wording;
- backend contract testy z B1 pro `radar_overlay` shape a stale clearing.

Edge cases k pokrytí:

- missing overlay;
- invalid schema/status;
- stale current state after previous OK state;
- invalid/non-HTTPS tile template;
- frame mismatch;
- selected core missing or duplicate;
- selected core omitted by render cap;
- no centroid;
- too many tiles;
- tile load fail;
- lightning-only evidence;
- mobile 320 px;
- reduced motion.

## 14. Acceptance checklist pro tento UI design

- Live RainViewer layer je backend-driven a frontend nefetchuje RainViewer metadata.
- Tile/core frame times musí matchovat před live renderem.
- All-core overlay vykresluje všechna publikovaná/renderovatelná cores.
- Selected risk-driver hierarchy je řízená backendovým `selected_core_id`/`selected`, ne frontend distance heuristikou.
- Marker selected core používá `render_latitude`/`render_longitude`, defaultně centroid.
- Simple Home default zůstává compact clear/unavailable a bez controls.
- Mobile 320–390 px nemá horizontální scroll.
- Attribution RainViewer je viditelná v radar modulu.
- Accessibility a reduced motion jsou explicitní.
- Stale/loading/error fallback nikdy neukazuje staré tiles/cores.
- Schematic renderer zůstává fallback.
- Radarová aktivita není potvrzené krupobití.
