"""FastAPI 入口：化学方程式精确配平 API。"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .balancer import BalanceError, balance_equation, verify_coefficients
from .parser import FormulaError
from .schemas import (
    BalanceRequest,
    BalanceResponse,
    VerifyRequest,
    VerifyResponse,
)

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
