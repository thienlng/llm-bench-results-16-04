#!/bin/bash
# Run the benchmark data extraction pipeline
# Usage: ./run_pipeline.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Extracting benchmark data ==="
python3 extract_benchmark.py "$@"

echo ""
echo "=== Generated files ==="
echo "  benchmark_data.csv  - Flat table (one row per model+CCU)"
echo "  benchmark_data.json - Structured data (per-model, per-CCU metrics)"
echo "  model_config.json   - Model metadata and configuration"
echo ""
echo "Open index.html in a browser to view the report."