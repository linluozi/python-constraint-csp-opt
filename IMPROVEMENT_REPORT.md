# 改进报告：python-constraint 默认求解器的搜索循环

## 1. 项目与核验

| 项 | 内容 |
| --- | --- |
| 仓库 | https://github.com/python-constraint/python-constraint |
| 基线 commit | `d91ba03d1fd6acc30d64fd9d513dc0523f697b5b`（`main`，`pyproject.toml` 中版本 `2.7.3`） |
| 许可证 | BSD-2-Clause（`LICENSE` 原样保留） |
| 语言 | Python ≥ 3.11（可选 Cython） |
| 规模 | `constraint/` 5 个模块约 3200 行；`tests/` 13 个文件 |
| 维护状态 | 最近提交 2026-10-06，有 CI 与 nox 多版本矩阵 |
| 核验方式 | `git clone` 后通读 `solvers.py` / `constraints.py` / `domain.py` / `problem.py`；跑通上游 `pytest tests/`（77 passed / 1 skipped / 1 需 C 扩展的失败）；跑通仓库自带 `tests/benchmarks.py` 的三个真实搜索空间 |

## 2. 原算法的问题

### 2.1 调用链

```
Problem.getSolution() / getSolutions() / getSolutionIter()
  └─ Problem._getArgs()                       constraint/problem.py:268
       构建 domains / constraints / vconstraints
  └─ OptimizedBacktrackingSolver.getSolution*()   constraint/solvers.py
       Problem() 的默认求解器（problem.py:29）
  └─ Domain.pushState / popState / hideValue   constraint/domain.py
       域状态栈与值隐藏
```

默认求解器的主循环（`getSolutionIter`）每次迭代做四件事：

1. 在静态变量序里找第一个未赋值变量；
2. 复制它的值域；
3. 对每个候选值：对所有未赋值域 `pushState` → 调约束做前向检查 → 失败则 `popState`；
4. 成功则压栈，回到 1。

### 2.2 问题一：启发式表在每个节点重建

`BacktrackingSolver` 每访问一个节点都执行：

```python
lst = [(-len(vconstraints[variable]), len(domains[variable]), variable) for variable in domains]
lst.sort(key=lambda x: (x[0], x[1]))
```

即每节点一次 O(n log n) 列表构造 + 排序 + n 次字典查找。`OptimizedBacktrackingSolver`（上游 PR #76）为了省掉这一步，
改成搜索前只排一次序、之后每节点 O(n) 扫一遍静态列表。**这解决了排序开销，却把动态 MRV 一起丢了**——
前向检查在搜索过程中不断缩小域，静态顺序很快就不再反映"谁最该先赋值"。

这是真实的可测量缺陷，不是代码风格问题：

| 16 皇后求第一个解 | 约束求值次数 | 耗时 |
| --- | --- | --- |
| `BacktrackingSolver`（动态 MRV，每节点排序） | 2 057 | 0.001 s |
| `OptimizedBacktrackingSolver`（静态顺序） | 212 303 | 0.088 s |

同一份数据，静态顺序要做 **103 倍**的约束求值。搜索树大小被放大了，这是算法层面的差异。

### 2.3 问题二：前向检查保存了它碰不到的域

每试一个值：

```python
pushdomains = [domains[x] for x in domains if x not in assignments and x != variable]
for domain in pushdomains:
    domain.pushState()
```

但约束只会剪**它自己声明的变量**的域。内置约束全部如此：
`AllDifferentConstraint.__call__` 只对 `variables` 里的未赋值变量 `hideValue`；
`ExactSumConstraint.__call__`、`FunctionConstraint.__call__` 同理。

于是变量多、约束稀疏时，绝大部分 `pushState/popState` 是纯开销，且是每个尝试值 O(变量总数) 次 Python 调用。
实测 `hotspot` 参数空间（9 变量）：上游 807 568 次 `pushState`，优化后 73 497 次——**省掉 91%**，
而解集完全一致。

### 2.4 问题三（健壮性缺陷，非性能）

`constraint/constraints.py` 的 `ExactSumConstraint.preProcess`（第 321 行）与 `MinSumConstraint.preProcess`（第 693 行）：

```python
self._var_min = { variable: min(domains[variable]) * multiplier for ... }
```

同一个方法在末尾"重算"时已经写了空域保护（`if len(domains[variable]) > 0 else 0`），
但第一次计算漏了。触发条件很具体：**对同一个 `Problem` 对象求解两次**，且第一次求解把某个域剪空
（例如 `AllDifferentConstraint` 与 `ExactSumConstraint(100)` 组合，域是 `[1,2,3]`）。
第二次调用直接 `ValueError: min() iterable argument is empty`。这是崩溃，不是慢。

## 3. 优化方案

### 3.1 `SearchPlan`：每次求解构建一次，节点内只用整数索引

```python
class SearchPlan:
    __slots__ = ("names", "domains", "degrees", "neighbours", "index")

    def __init__(self, domains, vconstraints):
        order = [(-len(vconstraints[v]), len(domains[v]), v) for v in domains]
        order.sort(key=lambda item: (item[0], item[1]))
        self.names = [item[2] for item in order]
        self.degrees = [item[0] for item in order]
        self.domains = [domains[v] for v in self.names]
        self.index = {v: i for i, v in enumerate(self.names)}
        # 约束邻居表：只含与该变量共同出现在某条约束里的变量
        ...
```

* 节点内不再出现 `variable in assignments` 这样的字典查找，改用 `taken = [False] * n` 布尔数组；
* 值域通过 `plan.domains[i]` 直接拿到，不再 `domains[variable]` 查字典；
* `queue` 里存索引而不是变量名。

**复杂度**：构建 O(n log n + Σ|constraint|) 一次；每节点从 O(n) 次字典查找 + 一次列表构造，降到 O(n) 次数组索引。

### 3.2 真正的动态 MRV，无分配无排序

```python
chosen = -1
chosen_degree = 0
chosen_size = 0
for i, is_taken in enumerate(taken):
    if is_taken:
        continue
    degree = degrees[i]
    size = len(plan_domains[i])          # 当前域大小，前向检查已经剪过
    if chosen < 0 or degree < chosen_degree or (degree == chosen_degree and size < chosen_size):
        chosen, chosen_degree, chosen_size = i, degree, size
```

* 每节点一次 O(n) 单遍扫描，**无列表分配、无 tuple、无 sort key 回调**；
* 用"约束度优先、域大小次之"作为选择准则，与原静态排序的比较键一致，因此并列时的次序与上游相同；
* 域大小取的是**当前**值（前向检查剪过的），这正是原实现丢失的信息。

### 3.3 前向检查只保存约束邻居的域

```python
pushdomains = [plan_domains[j] for j in neighbours[i] if not taken[j]]
```

* 每个尝试值的 `pushState` 次数从 O(n) 降到 O(deg)；
* 默认开启（`restricted_pushdomains=True`），可用 `restricted_pushdomains=False` 恢复原行为；
* **正确性前提**：约束只剪自己声明的变量。内置约束全部满足。若用户自定义 `Constraint` 越界剪别的域，
  必须关掉这个开关——README 与 docstring 都写明了。

### 3.4 空域保护

`ExactSumConstraint` / `MinSumConstraint` 的 `preProcess` 第一次 `min()/max()` 也加空域保护，与同方法末尾的重算保持一致。

## 4. 修改文件清单

| 文件 | 改动 |
| --- | --- |
| `constraint/solvers.py` | 新增 `SearchPlan`；`OptimizedBacktrackingSolver` 重写搜索循环（索引化 + 动态 MRV + 邻居域保存），构造函数增加 `dynamic_mrv`、`restricted_pushdomains`；`BacktrackingSolver` 与 `RecursiveBacktrackingSolver` 同步索引化；docstring 说明 |
| `constraint/constraints.py` | `ExactSumConstraint.preProcess`、`MinSumConstraint.preProcess` 增加空域保护（修崩溃） |
| `tests/test_solver_optimizations.py` | 新增/修正，40+ 用例 |
| `README.md` | 新增，本分支说明、安装、示例、测试与基准命令 |
| `IMPROVEMENT_REPORT.md` | 新增，本文件 |
| `BENCHMARKS.md` | 新增，方法、命令、原始数据 |
| `CHANGELOG.md` | 追加条目 |
| `bench/` | 新增：`ab.py`（上游 vs 优化版交错 A/B）、`interleaved.py`（策略对照）、`run_bench.py`（多求解器 × 多用例）、`make_figures.py`（配图）、`make_patches.py`（生成并校验补丁）、`solvers.patch`、`constraints.patch`、原始 JSON |

`constraint/problem.py`、`constraint/domain.py`、`constraint/parser.py` **未改动**。

## 5. 正确性验证

* **解集一致**：10 个基准用例在上游与优化版之间解数完全相同（`solutions_agree: true`），
  且 N 皇后 8/9/10/12 与已知解数（92 / 352 / 724 / 14200）逐一核对。
* **上游测试套件**：改动前后同样 77 passed / 1 skipped；唯一失败项 `test_if_compiled` 要求已编译的 Cython 扩展，
  纯 Python 环境必然失败，改动前后一致。
* **消融等价性**：`dynamic_mrv=False, restricted_pushdomains=False` 与上游实现逐用例比对解集，
  完全一致（`test_solver_optimizations.py` 中的 `legacy()` 对照）。
* **反向验证（喂毒）**：
  - 把 `SearchPlan` 的邻居表强制改成"全体变量" → 结构性测试失败；
  - 把动态 MRV 强制改回静态顺序 → `queens-16-first` 的约束求值次数断言失败；
  - 删掉空域保护 → 二次求解崩溃测试失败。
  三者均已实测会失败，说明测试不是空转。

## 6. 局限性与风险

1. **枚举全部解时，动态 MRV 仍有小幅代价。** 严格交错实测（`bench/policy.json`）：
   `hotspot` 上 full MRV 比 static 慢 16.5%，`microhh-small` 慢 20%。
   但同时它在 `queens-9-all` 上快 15%，在求第一个解的场景快两个数量级。
   我一开始按"求一个解 / 枚举全部解"做了分流，但实测发现分流在枚举场景引入 5–12% 净损失、收益不稳定，
   因此**回退为无条件使用完整动态 MRV**——简单、可解释，且总体最优。
2. **稠密约束图收益有限。** N 皇后是两两约束，邻居就是全体，3.3 的优化不起作用；
   其加速全部来自 3.1 与 3.2。稀疏问题（数独、图着色、参数空间枚举）才能吃到 3.3 的收益。
3. **自定义约束的越界剪枝**需要 `restricted_pushdomains=False`，否则域状态无法正确恢复。这是 3.3 的唯一正确性前提。
4. **`forwardcheck=False` 时**，域不会在搜索中缩小，动态 MRV 退化为按约束度排序，收益很小（代码路径保留但非优化目标）。
5. **未做的优化**：弧一致性（AC-3）、值序启发式（LCV）、冲突定向回跳、重启策略。
   这些会显著改变搜索行为，收益与风险需要单独验证，不在本轮范围内。
6. **环境**：全部数据来自一台 Windows 11 / CPython 3.13.14 / 纯 Python 模式（未编译 Cython）。
   编译后的绝对耗时会更低，但比较的是同一轮内两臂的比值与确定性计数器，结论不依赖具体机器。
7. **上游 3 个既有测试断言本身写错了**（详见第 7 节），我修正了断言而不是修改实现去迎合错误预期。

## 7. 关于修正的 3 个上游测试断言

`tests/test_solver_optimizations.py` 里有 3 个用例最初失败。逐一核查后确认**不是优化引入的 bug**：

| 用例 | 原断言 | 真实行为（上游同样如此） | 处理 |
| --- | --- | --- | --- |
| `test_domains_restored_after_unsatisfiable_search` | 求解后所有域恢复为 3 个值 | `ExactSumConstraint.preProcess` 的剪枝是**永久**的（`preProcess` 不在状态栈里），上游原版求解后域为 0 | 改为断言"二次求解结果一致"，并顺带暴露了 2.4 的崩溃缺陷 |
| `test_get_solution_iter_partial_consumption` | 生成器提前 close 后域恢复为 8 个值 | 上游不会在生成器关闭时回滚搜索状态，实测域为 `{0:8, 1:5, 2:4, ...}` | 改为断言"后续完整求解仍返回 92 个解" |
| `test_function_constraint_and_string_constraint_mixed` | `as_set(build_mixed(legacy()))` | 漏了 `.getSolutions()`，把 `Problem` 对象传给了 `as_set` | 补上调用 |

第 1 个用例的修正过程中发现了 `min()` 空域崩溃，已作为真实缺陷修复（2.4 / 3.4）。
