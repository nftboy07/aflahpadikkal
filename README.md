# Polymarket Bot (Starter)

A lightweight **signal bot** for Polymarket markets.

This project does **not** place live orders by default. It scans active markets via the public Gamma API and emits trading signals based on configurable probability thresholds.

## Features

- Fetches open markets from Polymarket's public Gamma API.
- Extracts YES/NO token prices (when available).
- Applies a simple configurable strategy:
  - Buy YES signal when YES price <= `yes_buy_below`
  - Buy NO signal when NO price <= `no_buy_below`
- Cooldown and per-market signal deduplication.
- Optional webhook notifications.
- Dry-run mode on by default.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

## Environment Variables

| Variable | Default | Description |
|---|---:|---|
| `POLL_INTERVAL_SECONDS` | `20` | Scan interval |
| `MARKET_LIMIT` | `100` | Number of markets per scan |
| `YES_BUY_BELOW` | `0.35` | Trigger YES signal at or below this price |
| `NO_BUY_BELOW` | `0.35` | Trigger NO signal at or below this price |
| `MARKET_COOLDOWN_SECONDS` | `1800` | Cooldown before repeating a signal for same side |
| `DRY_RUN` | `true` | If true, only logs signals |
| `WEBHOOK_URL` | _(empty)_ | Optional JSON webhook endpoint |

## Notes

- This is a starter bot template, not financial advice.
- If you want real order execution, add exchange client code in `Executor.execute()`.
