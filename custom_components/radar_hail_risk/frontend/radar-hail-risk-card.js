class RadarHailRiskCard extends HTMLElement {
  static getStubConfig() {
    return {
      type: 'custom:radar-hail-risk-card',
      title: 'Bouřky v okolí',
      level_entity: 'sensor.radar_hail_risk_level',
      summary_entity: 'sensor.radar_hail_risk_summary',
      max_dbz_entity: 'sensor.radar_hail_risk_max_dbz',
      core_distance_entity: 'sensor.radar_hail_risk_core_distance',
      lightning_distance_entity: 'sensor.radar_hail_risk_lightning_distance',
      active_entity: 'binary_sensor.radar_hail_risk_active',
      stale_entity: 'binary_sensor.radar_hail_risk_data_stale',
    };
  }

  setConfig(config) {
    if (!config) throw new Error('Invalid configuration');
    const radarOverlay = ['auto', 'off', 'always'].includes(config.radar_overlay)
      ? config.radar_overlay
      : 'auto';
    this.config = {
      title: 'Bouřky v okolí',
      level_entity: 'sensor.radar_hail_risk_level',
      summary_entity: 'sensor.radar_hail_risk_summary',
      max_dbz_entity: 'sensor.radar_hail_risk_max_dbz',
      core_distance_entity: 'sensor.radar_hail_risk_core_distance',
      lightning_distance_entity: 'sensor.radar_hail_risk_lightning_distance',
      active_entity: 'binary_sensor.radar_hail_risk_active',
      stale_entity: 'binary_sensor.radar_hail_risk_data_stale',
      home_label: 'Domov',
      radar_overlay: 'auto',
      ...config,
      radar_overlay: radarOverlay,
    };
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return this._cardSize || 1;
  }

  render() {
    if (!this.shadowRoot || !this._hass || !this.config) return;

    const state = this.state(this.config.level_entity);
    const level = this.levelValue(state?.state);
    const attrs = state?.attributes || {};
    const source = attrs.source_status || {};
    const stale = this.state(this.config.stale_entity)?.state === 'on' || attrs.is_stale === true;
    const evidence = String(attrs.evidence_kind || 'none').toLowerCase();
    const mode = this.displayMode(level, evidence, stale);
    const presentation = this.presentation(mode);
    const overlay = this.validRadarOverlay(attrs, stale, source);
    const liveOverlayEligible = this.liveOverlayEligible(evidence, overlay);
    const tileError = liveOverlayEligible
      && this._radarTileErrorFrameTime === overlay.frame.time;
    const liveRadar = liveOverlayEligible
      ? this.liveRadar(overlay)
      : null;

    if (mode === 'unavailable' || (mode === 'clear' && !liveRadar)) {
      this._cardSize = 1;
      this.shadowRoot.innerHTML = this.compactCard(presentation, mode);
      return;
    }

    const radarCurrent = source.radar === 'ok' && !stale;
    const lightningCurrent = source.lightning === 'ok' && !stale;
    const coreDistance = radarCurrent
      ? this.number(
          this.state(this.config.core_distance_entity)?.state ??
            attrs.selected_core_distance_km ??
            attrs.core_distance_km,
        )
      : null;
    const stormCores = Array.isArray(attrs.storm_cores) ? attrs.storm_cores : [];
    const selectedCore = Number.isFinite(coreDistance)
      ? stormCores.reduce((best, core) => {
          const distance = this.number(core?.distance_km);
          if (!Number.isFinite(distance)) return best;
          if (!best) return core;
          const bestDistance = this.number(best.distance_km);
          return Math.abs(distance - coreDistance) < Math.abs(bestDistance - coreDistance) ? core : best;
        }, null)
      : null;
    const coreBearing = this.number(selectedCore?.bearing_degrees);
    const renderableCores = stormCores.filter(
      (core) => Number.isFinite(this.number(core?.distance_km)) && Number.isFinite(this.number(core?.bearing_degrees)),
    );
    const lightningDistance = lightningCurrent
      ? this.number(
          this.state(this.config.lightning_distance_entity)?.state ?? attrs.lightning_distance_km,
        )
      : null;
    const approaching = attrs.storm_approaching === true;
    const receding = attrs.distance_trend === 'receding';
    const eta = approaching ? this.number(attrs.storm_eta_minutes) : null;
    const coreMaxDbz = radarCurrent
      ? this.number(
          attrs.selected_core_max_dbz ?? this.state(this.config.max_dbz_entity)?.state,
        )
      : null;
    const coreArea = radarCurrent ? this.number(attrs.selected_core_area_km2) : null;
    const liveCoreCount = liveRadar && Number.isInteger(overlay?.limits?.core_count_rendered)
      ? overlay.limits.core_count_rendered
      : null;
    const liveCoreTotal = liveRadar && Number.isInteger(overlay?.limits?.core_count_total)
      ? overlay.limits.core_count_total
      : null;
    const facts = [];

    if (coreDistance != null && mode !== 'lightning') {
      facts.push(this.fact('mdi:map-marker-distance', 'Nejbližší jádro', `${coreDistance.toFixed(1)} km`));
    }
    if (coreMaxDbz != null && mode !== 'lightning') {
      facts.push(this.fact('mdi:radar', 'Intenzita jádra', `${Math.round(coreMaxDbz)} dBZ`));
    }
    if (coreArea != null && mode !== 'lightning') {
      facts.push(this.fact('mdi:selection-ellipse', 'Plocha jádra', `${coreArea.toFixed(1)} km²`));
    }
    if (liveCoreCount != null && liveCoreTotal > liveCoreCount && mode !== 'lightning') {
      facts.push(this.fact('mdi:dots-circle', 'Zobrazeno', `${liveCoreCount} z ${liveCoreTotal} jader`));
    } else if (liveCoreCount > 1 && mode !== 'lightning') {
      facts.push(this.fact('mdi:dots-circle', 'Detekovaná jádra', String(liveCoreCount)));
    } else if (!liveRadar && renderableCores.length > 1 && mode !== 'lightning') {
      facts.push(this.fact('mdi:dots-circle', 'Detekovaná jádra', String(renderableCores.length)));
    }
    if (approaching) {
      facts.push(this.fact('mdi:arrow-collapse', 'Pohyb', 'Přibližuje se'));
    } else if (receding) {
      facts.push(this.fact('mdi:arrow-expand', 'Pohyb', 'Vzdaluje se'));
    }
    if (eta != null) {
      facts.push(this.fact('mdi:clock-outline', 'Příchod', this.formatEta(eta)));
    }
    if (lightningDistance != null) {
      facts.push(this.fact('mdi:flash', 'Nejbližší blesk', `${lightningDistance.toFixed(1)} km`));
    } else if (evidence === 'radar_hail_with_lightning') {
      facts.push(this.fact('mdi:flash', 'Blesky', 'Také detekovány'));
    }

    const showSchematic = radarCurrent && coreDistance != null && mode !== 'lightning';
    const radarModule = liveRadar?.html || (
      showSchematic ? this.radar(renderableCores, selectedCore, coreDistance, coreBearing, approaching) : ''
    );
    this._cardSize = liveRadar ? 5 : (showSchematic ? 4 : 3);
    this.shadowRoot.innerHTML = `
      <style>${this.css(presentation.accent, presentation.glow)}</style>
      <ha-card class="risk-card ${mode}">
        <div class="accent-line"></div>
        <section class="hero">
          <div class="icon"><ha-icon icon="${presentation.icon}"></ha-icon></div>
          <div class="headline">
            <div class="eyebrow">${this.escape(this.config.title)}</div>
            <div class="status">${this.escape(presentation.title)}</div>
            <div class="message">${this.escape(this.message(mode, { coreDistance, approaching, receding }))}</div>
          </div>
        </section>
        ${radarModule}
        ${tileError ? '<div class="radar-error">Radarová vrstva se nepodařila načíst, zobrazuji schematický náhled.</div>' : ''}
        ${facts.length ? `<section class="facts">${facts.join('')}</section>` : ''}
        ${mode === 'lightning' ? '<div class="hail-note">Kroupy nejsou radarově potvrzené</div>' : ''}
        ${liveRadar || mode === 'lightning' ? '' : '<div class="safety-note">Radarová aktivita není potvrzené krupobití · sledujte oficiální výstrahy.</div>'}
      </ha-card>
    `;
    if (liveRadar) this.bindRadarTileErrors(liveRadar.frameTime);
  }

  compactCard(presentation, mode) {
    const detail = mode === 'clear'
      ? 'Silné radarové jádro v okolí nezjištěno'
      : 'Detekce dočasně není dostupná';
    return `
      <style>${this.css(presentation.accent, presentation.glow)}</style>
      <ha-card class="risk-card compact ${mode}">
        <div class="compact-icon"><ha-icon icon="${presentation.icon}"></ha-icon></div>
        <div class="compact-copy">
          <div class="eyebrow">${this.escape(this.config.title)}</div>
          <strong>${detail}</strong>
        </div>
      </ha-card>
    `;
  }

  displayMode(level, evidence, stale) {
    if (stale || level === 'unavailable') return 'unavailable';
    if (level === 'none') return 'clear';
    if (evidence === 'lightning_only') return 'lightning';
    if (evidence === 'radar_hail_with_lightning' || evidence === 'radar_hail') {
      return level === 'urgent' ? 'hail-high' : 'hail-possible';
    }
    if (evidence === 'radar_storm') return 'storm';
    return 'weather-attention';
  }

  presentation(mode) {
    const modes = {
      clear: {
        title: 'Klid',
        icon: 'mdi:weather-partly-cloudy',
        accent: '#65a30d',
        glow: 'rgba(101,163,13,.12)',
      },
      unavailable: {
        title: 'Bez aktuálních dat',
        icon: 'mdi:cloud-alert-outline',
        accent: '#94a3b8',
        glow: 'rgba(148,163,184,.12)',
      },
      storm: {
        title: 'Bouřka v okolí',
        icon: 'mdi:weather-lightning-rainy',
        accent: '#eab308',
        glow: 'rgba(234,179,8,.22)',
      },
      lightning: {
        title: 'Blesky poblíž',
        icon: 'mdi:weather-lightning',
        accent: '#f59e0b',
        glow: 'rgba(245,158,11,.24)',
      },
      'hail-possible': {
        title: 'Možné kroupy',
        icon: 'mdi:weather-hail',
        accent: '#f97316',
        glow: 'rgba(249,115,22,.28)',
      },
      'hail-high': {
        title: 'Vysoká možnost krup',
        icon: 'mdi:alert-decagram',
        accent: '#ef4444',
        glow: 'rgba(239,68,68,.30)',
      },
      'weather-attention': {
        title: 'Počasí vyžaduje pozornost',
        icon: 'mdi:weather-cloudy-alert',
        accent: '#eab308',
        glow: 'rgba(234,179,8,.20)',
      },
    };
    return modes[mode] || modes['weather-attention'];
  }

  message(mode, context) {
    const { coreDistance, approaching, receding } = context;
    if (mode === 'clear') return 'Silné radarové jádro v okolí nezjištěno.';
    if (mode === 'lightning') return 'V okolí byla zaznamenána aktuální blesková aktivita.';
    if (mode === 'hail-possible') return 'Radar ukazuje silné jádro s možností krup.';
    if (mode === 'hail-high') return 'Silné radarové jádro je blízko domova.';
    if (mode === 'storm') {
      if (approaching) return 'Radarové jádro se přibližuje k domovu.';
      if (receding) return 'Radarové jádro se vzdaluje od domova.';
      if (coreDistance != null) return 'Radar zachytil bouřkové jádro v širším okolí.';
      return 'Radar zachytil bouřkovou aktivitu v okolí.';
    }
    return 'Byla zjištěna aktuální změna počasí.';
  }

  fact(icon, label, value) {
    return `
      <div class="fact">
        <ha-icon icon="${icon}"></ha-icon>
        <div><span>${this.escape(label)}</span><strong>${this.escape(value)}</strong></div>
      </div>
    `;
  }

  liveOverlayEligible(evidence, overlay) {
    if (!overlay || this.config.radar_overlay === 'off') return false;
    if (this.config.radar_overlay === 'always') return true;
    return ['radar_storm', 'radar_hail', 'radar_hail_with_lightning'].includes(evidence);
  }

  validRadarOverlay(attrs, stale, source) {
    const overlay = attrs.radar_overlay;
    if (!overlay || typeof overlay !== 'object' || Array.isArray(overlay)) return null;
    if (overlay.schema_version !== 1 || overlay.status !== 'ok') return null;
    if (source.radar !== 'ok' || stale || attrs.is_stale === true) return null;

    const frame = overlay.frame;
    if (!frame || typeof frame !== 'object' || Array.isArray(frame)) return null;
    if (!Number.isInteger(frame.time) || frame.time < 0 || frame.time !== attrs.frame_time) return null;
    const frameAge = this.number(frame.age_seconds);
    const attrsFrameAge = this.number(attrs.frame_age_seconds);
    if (frameAge == null || attrsFrameAge == null || Math.abs(frameAge - attrsFrameAge) > 1) return null;
    if (!this.validTileTemplate(frame.tile_url_template)) return null;
    const displayZoom = this.number(frame.display_zoom);
    const maxNativeZoom = this.number(frame.max_native_zoom);
    const tileSize = this.number(frame.tile_size) || 512;
    if (displayZoom == null || maxNativeZoom == null || displayZoom < 0 || maxNativeZoom < 0) return null;
    if (tileSize <= 0) return null;

    const viewport = overlay.viewport;
    const centerLatitude = this.number(viewport?.center_latitude);
    const centerLongitude = this.number(viewport?.center_longitude);
    const radiusKm = this.number(viewport?.radius_km);
    if (!this.validLatLon(centerLatitude, centerLongitude) || radiusKm == null || radiusKm <= 0) return null;

    const cores = Array.isArray(overlay.cores) ? overlay.cores : null;
    if (!cores || cores.some((core) => !core || core.frame_time !== frame.time)) return null;
    const selectedId = overlay.selected_core_id;
    const selectedCores = cores.filter((core) => core.selected === true);
    if (selectedId != null) {
      if (typeof selectedId !== 'string' || selectedId.trim() === '') return null;
      const matches = cores.filter((core) => core.id === selectedId);
      if (matches.length !== 1 || selectedCores.length !== 1 || matches[0] !== selectedCores[0]) return null;
      const selected = matches[0];
      if (!this.corePosition(selected)) return null;
      const synchronizedValues = [
        [selected.distance_km, attrs.selected_core_distance_km],
        [selected.threshold_dbz, attrs.selected_core_threshold_dbz],
        [selected.max_dbz, attrs.selected_core_max_dbz],
      ];
      if (synchronizedValues.some(([overlayValue, attrsValue]) => {
        const left = this.number(overlayValue);
        const right = this.number(attrsValue);
        return left == null || right == null || Math.abs(left - right) > 0.001;
      })) return null;
    } else if (selectedCores.length) {
      return null;
    }

    return {
      ...overlay,
      frame: {
        ...frame,
        display_zoom: Math.min(Math.floor(displayZoom), Math.floor(maxNativeZoom), 7),
        tile_size: Math.floor(tileSize),
      },
      viewport: {
        ...viewport,
        center_latitude: centerLatitude,
        center_longitude: centerLongitude,
        radius_km: radiusKm,
      },
      cores,
    };
  }

  validTileTemplate(template) {
    if (typeof template !== 'string' || !template || /[\u0000-\u001f\u007f\s]/i.test(template)) return false;
    const placeholders = template.match(/\{[^{}]+\}/g) || [];
    if (placeholders.length !== 3 || new Set(placeholders).size !== 3) return false;
    if (!['{z}', '{x}', '{y}'].every((placeholder) => placeholders.includes(placeholder))) return false;
    const candidate = template.replaceAll('{z}', '7').replaceAll('{x}', '64').replaceAll('{y}', '64');
    if (/[{}]/.test(candidate)) return false;
    try {
      const url = new URL(candidate);
      return url.protocol === 'https:' && !url.username && !url.password;
    } catch (_error) {
      return false;
    }
  }

  validLatLon(latitude, longitude) {
    return Number.isFinite(latitude) && Number.isFinite(longitude)
      && latitude >= -85.05112878 && latitude <= 85.05112878
      && longitude >= -180 && longitude <= 180;
  }

  corePosition(core) {
    const candidates = [
      [core?.render_latitude, core?.render_longitude],
      [core?.centroid_latitude, core?.centroid_longitude],
      [core?.latitude, core?.longitude],
    ];
    for (const [latitudeValue, longitudeValue] of candidates) {
      const latitude = this.number(latitudeValue);
      const longitude = this.number(longitudeValue);
      if (this.validLatLon(latitude, longitude)) return { latitude, longitude };
    }
    return null;
  }

  projectWebMercator(latitude, longitude, zoom, tileSize) {
    const boundedLatitude = Math.min(85.05112878, Math.max(-85.05112878, latitude));
    const worldSize = (2 ** zoom) * tileSize;
    const latitudeRadians = boundedLatitude * Math.PI / 180;
    return {
      x: ((longitude + 180) / 360) * worldSize,
      y: ((1 - Math.asinh(Math.tan(latitudeRadians)) / Math.PI) / 2) * worldSize,
    };
  }

  radiusPixels(radiusKm, centerLatitude, zoom, tileSize) {
    const earthCircumferenceM = 2 * Math.PI * 6378137;
    const metersPerPixel = (
      Math.cos(centerLatitude * Math.PI / 180) * earthCircumferenceM
    ) / ((2 ** zoom) * tileSize);
    return radiusKm * 1000 / metersPerPixel;
  }

  tileGrid(overlay) {
    const { frame, viewport } = overlay;
    const zoom = frame.display_zoom;
    const tileSize = frame.tile_size;
    const center = this.projectWebMercator(
      viewport.center_latitude,
      viewport.center_longitude,
      zoom,
      tileSize,
    );
    const radius = this.radiusPixels(viewport.radius_km, viewport.center_latitude, zoom, tileSize);
    if (!Number.isFinite(radius) || radius <= 0) return null;
    const minX = Math.floor((center.x - radius) / tileSize);
    const maxX = Math.floor((center.x + radius) / tileSize);
    const worldTiles = 2 ** zoom;
    const minY = Math.max(0, Math.floor((center.y - radius) / tileSize));
    const maxY = Math.min(worldTiles - 1, Math.floor((center.y + radius) / tileSize));
    const count = (maxX - minX + 1) * (maxY - minY + 1);
    if (count <= 0 || count > 25 || (viewport.radius_km <= 80 && count > 9)) return null;
    return {
      zoom,
      tileSize,
      minX,
      maxX,
      minY,
      maxY,
      worldTiles,
      width: (maxX - minX + 1) * tileSize,
      height: (maxY - minY + 1) * tileSize,
      originX: minX * tileSize,
      originY: minY * tileSize,
      center,
      radius,
    };
  }

  liveRadar(overlay) {
    if (this._radarTileErrorFrameTime === overlay.frame.time) return null;
    const grid = this.tileGrid(overlay);
    if (!grid) return null;

    const tiles = [];
    for (let y = grid.minY; y <= grid.maxY; y += 1) {
      for (let x = grid.minX; x <= grid.maxX; x += 1) {
        const tileX = ((x % grid.worldTiles) + grid.worldTiles) % grid.worldTiles;
        const src = overlay.frame.tile_url_template
          .replaceAll('{z}', String(grid.zoom))
          .replaceAll('{x}', String(tileX))
          .replaceAll('{y}', String(y));
        tiles.push(`<img class="radar-tile" src="${this.escape(src)}" alt="" aria-hidden="true" loading="lazy" decoding="async" referrerpolicy="no-referrer" style="left:${((x - grid.minX) * grid.tileSize / grid.width) * 100}%;top:${((y - grid.minY) * grid.tileSize / grid.height) * 100}%;width:${(grid.tileSize / grid.width) * 100}%;height:${(grid.tileSize / grid.height) * 100}%" />`);
      }
    }

    const offsetX = grid.originX;
    const offsetY = grid.originY;
    const centerX = grid.center.x - offsetX;
    const centerY = grid.center.y - offsetY;
    const rings = [
      ['monitoring', overlay.viewport.radius_km],
      ['warning', this.number(overlay.viewport.warning_radius_km)],
      ['urgent', this.number(overlay.viewport.urgent_radius_km)],
    ].filter(([, radiusKm]) => radiusKm != null && radiusKm > 0)
      .map(([kind, radiusKm]) => `<circle class="live-ring ${kind}" cx="${centerX}" cy="${centerY}" r="${this.radiusPixels(radiusKm, overlay.viewport.center_latitude, grid.zoom, grid.tileSize)}" />`)
      .join('');
    const orderedCores = [...overlay.cores].sort(
      (left, right) => Number(left.id === overlay.selected_core_id) - Number(right.id === overlay.selected_core_id),
    );
    let selectedRendered = overlay.selected_core_id == null;
    const marks = orderedCores.flatMap((core) => {
      const position = this.corePosition(core);
      if (!position) return [];
      const point = this.projectWebMercator(position.latitude, position.longitude, grid.zoom, grid.tileSize);
      const worldSize = grid.worldTiles * grid.tileSize;
      let unwrappedX = point.x;
      if (unwrappedX - grid.center.x > worldSize / 2) unwrappedX -= worldSize;
      if (unwrappedX - grid.center.x < -worldSize / 2) unwrappedX += worldSize;
      const x = unwrappedX - offsetX;
      const y = point.y - offsetY;
      if (x < -12 || y < -12 || x > grid.width + 12 || y > grid.height + 12) return [];
      const id = this.escape(core.id ?? '');
      const positionStyle = `left:${(x / grid.width) * 100}%;top:${(y / grid.height) * 100}%`;
      if (core.id === overlay.selected_core_id) {
        selectedRendered = true;
        return [`<span class="live-core-halo" style="${positionStyle}"></span>
          <span class="live-core selected" data-core-id="${id}" data-projected-x="${x}" data-projected-y="${y}" style="${positionStyle}"></span>`];
      }
      return [`<span class="live-core secondary" data-core-id="${id}" data-projected-x="${x}" data-projected-y="${y}" style="${positionStyle}"></span>`];
    });
    if (!selectedRendered) return null;
    const selected = overlay.cores.find((core) => core.id === overlay.selected_core_id);
    const selectedDistance = this.number(selected?.distance_km);
    const selectedSummary = selectedDistance == null
      ? ''
      : `<strong>Hlavní jádro ${selectedDistance.toFixed(1)} km od ${this.escape(this.homeDistanceLabel())}</strong>`;
    const frameLabel = overlay.frame.time_iso || String(overlay.frame.time);
    const ageSeconds = this.number(overlay.frame.age_seconds);
    const ageLabel = ageSeconds == null ? '' : ` · stáří ${Math.max(0, Math.round(ageSeconds / 60))} min`;

    return {
      frameTime: overlay.frame.time,
      html: `
        <section class="radar-live" role="img" aria-label="Radarový snímek RainViewer s bouřkovými jádry v okolí domova">
          <div class="radar-live-stage" style="aspect-ratio:${grid.width}/${grid.height}">
            <div class="radar-tiles">${tiles.join('')}</div>
            <svg class="radar-live-overlay" viewBox="0 0 ${grid.width} ${grid.height}" preserveAspectRatio="none" aria-hidden="true">
              ${rings}
            </svg>
            <div class="radar-markers" aria-hidden="true">
              <span class="live-home-halo" style="left:${(centerX / grid.width) * 100}%;top:${(centerY / grid.height) * 100}%"></span>
              <span class="live-home" style="left:${(centerX / grid.width) * 100}%;top:${(centerY / grid.height) * 100}%"></span>
              ${marks.join('')}
            </div>
            <span class="live-home-label" style="left:${(centerX / grid.width) * 100}%;top:${(centerY / grid.height) * 100}%">${this.escape(this.config.home_label)}</span>
          </div>
          <div class="radar-live-meta">
            <span>Radarový snímek ${this.escape(frameLabel)}${this.escape(ageLabel)}</span>
            <a href="https://www.rainviewer.com/" target="_blank" rel="noopener noreferrer">Weather data by RainViewer</a>
          </div>
          ${selectedSummary ? `<div class="radar-live-selected">${selectedSummary}</div>` : ''}
          <div class="radar-live-safety">Radarová aktivita není potvrzené krupobití · sledujte oficiální výstrahy.</div>
        </section>
      `,
    };
  }

  bindRadarTileErrors(frameTime) {
    const tiles = this.shadowRoot?.querySelectorAll?.('.radar-tile');
    if (!tiles) return;
    tiles.forEach((tile) => tile.addEventListener('error', () => {
      if (this._radarTileErrorFrameTime === frameTime) return;
      this._radarTileErrorFrameTime = frameTime;
      this.render();
    }, { once: true }));
  }

  homeDistanceLabel() {
    return this.config.home_label === 'Domov' ? 'domova' : this.config.home_label;
  }

  radar(cores, selectedCore, distance, bearing, approaching) {
    const maxDistance = Math.max(distance, ...cores.map((core) => this.number(core.distance_km) ?? 0));
    const maxKm = Math.max(50, Math.ceil(maxDistance / 20) * 20);
    const marks = cores
      .map((core) => ({
        point: this.point(this.number(core.distance_km), this.number(core.bearing_degrees), maxKm),
        selected: core === selectedCore,
      }))
      .sort((left, right) => Number(left.selected) - Number(right.selected));
    if (!marks.some((mark) => mark.selected) && Number.isFinite(bearing)) {
      marks.push({ point: this.point(distance, bearing, maxKm), selected: true });
    }
    const coreMarks = marks.map((mark) => {
      if (mark.selected) {
        return `<circle class="core-pulse selected" cx="${mark.point.x}" cy="${mark.point.y}" r="14" />
          <circle class="core-node selected" cx="${mark.point.x}" cy="${mark.point.y}" r="8" />`;
      }
      return `<circle class="core-node secondary" cx="${mark.point.x}" cy="${mark.point.y}" r="5" />`;
    }).join('');
    return `
      <section class="radar-wrap">
        <svg class="radar" viewBox="0 0 180 180" role="img" aria-label="Polohy bouřkových jader vůči domovu">
          <circle class="radar-bg" cx="90" cy="90" r="72" />
          <circle class="ring" cx="90" cy="90" r="36" />
          <circle class="ring" cx="90" cy="90" r="70" />
          <line class="axis" x1="90" y1="20" x2="90" y2="160" />
          <line class="axis" x1="20" y1="90" x2="160" y2="90" />
          <circle class="home-node" cx="90" cy="90" r="6" />
          ${coreMarks}
          <text class="north" x="90" y="14" text-anchor="middle">S</text>
        </svg>
        <div class="radar-copy">
          <strong>${distance.toFixed(1)} km</strong>
          <span>hlavní jádro od ${this.escape(this.homeDistanceLabel())}</span>
          ${approaching ? '<em>Přibližuje se</em>' : ''}
        </div>
      </section>
    `;
  }

  point(distance, bearingDeg, maxKm) {
    const clamped = Math.min(Math.max(distance ?? maxKm, 0), maxKm);
    const radius = (clamped / maxKm) * 68;
    const rad = (Number(bearingDeg) - 90) * Math.PI / 180;
    return { x: 90 + Math.cos(rad) * radius, y: 90 + Math.sin(rad) * radius };
  }

  formatEta(minutes) {
    const value = Math.max(1, Math.round(minutes));
    if (value < 10) return 'méně než 10 min';
    const lower = Math.floor(value / 5) * 5;
    const upper = Math.ceil(value / 5) * 5;
    return lower === upper ? `přibližně ${lower} min` : `přibližně ${lower}–${upper} min`;
  }

  state(entityId) {
    return entityId ? this._hass?.states?.[entityId] : undefined;
  }

  levelValue(value) {
    const normalized = String(value ?? '').toLowerCase();
    return ['none', 'watch', 'warning', 'urgent', 'unavailable'].includes(normalized)
      ? normalized
      : 'unavailable';
  }

  number(value) {
    if (value == null || ['unknown', 'unavailable', 'none', ''].includes(String(value))) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  css(accent, glow) {
    return `
      :host { display:block; max-width:100%; overflow-x:hidden; }
      ha-card.risk-card {
        display:block;
        position:relative;
        overflow:hidden;
        padding:18px;
        border-radius:24px;
        color:var(--primary-text-color, #f8fafc);
        background:
          radial-gradient(circle at 100% 0%, ${glow}, transparent 38%),
          var(--ha-card-background, var(--card-background-color, #111827));
        border:1px solid color-mix(in srgb, ${accent} 42%, var(--divider-color, #334155));
        box-shadow:0 12px 36px rgba(0,0,0,.18);
      }
      ha-card.compact { display:flex; align-items:center; gap:13px; padding:13px 16px; border-radius:18px; box-shadow:none; }
      .compact-icon, .icon { display:grid; place-items:center; flex:0 0 auto; color:${accent}; background:${glow}; border:1px solid color-mix(in srgb, ${accent} 40%, transparent); }
      .compact-icon { width:38px; height:38px; border-radius:12px; }
      .compact-icon ha-icon { width:22px; height:22px; }
      .compact-copy { min-width:0; }
      .compact-copy strong { display:block; margin-top:2px; font-size:14px; }
      .eyebrow { color:var(--secondary-text-color, #94a3b8); font-size:11px; line-height:1.2; letter-spacing:.09em; text-transform:uppercase; font-weight:750; }
      .accent-line { position:absolute; inset:0 0 auto; height:3px; background:${accent}; }
      .hero { display:flex; align-items:flex-start; gap:14px; }
      .icon { width:48px; height:48px; border-radius:15px; }
      .icon ha-icon { width:28px; height:28px; }
      .headline { min-width:0; }
      .status { margin-top:4px; color:${accent}; font-size:27px; line-height:1.08; font-weight:850; letter-spacing:-.025em; }
      .message { margin-top:7px; color:var(--secondary-text-color, #cbd5e1); font-size:14px; line-height:1.4; }
      .facts { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:9px; margin-top:14px; }
      .fact { display:flex; align-items:center; gap:10px; min-width:0; padding:10px 11px; border-radius:14px; background:color-mix(in srgb, var(--card-background-color, #111827) 88%, ${accent}); border:1px solid var(--divider-color, rgba(148,163,184,.16)); }
      .fact ha-icon { flex:0 0 auto; width:20px; height:20px; color:${accent}; }
      .fact span { display:block; color:var(--secondary-text-color, #94a3b8); font-size:10px; }
      .fact strong { display:block; overflow:hidden; margin-top:1px; font-size:14px; text-overflow:ellipsis; white-space:nowrap; }
      .radar-wrap { display:grid; grid-template-columns:minmax(150px, 210px) 1fr; align-items:center; gap:10px; margin-top:12px; padding:8px 12px; border-radius:18px; background:color-mix(in srgb, var(--card-background-color, #111827) 92%, ${accent}); }
      .radar { width:100%; max-height:190px; }
      .radar-bg { fill:${glow}; }
      .ring { fill:none; stroke:var(--divider-color, rgba(148,163,184,.25)); stroke-width:1; stroke-dasharray:3 5; }
      .axis { stroke:var(--divider-color, rgba(148,163,184,.14)); stroke-width:1; }
      .home-node { fill:var(--primary-text-color, #f8fafc); stroke:var(--card-background-color, #111827); stroke-width:2; }
      .core-node { fill:${accent}; stroke:#fff; stroke-width:1.5; filter:drop-shadow(0 0 8px ${accent}); }
      .core-node.secondary { opacity:.68; stroke-width:1; filter:drop-shadow(0 0 4px ${accent}); }
      .core-node.selected { opacity:1; }
      .core-pulse { fill:none; stroke:${accent}; stroke-width:2; opacity:.42; }
      .north { fill:var(--secondary-text-color, #94a3b8); font-size:9px; font-weight:800; }
      .radar-copy strong { display:block; color:${accent}; font-size:25px; }
      .radar-copy span { display:block; color:var(--secondary-text-color, #94a3b8); font-size:12px; }
      .radar-copy em { display:inline-block; margin-top:8px; padding:5px 8px; border-radius:999px; color:${accent}; background:${glow}; font-size:11px; font-style:normal; font-weight:750; }
      .radar-live { min-width:0; max-width:100%; margin-top:12px; overflow:hidden; border-radius:18px; background:#07111f; border:1px solid var(--divider-color, rgba(148,163,184,.18)); }
      .radar-live-stage { position:relative; width:100%; min-height:220px; max-height:320px; overflow:hidden; background:radial-gradient(circle at center, rgba(51,65,85,.48), #07111f 72%); }
      .radar-tiles, .radar-live-overlay { position:absolute; inset:0; width:100%; height:100%; }
      .radar-tile { position:absolute; display:block; object-fit:fill; opacity:.8; pointer-events:none; }
      .radar-live-overlay { z-index:2; }
      .live-ring { fill:none; stroke-width:2; vector-effect:non-scaling-stroke; }
      .live-ring.monitoring { stroke:rgba(226,232,240,.72); stroke-dasharray:7 6; }
      .live-ring.warning { stroke:rgba(249,115,22,.58); }
      .live-ring.urgent { stroke:rgba(239,68,68,.65); }
      .radar-markers { position:absolute; inset:0; z-index:3; pointer-events:none; }
      .live-home-halo, .live-home, .live-core, .live-core-halo { position:absolute; box-sizing:border-box; border-radius:50%; transform:translate(-50%, -50%); }
      .live-home-halo { width:18px; height:18px; background:rgba(15,23,42,.62); border:2px solid #fff; }
      .live-home { width:10px; height:10px; background:#fff; border:2px solid #0f172a; }
      .live-core { background:${accent}; border:2px solid #fff; filter:drop-shadow(0 0 7px ${accent}); }
      .live-core.secondary { width:10px; height:10px; opacity:.72; border-width:1.5px; }
      .live-core.selected { width:14px; height:14px; opacity:1; z-index:2; }
      .live-core-halo { width:22px; height:22px; border:4px solid ${accent}; opacity:.75; animation:selected-core-pulse 1.8s ease-out infinite; }
      .live-home-label { position:absolute; z-index:4; transform:translate(10px, 8px); color:#fff; font-size:11px; font-weight:800; text-shadow:0 1px 3px #000; }
      .radar-live-meta { display:flex; justify-content:space-between; gap:10px; padding:8px 10px 0; color:var(--secondary-text-color, #94a3b8); font-size:10px; line-height:1.35; }
      .radar-live-meta a { color:var(--primary-text-color, #e2e8f0); }
      .radar-live-meta a:focus-visible { outline:2px solid ${accent}; outline-offset:2px; }
      .radar-live-selected { padding:7px 10px 0; color:${accent}; font-size:13px; }
      .radar-live-safety { padding:7px 10px 10px; color:var(--secondary-text-color, #cbd5e1); font-size:10px; line-height:1.35; }
      .radar-error { margin-top:9px; color:var(--secondary-text-color, #94a3b8); font-size:10px; }
      .hail-note { margin-top:13px; padding:9px 11px; border-radius:12px; color:var(--secondary-text-color, #cbd5e1); background:var(--secondary-background-color, rgba(15,23,42,.45)); font-size:12px; }
      .safety-note { margin-top:13px; color:var(--secondary-text-color, #94a3b8); font-size:10px; }
      @keyframes selected-core-pulse { from { opacity:.75; transform:translate(-50%, -50%) scale(1); } to { opacity:.08; transform:translate(-50%, -50%) scale(1.8); } }
      @media (max-width:600px) {
        ha-card.risk-card { padding:15px; border-radius:20px; }
        ha-card.compact { padding:12px 14px; }
        .status { font-size:23px; }
        .facts { grid-template-columns:1fr; }
        .radar-wrap { grid-template-columns:minmax(125px, 165px) 1fr; }
        .radar-live-stage { min-height:220px; max-height:320px; aspect-ratio:1/1 !important; }
        .radar-live-meta { flex-direction:column; gap:3px; }
      }
      @media (prefers-reduced-motion: reduce) {
        .live-core-halo { animation:none; }
      }
    `;
  }

  escape(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }
}

customElements.define('radar-hail-risk-card', RadarHailRiskCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'radar-hail-risk-card',
  name: 'Bouřky a možné kroupy',
  description: 'Adaptivní karta zobrazující jen aktuální a prakticky relevantní údaje.',
});
