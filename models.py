"""Domain models for the COS golden dataset."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class RecommendedProduct:
    """A product recommended in the 'Style with' section."""

    product_id: str
    product_name: str
    product_url: str
    product_images: list[str] = field(default_factory=list)


@dataclass
class SourceProduct:
    """A source product with its Style-with recommendations."""

    source_product_id: str
    source_product_name: str
    source_product_url: str
    source_product_images: list[str]
    section: str
    recommended_products: list[RecommendedProduct] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> SourceProduct:
        recs = [
            RecommendedProduct(**rp) for rp in d.get("recommended_products", [])
        ]
        return cls(
            source_product_id=d["source_product_id"],
            source_product_name=d["source_product_name"],
            source_product_url=d["source_product_url"],
            source_product_images=d["source_product_images"],
            section=d["section"],
            recommended_products=recs,
        )


@dataclass
class CrawlState:
    """Resumable crawl state: discovered URLs and already-scraped product IDs."""

    discovered_urls: dict[str, list[str]] = field(default_factory=dict)
    scraped_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> CrawlState:
        return cls(
            discovered_urls=d.get("discovered_urls", {}),
            scraped_ids=d.get("scraped_ids", []),
        )
