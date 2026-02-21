import dataclasses
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple
from urllib import error, parse, request

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv() -> None:
        return None


load_dotenv()

GAMMA_BASE = "https://gamma-api.polymarket.com"


@dataclasses.dataclass
class Settings:
    poll_interval_seconds: int = int(os.getenv("POLL_INTERVAL_SECONDS", "20"))
    market_limit: int = int(os.getenv("MARKET_LIMIT", "100"))
    yes_buy_below: float = float(os.getenv("YES_BUY_BELOW", "0.35"))
    no_buy_below: float = float(os.getenv("NO_BUY_BELOW", "0.35"))
    market_cooldown_seconds: int = int(os.getenv("MARKET_COOLDOWN_SECONDS", "1800"))
    dry_run: bool = os.getenv("DRY_RUN", "true").lower() == "true"
    webhook_url: str = os.getenv("WEBHOOK_URL", "").strip()


@dataclasses.dataclass
class Signal:
    market_id: str
    question: str
    side: str
    price: float
    reason: str
    at: datetime


class GammaClient:
    def fetch_markets(self, limit: int = 100) -> List[dict]:
        query = parse.urlencode({"closed": "false", "limit": str(limit)})
        url = f"{GAMMA_BASE}/markets?{query}"
        with request.urlopen(url, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("markets", "data"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []


class Strategy:
    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def _extract_prices(market: dict) -> Optional[Tuple[float, float]]:
        outcome_prices = market.get("outcomePrices")
        if outcome_prices is not None:
            if isinstance(outcome_prices, str):
                raw = outcome_prices.strip()
                if raw.startswith("[") and raw.endswith("]"):
                    raw = raw[1:-1]
                parts = [p.strip().strip('"').strip("'") for p in raw.split(",") if p.strip()]
                if len(parts) >= 2:
                    try:
                        return float(parts[0]), float(parts[1])
                    except ValueError:
                        pass
            elif isinstance(outcome_prices, Iterable):
                values = list(outcome_prices)
                if len(values) >= 2:
                    try:
                        return float(values[0]), float(values[1])
                    except (TypeError, ValueError):
                        pass

        yes = market.get("yesPrice")
        no = market.get("noPrice")
        if yes is not None and no is not None:
            try:
                return float(yes), float(no)
            except (TypeError, ValueError):
                pass
        return None

    def generate_signals(self, markets: List[dict]) -> List[Signal]:
        signals: List[Signal] = []
        now = datetime.now(timezone.utc)
        for market in markets:
            prices = self._extract_prices(market)
            if prices is None:
                continue
            yes, no = prices
            question = market.get("question", "(unknown market)")
            market_id = str(market.get("id", market.get("conditionId", "unknown")))
            if yes <= self.settings.yes_buy_below:
                signals.append(Signal(market_id, question, "YES", yes, f"YES {yes:.3f} <= threshold {self.settings.yes_buy_below:.3f}", now))
            if no <= self.settings.no_buy_below:
                signals.append(Signal(market_id, question, "NO", no, f"NO {no:.3f} <= threshold {self.settings.no_buy_below:.3f}", now))
        return signals


class Executor:
    def __init__(self, settings: Settings):
        self.settings = settings

    def execute(self, signal: Signal) -> None:
        payload = {
            "market_id": signal.market_id,
            "question": signal.question,
            "side": signal.side,
            "price": signal.price,
            "reason": signal.reason,
            "at": signal.at.isoformat(),
            "dry_run": self.settings.dry_run,
        }
        if self.settings.dry_run:
            logging.info("[DRY-RUN] signal=%s", payload)
        else:
            logging.info("[LIVE] TODO place order for signal=%s", payload)

        if self.settings.webhook_url:
            body = json.dumps(payload).encode("utf-8")
            req = request.Request(self.settings.webhook_url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            try:
                request.urlopen(req, timeout=10).read()
            except Exception as exc:
                logging.warning("Webhook failed: %s", exc)


class Bot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = GammaClient()
        self.strategy = Strategy(settings)
        self.executor = Executor(settings)
        self.last_sent: Dict[str, float] = {}

    def _is_cooled_down(self, signal: Signal) -> bool:
        key = f"{signal.market_id}:{signal.side}"
        now = time.time()
        last = self.last_sent.get(key)
        if last is None or now - last >= self.settings.market_cooldown_seconds:
            self.last_sent[key] = now
            return True
        return False

    def run_forever(self) -> None:
        logging.info("Starting Polymarket bot with settings: %s", self.settings)
        while True:
            try:
                markets = self.client.fetch_markets(self.settings.market_limit)
                for signal in self.strategy.generate_signals(markets):
                    if self._is_cooled_down(signal):
                        self.executor.execute(signal)
            except (error.URLError, error.HTTPError) as exc:
                logging.warning("Network/API error: %s", exc)
            except Exception as exc:
                logging.exception("Unexpected error: %s", exc)
            time.sleep(self.settings.poll_interval_seconds)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    Bot(Settings()).run_forever()


if __name__ == "__main__":
    main()
