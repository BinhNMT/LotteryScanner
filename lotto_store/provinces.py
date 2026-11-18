"""Official XSMN (Southern Vietnam Lottery) province metadata and helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class XsmnProvinceMeta:
    """Metadata for an official XSMN province/city."""

    code: str
    name: str
    draw_days: tuple[int, ...]  # 0 = Sunday .. 6 = Saturday


XSMN_PROVINCES: tuple[XsmnProvinceMeta, ...] = (
    XsmnProvinceMeta(code="TPHCM", name="TP. Hồ Chí Minh", draw_days=(1, 6)),
    XsmnProvinceMeta(code="DT", name="Đồng Tháp", draw_days=(1,)),
    XsmnProvinceMeta(code="CM", name="Cà Mau", draw_days=(1,)),
    XsmnProvinceMeta(code="BT", name="Bến Tre", draw_days=(2,)),
    XsmnProvinceMeta(code="VT", name="Vũng Tàu", draw_days=(2,)),
    XsmnProvinceMeta(code="BL", name="Bạc Liêu", draw_days=(2,)),
    XsmnProvinceMeta(code="DN", name="Đồng Nai", draw_days=(3,)),
    XsmnProvinceMeta(code="CT", name="Cần Thơ", draw_days=(3,)),
    XsmnProvinceMeta(code="ST", name="Sóc Trăng", draw_days=(3,)),
    XsmnProvinceMeta(code="TN", name="Tây Ninh", draw_days=(4,)),
    XsmnProvinceMeta(code="AG", name="An Giang", draw_days=(4,)),
    XsmnProvinceMeta(code="BTH", name="Bình Thuận", draw_days=(4,)),
    XsmnProvinceMeta(code="VL", name="Vĩnh Long", draw_days=(5,)),
    XsmnProvinceMeta(code="BD", name="Bình Dương", draw_days=(5,)),
    XsmnProvinceMeta(code="TV", name="Trà Vinh", draw_days=(5,)),
    XsmnProvinceMeta(code="LA", name="Long An", draw_days=(6,)),
    XsmnProvinceMeta(code="BP", name="Bình Phước", draw_days=(6,)),
    XsmnProvinceMeta(code="HG", name="Hậu Giang", draw_days=(6,)),
    XsmnProvinceMeta(code="TG", name="Tiền Giang", draw_days=(0,)),
    XsmnProvinceMeta(code="KG", name="Kiên Giang", draw_days=(0,)),
    XsmnProvinceMeta(code="DL", name="Đà Lạt", draw_days=(0,)),
)

XSMN_PROVINCE_MAP: dict[str, XsmnProvinceMeta] = {
    province.code: province for province in XSMN_PROVINCES
}


def normalize_province_code(code: str, *, validate: bool = True) -> str:
    """Normalize a province code (strip & uppercase) and optionally validate it."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("province_code must be a non-empty string.")
    normalized = code.strip().upper()
    if validate and normalized not in XSMN_PROVINCE_MAP:
        raise ValueError(f"Unknown XSMN province code: {normalized!r}")
    return normalized
