#!/usr/bin/env python3
"""Extract benchmark results from vLLM bench serve log files into CSV and JSON.

Usage:
    python extract_benchmark.py [--results-dir DIR] [--config FILE] [--output-dir DIR]

Reads model_config.json for folder-to-model mappings, parses all benchmark
log files found under benchmark_results/results/{folder}/, and outputs:
  - benchmark_data.csv   (flat table: one row per model+CCU)
  - benchmark_data.json  (structured: per-model, per-CCU metrics)
"""

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from collections import OrderedDict

RESULTS_DIR = Path(__file__).parent / "benchmark_results" / "results"
CONFIG_FILE = Path(__file__).parent / "model_config.json"
OUTPUT_DIR = Path(__file__).parent


def load_config(config_path: Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_benchmark_log(filepath: Path) -> dict | None:
    """Parse a single vLLM bench serve log file and return metrics dict."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    result_section = content.rfind("============ Serving Benchmark Result ============")
    if result_section == -1:
        print(f"  WARNING: No benchmark result section in {filepath.name}", file=sys.stderr)
        return None

    section = content[result_section:]

    patterns = {
        "successful_requests": r"Successful requests:\s+(\d+)",
        "failed_requests": r"Failed requests:\s+(\d+)",
        "max_concurrency": r"Maximum request concurrency:\s+(\d+)",
        "duration_s": r"Benchmark duration \(s\):\s+([\d.]+)",
        "total_input_tokens": r"Total input tokens:\s+(\d+)",
        "total_output_tokens": r"Total generated tokens:\s+(\d+)",
        "req_throughput": r"Request throughput \(req/s\):\s+([\d.]+)",
        "output_tok_throughput": r"Output token throughput \(tok/s\):\s+([\d.]+)",
        "peak_output_tok_throughput": r"Peak output token throughput \(tok/s\):\s+([\d.]+)",
        "peak_concurrent_requests": r"Peak concurrent requests:\s+([\d.]+)",
        "total_tok_throughput": r"Total token throughput \(tok/s\):\s+([\d.]+)",
        "ttft_mean_ms": r"Mean TTFT \(ms\):\s+([\d.]+)",
        "ttft_median_ms": r"Median TTFT \(ms\):\s+([\d.]+)",
        "ttft_p99_ms": r"P99 TTFT \(ms\):\s+([\d.]+)",
        "tpot_mean_ms": r"Mean TPOT \(ms\):\s+([\d.]+)",
        "tpot_median_ms": r"Median TPOT \(ms\):\s+([\d.]+)",
        "tpot_p99_ms": r"P99 TPOT \(ms\):\s+([\d.]+)",
        "itl_mean_ms": r"Mean ITL \(ms\):\s+([\d.]+)",
        "itl_median_ms": r"Median ITL \(ms\):\s+([\d.]+)",
        "itl_p99_ms": r"P99 ITL \(ms\):\s+([\d.]+)",
    }

    metrics = {}
    for key, pattern in patterns.items():
        m = re.search(pattern, section)
        if m:
            val = m.group(1)
            metrics[key] = int(val) if key in (
                "successful_requests", "failed_requests", "max_concurrency",
                "total_input_tokens", "total_output_tokens"
            ) else float(val)
        else:
            metrics[key] = None

    metrics["itl_mean_ms"] = metrics.get("itl_mean_ms") or metrics.get("tpot_mean_ms")

    ccu_match = re.search(r"_rate(\d+)\.log$", filepath.name)
    if ccu_match:
        metrics["ccu"] = int(ccu_match.group(1))
    else:
        print(f"  WARNING: Cannot extract CCU from filename {filepath.name}", file=sys.stderr)
        return None

    return metrics


def compute_e2e_latency(metrics: dict, output_tokens: int) -> float | None:
    """E2E latency = TTFT_mean + output_tokens * TPOT_mean (in seconds)."""
    ttft = metrics.get("ttft_mean_ms")
    tpot = metrics.get("tpot_mean_ms")
    if ttft is not None and tpot is not None and output_tokens > 0:
        return round((ttft + output_tokens * tpot) / 1000.0, 2)
    return None


def extract_all(results_dir: Path, config: dict) -> tuple[list[dict], dict]:
    """Extract all benchmark data. Returns (flat_rows, structured_json)."""
    models_cfg = config["models"]
    benchmark_cfg = config.get("benchmark_config", {})
    output_tokens = benchmark_cfg.get("output_tokens", 5000)
    flat_rows = []
    structured = OrderedDict()

    for model_cfg in models_cfg:
        folder = model_cfg["folder"]
        model_dir = results_dir / folder
        if not model_dir.exists():
            print(f"  WARNING: Directory not found: {model_dir}", file=sys.stderr)
            continue

        short_name = model_cfg["short_name"]
        structured[short_name] = {
            "full_name": model_cfg["full_name"],
            "display_name": model_cfg["display_name"],
            "chart_label": model_cfg["chart_label"],
            "hardware": model_cfg["hardware"],
            "hardware_short": model_cfg["hardware_short"],
            "gpu_count": model_cfg["gpu_count"],
            "params": model_cfg["params"],
            "quantization": model_cfg["quantization"],
            "model_type": model_cfg["model_type"],
            "color": model_cfg["color"],
            "css_class": model_cfg["css_class"],
            "huggingface_url": model_cfg.get("huggingface_url", ""),
            "ccu_levels": [],
            "data": {}
        }

        log_files = sorted(model_dir.glob("*.log"))
        if not log_files:
            print(f"  WARNING: No .log files in {model_dir}", file=sys.stderr)
            continue

        for log_file in log_files:
            metrics = parse_benchmark_log(log_file)
            if metrics is None:
                continue

            ccu = metrics["ccu"]
            e2e = compute_e2e_latency(metrics, output_tokens)
            structured[short_name]["ccu_levels"].append(ccu)
            structured[short_name]["data"][str(ccu)] = {
                "successful_requests": metrics.get("successful_requests"),
                "failed_requests": metrics.get("failed_requests"),
                "duration_s": metrics.get("duration_s"),
                "req_throughput": metrics.get("req_throughput"),
                "total_tok_throughput": metrics.get("total_tok_throughput"),
                "output_tok_throughput": metrics.get("output_tok_throughput"),
                "peak_output_tok_throughput": metrics.get("peak_output_tok_throughput"),
                "e2e_latency_s": e2e,
                "ttft_mean_ms": metrics.get("ttft_mean_ms"),
                "ttft_median_ms": metrics.get("ttft_median_ms"),
                "ttft_p99_ms": metrics.get("ttft_p99_ms"),
                "tpot_mean_ms": metrics.get("tpot_mean_ms"),
                "tpot_median_ms": metrics.get("tpot_median_ms"),
                "tpot_p99_ms": metrics.get("tpot_p99_ms"),
                "itl_mean_ms": metrics.get("itl_mean_ms"),
                "itl_median_ms": metrics.get("itl_median_ms"),
                "itl_p99_ms": metrics.get("itl_p99_ms"),
            }

            row = {
                "model_folder": folder,
                "model_short_name": short_name,
                "model_display_name": model_cfg["display_name"],
                "model_full_name": model_cfg["full_name"],
                "hardware": model_cfg["hardware_short"],
                "ccu": ccu,
                "successful_requests": metrics.get("successful_requests"),
                "failed_requests": metrics.get("failed_requests"),
                "duration_s": metrics.get("duration_s"),
                "req_throughput_req_s": metrics.get("req_throughput"),
                "total_tok_throughput_tok_s": metrics.get("total_tok_throughput"),
                "output_tok_throughput_tok_s": metrics.get("output_tok_throughput"),
                "peak_output_tok_throughput_tok_s": metrics.get("peak_output_tok_throughput"),
                "e2e_latency_s": e2e,
                "ttft_mean_ms": metrics.get("ttft_mean_ms"),
                "ttft_median_ms": metrics.get("ttft_median_ms"),
                "ttft_p99_ms": metrics.get("ttft_p99_ms"),
                "tpot_mean_ms": metrics.get("tpot_mean_ms"),
                "tpot_median_ms": metrics.get("tpot_median_ms"),
                "tpot_p99_ms": metrics.get("tpot_p99_ms"),
                "itl_mean_ms": metrics.get("itl_mean_ms"),
                "itl_median_ms": metrics.get("itl_median_ms"),
                "itl_p99_ms": metrics.get("itl_p99_ms"),
            }
            flat_rows.append(row)

        structured[short_name]["ccu_levels"].sort()

    return flat_rows, structured


def write_csv(rows: list[dict], output_path: Path):
    if not rows:
        print("  No data to write to CSV", file=sys.stderr)
        return

    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Written {len(rows)} rows to {output_path}")


def write_json(structured: dict, output_path: Path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(structured, f, indent=2, ensure_ascii=False)
    print(f"  Written structured JSON to {output_path}")


def write_data_js(structured: dict, config: dict, output_path: Path):
    js_content = (
        "// Auto-generated by extract_benchmark.py — do not edit manually\n"
        "// This file embeds benchmark data for offline viewing (file:// protocol)\n\n"
        f"window.BENCHMARK_DATA = {json.dumps(structured, indent=2, ensure_ascii=False)};\n\n"
        f"window.MODEL_CONFIG = {json.dumps(config, indent=2, ensure_ascii=False)};\n"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"  Written data.js to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Extract vLLM benchmark results to CSV/JSON")
    parser.add_argument("--results-dir", default=str(RESULTS_DIR), help="Path to benchmark results directory")
    parser.add_argument("--config", default=str(CONFIG_FILE), help="Path to model_config.json")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory for CSV/JSON files")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    config_path = Path(args.config)
    output_dir = Path(args.output_dir)

    print(f"Loading config from {config_path}")
    config = load_config(config_path)

    print(f"Extracting benchmark data from {results_dir}")
    flat_rows, structured = extract_all(results_dir, config)

    csv_path = output_dir / "benchmark_data.csv"
    json_path = output_dir / "benchmark_data.json"
    js_path = output_dir / "data.js"

    write_csv(flat_rows, csv_path)
    write_json(structured, json_path)
    write_data_js(structured, config, js_path)

    print("Done!")


if __name__ == "__main__":
    main()