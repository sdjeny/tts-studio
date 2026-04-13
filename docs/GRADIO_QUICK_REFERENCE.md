# Gradio 性能问题快速参考

## 🚨 常见问题速查

### 问题 1：Tab 切换卡死

**症状：** 点击 Tab 后浏览器无响应

**原因：** 
- 使用了 `demo.load` 事件
- 嵌套过多 Accordion（>5层）

**解决：**
```python
# ❌ 错误
demo.load(on_load, None, [component])

# ✅ 正确：预加载 + 静态初始化
def build_ui():
    initial_data = load_data()  # 预加载
    with gr.Blocks():
        component = gr.Dataframe(value=initial_data)  # 静态初始化
```

---

### 问题 2：控制台大量警告

**症状：**
```
[Violation] 'click' handler took 193ms
[Violation] 'setTimeout' handler took 252ms
```

**原因：** `demo.load` 或深层嵌套组件

**解决：** 移除所有 `demo.load`，改用预加载

---

### 问题 3：组件更新不显示

**症状：** 设置了 `.value` 但前端不刷新

**原因：** Gradio 不是响应式框架

**解决：**
```python
# ❌ 错误
def on_event():
    output.value = data  # 无效

# ✅ 正确
def on_event():
    return data  # 通过返回值更新

component.change(on_event, [input], [output])
```

---

### 问题 4：首次加载数据空白

**症状：** 工程已加载但界面显示为空

**原因：** 运行时赋值不会触发渲染

**解决：**
```python
# ❌ 错误：运行时赋值
def on_app_load():
    clips_table.value = data

# ✅ 正确：初始化时传入
def build_ui():
    initial_data = load_data()
    with gr.Blocks():
        clips_table = gr.Dataframe(value=initial_data)
```

---

## 🔧 快速修复模板

### 标准预加载模式

```python
def build_ui():
    # 1. 预加载数据
    initial_value_1 = default_value
    initial_value_2 = default_value
    
    if has_initial_data:
        try:
            loaded = load_data()
            initial_value_1 = loaded.field1
            initial_value_2 = loaded.field2
        except Exception as e:
            logger.error(f"预加载失败: {e}")
    
    # 2. 静态初始化组件
    with gr.Blocks() as demo:
        comp1 = gr.Textbox(value=initial_value_1)
        comp2 = gr.Dataframe(value=initial_value_2)
        
        # 3. 只保留用户交互事件
        def on_change(input):
            return process(input)
        
        comp1.change(on_change, [comp1], [comp2])
    
    return demo
```

---

## ⚡ 性能检查清单

启动应用后检查：

- [ ] 浏览器控制台无 `[Violation]` 警告
- [ ] Tab 切换流畅（< 100ms）
- [ ] 首次加载时间 < 2秒
- [ ] 所有组件正常显示数据
- [ ] 切换工程响应迅速
- [ ] 内存占用稳定

---

## 📊 性能对比

| 方案 | 首屏加载 | Tab切换 | 警告 | 推荐度 |
|------|---------|---------|------|--------|
| demo.load | ❌ 慢 | ⚠️ 卡顿 | ❌ 大量 | ⭐ |
| 手动 .value | ❌ 不显示 | ✅ 快 | ✅ 无 | ⭐ |
| **预加载+静态** | ✅ 即时 | ✅ 快 | ✅ 无 | ⭐⭐⭐⭐⭐ |

---

## 🎯 关键记忆点

1. **Gradio 不是响应式的** - 手动赋值 `.value` 无效
2. **避免运行时事件** - 能预计算的不要运行时计算
3. **减少嵌套层级** - Accordion/Tabs 不超过3层
4. **慎用 demo.load** - 即使只执行一次也有开销
5. **服务器端预渲染** - 在 HTML 生成前准备好数据

---

**详细文档：** [GRADIO_PERFORMANCE_OPTIMIZATION.md](./GRADIO_PERFORMANCE_OPTIMIZATION.md)
