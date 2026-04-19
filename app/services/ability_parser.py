"""Ability Parser Service - Parse and classify card abilities."""
import logging
import re
from dataclasses import dataclass
from typing import Optional, Set

from app.services.keyword_extractor import extract_keywords


logger = logging.getLogger(__name__)


class EffectType:
    """Effect type constants for classification."""
    REMOVAL = "removal"        # Destruir, Desterrar, Anular
    BUFF = "buff"              # +Fuerza, +Daño, Indestructible
    DRAW = "draw"              # Robar cartas
    DAMAGE = "damage"          # Daño directo, inflige X daño
    PROTECTION = "protection"  # Guardián, Inmunidad, Resistencia
    RESOURCE = "resource"      # Generar oro, buscar oro
    DISRUPTION = "disruption"  # Descartar, botar del mazo
    SUMMON = "summon"          # Exhumar, volver al campo
    EVADE = "evade"            # Imbloqueable, Vuelo
    TEMPORAL = "temporal"      # Fase/Turno effects


@dataclass
class AbilityProfile:
    """Profile of an ability with extracted features."""
    keywords: Set[str]                # Extracted keywords
    effect_types: Set[str]            # Classified effect categories
    targets: Set[str]                 # Targets (aliado, totem, arma, oponente, mazo)
    magnitude: Optional[int]          # Numeric values (damage, draw count, etc.)
    conditions: Set[str]             # Trigger conditions (al entrar, al atacar, etc.)
    raw_text: Optional[str]           # Original text preserved


# Effect classification patterns
EFFECT_PATTERNS = {
    EffectType.REMOVAL: [
        r"\bdestruye?\b",
        r"\bdestrui(?:da|do)\b",
        r"\bdestrucc",
        r"\bdesterrar\b",
        r"\bdestierra?\b",
        r"\banula?\b",
        r"\bsacrifica?\b",
        r"\belimina?\b",
    ],
    EffectType.BUFF: [
        r"\b\+\s*\d+\s*fuerza\b",
        r"\b\+\s*\d+\s*daño\b",
        r"\b\+\s*\d+\s*vida\b",
        r"\b\+\s*\d+\s*armadura\b",
        r"\bindestructible\b",
        r"\bpotencia\b",
        r"\bfuerza\b.*\b\+\b",
        r"\bdaño\b.*\b\+\b",
        r"\+\d+\b",  # Match standalone +X patterns (no leading word boundary because + is not a word char)
        r"\b\+\s*\d+",  # Match "+ X" with space
    ],
    EffectType.DRAW: [
        r"\broba?\s+(\d+)\s*cartas?",
        r"\broba?\s+cartas?",
    ],
    EffectType.DAMAGE: [
        r"\binflige?\s+(\d+)\s*(?:puntos\s+de\s+)?daño",
        r"\binflige?\s+daño",
        r"\bdaño\s+directo\b",
        r"\b\d+\s+daño\s+al\s+",
    ],
    EffectType.PROTECTION: [
        r"\bguardi",
        r"\binmunid",
        r"\bresistencia\b",
        r"\bprotege\b",
        r"\bimpide\b.*\bdaño\b",
    ],
    EffectType.RESOURCE: [
        r"\bgenera?\s+(\d+)\s*oro",
        r"\bgenera?\s+oro\b",
        r"\bbuscar\s+oro\b",
        r"\bprodu",
    ],
    EffectType.DISRUPTION: [
        r"\bdescarta?\s+(\d+)\s*cartas?",
        r"\bdescarta?\b",
        r"\bbota?\s+del\s+mazo\b",
        r"\bdestierra?\s+\d+\s*cartas?",
        r"\bdestierra?\b",  # Add standalone destierro/destierra
        r"\bdestierro\b",
    ],
    EffectType.SUMMON: [
        r"\bexhuma?\b",
        r"\bexhumar\b",
        r"\btraer\s+del\s+cementerio\b",
        r"\bdevuelve?\s+al\s+campo\b",
        r"\bdevolver\s+al\s+campo\b",
        r"\binvocar\b",
    ],
    EffectType.EVADE: [
        r"\bimbloqueable\b",
        r"\bvuelo\b",
        r"\bno\s+puede\s+ser\b.*\bbloqueado",
    ],
    EffectType.TEMPORAL: [
        r"\bal\s+entrar\b",
        r"\bal\s+salir\b",
        r"\bal\s+ataca?\b",
        r"\bal\s+defende?\b",
        r"\bcuando\b",  # Add when/cuando trigger
        r"\bsi\b.*\bentonces\b",
        r"\bcomienzo\s+del\s+turno\b",
        r"\bal\s+final\s+del\s+turno\b",
        r"\bfase\s+de\b",
        r"\bturno\b",
    ],
}


# Target extraction patterns
TARGET_PATTERNS = [
    r"\baliado\b",
    r"\btotem\b",
    r"\barma\b",
    r"\boponente\b",
    r"\bcemento\b",
    r"\bcementerio\b",
    r"\bmazo\b",
    r"\bmano\b",
    r"\bcampo\b",
    r"\bcastillo\b",
    r"\bunidad\b",
    r"\bcarta\b",
    r"\bjugador\b",
    r"\btu\b",
]


# Condition extraction patterns
CONDITION_PATTERNS = [
    r"\bal\s+entrar\b",
    r"\bal\s+salir\b",
    r"\bal\s+atacar\b",
    r"\bal\s+defender\b",
    r"\bcomienzo\s+del\s+turno\b",
    r"\bal\s+final\s+del\s+turno\b",
    r"\bcuando\b",
    r"\bsi\b",
    r"\bmientras\b",
    r"\bcada\s+vez\b",
]


def parse_ability(text: Optional[str]) -> AbilityProfile:
    """
    Parse ability text and extract features.

    Args:
        text: Ability text to parse

    Returns:
        AbilityProfile with extracted keywords, effect types, targets, etc.
    """
    if not text:
        return AbilityProfile(
            keywords=set(),
            effect_types=set(),
            targets=set(),
            magnitude=None,
            conditions=set(),
            raw_text=text,
        )

    text_lower = text.lower()

    # Extract keywords using existing function
    keywords = extract_keywords(text)

    # Classify effect types
    effect_types = _classify_effect_types(text_lower)

    # Extract targets
    targets = _extract_targets(text_lower)

    # Extract magnitude (first numeric value found)
    magnitude = _extract_magnitude(text_lower)

    # Extract conditions
    conditions = _extract_conditions(text_lower)

    return AbilityProfile(
        keywords=keywords,
        effect_types=effect_types,
        targets=targets,
        magnitude=magnitude,
        conditions=conditions,
        raw_text=text,
    )


def _classify_effect_types(text: str) -> Set[str]:
    """Classify the effect types present in the text."""
    found = set()

    for effect_type, patterns in EFFECT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text):
                found.add(effect_type)
                break  # Only add each effect type once

    return found


def _extract_targets(text: str) -> Set[str]:
    """Extract target mentions from the text."""
    found = set()

    for pattern in TARGET_PATTERNS:
        if re.search(pattern, text):
            # Extract the matched target word
            match = re.search(pattern, text)
            if match:
                target = match.group(0)
                found.add(target)

    return found


def _extract_magnitude(text: str) -> Optional[int]:
    """Extract the first numeric value (magnitude) from the text."""
    # Look for patterns like "roba 2 cartas", "inflige 3 daño", "+2 fuerza", etc.
    patterns = [
        r"\broba?\s+(\d+)\s*cartas?",
        r"\binflige?\s+(\d+)\s*(?:puntos\s+de\s+)?daño",
        r"\bgenera?\s+(\d+)\s*oro",
        r"\b\+\s*(\d+)",  # Match "+X" patterns first
        r"\b(\d+)\s+daño\b",
        r"\bdescarta?\s+(\d+)\s*cartas?",
        r"\bdestierra?\s+(?:las\s+)?(\d+)\s*primeras?\s*cartas?",  # "destierra las 3 primeras cartas"
        r"\bdestierra?\s+(\d+)\s*cartas?",
        r"\b(\d+)\s*fuerza\b",  # "X fuerza"
        r"\b(\d+)\s+vida\b",  # "X vida"
        r"\b(\d+)\s+armadura\b",  # "X armadura"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return int(match.group(1))
            except (IndexError, ValueError):
                continue

    return None


def _extract_conditions(text: str) -> Set[str]:
    """Extract trigger conditions from the text."""
    found = set()

    for pattern in CONDITION_PATTERNS:
        if re.search(pattern, text):
            match = re.search(pattern, text)
            if match:
                condition = match.group(0)
                found.add(condition)

    return found


def calculate_effect_similarity(
    profile_a: AbilityProfile,
    profile_b: AbilityProfile
) -> float:
    """
    Calculate similarity score between two ability profiles.

    Scoring:
    - Shared effect types: 40% weight
    - Shared keywords: 30% weight
    - Shared targets: 15% weight
    - Similar magnitude: 15% weight

    Args:
        profile_a: First ability profile
        profile_b: Second ability profile

    Returns:
        Similarity score from 0.0 to 1.0
    """
    # 1. Effect type similarity (40% weight)
    effect_sim = _calculate_overlap_similarity(
        profile_a.effect_types,
        profile_b.effect_types
    )

    # 2. Keyword similarity (30% weight)
    keyword_sim = _calculate_overlap_similarity(
        profile_a.keywords,
        profile_b.keywords
    )

    # 3. Target similarity (15% weight)
    target_sim = _calculate_overlap_similarity(
        profile_a.targets,
        profile_b.targets
    )

    # 4. Magnitude similarity (15% weight)
    mag_sim = _calculate_magnitude_similarity(
        profile_a.magnitude,
        profile_b.magnitude
    )

    # Weighted average
    total_similarity = (
        effect_sim * 0.40 +
        keyword_sim * 0.30 +
        target_sim * 0.15 +
        mag_sim * 0.15
    )

    return round(total_similarity, 4)


def _calculate_overlap_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Calculate Jaccard similarity between two sets."""
    if not set_a and not set_b:
        # Both empty -> neutral similarity
        return 0.5

    if not set_a or not set_b:
        # One empty -> low similarity
        return 0.0

    shared = set_a & set_b
    total_unique = set_a | set_b

    if not total_unique:
        return 0.0

    return len(shared) / len(total_unique)


def _calculate_magnitude_similarity(
    mag_a: Optional[int],
    mag_b: Optional[int]
) -> float:
    """
    Calculate similarity between magnitudes.

    Returns:
        1.0 if both magnitudes are None
        1.0 if magnitudes are equal
        0.5 if one is None and other has value
        0.0 if both have different values
    """
    if mag_a is None and mag_b is None:
        return 1.0

    if mag_a is None or mag_b is None:
        return 0.5

    if mag_a == mag_b:
        return 1.0

    # If different, return inverse of relative difference
    # This gives partial credit for similar magnitudes
    max_mag = max(mag_a, mag_b)
    diff = abs(mag_a - mag_b)
    return max(0.0, 1.0 - (diff / max_mag))
