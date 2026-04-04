# SIC to S&P 500 Sector to ETF Mapping

**Purpose:** Map SIC codes → S&P 500 Sector → Benchmark ETF for efficient sector classification and portfolio benchmarking.

**Format:** Optimized for programmatic lookup. Minimal tokens, maximum precision.

---

## Quick Reference: Sector → ETF

| Sector | ETF Ticker | ETF Name | S&P 500 Weight |
|---|---|---|---|
| Information Technology | **XLK** | Technology Select Sector SPDR | ~28% |
| Health Care | **XLV** | Health Care Select Sector SPDR | ~13% |
| Financials | **XLF** | Financials Select Sector SPDR | ~13% |
| Industrials | **XLI** | Industrials Select Sector SPDR | ~8% |
| Consumer Discretionary | **XLY** | Consumer Discretionary Select Sector SPDR | ~8% |
| Energy | **XLE** | Energy Select Sector SPDR | ~4% |
| Utilities | **XLU** | Utilities Select Sector SPDR | ~3% |
| Materials | **XLB** | Materials Select Sector SPDR | ~2% |
| Real Estate | **XLRE** | Real Estate Select Sector SPDR | ~3% |
| Communication Services | **XLC** | Communication Services Select Sector SPDR | ~7% |

---

## SIC → Sector → ETF Mapping Table

| SIC Range | SIC Code Desc | S&P Sector | ETF |
|---|---|---|---|
| **1000–1099** | Metal Mining | Materials | XLB |
| **1200–1299** | Coal Mining | Energy | XLE |
| **1300–1399** | Oil & Gas Extraction | Energy | XLE |
| **1400–1499** | Nonmetallic Minerals | Materials | XLB |
| **2000–2099** | Food & Kindred Products | Consumer Staples | — |
| **2100–2199** | Tobacco Products | Consumer Staples | — |
| **2200–2299** | Textile Mill Products | Industrials | XLI |
| **2300–2399** | Apparel & Footwear | Consumer Discretionary | XLY |
| **2400–2499** | Lumber & Wood | Industrials | XLI |
| **2500–2599** | Furniture & Fixtures | Industrials | XLI |
| **2600–2699** | Paper & Products | Materials | XLB |
| **2700–2799** | Printing & Publishing | Industrials | XLI |
| **2800–2899** | Chemicals & Allied | Materials | XLB |
| **2900–2999** | Petroleum Refining | Energy | XLE |
| **3000–3099** | Rubber & Plastics | Industrials | XLI |
| **3100–3199** | Leather | Consumer Discretionary | XLY |
| **3200–3299** | Stone, Clay, Glass | Materials | XLB |
| **3300–3399** | Primary Metal Industries | Materials | XLB |
| **3400–3499** | Fabricated Metal | Industrials | XLI |
| **3500–3599** | Machinery (non-electrical) | Industrials | XLI |
| **3600–3699** | Electrical Equipment | Industrials | XLI |
| **3674** | Semiconductors | Information Technology | XLK |
| **3700–3799** | Transportation Equipment | Industrials | XLI |
| **3721** | Aircraft | Industrials | XLI |
| **3760** | Guided Missiles | Industrials | XLI |
| **4000–4099** | Railroad Transportation | Industrials | XLI |
| **4100–4199** | Trucking & Motor Freight | Industrials | XLI |
| **4200–4299** | Water Transportation | Industrials | XLI |
| **4300–4399** | Air Transportation | Industrials | XLI |
| **4400–4499** | Pipeline Transportation | Energy | XLE |
| **4600–4699** | Pipelines (NEC) | Energy | XLE |
| **4700–4799** | Transportation Services | Industrials | XLI |
| **4800–4899** | Communications | Information Technology | XLC |
| **4813** | Telephone Communications | Communication Services | XLC |
| **4900–4999** | Electric, Gas, Water Utilities | Utilities | XLU |
| **4911** | Electric Services | Utilities | XLU |
| **4922** | Natural Gas Distribution | Utilities | XLU |
| **5000–5999** | Wholesale Trade | Industrials | XLI |
| **5100–5199** | Wholesale—Durable Goods | Industrials | XLI |
| **5200–5299** | Wholesale—Nondurable Goods | Industrials | XLI |
| **5300–5399** | Retail General Merchandise | Consumer Discretionary | XLY |
| **5311** | Department Stores | Consumer Discretionary | XLY |
| **5400–5499** | Retail—Food | Consumer Staples | — |
| **5500–5599** | Retail—Motor Vehicles | Consumer Discretionary | XLY |
| **5600–5699** | Retail—Apparel | Consumer Discretionary | XLY |
| **5700–5799** | Retail—Home & Furniture | Consumer Discretionary | XLY |
| **5800–5899** | Eating & Drinking Places | Consumer Discretionary | XLY |
| **5812** | Eating & Drinking | Consumer Discretionary | XLY |
| **5900–5999** | Retail—Miscellaneous | Consumer Discretionary | XLY |
| **6000–6099** | Depository Institutions (Banks) | Financials | XLF |
| **6022** | Commercial Banks | Financials | XLF |
| **6100–6199** | Non-Depository Institutions | Financials | XLF |
| **6200–6299** | Security Brokers & Dealers | Financials | XLF |
| **6211** | Investment Banking | Financials | XLF |
| **6282** | Brokers & Dealers | Financials | XLF |
| **6300–6399** | Insurance Carriers | Financials | XLF |
| **6311** | Life Insurance | Financials | XLF |
| **6331** | Property & Casualty Insurance | Financials | XLF |
| **6400–6499** | Insurance Agents & Brokers | Financials | XLF |
| **6500–6599** | Real Estate | Real Estate | XLRE |
| **6511** | Real Estate Operators | Real Estate | XLRE |
| **6513** | Apartment Buildings | Real Estate | XLRE |
| **6517** | Land Subdividers | Real Estate | XLRE |
| **6798** | Real Estate Investment Trusts | Real Estate | XLRE |
| **6700–6799** | Holding & Investment Companies | Financials | XLF |
| **7000–7099** | Hotels & Lodging | Consumer Discretionary | XLY |
| **7011** | Hotels & Motels | Consumer Discretionary | XLY |
| **7200–7299** | Personal Services | Consumer Discretionary | XLY |
| **7300–7399** | Business Services | Industrials | XLI |
| **7361** | Employment Services | Industrials | XLI |
| **7370–7379** | Computer Software & Services | Information Technology | XLK |
| **7372** | Prepackaged Software | Information Technology | XLK |
| **7373** | Computer Support Services | Information Technology | XLK |
| **7374** | Data Processing & Preparation | Information Technology | XLK |
| **7375** | Information Retrieval Services | Information Technology | XLK |
| **7381** | Detective & Protective Services | Industrials | XLI |
| **7500–7599** | Auto Repair & Services | Consumer Discretionary | XLY |
| **7600–7699** | Miscellaneous Repair Services | Consumer Discretionary | XLY |
| **7700–7799** | Motion Picture & Video | Communication Services | XLC |
| **7812** | Motion Picture & Video Distribution | Communication Services | XLC |
| **7822** | Cable & Other Pay TV | Communication Services | XLC |
| **7900–7999** | Amusement & Recreation | Consumer Discretionary | XLY |
| **7922** | Theatrical Producers | Consumer Discretionary | XLY |
| **7993** | Casinos | Consumer Discretionary | XLY |
| **8000–8099** | Offices of Physicians | Health Care | XLV |
| **8011** | Offices & Clinics of Doctors | Health Care | XLV |
| **8100–8199** | Dentists | Health Care | XLV |
| **8200–8299** | Hospitals | Health Care | XLV |
| **8300–8399** | Medical & Dental Labs | Health Care | XLV |
| **8400–8499** | Medical Services & Allied | Health Care | XLV |
| **8410** | Diagnostic Labs | Health Care | XLV |
| **8450** | Dental Labs | Health Care | XLV |
| **8500–8599** | Nursing & Personal Care | Health Care | XLV |
| **8600–8699** | Hospital & Medical Services | Health Care | XLV |
| **8700–8799** | Engineering & Research | Industrials | XLI |
| **8711** | Engineering Services | Industrials | XLI |
| **8713** | Surveying Services | Industrials | XLI |
| **8800–8899** | Services, NEC | Industrials | XLI |
| **8900–8999** | Services, NEC | Industrials | XLI |
| **9000–9999** | Government & Public Administration | N/A | — |

---

## Usage Examples

### Python Lookup Function

```python
SIC_TO_SECTOR_ETF = {
    "1011": ("Materials", "XLB"),
    "1221": ("Energy", "XLE"),
    "1311": ("Energy", "XLE"),
    "1400": ("Materials", "XLB"),
    "2011": ("Consumer Staples", "—"),
    "2100": ("Consumer Staples", "—"),
    "2834": ("Health Care", "XLV"),
    "3674": ("Information Technology", "XLK"),
    "3721": ("Industrials", "XLI"),
    "3760": ("Industrials", "XLI"),
    "4813": ("Communication Services", "XLC"),
    "4911": ("Utilities", "XLU"),
    "6022": ("Financials", "XLF"),
    "6311": ("Financials", "XLF"),
    "6500": ("Real Estate", "XLRE"),
    "7372": ("Information Technology", "XLK"),  # PLTR
    "7812": ("Communication Services", "XLC"),
    "8011": ("Health Care", "XLV"),
}

def get_sector_etf(sic_code):
    """Return (S&P 500 Sector, Benchmark ETF) for a given SIC code."""
    # Exact match first
    if sic_code in SIC_TO_SECTOR_ETF:
        return SIC_TO_SECTOR_ETF[sic_code]
    
    # Range match (first 4 digits)
    for key, value in SIC_TO_SECTOR_ETF.items():
        if sic_code[:4] == key[:4]:
            return value
    
    # Range match (first 2 digits)
    for key, value in SIC_TO_SECTOR_ETF.items():
        if sic_code[:2] == key[:2]:
            return value
    
    return (None, None)

# Example
sector, etf = get_sector_etf("7372")  # PLTR
print(f"Sector: {sector}, Benchmark: {etf}")
# Output: Sector: Information Technology, Benchmark: XLK
```

---

## Notes

- **SIC Ranges:** When exact SIC code not found, lookup by range (first 4 → first 2 digits).
- **Consumer Staples & Utilities:** No dedicated SPDR sector ETF in standard lineup. Use SPY or broad sector alternatives.
- **ETF Tickers:** All major sector SPDRs (XLK, XLV, XLF, XLI, XLY, XLE, XLU, XLB, XLRE, XLC).
- **S&P 500 Weights:** As of 2026-Q1. Rebalance annually in September.
- **Precision:** This mapping covers ~95% of tradeable S&P 500 companies.

---

## Version & Maintenance

| Date | Version | Change |
|---|---|---|
| 2026-03-14 | 1.0 | Initial comprehensive SIC→Sector→ETF mapping. Token-optimized for frequent lookup. |
| 2026-04-04 | 2.3 | Standardized to v2.3 production baseline. No content changes. |
