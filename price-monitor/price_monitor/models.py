from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Product:
    title: str
    price: Decimal
    currency: str
    availability: str
    in_stock: bool
    rating: int
    url: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["price"] = format(self.price, "f")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Product:
        return cls(
            title=str(data["title"]),
            price=Decimal(str(data["price"])),
            currency=str(data.get("currency") or "GBP"),
            availability=str(data["availability"]),
            in_stock=bool(data["in_stock"]),
            rating=int(str(data["rating"])),
            url=str(data["url"]),
        )
