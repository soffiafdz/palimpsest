#!/usr/bin/env python3
"""
Main entry point for the database CLI when run as a module.

Usage:
    python -m dev.database.cli [options] [command]
"""
from . import cli

if __name__ == "__main__":
    cli(obj={})
