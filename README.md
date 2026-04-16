# 🏠 Homepage Performance Analytics

A comprehensive WBR (Weekly Business Review) chart generator for Walmart Homepage analytics. Generate performance reports for Module Performance, HPOV (AutoScroll Cards), and SIG (Scrollable Item Grid) modules.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![BigQuery](https://img.shields.io/badge/BigQuery-Enabled-green.svg)
![License](https://img.shields.io/badge/License-Internal-red.svg)

## 📊 Features

### 1. Module Performance (WBR)
- **Total, iOS, Android** breakdown
- Week-over-Week (WoW) comparison
- CTR, Clicks %, ATC % metrics
- Walmart Fiscal Week calendar (Sat → Fri)

### 2. HPOV Analysis (AutoScroll Cards 1-5)
- Custom date range selection
- Message-level performance
- Services grouping capability
- SOV projections
- Bar chart + Bubble chart visualizations

### 3. SIG Analysis (SIG Cards 1-6)
- Custom date range selection
- Carousel-level grouping
- Message aggregation across carousels
- Performance visualizations

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Google Cloud SDK with BigQuery access
- Access to `wmt-site-content-strategy.scs_production.hp_summary_asset`

### Installation

```bash
# Clone the repository
git clone https://github.com/pramitsingh/homeperformance.git
cd homeperformance

# Run the app
python3 main.py
```

### Access
Open your browser to: `http://127.0.0.1:8002`

## 📁 Project Structure

```
homeperformance/
├── main.py              # Main application (web server + queries)
├── README.md            # This file
├── BUSINESS_CONTEXT.md  # Business logic & metrics definitions
├── QUERIES.md           # All BigQuery queries used
└── .gitignore
```

## 🎯 Usage

### Module Performance Tab
1. Select a date (any day within the Walmart fiscal week)
2. Click "Generate Report"
3. View Total, iOS, and Android performance tables

### HPOV Tab
1. Select Start Date and End Date
2. Click "Load Messages"
3. Check the messages you want to analyze
4. (Optional) Add Services grouping
5. (Optional) Add SOV projections
6. Click "Generate HPOV Charts"

### SIG Tab
1. Select Start Date and End Date
2. Click "Load Carousels"
3. Select carousels to analyze
4. (Optional) Group carousels together
5. Click "Load Messages"
6. Select messages and generate charts

## 📈 Output

All generated charts are saved to: `~/Desktop/clickfather/`

| Output | Format |
|--------|--------|
| Module Performance | HTML table with WoW metrics |
| Bar Charts | Interactive HTML with CTR overlay |
| Bubble Charts | ATC Rate vs Exit Rate scatter |

## 🔧 Configuration

The app uses these default filters:
- **Content Type**: `Merch` only (excludes WMC/Ads)
- **Platforms**: iOS + Android apps
- **Table**: `hp_summary_asset`

## 👥 Team

- **Owner**: Homepage Strategy Team
- **Contact**: Pramit Singh

## 📝 License

Internal Walmart use only. Not for external distribution.
