class RadarHailRiskCard extends HTMLElement {
  static getStubConfig() {
    return {
      type: 'custom:radar-hail-risk-card',
      title: 'Krupové riziko',
      level_entity: 'sensor.radar_hail_risk_level',
      summary_entity: 'sensor.radar_hail_risk_summary',
      max_dbz_entity: 'sensor.radar_hail_risk_max_dbz',
      core_distance_entity: 'sensor.radar_hail_risk_core_distance',
      lightning_distance_entity: 'sensor.radar_hail_risk_lightning_distance',
      frame_age_entity: 'sensor.radar_hail_risk_frame_age',
      active_entity: 'binary_sensor.radar_hail_risk_active',
      stale_entity: 'binary_sensor.radar_hail_risk_data_stale',
    };
  }

  setConfig(config) {
    if (!config) throw new Error('Invalid configuration');
    this.config = {
      title: 'Krupové riziko',
      level_entity: 'sensor.radar_hail_risk_level',
      summary_entity: 'sensor.radar_hail_risk_summary',
      max_dbz_entity: 'sensor.radar_hail_risk_max_dbz',
      core_distance_entity: 'sensor.radar_hail_risk_core_distance',
      lightning_distance_entity: 'sensor.radar_hail_risk_lightning_distance',
      frame_age_entity: 'sensor.radar_hail_risk_frame_age',
      active_entity: 'binary_sensor.radar_hail_risk_active',
      stale_entity: 'binary_sensor.radar_hail_risk_data_stale',
      home_label: 'Domov',
      ...config,
    };
    if (!this.shadowRoot) {
      this.attachShadow({ mode: 'open' });
    }
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return 6;
  }

  render() {
    if (!this.shadowRoot || !this._hass || !this.config) return;
    const c = this.config;
    const levelState = this.state(c.level_entity);
    const level = this.safe(levelState?.state, 'unavailable');
    const attrs = levelState?.attributes || {};
    const summary = this.state(c.summary_entity)?.state || attrs.summary || 'Bez aktuálního shrnutí';
    const maxDbz = this.number(this.state(c.max_dbz_entity)?.state);
    const coreDistance = this.number(this.state(c.core_distance_entity)?.state ?? attrs.selected_core_distance_km);
    const lightningDistance = this.number(this.state(c.lightning_distance_entity)?.state ?? attrs.lightning_distance_km);
    const frameAge = this.number(this.state(c.frame_age_entity)?.state ?? attrs.frame_age_seconds);
    const stale = this.state(c.stale_entity)?.state === 'on' || attrs.is_stale === true;
    const active = this.state(c.active_entity)?.state === 'on';
    const core50 = this.number(attrs.core50_distance_km);
    const core55 = this.number(attrs.core55_distance_km);
    const core60 = this.number(attrs.core60_distance_km);
    const source = attrs.source_status || {};
    const confidence = this.number(attrs.confidence_score);
    const trend = attrs.distance_trend || '—';
    const dbzTrend = attrs.dbz_trend || '—';
    const speed = this.number(attrs.storm_motion_speed_kmh);
    const bearing = this.number(attrs.storm_motion_bearing);
    const approaching = attrs.storm_approaching === true;
    const eta = this.number(attrs.storm_eta_minutes);
    const lightningTriggered = attrs.lightning_triggered === true;

    const theme = this.theme(level, stale);
    const statusLabel = this.statusLabel(level, stale);
    const frameText = frameAge == null ? '—' : frameAge < 90 ? `${Math.round(frameAge)} s` : `${Math.round(frameAge / 60)} min`;
    const coreText = coreDistance == null ? '—' : `${coreDistance.toFixed(1)} km`;
    const lightningText = lightningDistance == null ? '—' : `${lightningDistance.toFixed(1)} km`;
    const dbzText = maxDbz == null ? '—' : `${Math.round(maxDbz)} dBZ`;

    this.shadowRoot.innerHTML = `
      <style>${this.css(theme)}</style>
      <ha-card class="risk-card ${theme.name}">
        <div class="glow"></div>
        <section class="hero">
          <div>
            <div class="eyebrow">${this.escape(c.title)}</div>
            <div class="status">${statusLabel}</div>
            <div class="summary">${this.escape(summary)}</div>
          </div>
          <div class="badge ${active ? 'active' : ''}">
            <span>${active ? 'ACTIVE' : 'MONITOR'}</span>
            <strong>${stale ? 'STALE' : 'LIVE'}</strong>
          </div>
        </section>

        <section class="radar-wrap">
          ${this.radarSvg({ coreDistance, lightningDistance, bearing, level, approaching, lightningTriggered, theme })}
          <div class="radar-legend">
            <div><span class="dot home"></span>${this.escape(c.home_label)}</div>
            <div><span class="dot core"></span>Storm core ${coreText}</div>
            <div><span class="dot lightning"></span>Blesk ${lightningText}</div>
          </div>
        </section>

        <section class="metrics">
          ${this.metric('Max dBZ', dbzText, 'mdi:radar')}
          ${this.metric('Jádro', coreText, 'mdi:map-marker-distance')}
          ${this.metric('Blesk', lightningText, 'mdi:flash')}
          ${this.metric('Radar age', frameText, 'mdi:clock-outline')}
        </section>

        <section class="thresholds">
          ${this.threshold('50+', core50, 15)}
          ${this.threshold('55+', core55, 25)}
          ${this.threshold('60+', core60, 15)}
        </section>

        <section class="chips">
          ${this.chip('Radar', source.radar || 'unknown')}
          ${this.chip('Blesky', source.lightning || 'unknown')}
          ${this.chip('Data', stale ? 'stale' : 'fresh')}
          ${confidence == null ? '' : this.chip('Confidence', `${Math.round(confidence)} %`)}
        </section>

        <section class="motion">
          <div>
            <span>Pohyb</span>
            <strong>${approaching ? 'Přibližuje se' : trend === 'receding' ? 'Vzdaluje se' : this.escape(String(trend))}</strong>
          </div>
          <div>
            <span>Trend dBZ</span>
            <strong>${this.escape(String(dbzTrend))}</strong>
          </div>
          <div>
            <span>Rychlost</span>
            <strong>${speed == null ? '—' : `${speed.toFixed(1)} km/h`}</strong>
          </div>
          <div>
            <span>ETA</span>
            <strong>${eta == null ? '—' : `${Math.round(eta)} min`}</strong>
          </div>
        </section>
      </ha-card>
    `;
  }

  state(entityId) {
    return entityId ? this._hass?.states?.[entityId] : undefined;
  }

  safe(value, fallback) {
    if (value == null || ['unknown', 'unavailable', 'none', ''].includes(String(value))) return fallback;
    return String(value);
  }

  number(value) {
    if (value == null || ['unknown', 'unavailable', 'none', ''].includes(String(value))) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  statusLabel(level, stale) {
    if (stale) return 'DATA ISSUE';
    return {
      urgent: 'URGENT RISK',
      warning: 'WARNING',
      watch: 'WATCH',
      none: 'CLEAR',
      unavailable: 'UNAVAILABLE',
    }[level] || String(level).toUpperCase();
  }

  theme(level, stale) {
    if (stale || level === 'unavailable') {
      return { name: 'stale', accent: '#94a3b8', glow: 'rgba(148,163,184,.24)' };
    }
    const map = {
      urgent: { accent: '#fb3b5f', glow: 'rgba(251,59,95,.42)' },
      warning: { accent: '#fb923c', glow: 'rgba(251,146,60,.34)' },
      watch: { accent: '#facc15', glow: 'rgba(250,204,21,.30)' },
      none: { accent: '#34d399', glow: 'rgba(52,211,153,.22)' },
    };
    return { name: level, ...(map[level] || map.none) };
  }

  metric(label, value, icon) {
    return `
      <div class="metric">
        <ha-icon icon="${icon}"></ha-icon>
        <span>${this.escape(label)}</span>
        <strong>${this.escape(value)}</strong>
      </div>
    `;
  }

  threshold(label, distance, warnLimit) {
    const value = distance == null ? '—' : `${distance.toFixed(1)} km`;
    const hot = distance != null && distance <= warnLimit;
    return `<div class="threshold ${hot ? 'hot' : ''}"><span>${label}</span><strong>${value}</strong></div>`;
  }

  chip(label, value) {
    const normalized = String(value).toLowerCase();
    const cls = normalized.includes('ok') || normalized === 'fresh' ? 'ok' : normalized.includes('stale') || normalized.includes('error') || normalized.includes('unavailable') ? 'bad' : 'neutral';
    return `<div class="chip ${cls}"><span>${this.escape(label)}</span><strong>${this.escape(value)}</strong></div>`;
  }

  radarSvg({ coreDistance, lightningDistance, bearing, approaching, lightningTriggered, theme }) {
    const core = this.point(coreDistance, bearing ?? 315, 58);
    const lightning = this.point(lightningDistance, 250, 58);
    const arrow = bearing == null ? '' : `<g transform="rotate(${bearing} 100 100)"><path class="motion-arrow" d="M100 26 L106 44 L100 40 L94 44 Z" /></g>`;
    const coreNode = coreDistance == null ? '' : `<circle class="core-node" cx="${core.x}" cy="${core.y}" r="8"/><circle class="core-pulse" cx="${core.x}" cy="${core.y}" r="14"/>`;
    const lightningNode = lightningDistance == null ? '' : `<path class="lightning-node ${lightningTriggered ? 'triggered' : ''}" d="M${lightning.x - 5} ${lightning.y - 11} L${lightning.x + 3} ${lightning.y - 11} L${lightning.x - 2} ${lightning.y - 1} L${lightning.x + 7} ${lightning.y - 1} L${lightning.x - 5} ${lightning.y + 13} L${lightning.x - 1} ${lightning.y + 2} L${lightning.x - 9} ${lightning.y + 2} Z"/>`;
    return `
      <svg class="radar" viewBox="0 0 200 200" role="img" aria-label="Radar storm visualization">
        <defs>
          <radialGradient id="radarFill" cx="50%" cy="50%" r="60%">
            <stop offset="0%" stop-color="${theme.accent}" stop-opacity="0.22"/>
            <stop offset="65%" stop-color="${theme.accent}" stop-opacity="0.05"/>
            <stop offset="100%" stop-color="#020617" stop-opacity="0"/>
          </radialGradient>
        </defs>
        <circle cx="100" cy="100" r="76" fill="url(#radarFill)"/>
        <circle class="ring" cx="100" cy="100" r="24"/>
        <circle class="ring" cx="100" cy="100" r="48"/>
        <circle class="ring outer" cx="100" cy="100" r="72"/>
        <line class="axis" x1="100" y1="28" x2="100" y2="172"/>
        <line class="axis" x1="28" y1="100" x2="172" y2="100"/>
        ${arrow}
        <circle class="home-node" cx="100" cy="100" r="6"/>
        ${coreNode}
        ${lightningNode}
        <text class="north" x="100" y="20" text-anchor="middle">N</text>
        <text class="range" x="124" y="97">25</text>
        <text class="range" x="149" y="97">50 km</text>
        ${approaching ? '<text class="approach" x="100" y="187" text-anchor="middle">APPROACHING</text>' : ''}
      </svg>
    `;
  }

  point(distance, bearingDeg, maxKm) {
    const clamped = Math.min(Math.max(distance ?? maxKm, 0), maxKm);
    const radius = (clamped / maxKm) * 72;
    const rad = (Number(bearingDeg) - 90) * Math.PI / 180;
    return { x: 100 + Math.cos(rad) * radius, y: 100 + Math.sin(rad) * radius };
  }

  css(theme) {
    return `
      :host { display:block; }
      ha-card.risk-card {
        position: relative;
        overflow: hidden;
        padding: 20px;
        border-radius: 28px;
        color: #f8fafc;
        background:
          linear-gradient(145deg, rgba(15,23,42,.96), rgba(2,6,23,.98)),
          radial-gradient(circle at 25% 0%, ${theme.glow}, transparent 38%);
        border: 1px solid color-mix(in srgb, ${theme.accent} 45%, rgba(148,163,184,.25));
        box-shadow: 0 24px 70px rgba(0,0,0,.38), inset 0 1px 0 rgba(255,255,255,.05);
      }
      .glow { position:absolute; inset:-30% -20% auto auto; width:240px; height:240px; border-radius:999px; background:${theme.glow}; filter: blur(28px); pointer-events:none; }
      .hero { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; position:relative; z-index:1; }
      .eyebrow { color:#94a3b8; font-size:12px; letter-spacing:.16em; text-transform:uppercase; font-weight:800; }
      .status { margin-top:6px; font-size:34px; line-height:1; font-weight:950; letter-spacing:-.04em; color:${theme.accent}; text-shadow:0 0 28px ${theme.glow}; }
      .summary { margin-top:9px; max-width:560px; color:#dbeafe; font-size:14px; line-height:1.35; }
      .badge { min-width:76px; padding:10px 12px; border-radius:18px; background:rgba(15,23,42,.72); border:1px solid rgba(148,163,184,.24); text-align:center; }
      .badge span { display:block; color:#94a3b8; font-size:10px; letter-spacing:.12em; font-weight:800; }
      .badge strong { display:block; margin-top:2px; color:${theme.accent}; font-size:13px; }
      .badge.active { border-color:${theme.accent}; box-shadow:0 0 24px ${theme.glow}; }
      .radar-wrap { display:grid; grid-template-columns:minmax(190px, 1fr) .9fr; gap:14px; align-items:center; margin:18px 0 14px; }
      .radar { width:100%; max-height:260px; min-height:210px; }
      .ring { fill:none; stroke:rgba(148,163,184,.26); stroke-width:1; stroke-dasharray:3 5; }
      .ring.outer { stroke:${theme.accent}; stroke-opacity:.45; }
      .axis { stroke:rgba(148,163,184,.12); stroke-width:1; }
      .home-node { fill:#e2e8f0; stroke:#020617; stroke-width:2; }
      .core-node { fill:${theme.accent}; stroke:#fff7ed; stroke-width:1.5; filter:drop-shadow(0 0 10px ${theme.accent}); }
      .core-pulse { fill:none; stroke:${theme.accent}; stroke-width:2; opacity:.55; }
      .lightning-node { fill:#fbbf24; stroke:#fef3c7; stroke-width:1; opacity:.85; filter:drop-shadow(0 0 8px rgba(251,191,36,.55)); }
      .lightning-node.triggered { fill:#f59e0b; opacity:1; }
      .motion-arrow { fill:${theme.accent}; opacity:.8; }
      .north, .range, .approach { fill:#94a3b8; font-size:9px; font-weight:800; letter-spacing:.08em; }
      .approach { fill:#fb7185; }
      .radar-legend { display:flex; flex-direction:column; gap:10px; color:#cbd5e1; font-size:13px; }
      .radar-legend div { display:flex; align-items:center; gap:9px; padding:9px 10px; border-radius:14px; background:rgba(15,23,42,.55); border:1px solid rgba(148,163,184,.14); }
      .dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
      .dot.home { background:#e2e8f0; } .dot.core { background:${theme.accent}; } .dot.lightning { background:#fbbf24; clip-path: polygon(40% 0, 100% 0, 58% 43%, 100% 43%, 28% 100%, 45% 56%, 0 56%); border-radius:0; }
      .metrics { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:10px; }
      .metric, .threshold, .chip, .motion > div { background:rgba(15,23,42,.68); border:1px solid rgba(148,163,184,.16); border-radius:16px; padding:11px; }
      .metric ha-icon { color:${theme.accent}; width:20px; height:20px; }
      .metric span, .motion span { display:block; color:#94a3b8; font-size:11px; margin-top:4px; }
      .metric strong, .motion strong { display:block; color:#f8fafc; font-size:15px; margin-top:2px; }
      .thresholds { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:10px; margin-top:10px; }
      .threshold { display:flex; justify-content:space-between; align-items:center; }
      .threshold span { color:#94a3b8; font-weight:800; } .threshold strong { color:#e2e8f0; }
      .threshold.hot { border-color:${theme.accent}; background:color-mix(in srgb, ${theme.accent} 14%, rgba(15,23,42,.72)); }
      .chips { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
      .chip { display:flex; gap:7px; align-items:center; padding:8px 10px; border-radius:999px; }
      .chip span { color:#94a3b8; font-size:11px; } .chip strong { font-size:12px; }
      .chip.ok strong { color:#34d399; } .chip.bad strong { color:#fb7185; } .chip.neutral strong { color:#fbbf24; }
      .motion { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:10px; margin-top:12px; }
      @media (max-width: 720px) {
        ha-card.risk-card { padding:16px; border-radius:22px; }
        .status { font-size:28px; }
        .radar-wrap { grid-template-columns:1fr; }
        .radar-legend { display:grid; grid-template-columns:1fr; }
        .metrics, .motion { grid-template-columns:repeat(2, minmax(0, 1fr)); }
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
  name: 'Radar Hail Risk Card',
  description: 'A polished cockpit card for Radar Hail Risk entities.',
});
