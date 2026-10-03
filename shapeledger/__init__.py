"""Strict, value-free JSONL shape profiling."""
from .core import ShapeError, compare, profile, validate
__all__ = ['ShapeError', 'compare', 'profile', 'validate']
