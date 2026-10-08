"""Compatibility entry point for the corrected overnight evidence.

The old Rev4 duplicate backtest has been retired. This regenerates the same
search, benchmarks, concentration and bootstrap checks used by Rev11.
Run python run.py for the full submission, including the PDF.
"""
from overnight_strategy_v6 import main

if __name__ == "__main__":
    main()
