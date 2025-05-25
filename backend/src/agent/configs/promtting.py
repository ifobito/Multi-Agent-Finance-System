def prompt_template_schema():
    
    outputs = """
-- Creating the companies table to store company information
CREATE TABLE companies (
    symbol VARCHAR(10) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sector VARCHAR(100),
    industry VARCHAR(100),
    country VARCHAR(100),
    website VARCHAR(255),
    market_cap BIGINT,
    pe_ratio DECIMAL(10,2),
    dividend_yield DECIMAL(6,2),
    fifty_two_week_high DECIMAL(10,2),
    fifty_two_week_low DECIMAL(10,2),
    description TEXT
);

-- Creating the stock_prices table to store historical stock price data
CREATE TABLE stock_prices (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    open_price DECIMAL(10,2),
    high_price DECIMAL(10,2),
    low_price DECIMAL(10,2),
    close_price DECIMAL(10,2),
    volume BIGINT,
    dividends DECIMAL(10,2),
    stock_splits DECIMAL(10,2),
    symbol VARCHAR(10),
    FOREIGN KEY (symbol) REFERENCES companies(symbol),
    UNIQUE (symbol, date)
);

-- Adding indexes for better query performance on stock_prices
CREATE INDEX idx_stock_prices_date ON stock_prices(date);
CREATE INDEX idx_stock_prices_symbol ON stock_prices(symbol);

-- companies: 
-- Purpose: Stores essential details about publicly traded companies, limited to the 30 constituents of the Dow Jones Industrial Average (DJIA).
-- Data Description: Contains metadata for exactly 30 companies with the following stock tickers: AAPL, AMGN, AXP, BA, CAT, CRM, CSCO, CVX, DIS, DOW, GS, HD, HON, IBM, INTC, JNJ, JPM, KO, MCD, MMM, MRK, MSFT, NKE, PG, TRV, UNH, V, VZ, WBA, WMT.
-- Key Fields:
--   - symbol (Primary Key): Unique stock ticker (e.g., AAPL for Apple).
--   - name: Full company name (required).
--   - sector, industry: Business sector and industry classification (e.g., Technology, Consumer Electronics).
--   - country, website: Company’s country of origin (typically United States) and official website.
--   - market_cap: Total market capitalization in USD.
--   - pe_ratio, dividend_yield: Price-to-earnings ratio and dividend yield percentage.
--   - fifty_two_week_high, fifty_two_week_low: Highest and lowest stock prices in the past 52 weeks.
--   - description: Brief overview of the company’s operations and offerings.
-- Significance: Acts as the primary reference for DJIA company metadata, linked to stock_prices via symbol.

-- stock_prices: 
-- Purpose: Captures historical daily stock price data for the 30 DJIA companies.
-- Data Description: Contains daily price records for the 30 DJIA tickers (AAPL, AMGN, AXP, BA, CAT, CRM, CSCO, CVX, DIS, DOW, GS, HD, HON, IBM, INTC, JNJ, JPM, KO, MCD, MMM, MRK, MSFT, NKE, PG, TRV, UNH, V, VZ, WBA, WMT), covering open, high, low, close prices, trading volume, dividends, and stock splits.
-- Key Fields:
--   - id (Primary Key): Unique identifier for each price record.
--   - date: Trading date for the price data.
--   - open_price, high_price, low_price, close_price: Stock prices at market open, daily high, low, and close, in USD.
--   - volume: Number of shares traded on the date.
--   - dividends, stock_splits: Dividend payments and stock split adjustments, in USD.
--   - symbol (Foreign Key): References companies(symbol) to associate prices with a DJIA company.
--   - UNIQUE (symbol, date): Prevents duplicate price records for the same company and date.
-- Indexes: 
--   - idx_stock_prices_date: Optimizes queries filtering by date.
--   - idx_stock_prices_symbol: Speeds up queries filtering by company symbol.
-- Significance: Enables tracking and analysis of stock performance trends for DJIA companies over time.

### Return Calculations

1. **Daily Return**:

   $$
   \text{Daily Return}_t = \frac{\text{Close}_t - \text{Close}_{t-1}}{\text{Close}_{t-1}}
   $$

2. **Cumulative Return**:

   $$
   \text{Cumulative Return} = \frac{\text{Close}_{\text{end}} - \text{Close}_{\text{start}}}{\text{Close}_{\text{start}}}
   $$

3. **Annualized Return**:

   $$
   \text{Annualized Return} = \text{Average Daily Return} \times 252
   $$

4. **Compound Annual Growth Rate (CAGR)**:

   $$
   \text{CAGR} = \left( \frac{\text{Close}_{\text{end}}}{\text{Close}_{\text{start}}} \right)^{\frac{1}{n}} - 1
   $$

   Where $n$ is the number of years.

---

### Volatility Calculations

1. **Daily Volatility**:

   $$
   \text{Daily Volatility} = \text{Standard Deviation of Daily Returns}
   $$

2. **Annualized Volatility**:

   $$
   \text{Annualized Volatility} = \text{Daily Volatility} \times \sqrt{252}
   $$

---

### Risk-Adjusted Metrics

1. **Sharpe Ratio**:

   $$
   \text{Sharpe Ratio} = \frac{\text{Annualized Return} - \text{Risk-Free Rate}}{\text{Annualized Volatility}}
   $$

2. **Beta** (Relative to a Benchmark):

   $$
   \beta = \frac{\text{Covariance}(\text{Asset Returns}, \text{Benchmark Returns})}{\text{Variance}(\text{Benchmark Returns})}
   $$

3. **Correlation**:

   $$
   \text{Correlation} = \frac{\text{Covariance}(\text{Asset Returns}, \text{Benchmark Returns})}{\text{Standard Deviation of Asset Returns} \times \text{Standard Deviation of Benchmark Returns}}
   $$

---

### Date-Specific Metrics

1. **Moving Average (e.g., 30-day)**:

   $$
   \text{Moving Average}_t = \frac{1}{30} \sum_{i=0}^{29} \text{Close}_{t-i}
   $$

2. **Standard Deviation of Closing Prices**:

   $$
   \text{Standard Deviation} = \sqrt{\frac{1}{n} \sum_{i=1}^{n} (\text{Close}_i - \text{Mean Close})^2}
   $$

---

### Dividend Metrics

1. **Dividend Yield**:

   $$
   \text{Dividend Yield} = \frac{\text{Annual Dividends per Share}}{\text{Price per Share}}
   $$

2. **Total Dividends Paid**:

   $$
   \text{Total Dividends} = \text{Dividend per Share} \times \text{Number of Shares}
   $$

---

### Volume Metrics

1. **Average Daily Trading Volume**:

   $$
   \text{Average Volume} = \frac{\sum \text{Daily Volume}}{\text{Number of Trading Days}}
   $$

2. **Total Trading Volume**:

   $$
   \text{Total Volume} = \sum \text{Daily Volume}
   $$

---

### Comparative Metrics

1. **Percentage Change Over Period**:

   $$
   \text{Percentage Change} = \left( \frac{\text{Close}_{\text{end}} - \text{Close}_{\text{start}}}{\text{Close}_{\text{start}}} \right) \times 100\%
   $$

2. **Absolute Change Over Period**:

   $$
   \text{Absolute Change} = \text{Close}_{\text{end}} - \text{Close}_{\text{start}}
   $$

---

### Maximum Drawdown

1. **Maximum Drawdown**:

   $$
   \text{Max Drawdown} = \max \left( \frac{\text{Peak} - \text{Trough}}{\text{Peak}} \right)
   $$

   Where "Peak" is the highest value before a decline, and "Trough" is the lowest value after the peak.

---

### Other Metrics

1. **Median Closing Price**:

   $$
   \text{Median} = \text{Middle value of sorted closing prices}
   $$

2. **Standard Deviation of Daily Returns**:

   $$
   \text{Standard Deviation} = \sqrt{\frac{1}{n} \sum_{i=1}^{n} (\text{Daily Return}_i - \text{Mean Daily Return})^2}
   $$


    """
    return outputs