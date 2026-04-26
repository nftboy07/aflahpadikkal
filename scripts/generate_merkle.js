#!/usr/bin/env node
const fs = require('fs');
const { parse } = require('csv-parse/sync');
const { MerkleTree } = require('merkletreejs');
const { solidityPackedKeccak256, getAddress } = require('ethers');

function usage() {
  console.log('Usage: node scripts/generate_merkle.js --input final_allocation.csv --output merkle.json');
}

function parseArgs() {
  const args = process.argv.slice(2);
  const out = { input: 'final_allocation.csv', output: 'merkle.json' };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--input') out.input = args[++i];
    else if (args[i] === '--output') out.output = args[++i];
    else if (args[i] === '--help' || args[i] === '-h') {
      usage();
      process.exit(0);
    }
  }
  return out;
}

function toLeaf(wallet, allocationTokens) {
  const checksum = getAddress(wallet);
  return Buffer.from(
    solidityPackedKeccak256(['address', 'uint256'], [checksum, BigInt(allocationTokens)]).slice(2),
    'hex'
  );
}

function main() {
  const { input, output } = parseArgs();
  const csvRaw = fs.readFileSync(input, 'utf8');
  const rows = parse(csvRaw, { columns: true, skip_empty_lines: true, trim: true });

  const allocations = rows
    .map((row) => ({
      wallet: row.wallet,
      allocation_tokens: row.allocation_tokens,
    }))
    .filter((r) => r.wallet && r.allocation_tokens)
    .sort((a, b) => a.wallet.toLowerCase().localeCompare(b.wallet.toLowerCase()));

  if (allocations.length === 0) {
    throw new Error('No allocations found in input CSV');
  }

  const leaves = allocations.map((a) => toLeaf(a.wallet, a.allocation_tokens));
  const tree = new MerkleTree(leaves, (data) => Buffer.from(solidityPackedKeccak256(['bytes32'], [data]).slice(2), 'hex'), {
    sortPairs: true,
  });

  const root = tree.getHexRoot();

  const claims = {};
  allocations.forEach((a, idx) => {
    const leaf = leaves[idx];
    claims[getAddress(a.wallet)] = {
      index: idx,
      wallet: getAddress(a.wallet),
      allocation_tokens: a.allocation_tokens,
      leaf: `0x${leaf.toString('hex')}`,
      proof: tree.getHexProof(leaf),
    };
  });

  const result = {
    merkleRoot: root,
    tokenTotal: allocations.reduce((acc, a) => acc + BigInt(a.allocation_tokens), 0n).toString(),
    claims,
  };

  fs.writeFileSync(output, JSON.stringify(result, null, 2));
  console.log(`Merkle root: ${root}`);
  console.log(`Wrote: ${output}`);
}

main();
