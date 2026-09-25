## 实施

- [x] 1.1 更新应用显示名与图标字符（取字 → 截图识字）
     【目标对象】`app/constants.py`、`main.py`、`app/__init__.py`、`app/settings_dialog.py`、`app/history_window.py`、`app/ocr_engine.py`
     【修改目的】界面显示名全部切换为「截图识字」，图标字与日志前缀同步，消除代码中全部「取字」字面量
     【修改方式】对以下已定位位置做精确字符串替换（操作类型：修改），共 6 处：
        - `app/constants.py`：模块级常量 `APP_NAME`（第 3 行）
        - `main.py`：模块 docstring（第 1 行）；`MainWindow._build_icon()` 静态方法内 `painter.drawText(...)` 调用（第 238 行）
        - `app/__init__.py`：包 docstring（第 1 行）
        - `app/settings_dialog.py`：`SettingsDialog.__init__()` 内 `setWindowTitle(...)`（第 134 行）
        - `app/history_window.py`：`HistoryWindow.__init__()` 内 `setWindowTitle(...)`（第 49 行）
        - `app/ocr_engine.py`：`_WarmupThread.run()` 内预热失败日志 `print(...)`（第 138 行）
     【相关依赖】无（纯字面量替换，不改逻辑与接口）
     【修改内容】
        - `app/constants.py`：`APP_NAME = "取字"` → `APP_NAME = "截图识字"`
        - `main.py` 模块 docstring：`取字（QuZi）入口：` → `截图识字（SnipOCR）入口：`
        - `main.py` `MainWindow._build_icon()`：`painter.drawText(QRect(0, 0, 64, 64), Qt.AlignmentFlag.AlignCenter, "取")` 仅将末参数 `"取"` → `"识"`
        - `app/__init__.py` 包 docstring：`取字（QuZi）——` → `截图识字（SnipOCR）——`
        - `app/settings_dialog.py` `SettingsDialog.__init__()`：`self.setWindowTitle("设置 — 取字")` → `self.setWindowTitle("设置 — 截图识字")`
        - `app/history_window.py` `HistoryWindow.__init__()`：`self.setWindowTitle("识别历史 — 取字")` → `self.setWindowTitle("识别历史 — 截图识字")`
        - `app/ocr_engine.py` `_WarmupThread.run()`：完整语句为
          `print(f"[取字] OCR 引擎预热失败: {exc}", file=sys.stderr)`，仅将日志前缀 `[取字]` → `[截图识字]`，其余保持原样
        - 无需改动（引用常量自动跟随）：`main.py` 中 `MainWindow.__init__()` 的 `setWindowTitle(f"{APP_NAME} {APP_VERSION} — 屏幕截图文字识别")`、`_build_ui()` 的 `QLabel(APP_NAME)`、`_build_tray()` 的 `tray.setToolTip(f"{APP_NAME} — ...")`、`closeEvent()` 的托盘消息标题均引用 `APP_NAME` 常量，随常量修改自动切换
        - 边界说明：已全仓库检索确认「取字」字面量仅存在于上述 6 个代码文件（`README.md` 由任务 1.3 处理），无其他遗漏

- [x] 1.2 更新技术标识（QuZi → SnipOCR）
     【目标对象】`app/settings.py`、`app/autostart.py`、`main.py`
     【修改目的】数据目录、注册表自启项、崩溃日志路径说明切换为 SnipOCR
     【修改方式】对以下已定位位置做精确字符串替换（操作类型：修改），共 4 处：
        - `app/settings.py`：模块 docstring（第 3 行）；模块级常量 `DATA_DIR`（第 16 行）
        - `app/autostart.py`：模块级常量 `VALUE_NAME`（第 9 行）
        - `main.py`：`_install_crash_logger()` 函数 docstring（第 413–414 行）
     【相关依赖】无
     【修改内容】
        - `app/settings.py` 第 16 行：`DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "QuZi"` 仅将末尾字符串 `"QuZi"` → `"SnipOCR"`，路径拼接逻辑不动
        - `app/settings.py` 模块 docstring：`存储位置：%APPDATA%/QuZi/config.json` → `存储位置：%APPDATA%/SnipOCR/config.json`
        - `app/autostart.py`：`VALUE_NAME = "QuZi"` → `VALUE_NAME = "SnipOCR"`（HKCU Run 注册表项名）
        - `main.py` `_install_crash_logger()` docstring：`%APPDATA%/QuZi/crash.log` → `%APPDATA%/SnipOCR/crash.log`
        - 无需改动（派生路径自动跟随）：`app/settings.py` 的 `CONFIG_PATH = DATA_DIR / "config.json"`、`app/history.py` 的 `HISTORY_PATH = DATA_DIR / "history.jsonl"`、`main.py` `_install_crash_logger()` 内的 `open(DATA_DIR / "crash.log", ...)` 均由 `DATA_DIR` 派生，随本任务自动切换
        - 边界说明：旧数据目录 `%APPDATA%\QuZi` 弃用，配置/历史回默认值（proposal 已确认无实际损失），无需编写迁移逻辑

- [x] 1.3 更新 README
     【目标对象】`README.md`
     【修改目的】文档与新名称一致，消除全文全部 `QuZi`（9 处）与「取字」（3 处）字面量
     【修改方式】全文逐处精确更名（操作类型：修改）
     【相关依赖】1.1 / 1.2 确定的命名规范（显示名「截图识字」、技术标识 SnipOCR）
     【修改内容】
        - 标题（第 1 行）：`# 取字（QuZi）—— 屏幕截图文字识别（离线）` → `# 截图识字（SnipOCR）—— 屏幕截图文字识别（离线）`
        - slogan（第 3 行）：`> 按 \`Alt + Q\`，框选即取字。` → `> 按 \`Alt + Q\`，框选屏幕，文字到手。`
        - 技术标识说明段（第 9–10 行）：`QuZi` → `SnipOCR`、「取字」→「截图识字」
        - 功能列表（第 18 行）：`%APPDATA%\QuZi\history.jsonl` → `%APPDATA%\SnipOCR\history.jsonl`
        - 项目结构注释（第 52 行）：`（%APPDATA%/QuZi/config.json）` → `（%APPDATA%/SnipOCR/config.json）`（注意此处为正斜杠形态，勿按反斜杠字面量检索）
        - 打包命令（第 89 行）：`--name QuZi` → `--name SnipOCR`，其余参数保持不动
        - 产物说明（第 98 行）：`dist\QuZi.exe` → `dist\SnipOCR.exe`；onefile 说明（第 108 行）：`dist\QuZi\` 目录 → `dist\SnipOCR\`
        - 故障排查（第 113 行）：`%APPDATA%\QuZi\crash.log` → `%APPDATA%\SnipOCR\crash.log`
        - 自查口径：完成后在 README 中检索 `QuZi` 与「取字」应 0 命中

- [x] 1.4 清理旧产物并终止运行中实例
     【目标对象】`dist\QuZi.exe`、`QuZi.spec`、`build\QuZi\` 目录、`build\SnapOCR\` 目录、运行中的 QuZi.exe 进程
     【修改目的】避免新旧产物混淆（`SnapOCR` 与 `SnipOCR` 仅差一字母，极易误认），并释放文件占用（否则删除/打包覆盖会 PermissionError）
     【修改方式】命令行删除与进程终止（操作类型：删除）
     【相关依赖】无（在 1.5 打包前执行即可）
     【修改内容】
        - `taskkill /F /IM QuZi.exe`（若在运行）；进程不存在时该命令报「没有找到进程」属预期，可忽略并继续
        - 删除 `QuZi.spec`（下次打包将以 `--name SnipOCR` 重新生成 `SnipOCR.spec`）
        - 删除 `dist\QuZi.exe` 与 `build\QuZi` 目录
        - 删除 `build\SnapOCR` 目录（工作区中存在的历史构建残留，一并清理以免与新名混淆）
        - 边界说明：删除前必须确认 QuZi.exe 进程已终止，否则文件被占用导致删除失败，需终止进程后重试

- [x] 1.5 重新打包 SnipOCR.exe 并完成启动验证
     【目标对象】`dist\SnipOCR.exe`（由打包命令生成的新产物）
     【修改目的】交付可分发的新命名单文件 exe，并确认运行正常、新数据目录生效
     【修改方式】PyInstaller 打包 + 进程存活检查 + 回归验证（操作类型：新增产物）
     【相关依赖】1.1–1.4 全部完成
     【修改内容】
        - 语法检查（既有验证步骤）：`python -m compileall -q main.py app test_smoke.py`
        - 回归验证（既有验证步骤）：`python test_smoke.py`（期望末行输出 `[4/4] 冒烟测试通过 ✓`）
        - 打包：`pyinstaller --noconsole --onefile --name SnipOCR --collect-all rapidocr_onnxruntime --exclude-module tensorflow --exclude-module tf_keras --exclude-module keras --exclude-module pandas --exclude-module matplotlib --exclude-module scipy --exclude-module psycopg2 main.py`（参数与原 `QuZi.spec` / README 打包命令完全一致，仅更名）
        - 启动 `dist\SnipOCR.exe`，等待约 15 秒（onefile 解压 + 启动）后执行 `tasklist /FI "IMAGENAME eq SnipOCR.exe"` 确认进程存活（onefile 模式为双进程形态属正常）
        - 确认 `%APPDATA%\SnipOCR\crash.log` 已生成且含本次启动记录（`_install_crash_logger()` 每次启动必写），以验证 1.2 的数据目录切换在打包产物中实际生效
