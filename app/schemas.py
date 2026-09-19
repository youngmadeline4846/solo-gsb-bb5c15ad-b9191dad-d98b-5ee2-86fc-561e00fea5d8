"""请求 / 响应模型。"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class BalanceRequest(BaseModel):
    reactants: list[str] = Field(
        min_length=1,
        description="反应物分子式列表",
        examples=[["KMnO4", "HCl"]],
    )
    products: list[str] = Field(
        min_length=1,
        description="生成物分子式列表",
        examples=[["KCl", "MnCl2", "H2O", "Cl2"]],
    )


class ElementAccount(BaseModel):
    element: str
    reactants: int = Field(description="反应物侧该元素原子总数")
    products: int = Field(description="生成物侧该元素原子总数")
    balanced: bool


class ChargeAccount(BaseModel):
    reactants: int = Field(description="反应物侧总电荷")
    products: int = Field(description="生成物侧总电荷")
    balanced: bool


class BalanceResponse(BaseModel):
    equation: str
    coefficients: list[int] = Field(description="全部系数（先反应物后生成物）")
    reactant_coefficients: list[int]
    product_coefficients: list[int]
    elements: list[ElementAccount] = Field(description="逐元素核算")
    charge: ChargeAccount = Field(description="电荷核算")
    balanced: bool


class VerifyRequest(BaseModel):
    reactants: list[str] = Field(min_length=1, examples=[["H2", "O2"]])
    products: list[str] = Field(min_length=1, examples=[["H2O"]])
    reactant_coefficients: list[int] = Field(min_length=1, examples=[[2, 1]])
    product_coefficients: list[int] = Field(min_length=1, examples=[[2]])


class VerifyResponse(BaseModel):
    balanced: bool
    equation: str
    elements: list[ElementAccount]
    charge: ChargeAccount
    gcd: int = Field(description="系数的最大公约数")
    is_reduced: bool = Field(description="系数是否已约简（gcd == 1）")
    message: str


class FeedInput(BaseModel):
    formula: str = Field(
        description="投料物质分子式（须为反应物之一）", examples=["H2"]
    )
    amount: Decimal = Field(description="投料数量（正数）", examples=["2.5"])
    unit: Literal["mol", "g"] = Field(description="投料单位，仅支持 mol 或 g")


class StoichiometryRequest(BaseModel):
    reactants: list[str] = Field(min_length=1, examples=[["H2", "O2"]])
    products: list[str] = Field(min_length=1, examples=[["H2O"]])
    feeds: list[FeedInput] = Field(min_length=1, description="各反应物投料")
    precision: int = Field(
        default=4, ge=2, le=8, description="输出小数位数（四舍五入，2～8）"
    )


class ReactantResult(BaseModel):
    formula: str
    coefficient: int = Field(description="配平系数")
    molar_mass_g_per_mol: str = Field(description="摩尔质量（g/mol）")
    fed_amount: str = Field(description="投料数量（按请求原样回显）")
    fed_unit: str = Field(description="投料单位（mol 或 g）")
    fed_mol: str = Field(description="投料折算物质的量（mol）")
    fed_g: str = Field(description="投料折算质量（g）")
    remaining_mol: str = Field(description="剩余量（mol）")
    remaining_g: str = Field(description="剩余量（g）")
    is_limiting: bool = Field(description="是否为限制反应物")


class ProductResult(BaseModel):
    formula: str
    coefficient: int = Field(description="配平系数")
    molar_mass_g_per_mol: str = Field(description="摩尔质量（g/mol）")
    theoretical_mol: str = Field(description="理论产量（mol）")
    theoretical_g: str = Field(description="理论产量（g）")


class StoichiometryResponse(BaseModel):
    equation: str
    coefficients: list[int] = Field(description="全部系数（先反应物后生成物）")
    reactant_coefficients: list[int]
    product_coefficients: list[int]
    precision: int = Field(description="本次输出采用的小数位数")
    extent_mol: str = Field(description="理论反应进度 ξ（mol）")
    limiting_reactants: list[str] = Field(description="限制反应物（可能并列多个）")
    reactants: list[ReactantResult]
    products: list[ProductResult]
