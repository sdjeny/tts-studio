# TTS Studio 使用指南

## 项目概述
TTS Studio 是一个文本转语音（Text-to-Speech）项目，用于实现语音合成与音频处理功能。项目包含后端服务（Python Flask/uvicorn）和前端界面（React/Vite）。

## 环境准备

### 宿主机配置
- **系统**: armbian
- **用户**: hermes (无 sudo 权限)
- **Docker**: 26.1.5

### 容器启动
1. 进入测试容器目录：
   ```bash
   cd /work/docker/tts-studio-new/
   ```

2. 启动测试容器：
   ```bash
   docker-compose up -d
   ```

3. 验证服务：
   ```bash
   curl http://127.0.0.1:7861/  # 检查服务是否正常
   ```

## 核心功能

### 1. 语音生成
- **接口**: `POST /api/tts`
- **参数**:
  - `text`: 需转换的文字内容
  - `character_id`: 角色ID（可选）
  - `style_enabled`: 是否启用风格化（布尔值）
- **示例**:
  ```bash
  curl -X POST http://127.0.0.1:7861/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，欢迎使用TTS Studio","character_id": "char_001"}'
  ```

### 2. 对白管理
- **新增对白**: `POST /api/dialogues`
- **修改对白**: `PUT /api/dialogues/{id}`
- **删除对白**: `DELETE /api/dialogues/{id}`

### 3. 角色管理
- **新增角色**: `POST /api/characters`
- **修改角色**: `PUT /api/characters/{id}`
- **删除角色**: `DELETE /api/characters/{id}`

## 前端界面

### 访问地址
- `http://127.0.0.1:5173/`

### 主要功能
- 项目列表展示
- 对白编辑与播放
- 角色管理
- 配置设置

## 配置说明

### 配置文件
- **路径**: `app/config.yaml`
- **敏感数据**: API密钥、模型参数等
- **注意事项**: 
  - 不能被volume直接覆盖
  - `setup.sh` 可能覆盖配置，需添加判断

### 端口映射
- 测试容器: `tts-studio-for-test` (端口 7861 → 容器内 8000)
- 旧版本容器: 7860 保持不变

## 故障排查

### 容器未启动
1. 检查日志：
   ```bash
   docker logs tts-studio-for-test
   ```

2. 验证依赖服务：
   - 确保数据库、模型服务正常运行

## 部署规则

### 测试容器
1. 端口映射: 7861 (外部访问)
2. 旧容器: 7860 保持不变

### 配置覆盖
1. `config.yaml` 需先备份再更新
2. `setup.sh` 覆盖时需添加条件判断

## 扩展建议

1. **自定义角色**: 查阅 `docs/character-voice-design.md`
2. **批量操作**: 参考 `docs/batch-operations-guide.md`
3. **插入对白**: 查看 `docs/insert-dialogue.md`

## 更新日志
- **v1.0.0**: 初始版本
- **v1.1.0**: 增加角色管理功能
- **v1.2.0**: 优化配置流程
- **v1.3.0**: 增加故障排查指南