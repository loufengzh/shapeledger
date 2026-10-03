# shapeledger 使用指南

记录 JSONL 中实际观察到的结构，比较导出数据或测试夹具的变化，不保存标量样本值。[English](../README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md)

## 安装与快速开始

需要 Python 3.10 或更高版本，运行时仅使用标准库。在仓库根目录执行：

```sh
python -m shapeledger profile examples/baseline.jsonl > /tmp/baseline.shape.json
python -m shapeledger profile examples/candidate.jsonl > /tmp/candidate.shape.json
python -m shapeledger compare /tmp/baseline.shape.json /tmp/candidate.shape.json
python -m shapeledger compare /tmp/baseline.shape.json /tmp/candidate.shape.json --fail-on added_type --fail-on removed_path --fail-on missing_increase
```

最后一条命令对这些示例返回 1。运行 `python -m pip install .` 可安装 `shapeledger` 命令；构建需要 setuptools，运行不需要第三方库。`profile -` 从标准输入读取。结果是确定性的 JSON，写到标准输出。请重定向到新文件：即使输入失败，shell 也可能先截断旧文件。工具不会输出部分分析结果。

## 输入与计数语义

每一行必须是一个完整的严格 UTF-8 JSON 值，支持任何根类型。空行、BOM、重复对象键、NaN、Infinity、溢出浮点数和损坏的记录均被拒绝。支持 CRLF 和末行无换行符。错误诊断指出无效记录的行号，不回显源数据。

版本 1 的结果包含 `version`、`records` 和排序后的 `nodes`。每个节点包含 `path`、`types`、`opportunities`、`array_items`。类型区分 object、array、string、integer、number、boolean、null；`1` 与 `1.0` 不同。路径采用带类型的片段，例如 `[["key","users"],["items"],["key","name"]]`。点、斜线、星号、空字符串或字面键 `items` 不会产生歧义。

- 根节点的机会数是记录总数。
- 对象键的机会数是父路径上观察到的对象实例数，而非所有记录或所有父类型。
- 数组通配节点的机会数是数组元素总数，每个元素（含 null）出现一次。
- 缺失数 = 机会数减去各类型出现次数之和。null 是存在的值，不是缺失。
- `array_items` 是该节点所有数组的长度之和。空数组不创建元素节点。数组中的对象字段只以对象实例为分母。
- 未观察到的数据没有节点。父路径消失时报告路径删除，不凭空制造零比率。

保留对象键和结构计数，动态键可能包含敏感信息。这是数据最小化，不是匿名化。标量值会在内存中短暂解析，但不会写入输出。错误不包含源文本或文件名。

## 比较与 CI

比较前会严格验证两个配置文件。事件包括 `added_path`（新增路径）、`removed_path`（删除路径）、`added_type`（新增类型）、`missing_increase`（缺失比例增加）与 `null_increase`（null 比例增加）。现有路径的比例使用精确有理数，输出如 `1/3`。null 比例的分母是机会数，不是存在数。任何正增长都会产生事件；0.1 版没有数值阈值参数。不报告删除的类型。新增或删除的路径只产生路径事件，不再产生类型或比例事件。

所有事件都输出；重复 `--fail-on KIND` 选择导致 CI 失败的事件。不设置门槛时仅提供报告。

- 退出 0：输入有效，没有命中选定门槛。
- 退出 1：命中至少一个选定门槛。
- 退出 2：输入、分析文件、限制、I/O 或命令参数错误。

## 限制与安全

按记录流式处理，不是按 JSON 词元。默认每行最多 1 MiB（含换行符，`--max-line-bytes`）；最多 10,000 个独立节点（`--max-nodes`）；路径深度最多 64（`--max-depth`，根深度为 0）。节点和深度参数只能降低格式上限，所有限制必须为正整数。内存取决于最大允许行和保留的路径集合；数组元素合并统计，不归一化动态键。Python 解析器可能先拒绝过深的记录。每个比较文件最多 32 MiB，并验证字段、版本、路径、计数和父子关系。

这不是完整 JSON Schema 或可信证明，不做模式验证、分布推断、分析合并、字段忽略或数值范围统计。浮点数使用标准库解析，其精度不影响类型计数。输出需要磁盘空间；关闭的管道属于 I/O 错误。

## 替代方案与开发

[GenSON](https://github.com/wolverdude/GenSON) 生成和合并 JSON Schema；[DataProfiler](https://github.com/capitalone/DataProfiler) 提供更广泛的统计和实体分析。本工具专注于结构计数、相对父对象的缺失率和明确的 CI 事件，不替代这些项目，也不声称发明新的模式推断算法。

```sh
python -m unittest discover -s tests -v
python -m pip wheel --no-deps . -w dist
```

CI 覆盖 Python 3.10–3.13 及 wheel 安装。贡献应包含回归测试；语义变化应同步四种语言文档。只提交合成示例，勿提交私密数据。未来方向包括分析合并、路径过滤和动态键预算。MIT 许可证。
