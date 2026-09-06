// 开发模式脚本：并行启动 Vite + Electron
const { spawn } = require('child_process')
const path = require('path')

// 启动 Vite
const vite = spawn('npx', ['vite'], {
  cwd: __dirname,
  stdio: 'inherit',
  shell: true,
})

// 等待 Vite 就绪后启动 Electron
setTimeout(() => {
  const electron = spawn('npx', ['electron', '.'], {
    cwd: __dirname,
    stdio: 'inherit',
    shell: true,
    env: { ...process.env, NODE_ENV: 'development' },
  })

  electron.on('close', (code) => {
    vite.kill()
    process.exit(code)
  })
}, 3000)

vite.on('close', () => process.exit(0))
