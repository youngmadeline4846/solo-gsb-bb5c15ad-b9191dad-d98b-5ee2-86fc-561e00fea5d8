"""化学计量接口测试。"""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.parser import parse_formula
from app.stoichiometry import (
    StoichiometryError,
    format_decimal,
    molar_mass,
)

client = TestClient(app)


def stoichiometry(payload):
    resp = client.post("/api/v1/stoichiometry", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------- 工具函数 ----------

def test_format_decimal_half_up():
    # 银行家舍入会得 1.2344，四舍五入必须为 1.2345
    assert format_decimal(Decimal("1.23445"), 4) == "1.2345"
    assert format_decimal(Decimal("2.5"), 4) == "2.5000"
    assert format_decimal(Decimal("0.00005"), 4) == "0.0001"
    # 负零归一化
    assert format_decimal(Decimal("-0.00001"), 4) == "0.0000"


def test_molar_mass():
    assert molar_mass(parse_formula("H2O")[0]) == Decimal("18.015")
    assert molar_mass(parse_formula("CuSO4.5H2O")[0]) == Decimal("249.677")
    with pytest.raises(StoichiometryError, match="Xe"):
        molar_mass(parse_formula("Xe")[0])


# ---------- 正常计算 ----------

def test_basic_mol_feeds_single_limiting():
    data = stoichiometry(
        {
            "reactants": ["H2", "O2"],
            "products": ["H2O"],
            "feeds": [
                {"formula": "H2", "amount": "2.5", "unit": "mol"},
                {"formula": "O2", "amount": "2", "unit": "mol"},
            ],
        }
    )
    assert data["equation"] == "2H2 + O2 -> 2H2O"
    assert data["coefficients"] == [2, 1, 2]
    assert data["precision"] == 4  # 默认精度
    assert data["extent_mol"] == "1.2500"
    assert data["limiting_reactants"] == ["H2"]

    h2, o2 = data["reactants"]
    assert h2["is_limiting"] is True
    assert h2["fed_mol"] == "2.5000"
    assert h2["fed_g"] == "5.0400"  # 2.5 * 2.016
    assert h2["remaining_mol"] == "0.0000"
    assert h2["remaining_g"] == "0.0000"
    assert o2["is_limiting"] is False
    assert o2["molar_mass_g_per_mol"] == "31.9980"
    assert o2["remaining_mol"] == "0.7500"
    assert o2["remaining_g"] == "23.9985"  # 0.75 * 31.998

    (water,) = data["products"]
    assert water["coefficient"] == 2
    assert water["molar_mass_g_per_mol"] == "18.0150"
    assert water["theoretical_mol"] == "2.5000"
    assert water["theoretical_g"] == "45.0375"  # 2.5 * 18.015


def test_gram_feeds_and_tied_limiting():
    # CaCO3 100.086 g 恰为 1 mol，与 2 mol HCl 等比例 -> 并列限制
    data = stoichiometry(
        {
            "reactants": ["CaCO3", "HCl"],
            "products": ["CaCl2", "H2O", "CO2"],
            "feeds": [
                {"formula": "CaCO3", "amount": "100.086", "unit": "g"},
                {"formula": "HCl", "amount": "2", "unit": "mol"},
            ],
        }
    )
    assert data["coefficients"] == [1, 2, 1, 1, 1]
    assert data["extent_mol"] == "1.0000"
    assert data["limiting_reactants"] == ["CaCO3", "HCl"]

    caco3, hcl = data["reactants"]
    assert caco3["fed_mol"] == "1.0000"
    assert caco3["fed_g"] == "100.0860"
    assert caco3["remaining_mol"] == "0.0000"
    assert hcl["fed_g"] == "72.9160"  # 2 * 36.458
    assert hcl["remaining_mol"] == "0.0000"

    cacl2, h2o, co2 = data["products"]
    assert cacl2["theoretical_mol"] == "1.0000"
    assert cacl2["theoretical_g"] == "110.9780"  # 40.078 + 2*35.45
    assert h2o["theoretical_g"] == "18.0150"
    assert co2["theoretical_g"] == "44.0090"  # 12.011 + 2*15.999


def test_stoichiometric_mixture_all_consumed():
    data = stoichiometry(
        {
            "reactants": ["H2", "O2"],
            "products": ["H2O"],
            "feeds": [
                {"formula": "H2", "amount": 2, "unit": "mol"},
                {"formula": "O2", "amount": 1, "unit": "mol"},
            ],
        }
    )
    assert data["limiting_reactants"] == ["H2", "O2"]
    assert all(r["remaining_mol"] == "0.0000" for r in data["reactants"])
    assert data["products"][0]["theoretical_g"] == "36.0300"


def test_float_amount_accepted():
    data = stoichiometry(
        {
            "reactants": ["H2", "O2"],
            "products": ["H2O"],
            "feeds": [
                {"formula": "H2", "amount": 2.5, "unit": "mol"},
                {"formula": "O2", "amount": 2.0, "unit": "mol"},
            ],
        }
    )
    assert data["reactants"][0]["fed_amount"] == "2.5"
    assert data["extent_mol"] == "1.2500"


def test_precision_rounding():
    payload = {
        "reactants": ["H2", "O2"],
        "products": ["H2O"],
        "feeds": [
            {"formula": "H2", "amount": "2.5", "unit": "mol"},
            {"formula": "O2", "amount": "2", "unit": "mol"},
        ],
        "precision": 2,
    }
    data = stoichiometry(payload)
    assert data["precision"] == 2
    assert data["extent_mol"] == "1.25"
    assert data["products"][0]["theoretical_g"] == "45.04"  # 45.0375 四舍五入
    assert data["reactants"][1]["remaining_g"] == "24.00"  # 23.9985 -> 24.00


def test_precision_eight():
    data = stoichiometry(
        {
            "reactants": ["NaOH", "HCl"],
            "products": ["NaCl", "H2O"],
            "feeds": [
                {"formula": "NaOH", "amount": "0.1", "unit": "g"},
                {"formula": "HCl", "amount": "1", "unit": "mol"},
            ],
            "precision": 8,
        }
    )
    # 0.1 / 39.997 = 0.00250018... mol
    assert data["reactants"][0]["fed_mol"] == "0.00250019"
    assert data["extent_mol"] == "0.00250019"


# ---------- 4xx 错误 ----------

def test_missing_feed_returns_400():
    resp = client.post(
        "/api/v1/stoichiometry",
        json={
            "reactants": ["H2", "O2"],
            "products": ["H2O"],
            "feeds": [{"formula": "H2", "amount": "1", "unit": "mol"}],
        },
    )
    assert resp.status_code == 400
    assert "缺失投料" in resp.json()["detail"]
    assert "O2" in resp.json()["detail"]


def test_duplicate_feed_returns_400():
    resp = client.post(
        "/api/v1/stoichiometry",
        json={
            "reactants": ["H2", "O2"],
            "products": ["H2O"],
            "feeds": [
                {"formula": "H2", "amount": "1", "unit": "mol"},
                {"formula": "H2", "amount": "32", "unit": "g"},
                {"formula": "O2", "amount": "1", "unit": "mol"},
            ],
        },
    )
    assert resp.status_code == 400
    assert "重复投料" in resp.json()["detail"]


@pytest.mark.parametrize("amount", ["0", "-1", "-0.5"])
def test_non_positive_amount_returns_400(amount):
    resp = client.post(
        "/api/v1/stoichiometry",
        json={
            "reactants": ["H2", "O2"],
            "products": ["H2O"],
            "feeds": [
                {"formula": "H2", "amount": amount, "unit": "mol"},
                {"formula": "O2", "amount": "1", "unit": "mol"},
            ],
        },
    )
    assert resp.status_code == 400
    assert "正数" in resp.json()["detail"]


def test_nan_amount_returns_4xx():
    resp = client.post(
        "/api/v1/stoichiometry",
        json={
            "reactants": ["H2", "O2"],
            "products": ["H2O"],
            "feeds": [
                {"formula": "H2", "amount": "NaN", "unit": "mol"},
                {"formula": "O2", "amount": "1", "unit": "mol"},
            ],
        },
    )
    assert 400 <= resp.status_code < 500


def test_unsupported_atomic_weight_returns_400():
    resp = client.post(
        "/api/v1/stoichiometry",
        json={
            "reactants": ["Zn", "HCl"],
            "products": ["ZnCl2", "H2"],
            "feeds": [
                {"formula": "Zn", "amount": "1", "unit": "mol"},
                {"formula": "HCl", "amount": "2", "unit": "mol"},
            ],
        },
    )
    assert resp.status_code == 400
    assert "Zn" in resp.json()["detail"]
    assert "原子量" in resp.json()["detail"]


def test_feed_not_a_reactant_returns_400():
    resp = client.post(
        "/api/v1/stoichiometry",
        json={
            "reactants": ["H2", "O2"],
            "products": ["H2O"],
            "feeds": [
                {"formula": "H2", "amount": "1", "unit": "mol"},
                {"formula": "O2", "amount": "1", "unit": "mol"},
                {"formula": "N2", "amount": "1", "unit": "mol"},
            ],
        },
    )
    assert resp.status_code == 400
    assert "不在反应物列表中" in resp.json()["detail"]


def test_unbalanceable_returns_422():
    resp = client.post(
        "/api/v1/stoichiometry",
        json={
            "reactants": ["H2", "O2"],
            "products": ["H2O", "H2O2"],
            "feeds": [
                {"formula": "H2", "amount": "1", "unit": "mol"},
                {"formula": "O2", "amount": "1", "unit": "mol"},
            ],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["null_space_dim"] == 2


def test_bad_formula_returns_400():
    resp = client.post(
        "/api/v1/stoichiometry",
        json={
            "reactants": ["H2$", "O2"],
            "products": ["H2O"],
            "feeds": [
                {"formula": "H2$", "amount": "1", "unit": "mol"},
                {"formula": "O2", "amount": "1", "unit": "mol"},
            ],
        },
    )
    assert resp.status_code == 400


def test_invalid_unit_returns_4xx():
    resp = client.post(
        "/api/v1/stoichiometry",
        json={
            "reactants": ["H2", "O2"],
            "products": ["H2O"],
            "feeds": [
                {"formula": "H2", "amount": "1", "unit": "kg"},
                {"formula": "O2", "amount": "1", "unit": "mol"},
            ],
        },
    )
    assert 400 <= resp.status_code < 500


@pytest.mark.parametrize("precision", [1, 9])
def test_precision_out_of_range_returns_4xx(precision):
    resp = client.post(
        "/api/v1/stoichiometry",
        json={
            "reactants": ["H2", "O2"],
            "products": ["H2O"],
            "feeds": [
                {"formula": "H2", "amount": "1", "unit": "mol"},
                {"formula": "O2", "amount": "1", "unit": "mol"},
            ],
            "precision": precision,
        },
    )
    assert 400 <= resp.status_code < 500
