# 化学方程式精确配平 API

基于 FastAPI 的化学方程式配平服务。服务端为反应物/生成物构建**元素守恒矩阵（含电荷行）**，用**有理数高斯消元**求零空间；仅当零空间为一维且基向量可化为全正时，返回最大公约数约简后的**最小正整数系数**及逐元素、电荷核算，否则返回 `422` 并说明原因（零空间维数或无法全正）。

## 快速启动（单条命令）

```bash
docker compose up --build
```

依赖随容器启动自动安装（`pip install -r requirements.txt` 后再拉起 uvicorn）。

- 服务地址：http://localhost:8000
- 交互式文档（Swagger UI）：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 配置

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `8000` | 容器内服务监听端口 |

宿主机端口映射在 `docker-compose.yml` 的 `ports` 中调整（默认 `8000:8000`）。

## 分子式语法

| 语法 | 示例 |
| --- | --- |
| 元素与下标 | `H2O`、`Fe2O3` |
| 嵌套括号（`()` `[]` `{}` 可混用） | `Ca(OH)2`、`K4[Fe(CN)6]` |
| 点号结晶水（`.` `·` `*`） | `CuSO4.5H2O`、`Na2CO3·10H2O` |
| 插入符电荷（推荐，无歧义） | `SO4^2-`、`Fe^3+`、`NH4^+` |
| 纯符号尾电荷（每个 `+`/`-` 计 1） | `Na+`、`Cl-`、`Ca++`、`SO4--` |
| 电子（半反应） | `e-` |

> 注意：不带 `^` 时，符号前的数字属于前一个元素/基团——`NH4+` 解析为 NH₄⁺（电荷 +1）；要表示 Ca²⁺ 请写 `Ca^2+`。

## API

### `POST /api/v1/balance` — 配平

```bash
curl -s http://localhost:8000/api/v1/balance \
  -H 'Content-Type: application/json' \
  -d '{"reactants": ["KMnO4", "HCl"], "products": ["KCl", "MnCl2", "H2O", "Cl2"]}'
```

响应（`200`）：

```json
{
  "equation": "2KMnO4 + 16HCl -> 2KCl + 2MnCl2 + 8H2O + 5Cl2",
  "coefficients": [2, 16, 2, 2, 8, 5],
  "reactant_coefficients": [2, 16],
  "product_coefficients": [2, 2, 8, 5],
  "elements": [
    {"element": "Cl", "reactants": 16, "products": 16, "balanced": true},
    {"element": "H",  "reactants": 16, "products": 16, "balanced": true},
    {"element": "K",  "reactants": 2,  "products": 2,  "balanced": true},
    {"element": "Mn", "reactants": 2,  "products": 2,  "balanced": true},
    {"element": "O",  "reactants": 8,  "products": 8,  "balanced": true}
  ],
  "charge": {"reactants": 0, "products": 0, "balanced": true},
  "balanced": true
}
```

离子方程式（含电荷行守恒）：

```bash
curl -s http://localhost:8000/api/v1/balance \
  -H 'Content-Type: application/json' \
  -d '{"reactants": ["MnO4-", "H+", "e-"], "products": ["Mn^2+", "H2O"]}'
# -> MnO4- + 8H+ + 5e- -> Mn^2+ + 4H2O
```

无法配平时返回 `422`，并说明零空间维数或无法全正：

```json
{
  "detail": {
    "message": "零空间维数为 2（必须恰好为 1 才能唯一配平）",
    "null_space_dim": 2
  }
}
```

化学式语法错误返回 `400`。

### `POST /api/v1/verify` — 校验系数

```bash
curl -s http://localhost:8000/api/v1/verify \
  -H 'Content-Type: application/json' \
  -d '{
        "reactants": ["H2", "O2"],
        "products": ["H2O"],
        "reactant_coefficients": [2, 1],
        "product_coefficients": [2]
      }'
```

响应包含逐元素与电荷核算、`balanced` 结论，以及系数的 `gcd` 与是否已约简（`is_reduced`）。

## 本地开发

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
pytest                 # 运行测试
```

## 项目结构

```
app/
  parser.py     # 分子式解析：嵌套括号、结晶水、离子电荷
  balancer.py   # 守恒矩阵（含电荷行）、有理数 RREF、零空间、整数化
  schemas.py    # 请求/响应模型
  main.py       # FastAPI 路由
tests/test_api.py
Dockerfile / docker-compose.yml
```
