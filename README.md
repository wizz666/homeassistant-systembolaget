# Systembolaget för Home Assistant

Integrera Systembolaget i Home Assistant — bevaka produkter, se veckans nyheter och kolla om din butik är öppen, direkt i din dashboard.

> Inga konton, ingen API-nyckel, ingen registrering. Fungerar direkt.

---

## Vad gör integrationen?

Integrationen skapar **sensorer** i Home Assistant med data från Systembolaget. Dessa sensorer kan visas på din dashboard, trigga automationer och skicka notiser.

**Tre typer av sensorer skapas automatiskt:**

| Sensor | Vad den visar |
|--------|---------------|
| `sensor.systembolaget_nyheter` | Antal nya produkter denna vecka |
| `sensor.systembolaget_butik` | Om din butik är öppen eller stängd just nu |
| `sensor.systembolaget_produkt_XXXX` | Pris och om produkten finns i din butik (en per bevakad produkt) |

---

## Installation

### Via HACS (rekommenderat)

1. Öppna HACS i Home Assistant
2. Gå till **Integrationer** → klicka på de tre punkterna (⋮) → **Anpassade arkiv**
3. Lägg till: `https://github.com/wizz666/homeassistant-systembolaget` (kategori: Integration)
4. Klicka **Lägg till** → Sök efter **Systembolaget** → **Ladda ned**
5. Starta om Home Assistant
6. Gå till **Inställningar → Enheter & tjänster → + Lägg till integration → Systembolaget**

### Manuell installation

1. Kopiera mappen `custom_components/systembolaget/` till din HA-config-mapp
2. Starta om Home Assistant
3. Gå till **Inställningar → Enheter & tjänster → + Lägg till integration → Systembolaget**

---

## Setup-guide (steg för steg)

### Steg 1 — Hitta din butik

När du lägger till integrationen visas detta formulär:

![Steg 1](docs/step1.png)

Skriv in din stad (ex. "Göteborg") och klicka **Nästa**. Integrationen söker automatiskt efter alla Systembolaget-butiker i din stad.

### Steg 2 — Välj butik

En lista med butiker visas. Välj din närmaste butik.

Lagerstatus för bevakade produkter visar sedan om produkten finns på **just den butiken**.

### Steg 3 — Lägg till produkter att bevaka (valfritt)

Du kan lägga till produkt-ID:n för produkter du vill hålla koll på.

**Hur hittar jag produkt-ID?**

Gå till [systembolaget.se](https://www.systembolaget.se) och klicka på en produkt. Titta på URL:en — siffrorna i slutet är produkt-ID:t:

```
https://www.systembolaget.se/produkt/ol/norrlands-guld-2512/
                                                        ^^^^
                                                   Produkt-ID: 2512
```

Alternativt kan du söka direkt från Home Assistant efter installationen (se tjänster nedan).

Fyll i ett eller flera ID:n separerade med kommatecken: `2512, 7348, 1337`

---

## Sensorer i detalj

### `sensor.systembolaget_nyheter`
**State:** Antal nya produkter (ex. `14 produkter`)

**Attribut:**
```yaml
products:
  - name: "Norrlands Guld Export"
    product_id: "2512"
    price: 16.90
    category: "Öl"
    alcohol_pct: 5.3
    volume_ml: 500
    country: "Sverige"
    is_organic: false
count: 14
```

### `sensor.systembolaget_butik`
**State:** `Öppen` eller `Stängd`

**Attribut:**
```yaml
name: "Systembolaget Avenyn"
address: "Kungsportsavenyn 42"
city: "Göteborg"
today_hours: "10:00–20:00"
is_open: true
store_id: "0620"
```

### `sensor.systembolaget_produkt_2512`
**State:** `16.90 kr` (eller `Ej hittad`)

**Attribut:**
```yaml
name: "Norrlands Guld Export"
price: 16.90
category: "Öl"
subcategory: "Lager"
alcohol_pct: 5.3
volume_ml: 500
country: "Sverige"
producer: "Spendrups"
in_stock: true              # finns globalt
in_store_assortment: true   # finns på din valda butik
is_organic: false
is_discontinued: false
image_url: "https://product-cdn.systembolaget.se/productimages/2512/2512.png"
```

---

## Dashboard-exempel

Klistra in detta i din Lovelace-dashboard (Redigera dashboard → Lägg till kort → Manuellt):

### Butiksöversikt

```yaml
type: entities
title: Systembolaget
entities:
  - entity: sensor.systembolaget_butik
    name: Butiksläge
    icon: mdi:store
  - type: attribute
    entity: sensor.systembolaget_butik
    attribute: today_hours
    name: Öppettider idag
    icon: mdi:clock-outline
  - entity: sensor.systembolaget_nyheter
    name: Nya produkter denna vecka
    icon: mdi:new-box
```

### Bevakad produkt som button-card

```yaml
type: custom:button-card
entity: sensor.systembolaget_produkt_2512
name: "[[[ return entity.attributes.name ]]]"
label: "[[[ return entity.attributes.in_store_assortment ? '✅ Finns i butik' : '❌ Ej i butik' ]]]"
show_label: true
show_state: true
icon: mdi:glass-mug-variant
color_type: card
color: "[[[ return entity.attributes.in_store_assortment ? 'green' : 'grey' ]]]"
```

### Automationsexempel — notis när bevakad produkt kommer in i butik

```yaml
automation:
  - alias: "Systembolaget — produkt tillbaka i butik"
    trigger:
      - platform: state
        entity_id: sensor.systembolaget_produkt_2512
        attribute: in_store_assortment
        to: true
        from: false
    action:
      - service: notify.mobile_app_din_telefon
        data:
          title: "🍺 Systembolaget"
          message: >
            {{ state_attr('sensor.systembolaget_produkt_2512', 'name') }}
            finns nu på {{ state_attr('sensor.systembolaget_butik', 'name') }}!
            Pris: {{ states('sensor.systembolaget_produkt_2512') }}
```

### Automationsexempel — fredag-notis med veckans nyheter

```yaml
automation:
  - alias: "Systembolaget — veckans nyheter på fredag"
    trigger:
      - platform: time
        at: "10:00:00"
    condition:
      - condition: template
        value_template: "{{ now().weekday() == 4 }}"
    action:
      - service: notify.mobile_app_din_telefon
        data:
          title: "🍷 Veckans nyheter på Systembolaget"
          message: >
            {% set p = state_attr('sensor.systembolaget_nyheter', 'products') %}
            {{ states('sensor.systembolaget_nyheter') }} nya produkter.
            {% for prod in p[:5] %}
            • {{ prod.name }} — {{ prod.price }} kr
            {% endfor %}
```

---

## Tjänster / Actions

### `systembolaget.refresh`
Hämtar ny data omedelbart utan att vänta på nästa automatiska uppdatering.

### `systembolaget.search_product`
Söker produkter och visar resultat som ett meddelande i HA. Perfekt för att hitta produkt-ID:n.

```yaml
service: systembolaget.search_product
data:
  query: "Mackmyra"
  size: 10
```

### `systembolaget.search_store`
Söker butiker och visar ID:n. Användbart om du vill byta butik utan att installera om.

```yaml
service: systembolaget.search_store
data:
  city: "Stockholm"
```

---

## Kategorier för Nyheter

Standard är `Vin,Öl,Sprit`. Tillgängliga kategorier:

- `Vin`
- `Öl`
- `Sprit`
- `Cider`
- `Alkoholfritt`
- `Mousserande vin`
- `Rosé`

---

## Felsökning

**Inga butiker hittades vid setup**
→ Prova en annan stavning av staden, eller ett kringliggande stadsnamn.

**Produkten visas som "Ej hittad"**
→ Kontrollera produkt-ID:t via systembolaget.se (siffrorna i URL:en). Kör `systembolaget.search_product` för att bekräfta.

**`in_store_assortment` är alltid `false`**
→ Produkten kanske inte ingår i din butiks sortiment. Prova att söka på butikens webbsida. Eller välj en annan butik via Konfigurera.

**Nyheter-listan är tom**
→ Kontrollera kategoristavningen — det är skiftlägeskänsligt: `Vin`, `Öl`, `Sprit`.

**Butiken visar alltid Stängd**
→ Kontrollera att rätt butik valdes. Kör `systembolaget.search_store` och jämför ID:t med inställningarna.

---

## Bidra

Öppna ett [issue](https://github.com/wizz666/homeassistant-systembolaget/issues) för buggar och önskemål. PR:ar välkomna!
