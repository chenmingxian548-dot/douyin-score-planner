# 给WorkBuddy用户的使用说明

不需要安装Codex。优先使用本项目提供的WorkBuddy专用技能ZIP，而不是把整个GitHub仓库ZIP当技能导入。

1. [点击下载WorkBuddy专用技能包](https://raw.githubusercontent.com/chenmingxian548-dot/douyin-score-planner/refs/heads/main/packages/douyin-score-planner-workbuddy-v0.1.0.zip)。将其保存到“下载”目录；保持ZIP，不要解压，也不要下载整个仓库ZIP来导入。
2. 打开WorkBuddy的技能页面，选择“添加技能→上传技能”，选择该ZIP。菜单可能因版本/语言略有区别，以当前界面为准。
3. 阅读WorkBuddy的安全检查结果，需要本人确认的项目由本人操作，不绕过检查。
4. 为这家店铺新开一个对话，发送：

> 使用“抖店体验分与目标分析”技能。先检查运行环境、安装本技能计算所需的隔离依赖。我会描述目标并提供后台原始导出表，不修改任何店铺设置。请先检查你是否具备自动取数工具；没有就明确说明，不要假装已取得数据。

5. 描述目标，例如“想在某日前让近30天平均体验分达到某分数，并核对黑标准入”。提供已有原始文件；Skill会解释缺什么以及影响。

WorkBuddy可执行本地脚本时会运行setup.py doctor和install-deps；默认Codex安装命令不适用于WorkBuddy，不要运行。没有Python 3.10+时需从Python官方安装入口准备基础运行时。无需Excel或终端Node。

目前本项目验证了计算、Skill包结构与macOS原生抖店/Codex只读取数。WorkBuddy界面导入、Windows整条流程和WorkBuddy自动取数尚未实测，不能称“全平台开箱即用”。第一版在WorkBuddy以原始报表分析为明确入口。

普通豆包聊天不能直接按这份说明安装使用。本项目尚未完成豆包平台接入；“豆包工作”也须核对对应入口与工具条件。

## 遇到问题

- **下载得到网页而不是ZIP**：使用上面的专用下载链接；也可在仓库的packages目录打开ZIP文件，点击“Download raw file”。
- **导入后找不到技能**：查看技能是否被禁用，先启用，再新开店铺专用对话并点名使用本技能。
- **提示缺Python**：从 https://www.python.org/downloads/ 安装Python 3.10或以上版本，然后让WorkBuddy重新检查环境。Windows的Python命令可用`py -3`。
- **依赖安装失败**：把错误交给WorkBuddy检查；不要将“Skill已导入”当作计算环境已安装。
- **无法自动取数**：当前自动取数脚本依赖特定宿主CUA工具；没有此能力就手动导出报表后交给Skill分析，不必提供店铺密码。
- **不知道提供哪些表**：先描述目标，Skill按目标列出所需资料及缺项影响；直接提供后台原始导出即可，不需要重填表。
- **计算日期不确定**：查看报告假设。只有整数均值、没有逐日精确分时，不会保证具体达标日或拿标日。

官方依据：[WorkBuddy本地技能导入](https://www.workbuddy.ai/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills)、[技能结构与脚本](https://open.workbuddy.cn/docs/skill)。
