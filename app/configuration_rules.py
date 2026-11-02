"""Reusable validation models for ERP master-data configuration.

Validation only: this module does not connect to PostgreSQL
or create, update, or delete database records.
"""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


OwnerType = Literal["OWN", "PARTY"]
LabourMethod = Literal["salary", "theka"]


class ConfigurationModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class EffectivePeriod(ConfigurationModel):
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_period(self):
        if (
            self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError(
                "effective_to must not be earlier than effective_from"
            )
        return self


class ProductDefinition(EffectivePeriod):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=150)
    product_type: str = Field(min_length=1, max_length=80)
    attributes: dict[str, str] = Field(default_factory=dict)
    active: bool = True


class UnitDefinition(EffectivePeriod):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=80)
    base_unit_code: str | None = None
    factor_to_base: Decimal = Field(gt=0)


class PackagingRule(EffectivePeriod):
    product_type: str = Field(min_length=1, max_length=80)
    packaging_code: str = Field(min_length=1, max_length=50)
    units_per_pack: int = Field(gt=0)
    net_weight_grams: Decimal | None = Field(default=None, gt=0)
    active: bool = True

    # Optional item-specific and nested-packaging settings.
    # Existing callers remain compatible because these fields are optional.
    product_code: str | None = Field(default=None, min_length=1, max_length=60)
    base_unit_code: str | None = Field(default=None, min_length=1, max_length=30)
    inner_packaging_code: str | None = Field(
        default=None, min_length=1, max_length=50
    )
    inner_packs_per_pack: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_packaging_relationship(self):
        has_inner_code = self.inner_packaging_code is not None
        has_inner_count = self.inner_packs_per_pack is not None

        if has_inner_code != has_inner_count:
            raise ValueError(
                "inner_packaging_code and inner_packs_per_pack must be provided together"
            )
        return self


class BabyConeMeasurement(ConfigurationModel):
    variant_code: str = Field(min_length=1, max_length=60)
    gross_weight_grams: Decimal = Field(gt=0)
    empty_core_tare_grams: Decimal = Field(ge=0)
    measured_yards: Decimal = Field(gt=0)
    measured_on: date
    operator_code: str = Field(min_length=1, max_length=60)

    @model_validator(mode="after")
    def validate_measurement(self):
        if self.gross_weight_grams <= self.empty_core_tare_grams:
            raise ValueError(
                "Gross weight must exceed empty-core tare weight"
            )
        return self

    @property
    def net_yarn_grams(self) -> Decimal:
        return self.gross_weight_grams - self.empty_core_tare_grams

    @property
    def grams_per_yard(self) -> Decimal:
        return self.net_yarn_grams / self.measured_yards


class OwnershipPolicy(EffectivePeriod):
    product_type: str = Field(min_length=1, max_length=80)
    allowed_owners: list[OwnerType] = Field(min_length=1)
    party_rate_required: bool = False
    party_stock_requires_approval: bool = False

    @model_validator(mode="after")
    def validate_party_policy(self):
        if "PARTY" in self.allowed_owners:
            if not self.party_rate_required:
                raise ValueError(
                    "PARTY stock requires an explicit party-rate policy"
                )
            if not self.party_stock_requires_approval:
                raise ValueError(
                    "PARTY stock requires an explicit approval policy"
                )
        if len(set(self.allowed_owners)) != len(self.allowed_owners):
            raise ValueError("Duplicate owner types are not allowed")
        return self


class ProcessCostRule(EffectivePeriod):
    process_code: str = Field(min_length=1, max_length=60)
    labour_method: LabourMethod
    waste_allowance_percent: Decimal = Field(
        default=Decimal("0"), ge=0, le=100
    )
    active: bool = True
