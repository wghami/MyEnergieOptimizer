"""Composition root: the only module that wires concrete adapters to ports (dishka, ADR 0002).

Providers are added milestone by milestone; nothing else may construct its own dependencies.
"""
