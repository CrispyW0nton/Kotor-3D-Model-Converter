#!/usr/bin/env python3
"""
KotorModTools – Entry Point
"""
import sys, os, logging

# Ensure the package root is on the path
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s  %(message)s"
)

def main():
    from src.gui.main_window import run
    run()

if __name__ == "__main__":
    main()
