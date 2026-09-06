// Æsirian Electron 主进程
const { app, BrowserWindow, shell } = require('electron')
const path = require('path')
const { spawn } = require('child_process')

let mainWindow = null
let backendProcess = null

// ─── 自动更新（electron-updater，仅生产构建启用） ───
function setupAutoUpdater() {
  if (app.isPackaged) {
    try {
      const { autoUpdater } = require('electron-updater')
      autoUpdater.autoDownload = false
      autoUpdater.on('update-available', () => {
        mainWindow && mainWindow.webContents.send('update-available')
      })
      autoUpdater.on('update-downloaded', () => {
        mainWindow && mainWindow.webContents.send('update-downloaded')
      })
      autoUpdater.checkForUpdates().catch(() => {})
    } catch (e) {
      console.log('[Æsirian] 自动更新不可用（未配置 publish）:', e.message)
    }
  }
}

// ─── 后端引擎管理 ───
function startBackend() {
  // 检查后端是否已在运行
  const http = require('http')
  const probe = http.get('http://127.0.0.1:8765/health', (res) => {
    console.log('[Æsirian] 后端已在运行，跳过启动')
    res.resume()
  })
  probe.on('error', () => {
    // 未运行，尝试启动
    console.log('[Æsirian] 启动后端引擎…')
    const python = process.env.PYTHON || 'python'
    const backendDir = path.join(__dirname, '..', '..', '..')
    // 启动 uvicorn
    backendProcess = spawn(python, ['-m', 'uvicorn', 'bridge.api_server:app',
      '--host', '127.0.0.1', '--port', '8765'], {
      cwd: backendDir,
      stdio: 'ignore',
      detached: false,
      env: process.env,
    })
    console.log('[Æsirian] 后端 PID:', backendProcess.pid)
  })
  probe.setTimeout(1500, () => probe.destroy())
}

// ─── 主窗口 ───
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'Æsirian — 叙事协作实验室',
    backgroundColor: '#f5f3ef',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  // 开发模式加载 Vite，生产模式加载构建产物
  const devUrl = process.env.VITE_DEV_SERVER_URL || 'http://localhost:5173'
  const prodFile = path.join(__dirname, '..', '..', 'dist', 'index.html')

  if (process.env.NODE_ENV === 'development' || process.argv.includes('--dev')) {
    mainWindow.loadURL(devUrl)
  } else {
    mainWindow.loadFile(prodFile)
  }

  // 外部链接用系统浏览器打开
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  // 打开 DevTools
  // mainWindow.webContents.openDevTools()

  mainWindow.on('closed', () => { mainWindow = null })
}

// ─── 生命周期 ───
app.whenReady().then(() => {
  startBackend()
  createWindow()
  setupAutoUpdater()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', () => {
  // 清理后端进程
  if (backendProcess) {
    console.log('[Æsirian] 停止后端引擎…')
    try { backendProcess.kill() } catch (e) {}
  }
})
