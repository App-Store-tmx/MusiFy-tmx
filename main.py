#!/usr/bin/env python3
"""Musify — Music Streaming for Termux Desktop"""
import sys
import os

# Ensure src is importable when run from project root
sys.path.insert(0, os.path.dirname(__file__))

from src.app import main

if __name__ == "__main__":
    main()
