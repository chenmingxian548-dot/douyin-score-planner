# 宿主能力与导入边界

核对日期：2026-11-08。相同SKILL.md结构不代表相同执行权限或电脑控制API。

## WorkBuddy

官方用户文档确认“添加技能→上传技能”可导入本地技能包：
https://www.workbuddy.ai/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills

官方开发文档定义skill-name/SKILL.md、references、scripts等资源，脚本通过宿主Bash工具执行；市场包元数据还包含display_name/display_name_en/description_zh/description_en/version/author：
https://open.workbuddy.cn/docs/skill

本项目生成WorkBuddy专用ZIP：单层技能文件夹，包含上述元数据和所有计算依赖/脚本/资料；不含Codex安装目录或运行环境。用户通过官方技能页面导入，由WorkBuddy读取技能后运行环境检查与隔离安装。Windows的Python命令可用py -3，技能环境执行器为.venv/Scripts/python.exe。

这里只验证过包结构及解压后计算，不声称已经在WorkBuddy界面导入、Windows实机取数或完成整条新用户验收。自动取数脚本使用cua_repl，WorkBuddy不得当作同名API直接调用；缺少相应宿主工具时明确提示改用后台原始报表。不能运行默认setup.py install-skill误装到Codex目录。

## 豆包

普通豆包聊天、豆包工作Skill和豆包应用插件分别判断。未取得对应客户端真实运行证据，不能把本地Python或电脑控制视为已有能力。

豆包应用插件官方规范说明不能假设Skill能运行脚本、装包或执行代码，能力需经MCP工具暴露：
https://open.doubao.com/apps-plugin/docs/core-concepts/skill-guidelines

豆包工作Skill接入指南另有开发者认证、资源包校验、评测与审核上架流程：
https://open.doubao.com/document/doubao-developer-guide/skill-integration-guide

本版没有远程MCP服务、豆包平台审核或上架，不作为豆包应用插件分发。不要求用户为此提供店铺密码、token或把订单上传到第三方服务。需要豆包版本时先明确产品入口及执行能力，再按对应官方要求接入；不擅自扩建云端服务。
