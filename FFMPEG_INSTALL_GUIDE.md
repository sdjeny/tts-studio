# FFmpeg 安装指南（Windows）

## 方法1：手动安装（推荐，最稳定）

### 步骤：

1. **下载 FFmpeg**
   - 访问：https://www.gyan.dev/ffmpeg/builds/
   - 下载 `ffmpeg-release-essentials.zip`（约 65MB）

2. **解压文件**
   - 将 zip 文件解压到：`C:\ffmpeg`
   - 确保目录结构如下：
     ```
     C:\ffmpeg\
     ├── bin\
     │   ├── ffmpeg.exe
     │   ├── ffprobe.exe
     │   └── ...
     ├── doc\
     └── ...
     ```

3. **添加到系统 PATH**
   
   **方法 A：通过 PowerShell（管理员权限）**
   ```powershell
   $env:Path += ";C:\ffmpeg\bin"
   [System.Environment]::SetEnvironmentVariable("Path", $env:Path, "User")
   ```
   
   **方法 B：通过系统设置**
   - 按 `Win + X` → 选择"系统"
   - 点击"高级系统设置"
   - 点击"环境变量"
   - 在"用户变量"中找到 `Path`
   - 点击"编辑" → "新建"
   - 添加：`C:\ffmpeg\bin`
   - 点击"确定"保存

4. **验证安装**
   打开新的 PowerShell 窗口，运行：
   ```powershell
   ffmpeg -version
   ```
   如果显示版本信息，说明安装成功！

---

## 方法2：使用 winget（如果网络良好）

```powershell
winget install Gyan.FFmpeg
```

**注意**：winget 下载可能需要科学上网或稳定的网络连接。

---

## 常见问题

### Q: 安装后运行 `ffmpeg` 提示找不到命令？

A: 这是因为 PATH 没有生效，请：
1. 关闭所有 PowerShell 窗口
2. 重新打开新的 PowerShell 窗口
3. 再次运行 `ffmpeg -version`

### Q: winget 下载失败？

A: 使用手动安装方法（方法1），更可靠。

### Q: 如何验证 pydub 是否能找到 FFmpeg？

A: 运行以下 Python 代码：
```python
from pydub import AudioSegment
import io

# 测试 pydub
try:
    silence = AudioSegment.silent(duration=1000)
    print("✅ pydub 可以正常使用 FFmpeg")
except Exception as e:
    print(f"❌ pydub 无法使用 FFmpeg: {e}")
```

---

## 安装完成后的下一步

FFmpeg 安装成功后，重新运行测试：

```powershell
python test_advanced_tts.py
```

测试文件会生成在 `data/audio/` 目录下。
