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
      ...config,
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

    if (mode === 'clear' || mode === 'unavailable') {
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
    const lightningDistance = lightningCurrent
      ? this.number(
          this.state(this.config.lightning_distance_entity)?.state ?? attrs.lightning_distance_km,
        )
      : null;
    const approaching = attrs.storm_approaching === true;
    const receding = attrs.distance_trend === 'receding';
    const eta = approaching ? this.number(attrs.storm_eta_minutes) : null;
    const facts = [];

    if (coreDistance != null && mode !== 'lightning') {
      facts.push(this.fact('mdi:map-marker-distance', 'Nejbližší jádro', `${coreDistance.toFixed(1)} km`));
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

    const showRadar = radarCurrent && coreDistance != null && mode !== 'lightning';
    this._cardSize = showRadar ? 4 : 3;
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
        ${showRadar ? this.radar(coreDistance, attrs.storm_motion_bearing, approaching) : ''}
        ${facts.length ? `<section class="facts">${facts.join('')}</section>` : ''}
        ${mode === 'lightning' ? '<div class="hail-note">Kroupy nejsou radarově potvrzené</div>' : ''}
        <div class="safety-note">Orientační radarové upozornění · sledujte oficiální výstrahy</div>
      </ha-card>
    `;
  }

  compactCard(presentation, mode) {
    const detail = mode === 'clear'
      ? 'Nic významného nezjištěno'
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

  radar(distance, bearing, approaching) {
    const point = this.point(distance, this.number(bearing) ?? 315, 50);
    return `
      <section class="radar-wrap">
        <svg class="radar" viewBox="0 0 180 180" role="img" aria-label="Poloha bouřkového jádra vůči domovu">
          <circle class="radar-bg" cx="90" cy="90" r="72" />
          <circle class="ring" cx="90" cy="90" r="36" />
          <circle class="ring" cx="90" cy="90" r="70" />
          <line class="axis" x1="90" y1="20" x2="90" y2="160" />
          <line class="axis" x1="20" y1="90" x2="160" y2="90" />
          <circle class="home-node" cx="90" cy="90" r="6" />
          <circle class="core-pulse" cx="${point.x}" cy="${point.y}" r="14" />
          <circle class="core-node" cx="${point.x}" cy="${point.y}" r="8" />
          <text class="north" x="90" y="14" text-anchor="middle">S</text>
        </svg>
        <div class="radar-copy">
          <strong>${distance.toFixed(1)} km</strong>
          <span>od ${this.escape(this.config.home_label)}</span>
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
      :host { display:block; }
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
      .core-pulse { fill:none; stroke:${accent}; stroke-width:2; opacity:.42; }
      .north { fill:var(--secondary-text-color, #94a3b8); font-size:9px; font-weight:800; }
      .radar-copy strong { display:block; color:${accent}; font-size:25px; }
      .radar-copy span { display:block; color:var(--secondary-text-color, #94a3b8); font-size:12px; }
      .radar-copy em { display:inline-block; margin-top:8px; padding:5px 8px; border-radius:999px; color:${accent}; background:${glow}; font-size:11px; font-style:normal; font-weight:750; }
      .hail-note { margin-top:13px; padding:9px 11px; border-radius:12px; color:var(--secondary-text-color, #cbd5e1); background:var(--secondary-background-color, rgba(15,23,42,.45)); font-size:12px; }
      .safety-note { margin-top:13px; color:var(--secondary-text-color, #94a3b8); font-size:10px; }
      @media (max-width:600px) {
        ha-card.risk-card { padding:15px; border-radius:20px; }
        ha-card.compact { padding:12px 14px; }
        .status { font-size:23px; }
        .facts { grid-template-columns:1fr; }
        .radar-wrap { grid-template-columns:minmax(125px, 165px) 1fr; }
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
