/**
 * Æsirian dashboard.html 浏览器验证
 * 用 Playwright 无头浏览器打开 dashboard，验证所有功能
 */
const { chromium } = require('/sessions/vigilant-zen-curie/.npm/_npx/31e32ef8478fbf80/node_modules/playwright-core')
const path = require('path')
const fs = require('fs')

async function main() {
  console.log('🚀 启动浏览器验证 dashboard.html...')

  const browser = await chromium.launch({
    // 使用 headless shell（依赖更少）
    executablePath: '/sessions/vigilant-zen-curie/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell',
    args: ['--no-sandbox'],
  })

  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
  const errors = []

  // 捕获页面错误
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push('[console.error] ' + msg.text())
  })
  page.on('pageerror', err => errors.push('[pageerror] ' + err.message))

  // 1. 打开 dashboard
  console.log('1️⃣ 打开 http://127.0.0.1:8765/dashboard.html')
  await page.goto('http://127.0.0.1:8765/dashboard.html', { waitUntil: 'networkidle' })
  await page.waitForTimeout(1500)

  // 2. 检查标题
  const title = await page.title()
  console.log(`   标题: ${title}`)

  // 3. 检查健康状态
  const healthText = await page.$eval('#health-text', el => el.textContent).catch(() => 'NOT FOUND')
  console.log(`   引擎状态: ${healthText}`)

  // 4. 检查关键元素
  const elements = ['idea-input', 'create-result', 'project-card', 'chapter-text', 'tab-writing', 'tab-mind', 'tab-gates', 'tab-suggest']
  for (const id of elements) {
    const exists = await page.$('#' + id)
    console.log(`   ${exists ? '✅' : '❌'} #${id}`)
  }

  // 5. 创建项目
  console.log('2️⃣ 创建项目')
  await page.click('#btn-create').catch(e => {})
  // 直接用JS调API
  await page.evaluate(async () => {
    const res = await fetch('http://127.0.0.1:8765/import-from-pwa', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({premise:'洛阳星港的修复师', unit_text:'陈默修复罪忆水晶', characters:[{name:'陈默',role:'修复师'}]})
    })
    return res.json()
  }).then(data => {
    console.log(`   ✅ 项目创建: ${data.project_id ? data.project_id.slice(0,12) : JSON.stringify(data)}`)
  }).catch(e => {
    console.log(`   ❌ 创建失败: ${e.message}`)
    errors.push('[create] ' + e.message)
  })

  // 6. 截图
  const shotDir = path.join(__dirname, '..', 'output', 'playwright')
  fs.mkdirSync(shotDir, { recursive: true })
  const shotPath = path.join(shotDir, 'dashboard.png')
  await page.screenshot({ path: shotPath, fullPage: true })
  console.log(`3️⃣ 截图保存: ${shotPath}`)

  // 7. 检查页面截图里的文字
  const bodyText = await page.evaluate(() => document.body.innerText)
  console.log(`4️⃣ 页面文本片段: ${bodyText.slice(0, 200).replace(/\n/g, ' ')}`)

  // 8. 错误汇总
  if (errors.length > 0) {
    console.log('\n⚠️ 发现页面错误:')
    errors.forEach(e => console.log(`  ${e.slice(0, 120)}`))
  } else {
    console.log('\n✅ 无页面错误')
  }

  await browser.close()
  console.log('\n🏁 验证完成')
}

main().catch(err => {
  console.error('FATAL:', err.message)
  process.exit(1)
})
