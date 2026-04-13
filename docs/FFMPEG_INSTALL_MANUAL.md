# FFmpeg 手动安装指南（Windows）

## 为什么需要 FFmpeg？

本项目的**高级 TTS 功能**（自动拆分+拼接）使用 pydub 库来拼接多个音频片段，pydub 需要 FFmpeg 作为后端。

## 安装步骤

### 步骤 1：下载 FFmpeg

1. 访问：https://www.gyan.dev/ffmpeg/builds/
2. 找到 **FFmpeg release essentials** 部分
3. 下载：`ffmpeg-release-essentials.zip`（约 65MB）

或者直接访问：
```
https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
```

### 步骤 2：解压文件

1. 创建目录：`C:\ffmpeg`
2. 将下载的 zip 文件解压到 `C:\ffmpeg`
3. 确保目录结构如下：

```
C:\ffmpeg\
├── bin\
│   ├── ffmpeg.exe      ← 主程序
│   ├── ffprobe.exe     ← 探测工具
│   └── ffplay.exe      ← 播放工具
├── doc\
├── presets\
└── LICENSE
```

### 步骤 3：添加到系统 PATH

#### 方法 A：通过 PowerShell（推荐）

**以管理员身份**打开 PowerShell，运行：

```powershell
# 临时添加（仅当前窗口有效）
$env:Path += ";C:\ffmpeg\bin"

# 永久添加到用户环境变量
[System.Environment]::SetEnvironmentVariable(
    "Path",
    [System.Environment]::GetEnvironmentVariable("Path", "User") + ";C:\ffmpeg\bin",
    "User"
)
```

#### 方法 B：通过 Windows 设置

1. 按 `Win + R`，输入 `sysdm.cpl`，回车
2. 点击"高级"选项卡
3. 点击"环境变量"按钮
4. 在"用户变量"部分，找到 `Path`
5. 点击"编辑"
6. 点击"新建"
7. 输入：`C:\ffmpeg\bin`
8. 点击"确定"保存所有窗口

### 步骤 4：验证安装

**重要：关闭所有 PowerShell 窗口，重新打开新的窗口！**

运行：
```powershell
ffmpeg -version
```

如果看到版本信息，说明安装成功！

### 步骤 5：测试 pydub

```powershell
python -c "from pydub import AudioSegment; AudioSegment.silent(1000).export('test.mp3', format='mp3'); print('✅ 成功')"
```

如果生成 `test.mp3` 文件，说明 pydub 可以正常使用 FFmpeg。

## 常见问题

### Q1: winget 安装失败怎么办？

A: 使用上面的手动安装方法，更可靠。

### Q2: 运行 `ffmpeg` 提示找不到命令？

A: 这是因为 PATH 没有生效：
1. 确保完全关闭所有 PowerShell 窗口
2. 重新打开新的 PowerShell 窗口
3. 再次运行 `ffmpeg -version`

### Q3: pydub 仍然提示找不到 FFmpeg？

A: 检查 PATH 是否正确：
```powershell
# 查看 PATH
$env:Path -split ';' | Select-String ffmpeg

# 手动指定 FFmpeg 路径（Python 代码）
from pydub import AudioSegment
AudioSegment.converter = r"C:\ffmpeg\bin\ffmpeg.exe"
AudioSegment.ffprobe = r"C:\ffmpeg\bin\ffprobe.exe"
```

### Q4: 可以只下载 ffmpeg.exe 吗？

A: 可以，但建议下载完整的 release，包含 ffprobe 等工具。

## 安装完成后的测试

运行完整测试：
```powershell
python test_advanced_tts.py
```

测试文件会生成在 `data/audio/` 目录下。

## 备选方案（如果无法安装 FFmpeg）

如果暂时无法安装 FFmpeg，可以：

1. **使用纯文本模式**：不使用 `{rate=...}` 等高级标记
2. **使用 SSML 模式**：直接使用 `<speak>...</speak>`（最多 2 个 prosody）
3. **手动拼接**：使用其他音频编辑软件手动拼接

但强烈建议安装 FFmpeg，以充分利用高级 TTS 功能！
