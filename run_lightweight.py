#!/usr/bin/env python3
"""Instant rescore + export from cached CNN data. No network required."""

from run_screener import main

if __name__ == "__main__":
    import sys
    sys.argv = [sys.argv[0], "--from-cache", *sys.argv[1:]]
    raise SystemExit(main())
