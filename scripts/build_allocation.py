#!/usr/bin/env python3
import argparse
import csv
import os
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, getcontext
from typing import Dict, Iterable, List

import json
from urllib.request import Request, urlopen

getcontext().prec = 50

MIN_DONATION = Decimal("0.001")
MAX_DONATION = Decimal("5")
TOTAL_TOKENS = 9_000_000_000


@dataclass
class Donor:
    wallet: str
    eth_donated: Decimal
    eth_capped: Decimal
    sqrt_weight: Decimal
    allocation_tokens: int = 0


def normalize_wallet(wallet: str) -> str:
    wallet = wallet.strip()
    if not wallet:
        return wallet
    if wallet.startswith("0x"):
        return wallet.lower()
    return wallet


def parse_decimal(value: str) -> Decimal:
    return Decimal(str(value).strip())


def read_csv(input_csv: str) -> List[Dict[str, str]]:
    with open(input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"wallet", "eth_donated"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing required columns: {sorted(missing)}")
        return list(reader)


def fetch_dune_rows(api_key: str, query_id: int) -> List[Dict[str, str]]:
    url = f"https://api.dune.com/api/v1/query/{query_id}/results"
    headers = {"X-Dune-API-Key": api_key, "Accept": "application/json"}
    req = Request(url, headers=headers, method="GET")
    with urlopen(req, timeout=60) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"Dune API error: HTTP {resp.status}")
        payload = json.loads(resp.read().decode("utf-8"))
    rows = payload.get("result", {}).get("rows", [])
    if not rows:
        raise RuntimeError("No rows returned from Dune API. Ensure query returns wallet + eth_donated.")
    return rows


def aggregate_rows(rows: Iterable[Dict[str, str]]) -> List[Donor]:
    aggregated: Dict[str, Decimal] = {}
    for row in rows:
        wallet = normalize_wallet(str(row.get("wallet", "")))
        donated_raw = row.get("eth_donated", 0)
        if not wallet:
            continue
        try:
            donated = parse_decimal(donated_raw)
        except Exception:
            continue
        if donated < MIN_DONATION:
            continue
        aggregated[wallet] = aggregated.get(wallet, Decimal("0")) + donated

    donors: List[Donor] = []
    for wallet, donated_total in aggregated.items():
        capped = min(donated_total, MAX_DONATION)
        weight = Decimal(capped.sqrt())
        donors.append(Donor(wallet=wallet, eth_donated=donated_total, eth_capped=capped, sqrt_weight=weight))

    donors.sort(key=lambda d: d.wallet)
    return donors


def allocate_tokens(donors: List[Donor], total_tokens: int) -> None:
    if not donors:
        raise RuntimeError("No eligible donors after filtering")

    total_weight = sum(d.sqrt_weight for d in donors)
    if total_weight == 0:
        raise RuntimeError("Total sqrt weight is 0")

    base_allocations: List[int] = []
    remainders: List[tuple[Decimal, int]] = []

    for idx, donor in enumerate(donors):
        exact = (Decimal(total_tokens) * donor.sqrt_weight) / total_weight
        base = int(exact.to_integral_value(rounding=ROUND_FLOOR))
        donor.allocation_tokens = base
        base_allocations.append(base)
        remainders.append((exact - Decimal(base), idx))

    distributed = sum(base_allocations)
    remaining = total_tokens - distributed

    remainders.sort(key=lambda x: (x[0], donors[x[1]].wallet), reverse=True)
    for _, idx in remainders[:remaining]:
        donors[idx].allocation_tokens += 1


def write_donors_csv(donors: List[Donor], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["wallet", "eth_donated", "eth_capped", "sqrt_weight"])
        for d in donors:
            writer.writerow([d.wallet, f"{d.eth_donated}", f"{d.eth_capped}", f"{d.sqrt_weight}"])


def write_final_allocation_csv(donors: List[Donor], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["wallet", "eth_donated", "eth_capped", "sqrt_weight", "allocation_tokens"])
        for d in donors:
            writer.writerow([d.wallet, f"{d.eth_donated}", f"{d.eth_capped}", f"{d.sqrt_weight}", d.allocation_tokens])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build donor allocation CSVs for an airdrop")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--input-csv", help="Path to CSV with columns wallet,eth_donated")
    src.add_argument("--dune-query-id", type=int, help="Dune query ID returning wallet + eth_donated")

    parser.add_argument("--dune-api-key", default=os.getenv("DUNE_API_KEY"), help="Dune API key")
    parser.add_argument("--total-tokens", type=int, default=TOTAL_TOKENS, help="Total token supply to distribute")
    parser.add_argument("--out-donors", default="donors.csv")
    parser.add_argument("--out-allocation", default="final_allocation.csv")
    args = parser.parse_args()

    if args.input_csv:
        rows = read_csv(args.input_csv)
    else:
        if not args.dune_api_key:
            raise SystemExit("--dune-api-key (or DUNE_API_KEY env var) is required with --dune-query-id")
        rows = fetch_dune_rows(args.dune_api_key, args.dune_query_id)

    donors = aggregate_rows(rows)
    allocate_tokens(donors, args.total_tokens)

    write_donors_csv(donors, args.out_donors)
    write_final_allocation_csv(donors, args.out_allocation)

    total_allocated = sum(d.allocation_tokens for d in donors)
    print(f"Eligible donors: {len(donors)}")
    print(f"Total allocated tokens: {total_allocated}")
    print(f"Wrote: {args.out_donors}")
    print(f"Wrote: {args.out_allocation}")


if __name__ == "__main__":
    main()
