# Crypto Airdrop Pipeline

Complete, reproducible pipeline to:
1. Fetch donor data from Dune API (or load CSV)
2. Apply square-root allocation model with min/cap donation rules
3. Generate Merkle tree for claim contracts
4. Export all required artifacts

## Rules implemented
- Input columns: `wallet`, `eth_donated`
- Ignore donations `< 0.001 ETH`
- Cap donations at `5 ETH`
- Weight = `sqrt(capped_eth)`
- Allocate a fixed `9,000,000,000` tokens (default)

## Outputs
- `donors.csv`
- `final_allocation.csv`
- `merkle.json`
- Merkle root printed in terminal and stored in `merkle.json` as `merkleRoot`

---

## 1) Install dependencies

### Python
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Node.js
```bash
npm install
```

---

## 2) Prepare input data

### Option A: CSV input
Use a CSV like:
```csv
wallet,eth_donated
0xabc...,0.12
0xdef...,3.9
```

### Option B: Dune API input
Provide a Dune query that returns columns named exactly:
- `wallet`
- `eth_donated`

Set API key:
```bash
export DUNE_API_KEY=your_api_key_here
```

---

## 3) Build allocations (Python)

### From CSV
```bash
python3 scripts/build_allocation.py \
  --input-csv sample_input.csv \
  --out-donors donors.csv \
  --out-allocation final_allocation.csv
```

### From Dune API
```bash
python3 scripts/build_allocation.py \
  --dune-query-id 1234567 \
  --dune-api-key "$DUNE_API_KEY" \
  --out-donors donors.csv \
  --out-allocation final_allocation.csv
```

What this step does:
- Aggregates repeated wallets
- Filters out donations below `0.001`
- Caps donation per wallet at `5`
- Computes sqrt weight
- Distributes total tokens with floor+largest remainder, so sum equals exactly `9,000,000,000`

---

## 4) Generate Merkle tree (Node.js)

```bash
node scripts/generate_merkle.js \
  --input final_allocation.csv \
  --output merkle.json
```

This prints:
- `Merkle root: 0x...`

And writes:
- `merkle.json` containing:
  - `merkleRoot`
  - `tokenTotal`
  - `claims` map with wallet proof data

---

## 5) One-liner run (sample)

```bash
python3 scripts/build_allocation.py --input-csv sample_input.csv && node scripts/generate_merkle.js --input final_allocation.csv --output merkle.json
```

---

## Claim contract compatibility notes
- Leaf encoding used: `keccak256(abi.encodePacked(address, uint256))`
- Pair sorting enabled in Merkle tree (`sortPairs: true`)
- Ensure your Solidity verifier uses the same leaf encoding and sorted pair assumptions.
