# Æsirian — Windows 完整启动指南

## 前提条件

```
Python 3.10+   →  python --version
PowerShell     →  系统自带
```

---

## 第一步：启动后端引擎

打开 PowerShell，依次执行：

```powershell
cd D:\Claude\NovelProjects\aesirian
python -m uvicorn bridge.api_server:app --host 127.0.0.1 --port 8765
```

看到日志：

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8765
```

表示引擎启动成功。

> **保持这个窗口打开**。关闭终端服务器就停了。

---

## 第二步：打开控制台

打开浏览器，访问：

```
http://127.0.0.1:8765/dashboard.html
```

你应该看到：
- 左上角 ✦ Æsirian
- 右上角 绿色圆点 + "healthy · 5 引擎"
- 四个功能面板

---

## 第三步：快速验证（3分钟走通全流程）

### 方式一：从灵感开始

1. 在 **✦ 从灵感开始** 输入框输入想法
2. 点 **创建项目**
3. 项目出现在右侧卡片
4. 点 **载入第1章《罪忆》**
5. 点 **提交章节**
6. 自动切换到 **⊞ 审计** 标签页，查看 166 道门禁结果
7. 切到 **◇ 心智网格** 查看角色信念状态图
8. 切到 **→ 建议** 查看续写方向

### 方式二：直接写

1. 先在灵感框创建项目
2. 在写作区写你的故事
3. 写完后 **Ctrl+Enter** 或点 **提交章节**
4. 系统自动执行实体提取→G1-G5→章后审计→生成建议

---

## 第四步：用第1章+第2章验证引擎

启动后端后，在另一个终端执行（保持后端运行）：

```powershell
cd D:\Claude\NovelProjects\aesirian
python -c "
import sys; sys.path.insert(0,'.')
from fastapi.testclient import TestClient
from bridge.api_server import app
exec(open('tests/write_chapter_example.py').read())
"
```

---

## 系统架构

```
你 → 浏览器 → http://127.0.0.1:8765/dashboard.html
                  ↓
            FastAPI 服务器
                  ↓
     ┌────┬────┬────┬────┬────┐
     │ToM │ KG │Gates│读者│冷却│
     │引擎│    │ 166│模型│矩阵│
     └────┴────┴────┴────┴────┘
                  ↓
            文鉴风格指纹
          (15+维度 + 爆款对比)
```

---

## 已知限制

1. **浏览器和服务器必须在同一台机器上**
   - 服务器监听 `127.0.0.1`（本地），不走网络
   - 这是本地应用的正常模式

2. **node_modules 安装超时问题**
   - 在 Linux 沙箱内执行 `npm install` 网络不稳定
   - 可在 Windows 上执行：`cd electron_ide && npm install`
   - 安装后 `npm run dev` 启动 Vite 开发服务器

3. **文鉴分析层桥接**
   - `narrative_analyzer`、`webnovel_analyzer`、`sentiment_lexicon` 等模块在启用时会自动桥接
   - 目前 pipeline 的 `_enrich_context` 使用了简化的占位版本
   - 完整版需要复制 `wenjian-v5.1.0-github-upload` 中的 `narrative_analyzer.py` 等文件
   - **不影响门禁执行**——166 道门禁全部正常工作
