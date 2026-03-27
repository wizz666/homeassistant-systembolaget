/**
 * Systembolaget Card v1.4 — röd pulserande dot när stängt
 * Custom Lovelace card for Systembolaget data from Home Assistant sensors.
 *
 * Sensors used:
 *   sensor.systembolaget_butik
 *   sensor.systembolaget_nyheter
 *   sensor.systembolaget_produkt_* (any number)
 */

class SystembolagetCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._config = {};
    this._activeTab = 'nyheter'; // 'nyheter' | 'produkter'
    this._activeCategory = 'alla';
    this._searchTerm = '';
    this._sortBy = 'default'; // 'default' | 'price_asc' | 'price_desc' | 'alc_desc' | 'name'
  }

  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 12; }

  // ── Data helpers ─────────────────────────────────────────────────────────

  _state(id) {
    return this._hass?.states[id]?.state ?? null;
  }

  _attr(id, key) {
    return this._hass?.states[id]?.attributes?.[key] ?? null;
  }

  _valid(v) {
    return v != null && v !== 'unknown' && v !== 'unavailable' && v !== 'None';
  }

  _productSensors() {
    if (!this._hass) return [];
    return Object.keys(this._hass.states)
      .filter(k => k.startsWith('sensor.systembolaget_produkt_'))
      .map(k => this._hass.states[k])
      .filter(s => s.state !== 'Ej hittad');
  }

  _esc(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Visual helpers ────────────────────────────────────────────────────────

  _catIcon(cat) {
    if (!cat) return '🍾';
    const c = cat.toLowerCase();
    if (c.includes('öl') || c.includes('beer')) return '🍺';
    if (c.includes('vin') || c.includes('wine')) return '🍷';
    if (c.includes('sprit') || c.includes('spirit')) return '🥃';
    if (c.includes('cider')) return '🍹';
    if (c.includes('mousserande') || c.includes('champagne')) return '🥂';
    if (c.includes('rosé')) return '🌸';
    if (c.includes('alkoholfritt')) return '💧';
    return '🍾';
  }

  _catColor(cat) {
    if (!cat) return '#90a4ae';
    const c = cat.toLowerCase();
    if (c.includes('öl')) return '#f59e0b';
    if (c.includes('vin')) return '#c084fc';
    if (c.includes('sprit')) return '#f87171';
    if (c.includes('cider')) return '#34d399';
    if (c.includes('mousserande')) return '#fbbf24';
    if (c.includes('rosé')) return '#fb7185';
    if (c.includes('alkoholfritt')) return '#60a5fa';
    return '#94a3b8';
  }

  _stockBadge(inStore, inStock) {
    if (inStore === true)  return `<span class="badge badge-instore">✓ I din butik</span>`;
    if (inStore === false) return `<span class="badge badge-nostore">✕ Ej i butik</span>`;
    if (inStock === false) return `<span class="badge badge-outofstock">Slut</span>`;
    return `<span class="badge badge-unknown">Okänd lager</span>`;
  }

  // ── CSS ───────────────────────────────────────────────────────────────────

  _css() {
    return `
      <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        :host { display: block; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }

        .card {
          background: #0b1810;
          border-radius: 20px;
          overflow: hidden;
          color: #e8f5e9;
        }

        /* ── Header ── */
        .header {
          background: linear-gradient(135deg, #004d38 0%, #006F51 50%, #007a5a 100%);
          padding: 20px 20px 16px;
          position: relative;
          overflow: hidden;
        }
        .header::before {
          content: '';
          position: absolute;
          top: -40px; right: -40px;
          width: 160px; height: 160px;
          background: rgba(245,211,0,0.08);
          border-radius: 50%;
        }
        .header::after {
          content: '';
          position: absolute;
          bottom: -30px; left: 30%;
          width: 100px; height: 100px;
          background: rgba(255,255,255,0.04);
          border-radius: 50%;
        }
        .header-top {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          position: relative;
          z-index: 1;
        }
        .store-name {
          font-size: 1.2rem;
          font-weight: 800;
          color: #fff;
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
        }
        .store-sub {
          font-size: 0.72rem;
          color: rgba(255,255,255,0.55);
          margin-top: 3px;
        }
        .store-hours {
          font-size: 0.78rem;
          color: rgba(245,211,0,0.90);
          margin-top: 5px;
          font-weight: 600;
        }
        .status-pill {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 5px 12px;
          border-radius: 20px;
          font-size: 0.75rem;
          font-weight: 700;
          letter-spacing: 0.05em;
          flex-shrink: 0;
        }
        .status-open {
          background: rgba(105,240,174,0.18);
          color: #69f0ae;
          border: 1px solid rgba(105,240,174,0.30);
        }
        .status-closed {
          background: rgba(239,154,154,0.15);
          color: #ef9a9a;
          border: 1px solid rgba(239,154,154,0.25);
        }
        .live-dot {
          width: 8px; height: 8px;
          border-radius: 50%;
          background: #69f0ae;
          animation: pulse 1.6s ease-in-out infinite;
          flex-shrink: 0;
        }
        .live-dot.closed {
          background: #ef9a9a;
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(1.4); }
        }

        /* ── Tabs ── */
        .tabs {
          display: flex;
          background: #0b1810;
          border-bottom: 1px solid rgba(255,255,255,0.06);
        }
        .tab {
          flex: 1;
          padding: 12px 8px;
          text-align: center;
          font-size: 0.78rem;
          font-weight: 600;
          color: rgba(255,255,255,0.40);
          cursor: pointer;
          border-bottom: 2px solid transparent;
          transition: color 0.2s, border-color 0.2s;
          user-select: none;
        }
        .tab.active {
          color: #F5D300;
          border-bottom-color: #F5D300;
        }
        .tab:hover:not(.active) {
          color: rgba(255,255,255,0.70);
        }

        /* ── Category filter ── */
        .cat-filter {
          display: flex;
          gap: 6px;
          padding: 10px 14px;
          overflow-x: auto;
          scrollbar-width: none;
          background: #0d1a14;
          border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .cat-filter::-webkit-scrollbar { display: none; }
        .cat-chip {
          flex-shrink: 0;
          padding: 4px 10px;
          border-radius: 12px;
          font-size: 0.70rem;
          font-weight: 600;
          cursor: pointer;
          border: 1px solid rgba(255,255,255,0.10);
          color: rgba(255,255,255,0.50);
          background: transparent;
          transition: all 0.15s;
          user-select: none;
        }
        .cat-chip.active {
          background: rgba(245,211,0,0.12);
          border-color: rgba(245,211,0,0.40);
          color: #F5D300;
        }

        /* ── Search + Sort bar ── */
        .search-sort {
          display: flex;
          gap: 8px;
          padding: 10px 12px;
          background: #0d1a14;
          border-bottom: 1px solid rgba(255,255,255,0.05);
          align-items: center;
        }
        .search-wrap {
          flex: 1;
          position: relative;
          display: flex;
          align-items: center;
        }
        .search-icon {
          position: absolute;
          left: 9px;
          font-size: 0.80rem;
          color: rgba(255,255,255,0.30);
          pointer-events: none;
        }
        .search-input {
          width: 100%;
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.10);
          border-radius: 8px;
          padding: 6px 8px 6px 28px;
          color: rgba(255,255,255,0.85);
          font-size: 0.78rem;
          outline: none;
          transition: border-color 0.15s;
        }
        .search-input::placeholder { color: rgba(255,255,255,0.28); }
        .search-input:focus { border-color: rgba(245,211,0,0.40); }
        .search-clear {
          position: absolute;
          right: 8px;
          font-size: 0.75rem;
          color: rgba(255,255,255,0.35);
          cursor: pointer;
          display: none;
          padding: 2px;
        }
        .search-clear.visible { display: block; }
        .sort-select {
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.10);
          border-radius: 8px;
          padding: 6px 8px;
          color: rgba(255,255,255,0.70);
          font-size: 0.72rem;
          outline: none;
          cursor: pointer;
          flex-shrink: 0;
        }
        .sort-select option {
          background: #1a2e25;
          color: white;
        }
        .result-count {
          font-size: 0.62rem;
          color: rgba(255,255,255,0.28);
          padding: 0 14px 6px;
          background: #0d1a14;
        }

        /* ── Content ── */
        .content {
          padding: 12px;
        }
        .section-label {
          font-size: 0.65rem;
          font-weight: 700;
          letter-spacing: 0.10em;
          text-transform: uppercase;
          color: rgba(255,255,255,0.30);
          margin-bottom: 8px;
          padding: 0 2px;
        }

        /* ── Nyheter list ── */
        .arrivals {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        .arrival-row {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 9px 10px;
          border-radius: 10px;
          background: rgba(255,255,255,0.03);
          transition: background 0.15s;
        }
        .arrival-row:hover {
          background: rgba(255,255,255,0.06);
        }
        .arrival-icon {
          font-size: 1.3rem;
          flex-shrink: 0;
          width: 28px;
          text-align: center;
        }
        .arrival-info {
          flex: 1;
          min-width: 0;
        }
        .arrival-name {
          font-size: 0.82rem;
          font-weight: 600;
          color: rgba(255,255,255,0.88);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .arrival-meta {
          font-size: 0.68rem;
          color: rgba(255,255,255,0.35);
          margin-top: 1px;
        }
        .arrival-cat {
          font-size: 0.60rem;
          font-weight: 700;
          padding: 2px 6px;
          border-radius: 6px;
          background: rgba(255,255,255,0.07);
          flex-shrink: 0;
        }
        .arrival-price {
          font-size: 0.88rem;
          font-weight: 800;
          color: #F5D300;
          flex-shrink: 0;
          min-width: 54px;
          text-align: right;
        }

        /* ── Product cards ── */
        .products-grid {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .product-card {
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 14px;
          overflow: hidden;
          transition: border-color 0.2s;
        }
        .product-card:hover {
          border-color: rgba(245,211,0,0.20);
        }
        .product-card.instore {
          border-color: rgba(105,240,174,0.20);
        }
        .product-inner {
          display: flex;
          align-items: stretch;
          gap: 0;
        }
        .product-img {
          width: 72px;
          min-height: 80px;
          flex-shrink: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(0,0,0,0.25);
          overflow: hidden;
          border-radius: 14px 0 0 14px;
        }
        .product-img img {
          width: 52px;
          height: 72px;
          object-fit: contain;
          opacity: 0.92;
        }
        .product-img .fallback-icon {
          font-size: 2rem;
          opacity: 0.5;
        }
        .product-body {
          flex: 1;
          padding: 11px 12px;
          min-width: 0;
        }
        .product-name {
          font-size: 0.88rem;
          font-weight: 700;
          color: #fff;
          line-height: 1.3;
          margin-bottom: 4px;
        }
        .product-meta {
          font-size: 0.68rem;
          color: rgba(255,255,255,0.40);
          margin-bottom: 6px;
          line-height: 1.5;
        }
        .product-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
        }
        .product-price {
          font-size: 1.15rem;
          font-weight: 900;
          color: #F5D300;
        }

        /* ── Badges ── */
        .badge {
          display: inline-flex;
          align-items: center;
          padding: 3px 8px;
          border-radius: 8px;
          font-size: 0.65rem;
          font-weight: 700;
          letter-spacing: 0.03em;
        }
        .badge-instore   { background: rgba(105,240,174,0.15); color: #69f0ae; border: 1px solid rgba(105,240,174,0.25); }
        .badge-nostore   { background: rgba(239,154,154,0.12); color: #ef9a9a; border: 1px solid rgba(239,154,154,0.20); }
        .badge-outofstock { background: rgba(100,116,139,0.20); color: #94a3b8; border: 1px solid rgba(100,116,139,0.20); }
        .badge-unknown   { background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.35); border: 1px solid rgba(255,255,255,0.08); }

        /* ── Empty states ── */
        .empty {
          text-align: center;
          padding: 28px 16px;
          color: rgba(255,255,255,0.25);
          font-size: 0.80rem;
          line-height: 1.7;
        }
        .empty-icon { font-size: 2rem; margin-bottom: 8px; }

        /* ── Footer ── */
        .footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 10px 14px;
          border-top: 1px solid rgba(255,255,255,0.05);
          background: #080f0a;
        }
        .footer-updated {
          font-size: 0.70rem;
          color: rgba(255,255,255,0.75);
        }
        .refresh-btn {
          display: flex;
          align-items: center;
          gap: 5px;
          padding: 5px 12px;
          border-radius: 8px;
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.08);
          color: rgba(255,255,255,0.55);
          font-size: 0.70rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s;
          user-select: none;
        }
        .refresh-btn:hover {
          background: rgba(255,255,255,0.09);
          color: rgba(255,255,255,0.80);
          border-color: rgba(255,255,255,0.15);
        }

        /* ── Divider ── */
        .divider { height: 1px; background: rgba(255,255,255,0.05); margin: 10px 0; }
      </style>
    `;
  }

  // ── Section: Header ───────────────────────────────────────────────────────

  _buildHeader() {
    const storeState  = this._state('sensor.systembolaget_butik');
    const name        = this._attr('sensor.systembolaget_butik', 'name') || 'Systembolaget';
    const address     = this._attr('sensor.systembolaget_butik', 'address') || '';
    const city        = this._attr('sensor.systembolaget_butik', 'city') || '';
    const hours       = this._attr('sensor.systembolaget_butik', 'today_hours') || '–';
    const isOpen      = storeState === 'Öppet';

    const addrLine = [address, city].filter(Boolean).join(', ');
    const statusPill = isOpen
      ? `<div class="status-pill status-open"><div class="live-dot"></div>ÖPPET</div>`
      : `<div class="status-pill status-closed"><div class="live-dot closed"></div>STÄNGT</div>`;

    return `
      <div class="header">
        <div class="header-top">
          <div>
            <div class="store-name">🍷 ${this._esc(name)}</div>
            ${addrLine ? `<div class="store-sub">${this._esc(addrLine)}</div>` : ''}
            ${hours !== '–' ? `<div class="store-hours">⏰ Idag: ${this._esc(hours)}</div>` : ''}
          </div>
          ${statusPill}
        </div>
      </div>`;
  }

  // ── Section: Tabs ─────────────────────────────────────────────────────────

  _buildTabs() {
    const nyhetCount    = this._attr('sensor.systembolaget_nyheter', 'count') ?? 0;
    const produktCount  = this._productSensors().length;

    const tabs = [
      { id: 'nyheter',   label: `🆕 Nyheter  ${nyhetCount > 0 ? `<span style="color:#F5D300;">(${nyhetCount})</span>` : ''}` },
      { id: 'produkter', label: `📦 Bevakade ${produktCount > 0 ? `<span style="color:#69f0ae;">(${produktCount})</span>` : ''}` },
    ];

    return `
      <div class="tabs">
        ${tabs.map(t => `
          <div class="tab ${this._activeTab === t.id ? 'active' : ''}" data-tab="${t.id}">
            ${t.label}
          </div>`).join('')}
      </div>`;
  }

  // ── Section: Category filter (only for nyheter tab) ───────────────────────

  _buildCatFilter(products) {
    const cats = ['alla', ...new Set(products.map(p => p.category).filter(Boolean))];
    return `
      <div class="cat-filter">
        ${cats.map(c => `
          <div class="cat-chip ${this._activeCategory === c ? 'active' : ''}" data-cat="${this._esc(c)}">
            ${this._catIcon(c === 'alla' ? null : c)} ${c === 'alla' ? 'Alla' : this._esc(c)}
          </div>`).join('')}
      </div>`;
  }

  // ── Section: New Arrivals ─────────────────────────────────────────────────

  _sortProducts(products) {
    const list = [...products];
    switch (this._sortBy) {
      case 'price_asc':   return list.sort((a, b) => (a.price || 0) - (b.price || 0));
      case 'price_desc':  return list.sort((a, b) => (b.price || 0) - (a.price || 0));
      case 'alc_desc':    return list.sort((a, b) => (b.alcohol_pct || 0) - (a.alcohol_pct || 0));
      case 'name':        return list.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'sv'));
      default:            return list; // API order = launch date desc
    }
  }

  _buildSearchSort() {
    const hasSearch = this._searchTerm.length > 0;
    return `
      <div class="search-sort">
        <div class="search-wrap">
          <span class="search-icon">🔍</span>
          <input
            class="search-input"
            id="search-input"
            type="text"
            placeholder="Sök produkt, land, druva…"
            value="${this._esc(this._searchTerm)}"
            autocomplete="off"
          />
          <span class="search-clear ${hasSearch ? 'visible' : ''}" id="search-clear">✕</span>
        </div>
        <select class="sort-select" id="sort-select">
          <option value="default"    ${this._sortBy === 'default'    ? 'selected' : ''}>Nyast</option>
          <option value="price_asc"  ${this._sortBy === 'price_asc'  ? 'selected' : ''}>Pris ↑</option>
          <option value="price_desc" ${this._sortBy === 'price_desc' ? 'selected' : ''}>Pris ↓</option>
          <option value="alc_desc"   ${this._sortBy === 'alc_desc'   ? 'selected' : ''}>Alkohol ↓</option>
          <option value="name"       ${this._sortBy === 'name'       ? 'selected' : ''}>Namn A–Ö</option>
        </select>
      </div>`;
  }

  _buildNyheter() {
    const allProducts = this._attr('sensor.systembolaget_nyheter', 'products') || [];

    if (allProducts.length === 0) {
      return `
        <div class="content">
          <div class="empty">
            <div class="empty-icon">🍾</div>
            Inga nyheter hämtade ännu.<br>Klicka Uppdatera nedan.
          </div>
        </div>`;
    }

    // 1. Category filter
    let filtered = this._activeCategory === 'alla'
      ? allProducts
      : allProducts.filter(p => p.category === this._activeCategory);

    // 2. Search filter
    const term = this._searchTerm.toLowerCase().trim();
    if (term) {
      filtered = filtered.filter(p =>
        (p.name        || '').toLowerCase().includes(term) ||
        (p.country     || '').toLowerCase().includes(term) ||
        (p.producer    || '').toLowerCase().includes(term) ||
        (p.subcategory || '').toLowerCase().includes(term) ||
        (p.category    || '').toLowerCase().includes(term)
      );
    }

    // 3. Sort
    const sorted = this._sortProducts(filtered);

    const noResults = sorted.length === 0 ? `
      <div class="empty">
        <div class="empty-icon">🔍</div>
        Inga produkter matchar "${this._esc(this._searchTerm)}".
      </div>` : '';

    const rows = sorted.slice(0, 30).map(p => {
      const name     = p.name || '–';
      const price    = p.price ? `${p.price} kr` : '–';
      const meta     = [
        p.country,
        p.alcohol_pct ? `${p.alcohol_pct}%` : null,
        p.volume_ml   ? `${p.volume_ml} ml` : null,
        p.subcategory || null,
      ].filter(Boolean).join(' · ');
      const catColor = this._catColor(p.category);

      // Highlight search match in name
      let displayName = this._esc(name);
      if (term && name.toLowerCase().includes(term)) {
        const idx = name.toLowerCase().indexOf(term);
        const pre  = this._esc(name.slice(0, idx));
        const match = this._esc(name.slice(idx, idx + term.length));
        const post  = this._esc(name.slice(idx + term.length));
        displayName = `${pre}<mark style="background:rgba(245,211,0,0.30);color:#F5D300;border-radius:2px;">${match}</mark>${post}`;
      }

      return `
        <div class="arrival-row">
          <div class="arrival-icon">${this._catIcon(p.category)}</div>
          <div class="arrival-info">
            <div class="arrival-name">${displayName}</div>
            ${meta ? `<div class="arrival-meta">${this._esc(meta)}</div>` : ''}
          </div>
          <div class="arrival-cat" style="color:${catColor};">${this._esc(p.subcategory || p.category || '')}</div>
          <div class="arrival-price">${this._esc(price)}</div>
        </div>`;
    }).join('');

    const countLabel = term
      ? `${sorted.length} träff${sorted.length !== 1 ? 'ar' : ''} för "${this._esc(this._searchTerm)}"`
      : `${sorted.length} produkter`;

    return `
      ${this._buildCatFilter(allProducts)}
      ${this._buildSearchSort()}
      ${sorted.length > 0 ? `<div class="result-count">${countLabel}</div>` : ''}
      <div class="content">
        ${noResults}
        <div class="arrivals">${rows}</div>
      </div>`;
  }

  // ── Section: Watched Products ─────────────────────────────────────────────

  _buildProdukter() {
    const sensors = this._productSensors();

    if (sensors.length === 0) {
      return `
        <div class="content">
          <div class="empty">
            <div class="empty-icon">📦</div>
            Inga bevakade produkter.<br>
            Lägg till produkt-ID:n via<br>
            <strong>Inställningar → Systembolaget → Konfigurera</strong>
          </div>
        </div>`;
    }

    const cards = sensors.map(s => {
      const attrs    = s.attributes || {};
      const name     = attrs.name || s.entity_id.replace('sensor.systembolaget_produkt_', 'ID ');
      const price    = s.state !== 'Ej hittad' ? s.state : '–';
      const inStore  = attrs.in_store_assortment;
      const inStock  = attrs.in_stock;
      const pid      = attrs.product_id || '';
      const imgUrl   = pid ? `https://product-cdn.systembolaget.se/productimages/${pid}/${pid}.png` : '';
      const meta     = [
        attrs.country,
        attrs.alcohol_pct != null ? `${attrs.alcohol_pct}%` : null,
        attrs.volume_ml ? `${attrs.volume_ml} ml` : null,
        attrs.producer,
      ].filter(Boolean).join(' · ');
      const vintage  = attrs.vintage && attrs.vintage !== '' ? ` ${attrs.vintage}` : '';
      const organic  = attrs.is_organic ? ' 🌿' : '';
      const isInStore = inStore === true;

      return `
        <div class="product-card ${isInStore ? 'instore' : ''}">
          <div class="product-inner">
            <div class="product-img">
              ${imgUrl
                ? `<img src="${this._esc(imgUrl)}" alt="" onerror="this.style.display='none';this.nextElementSibling.style.display='block';">
                   <div class="fallback-icon" style="display:none;">${this._catIcon(attrs.category)}</div>`
                : `<div class="fallback-icon">${this._catIcon(attrs.category)}</div>`}
            </div>
            <div class="product-body">
              <div class="product-name">${this._esc(name)}${this._esc(vintage)}${organic}</div>
              ${meta ? `<div class="product-meta">${this._esc(meta)}</div>` : ''}
              <div class="product-footer">
                <div class="product-price">${this._esc(price)}</div>
                ${this._stockBadge(inStore, inStock)}
              </div>
            </div>
          </div>
        </div>`;
    }).join('');

    return `
      <div class="content">
        <div class="section-label">${sensors.length} bevakade produkter</div>
        <div class="products-grid">${cards}</div>
      </div>`;
  }

  // ── Footer ────────────────────────────────────────────────────────────────

  _buildFooter() {
    const storeId = this._attr('sensor.systembolaget_butik', 'store_id') || '';
    return `
      <div class="footer">
        <div class="footer-updated">
          Butik-ID: ${this._esc(storeId)} · Uppdateras varje timme
        </div>
        <div class="refresh-btn" id="refresh-btn">
          ↺ Uppdatera
        </div>
      </div>`;
  }

  // ── Main render ───────────────────────────────────────────────────────────

  _render() {
    if (!this._hass) return;

    const html = `
      ${this._css()}
      <div class="card">
        ${this._buildHeader()}
        ${this._buildTabs()}
        ${this._activeTab === 'nyheter' ? this._buildNyheter() : this._buildProdukter()}
        ${this._buildFooter()}
      </div>`;

    this.shadowRoot.innerHTML = html;
    this._attachEvents();
  }

  _attachEvents() {
    // Tab switching
    this.shadowRoot.querySelectorAll('.tab').forEach(el => {
      el.addEventListener('click', () => {
        this._activeTab = el.dataset.tab;
        this._render();
      });
    });

    // Category filter
    this.shadowRoot.querySelectorAll('.cat-chip').forEach(el => {
      el.addEventListener('click', () => {
        this._activeCategory = el.dataset.cat;
        this._render();
      });
    });

    // Search input
    const searchInput = this.shadowRoot.getElementById('search-input');
    if (searchInput) {
      searchInput.addEventListener('input', e => {
        this._searchTerm = e.target.value;
        this._render();
        // Re-focus and restore cursor position after re-render
        const newInput = this.shadowRoot.getElementById('search-input');
        if (newInput) {
          const len = newInput.value.length;
          newInput.focus();
          newInput.setSelectionRange(len, len);
        }
      });
    }

    // Search clear
    const searchClear = this.shadowRoot.getElementById('search-clear');
    if (searchClear) {
      searchClear.addEventListener('click', () => {
        this._searchTerm = '';
        this._render();
        const newInput = this.shadowRoot.getElementById('search-input');
        if (newInput) newInput.focus();
      });
    }

    // Sort select
    const sortSelect = this.shadowRoot.getElementById('sort-select');
    if (sortSelect) {
      sortSelect.addEventListener('change', e => {
        this._sortBy = e.target.value;
        this._render();
      });
    }

    // Refresh
    const btn = this.shadowRoot.getElementById('refresh-btn');
    if (btn) {
      btn.addEventListener('click', () => {
        if (!this._hass) return;
        this._hass.callService('systembolaget', 'refresh', {});
        btn.textContent = '✓ Skickat';
        setTimeout(() => { if (btn) btn.textContent = '↺ Uppdatera'; }, 2000);
      });
    }
  }
}

customElements.define('systembolaget-card', SystembolagetCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'systembolaget-card',
  name: 'Systembolaget Card',
  description: 'Nyheter, butiksinfo och bevakade produkter från Systembolaget.',
  preview: false,
});
