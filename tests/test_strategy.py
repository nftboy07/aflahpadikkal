from bot import Settings, Strategy


def test_extract_prices_from_string_array():
    market = {"outcomePrices": '["0.12", "0.88"]'}
    yes, no = Strategy._extract_prices(market)
    assert yes == 0.12
    assert no == 0.88


def test_generate_signal_yes_and_no_thresholds():
    strategy = Strategy(Settings(yes_buy_below=0.30, no_buy_below=0.25))
    markets = [{"id": "1", "question": "Q", "outcomePrices": [0.20, 0.24]}]

    signals = strategy.generate_signals(markets)

    assert len(signals) == 2
    assert {s.side for s in signals} == {"YES", "NO"}
