"""Shared keyword extraction utilities."""
from typing import Optional, Set


def extract_keywords(text: Optional[str]) -> Set[str]:
    """Extract keywords from ability text."""
    if not text:
        return set()

    found = set()
    text_lower = text.lower()

    # Map of keyword -> possible forms (stems/conjugations) to match
    keyword_forms = {
        "Furia": ["furia"],
        "Imbloqueable": ["imbloqueable"],
        "Indestructible": ["indestructible"],
        "Inmunidad": ["inmunidad"],
        "Exhumar": ["exhumar", "exhuma"],
        "Guardián": ["guardián", "guardian"],
        "Retador": ["retador"],
        "Única": ["única", "unica"],
        "Errante": ["errante"],
        "Mercenario": ["mercenario"],
        "Maquinaria": ["maquinaria"],
        "Botar": ["botar", "bota"],
        "Desterrar": ["desterrar", "destierra", "destierro"],
        "Destruir": ["destruir", "destruye", "destruida", "destruido"],
        "Anular": ["anular", "anula"],
        "Robar": ["robar", "roba"],
        "Daño directo": ["daño directo", "daño directo"],
        "Oro Inicial": ["oro inicial"],
        "Generar": ["generar", "genera"],
        "Vuelo": ["vuelo"],
        "Templado": ["templado"],
        "Provocar": ["provocar", "provoca"],
        "Celeridad": ["celeridad"],
        "Vigilancia": ["vigilancia"],
        "Alcanzar": ["alcanzar", "alcanza"],
        "Atacar": ["atacar", "ataca", "ataque"],
        "Defender": ["defender", "defiende", "defensa"],
        "Mazo": ["mazo"],
        "Mano": ["mano"],
        "Campo": ["campo"],
        "Cementerio": ["cementerio"],
        "Destierro": ["destierro"],
        "Turno": ["turno"],
        "Fase": ["fase"],
        "Combate": ["combate"],
        "Vida": ["vida"],
        "Armadura": ["armadura"],
        "Resistencia": ["resistencia"],
    }

    for keyword, forms in keyword_forms.items():
        for form in forms:
            if form in text_lower:
                found.add(keyword)
                break

    return found
