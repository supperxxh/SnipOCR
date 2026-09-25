# 变更：应用更名为「截图识字」（技术标识 SnipOCR）

## 原因

用户认为当前名称「取字」（技术标识 QuZi）不自解释，希望改名后"一看就知道是
干嘛的"。新名「截图识字」字面即功能（截图→识别文字），零理解成本；
技术标识 SnipOCR（snip=剪取 + OCR）同样自解释，用于 exe 文件名 /
数据目录 / 注册表项，延续"中文显示名 + ASCII 技术名"的行业惯例。

## 变更内容

- 显示名「取字」→「截图识字」：应用常量、图标字（"取"→"识"）、
  设置/历史子窗口标题、日志前缀、模块 docstring
- 技术标识 `QuZi` → `SnipOCR`：数据目录（%APPDATA%）、注册表自启项、
  exe 产物名、spec 文件
- README 全局更名（标题、正文、打包命令、路径说明）
- 清理旧产物（QuZi.spec / dist\QuZi.exe / build\QuZi）并终止运行中的旧实例
- 以 `--name SnipOCR` 重新打包，启动验证

## 影响

- **受影响的规范**：无（纯命名变更，无行为/接口变化）
- **受影响的代码**：
    - `app/constants.py`: `APP_NAME` 常量值。
    - `main.py`: 图标绘制字符、模块 docstring、crash logger docstring。
    - `app/settings_dialog.py`: 对话框标题。
    - `app/history_window.py`: 窗口标题。
    - `app/ocr_engine.py`: 预热失败日志前缀。
    - `app/settings.py`: `DATA_DIR` 目录名及 docstring。
    - `app/autostart.py`: 注册表 `VALUE_NAME`。
    - `README.md`: 全文更名与打包命令更新。
- **产物影响**：`dist\QuZi.exe` → `dist\SnipOCR.exe`；旧数据目录
  `%APPDATA%\QuZi` 弃用（配置回默认值，无实际损失）。
