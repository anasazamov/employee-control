"""ltree yordamchilar. Bo'lim-yo'llari org-ildizli (o_{shortid}...) va faqat
[a-z0-9_] label'lardan iborat bo'lishi shart — GiST subtree-so'rovlar shunga tayanadi."""

import re
import secrets

_LABEL_RE = re.compile(r"^[a-z0-9_]+$")


def slug_label(name: str) -> str:
    """Ixtiyoriy nomdan ltree-label. Bo'sh chiqsa tasodifiy suffiks — hech qachon
    bo'sh label bo'lmaydi (ltree buni rad etadi)."""
    label = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not label:
        label = "n"
    # Ota-yo'l ostida yagonalik chaqiruvchida tekshiriladi; bu yerda faqat shakl
    return label


def is_valid_path(path: str) -> bool:
    return bool(path) and all(_LABEL_RE.match(p) for p in path.split("."))


def unique_child_path(parent_path: str, name: str, existing_labels: set[str]) -> str:
    """Ota ostida yagona label bilan to'liq yo'l. Konflikt bo'lsa qisqa suffiks."""
    base = slug_label(name)
    label = base
    while label in existing_labels:
        label = f"{base}_{secrets.token_hex(2)}"
    return f"{parent_path}.{label}"
