# 截图识字（SnipOCR）—— 屏幕截图文字识别（离线）

> 按 `Alt + Q`，框选屏幕，文字到手。

桌面端 OCR 小工具：在屏幕**任意位置框选**一块区域，离线识别其中的**文字 / 二维码**，
一键复制。识别引擎为 RapidOCR（PaddleOCR 模型 + onnxruntime 推理），
**全部在本地运行，数据不上传**。

> 技术标识统一为 ASCII 的 `SnipOCR`（exe 文件名、数据目录、注册表项），
> 界面显示名为「截图识字」。

## 功能

- **截图识别**：全局热键（默认 `Alt + Q`，可自定义）随时触发；全屏冻结 + 橡皮筋框选（十字准星辅助），支持多显示器
- **中英混合识别**：按阅读顺序自动分行合并，中文之间不加空格
- **二维码检测**：框选区域内含二维码时同步解码，结果窗顶部绿色高亮条显示，点击即复制
- **自动复制**（可开关）：识别完成即写入剪贴板，无需点击
- **识别历史**（可开关）：最近 100 条落盘（`%APPDATA%\SnipOCR\history.jsonl`），主窗/托盘可打开回查，双击条目再复制
- **设置界面**：热键录制（必须带 Ctrl/Alt/Shift 修饰键）、各功能开关集中管理
- **开机自启**（托盘勾选 / 设置）：写 `HKCU\...\Run` 注册表，仅对打包后的 exe 生效
- **系统托盘**常驻，后台预热模型，关闭主窗即最小化到托盘

## 快速开始

```bat
:: 1. 安装依赖（Python 3.10+）
python -m pip install -r requirements.txt

:: 2. 运行
python main.py
```

## 使用

**启动形态**：程序驻留系统托盘，不占任务栏；首次运行会显示引导主窗
（之后静默启动），主窗可从托盘双击或菜单"显示主窗口"随时唤出；
重复双击 exe 会因单实例锁自动退出，不会多开。

1. 按 `Alt + Q`（或点击"开始截图"），屏幕冻结并变暗；
2. 按住鼠标左键拖出选区（右键 / `Esc` 取消）；
3. 松开鼠标，选区附近弹出识别结果（开启了自动复制则已在剪贴板）；
4. 编辑 / 复制文本，点击二维码条可复制码内容，`Esc` 关闭浮窗；
5. "识别历史"回查过往结果；"设置"修改热键与开关；
6. 关闭主窗口 = 最小化到托盘；托盘菜单"退出"才会真正退出。

## 项目结构

```
main.py                 入口：主窗、托盘、全局热键、流程编排
app/
├── about_dialog.py     关于对话框（应用名 / 版本 / 简介 / 版权）
├── constants.py        配置常量（默认热键、应用名等）
├── capture.py          截图框选：mss 抓图 + 橡皮筋选区遮罩窗
├── ocr_engine.py       RapidOCR 封装：懒加载、后台线程推理、阅读序合并
├── qrcode.py           二维码检测（OpenCV QRCodeDetector，零额外依赖）
├── result_window.py    结果浮窗：置顶可编辑 + 复制 + 二维码条
├── settings.py         用户设置（%APPDATA%/SnipOCR/config.json）
├── settings_dialog.py  设置对话框（含热键录制控件）
├── history.py          识别历史（JSONL 追加 + 自动裁剪）
├── history_window.py   历史窗口（回查 / 复制 / 清空）
└── autostart.py        开机自启（HKCU Run 注册表项）
test_smoke.py           冒烟测试（合成图走完整识别链路）
```

数据流：

```
热键/按钮 ──> CaptureOverlay（全屏框选）
                │ captured(QPixmap)
                ▼
        pixmap_to_ndarray（主线程，BGR）
                │ ndarray
                ▼
        OcrWorker（QThread：二维码检测 + RapidOCR 推理）
                │ result_ready(ocr_text, qr_text)
                ▼
        ResultWindow（展示 / 编辑 / 复制）
          + 自动复制（可选） + 历史入库（可选）
```

## 测试

```bat
python test_smoke.py
```

合成一张带文字的图片，验证「QPixmap 转换 → 二维码检测 → RapidOCR 推理 → 阅读序合并
→ QThread worker 信号回传」全链路。

## 打包为 exe（新电脑无 Python 环境可直接运行）

```bat
python -m pip install pyinstaller
pyinstaller --noconsole --onefile --name SnipOCR ^
    --collect-all rapidocr_onnxruntime ^
    --exclude-module tensorflow --exclude-module tf_keras ^
    --exclude-module keras --exclude-module pandas ^
    --exclude-module matplotlib --exclude-module scipy ^
    --exclude-module psycopg2 ^
    main.py
```

产物：`dist\SnipOCR.exe`（单文件约 140MB，含 OCR 模型，可直接拷贝到
任何 64 位 Windows 机器双击运行，无需安装任何环境）。

说明：

- `--collect-all rapidocr_onnxruntime` 把 onnx 模型一并打进包；
- `--exclude-module ...` 防止机器上已安装的无关大包（TensorFlow /
  pandas / scipy 等）被依赖分析误拉入。干净环境下可省略，
  在依赖繁杂的机器上打包必须带上，否则体积会膨胀到 500MB+；
- onefile 模式启动时需解压到临时目录，首次启动约慢 2~5 秒；
  追求启动速度可去掉 `--onefile`（生成 `dist\SnipOCR\` 目录，
  整个文件夹拷走分发）。

## 故障排查

程序崩溃或行为异常时，查看日志：`%APPDATA%\SnipOCR\crash.log`
（包含启动记录、原生崩溃栈与未捕获异常栈）。截图采用 mss（GDI）
实现，不依赖 Qt 截图接口，兼容各类打包环境。

## 已知限制

- 多显示器使用主屏缩放比例换算物理像素，混合 DPI（如一屏 100%、另一屏 150%）
  的副屏选区可能有轻微偏差；
- `keyboard` 库注册全局热键在极少数锁屏 / 提权环境下会失败，
  此时可用主窗口按钮或托盘菜单触发，功能不受影响；
- Windows 专用（截图部分依赖 GDI / mss）；
- OpenCV 二维码解码对中文内容的支持取决于编码兼容性，URL / 数字 / 英文最稳。
