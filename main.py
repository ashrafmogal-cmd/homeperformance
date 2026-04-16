#!/usr/bin/env python3
"""
Homepage Performance - Comprehensive WBR Chart Generator
- Module Performance (Total, iOS, Android) - Walmart Fiscal Week
- HPOV (AutoScroll Cards 1-5) - Custom Date Range
- SIG (SIG Cards 1-6) - Custom Date Range
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta
import subprocess
import json
import os
import html
import re

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG - SAME AS WBR APP
# ══════════════════════════════════════════════════════════════════════════════

TABLE = "`wmt-site-content-strategy.scs_production.hp_summary_asset`"
BQ_PATH = os.path.expanduser("~/google-cloud-sdk/bin/bq")

CONTENT_TYPE_CASE = """
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
"""

ATF_ZONES_LIST = [
    'contentzone1', 'contentzone2', 'contentzone3',
    'contentzone4', 'contentzone5', 'contentzone6',
    'topcontentzone1', 'topcontentzone2', 'topcontentzone3',
    'topcontentzone4', 'topcontentzone5', 'topcontentzone6'
]
ATF_ZONES_SQL = ",".join([f"'{z}'" for z in ATF_ZONES_LIST])

MODULE_CASE = f"""
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
    AND LOWER(COALESCE(content_zone, '')) NOT IN ({ATF_ZONES_SQL})
    THEN 'BTF Navigation'
    WHEN LOWER(COALESCE(hp_module_type, '')) = 'content'
    AND LOWER(COALESCE(content_zone, '')) NOT IN ({ATF_ZONES_SQL})
    THEN 'BTF Content'
    WHEN LOWER(COALESCE(hp_module_type, '')) = 'carousel'
    AND LOWER(COALESCE(content_zone, '')) NOT IN ({ATF_ZONES_SQL})
    THEN 'BTF Carousels'
  END
"""

UTILITY_MODULES = "Order Status Tracker, Review Banner, Credit Card Banner, Feedback, Amend Banner"

COLORS = [
    '#0071ce', '#ec4899', '#22c55e', '#f97316', '#a855f7', '#14b8a6', 
    '#84cc16', '#6366f1', '#38bdf8', '#f472b6', '#eab308', '#ef4444',
]

SERVICES_COLOR = '#6366f1'

SIG_NAME_MAP = {
    'household essentials': 'HH Essentials',
    'tech rollbacks': 'Tech',
    'arts and crafts': 'Arts & Crafts',
    'gaming and media': 'Gaming',
    'patio and garden': 'Patio & Garden',
    'beauty rollbacks': 'Beauty',
    'home rollbacks': 'Home',
    'rollbacks and more': 'R&M',
    'jump right back in': 'CYS',
}

HPOV_NAME_MAP = {
    # Only shorten very specific long patterns
    'rollbacks & more pov': 'R&M POV',
    'rollbacks and more pov': 'R&M POV',
    'spring baby event': 'Spring Baby',
    'spring home living': 'Spring Home',
    'the farmers dog': 'Farmers Dog',
    'dinner tonight get it fast': 'Dinner Tonight',
}


def get_walmart_fiscal_week_dates(selected_date: str):
    dt = datetime.strptime(selected_date, "%Y-%m-%d")
    weekday = dt.weekday()
    if weekday == 5:
        days_since_saturday = 0
    elif weekday == 6:
        days_since_saturday = 1
    else:
        days_since_saturday = weekday + 2
    current_saturday = dt - timedelta(days=days_since_saturday)
    current_start = current_saturday.strftime("%Y-%m-%d")
    current_end = dt.strftime("%Y-%m-%d")
    prev_start = (current_saturday - timedelta(days=7)).strftime("%Y-%m-%d")
    prev_end = (dt - timedelta(days=7)).strftime("%Y-%m-%d")
    return current_start, current_end, prev_start, prev_end


def get_day_name(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%a")


def shorten_sig_name(name: str) -> str:
    lower = name.lower()
    for pattern, short in SIG_NAME_MAP.items():
        if pattern in lower:
            if 'rollbacks' in lower and pattern != 'rollbacks and more':
                cat = lower.replace('rollbacks and more', '').replace('rollbacks & more', '').strip()
                cat = cat.title()
                if len(cat) > 0:
                    return f"{cat} R&M"
            return short
    if len(name) > 18:
        return name[:16] + '..'
    return name


def shorten_hpov_name(name: str) -> str:
    """Shorten HPOV message names for cleaner chart display - conservative approach"""
    lower = name.lower()
    
    # Direct pattern matches for very long names only
    for pattern, short in HPOV_NAME_MAP.items():
        if pattern in lower:
            return short
    
    # Truncate if still too long (max 16 chars for chart)
    if len(name) > 16:
        return name[:14] + '..'
    return name


def normalize_name(name: str) -> str:
    return name.lower().strip()


def escape_js_string(s: str) -> str:
    """Escape string for safe use in JavaScript single-quoted strings"""
    return s.replace("'", "\\'")


def find_matching_message(user_input: str, available_messages: list) -> str:
    normalized_input = normalize_name(user_input)
    for msg in available_messages:
        if normalize_name(msg) == normalized_input:
            return msg
    return user_input


def run_bq_query(query: str):
    cmd = [BQ_PATH, "query", "--use_legacy_sql=false", "--format=json", "--max_rows=200", query]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"BQ Error: {result.stderr}")
            return []
        output = result.stdout.strip()
        if not output or output == "[]":
            return []
        return json.loads(output)
    except Exception as e:
        print(f"Error running bq: {e}")
        return []


def format_number(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(int(n))


# ══════════════════════════════════════════════════════════════════════════════
# MODULE PERFORMANCE QUERY
# ══════════════════════════════════════════════════════════════════════════════

def get_wbr_data(start_date: str, end_date: str, prev_start: str, prev_end: str, platform_filter: str = None):
    if platform_filter == "iOS":
        platform_clause = "AND experience_lvl2 = 'App: iOS'"
    elif platform_filter == "Android":
        platform_clause = "AND experience_lvl2 = 'App: Android'"
    else:
        platform_clause = ""
    
    query = f"""
    WITH current_week AS (
      SELECT 
        {MODULE_CASE} AS Module,
        SUM(overall_click_count) AS current_clicks,
        SUM(module_view_count) AS current_impressions,
        SUM(total_atc_count) AS current_atc,
        SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) AS current_ctr
      FROM {TABLE}
      WHERE session_start_dt BETWEEN '{start_date}' AND '{end_date}'
        AND ({CONTENT_TYPE_CASE}) = 'Merch'
        {platform_clause}
      GROUP BY Module
      HAVING Module IS NOT NULL
    ),
    previous_week AS (
      SELECT 
        {MODULE_CASE} AS Module,
        SUM(overall_click_count) AS prev_clicks,
        SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) AS prev_ctr,
        SUM(total_atc_count) AS prev_atc
      FROM {TABLE}
      WHERE session_start_dt BETWEEN '{prev_start}' AND '{prev_end}'
        AND ({CONTENT_TYPE_CASE}) = 'Merch'
        {platform_clause}
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
        WHEN 'HPOV' THEN 1 WHEN 'ATF Carousels (SIG)' THEN 2 WHEN 'ATF Carousels' THEN 3
        WHEN 'Walmart+ Banner' THEN 4 WHEN 'Utility' THEN 5 WHEN 'BTF Navigation' THEN 6
        WHEN 'BTF Content' THEN 7 WHEN 'BTF Carousels' THEN 8
      END
    """
    
    results = run_bq_query(query)
    return [{
        "module": row.get('Module', ''),
        "ctr_pct": float(row.get('ctr_pct', 0) or 0),
        "ctr_wow_pct": float(row.get('ctr_wow_pct')) if row.get('ctr_wow_pct') else None,
        "clicks_pct": float(row.get('clicks_pct', 0) or 0),
        "clicks_wow_pct": float(row.get('clicks_wow_pct')) if row.get('clicks_wow_pct') else None,
        "atc_pct": float(row.get('atc_pct')) if row.get('atc_pct') else None,
        "atc_wow_pct": float(row.get('atc_wow_pct')) if row.get('atc_wow_pct') else None,
    } for row in results]


def format_wow(value):
    if value is None:
        return {"value": "—", "class": ""}
    sign = "+" if value > 0 else ""
    css_class = "green" if value > 0 else "red" if value < 0 else ""
    return {"value": f"{sign}{value}%", "class": css_class}


# ══════════════════════════════════════════════════════════════════════════════
# HPOV QUERIES
# ══════════════════════════════════════════════════════════════════════════════

def query_hpov_messages(start_date: str, end_date: str):
    query = f"""
    SELECT
      message_name,
      SUM(module_view_count) AS views,
      SUM(overall_click_count) AS clicks,
      ROUND(SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) * 100, 2) AS ctr
    FROM {TABLE}
    WHERE session_start_dt BETWEEN '{start_date}' AND '{end_date}'
      AND ({CONTENT_TYPE_CASE}) = 'Merch'
      AND LOWER(hp_module_name) LIKE 'autoscroll card%'
      AND message_name IS NOT NULL
    GROUP BY message_name
    ORDER BY views DESC
    LIMIT 50
    """
    return run_bq_query(query)


def query_hpov_data(start_date: str, end_date: str, messages: list):
    msg_list = ", ".join([f"'{m}'" for m in messages])
    query = f"""
    SELECT
      message_name,
      SUM(module_view_count) AS views,
      SUM(overall_click_count) AS clicks,
      ROUND(SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) * 100, 2) AS ctr,
      ROUND((1 - SAFE_DIVIDE(SUM(all_clicks_count_flag), SUM(asset_clicks_count))) * 100, 2) AS exit_rate,
      SUM(total_atc_count) AS atc,
      ROUND(SAFE_DIVIDE(SUM(total_atc_count), SUM(module_view_count)) * 1000, 2) AS atc_rate,
      SUM(total_gmv) AS gmv
    FROM {TABLE}
    WHERE session_start_dt BETWEEN '{start_date}' AND '{end_date}'
      AND ({CONTENT_TYPE_CASE}) = 'Merch'
      AND LOWER(hp_module_name) LIKE 'autoscroll card%'
      AND message_name IN ({msg_list})
    GROUP BY message_name
    ORDER BY views DESC
    """
    return run_bq_query(query)


def query_hpov_sponsored(start_date: str, end_date: str):
    """Query WMC (Sponsored/Ads) data for AutoScroll Cards 1-5"""
    query = f"""
    SELECT
      'WMC Ads' AS message_name,
      SUM(module_view_count) AS views,
      SUM(overall_click_count) AS clicks,
      ROUND(SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) * 100, 2) AS ctr,
      ROUND((1 - SAFE_DIVIDE(SUM(all_clicks_count_flag), SUM(asset_clicks_count))) * 100, 2) AS exit_rate,
      SUM(total_atc_count) AS atc,
      ROUND(SAFE_DIVIDE(SUM(total_atc_count), SUM(module_view_count)) * 1000, 2) AS atc_rate,
      SUM(total_gmv) AS gmv
    FROM {TABLE}
    WHERE session_start_dt BETWEEN '{start_date}' AND '{end_date}'
      AND ({CONTENT_TYPE_CASE}) = 'WMC'
      AND LOWER(hp_module_name) LIKE 'autoscroll card%'
    """
    return run_bq_query(query)


def get_fytd_benchmark(module_type='hpov'):
    if module_type == 'hpov':
        module_filter = "LOWER(hp_module_name) LIKE 'autoscroll card%'"
    else:
        module_filter = "LOWER(hp_module_name) LIKE 'sig card%' OR LOWER(hp_module_name) LIKE 'scrollable item grid card%'"
    
    query = f"""
    SELECT ROUND(SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) * 100, 2) AS fytd_ctr
    FROM {TABLE}
    WHERE session_start_dt >= '2026-02-01'
      AND ({CONTENT_TYPE_CASE}) = 'Merch'
      AND ({module_filter})
    """
    results = run_bq_query(query)
    if results:
        return float(results[0].get('fytd_ctr', 0.22) or 0.22)
    return 0.22 if module_type == 'hpov' else 1.16


# ══════════════════════════════════════════════════════════════════════════════
# SIG QUERIES
# ══════════════════════════════════════════════════════════════════════════════

def query_sig_carousels(start_date: str, end_date: str):
    query = f"""
    SELECT
      Carousel_Name,
      SUM(module_view_count) AS views,
      COUNT(DISTINCT message_name) AS message_count
    FROM {TABLE}
    WHERE session_start_dt BETWEEN '{start_date}' AND '{end_date}'
      AND ({CONTENT_TYPE_CASE}) = 'Merch'
      AND (LOWER(hp_module_name) LIKE 'sig card%' OR LOWER(hp_module_name) LIKE 'scrollable item grid card%')
      AND Carousel_Name IS NOT NULL
    GROUP BY Carousel_Name
    ORDER BY views DESC
    LIMIT 30
    """
    return run_bq_query(query)


def query_sig_messages(start_date: str, end_date: str, carousels: list = None):
    carousel_filter = ""
    if carousels:
        carousel_list = ", ".join([f"'{c}'" for c in carousels])
        carousel_filter = f"AND Carousel_Name IN ({carousel_list})"
    
    # Aggregate by message_name only to avoid duplicates in selection list
    query = f"""
    SELECT
      message_name,
      SUM(module_view_count) AS views,
      SUM(overall_click_count) AS clicks,
      ROUND(SAFE_DIVIDE(SUM(overall_click_count), SUM(module_view_count)) * 100, 2) AS ctr
    FROM {TABLE}
    WHERE session_start_dt BETWEEN '{start_date}' AND '{end_date}'
      AND ({CONTENT_TYPE_CASE}) = 'Merch'
      AND (LOWER(hp_module_name) LIKE 'sig card%' OR LOWER(hp_module_name) LIKE 'scrollable item grid card%')
      AND message_name IS NOT NULL
      {carousel_filter}
    GROUP BY message_name
    ORDER BY views DESC
    LIMIT 50
    """
    return run_bq_query(query)


def query_sig_data(start_date: str, end_date: str, messages: list):
    msg_list = ", ".join([f"'{m}'" for m in messages])
    query = f"""
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
    FROM {TABLE}
    WHERE session_start_dt BETWEEN '{start_date}' AND '{end_date}'
      AND ({CONTENT_TYPE_CASE}) = 'Merch'
      AND (LOWER(hp_module_name) LIKE 'sig card%' OR LOWER(hp_module_name) LIKE 'scrollable item grid card%')
      AND message_name IN ({msg_list})
    GROUP BY Carousel_Name, message_name
    ORDER BY views DESC
    """
    return run_bq_query(query)


def aggregate_sig_data_by_message(data: list, carousel_groups: dict = None):
    if not carousel_groups:
        return data
    
    carousel_to_group = {}
    for group_name, carousels in carousel_groups.items():
        for c in carousels:
            carousel_to_group[c.lower().strip()] = group_name
    
    aggregated = {}
    for d in data:
        carousel = d.get('Carousel_Name', '')
        msg = d.get('message_name', '')
        group = carousel_to_group.get(carousel.lower().strip(), carousel)
        key = (group, msg)
        
        if key not in aggregated:
            aggregated[key] = {
                'Carousel_Name': group, 'message_name': msg,
                'views': 0, 'clicks': 0, 'atc': 0, 'gmv': 0,
                'exit_weighted': 0, 'atc_weighted': 0,
            }
        
        views = int(d.get('views', 0) or 0)
        clicks = int(d.get('clicks', 0) or 0)
        atc = int(d.get('atc', 0) or 0)
        gmv = float(d.get('gmv', 0) or 0)
        exit_rate = float(d.get('exit_rate', 0) or 0)
        atc_rate = float(d.get('atc_rate', 0) or 0)
        
        aggregated[key]['views'] += views
        aggregated[key]['clicks'] += clicks
        aggregated[key]['atc'] += atc
        aggregated[key]['gmv'] += gmv
        aggregated[key]['exit_weighted'] += exit_rate * views
        aggregated[key]['atc_weighted'] += atc_rate * views
    
    result = []
    for key, agg in aggregated.items():
        views = agg['views']
        ctr = round((agg['clicks'] / views * 100) if views > 0 else 0, 2)
        exit_rate = round((agg['exit_weighted'] / views) if views > 0 else 0, 2)
        atc_rate = round((agg['atc_weighted'] / views) if views > 0 else 0, 2)
        
        result.append({
            'Carousel_Name': agg['Carousel_Name'], 'message_name': agg['message_name'],
            'views': agg['views'], 'clicks': agg['clicks'], 'ctr': ctr,
            'exit_rate': exit_rate, 'atc': agg['atc'], 'atc_rate': atc_rate, 'gmv': agg['gmv'],
        })
    
    result.sort(key=lambda x: x['views'], reverse=True)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# MODULE PERFORMANCE HTML
# ══════════════════════════════════════════════════════════════════════════════

def build_module_table_html(data, title: str, platform_label: str = None, header_color: str = "#041e42"):
    rows_html = ""
    for i, row in enumerate(data):
        bg = "background-color: #f9fafb;" if i % 2 == 1 else ""
        ctr_wow = format_wow(row['ctr_wow_pct'])
        clicks_wow = format_wow(row['clicks_wow_pct'])
        atc_wow = format_wow(row['atc_wow_pct'])
        atc_pct = f"{row['atc_pct']}%" if row['atc_pct'] is not None else "—"
        
        rows_html += f'''
        <tr style="{bg}">
            <td style="padding: 12px; text-align: left; font-weight: 500; border-bottom: 1px solid #e5e7eb;">{row['module']}</td>
            <td style="padding: 12px; text-align: center; border-bottom: 1px solid #e5e7eb;">{row['ctr_pct']}%</td>
            <td style="padding: 12px; text-align: center; border-bottom: 1px solid #e5e7eb;" class="{ctr_wow['class']}">{ctr_wow['value']}</td>
            <td style="padding: 12px; text-align: center; border-bottom: 1px solid #e5e7eb;">{row['clicks_pct']}%</td>
            <td style="padding: 12px; text-align: center; border-bottom: 1px solid #e5e7eb;" class="{clicks_wow['class']}">{clicks_wow['value']}</td>
            <td style="padding: 12px; text-align: center; border-bottom: 1px solid #e5e7eb;">{atc_pct}</td>
            <td style="padding: 12px; text-align: center; border-bottom: 1px solid #e5e7eb;" class="{atc_wow['class']}">{atc_wow['value']}</td>
        </tr>'''
    
    if not rows_html:
        rows_html = '<tr><td colspan="7" style="padding: 20px; text-align: center; color: #6b7280;">No data available</td></tr>'
    
    platform_badge = ""
    if platform_label:
        platform_badge = f'<span style="background: {header_color}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; margin-left: 12px;">{platform_label}</span>'
    
    return f'''
    <div style="margin-top: 32px;">
        <h2 style="font-size: 1.1rem; color: #1f2937; margin-bottom: 12px; display: flex; align-items: center;">
            {title}{platform_badge}
        </h2>
        <table style="width: 100%; border-collapse: collapse; font-size: 0.875rem;">
            <thead>
                <tr>
                    <th style="text-align: left; background: {header_color}; color: white; padding: 12px;">Module</th>
                    <th style="background: {header_color}; color: white; padding: 12px;">CTR %</th>
                    <th style="background: {header_color}; color: white; padding: 12px;">CTR WoW %</th>
                    <th style="background: {header_color}; color: white; padding: 12px;">Clicks %</th>
                    <th style="background: {header_color}; color: white; padding: 12px;">Clicks WoW %</th>
                    <th style="background: {header_color}; color: white; padding: 12px;">ATC %</th>
                    <th style="background: {header_color}; color: white; padding: 12px;">ATC WoW %</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    '''


def generate_module_performance_html(data_total, data_ios, data_android, 
                                      current_start, current_end, prev_start, prev_end):
    curr_start_day = get_day_name(current_start)
    curr_end_day = get_day_name(current_end)
    prev_start_day = get_day_name(prev_start)
    prev_end_day = get_day_name(prev_end)
    
    table_total = build_module_table_html(data_total, "All Platforms (Total)", None, "#041e42")
    table_ios = build_module_table_html(data_ios, "iOS Performance", "App: iOS", "#007AFF")
    table_android = build_module_table_html(data_android, "Android Performance", "App: Android", "#3DDC84")
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Homepage Module Performance</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; padding: 24px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); padding: 24px; }}
        .green {{ color: #2a8703; font-weight: 600; }}
        .red {{ color: #ea1100; font-weight: 600; }}
        h1 {{ color: #1f2937; margin-bottom: 16px; font-size: 1.5rem; }}
        .date-boxes {{ display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }}
        .date-box {{ padding: 12px 16px; border-radius: 8px; }}
        .date-box.current {{ background: #e8eef5; border: 1px solid #041e42; }}
        .date-box.prev {{ background: #f3f4f6; border: 1px solid #9ca3af; }}
        .date-box span {{ font-size: 0.75rem; color: #6b7280; }}
        .date-box p {{ font-weight: 600; color: #041e42; margin-top: 4px; }}
        .filter-info {{ color: #4b5563; margin-bottom: 16px; font-size: 0.875rem; }}
        .divider {{ border-top: 2px solid #e5e7eb; margin: 32px 0; }}
        .legend {{ margin-top: 16px; font-size: 0.75rem; color: #6b7280; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>Weekly Business Review - Homepage Module Performance</h1>
            <div class="date-boxes">
                <div class="date-box current">
                    <span>Current Week</span>
                    <p>{current_start} ({curr_start_day}) → {current_end} ({curr_end_day})</p>
                </div>
                <div class="date-box prev">
                    <span>Previous Week</span>
                    <p>{prev_start} ({prev_start_day}) → {prev_end} ({prev_end_day})</p>
                </div>
            </div>
            <p class="filter-info"><strong>Filter:</strong> Content Type = Merch</p>
            {table_total}
            <div class="divider"></div>
            {table_ios}
            <div class="divider"></div>
            {table_android}
            <div class="legend" style="margin-top: 24px;">
                <span class="green">Green</span> = WoW% &gt; 0 (improvement) | <span class="red">Red</span> = WoW% &lt; 0 (decline)<br>
                Utility Modules: {UTILITY_MODULES}
            </div>
        </div>
    </div>
</body>
</html>'''


# ══════════════════════════════════════════════════════════════════════════════
# BAR CHART HTML
# ══════════════════════════════════════════════════════════════════════════════

def generate_bar_chart_html(data: list, projections: dict, services_messages: list, 
                            start_date: str, end_date: str, benchmark: float, 
                            chart_type='hpov', carousel_groups: dict = None,
                            sponsored_data: dict = None):
    
    # Add sponsored data to total views calculation if present
    sponsored_views = int(sponsored_data.get('views', 0) or 0) if sponsored_data else 0
    sponsored_clicks = int(sponsored_data.get('clicks', 0) or 0) if sponsored_data else 0
    
    if chart_type == 'hpov' and services_messages:
        services_lower = [s.lower() for s in services_messages]
        non_services = [d for d in data if d.get('message_name', '').lower() not in services_lower]
        services = [d for d in data if d.get('message_name', '').lower() in services_lower]
    else:
        non_services = data
        services = []
    
    total_views = sum(int(d.get('views', 0) or 0) for d in data) + sponsored_views
    total_clicks = sum(int(d.get('clicks', 0) or 0) for d in data) + sponsored_clicks
    
    # Exclude sponsored from top performer calc (only Merch)
    top_performer = max(data, key=lambda x: float(x.get('ctr', 0) or 0)) if data else None
    top_name = top_performer.get('message_name', 'N/A')[:15] if top_performer else 'N/A'
    top_ctr = float(top_performer.get('ctr', 0) or 0) if top_performer else 0
    
    items_js = []
    groups_js = []
    idx = 0
    
    # Add Sponsored (WMC) as FIRST bar if present
    if sponsored_data and chart_type == 'hpov':
        views = int(sponsored_data.get('views', 0) or 0)
        ctr = float(sponsored_data.get('ctr', 0) or 0)
        label = format_number(views)
        sov = round(views / total_views * 100, 1) if total_views > 0 else 0
        
        items_js.append(f"{{ name:'WMC Ads', imp:{views}, ctr:{ctr}, color:'#6b7280', label:'{label}' }}")
        groups_js.append(f"{{ name:'WMC Ads', start:0, end:0, color:'#6b7280', sov:'{sov}%' }}")
        idx += 1
    
    for d in non_services:
        name = d.get('message_name', '')
        views = int(d.get('views', 0) or 0)
        ctr = float(d.get('ctr', 0) or 0)
        color = COLORS[idx % len(COLORS)]
        label = format_number(views)
        sov = round(views / total_views * 100, 1) if total_views > 0 else 0
        
        proj = ''
        for proj_name, proj_val in projections.items():
            if proj_name.lower() == name.lower():
                proj = proj_val
                break
        
        if chart_type == 'sig':
            short_name = shorten_sig_name(name)
        else:
            short_name = shorten_hpov_name(name)
        
        # Escape for JavaScript
        safe_name = escape_js_string(short_name)
        
        items_js.append(f"{{ name:'{safe_name}', imp:{views}, ctr:{ctr}, color:'{color}', label:'{label}' }}")
        proj_str = f", proj:'{proj}%'" if proj else ""
        groups_js.append(f"{{ name:'{safe_name}', start:{idx}, end:{idx}, color:'{color}', sov:'{sov}%'{proj_str} }}")
        idx += 1
    
    if services:
        services_start = idx
        services_total_views = 0
        for d in services:
            name = d.get('message_name', '')
            views = int(d.get('views', 0) or 0)
            ctr = float(d.get('ctr', 0) or 0)
            label = format_number(views)
            short_name = shorten_hpov_name(name)
            safe_name = escape_js_string(short_name)
            
            items_js.append(f"{{ name:'{safe_name}', imp:{views}, ctr:{ctr}, color:'{SERVICES_COLOR}', label:'{label}' }}")
            services_total_views += views
            idx += 1
        
        services_end = idx - 1
        services_sov = round(services_total_views / total_views * 100, 1) if total_views > 0 else 0
        
        services_proj = ''
        for proj_name, proj_val in projections.items():
            if proj_name.lower() == 'services':
                services_proj = proj_val
                break
        
        proj_str = f", proj:'{services_proj}%'" if services_proj else ""
        groups_js.append(f"{{ name:'Services', start:{services_start}, end:{services_end}, color:'{SERVICES_COLOR}', sov:'{services_sov}%'{proj_str}, staggerDown:true }}")
    
    items_str = ",\n    ".join(items_js)
    groups_str = ",\n    ".join(groups_js)
    date_display = f"{start_date} to {end_date}"
    title = "HPOV (AutoScroll Cards 1–5)" if chart_type == 'hpov' else "SIG (Cards 1–6)"
    bench_label = "FYTD HPOV Benchmark" if chart_type == 'hpov' else "FYTD SIG Benchmark"
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title} Performance — {date_display}</title>
    <style>
        * {{ box-sizing:border-box; margin:0; padding:0; }}
        body {{ font-family:'Segoe UI',Tahoma,sans-serif; background:white; }}
        .container {{ max-width:1950px; margin:0 auto; padding:16px; }}
        .section {{ background:white; border-radius:10px; padding:18px; margin-bottom:18px; border:1px solid #e5e5e5; }}
        .hdr {{ text-align:center; margin-bottom:12px; border-bottom:1px solid #eee; padding-bottom:10px; }}
        .hdr h1 {{ font-size:18px; font-weight:700; color:#1a1a1a; }}
        .hdr p  {{ color:#555; font-size:12px; margin-top:4px; }}
        .metrics {{ display:flex; gap:10px; margin-bottom:14px; }}
        .metric  {{ flex:1; background:white; border-radius:6px; padding:10px 12px;
                    border-left:4px solid; border-top:1px solid #eee; border-right:1px solid #eee; border-bottom:1px solid #eee; }}
        .metric-label {{ font-size:11px; color:#666; }}
        .metric-value {{ font-size:20px; font-weight:700; color:#1a1a1a; white-space:nowrap; }}
        .chart-box svg {{ display:block; width:100%; height:auto; }}
    </style>
</head>
<body>
<div class="container">
<div class="section">
    <div class="hdr">
        <h1>📊 Message Performance — {title}</h1>
        <p>Date Range: {date_display}</p>
    </div>
    <div class="metrics">
        <div class="metric" style="border-left-color:#0071ce;">
            <div class="metric-label">Total Impressions (Merch)</div>
            <div class="metric-value">{format_number(total_views)}</div>
        </div>
        <div class="metric" style="border-left-color:#22c55e;">
            <div class="metric-label">Total Clicks (Merch)</div>
            <div class="metric-value">{format_number(total_clicks)}</div>
        </div>
        <div class="metric" style="border-left-color:#ffc220;">
            <div class="metric-label">FYTD CTR Benchmark</div>
            <div class="metric-value">{benchmark:.2f}%</div>
        </div>
        <div class="metric" style="border-left-color:#0ea5e9;">
            <div class="metric-label">Top Performer CTR</div>
            <div class="metric-value">{top_name} @ {top_ctr:.2f}%</div>
        </div>
    </div>
    <div class="chart-box" id="chart"></div>
</div>
</div>
<script>
function buildChart(containerId, items, groups, config) {{
    const W = config.width || 1800, H = config.height || 640;
    const L = 50, R = W - 50, T = 55, B = config.B || 400;
    const n = items.length;
    const slot = (R - L) / n;
    const bw = slot * 0.65;
    const maxImp = Math.max(...items.map(d => d.imp));
    const ctrMin = config.ctrMin, ctrMax = config.ctrMax;
    const ctrToY = v => B - ((v - ctrMin) / (ctrMax - ctrMin)) * (B - T);
    const impToH = v => (v / maxImp) * (B - T);

    let svg = `<svg width="${{W}}" height="${{H}}" viewBox="0 0 ${{W}} ${{H}}" xmlns="http://www.w3.org/2000/svg" style="font-family:'Segoe UI',Arial,sans-serif;">`;
    svg += `<rect width="${{W}}" height="${{H}}" fill="white"/>`;

    const legY = 24;
    svg += `<circle cx="${{W/2-155}}" cy="${{legY}}" r="7" fill="#ffc220"/>`;
    svg += `<text x="${{W/2-141}}" y="${{legY+5}}" font-size="13" font-weight="600" fill="#555">${{config.benchLabel}}</text>`;
    svg += `<circle cx="${{W/2+65}}" cy="${{legY}}" r="7" fill="white" stroke="#333" stroke-width="2"/>`;
    svg += `<text x="${{W/2+79}}" y="${{legY+5}}" font-size="13" font-weight="600" fill="#555">CTR %</text>`;

    const benchY = ctrToY(config.benchmark);
    svg += `<line x1="${{L}}" y1="${{benchY}}" x2="${{R}}" y2="${{benchY}}" stroke="#ffc220" stroke-width="2.5" stroke-dasharray="8,5"/>`;
    svg += `<rect x="${{R-280}}" y="${{benchY-25}}" width="275" height="18" fill="white" fill-opacity="0.9" rx="3"/>`;
    svg += `<text x="${{R-8}}" y="${{benchY-11}}" font-size="12" font-weight="bold" fill="#b8860b" text-anchor="end">FYTD Benchmark: ${{config.benchmark}}%</text>`;

    const ctrPoints = [];
    items.forEach((d, i) => {{
        const cx = L + i * slot + slot / 2;
        const x  = cx - bw / 2;
        const h  = Math.max(4, impToH(d.imp));
        const barTopY = B - h;
        svg += `<rect x="${{x.toFixed(1)}}" y="${{barTopY.toFixed(1)}}" width="${{bw.toFixed(1)}}" height="${{h.toFixed(1)}}" fill="${{d.color}}" rx="3"/>`;
        const preferred = barTopY - 16;
        const baseY = Math.max(T + 14, preferred);
        const postStagger = (i % 2 === 1) ? 16 : 0;
        const impLabelY = baseY + postStagger;
        const impLabelFill = (impLabelY > barTopY) ? 'white' : d.color;
        svg += `<text x="${{cx.toFixed(1)}}" y="${{impLabelY.toFixed(1)}}" text-anchor="middle" font-size="12" font-weight="bold" fill="${{impLabelFill}}">${{d.label}}</text>`;
        ctrPoints.push({{ cx, cy: ctrToY(d.ctr), ctr: d.ctr, idx: i }});
    }});

    const pathD = ctrPoints.map((p,i) => `${{i===0?'M':'L'}} ${{p.cx.toFixed(1)}} ${{p.cy.toFixed(1)}}`).join(' ');
    svg += `<path d="${{pathD}}" fill="none" stroke="#1a1a1a" stroke-width="2"/>`;

    ctrPoints.forEach(p => {{
        svg += `<circle cx="${{p.cx.toFixed(1)}}" cy="${{p.cy.toFixed(1)}}" r="5" fill="white" stroke="#1a1a1a" stroke-width="2"/>`;
        const off = (p.idx % 2 === 1) ? 44 : 26;
        const ly  = Math.max(T + 10, p.cy - off);
        svg += `<text x="${{p.cx.toFixed(1)}}" y="${{ly.toFixed(1)}}" text-anchor="middle" font-size="12" font-weight="bold" fill="#1a1a1a">${{p.ctr}}%</text>`;
    }});

    const bracketY = B + 12;
    groups.forEach(g => {{
        const x1 = L + g.start * slot + (slot - bw) / 2;
        const x2 = L + g.end   * slot + slot / 2 + bw / 2;
        svg += `<line x1="${{x1.toFixed(1)}}" y1="${{bracketY}}" x2="${{x2.toFixed(1)}}" y2="${{bracketY}}" stroke="${{g.color}}" stroke-width="4" stroke-linecap="round"/>`;
        svg += `<line x1="${{x1.toFixed(1)}}" y1="${{(bracketY-5).toFixed(1)}}" x2="${{x1.toFixed(1)}}" y2="${{(bracketY+5).toFixed(1)}}" stroke="${{g.color}}" stroke-width="2"/>`;
        svg += `<line x1="${{x2.toFixed(1)}}" y1="${{(bracketY-5).toFixed(1)}}" x2="${{x2.toFixed(1)}}" y2="${{(bracketY+5).toFixed(1)}}" stroke="${{g.color}}" stroke-width="2"/>`;
    }});

    items.forEach((d, i) => {{
        const cx = L + i * slot + slot / 2;
        svg += `<text x="${{cx.toFixed(1)}}" y="${{(bracketY+20).toFixed(1)}}" text-anchor="middle" font-size="9" font-weight="700" fill="#333">${{d.name}}</text>`;
    }});

    groups.forEach(g => {{
        const x1  = L + g.start * slot + (slot - bw) / 2;
        const x2  = L + g.end   * slot + slot / 2 + bw / 2;
        const mx  = (x1 + x2) / 2;
        const baseY = g.staggerDown ? bracketY + 50 : bracketY + 36;
        if (g.start !== g.end) {{
            svg += `<text x="${{mx.toFixed(1)}}" y="${{baseY}}" text-anchor="middle" font-size="10" font-weight="700" fill="${{g.color}}">${{g.name}}</text>`;
        }}
        svg += `<text x="${{mx.toFixed(1)}}" y="${{(baseY+13).toFixed(1)}}" text-anchor="middle" font-size="9" font-weight="600" fill="${{g.color}}">${{g.sov}} SOV</text>`;
        if (g.proj) {{
            svg += `<text x="${{mx.toFixed(1)}}" y="${{(baseY+25).toFixed(1)}}" text-anchor="middle" font-size="9" font-weight="700" fill="#16a34a">→ ${{g.proj}} proj</text>`;
        }}
    }});

    svg += `</svg>`;
    document.getElementById(containerId).innerHTML = svg;
}}

const items = [{items_str}];
const groups = [{groups_str}];
const maxCtr = Math.max(...items.map(d => d.ctr));
const ctrMax = Math.ceil(maxCtr * 10) / 10 + 0.1;

buildChart('chart', items, groups, {{
    benchmark: {benchmark},
    ctrMin: 0.0,
    ctrMax: ctrMax,
    benchLabel: '{bench_label}',
    width: 1900,
    height: 670,
    B: 420,
}});
</script>
</body>
</html>'''


def generate_bubble_chart_html(data: list, start_date: str, end_date: str, highlight_name: str = None, chart_type='hpov'):
    date_display = f"{start_date} to {end_date}"
    title = "AutoScroll Cards (HPOV)" if chart_type == 'hpov' else "SIG Cards"
    
    bubble_data = []
    for d in data:
        name = d.get('message_name', '')
        views = int(d.get('views', 0) or 0)
        atc_rate = float(d.get('atc_rate', 0) or 0)
        exit_rate = float(d.get('exit_rate', 0) or 0)
        
        if chart_type == 'sig':
            short_name = shorten_sig_name(name)
        else:
            short_name = shorten_hpov_name(name)
        
        safe_name = escape_js_string(short_name)
        bubble_data.append(f"{{ name:'{safe_name}', imp:{views}, atc:{atc_rate}, exit:{exit_rate} }}")
    
    data_str = ",\n    ".join(bubble_data)
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Bubble Chart — {title} | {date_display}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@1.4.0/dist/chartjs-plugin-annotation.min.js"></script>
    <style>
        body {{ font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif; }}
        .box-header  {{ background:#ffc220; padding:10px 16px; font-weight:700; font-size:.9rem; color:#041e42; text-align:center; }}
        .insights-bd {{ background:#041e42; padding:14px 12px; min-height:100px; }}
        .ins-item    {{ display:flex; gap:9px; margin-bottom:10px; align-items:flex-start; }}
        .ins-num     {{ width:20px; height:20px; border-radius:50%; flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:.65rem; font-weight:800; color:#fff; margin-top:2px; }}
        .ins-txt     {{ font-size:.76rem; color:#cbd5e1; line-height:1.4; }}
        .ins-txt strong {{ color:#fff; }}
        .leg-bd      {{ background:#041e42; padding:12px 8px; display:flex; gap:8px; justify-content:center; }}
        .leg-pill    {{ flex:1; display:flex; flex-direction:column; align-items:center; gap:6px; padding:10px 6px; border-radius:8px; border:2px solid; }}
        .leg-dot     {{ width:22px; height:22px; border-radius:50%; }}
        .leg-lbl     {{ font-size:.7rem; font-weight:700; text-align:center; line-height:1.2; }}
        .pill-g {{ border-color:#16a34a; }} .pill-g .leg-lbl {{ color:#4ade80; }}
        .pill-n {{ border-color:#94a3b8; }} .pill-n .leg-lbl {{ color:#94a3b8; }}
        .pill-r {{ border-color:#dc2626; }} .pill-r .leg-lbl {{ color:#f87171; }}
        .side-box {{ border-radius:10px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.15); }}
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
<div class="max-w-[1300px] mx-auto p-6">
<div class="rounded-xl shadow-lg overflow-hidden" style="background:#fff;">
    <header class="py-5 px-8 text-center" style="background:#041e42;">
        <h2 class="text-lg font-bold text-white">❆ Message Performance Stats — {title} ❆</h2>
        <p class="text-slate-300 text-xs mt-1">{date_display}</p>
    </header>
    <div style="display:flex;">
        <div style="flex:1; min-width:0; background:#fff;">
            <div style="height:660px; position:relative;"><canvas id="bubble"></canvas></div>
            <p class="text-center text-slate-400 text-xs pb-3">Bubble Size = Impressions · X = ATC Rate · Y = Exit Rate (lower is better)</p>
        </div>
        <div style="width:290px; flex-shrink:0; border-left:1px solid #e2e8f0; padding:16px; background:#fff; display:flex; flex-direction:column; gap:14px;">
            <div class="side-box">
                <div class="box-header">Key Insights</div>
                <div class="insights-bd" id="insights"></div>
            </div>
            <div class="side-box" style="margin-top:auto;">
                <div class="box-header">Legend</div>
                <div class="leg-bd">
                    <div class="leg-pill pill-g"><div class="leg-dot" style="background:#16a34a;"></div><div class="leg-lbl">Top Performer</div></div>
                    <div class="leg-pill pill-n"><div class="leg-dot" style="background:#94a3b8;"></div><div class="leg-lbl">Neutral</div></div>
                    <div class="leg-pill pill-r"><div class="leg-dot" style="background:#dc2626;"></div><div class="leg-lbl">Low Performer</div></div>
                </div>
            </div>
        </div>
    </div>
</div>
</div>
<script>
const C_TOP = {{ fill:'rgba(34,197,94,0.62)', stroke:'rgb(22,163,74)' }};
const C_BOT = {{ fill:'rgba(239,68,68,0.62)', stroke:'rgb(220,38,38)' }};
const C_NEU = {{ fill:'rgba(148,163,184,0.55)', stroke:'rgb(100,116,139)' }};

function buildInsights(id, items) {{
    const el = document.getElementById(id);
    items.slice(0,6).forEach((it, i) => {{
        el.innerHTML += `<div class="ins-item"><div class="ins-num" style="background:${{it.color}}">${{i+1}}</div><div class="ins-txt"><strong>${{it.name}}</strong> (${{it.stat}}) — ${{it.desc}}</div></div>`;
    }});
}}

function applyYJitter(pts, threshold=1.8) {{
    const groups = [];
    pts.forEach(pt => {{
        const g = groups.find(g => Math.abs(g.y0 - pt.y) < threshold);
        if (g) g.members.push(pt); else groups.push({{ y0:pt.y, members:[pt] }});
    }});
    groups.forEach(g => {{
        if (g.members.length <= 1) return;
        g.members.sort((a,b) => a.x - b.x);
        const half = Math.min(3.5, g.members.length * 0.5);
        g.members.forEach((pt,i) => {{ pt.y = g.y0 + (g.members.length===1 ? 0 : (i/(g.members.length-1)-0.5)*2*half); }});
    }});
}}

function drawLabels(chart, pts) {{
    const c = chart.ctx, ca = chart.chartArea;
    const pad=3, bh=13, gap=5;
    c.font = 'bold 8px system-ui';
    const placed = [];
    pts.forEach((pt,i) => {{
        const m  = chart.getDatasetMeta(0).data[i];
        const bx = m.x, by = m.y, br = pt.r;
        const bw = c.measureText(pt.name).width + pad*2;
        let cands = [[bx+br+gap, by-bh/2], [bx-bw/2, by-br-bh-gap], [bx-br-bw-gap, by-bh/2], [bx-bw/2, by+br+gap]];
        let chosen = null;
        for (const [cx,cy] of cands) {{
            const lx = Math.max(ca.left+2, Math.min(cx, ca.right-bw-2));
            const ly = Math.max(ca.top+2,  Math.min(cy, ca.bottom-bh-2));
            const ok = !placed.some(p => lx<p.x+p.w+3 && lx+bw+3>p.x && ly<p.y+p.h+3 && ly+bh+3>p.y);
            if (ok) {{ chosen={{lx,ly}}; break; }}
        }}
        if (!chosen) {{ const [cx,cy] = cands[0]; chosen = {{ lx:Math.max(ca.left+2,Math.min(cx,ca.right-bw-2)), ly:Math.max(ca.top+2,Math.min(cy,ca.bottom-bh-2)) }}; }}
        placed.push({{x:chosen.lx, y:chosen.ly, w:bw, h:bh}});
        c.save();
        c.fillStyle='rgba(255,255,255,0.93)'; c.fillRect(chosen.lx,chosen.ly,bw,bh);
        c.strokeStyle=pt.c.stroke; c.lineWidth=1; c.strokeRect(chosen.lx,chosen.ly,bw,bh);
        c.fillStyle='#1e293b'; c.textAlign='left'; c.textBaseline='middle';
        c.fillText(pt.name, chosen.lx+pad, chosen.ly+bh/2);
        c.restore();
    }});
}}

function renderBubble({{ canvasId, pts, minX, maxX, minY, maxY, mX, mExit }}) {{
    const ctx = document.getElementById(canvasId).getContext('2d');
    new Chart(ctx, {{
        type:'bubble',
        data:{{ datasets:[{{ data:pts, backgroundColor:pts.map(p=>p.c.fill), borderColor:pts.map(p=>p.c.stroke), borderWidth:2 }}]}},
        options:{{
            responsive:true, maintainAspectRatio:false,
            layout:{{ padding:{{ top:80, right:230, bottom:70, left:90 }} }},
            scales:{{
                x:{{ title:{{ display:true, text:'ATC Rate (per 1K Impressions)', font:{{size:12,weight:'bold'}}, color:'#475569' }}, min:minX, max:maxX, grid:{{display:false}}, ticks:{{color:'#64748b'}} }},
                y:{{ title:{{ display:true, text:'Exit Rate (← Lower is Better)', font:{{size:12,weight:'bold'}}, color:'#475569' }}, min:minY, max:maxY, reverse:true, grid:{{display:false}}, ticks:{{ color:'#64748b', callback:v=>v+'%' }} }},
            }},
            plugins:{{
                legend:{{ display:false }},
                tooltip:{{ callbacks:{{ label:c=>[c.raw.name,`ATC: ${{c.raw.x.toFixed(2)}}`,`Exit: ${{c.raw.y.toFixed(1)}}%`,`Imp: ${{(c.raw.imp/1e6).toFixed(2)}}M`] }} }},
                annotation:{{ annotations:{{
                    gZone:{{ type:'box', xMin:mX, xMax:maxX, yMin:minY, yMax:mExit, backgroundColor:'rgba(34,197,94,0.06)', borderWidth:0 }},
                    rZone:{{ type:'box', xMin:minX, xMax:mX, yMin:mExit, yMax:maxY, backgroundColor:'rgba(239,68,68,0.06)', borderWidth:0 }},
                    vLine:{{ type:'line', xMin:mX, xMax:mX, yMin:minY, yMax:maxY, borderColor:'rgba(100,116,139,0.35)', borderWidth:1, borderDash:[5,4] }},
                    hLine:{{ type:'line', xMin:minX, xMax:maxX, yMin:mExit, yMax:mExit, borderColor:'rgba(100,116,139,0.35)', borderWidth:1, borderDash:[5,4], label:{{ display:true, content:`Avg Exit: ${{mExit.toFixed(1)}}%`, position:'end', backgroundColor:'transparent', color:'#94a3b8', font:{{size:10}} }} }},
                }}}},
            }},
        }},
        plugins:[
            {{ id:'avgX', afterDraw(chart) {{ const {{ctx:c, scales:{{x,y}}}} = chart; const px = x.getPixelForValue(mX), py = y.getPixelForValue(minY) + 22; c.save(); c.font='bold 12px system-ui'; c.fillStyle='#334155'; c.textAlign='center'; c.fillText(`Avg ATC: ${{mX.toFixed(2)}}`, px, py); c.restore(); }} }},
            {{ id:'labels', afterDraw(chart) {{ drawLabels(chart, pts); }} }},
        ],
    }});
}}

function makeBubble(canvasId, data, insId) {{
    const totalImp = data.reduce((s,d)=>s+d.imp,0);
    const mAtc  = data.reduce((s,d)=>s+d.atc,0) / data.length;
    const mExit = data.reduce((s,d)=>s+d.imp*d.exit,0) / totalImp;
    const maxI  = Math.max(...data.map(d=>d.imp));
    const cl = data.map(d => ({{ ...d, c: d.atc>mAtc && d.exit<mExit ? C_TOP : d.atc<mAtc && d.exit>mExit ? C_BOT : C_NEU }}));
    const pts = cl.map(d => ({{ x:d.atc, y:d.exit, r:Math.sqrt(d.imp/maxI)*24+5, name:d.name, imp:d.imp, c:d.c }}));
    applyYJitter(pts);
    buildInsights(insId, [
        ...cl.filter(d=>d.c===C_TOP).sort((a,b)=>b.atc-a.atc).slice(0,3).map(d=>({{ name:d.name, stat:`ATC ${{d.atc.toFixed(2)}}, exit ${{d.exit.toFixed(1)}}%`, desc:'High ATC & low exit 🟢', color:'#16a34a' }})),
        ...cl.filter(d=>d.c===C_BOT).sort((a,b)=>b.exit-a.exit).slice(0,3).map(d=>({{ name:d.name, stat:`ATC ${{d.atc.toFixed(2)}}, exit ${{d.exit.toFixed(1)}}%`, desc:'High exit, low ATC 🔴', color:'#dc2626' }})),
    ]);
    const maxAtc = Math.max(...data.map(d=>d.atc));
    const minExit = Math.min(...data.map(d=>d.exit));
    const maxExit = Math.max(...data.map(d=>d.exit));
    renderBubble({{ canvasId, pts, minX:-0.1, maxX:Math.max(2.0, maxAtc+0.5), minY:Math.max(10, minExit-10), maxY:Math.min(90, maxExit+10), mX:mAtc, mExit }});
}}

const data = [{data_str}];
makeBubble('bubble', data, 'insights');
</script>
</body>
</html>'''


# ══════════════════════════════════════════════════════════════════════════════
# WEB UI
# ══════════════════════════════════════════════════════════════════════════════

generated_charts = {'bar': '', 'bubble': '', 'modules': ''}


def render_main_page(tab='modules', selected_date="", week_info=None,
                     module_generated=False,
                     hpov_messages=None, selected_hpov=None, services_input="", projections_input="", highlight="",
                     sig_carousels=None, selected_carousels=None, sig_messages=None, selected_sig=None, 
                     sig_projections_input="", carousel_groups_input="",
                     charts_generated=False,
                     hpov_start="", hpov_end="", sig_start="", sig_end="",
                     include_wmc=True):
    
    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    wmc_checked = "checked" if include_wmc else ""
    
    if not selected_date:
        selected_date = today
    if not hpov_start:
        hpov_start = week_ago
    if not hpov_end:
        hpov_end = today
    if not sig_start:
        sig_start = week_ago
    if not sig_end:
        sig_end = today
    
    tab_modules_active = "active" if tab == 'modules' else ""
    tab_hpov_active = "active" if tab == 'hpov' else ""
    tab_sig_active = "active" if tab == 'sig' else ""
    
    week_display = ""
    if week_info:
        week_display = f'''
        <div class="week-info">
            <div class="week-box current">
                <div class="week-label">Current Week</div>
                <div class="week-dates">{week_info[0]} ({get_day_name(week_info[0])}) → {week_info[1]} ({get_day_name(week_info[1])})</div>
            </div>
            <div class="week-box previous">
                <div class="week-label">Previous Week</div>
                <div class="week-dates">{week_info[2]} ({get_day_name(week_info[2])}) → {week_info[3]} ({get_day_name(week_info[3])})</div>
            </div>
        </div>
        <p class="filter-note"><strong>Filter:</strong> Content Type = Merch</p>'''
    
    hpov_date_display = f'''
        <div class="date-range-box">
            <span class="date-range-label">📅 Date Range:</span>
            <span class="date-range-value">{hpov_start} → {hpov_end}</span>
        </div>
        <p class="filter-note"><strong>Filter:</strong> Content Type = Merch</p>'''
    
    sig_date_display = f'''
        <div class="date-range-box">
            <span class="date-range-label">📅 Date Range:</span>
            <span class="date-range-value">{sig_start} → {sig_end}</span>
        </div>
        <p class="filter-note"><strong>Filter:</strong> Content Type = Merch</p>'''
    
    hpov_msgs_html = ""
    if hpov_messages:
        for m in hpov_messages:
            name = m.get('message_name', '')
            views = int(m.get('views', 0) or 0)
            ctr = float(m.get('ctr', 0) or 0)
            checked = "checked" if selected_hpov and any(s.lower() == name.lower() for s in selected_hpov) else ""
            hpov_msgs_html += f'''<label class="msg-item"><input type="checkbox" name="selected_hpov" value="{html.escape(name)}" {checked}><span class="msg-name">{html.escape(name)}</span><span class="msg-stat">{format_number(views)}</span><span class="msg-ctr">{ctr:.2f}%</span></label>'''
    
    sig_carousel_html = ""
    if sig_carousels:
        for c in sig_carousels:
            name = c.get('Carousel_Name', '')
            views = int(c.get('views', 0) or 0)
            count = int(c.get('message_count', 0) or 0)
            checked = "checked" if selected_carousels and name in selected_carousels else ""
            sig_carousel_html += f'''<label class="msg-item"><input type="checkbox" name="selected_carousels" value="{html.escape(name)}" {checked}><span class="msg-name">{html.escape(name)}</span><span class="msg-stat">{format_number(views)}</span><span class="msg-ctr">{count} msgs</span></label>'''
    
    sig_msgs_html = ""
    if sig_messages:
        for m in sig_messages:
            name = m.get('message_name', '')
            views = int(m.get('views', 0) or 0)
            ctr = float(m.get('ctr', 0) or 0)
            checked = "checked" if selected_sig and name in selected_sig else ""
            # Show ORIGINAL name in selection list (not shortened)
            sig_msgs_html += f'''<label class="msg-item"><input type="checkbox" name="selected_sig" value="{html.escape(name)}" {checked}><span class="msg-name" title="{html.escape(name)}">{html.escape(name)}</span><span class="msg-stat">{format_number(views)}</span><span class="msg-ctr">{ctr:.2f}%</span></label>'''
    
    results_html = ""
    if charts_generated or module_generated:
        results_html = f'''
        <div class="results-box">
            <h3>✅ Charts Generated!</h3>
            <div class="results-btns">
                {"<a href='/view-modules' target='_blank' class='btn btn-view'>📊 View Module Performance</a>" if module_generated else ""}
                {"<a href='/view-bar' target='_blank' class='btn btn-view'>📊 View Bar Chart</a>" if charts_generated else ""}
                {"<a href='/view-bubble' target='_blank' class='btn btn-view2'>🫧 View Bubble Chart</a>" if charts_generated else ""}
            </div>
            <p class="results-path">Saved to ~/Desktop/clickfather/</p>
        </div>'''
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Homepage Performance</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; }}
        .header {{ background: #041e42; color: white; padding: 16px 24px; }}
        .header h1 {{ font-size: 1.5rem; font-weight: 700; }}
        .header p {{ color: #94a3b8; font-size: 0.9rem; margin-top: 4px; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        .tabs {{ display: flex; gap: 4px; margin-bottom: 20px; }}
        .tab {{ padding: 12px 24px; background: #e5e7eb; border: none; border-radius: 8px 8px 0 0; cursor: pointer; font-weight: 600; color: #6b7280; }}
        .tab.active {{ background: white; color: #0071ce; }}
        .tab-content {{ display: none; background: white; border-radius: 0 8px 8px 8px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .tab-content.active {{ display: block; }}
        .form-row {{ display: flex; gap: 16px; margin-bottom: 20px; align-items: flex-end; flex-wrap: wrap; }}
        .form-group {{ flex: 1; min-width: 150px; }}
        .form-group label {{ display: block; font-weight: 600; color: #374151; margin-bottom: 6px; }}
        input[type="date"], input[type="text"], textarea {{ width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 1rem; }}
        textarea {{ min-height: 80px; font-family: monospace; font-size: 0.9rem; }}
        .btn {{ padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.95rem; text-decoration: none; display: inline-block; }}
        .btn-primary {{ background: #0071ce; color: white; }}
        .btn-secondary {{ background: #6b7280; color: white; }}
        .btn-success {{ background: #10b981; color: white; }}
        .btn-view {{ background: #0071ce; color: white; }}
        .btn-view2 {{ background: #6366f1; color: white; }}
        .section-title {{ font-size: 1.1rem; font-weight: 700; color: #1f2937; margin: 24px 0 12px 0; padding-top: 16px; border-top: 1px solid #e5e7eb; }}
        .section-title:first-of-type {{ border-top: none; margin-top: 0; padding-top: 0; }}
        .msg-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 6px; max-height: 300px; overflow-y: auto; padding: 4px; background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb; }}
        .msg-item {{ display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: white; border-radius: 4px; cursor: pointer; border: 1px solid #e5e7eb; }}
        .msg-item:hover {{ background: #f0f9ff; border-color: #0071ce; }}
        .msg-item input {{ flex-shrink: 0; }}
        .msg-name {{ flex: 1; font-weight: 500; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .msg-stat {{ color: #6b7280; font-size: 0.8rem; }}
        .msg-ctr {{ color: #0071ce; font-size: 0.8rem; font-weight: 600; }}
        .help {{ font-size: 0.8rem; color: #6b7280; margin-top: 4px; }}
        .results-box {{ margin-top: 24px; padding: 20px; background: #ecfdf5; border: 2px solid #10b981; border-radius: 10px; }}
        .results-box h3 {{ color: #059669; margin-bottom: 12px; }}
        .results-btns {{ display: flex; gap: 12px; flex-wrap: wrap; }}
        .results-path {{ margin-top: 12px; color: #6b7280; font-size: 0.85rem; }}
        .week-info {{ display: flex; gap: 16px; margin: 20px 0; }}
        .week-box {{ flex: 1; padding: 16px; border-radius: 8px; border: 2px solid; }}
        .week-box.current {{ border-color: #0071ce; background: #f0f9ff; }}
        .week-box.previous {{ border-color: #94a3b8; background: #f9fafb; }}
        .week-label {{ font-size: 0.85rem; font-weight: 500; color: #6b7280; margin-bottom: 4px; }}
        .week-box.current .week-label {{ color: #0071ce; }}
        .week-dates {{ font-size: 1.1rem; font-weight: 700; color: #1f2937; }}
        .filter-note {{ font-size: 0.9rem; color: #6b7280; margin-top: 8px; }}
        .inline-hint {{ color: #6b7280; font-size: 0.85rem; margin-left: 12px; }}
        .date-range-box {{ display: inline-flex; align-items: center; gap: 8px; padding: 12px 20px; background: #f0f9ff; border: 2px solid #0071ce; border-radius: 8px; margin: 16px 0; }}
        .date-range-label {{ font-weight: 600; color: #0071ce; }}
        .date-range-value {{ font-weight: 700; color: #1f2937; font-size: 1.1rem; }}
    </style>
    <script>
        function switchTab(tabName) {{
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelector(`[data-tab="${{tabName}}"]`).classList.add('active');
            document.getElementById(`tab-${{tabName}}`).classList.add('active');
        }}
    </script>
</head>
<body>
    <div class="header">
        <h1>🏠 Homepage Performance</h1>
        <p>Generate WBR charts for Module Performance, HPOV, and SIG</p>
    </div>
    
    <div class="container">
        <div class="tabs">
            <button class="tab {tab_modules_active}" data-tab="modules" onclick="switchTab('modules')">📊 Module Performance</button>
            <button class="tab {tab_hpov_active}" data-tab="hpov" onclick="switchTab('hpov')">📱 HPOV</button>
            <button class="tab {tab_sig_active}" data-tab="sig" onclick="switchTab('sig')">🛒 SIG</button>
        </div>
        
        <!-- Module Performance Tab -->
        <div id="tab-modules" class="tab-content {tab_modules_active}">
            <form method="post" action="/">
                <input type="hidden" name="tab" value="modules">
                <div class="form-row">
                    <div class="form-group" style="flex:0 0 200px;">
                        <label>Select Date (Walmart Fiscal Week)</label>
                        <input type="date" name="selected_date" value="{selected_date}">
                    </div>
                    <div class="form-group" style="flex:0; display:flex; align-items:flex-end;">
                        <button type="submit" name="action" value="generate_modules" class="btn btn-primary">Generate Report</button>
                    </div>
                    <div class="form-group" style="display:flex; align-items:center;">
                        <span class="inline-hint">Walmart week: Sat → selected date</span>
                    </div>
                </div>
                {week_display if tab == 'modules' else ''}
                {results_html if tab == 'modules' else ''}
            </form>
        </div>
        
        <!-- HPOV Tab -->
        <div id="tab-hpov" class="tab-content {tab_hpov_active}">
            <form method="post" action="/">
                <input type="hidden" name="tab" value="hpov">
                <div class="section-title" style="border-top:none; margin-top:0; padding-top:0;">1️⃣ Select Date Range</div>
                <div class="form-row">
                    <div class="form-group" style="flex:0 0 180px;">
                        <label>Start Date</label>
                        <input type="date" name="hpov_start" value="{hpov_start}">
                    </div>
                    <div class="form-group" style="flex:0 0 180px;">
                        <label>End Date</label>
                        <input type="date" name="hpov_end" value="{hpov_end}">
                    </div>
                    <div class="form-group" style="flex:0; display:flex; align-items:flex-end;">
                        <button type="submit" name="action" value="load_hpov" class="btn btn-primary">Load Messages</button>
                    </div>
                </div>
                {hpov_date_display if hpov_messages else ''}
                
                {f"""
                <div class="section-title">2️⃣ Select Messages</div>
                <div class="msg-grid">{hpov_msgs_html}</div>
                <p class="help">Check messages to include. Case-insensitive matching.</p>
                
                <div class="section-title">3️⃣ Services Grouping (Optional)</div>
                <div class="form-group">
                    <label>Services Messages (one per line)</label>
                    <textarea name="services" placeholder="Dinner Tonight Get It Fast">{html.escape(services_input)}</textarea>
                </div>
                
                <div class="section-title">3b. Include WMC Ads</div>
                <div class="form-group" style="display:flex; align-items:center; gap:12px;">
                    <input type="checkbox" name="include_wmc" id="include_wmc" value="1" {wmc_checked} style="width:20px; height:20px;">
                    <label for="include_wmc" style="font-weight:500; margin:0;">Include Sponsored (WMC Ads) as first bar</label>
                    <span style="color:#6b7280; font-size:0.85rem;">— Gray bar showing WMC sponsored content in HPOV</span>
                </div>
                
                <div class="section-title">4️⃣ Projections & Highlight (Optional)</div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Projections (message_name,projection%)</label>
                        <textarea name="projections" placeholder="Arih Pre Order,8.5">{html.escape(projections_input)}</textarea>
                    </div>
                    <div class="form-group">
                        <label>Highlight Message</label>
                        <input type="text" name="highlight" value="{html.escape(highlight)}" placeholder="e.g., Arih Pre Order">
                    </div>
                </div>
                
                <button type="submit" name="action" value="generate_hpov" class="btn btn-success">🚀 Generate HPOV Charts</button>
                """ if hpov_messages else ''}
                {results_html if tab == 'hpov' and charts_generated else ''}
            </form>
        </div>
        
        <!-- SIG Tab -->
        <div id="tab-sig" class="tab-content {tab_sig_active}">
            <form method="post" action="/">
                <input type="hidden" name="tab" value="sig">
                <div class="section-title" style="border-top:none; margin-top:0; padding-top:0;">1️⃣ Select Date Range</div>
                <div class="form-row">
                    <div class="form-group" style="flex:0 0 180px;">
                        <label>Start Date</label>
                        <input type="date" name="sig_start" value="{sig_start}">
                    </div>
                    <div class="form-group" style="flex:0 0 180px;">
                        <label>End Date</label>
                        <input type="date" name="sig_end" value="{sig_end}">
                    </div>
                    <div class="form-group" style="flex:0; display:flex; align-items:flex-end;">
                        <button type="submit" name="action" value="load_sig_carousels" class="btn btn-primary">Load Carousels</button>
                    </div>
                </div>
                {sig_date_display if sig_carousels else ''}
                
                {f"""
                <div class="section-title">2️⃣ Select Carousels</div>
                <div class="msg-grid">{sig_carousel_html}</div>
                
                <div class="section-title">2b. Group Carousels (Optional)</div>
                <div class="form-group">
                    <label>Carousel Groups (GroupName:Carousel1,Carousel2)</label>
                    <textarea name="carousel_groups">{html.escape(carousel_groups_input)}</textarea>
                    <p class="help">Same message names across grouped carousels will be aggregated.</p>
                </div>
                
                <button type="submit" name="action" value="load_sig_messages" class="btn btn-secondary" style="margin-top:12px;">📋 Load Messages</button>
                """ if sig_carousels else ''}
                
                {f"""
                <div class="section-title">3️⃣ Select Messages</div>
                <div class="msg-grid">{sig_msgs_html}</div>
                
                <div class="section-title">4️⃣ Projections (Optional)</div>
                <div class="form-group">
                    <label>Projections (message_name,projection%)</label>
                    <textarea name="sig_projections">{html.escape(sig_projections_input)}</textarea>
                </div>
                
                <button type="submit" name="action" value="generate_sig" class="btn btn-success">🚀 Generate SIG Charts</button>
                """ if sig_messages else ''}
                {results_html if tab == 'sig' and charts_generated else ''}
            </form>
        </div>
    </div>
</body>
</html>'''


class ChartHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/view-bar' and generated_charts['bar']:
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(generated_charts['bar'].encode('utf-8'))
            return
        if self.path == '/view-bubble' and generated_charts['bubble']:
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(generated_charts['bubble'].encode('utf-8'))
            return
        if self.path == '/view-modules' and generated_charts['modules']:
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(generated_charts['modules'].encode('utf-8'))
            return
        
        html_content = render_main_page()
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = parse_qs(post_data)
        
        tab = params.get('tab', ['modules'])[0]
        selected_date = params.get('selected_date', [''])[0]
        action = params.get('action', [''])[0]
        
        # HPOV params
        hpov_start = params.get('hpov_start', [''])[0]
        hpov_end = params.get('hpov_end', [''])[0]
        selected_hpov = params.get('selected_hpov', [])
        services_input = params.get('services', [''])[0]
        projections_input = params.get('projections', [''])[0]
        highlight = params.get('highlight', [''])[0].strip()
        include_wmc = params.get('include_wmc', [''])[0] == '1'
        
        # SIG params
        sig_start = params.get('sig_start', [''])[0]
        sig_end = params.get('sig_end', [''])[0]
        selected_carousels = params.get('selected_carousels', [])
        selected_sig = params.get('selected_sig', [])
        sig_projections_input = params.get('sig_projections', [''])[0]
        carousel_groups_input = params.get('carousel_groups', [''])[0]
        
        hpov_messages = None
        sig_carousels = None
        sig_messages = None
        charts_generated = False
        module_generated = False
        week_info = None
        
        # Module Performance
        if action == 'generate_modules' and selected_date:
            week_info = get_walmart_fiscal_week_dates(selected_date)
            current_start, current_end, prev_start, prev_end = week_info
            
            print(f"[INFO] Generating module performance for {current_start} to {current_end}...")
            data_total = get_wbr_data(current_start, current_end, prev_start, prev_end, platform_filter=None)
            print(f"[INFO] Got {len(data_total)} modules for TOTAL")
            
            data_ios = get_wbr_data(current_start, current_end, prev_start, prev_end, platform_filter="iOS")
            print(f"[INFO] Got {len(data_ios)} modules for iOS")
            
            data_android = get_wbr_data(current_start, current_end, prev_start, prev_end, platform_filter="Android")
            print(f"[INFO] Got {len(data_android)} modules for Android")
            
            modules_html = generate_module_performance_html(data_total, data_ios, data_android,
                                                            current_start, current_end, prev_start, prev_end)
            generated_charts['modules'] = modules_html
            
            output_dir = os.path.expanduser("~/Desktop/clickfather")
            os.makedirs(output_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(os.path.join(output_dir, f"module_performance_{ts}.html"), 'w') as f:
                f.write(modules_html)
            
            module_generated = True
        
        # HPOV - Load messages
        elif action == 'load_hpov' and hpov_start and hpov_end:
            print(f"[INFO] Loading HPOV messages for {hpov_start} to {hpov_end}...")
            hpov_messages = query_hpov_messages(hpov_start, hpov_end)
            print(f"[INFO] Found {len(hpov_messages)} HPOV messages")
        
        # HPOV - Generate charts
        elif action == 'generate_hpov' and hpov_start and hpov_end and selected_hpov:
            print(f"[INFO] Generating HPOV charts for {hpov_start} to {hpov_end}...")
            hpov_messages = query_hpov_messages(hpov_start, hpov_end)
            
            all_msg_names = [m.get('message_name', '') for m in hpov_messages]
            matched_messages = [find_matching_message(sel, all_msg_names) for sel in selected_hpov]
            
            data = query_hpov_data(hpov_start, hpov_end, matched_messages)
            
            # Query Sponsored (WMC) data if checkbox is checked
            sponsored_data = None
            if include_wmc:
                sponsored_results = query_hpov_sponsored(hpov_start, hpov_end)
                sponsored_data = sponsored_results[0] if sponsored_results else None
                print(f"[INFO] Sponsored data: {sponsored_data}")
            else:
                print(f"[INFO] WMC Ads not included (checkbox unchecked)")
            
            services_list = [s.strip() for s in services_input.strip().split('\n') if s.strip()]
            
            projections = {}
            for line in projections_input.strip().split('\n'):
                if ',' in line:
                    parts = line.split(',', 1)
                    if len(parts) >= 2:
                        projections[parts[0].strip()] = parts[1].strip().replace('%', '')
            
            benchmark = get_fytd_benchmark('hpov')
            
            bar_html = generate_bar_chart_html(data, projections, services_list, hpov_start, hpov_end, benchmark, 'hpov', None, sponsored_data)
            bubble_html = generate_bubble_chart_html(data, hpov_start, hpov_end, highlight if highlight else None, 'hpov')
            
            generated_charts['bar'] = bar_html
            generated_charts['bubble'] = bubble_html
            
            output_dir = os.path.expanduser("~/Desktop/clickfather")
            os.makedirs(output_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(os.path.join(output_dir, f"hpov_bar_{ts}.html"), 'w') as f:
                f.write(bar_html)
            with open(os.path.join(output_dir, f"hpov_bubble_{ts}.html"), 'w') as f:
                f.write(bubble_html)
            
            charts_generated = True
        
        # SIG - Load carousels
        elif action == 'load_sig_carousels' and sig_start and sig_end:
            print(f"[INFO] Loading SIG carousels for {sig_start} to {sig_end}...")
            sig_carousels = query_sig_carousels(sig_start, sig_end)
            print(f"[INFO] Found {len(sig_carousels)} carousels")
        
        # SIG - Load messages
        elif action == 'load_sig_messages' and sig_start and sig_end and selected_carousels:
            sig_carousels = query_sig_carousels(sig_start, sig_end)
            sig_messages = query_sig_messages(sig_start, sig_end, selected_carousels)
            print(f"[INFO] Found {len(sig_messages)} messages")
        
        # SIG - Generate charts
        elif action == 'generate_sig' and sig_start and sig_end and selected_sig:
            print(f"[INFO] Generating SIG charts for {sig_start} to {sig_end}...")
            sig_carousels = query_sig_carousels(sig_start, sig_end)
            sig_messages = query_sig_messages(sig_start, sig_end)
            data = query_sig_data(sig_start, sig_end, selected_sig)
            
            carousel_groups = {}
            for line in carousel_groups_input.strip().split('\n'):
                if ':' in line:
                    parts = line.split(':', 1)
                    group_name = parts[0].strip()
                    carousels = [c.strip() for c in parts[1].split(',')]
                    carousel_groups[group_name] = carousels
            
            if carousel_groups:
                data = aggregate_sig_data_by_message(data, carousel_groups)
            
            projections = {}
            for line in sig_projections_input.strip().split('\n'):
                if ',' in line:
                    parts = line.split(',', 1)
                    if len(parts) >= 2:
                        projections[parts[0].strip()] = parts[1].strip().replace('%', '')
            
            benchmark = get_fytd_benchmark('sig')
            
            bar_html = generate_bar_chart_html(data, projections, [], sig_start, sig_end, benchmark, 'sig', carousel_groups)
            bubble_html = generate_bubble_chart_html(data, sig_start, sig_end, None, 'sig')
            
            generated_charts['bar'] = bar_html
            generated_charts['bubble'] = bubble_html
            
            output_dir = os.path.expanduser("~/Desktop/clickfather")
            os.makedirs(output_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(os.path.join(output_dir, f"sig_bar_{ts}.html"), 'w') as f:
                f.write(bar_html)
            with open(os.path.join(output_dir, f"sig_bubble_{ts}.html"), 'w') as f:
                f.write(bubble_html)
            
            charts_generated = True
        
        html_content = render_main_page(
            tab=tab, selected_date=selected_date, week_info=week_info,
            module_generated=module_generated,
            hpov_messages=hpov_messages, selected_hpov=selected_hpov,
            services_input=services_input, projections_input=projections_input, highlight=highlight,
            sig_carousels=sig_carousels, selected_carousels=selected_carousels,
            sig_messages=sig_messages, selected_sig=selected_sig,
            sig_projections_input=sig_projections_input, carousel_groups_input=carousel_groups_input,
            charts_generated=charts_generated,
            hpov_start=hpov_start, hpov_end=hpov_end, sig_start=sig_start, sig_end=sig_end,
            include_wmc=include_wmc,
        )
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))
    
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def main():
    port = 8002
    server = HTTPServer(('0.0.0.0', port), ChartHandler)
    print("=" * 60)
    print("  🏠 Homepage Performance")
    print(f"  Running at: http://127.0.0.1:{port}")
    print("  - Module Performance: Walmart Fiscal Week")
    print("  - HPOV & SIG: Custom Date Range")
    print("=" * 60)
    server.serve_forever()


if __name__ == "__main__":
    main()
