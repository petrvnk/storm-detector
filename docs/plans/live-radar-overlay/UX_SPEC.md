# UX Spec – živý RainViewer overlay

> Stav dokumentu: UX/UI specifikace pro implementaci živého radarového overlaye v Radar Hail Risk kartě. Dokument je pouze specifikace; neimplementuje produktový kód, release ani změny Home Assistant konfigurace.

## 1. Produktový záměr

Uživatel má v jedné Home Assistant kartě rychle pochopit:

- zda je aktuální radarová aktivita v okolí domova;
- kde je domov vůči radarovým srážkám;
- kde jsou všechna backendem publikovaná bouřková jádra;
- které jádro řídí aktuální rizikový stav;
- jak starý je radarový snímek;
- že radarová aktivita není potvrzené krupobití.

Karta nesmí působit jako plnohodnotná meteorologická mapa. Je to glanceable Simple Home risk card s neinteraktivním radarovým modulem.

## 2. UX zásady

1. **Bezpečnost před efektem.** Silná radarová vizualizace nesmí vytvořit dojem potvrzených krup. Hail wording pouze při `evidence_kind` dovolujícím hail.
2. **Aktuálnost před kontinuitou.** Při stale/unavailable stavu je lepší prázdný compact fallback než hezky vypadající starý radar.
3. **Backend jako rozhodčí.** Frontend zobrazuje backendový kontrakt; nevybírá frame, nefetchuje RainViewer metadata a nevybírá selected core vzdálenostní heuristikou.
4. **Simple Home default.** Bez pan/zoom/play controls, bez hover-only detailů, bez velké mapy v clear/unavailable stavu.
5. **Fallback je normální stav.** Schematic renderer zůstává podporovaný, ne „error screen“.

## 3. Informační architektura karty

Výchozí karta pro radar storm/hail mode:

1. accent line / risk color;
2. hero icon + title + krátká message;
3. radar module;
4. 2–4 facts;
5. safety note.

Radar module obsahuje:

- neutral dark panel;
- RainViewer tile layer;
- 80 km monitoring radius;
- optional warning/urgent rings;
- home marker;
- secondary core markers;
- selected risk-driver marker/halo/label;
- timestamp/staleness label;
- visible RainViewer attribution;
- module-level safety note nebo krátké safety footer copy.

Facts doplňují mapu textově, aby informace nebyla závislá na barvě nebo hoveru.

## 4. Stavová matice

| Stav | Podmínka | Default UI | Live overlay? | Poznámka |
|---|---|---|---|---|
| Clear | `level=none`, nestale | compact clear | ne v `auto`; ano jen `always` + valid radar | Bez velké mapy pro Simple Home |
| Unavailable | `level=unavailable` nebo chybí data | compact unavailable | ne | Bez starých hodnot |
| Stale | `is_stale=true` nebo stale binary on | compact unavailable | ne | Žádné staré tiles, cores, ETA |
| Lightning-only | `evidence_kind=lightning_only` | lightning card + no-hail note | ne v `auto`; volitelně `always` | Nikdy „Možné kroupy“ |
| Radar storm | `evidence_kind=radar_storm` | storm hero + radar module | ano, pokud validní | Copy říká bouřka/jádro, ne kroupy |
| Radar hail | `evidence_kind=radar_hail` | hail-possible/high hero + radar module | ano, pokud validní | Hail wording jako možnost, ne potvrzení |
| Radar hail + lightning | `evidence_kind=radar_hail_with_lightning` | hail hero + radar module + lightning fact | ano, pokud validní | Lightning je doplňkový kontext |
| Overlay invalid | contract mismatch/error | schematic fallback | ne | Risk level zůstává stejný |
| Tile load fail | `<img>` error for current frame | schematic fallback + small notice | ne pro stejný frame | Risk level se nemění |
| Too many tiles | tile grid > hard cap | schematic fallback | ne | Performance ochrana |

## 5. Copy guidance

### 5.1 Hero title

Stávající title semantics zachovat:

- clear: `Klid`;
- unavailable/stale: `Bez aktuálních dat`;
- radar storm: `Bouřka v okolí`;
- lightning-only: `Blesky poblíž`;
- radar hail warning: `Možné kroupy`;
- urgent radar hail: `Vysoká možnost krup`;
- generic: `Počasí vyžaduje pozornost`.

Nepoužívat:

- `Kroupy potvrzeny`;
- `Kroupy padají`;
- `Hail confirmed`;
- jakýkoliv text odvozující potvrzené krupobití pouze z radarové vrstvy.

### 5.2 Radar module labely

Doporučené texty:

- module aria label: `Radarový snímek RainViewer s bouřkovými jádry v okolí domova`;
- selected label: `hlavní jádro`;
- selected detail: `Hlavní jádro {distance} km od {home_label}`;
- storm mode selected detail: `Bouřkové jádro {distance} km od {home_label}`;
- hail mode selected detail: `Jádro s možností krup {distance} km od {home_label}`;
- timestamp: `Radarový snímek {time} · stáří {age}`;
- attribution: `Weather data by RainViewer`;
- tile error notice: `Radarová vrstva se nepodařila načíst, zobrazuji schematický náhled.`;
- safety note: `Radarová aktivita není potvrzené krupobití · sledujte oficiální výstrahy.`

V češtině v UI preferovat „snímek“ před „měření“, protože RainViewer frame time nemusí být přesný čas všech zdrojových radarů v kompozitu.

### 5.3 Facts

Facts pod mapou mají preferovat 2–4 položky podle dostupnosti:

- `Nejbližší/hlavní jádro`: `{distance_km.toFixed(1)} km`;
- `Intenzita jádra`: `{max_dbz} dBZ`;
- `Plocha jádra`: `{area_km2.toFixed(1)} km²`;
- `Detekovaná jádra`: count renderovatelných cores;
- `Zobrazeno`: `X z N jader`, pokud render cap omezil publikovaná jádra;
- `Pohyb`: `Přibližuje se` / `Vzdaluje se`;
- `Příchod`: ETA pouze pokud backend říká approaching a ETA je validní;
- `Nejbližší blesk`: pouze pokud lightning source je current.

Nepoužívat ETA/facts ze stale state.

## 6. Visual hierarchy

### 6.1 Layer order

Odspodu nahoru:

1. neutral panel background;
2. RainViewer radar tiles;
3. 80 km monitoring radius;
4. optional warning/urgent rings;
5. home marker;
6. secondary core markers;
7. selected risk-driver halo;
8. selected risk-driver marker;
9. selected label/distance summary;
10. attribution + timestamp;
11. safety note.

### 6.2 Panel style

- dark/neutral background, aby radarová vrstva byla čitelná a nezaváděla další mapovou atribuci;
- tiles opacity přibližně 0.72–0.85;
- radius rings subtilní, ne dominantní;
- selected core je dominantní vůči secondary cores;
- urgent/hail accent smí zvýraznit vybrané jádro, ale nesmí nahradit textovou safety note.

### 6.3 Barvy core markerů

Doporučená semantika:

- near-watch/storm 45–49 dBZ: žlutá/amber s nižší saturací;
- watch 50–54 dBZ: amber/orange;
- warning 55–59 dBZ: orange;
- urgent 60+ dBZ: red;
- selected risk-driving core: barva podle aktuálního mode/accent + větší halo + vyšší z-index.

Barva sama o sobě není jediný nositel významu; facts a labels musí být srozumitelné samostatně.

## 7. All-core overlay behavior

Karta vykreslí všechna jádra z `radar_overlay.cores`, která jsou publikovaná a renderovatelná pro aktuální frame.

Renderable core:

- má validní `frame_time` shodný s `radar_overlay.frame.time`;
- má validní render pozici;
- není explicitně mimo viewport hard bounds;
- neporušuje cap DOM/tile/marker budget.

Marker pozice:

1. použít `render_latitude` / `render_longitude`;
2. pokud chybí, použít `centroid_latitude` / `centroid_longitude`;
3. pokud chybí, použít `latitude` / `longitude` jako poslední kompatibilní fallback.

Secondary core markers:

- průměr vizuálně alespoň 9 px na mobile;
- nižší opacity než selected;
- bez trvalých text labels na malém displeji;
- detaily přes facts/count, ne hover-only tooltip.

Pokud je publikováno více cores než renderer ukáže:

- selected core musí zůstat zahrnuté;
- facts zobrazí `Zobrazeno X z N jader`;
- UI nesmí potichu vytvořit dojem, že ostatní cores neexistují.

## 8. Selected-core UX semantics

Selected core je risk-driver z backend kontraktu.

Frontend musí používat:

- `radar_overlay.selected_core_id`;
- core `id` matching selected id;
- `selected: true`;
- volitelně `role: risk_driver`.

Frontend nesmí pro live overlay vybrat selected marker podle nejbližší vzdálenosti nebo podle pořadí v `storm_cores`.

Selected marker:

- halo 18–24 px;
- inner marker větší než secondary;
- nejvyšší z-index mezi core markery;
- label vždy viditelný nebo textově zastoupený pod mapou;
- pulse je povolený pouze pokud není `prefers-reduced-motion: reduce`;
- label nikdy netvrdí potvrzené krupobití.

Vzdálenost v copy:

- používá `distance_km`, tedy vzdálenost nejbližšího bodu komponenty k domovu;
- marker může být na centroidu, takže copy nemá implikovat, že bod markeru je přesně ve vzdálenosti textu.

Doporučený text: `Hlavní jádro {distance} km od Domov`.

## 9. Simple Home behavior

Default `radar_overlay: auto`:

- clear: kompaktní karta, bez radarové vrstvy;
- unavailable/stale: kompaktní karta, bez starých tiles/cores/ETA;
- storm/hail: radar module je viditelný;
- lightning-only: lightning UX a no-hail note, live overlay jen s explicitním `always`;
- žádné pan/zoom/play controls;
- žádné hover-only tooltipy;
- žádná sekundární mapa nebo OSM layer;
- radar module nemá přebít hero/facts, pouze dát kontext.

Config `radar_overlay: always`:

- může ukázat validní current RainViewer layer i bez cores;
- musí stále ukázat timestamp, attribution a safety note;
- nesmí ukázat live overlay při stale/unavailable.

Config `radar_overlay: off`:

- live overlay se nepoužije ani při validním kontraktu;
- schematic fallback zůstává primární radarový modul.

## 10. Mobile spec 320–390 px

Hard UX požadavky:

- žádný horizontální scroll;
- card padding a radar panel nesmí vyžadovat viewport širší než 320 px;
- radar module v jednom sloupci;
- facts pod modulem v jednom sloupci;
- min height radar module: 220 px;
- max default height radar module: 320 px;
- preferovaný aspect ratio: 1:1 pro velmi úzké šířky, 4:3 pokud je prostor;
- secondary marker min 9 px;
- selected halo 18–24 px;
- selected label krátký, např. `hlavní jádro`;
- timestamp a attribution se mohou zalomit, ale nesmí překrýt selected marker;
- safety note zůstává viditelná, ne pouze v tooltipu.

Layout doporučení:

```text
[hero icon] [title/message]
[radar module full width]
[timestamp + attribution]
[selected summary]
[facts, 1 column]
[safety note]
```

Na mobilu neukazovat secondary core text labels uvnitř mapy; ponechat markers + count fact.

## 11. Desktop/tablet behavior

- Radar module může být map + side summary ve dvou sloupcích, pokud šířka dovolí;
- facts mohou být 2 sloupce;
- selected summary může být vedle mapy nebo pod ní;
- stále bez pan/zoom/play controls;
- attribution a timestamp musí být viditelné i na větším layoutu, ne schované v rohu s nízkým kontrastem.

## 12. Loading, stale a error fallback

### 12.1 Loading/current update

Během běžného HA state update karta nemá ukazovat spinner místo starého obsahu, pokud state ještě nepřišel. Jakmile nový state přijde:

- valid current overlay: vykreslit live overlay;
- invalid/stale/unavailable: okamžitě skrýt live tiles/cores;
- staré tiles z předchozího frame nesmí zůstat v DOM, pokud aktuální state není OK.

### 12.2 Stale/unavailable

Při stale/unavailable:

- compact unavailable;
- bez RainViewer tiles;
- bez core markers;
- bez selected core distance;
- bez ETA;
- bez starých facts;
- copy: `Detekce dočasně není dostupná`;
- safety note může být v compact variantě vynechaná, pokud by zbytečně zvětšila kartu, ale karta nesmí tvrdit klid.

### 12.3 Tile load error

Když tile image failne pro jinak validní frame:

- fallback na schematic pro stejný frame;
- zobrazit malou zprávu: `Radarová vrstva se nepodařila načíst, zobrazuji schematický náhled.`;
- zachovat risk title/facts z HA state;
- nepřepisovat risk level ani evidence_kind;
- nepoužívat starý tile frame.

### 12.4 Contract mismatch

Když `radar_overlay.frame.time` neodpovídá `attrs.frame_time`, nebo core frame time nesedí:

- live overlay se nepoužije;
- schematic fallback je povolen, pokud current state není stale/unavailable;
- test/dev může logovat console warning;
- UI nesmí potichu zobrazit nesynchronizovaný tile/core overlay.

## 13. Accessibility

Radar module:

- semantic role/aria-label: `role="img"` na SVG nebo wrapperu, případně `aria-label="Radarový snímek RainViewer s bouřkovými jádry v okolí domova"`;
- decorative tile images: `alt=""` a `aria-hidden="true"`;
- core markers mohou být dekorativní, pokud selected/core facts textově popisují stav;
- selected summary musí být textově dostupné mimo hover;
- attribution link je focusovatelný a má visible focus;
- žádná důležitá informace pouze přes hover tooltip;
- keyboard uživatel nemusí nic ovládat, aby pochopil aktuální stav;
- kontrast textů a safety note musí odpovídat HA theme co nejlépe přes CSS variables.

Color/accessibility:

- nekomunikovat risk jen barvou markeru;
- selected core má i velikost/halo/label;
- secondary cores mají count fact;
- urgent stav nepoužívá blikání.

## 14. Reduced motion

Implementace musí respektovat:

```css
@media (prefers-reduced-motion: reduce) { ... }
```

Požadavky:

- vypnout selected-core pulse animation, nebo ji nahradit statickým halo;
- žádná tile animace;
- žádné blikání urgent markerů;
- žádné autoplay radar frame animation, protože feature je live current overlay, ne timeline.

## 15. Attribution a licence

Atribuce musí být viditelná přímo v radar modulu:

- text/link: `Weather data by RainViewer`;
- URL: `https://www.rainviewer.com/`;
- umístění: spodní okraj radar modulu nebo timestamp row;
- na mobilu se může zalomit pod timestamp, ale nesmí zmizet.

Docs wording pro README/navazující docs:

- RainViewer radar data and availability are provided under RainViewer's own terms;
- repository MIT license applies to this integration code, not to RainViewer data;
- live overlay loads RainViewer tile images in the browser for the displayed area;
- if RainViewer tiles are unavailable or blocked, the card falls back to the schematic radar view.

Český UI safety text:

- `Radarová aktivita není potvrzené krupobití · sledujte oficiální výstrahy.`

## 16. Privacy/security UX note

Uživatel má být v dokumentaci upozorněn, že live overlay přidává browser-side image requests na RainViewer pro tile okolí monitorované lokace. UI samotné nemusí zobrazovat dlouhý privacy text v kartě, ale README/docs batch ho má uvést.

Default cesta nepřidává žádnou další datovou doménu kromě RainViewer tiles a nepoužívá externí JS.

## 17. Acceptance checklist pro UX

- Live RainViewer layer je viditelná pouze při validním backend-driven kontraktu nebo explicitním `always` režimu a current datech.
- Frontend nefetchuje RainViewer metadata.
- Tile/core frame times musí matchovat; mismatch fallbackuje.
- 80 km monitoring radius je jasný.
- Optional warning/urgent rings jsou subtilní, ne matoucí.
- Home marker je čitelný.
- Všechna publikovaná/renderovatelná cores jsou zobrazená nebo je uvedený count cap.
- Selected risk-driver core je dominantní a řízené backendem.
- Selected marker používá `render_latitude`/`render_longitude`, defaultně centroid.
- Clear/unavailable/stale default zůstává compact.
- Simple Home nemá pan/zoom/play controls.
- Mobile 320–390 px je bez horizontálního scrollu; module height 220–320 px.
- RainViewer attribution je visible link v radar module.
- RainViewer data terms/availability jsou oddělené od MIT licence repozitáře.
- Accessibility: role/aria-label, decorative tile alt/aria-hidden, no hover-only info.
- Reduced motion zjemní/vypne selected pulse.
- Tile load errors fallbackují na schematic a nemění risk level.
- Stale/unavailable nikdy neukazuje staré tiles, cores, ETA ani selected core facts.
- Radarová aktivita není potvrzené krupobití; hail wording jen podle `evidence_kind`.

## 18. Handover pro coding agent

Implementuj UX podle této priority:

1. Nejdřív bezpečné gating/fallbacky: stale/unavailable, frame mismatch, no metadata fetch, config `auto|off|always`.
2. Potom live radar module: neutral panel, tiles, 80 km radius, home marker, all-core markers, selected marker/halo/label.
3. Potom polish: timestamp, attribution, safety note, facts/count cap, tile error notice.
4. Nakonec mobile/accessibility/reduced motion CSS a testy.

Testovací důkazy, které má implementace dodat:

- valid overlay renders RainViewer tile image URLs from backend template;
- no RainViewer metadata endpoint string/fetch path is used by frontend;
- all cores render and selected core is visually distinct;
- selected core is chosen by backend `selected_core_id`, not distance heuristic;
- stale/unavailable hides tiles, cores, ETA and old selected values;
- frame mismatch falls back;
- tile load failure falls back to schematic without changing risk state;
- attribution and safety note are present;
- lightning-only does not show hail wording;
- mobile CSS contains one-column facts/no-horizontal-scroll constraints;
- reduced-motion rule disables or reduces selected pulse.
