# 📖 Business Context & Definitions

This document explains the business logic, metrics, and module definitions used in the Homepage Performance application.

---

## 🗓️ Walmart Fiscal Calendar

### Fiscal Week
- **Walmart fiscal week runs SATURDAY through FRIDAY** (NOT Monday-Sunday)
- Example: WK42 = Sat Nov 15 through Fri Nov 21

### WBR Reporting Windows
| Report Type | Window |
|-------------|--------|
| Standard WBR (Homepage Performance) | Saturday → Tuesday (4 days) |
| Messaging Performance WBR | Monday → Sunday (full 7-day week) |

---

## 📊 Metrics Definitions

### Core Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| **Impressions** | `SUM(module_view_count)` | Number of times a module was viewed |
| **Clicks** | `SUM(overall_click_count)` | Total clicks on the module |
| **CTR** | `clicks / impressions × 100` | Click-through rate percentage |
| **ATC** | `SUM(total_atc_count)` | Add-to-cart count |
| **ATC Rate** | `atc / impressions × 1000` | ATC per 1,000 impressions |
| **Exit Rate** | `(1 - all_clicks_count_flag / asset_clicks_count) × 100` | % of users who left without engaging further |
| **GMV** | `SUM(total_gmv)` | Gross Merchandise Value |

### Share Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| **Clicks %** | `module_clicks / total_clicks × 100` | Share of total homepage clicks |
| **ATC %** | `module_atc / total_atc × 100` | Share of total homepage ATC |
| **SOV** | `message_impressions / total_impressions × 100` | Share of Voice |

### Week-over-Week (WoW)

| Metric | Formula | Description |
|--------|---------|-------------|
| **CTR WoW %** | `(current_ctr / prev_ctr - 1) × 100` | CTR change from previous week |
| **Clicks WoW %** | `(current_clicks / prev_clicks - 1) × 100` | Clicks change from previous week |
| **ATC WoW %** | `(current_atc / prev_atc - 1) × 100` | ATC change from previous week |

---

## 🏷️ Content Type Classification

We filter for **Merch content only** to exclude WMC (Walmart Media Connect) ads.

### Content Type Logic

```sql
CASE
  -- Explicit Ads
  WHEN LOWER(content_served_by) = 'ads' THEN 'WMC'
  
  -- Explicit Merch
  WHEN disable_content_personalization LIKE '%true%' THEN 'Merch'
  
  -- Legacy HPOV WMC (before March 2025)
  WHEN disable_content_personalization LIKE '%false%'
       AND personalized_asset = 'default'
       AND session_start_dt <= '2025-03-01'
       AND content_zone = 'contentzone3'
       AND hp_module_name IN ('autoscroll card 1','autoscroll card 2','autoscroll card 3')
  THEN 'WMC'
  
  -- BTF Banner WMC
  WHEN disable_content_personalization LIKE '%false%'
       AND personalized_asset = 'default'
       AND (
         (content_zone IN ('contentzone8','contentzone9') AND hp_module_name = 'adjustable banner small')
         OR
         (content_zone IN ('contentzone10','contentzone11') AND hp_module_name = 'triple pack small')
       )
  THEN 'WMC'
  
  ELSE 'Merch'
END
```

---

## 📦 Module Buckets

Modules are grouped into strategic buckets for WBR reporting:

| Bucket | Modules Included | Location |
|--------|------------------|----------|
| **HPOV** | AutoScroll Cards 1-5 | Above the Fold |
| **ATF Carousels (SIG)** | SIG Cards 1-6 | contentzone3-6 |
| **ATF Carousels** | Other carousels | contentzone3-6 |
| **Walmart+ Banner** | W+ promotional banner | ATF (non-utility) |
| **Utility** | Utility-type modules | Various |
| **BTF Navigation** | Navigation modules | Below the Fold |
| **BTF Content** | Content modules | Below the Fold |
| **BTF Carousels** | Carousel modules | Below the Fold |

### ATF Zones (Above the Fold)
```
contentzone1, contentzone2, contentzone3, contentzone4, contentzone5, contentzone6,
topcontentzone1, topcontentzone2, topcontentzone3, topcontentzone4, topcontentzone5, topcontentzone6
```

---

## 📱 HPOV (Homepage Own Voice)

### Definition
AutoScroll Cards 1-5 — the primary messaging carousel at the top of the Walmart homepage.

### Key Characteristics
- 5 card positions
- Horizontal scrolling
- Primary vehicle for promotional messaging
- Highest visibility location on homepage

### Services Grouping
Some messages are grouped as "Services" for reporting:
- Financial services
- Subscription services
- Delivery services
- Healthcare services

---

## 🛒 SIG (Scrollable Item Grid)

### Definition
SIG Cards 1-6 — product carousels showing personalized item recommendations.

### Key Characteristics
- 6 card positions in ATF
- Category-based product carousels
- Personalized recommendations
- High engagement potential

### Common SIG Categories
| Full Name | Short Name |
|-----------|------------|
| Household Essentials | HH Essentials |
| Tech Rollbacks | Tech |
| Beauty Rollbacks | Beauty |
| Home Rollbacks | Home |
| Rollbacks and More | R&M |
| Jump Right Back In | CYS (Continue Your Shopping) |
| Patio and Garden | Patio & Garden |
| Gaming and Media | Gaming |
| Arts and Crafts | Arts & Crafts |

---

## 🎯 FYTD Benchmark

### Definition
Fiscal Year-to-Date benchmark CTR for comparing message performance.

### Calculation
```sql
SELECT SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) * 100
FROM hp_summary_asset
WHERE session_start_dt >= '2026-02-01'  -- FY26 start
  AND Content_Type = 'Merch'
  AND hp_module_name LIKE 'autoscroll card%'  -- or 'sig card%'
```

### Typical Benchmarks
| Module Type | FYTD CTR |
|-------------|----------|
| HPOV (AutoScroll) | ~0.22% |
| SIG Cards | ~1.16% |

---

## 📈 Engagement Classification

Messages are classified into engagement tiers based on benchmark comparison:

| Tier | Benchmark Index | Meaning |
|------|-----------------|---------|
| **High Engagement** | ≥ 1.3 | Outperforming by 30%+ |
| **Avg Engagement** | ≥ 0.7 | Within 30% of benchmark |
| **Trailing Engagement** | < 0.7 | Underperforming by 30%+ |

### Benchmark Index Formula
```
benchmark_index = message_ctr / weighted_location_benchmark_ctr
```

---

## 🔍 Bubble Chart Quadrants

The bubble chart plots ATC Rate (X) vs Exit Rate (Y):

| Quadrant | ATC | Exit | Classification |
|----------|-----|------|----------------|
| **Top Right** | High | Low | 🟢 Top Performer |
| **Bottom Left** | Low | High | 🔴 Low Performer |
| **Other** | Mixed | Mixed | ⚪ Neutral |

### Interpretation
- **Large bubble** = High impressions
- **Right position** = High ATC rate (good)
- **Top position** = Low exit rate (good, since Y-axis is inverted)

---

## 🎨 Walmart Brand Colors

| Color | Hex | Usage |
|-------|-----|-------|
| Walmart Blue | `#0071CE` | Primary brand |
| Walmart Yellow | `#FFC220` | Accent/highlight |
| Walmart Navy | `#041E42` | Headers |
| Green | `#22C55E` | Positive indicators |
| Red | `#EA1100` | Negative indicators |

---

## 📋 Utility Modules Reference

These modules are classified as "Utility" in the module bucket:
- Order Status Tracker
- Review Banner
- Credit Card Banner
- Feedback
- Amend Banner

---

## 🔐 Data Access

### Required Permissions
- BigQuery access to `wmt-site-content-strategy` project
- Read access to `scs_production.hp_summary_asset` table

### Platform Filters
| Platform | experience_lvl2 Value |
|----------|----------------------|
| iOS | `'App: iOS'` |
| Android | `'App: Android'` |
| Desktop | `'Web: Desktop'` |
| mWeb | `'Web: mWeb'` |

**Note**: Default analysis uses iOS + Android only.
