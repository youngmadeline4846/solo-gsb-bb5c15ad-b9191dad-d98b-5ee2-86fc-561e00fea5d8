"""化学计量计算：限制反应物判定、理论产量与剩余量。

复用 parser 的分子式解析与 balancer 的配平结果，用内置原子量表在
mol / g 之间换算。全部中间计算使用 Decimal（高精度上下文），仅在
输出时按请求 precision 做四舍五入（ROUND_HALF_UP）。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

from .balancer import balance_equation
from .parser import parse_formula

# 内置原子量表（g/mol）
ATOMIC_WEIGHTS: dict[str, Decimal] = {
    "H": Decimal("1.008"),
    "C": Decimal("12.011"),
    "N": Decimal("14.007"),
    "O": Decimal("15.999"),
    "Na": Decimal("22.990"),
    "Mg": Decimal("24.305"),
    "Al": Decimal("26.982"),
    "S": Decimal("32.06"),
    "Cl": Decimal("35.45"),
    "K": Decimal("39.098"),
    "Ca": Decimal("40.078"),
    "Fe": Decimal("55.845"),
    "Cu": Decimal("63.546"),
    "Mn": Decimal("54.938"),
}

SUPPORTED_ELEMENTS = tuple(ATOMIC_WEIGHTS)


class StoichiometryError(ValueError):
    """投料或原子量等输入问题（路由层映射为 400）。"""


@dataclass
class Feed:
    """一种反应物的投料。"""

    formula: str
    amount: Decimal
    unit: str  # "mol" | "g"


def molar_mass(composition: Counter) -> Decimal:
    """由元素组成计算摩尔质量（g/mol）；含表外元素时抛 StoichiometryError。"""
    unsupported = sorted(el for el in composition if el not in ATOMIC_WEIGHTS)
    if unsupported:
        raise StoichiometryError(
            f"元素 {', '.join(unsupported)} 不在内置原子量表中"
            f"（支持 {', '.join(SUPPORTED_ELEMENTS)}）"
        )
    return sum(
        (ATOMIC_WEIGHTS[el] * count for el, count in composition.items()),
        Decimal(0),
    )


def format_decimal(value: Decimal, precision: int) -> str:
    """按 precision 位小数四舍五入（ROUND_HALF_UP）并格式化为字符串。"""
    with localcontext() as ctx:
        ctx.prec = 50
        quantum = Decimal(1).scaleb(-precision)
        rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
    if rounded == 0:
        rounded = abs(rounded)  # 避免出现 "-0.0000"
    return str(rounded)


def _validate_feeds(reactants: list[str], feeds: list[Feed]) -> dict[str, Feed]:
    """投料检查：数量为正、不重复、属于反应物、且覆盖全部反应物。"""
    reactant_keys = [r.strip() for r in reactants]
    if len(set(reactant_keys)) != len(reactant_keys):
        raise StoichiometryError("反应物列表中存在重复物质，无法一一对应投料")
    feed_map: dict[str, Feed] = {}
    for feed in feeds:
        key = feed.formula.strip()
        if not feed.amount.is_finite() or feed.amount <= 0:
            raise StoichiometryError(
                f"投料数量必须为正数（{feed.formula!r} 的投料为 {feed.amount}）"
            )
        if key in feed_map:
            raise StoichiometryError(f"同一物质重复投料: {key}")
        if key not in reactant_keys:
            raise StoichiometryError(f"投料物质 {key} 不在反应物列表中")
        feed_map[key] = feed
    missing = [r for r, k in zip(reactants, reactant_keys) if k not in feed_map]
    if missing:
        raise StoichiometryError("缺失投料: " + ", ".join(missing))
    return feed_map


def compute_stoichiometry(
    reactants: list[str],
    products: list[str],
    feeds: list[Feed],
    precision: int,
) -> dict:
    """配平 + 投料 → 限制反应物、理论反应进度、理论产量与各反应物剩余量。

    FormulaError / BalanceError 与 StoichiometryError 均由路由层映射为 4xx。
    """
    feed_map = _validate_feeds(reactants, feeds)

    # 配平与分子式解析复用现有实现
    balanced = balance_equation(reactants, products)
    coeffs = balanced["coefficients"]
    n_r = len(reactants)

    formulas = list(reactants) + list(products)
    masses = [molar_mass(parse_formula(f)[0]) for f in formulas]

    with localcontext() as ctx:
        ctx.prec = 50  # 中间计算高精度，仅在输出时按 precision 舍入

        fed_mol: list[Decimal] = []
        fed_g: list[Decimal] = []
        for i, formula in enumerate(reactants):
            feed = feed_map[formula.strip()]
            mass = masses[i]
            if feed.unit == "mol":
                n = feed.amount
                g = n * mass
            else:
                if mass == 0:
                    raise StoichiometryError(
                        f"{formula} 的摩尔质量为 0，无法按 g 换算投料"
                    )
                n = feed.amount / mass
                g = feed.amount
            fed_mol.append(n)
            fed_g.append(g)

        # 反应进度 ξ_i = n_i / ν_i，最小者（含并列）为限制反应物
        extents = [fed_mol[i] / coeffs[i] for i in range(n_r)]
        xi = min(extents)

        reactant_results = []
        limiting = []
        for i, formula in enumerate(reactants):
            feed = feed_map[formula.strip()]
            is_limiting = extents[i] == xi
            if is_limiting:
                limiting.append(formula)
            remaining = Decimal(0) if is_limiting else fed_mol[i] - coeffs[i] * xi
            reactant_results.append(
                {
                    "formula": formula,
                    "coefficient": coeffs[i],
                    "molar_mass_g_per_mol": format_decimal(masses[i], precision),
                    "fed_amount": str(feed.amount),
                    "fed_unit": feed.unit,
                    "fed_mol": format_decimal(fed_mol[i], precision),
                    "fed_g": format_decimal(fed_g[i], precision),
                    "remaining_mol": format_decimal(remaining, precision),
                    "remaining_g": format_decimal(remaining * masses[i], precision),
                    "is_limiting": is_limiting,
                }
            )

        product_results = []
        for j, formula in enumerate(products):
            k = n_r + j
            theo_mol = Decimal(coeffs[k]) * xi
            product_results.append(
                {
                    "formula": formula,
                    "coefficient": coeffs[k],
                    "molar_mass_g_per_mol": format_decimal(masses[k], precision),
                    "theoretical_mol": format_decimal(theo_mol, precision),
                    "theoretical_g": format_decimal(theo_mol * masses[k], precision),
                }
            )

    return {
        "equation": balanced["equation"],
        "coefficients": coeffs,
        "reactant_coefficients": balanced["reactant_coefficients"],
        "product_coefficients": balanced["product_coefficients"],
        "precision": precision,
        "extent_mol": format_decimal(xi, precision),
        "limiting_reactants": limiting,
        "reactants": reactant_results,
        "products": product_results,
    }
