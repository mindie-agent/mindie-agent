## 变更摘要 (Summary)

- 

## 设计原则 Review (Pre-PR Checklist)

> 本仓库（`mindie-agent`）仅承载顶层产品架构、领域路由边界、活文档（`docs/`）、发布通道（`channels/0.1.json`）与跨仓契约门禁（`.github/scripts/`）。涉及运行时代码、宿主插件或评测基准的改动请路由至对应兄弟仓库（见 [`CONTRIBUTING.md`](../CONTRIBUTING.md)）。每项须勾选并填写具体核验证据（如不适用请注明 `not-applicable: <具体原因>`）：

- [ ] **`HUB-ROUTE`** — 职责与仓库路由边界：本 PR 未混入任何运行时业务代码或宿主适配器实现，跨仓指引与兄弟仓库职责映射准确一致。
  - `HUB-ROUTE`: 
- [ ] **`HUB-DOC`** — 活文档同步、归档不可变与中英对齐：活跃规范（`docs/*.md` / `.en.md`）与当前架构一致，中英双语配对及 `##` 章节结构对称，未覆写历史归档（`docs/archive/**`）或历史发版记录（`docs/releases/**`），且通过 `code_doc_hygiene_gate.py` 与 `LF` 换行校验。
  - `HUB-DOC`: 
- [ ] **`HUB-RELEASE`** — 发布通道与独立/组合发布契约（`R1–R6`）：若改动 `channels/0.1.json` 或受管版本块，已通过 `sync_org_versions.py --release-scope product --check` 与 `check_auto_update_readiness.py`；纯文档/门禁改动请填写 `not-applicable: <原因>`。
  - `HUB-RELEASE`: 
- [ ] **`HUB-GATE`** — 门禁脚本纯标准库、无冗余包袱与单测覆盖：若改动 `.github/scripts/` 或工作流，保持纯 Python 标准库、零孤立模块/影子文件（`code_doc_hygiene_gate.py`）、显式输出 `selected / exercised / missing / unselected` 仓库覆盖率、Windows 子进程无弹窗且隔离单测全部通过；未改动门禁请填写 `not-applicable: <原因>`。
  - `HUB-GATE`: 

## 验证结果 (Verification)

> 每条命令冒号后须填写实际运行结果（命令本身、空白或模板占位符均不计作结果）：

- `python3 .github/scripts/check_lf_eol.py`: 
- `python3 .github/scripts/code_doc_hygiene_gate.py --main-repo .`: 
- `python3 -m unittest discover -s .github/scripts/tests -p 'test_*.py' -v`: 
