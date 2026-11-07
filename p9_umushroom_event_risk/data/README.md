# Price data (not redistributed)

`model.py` and `compare.py` read `data/prices.txt`, which is not tracked because the sources do not permit redistribution. Rebuild it from:

| Symbol | Instrument | Currency | Source used |
| --- | --- | --- | --- |
| NVDA | NVIDIA | USD | Financial Modeling Prep, `historical-price-eod-light` |
| WMT | Walmart | USD | Financial Modeling Prep |
| AMAT | Applied Materials | USD | Yahoo Finance, adjusted close |
| HD | Home Depot | USD | Yahoo Finance, adjusted close |
| BAE | BAE Systems (BA.L) | GBP (pence) | Yahoo Finance, adjusted close |
| RR | Rolls-Royce (RR.L) | GBP (pence) | Yahoo Finance, adjusted close |
| BTC | Bitcoin (BTCUSD) | USD | Financial Modeling Prep, crypto EOD |
| ETH | Ethereum (ETHUSD) | USD | Financial Modeling Prep, crypto EOD |
| GBPUSD | Sterling per dollar | FX | Financial Modeling Prep, forex EOD |

Date range: 1 May 2026 to 6 Nov 2026 (daily closes). Crypto and FX were sampled on US trading days only, so weekend moves fall into Monday's return.

Format, one line per symbol:

```
SYMBOL|CCY|YYYY-MM-DD,price;YYYY-MM-DD,price;...
```

Dates may be written `MM-DD` (read as 2026). Lines starting with `#` are comments. The model drops six past earnings-reaction days listed in `model.py` (`PAST_EVENT_DAYS`).
