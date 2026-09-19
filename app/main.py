"""FastAPI 入口：化学方程式精确配平 API。"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .balancer import BalanceError, balance_equation, verify_coefficients
from .parser import FormulaError
from .schemas import (
    BalanceRequest,
    BalanceResponse,
    StoichiometryRequest,
    StoichiometryResponse,
    VerifyRequest,
    VerifyResponse,
)
from .stoichiometry import Feed, StoichiometryError, compute_stoichiometry

app = FastAPI(
    title="化学方程式配平 API",
    description=(
        "基于元素守恒矩阵（含电荷行）与有理数高斯消元零空间的精确配平服务。"
        "支持嵌套括号、点号结晶水与末尾离子电荷。"
    ),
    version="1.0.0",
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/api/v1/balance",
    response_model=BalanceResponse,
    tags=["balance"],
    summary="配平化学方程式",
    responses={
        400: {"description": "化学式无法解析"},
        422: {"description": "零空间维数不为 1，或无法化为全正系数"},
    },
)
def balance(req: BalanceRequest) -> dict:
    try:
        return balance_equation(req.reactants, req.products)
    except FormulaError as exc:
        raise HTTPException(status_code=400, detail=f"化学式解析失败: {exc}") from exc
    except BalanceError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": exc.message, "null_space_dim": exc.nullity},
        ) from exc


@app.post(
    "/api/v1/verify",
    response_model=VerifyResponse,
    tags=["balance"],
    summary="校验给定系数是否配平",
    responses={400: {"description": "化学式无法解析或系数数量不匹配"}},
)
def verify(req: VerifyRequest) -> dict:
    if len(req.reactant_coefficients) != len(req.reactants):
        raise HTTPException(
            status_code=400,
            detail="reactant_coefficients 数量必须与 reactants 一致",
        )
    if len(req.product_coefficients) != len(req.products):
        raise HTTPException(
            status_code=400,
            detail="product_coefficients 数量必须与 products 一致",
        )
    if any(c <= 0 for c in req.reactant_coefficients + req.product_coefficients):
        raise HTTPException(status_code=400, detail="系数必须为正整数")
    try:
        return verify_coefficients(
            req.reactants,
            req.products,
            req.reactant_coefficients,
            req.product_coefficients,
        )
    except FormulaError as exc:
        raise HTTPException(status_code=400, detail=f"化学式解析失败: {exc}") from exc


@app.post(
    "/api/v1/stoichiometry",
    response_model=StoichiometryResponse,
    tags=["stoichiometry"],
    summary="化学计量计算：限制反应物、理论产量与剩余量",
    responses={
        400: {
            "description": "投料缺失/重复/非正数量/非反应物、不支持的元素原子量，"
            "或化学式无法解析"
        },
        422: {"description": "方程无法配平，或请求体校验失败"},
    },
)
def stoichiometry(req: StoichiometryRequest) -> dict:
    feeds = [Feed(formula=f.formula, amount=f.amount, unit=f.unit) for f in req.feeds]
    try:
        return compute_stoichiometry(
            req.reactants, req.products, feeds, req.precision
        )
    except StoichiometryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FormulaError as exc:
        raise HTTPException(status_code=400, detail=f"化学式解析失败: {exc}") from exc
    except BalanceError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": exc.message, "null_space_dim": exc.nullity},
        ) from exc
