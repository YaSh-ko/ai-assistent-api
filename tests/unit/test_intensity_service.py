"""Tests for valence → intensity mapping."""
from src.services.intensity_service import valence_to_intensity


def test_valence_to_intensity_maps_scale():
    assert valence_to_intensity(0.0) == 0.0
    assert valence_to_intensity(1.0) == 10.0
    assert valence_to_intensity(-1.0) == -10.0
    assert valence_to_intensity(0.5) == 5.0


def test_valence_to_intensity_clamps():
    assert valence_to_intensity(2.0) == 10.0
    assert valence_to_intensity(-3.0) == -10.0


def test_valence_to_intensity_none_for_missing():
    assert valence_to_intensity(None) is None
    assert valence_to_intensity("bad") is None
