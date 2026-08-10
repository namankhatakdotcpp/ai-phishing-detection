"""CLI entry point for writing the LLM-generated phishing partition to disk.

Usage (mock, default — no cost, no API key needed):
    python -m phishshield.data.generate_llm_dataset [--out PATH] [--seed N]

Usage (cost estimate only — no network calls, no API key needed):
    python -m phishshield.data.generate_llm_dataset --dry-run
    python -m phishshield.data.generate_llm_dataset --dry-run --max-samples 100

Usage (Phase 8, real API calls — costs money, requires credentials):
    pip install -e ".[gemini]"      # default provider — GEMINI_API_KEY / GOOGLE_API_KEY
    python -m phishshield.data.generate_llm_dataset --live --max-samples 4   # canary first

    pip install -e ".[llm]"         # --provider anthropic — ANTHROPIC_API_KEY
    python -m phishshield.data.generate_llm_dataset --live --provider anthropic --max-samples 4

See `phishshield.data.generation` for the ethical/scope constraint this
module operates under (local-only output, gitignored `data/generated/`).
"""

from __future__ import annotations

import argparse

from phishshield.data.generation import (
    BRANDS,
    OBFUSCATIONS,
    TONES,
    count_unique_lure_calls,
    generate_llm_phishing_dataset,
    save_samples_jsonl,
)
from phishshield.data.llm_client import (
    ANTHROPIC_DEFAULT_EFFORT,
    ANTHROPIC_DEFAULT_MODEL,
    GEMINI_DEFAULT_MODEL,
)

DEFAULT_OUT = "data/generated/llm_phishing_v1.jsonl"
DEFAULT_PROVIDER = "gemini"

# Rough, deliberately padded per-call token estimate for --dry-run: a short
# structured-output request (system + brand/tone prompt in, {title, lure_copy}
# JSON out). This is an ESTIMATE for budget sanity-checking, not a billing
# guarantee — actual usage depends on the live model's response.
_EST_INPUT_TOKENS_PER_CALL = 250
_EST_OUTPUT_TOKENS_PER_CALL = 400

_MODEL_PRICING_PER_MTOK = {
    # (input $/MTok, output $/MTok). Anthropic: first-party Claude API rates.
    # Gemini: paid-tier rates as a conservative fallback — the free tier
    # (used by default here) covers this volume at $0, subject to rate
    # limits; verify current pricing/limits at ai.google.dev/pricing.
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "gemini-flash-latest": (0.30, 2.50),  # alias tracking whatever "flash" currently is
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}

_DEFAULT_MODEL_BY_PROVIDER = {
    "anthropic": ANTHROPIC_DEFAULT_MODEL,
    "gemini": GEMINI_DEFAULT_MODEL,
}
_DEFAULT_EFFORT_BY_PROVIDER = {
    "anthropic": ANTHROPIC_DEFAULT_EFFORT,
    "gemini": None,  # Gemini has no effort parameter
}


def _estimate_cost_usd(model: str, num_calls: int) -> float | None:
    pricing = _MODEL_PRICING_PER_MTOK.get(model)
    if pricing is None:
        return None
    input_price, output_price = pricing
    input_cost = num_calls * _EST_INPUT_TOKENS_PER_CALL / 1_000_000 * input_price
    output_cost = num_calls * _EST_OUTPUT_TOKENS_PER_CALL / 1_000_000 * output_price
    return input_cost + output_cost


def _print_dry_run(args: argparse.Namespace) -> None:
    full_grid = len(BRANDS) * len(TONES) * len(OBFUSCATIONS)
    total_samples = min(args.max_samples, full_grid) if args.max_samples else full_grid
    num_calls = count_unique_lure_calls(max_samples=args.max_samples)
    cost = _estimate_cost_usd(args.model, num_calls)

    print("=== dry run: no API calls made, no credentials required ===")
    print(f"provider: {args.provider}  model: {args.model}  effort: {args.effort}")
    print(f"total samples: {total_samples} (full grid: {full_grid})")
    print(f"unique lure-copy API calls (cached per brand+tone pair): {num_calls}")
    if cost is None:
        print(f"cost estimate: unknown model, no pricing on file for {args.model!r}")
    else:
        note = " — likely $0 on the free tier, subject to rate limits" if args.provider == "gemini" else ""
        print(
            f"cost estimate (paid-tier rates): ~${cost:.4f}{note} "
            f"(ESTIMATE only, assumes ~{_EST_INPUT_TOKENS_PER_CALL} input + "
            f"~{_EST_OUTPUT_TOKENS_PER_CALL} output tokens/call — not a billing guarantee)"
        )
    print("\nRe-run with --live (and no --dry-run) to actually spend this budget.")
    print("Recommended: try --live --max-samples 4 first and read the output before the full grid.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output JSONL path")
    parser.add_argument("--seed", type=int, default=42, help="Generation seed (mock mode only)")
    parser.add_argument(
        "--max-samples", type=int, default=None,
        help="Hard cap on total samples generated (also caps live API call count)",
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Call a real LLM API for lure copy instead of using mock templates. Costs money (or free-tier quota).",
    )
    parser.add_argument(
        "--provider", choices=["anthropic", "gemini"], default=DEFAULT_PROVIDER,
        help=f"LLM provider for --live mode (default: {DEFAULT_PROVIDER})",
    )
    parser.add_argument("--model", default=None, help="Model for --live mode (default depends on --provider)")
    parser.add_argument("--effort", default=None, help="output_config.effort, Anthropic only (default: low)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the estimated sample count / API call count / cost and exit. No network calls.",
    )
    args = parser.parse_args()

    if args.model is None:
        args.model = _DEFAULT_MODEL_BY_PROVIDER[args.provider]
    if args.effort is None:
        args.effort = _DEFAULT_EFFORT_BY_PROVIDER[args.provider]

    if args.dry_run:
        _print_dry_run(args)
        return

    llm_client = None
    if args.live:
        from phishshield.data.llm_client import build_lure_client, describe_env_key

        print(f"=== LIVE mode: calling {args.provider}/{args.model} for lure copy ===")
        print(f"credential check: {describe_env_key(args.provider)}")  # masked — never the full key
        llm_client = build_lure_client(args.provider, model=args.model, effort=args.effort)

    samples = generate_llm_phishing_dataset(seed=args.seed, llm_client=llm_client, max_samples=args.max_samples)
    save_samples_jsonl(samples, args.out)
    print(f"wrote {len(samples)} LLM-generated phishing samples to {args.out}")


if __name__ == "__main__":
    main()
