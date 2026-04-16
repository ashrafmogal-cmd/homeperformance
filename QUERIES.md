# 📝 BigQuery Queries Reference

This document contains all BigQuery queries used in the Homepage Performance application.

---

## 🗄️ Data Source

| Property | Value |
|----------|-------|
| **Project** | `wmt-site-content-strategy` |
| **Dataset** | `scs_production` |
| **Table** | `hp_summary_asset` |

---

## 🔧 Common Filters

### Content Type Filter (Merch Only)

```sql
CASE
  WHEN LOWER(COALESCE(content_served_by, '')) = 'ads' THEN 'WMC'
  WHEN LOWER(COALESCE(disable_content_personalization, '')) LIKE '%true%' THEN 'Merch'
  WHEN LOWER(COALESCE(disable_content_personalization, '')) LIKE '%false%'
       AND LOWER(COALESCE(personalized_asset, '')) = 'default'
       AND session_start_dt <= '2025-03-01'
       AND LOWER(COALESCE(content_zone, '')) = 'contentzone3'
       AND LOWER(COALESCE(hp_module_name, '')) IN ('autoscroll card 1','autoscroll card 2','autoscroll card 3')
    THEN 'WMC'
  WHEN LOWER(COALESCE(disable_content_personalization, '')) LIKE '%false%'
       AND LOWER(COALESCE(personalized_asset, '')) = 'default'
       AND (
         (LOWER(COALESCE(content_zone, '')) IN ('contentzone8','contentzone9')
           AND LOWER(COALESCE(hp_module_name, '')) = 'adjustable banner small')
         OR
         (LOWER(COALESCE(content_zone, '')) IN ('contentzone10','contentzone11')
           AND LOWER(COALESCE(hp_module_name, '')) = 'triple pack small')
       )
    THEN 'WMC'
  ELSE 'Merch'
END
```

### Module Bucket Classification

```sql
CASE
  WHEN LOWER(COALESCE(hp_module_name, '')) IN (
    'autoscroll card 1', 'autoscroll card 2', 'autoscroll card 3',
    'autoscroll card 4', 'autoscroll card 5'
  ) THEN 'HPOV'
  
  WHEN LOWER(COALESCE(hp_module_name, '')) IN (
    'sig card 1', 'sig card 2', 'sig card 3',
    'sig card 4', 'sig card 5', 'sig card 6'
  ) 
  AND LOWER(COALESCE(content_zone, '')) IN ('contentzone3','contentzone4','contentzone5','contentzone6')
  THEN 'ATF Carousels (SIG)'
  
  WHEN LOWER(COALESCE(content_zone, '')) IN ('contentzone3','contentzone4','contentzone5','contentzone6')
  AND LOWER(COALESCE(hp_module_type, '')) = 'carousel'
  AND LOWER(COALESCE(hp_module_name, '')) NOT IN (
    'sig card 1', 'sig card 2', 'sig card 3',
    'sig card 4', 'sig card 5', 'sig card 6'
  )
  THEN 'ATF Carousels'
  
  WHEN LOWER(COALESCE(hp_module_name, '')) = 'walmart+ banner'
  AND LOWER(COALESCE(hp_module_type, '')) != 'utility'
  THEN 'Walmart+ Banner'
  
  WHEN LOWER(COALESCE(hp_module_type, '')) = 'utility'
  THEN 'Utility'
  
  WHEN LOWER(COALESCE(hp_module_type, '')) = 'navigation'
  AND LOWER(COALESCE(content_zone, '')) NOT IN (ATF_ZONES)
  THEN 'BTF Navigation'
  
  WHEN LOWER(COALESCE(hp_module_type, '')) = 'content'
  AND LOWER(COALESCE(content_zone, '')) NOT IN (ATF_ZONES)
  THEN 'BTF Content'
  
  WHEN LOWER(COALESCE(hp_module_type, '')) = 'carousel'
  AND LOWER(COALESCE(content_zone, '')) NOT IN (ATF_ZONES)
  THEN 'BTF Carousels'
END
```

---

## 📊 Module Performance Queries

### WBR Module Performance (Week-over-Week)

```sql
WITH current_week AS (
  SELECT 
    MODULE_CASE AS Module,
    SUM(overall_click_count) AS current_clicks,
    SUM(module_view_count) AS current_impressions,
    SUM(total_atc_count) AS current_atc,
    SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) AS current_ctr
  FROM `wmt-site-content-strategy.scs_production.hp_summary_asset`
  WHERE session_start_dt BETWEEN '{{CURRENT_START}}' AND '{{CURRENT_END}}'
    AND (CONTENT_TYPE_CASE) = 'Merch'
    -- Optional: AND experience_lvl2 = 'App: iOS'
  GROUP BY Module
  HAVING Module IS NOT NULL
),

previous_week AS (
  SELECT 
    MODULE_CASE AS Module,
    SUM(overall_click_count) AS prev_clicks,
    SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) AS prev_ctr,
    SUM(total_atc_count) AS prev_atc
  FROM `wmt-site-content-strategy.scs_production.hp_summary_asset`
  WHERE session_start_dt BETWEEN '{{PREV_START}}' AND '{{PREV_END}}'
    AND (CONTENT_TYPE_CASE) = 'Merch'
  GROUP BY Module
  HAVING Module IS NOT NULL
),

totals_current AS (
  SELECT SUM(current_clicks) AS total_clicks, SUM(current_atc) AS total_atc
  FROM current_week
)

SELECT 
  c.Module,
  ROUND(c.current_ctr * 100, 2) AS ctr_pct,
  ROUND((SAFE_DIVIDE(c.current_ctr, p.prev_ctr) - 1) * 100, 1) AS ctr_wow_pct,
  ROUND(SAFE_DIVIDE(c.current_clicks, t.total_clicks) * 100, 1) AS clicks_pct,
  ROUND((SAFE_DIVIDE(c.current_clicks, p.prev_clicks) - 1) * 100, 1) AS clicks_wow_pct,
  ROUND(SAFE_DIVIDE(c.current_atc, t.total_atc) * 100, 1) AS atc_pct,
  ROUND((SAFE_DIVIDE(c.current_atc, p.prev_atc) - 1) * 100, 1) AS atc_wow_pct
FROM current_week c
LEFT JOIN previous_week p ON c.Module = p.Module
CROSS JOIN totals_current t
ORDER BY 
  CASE c.Module
    WHEN 'HPOV' THEN 1
    WHEN 'ATF Carousels (SIG)' THEN 2
    WHEN 'ATF Carousels' THEN 3
    WHEN 'Walmart+ Banner' THEN 4
    WHEN 'Utility' THEN 5
    WHEN 'BTF Navigation' THEN 6
    WHEN 'BTF Content' THEN 7
    WHEN 'BTF Carousels' THEN 8
  END
```

---

## 📱 HPOV Queries

### Get HPOV Messages List

```sql
SELECT
  message_name,
  SUM(module_view_count) AS views,
  SUM(overall_click_count) AS clicks,
  ROUND(SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) * 100, 2) AS ctr
FROM `wmt-site-content-strategy.scs_production.hp_summary_asset`
WHERE session_start_dt BETWEEN '{{START_DATE}}' AND '{{END_DATE}}'
  AND (CONTENT_TYPE_CASE) = 'Merch'
  AND LOWER(hp_module_name) LIKE 'autoscroll card%'
  AND message_name IS NOT NULL
GROUP BY message_name
ORDER BY views DESC
LIMIT 50
```

### Get HPOV Sponsored/WMC Data

This query retrieves WMC (Walmart Media Connect) sponsored ads data for HPOV cards.
Shown as the **first bar** in the bar chart with gray color.

```sql
SELECT
  'WMC Ads' AS message_name,
  SUM(module_view_count) AS views,
  SUM(overall_click_count) AS clicks,
  ROUND(SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) * 100, 2) AS ctr,
  ROUND((1 - SAFE_DIVIDE(SUM(all_clicks_count_flag), SUM(asset_clicks_count))) * 100, 2) AS exit_rate,
  SUM(total_atc_count) AS atc,
  ROUND(SAFE_DIVIDE(SUM(total_atc_count), SUM(module_view_count)) * 1000, 2) AS atc_rate,
  SUM(total_gmv) AS gmv
FROM `wmt-site-content-strategy.scs_production.hp_summary_asset`
WHERE session_start_dt BETWEEN '{{START_DATE}}' AND '{{END_DATE}}'
  AND (CONTENT_TYPE_CASE) = 'WMC'  -- Sponsored content
  AND LOWER(hp_module_name) LIKE 'autoscroll card%'
```

### Get HPOV Message Details

```sql
SELECT
  message_name,
  SUM(module_view_count) AS views,
  SUM(overall_click_count) AS clicks,
  ROUND(SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) * 100, 2) AS ctr,
  ROUND((1 - SAFE_DIVIDE(SUM(all_clicks_count_flag), SUM(asset_clicks_count))) * 100, 2) AS exit_rate,
  SUM(total_atc_count) AS atc,
  ROUND(SAFE_DIVIDE(SUM(total_atc_count), SUM(module_view_count)) * 1000, 2) AS atc_rate,
  SUM(total_gmv) AS gmv
FROM `wmt-site-content-strategy.scs_production.hp_summary_asset`
WHERE session_start_dt BETWEEN '{{START_DATE}}' AND '{{END_DATE}}'
  AND (CONTENT_TYPE_CASE) = 'Merch'
  AND LOWER(hp_module_name) LIKE 'autoscroll card%'
  AND message_name IN ({{SELECTED_MESSAGES}})
GROUP BY message_name
ORDER BY views DESC
```

### FYTD HPOV Benchmark

```sql
SELECT 
  ROUND(SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) * 100, 2) AS fytd_ctr
FROM `wmt-site-content-strategy.scs_production.hp_summary_asset`
WHERE session_start_dt >= '2026-02-01'  -- FY26 start
  AND (CONTENT_TYPE_CASE) = 'Merch'
  AND LOWER(hp_module_name) LIKE 'autoscroll card%'
```

---

## 🛒 SIG Queries

### Get SIG Carousels

```sql
SELECT
  Carousel_Name,
  SUM(module_view_count) AS views,
  COUNT(DISTINCT message_name) AS message_count
FROM `wmt-site-content-strategy.scs_production.hp_summary_asset`
WHERE session_start_dt BETWEEN '{{START_DATE}}' AND '{{END_DATE}}'
  AND (CONTENT_TYPE_CASE) = 'Merch'
  AND (LOWER(hp_module_name) LIKE 'sig card%' OR LOWER(hp_module_name) LIKE 'scrollable item grid card%')
  AND Carousel_Name IS NOT NULL
GROUP BY Carousel_Name
ORDER BY views DESC
LIMIT 30
```

### Get SIG Messages

```sql
SELECT
  Carousel_Name,
  message_name,
  SUM(module_view_count) AS views,
  SUM(overall_click_count) AS clicks,
  ROUND(SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) * 100, 2) AS ctr
FROM `wmt-site-content-strategy.scs_production.hp_summary_asset`
WHERE session_start_dt BETWEEN '{{START_DATE}}' AND '{{END_DATE}}'
  AND (CONTENT_TYPE_CASE) = 'Merch'
  AND (LOWER(hp_module_name) LIKE 'sig card%' OR LOWER(hp_module_name) LIKE 'scrollable item grid card%')
  AND message_name IS NOT NULL
  AND Carousel_Name IN ({{SELECTED_CAROUSELS}})
GROUP BY Carousel_Name, message_name
ORDER BY views DESC
LIMIT 100
```

### Get SIG Message Details

```sql
SELECT
  Carousel_Name,
  message_name,
  SUM(module_view_count) AS views,
  SUM(overall_click_count) AS clicks,
  ROUND(SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) * 100, 2) AS ctr,
  ROUND((1 - SAFE_DIVIDE(SUM(all_clicks_count_flag), SUM(asset_clicks_count))) * 100, 2) AS exit_rate,
  SUM(total_atc_count) AS atc,
  ROUND(SAFE_DIVIDE(SUM(total_atc_count), SUM(module_view_count)) * 1000, 2) AS atc_rate,
  SUM(total_gmv) AS gmv
FROM `wmt-site-content-strategy.scs_production.hp_summary_asset`
WHERE session_start_dt BETWEEN '{{START_DATE}}' AND '{{END_DATE}}'
  AND (CONTENT_TYPE_CASE) = 'Merch'
  AND (LOWER(hp_module_name) LIKE 'sig card%' OR LOWER(hp_module_name) LIKE 'scrollable item grid card%')
  AND message_name IN ({{SELECTED_MESSAGES}})
GROUP BY Carousel_Name, message_name
ORDER BY views DESC
```

### FYTD SIG Benchmark

```sql
SELECT 
  ROUND(SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) * 100, 2) AS fytd_ctr
FROM `wmt-site-content-strategy.scs_production.hp_summary_asset`
WHERE session_start_dt >= '2026-02-01'  -- FY26 start
  AND (CONTENT_TYPE_CASE) = 'Merch'
  AND (LOWER(hp_module_name) LIKE 'sig card%' OR LOWER(hp_module_name) LIKE 'scrollable item grid card%')
```

---

## 🎯 Message Engagement Benchmark Query

This query classifies messages by engagement tier using impressions-weighted benchmarks.

```sql
WITH
base AS (
  SELECT
    experience_lvl2,
    hp_module_name,
    message_name,
    SUM(module_view_count) AS impressions,
    SUM(COALESCE(overall_click_count, 0)) AS clicks
  FROM `wmt-site-content-strategy.scs_production.hp_summary_asset`
  WHERE session_start_dt BETWEEN '{{START_DATE}}' AND '{{END_DATE}}'
    AND (CONTENT_TYPE_CASE) = 'Merch'
    AND experience_lvl2 IN ('App: iOS', 'App: Android')
    AND hp_module_name LIKE 'AutoScroll Card%'
    AND message_name IS NOT NULL
  GROUP BY 1, 2, 3
),

message_metrics AS (
  SELECT 
    message_name, 
    experience_lvl2, 
    hp_module_name,
    SUM(impressions) AS msg_impressions,
    SUM(clicks) AS msg_clicks,
    SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS msg_ctr_raw
  FROM base 
  GROUP BY 1, 2, 3
),

location_benchmark AS (
  SELECT 
    experience_lvl2, 
    hp_module_name,
    SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS location_benchmark_ctr
  FROM base 
  GROUP BY 1, 2
),

total_msg_impressions AS (
  SELECT message_name, SUM(impressions) AS total_msg_imp 
  FROM base 
  GROUP BY 1
),

message_with_benchmark AS (
  SELECT 
    mm.message_name, 
    mm.msg_impressions, 
    mm.msg_clicks, 
    mm.msg_ctr_raw,
    lb.location_benchmark_ctr,
    tmi.total_msg_imp,
    lb.location_benchmark_ctr * mm.msg_impressions AS weighted_bench_contribution
  FROM message_metrics mm
  JOIN location_benchmark lb USING (experience_lvl2, hp_module_name)
  JOIN total_msg_impressions tmi USING (message_name)
),

message_final AS (
  SELECT 
    message_name,
    SUM(msg_impressions) AS total_impressions,
    SUM(msg_clicks) AS total_clicks,
    SAFE_DIVIDE(SUM(msg_clicks), SUM(msg_impressions)) AS msg_ctr_raw,
    SAFE_DIVIDE(SUM(weighted_bench_contribution), MAX(total_msg_imp)) AS final_weighted_benchmark_ctr
  FROM message_with_benchmark 
  GROUP BY 1
),

classified AS (
  SELECT 
    message_name, 
    total_impressions, 
    total_clicks,
    ROUND(msg_ctr_raw * 100, 4) AS msg_ctr_pct,
    ROUND(final_weighted_benchmark_ctr * 100, 4) AS weighted_benchmark_ctr_pct,
    ROUND(SAFE_DIVIDE(msg_ctr_raw, final_weighted_benchmark_ctr), 3) AS benchmark_index,
    CASE
      WHEN SAFE_DIVIDE(msg_ctr_raw, final_weighted_benchmark_ctr) >= 1.3 THEN 'High Engagement'
      WHEN SAFE_DIVIDE(msg_ctr_raw, final_weighted_benchmark_ctr) >= 0.7 THEN 'Avg Engagement'
      WHEN SAFE_DIVIDE(msg_ctr_raw, final_weighted_benchmark_ctr) < 0.7 THEN 'Trailing Engagement'
      ELSE 'Unclassified'
    END AS engagement_ranking
  FROM message_final
)

SELECT 
  ROW_NUMBER() OVER (ORDER BY total_impressions DESC) AS rank,
  message_name, 
  total_impressions, 
  total_clicks,
  CONCAT(CAST(msg_ctr_pct AS STRING), '%') AS msg_ctr,
  CONCAT(CAST(weighted_benchmark_ctr_pct AS STRING), '%') AS weighted_benchmark_ctr,
  benchmark_index, 
  engagement_ranking
FROM classified
ORDER BY total_impressions DESC
LIMIT 50
```

---

## 📅 Date Calculation Helpers

### Get Walmart Fiscal Week Dates (Python)

```python
def get_walmart_fiscal_week_dates(selected_date: str):
    """
    Walmart fiscal week runs Saturday through Friday.
    Returns: (current_start, current_end, prev_start, prev_end)
    """
    dt = datetime.strptime(selected_date, "%Y-%m-%d")
    weekday = dt.weekday()
    
    if weekday == 5:  # Saturday
        days_since_saturday = 0
    elif weekday == 6:  # Sunday
        days_since_saturday = 1
    else:
        days_since_saturday = weekday + 2
    
    current_saturday = dt - timedelta(days=days_since_saturday)
    current_start = current_saturday.strftime("%Y-%m-%d")
    current_end = dt.strftime("%Y-%m-%d")
    
    prev_start = (current_saturday - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_end = (dt - timedelta(days=7)).strftime("%Y-%m-%d")
    
    return current_start, current_end, prev_start, prev_end
```

---

## ⚠️ Important Notes

1. **Always use SAFE_DIVIDE** to avoid division by zero errors
2. **Always use COALESCE** for nullable columns like `overall_click_count`
3. **Platform filter uses space**: `'App: iOS'` not `'App:iOS'`
4. **Always filter for Merch**: Use the Content Type CASE statement
5. **message_name IS NOT NULL**: Always exclude null message rows when grouping
