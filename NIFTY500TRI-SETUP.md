# Nifty 500 TRI benchmark integration

- `nifty500tri.json` is populated by `update_nifty500tri.py` from NSE Indices' official Total Returns Index Values endpoint. It contains `{ "d": "YYYY-MM-DD", "n": <TRI value> }` records.
- On the first GitHub Actions run, the script requests the full history from 1 Jan 1995 in <=365-day chunks. Subsequent runs refresh recent observations.
- The comparison chart uses only dates shared by the selected fund NAV, existing Nifty 50 price series, and Nifty 500 TRI. This avoids comparing different date windows.
- Nifty 50 remains the existing price-index series; Nifty 500 TRI includes dividend reinvestment.
- Data endpoint: https://www.niftyindices.com/Backpage.aspx/getTotalReturnIndexString; public historical-data page: https://www.niftyindices.com/reports/historical-data.

The generated `nifty500tri.json` is intentionally empty in the supplied ZIP rather than containing fabricated values. Run the GitHub Actions workflow (`Update NAV`) or run `python3 update_nifty500tri.py` in an environment with internet access to import official data.
