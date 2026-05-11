# TTS Studio 回归检查清单

每次代码改动后，部署前必须逐项确认。

## 一、数据模型默认值

| 检查项 | 期望值 | 验证方式 |
|--------|--------|----------|
| 新剧集 `style_enabled` | `False`（关闭） | 创建剧集后 API 返回验证 |
| 新对白 `style_enabled` | `False`（关闭） | 创建对白后 API 返回验证 |
| 对白 `character_id` | 必须是真实角色 UUID | 不能是 `__旁白__`/`__场景__` 等虚拟 ID |
| 对白 `character_name` | 与角色表一致 | 不能显示 `⚠ 异常` |

## 二、LLM 生成对白

| 检查项 | 期望值 | 验证方式 |
|--------|--------|----------|
| LLM 返回 `__旁白__`/`__场景__` 时 | 正确映射到同名真实角色 | 生成后检查 `character_id` 为真实 UUID |
| LLM 返回带下划线的角色名 | 归一化匹配（去下划线） | 步骤 3 归一化正则包含 `_` |
| LLM 返回全新角色名 | 自动创建新角色 | 新角色出现在角色列表中 |
| 新建角色的 `voice_id` | 复用项目已有音色，无则 `aiden` | 检查新角色 voice_id |

## 三、虚拟角色系统

| 检查项 | 期望值 | 验证方式 |
|--------|--------|----------|
| 代码中无 `__旁白__`/`__场景__` | `grep` 搜索结果为空 | `grep -r "__旁白__" app/` |
| 代码中无 `_VIRTUAL_CHARS` | `grep` 搜索结果为空 | `grep -r "_VIRTUAL_CHARS" app/` |
| 前端下拉框无虚拟选项 | 无 `__旁白__`/`__场景__` option | 检查 `DialogueList.tsx` |
| 角色面板无虚拟角色特殊逻辑 | 所有角色一视同仁 | 检查 `CharacterPanel.tsx` |

## 四、TTS 生成

| 检查项 | 期望值 | 验证方式 |
|--------|--------|----------|
| `style_enabled=False` 时 instruct | 仅 `base_instruct` | 检查 TTS 提交参数 |
| `style_enabled=True` 时 instruct | `base_instruct` + `scene_instruct` | 检查 TTS 提交参数 |
| 批量生成与单条生成 | 共用同一逻辑（无代码克隆） | 检查 `_resolve_dialogue_tts_params` |
| 角色不存在时 | 自动创建角色（voice_id 兜底） | 异常角色名的容错 |

## 五、数据迁移

| 检查项 | 期望值 | 验证方式 |
|--------|--------|----------|
| 旧数据 `character_id=__旁白__` | 全部迁移到真实角色 ID | 扫描所有项目对白 |
| 旧数据 `character_id=__场景__` | 全部迁移到真实角色 ID | 扫描所有项目迁移后验证 |
| 迁移后 `character_name` | 与角色表一致 | 检查对白 `character_name` 字段 |

## 六、插入对白

| 检查项 | 期望值 | 验证方式 |
|--------|--------|----------|
| 插入到某条对白后 | 新对白 order = 原 order + 1，后续顺序后移 | 插入后检查剧集对白列表顺序 |
| 插入到第一条前 | 新对白 order = 0，全部后移 | 插入后检查第一条 order 为 0 |
| 插入到最后一条后 | 新对白 order = max + 1 | 插入后检查末尾 order |
| 连续插入多条 | order 无重复、无跳号 | 多次插入后检查 order 连续性 |
| 并发插入 | 无数据竞争导致重复 order | 快速连续插入验证 |
| 点击 "+" 后 placeholder 出现 | 立即在该条后显示空白的编辑态 | 点击后 UI 验证 |
| placeholder 自动进入编辑态 | textarea 弹出并自动聚焦 | 点击后 UI 验证 |
| 取消后精确回滚 | placeholder 消失，原有对白 order 不变 | 取消后检查列表 |
| API 失败时回滚 | 显示错误，列表恢复到插入前的状态 | 断网/断后端测试 |
| 角色继承 | character_id 为空时继承目标对白角色 | 不选角色直接插入，检查角色字段 |
| 角色 fallback | 角色被删除时 fallback 到第一个角色 | 删除角色后插入，检查不显示异常 |

## 七、order 重建

| 检查项 | 期望值 | 验证方式 |
|--------|--------|----------|
| 历史遗留重复 order | reorder 后全部唯一且连续 | 调用 reorder 端点后验证 |
| 空剧集 reorder | 正常返回，无报错 | 对无对白的剧集调用 reorder |
| 单条对白 reorder | order 变为 0 | 对白数为 1 时调用验证 |
| reorder 幂等 | 多次调用结果一致 | 连续调用两次比对结果 |

## 八、服务部署

| 检查项 | 期望值 | 验证方式 |
|--------|--------|----------|
| 后端启动无报错 | `uvicorn` 正常监听 8000 | `curl /api/projects` 返回 200 |
| 前端编译无报错 | `npm run build` 成功 | `dist/` 目录有最新产物 |
| 前端服务正常 | 访问 5173 返回 200 | `curl http://localhost:5173/` |
| API 代理正常 | `/api/*` 代理到 8000 | 前端页面能正常加载项目列表 |

## 九、配置页面（Issue #11）

### 9.1 Config API

| 检查项 | 期望值 | 验证方式 | 实际结果 |
|--------|--------|----------|----------|
| `GET /api/config` | 返回完整配置，含 llm/tts 节点 | `curl http://localhost:8000/api/config` | ✅ 返回 llm + tts 节点 |
| api_key 脱敏 | 显示为 `****` 或 `xxxx****yyyy` | GET 返回中 `llm.api_key` 不含原始值 | ✅ `****` |
| `PATCH /api/config` 修改单字段 | temperature 更新为新值 | `curl -X PATCH ... -d '{"data":{"llm":{"temperature":0.85}}}'` | ✅ 0.85 |
| `PATCH /api/config` 修改嵌套字段 | tts.base_url 更新 | `curl -X PATCH ... -d '{"data":{"tts":{"base_url":"http://test:1234"}}}'` | ✅ |
| PATCH 脱敏值不覆盖 | 传 `xxxx****abcd` 时跳过，保留真实 key | PATCH 后 GET 验证 api_key 仍为脱敏值 | ✅ 跳过 |
| PATCH 空 body `{}` | 返回 422（缺少 data 字段） | `curl -X PATCH -d '{}'` | ✅ 422 |
| PATCH 无效 JSON | 返回 422 | `curl -X PATCH -d 'not json'` | ✅ 422 |
| 配置持久化 | PATCH 后 config.yaml 写入新值 | `grep temperature config.yaml` | ✅ 持久化 |
| `GET /api/health` | `{"status":"ok"}` | `curl /api/health` | ✅ |

### 9.2 前端 Settings 页面

| 检查项 | 期望值 | 验证方式 | 实际结果 |
|--------|--------|----------|----------|
| 首页可访问 | HTTP 200 | `curl -o /dev/null -w '%{http_code}' /` | ✅ 200 |
| Settings 入口可见 | header 有 ⚙️ 按钮 | 浏览器截图验证 | ⬜ 待浏览器环境 |
| 配置表单渲染 | 显示 llm/tts 等节点卡片 | 浏览器截图验证 | ⬜ 待浏览器环境 |
| api_key 显示脱敏 | 输入框显示 `****` | 浏览器检查 | ⬜ 待浏览器环境 |
| 保存后 toast | 绿色成功提示 | 浏览器操作验证 | ⬜ 待浏览器环境 |
| 保存后持久化 | 刷新页面值还在 | 浏览器刷新验证 | ⬜ 待浏览器环境 |
| 控制台无 JS 错误 | Console 无红色报错 | `browser_console()` | ⬜ 待浏览器环境 |

### 9.3 注意事项

- 空 body `{}` 返回 422 是正确行为（Pydantic 要求 `data` 字段）
- 前端测试项需要 Chrome/Chromium 环境，当前容器未安装，待补充
- 测试完成后需还原配置到原始值
