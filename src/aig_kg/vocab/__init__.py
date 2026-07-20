"""Vocabulary layer: concept sets and code normalization.

For the prototype, concept sets match on normalized codes and/or name keywords (local lab/med
codes are not yet crosswalked to LOINC/RxNorm). The interface is stable, so swapping in real
OHDSI Athena crosswalks later does not change the analytics tools.
"""
from aig_kg.vocab.concept_sets import ConceptSet, REGISTRY, get

__all__ = ["ConceptSet", "REGISTRY", "get"]
