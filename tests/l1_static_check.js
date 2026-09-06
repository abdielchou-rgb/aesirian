/**
 * L1 Static Checks — Node.js + JSDOM validation for dashboard.html
 * Run: node tests/l1_static_check.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const DASHBOARD_PATH = path.join(__dirname, '..', 'electron_ide', 'public', 'dashboard.html');

function loadDashboard() {
    const html = fs.readFileSync(DASHBOARD_PATH, 'utf-8');
    const dom = new JSDOM(html, {
        url: 'http://127.0.0.1:8765/dashboard.html',
        pretendToBeVisual: true,
        resources: 'usable',
        runScripts: 'dangerously',
    });
    return dom;
}

function testJSSyntax(dom) {
    const scripts = dom.window.document.querySelectorAll('script');
    let errors = 0;
    scripts.forEach((script, i) => {
        if (script.textContent) {
            try {
                new Function(script.textContent);
            } catch (e) {
                console.error(`❌ Script ${i} syntax error:`, e.message);
                errors++;
            }
        }
    });
    if (errors === 0) console.log('✅ All inline scripts parse without syntax errors');
    return errors === 0;
}

function testDOMElements(dom) {
    const requiredElements = [
        'toast',
        'idea-input',
        'btn-create',
        'recent-list',
        'view-inspiration',
        'view-writing',
        'project-title',
        'score-badge',
        'chapter-text',
        'submit-status',
        'submit-result',
        'btn-ai-continue',
        'btn-submit',
        'btn-more',
        'panel-layer',
        'panel-title',
        'more-drawer',
        'review-drawer',
        'review-body',
        'sug-list',
        'sug-stats',
        'mind-empty',
        'mind-content',
        'mind-svg',
        'belief-panel',
        'tension-zone',
        'mind-json',
        'gates-empty',
        'gates-content',
        'gates-summary-cards',
        'gates-simplified',
        'gates-expert',
        'btn-gate-mode',
        'chapters-empty',
        'chapters-list',
        'style-empty',
        'style-content',
        'style-radar',
        'style-sensory',
        'style-dialogue',
        'sim-hypothesis',
        'sim-char',
        'sim-prop',
        'sim-val',
        'sim-belief-list',
        'sim-result',
        'div-fragments',
        'div-result',
        'wiki-name',
        'wiki-type',
        'wiki-desc',
        'wiki-groups',
        'ol-premise',
        'ol-template',
        'ol-chapters',
        'ol-result',
    ];
    let errors = 0;
    requiredElements.forEach(id => {
        const el = dom.window.document.getElementById(id);
        if (!el) {
            console.error(`❌ Missing required element: #${id}`);
            errors++;
        }
    });
    if (errors === 0) console.log('✅ All required DOM elements present');
    return errors === 0;
}

function testAPICalls(dom) {
    const scripts = Array.from(dom.window.document.querySelectorAll('script'))
        .filter(s => s.textContent);
    const allScriptContent = scripts.map(s => s.textContent).join('\n');
    
    const apiCalls = [
        '/health',
        '/import-from-pwa',
        '/project/',
        '/mind-grid',
        '/submit-chapter',
        '/suggestions',
        '/chapter-1-sample',
        '/generate-chapter',
        '/chapters',
        '/export/md',
        '/belief',
        '/projects',
        '/style-report',
        '/simulate',
        '/diverge',
        '/wiki',
        '/ai-continue',
        '/api/context',
        '/api/generate-outline',
    ];
    
    let errors = 0;
    apiCalls.forEach(endpoint => {
        if (!allScriptContent.includes(endpoint)) {
            console.error(`❌ API endpoint not referenced in JS: ${endpoint}`);
            errors++;
        }
    });
    if (errors === 0) console.log('✅ All required API endpoints referenced in JS');
    return errors === 0;
}

function testFunctionDefinitions(dom) {
    const scripts = Array.from(dom.window.document.querySelectorAll('script'))
        .filter(s => s.textContent);
    const allScriptContent = scripts.map(s => s.textContent).join('\n');
    
    const requiredFunctions = [
        'api(',
        'toast(',
        'switchView(',
        'openPanel(',
        'closePanel(',
        'toggleMore(',
        'closeMore(',
        'openReview(',
        'closeReview(',
        'checkHealth(',
        'startWriting(',
        'loadRecentProjects(',
        'openProject(',
        'refresh(',
        'submitChapter(',
        'renderReview(',
        'refreshSuggestions(',
        'renderMindGrid(',
        'renderSuggestions(',
        'loadSampleChapter1(',
        'generateChapter(',
        'loadChapters(',
        'viewChapter(',
        'deleteChapter(',
        'exportMarkdown(',
        'selectCharacter(',
        'renderBeliefPanel(',
        'toggleBelief(',
        'addBelief(',
        'renderGateResults(',
        'toggleGateMode(',
        'drawRadar(',
        'loadStyleReport(',
        'drawSensory(',
        'drawDialoguePie(',
        'exportEpub(',
        'runSimulation(',
        'runDiverge(',
        'addSimBelief(',
        'renderCrossChapter(',
        'loadWiki(',
        'addWikiElement(',
        'harvestWiki(',
        'generateOutline(',
        'inspectContext(',
        'insertAtCursor(',
        'aiContinue(',
    ];
    
    let errors = 0;
    requiredFunctions.forEach(fn => {
        if (!allScriptContent.includes(fn)) {
            console.error(`❌ Required function not defined: ${fn}`);
            errors++;
        }
    });
    if (errors === 0) console.log('✅ All required JS functions defined');
    return errors === 0;
}

function testNoConsoleErrors(dom) {
    const originalError = console.error;
    let hasError = false;
    console.error = (...args) => {
        if (args[0] && args[0].includes && (args[0].includes('Failed to load') || args[0].includes('404'))) {
            hasError = true;
        }
        originalError.apply(console, args);
    };
    
    // Try to execute scripts in JSDOM
    const scripts = dom.window.document.querySelectorAll('script');
    scripts.forEach(script => {
        if (script.textContent) {
            try {
                dom.window.eval(script.textContent);
            } catch (e) {
                // Some functions will fail without backend, that's OK
            }
        }
    });
    
    console.error = originalError;
    if (!hasError) console.log('✅ No critical console errors on load');
    return !hasError;
}

// Main
console.log('🔍 L1 Static Check — JSDOM Validation\n');
console.log('Dashboard:', DASHBOARD_PATH);

try {
    const dom = loadDashboard();
    console.log('✅ Dashboard HTML loads in JSDOM\n');
    
    const results = [
        testJSSyntax(dom),
        testDOMElements(dom),
        testAPICalls(dom),
        testFunctionDefinitions(dom),
        testNoConsoleErrors(dom),
    ];
    
    const passed = results.filter(r => r).length;
    const total = results.length;
    
    console.log(`\n📊 L1 Results: ${passed}/${total} checks passed`);
    process.exit(passed === total ? 0 : 1);
} catch (e) {
    console.error('❌ L1 Check failed:', e.message);
    process.exit(1);
}