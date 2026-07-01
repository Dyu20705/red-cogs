from __future__ import annotations

from copy import deepcopy

from ..blueprint import CATEGORIES, ROLE_SPECS


def personal_profile() -> dict:
    return {"roles": deepcopy(ROLE_SPECS), "categories": deepcopy(CATEGORIES)}
