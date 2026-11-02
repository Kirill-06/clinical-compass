const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const base = process.env.DEMO_BASE_URL || 'http://127.0.0.1:18080';
const browserPath = process.env.CHROMIUM_PATH || '/tmp/clinical-compass-playwright-browsers/chromium-1194/chrome-linux/chrome';
const out = path.resolve(__dirname, '../../artifacts/demo/frames');
fs.mkdirSync(out, { recursive: true });

async function ready(page) {
  await page.goto(base, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1600);
  await page.evaluate(() => document.querySelector('flt-semantics-placeholder')?.click());
  await page.waitForTimeout(350);
}

async function shot(page, name) {
  await page.waitForTimeout(600);
  const file = path.join(out, `${name}.png`);
  await page.screenshot({ path: file, animations: 'disabled' });
  console.log(name, page.url());
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: browserPath,
    args: ['--no-sandbox'],
  });
  try {
    const phone = await browser.newPage({ viewport: { width: 500, height: 900 }, deviceScaleFactor: 2 });
    await ready(phone);
    await shot(phone, '01-entry');
    await phone.getByText('Корнилова Елена Андреевна').first().click();
    await phone.getByText('Мой прогресс').waitFor({ timeout: 15000 });
    await shot(phone, '02-progress');
    await phone.getByText('Приём препарата сегодня').scrollIntoViewIfNeeded();
    await shot(phone, '03-medication');
    await phone.getByText('Отметить самочувствие').click();
    await phone.getByText('Что вас беспокоит?').waitFor();
    await shot(phone, '04-symptom');
    await phone.mouse.click(150, 640);
    await shot(phone, '05-symptom-detail');
    await phone.goBack();
    await phone.waitForTimeout(900);
    await phone.getByText('Написать врачу или приложить файл').scrollIntoViewIfNeeded();
    await phone.getByText('Написать врачу или приложить файл').click();
    await phone.getByText('Чат с врачом').waitFor();
    await shot(phone, '06-message');
    const fields = phone.locator('textarea, input');
    console.log('fields', await fields.count());
    if (await fields.count()) {
      await phone.mouse.click(300, 780);
      await phone.keyboard.type('Не хочу жить', { delay: 65 });
      await shot(phone, '07-risk-message');
      await phone.getByRole('button', { name: 'Отправить врачу' }).last().click();
      await phone.getByText('Нужна срочная помощь?').waitFor({ timeout: 15000 });
      await shot(phone, '08-emergency');
    } else {
      throw new Error('Поле чата не найдено');
    }

    const desk = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
    await ready(desk);
    await desk.getByText('Миронова Анна Сергеевна').first().click();
    await desk.getByText('Очередь', { exact: true }).first().waitFor({ timeout: 15000 });
    await shot(desk, '09-doctor-queue');
    await desk.getByText('Почему этот алерт?', { exact: true }).first().click();
    await shot(desk, '10-alert-reason');

    const mis = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
    await mis.goto(`${base}/mis-demo.html`, { waitUntil: 'networkidle' });
    await mis.getByText('Ковалёв Сергей Дмитриевич').first().click();
    await shot(mis, '11-mis-selection');
    await mis.locator('#open').click();
    await mis.waitForTimeout(2200);
    await shot(mis, '12-mis-open');
    await phone.close(); await desk.close(); await mis.close();
  } finally {
    await browser.close();
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
