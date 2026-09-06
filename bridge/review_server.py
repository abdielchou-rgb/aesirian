"""四视图审查页独立开发服务器（可选入口）

用途：仅启动 review 四视图审查功能（不加载 Orchestrator/模型），
方便在模型未下载或离线环境中单独验收 electron_ide/public/review.html。

与 bridge/api_server.py 的集成方式等价：同一份 review_api.router。
正式使用可继续走 api_server（app 已 include review_router）。

启动：python -m bridge.review_server
访问：http://127.0.0.1:8766/review.html
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bridge.review_api import router as review_router

app = FastAPI(title="Æsirian Review Page", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(review_router)

_public = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "electron_ide", "public")
if os.path.isdir(_public):
    app.mount("/static", StaticFiles(directory=_public), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(_public, "review.html"))


@app.get("/review.html")
async def review_page():
    return FileResponse(os.path.join(_public, "review.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8766)
