# 抖店体验分与目标分析 Skill

版本0.1.0，首个候选测试版：支持环境检查、隔离依赖安装、宿主 CUA 只读取数、报表复核和多情景分析。用户用自然语言描述目标，无需手填配置或重整报表。全程不修改店铺设置、商品、评价、售后或违规状态。

**使用WorkBuddy的朋友请先看 [WorkBuddy导入说明](WORKBUDDY.md)**，使用专用技能ZIP，不需要安装Codex。WorkBuddy包结构和计算已本地校验，界面导入/Windows/自动取数尚未实测。普通豆包和豆包工作需另行核对入口，本版没有完成豆包平台接入。

## WorkBuddy快速开始

1. [下载WorkBuddy专用技能包](https://raw.githubusercontent.com/chenmingxian548-dot/douyin-score-planner/refs/heads/main/packages/douyin-score-planner-workbuddy-v0.1.0.zip)，保存为ZIP，直接导入，无需先解压。
2. 打开WorkBuddy的“技能”，选择“添加技能→上传技能”，选择下载的ZIP，按客户端提示完成检查并启用。
3. 为一家店新开一个对话，发送下面这段话：

> 使用“抖店体验分与目标分析”技能。先检查环境并安装本技能的隔离计算依赖，再让我描述目标和完成期限，告诉我需要哪些后台原始报表。只能查询、读取和导出，不修改任何店铺设置。请先确认你是否真的具备自动取数工具，没有就使用我提供的原始表格。

4. 描述目标并提供原始导出文件；之后每天在同一对话更新数据。需要登录或验证码时本人操作。结果会区分事实、条件假设和缺失依据。

首次缺少Python 3.10+时，按技能提示从Python官方安装；无需Excel、Git或终端Node。若客户端显示的导入菜单不同，请查阅[详细步骤和常见问题](WORKBUDDY.md)。不要将GitHub的整个仓库ZIP当作WorkBuddy技能包。

## 安装

下载完整仓库 ZIP 并解压。在支持本地脚本的 Codex 中提供本目录，让 AI 运行：

```sh
python3 skills/douyin-score-planner/scripts/setup.py doctor
python3 skills/douyin-score-planner/scripts/setup.py install-deps
python3 skills/douyin-score-planner/scripts/setup.py install-skill
```

Windows 可用 `py -3` 替代 `python3`（Windows整条流程未实测）。安装器寻找已有 Python 3.10+，只建立私有 `.venv`；缺少基础Python时给出官方安装入口。锁定依赖从PyPI按版本与哈希安装。安装已有不同Skill时拒绝覆盖。重新打开对话使宿主发现技能。

用户不需要安装 Excel、Git或Node。自动取数需要宿主实际提供的 CUA；安装 Skill 不会凭空安装这项能力，也不会取得店铺登录权限。没有取数工具时仍可分析原始导出文件。首版实测 macOS 原生抖店；不能承诺通用浏览器、所有电脑或所有店铺页面均可自动导出。

## 使用

在店铺专用对话中：

> 使用 $douyin-score-planner。我希望在某日前达到某个平均体验分或满足黑标准入。可以只读查看和导出我的店铺数据，不修改任何设置。

Skill确认目标与数据口径后获取所需资料；文件不足时会说明影响。可分析理想条件、当前状态延续、改善延迟、不同幅度和不可达边界。整数均值和未知评分映射不会被包装成精确预测。

## 本地演示与验证

```sh
skills/douyin-score-planner/.venv/bin/python skills/douyin-score-planner/scripts/planner.py analyze --config skills/douyin-score-planner/assets/example-goal.json --out /tmp/douyin-synthetic-report.json
skills/douyin-score-planner/.venv/bin/python -m unittest discover -s tests -v
```

演示全部为虚构数据；报告路径已存在时拒绝覆盖。Windows技能Python路径为 `.venv/Scripts/python.exe`。开发者可用Node运行纯解析/白名单测试 `node tests/test_collector.cjs`，终端Node不是使用依赖。

真实订单、登录凭据、导出、店铺名称、截图和私有报告不属于仓库内容。发布候选包由允许列表生成，排除运行环境和真实验证资料。验证状态见 [VALIDATION.md](VALIDATION.md)。
