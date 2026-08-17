"""Minimal evaluation harness around the existing Agent and Verifier.

Package layout:
- tasks/    task JSON files
- runner.py loads tasks, runs the Agent in isolated workspaces
- judge.py  executes verification commands via the existing Verifier
- metrics.py aggregates pass/fail into simple counts and success rate
- results/  persisted results JSON
"""
