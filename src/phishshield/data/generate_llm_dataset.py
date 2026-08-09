"""CLI entry point for writing the mock LLM-generated phishing partition to disk.

Usage:
    python -m phishshield.data.generate_llm_dataset [--out PATH] [--seed N]

See `phishshield.data.generation` for the ethical/scope constraint this
module operates under (mocked generation, local-only output).
"""

from __future__ import annotations

import argparse

from phishshield.data.generation import generate_llm_phishing_dataset, save_samples_jsonl

DEFAULT_OUT = "data/generated/llm_phishing_v1.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output JSONL path")
    parser.add_argument("--seed", type=int, default=42, help="Generation seed")
    args = parser.parse_args()

    samples = generate_llm_phishing_dataset(seed=args.seed)
    save_samples_jsonl(samples, args.out)
    print(f"wrote {len(samples)} LLM-generated phishing samples to {args.out}")


if __name__ == "__main__":
    main()
