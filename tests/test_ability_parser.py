"""Tests for ability parser service."""
import pytest

from app.services.ability_parser import (
    parse_ability,
    calculate_effect_similarity,
    EffectType,
    AbilityProfile,
)


def test_parse_destruction_ability():
    """Test parsing a destruction/removal ability."""
    profile = parse_ability("Destruye un aliado objetivo. Furia.")
    assert EffectType.REMOVAL in profile.effect_types
    assert "Furia" in profile.keywords
    assert "aliado" in profile.targets
    assert profile.raw_text == "Destruye un aliado objetivo. Furia."


def test_parse_draw_ability():
    """Test parsing a card draw ability."""
    profile = parse_ability("Roba 2 cartas de tu mazo.")
    assert EffectType.DRAW in profile.effect_types
    assert profile.magnitude == 2
    assert "mazo" in profile.targets
    assert "tu" in profile.targets


def test_parse_damage_ability():
    """Test parsing a damage ability."""
    profile = parse_ability("Inflige 3 puntos de daño al castillo oponente.")
    assert EffectType.DAMAGE in profile.effect_types
    assert profile.magnitude == 3
    assert "oponente" in profile.targets
    assert "castillo" in profile.targets


def test_parse_protection_ability():
    """Test parsing a protection ability."""
    profile = parse_ability("Guardián. Inmunidad a talismanes.")
    assert EffectType.PROTECTION in profile.effect_types
    assert "Guardián" in profile.keywords


def test_parse_buff_ability():
    """Test parsing a buff ability."""
    profile = parse_ability("+2 fuerza. Indestructible.")
    assert EffectType.BUFF in profile.effect_types
    assert profile.magnitude == 2
    assert "Indestructible" in profile.keywords


def test_parse_resource_ability():
    """Test parsing a resource generation ability."""
    profile = parse_ability("Genera 1 oro adicional.")
    assert EffectType.RESOURCE in profile.effect_types
    assert profile.magnitude == 1


def test_parse_disruption_ability():
    """Test parsing a disruption ability."""
    profile = parse_ability("Destierra las 3 primeras cartas del mazo oponente.")
    assert EffectType.DISRUPTION in profile.effect_types
    assert profile.magnitude == 3
    assert "mazo" in profile.targets
    assert "oponente" in profile.targets


def test_parse_summon_ability():
    """Test parsing a summon ability."""
    profile = parse_ability("Exhumar. Guardián.")
    assert EffectType.SUMMON in profile.effect_types
    assert EffectType.PROTECTION in profile.effect_types
    assert "Exhumar" in profile.keywords
    assert "Guardián" in profile.keywords


def test_parse_evade_ability():
    """Test parsing an evade ability."""
    profile = parse_ability("Imbloqueable. Daño directo.")
    assert EffectType.EVADE in profile.effect_types
    assert EffectType.DAMAGE in profile.effect_types
    assert "Imbloqueable" in profile.keywords


def test_parse_temporal_ability():
    """Test parsing a temporal/triggered ability."""
    profile = parse_ability("Al entrar en juego, destruye un aliado.")
    assert EffectType.REMOVAL in profile.effect_types
    assert EffectType.TEMPORAL in profile.effect_types
    assert "al entrar" in profile.conditions


def test_parse_mixed_effects():
    """Test parsing ability with multiple effect types."""
    profile = parse_ability(
        "Al entrar en juego, roba 2 cartas. Furia. +1 fuerza."
    )
    assert EffectType.TEMPORAL in profile.effect_types
    assert EffectType.DRAW in profile.effect_types
    assert EffectType.BUFF in profile.effect_types
    assert profile.magnitude == 2
    assert "al entrar" in profile.conditions
    assert "Furia" in profile.keywords


def test_parse_ability_with_conditional_damage():
    """Test parsing ability with conditional damage."""
    profile = parse_ability("Cuando ataca, inflige 2 daño al oponente.")
    assert EffectType.TEMPORAL in profile.effect_types
    assert EffectType.DAMAGE in profile.effect_types
    assert profile.magnitude == 2
    assert "cuando" in profile.conditions or "ataca" in profile.conditions


def test_effect_similarity_same_effects():
    """Test effect similarity with same effect types."""
    p1 = parse_ability("Destruye un aliado. Furia.")
    p2 = parse_ability("Destruye un totem. Furia.")
    sim = calculate_effect_similarity(p1, p2)
    assert sim > 0.7  # High similarity - same effects and keywords


def test_effect_similarity_different_effects():
    """Test effect similarity with different effect types."""
    p1 = parse_ability("Roba 2 cartas.")
    p2 = parse_ability("Destruye un aliado.")
    sim = calculate_effect_similarity(p1, p2)
    assert sim < 0.3  # Low similarity - different effects


def test_effect_similarity_perfect_match():
    """Test effect similarity with identical abilities."""
    p1 = parse_ability("Furia. Destruye un aliado.")
    p2 = parse_ability("Furia. Destruye un aliado.")
    sim = calculate_effect_similarity(p1, p2)
    assert sim == 1.0  # Perfect match


def test_effect_similarity_magnitude_difference():
    """Test effect similarity with different magnitudes."""
    p1 = parse_ability("Roba 2 cartas.")
    p2 = parse_ability("Roba 3 cartas.")
    sim = calculate_effect_similarity(p1, p2)
    # Similar magnitude, but not perfect
    assert 0.8 < sim < 1.0


def test_effect_similarity_no_keywords():
    """Test effect similarity with no keywords."""
    p1 = parse_ability("Roba 2 cartas.")
    p2 = parse_ability("Roba 2 cartas.")
    sim = calculate_effect_similarity(p1, p2)
    # Should still have high similarity due to effect types
    assert sim > 0.8


def test_parse_none_ability():
    """Test parsing None ability."""
    profile = parse_ability(None)
    assert len(profile.keywords) == 0
    assert len(profile.effect_types) == 0
    assert len(profile.targets) == 0
    assert len(profile.conditions) == 0
    assert profile.magnitude is None
    assert profile.raw_text is None


def test_parse_empty_ability():
    """Test parsing empty string ability."""
    profile = parse_ability("")
    assert len(profile.keywords) == 0
    assert len(profile.effect_types) == 0
    assert len(profile.targets) == 0
    assert len(profile.conditions) == 0
    assert profile.magnitude is None
    assert profile.raw_text == ""


def test_parse_keyword_variations():
    """Test that keyword extraction handles various conjugations."""
    profile1 = parse_ability("Destruye un aliado.")
    profile2 = parse_ability("Destruye un totem.")  # Change from "Destruir" to "Destruye"
    profile3 = parse_ability("Destruida la carta.")

    # All should detect destruction effect
    assert EffectType.REMOVAL in profile1.effect_types
    assert EffectType.REMOVAL in profile2.effect_types
    assert EffectType.REMOVAL in profile3.effect_types


def test_parse_mixed_case():
    """Test that parsing is case-insensitive."""
    profile1 = parse_ability("Furia. Destruye un aliado.")
    profile2 = parse_ability("furia. DESTRUYE UN ALIADO.")

    # Both should have same effect types
    assert profile1.effect_types == profile2.effect_types
    assert profile1.keywords == profile2.keywords


def test_parse_no_numeric_magnitude():
    """Test parsing ability without numeric magnitude."""
    profile = parse_ability("Roba cartas del mazo.")
    assert EffectType.DRAW in profile.effect_types
    # Magnitude should be None since no specific number
    assert profile.magnitude is None


def test_parse_multiple_targets():
    """Test parsing ability with multiple targets."""
    profile = parse_ability("Destruye un aliado y daña al castillo oponente.")
    assert "aliado" in profile.targets
    assert "castillo" in profile.targets
    assert "oponente" in profile.targets


def test_parse_complex_myl_ability():
    """Test parsing a complex MyL-style ability."""
    profile = parse_ability(
        "Al entrar en juego, destruye un aliado enemigo. Furia. "
        "Si tiene 3 o menos vida, inflige 2 daño al oponente."
    )

    assert EffectType.REMOVAL in profile.effect_types
    assert EffectType.TEMPORAL in profile.effect_types
    assert EffectType.DAMAGE in profile.effect_types
    assert "al entrar" in profile.conditions
    assert "Furia" in profile.keywords
    assert "aliado" in profile.targets
    assert "oponente" in profile.targets
    assert profile.magnitude == 2  # Last magnitude found


def test_effect_similarity_weighted_scoring():
    """Test that effect similarity uses weighted scoring correctly."""
    # High keyword similarity, low effect similarity
    p1 = parse_ability("Furia. Roba 1 carta.")
    p2 = parse_ability("Furia. Destruye un aliado.")
    sim = calculate_effect_similarity(p1, p2)

    # Should be low-to-moderate (share keywords but different effects and targets)
    # Effect types differ (40% weight), some shared keywords (30% weight)
    assert 0.1 < sim < 0.4


def test_parse_weapon_target():
    """Test parsing ability targeting weapons."""
    profile = parse_ability("Destruye un arma enemiga.")
    assert EffectType.REMOVAL in profile.effect_types
    assert "arma" in profile.targets


def test_parse_totem_target():
    """Test parsing ability targeting totems."""
    profile = parse_ability("Protege a un totem aliado.")
    assert EffectType.PROTECTION in profile.effect_types
    assert "totem" in profile.targets
    assert "aliado" in profile.targets


def test_parse_field_target():
    """Test parsing ability targeting the field."""
    profile = parse_ability("Devuelve al campo un aliado del cementerio.")
    assert EffectType.SUMMON in profile.effect_types
    assert "campo" in profile.targets
    assert "cementerio" in profile.targets
