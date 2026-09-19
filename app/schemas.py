"""请求 / 响应模型。"""
from __future__ import annotations

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
