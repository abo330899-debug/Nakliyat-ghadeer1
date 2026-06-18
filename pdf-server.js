const express = require("express");
const puppeteer = require("puppeteer-core");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

function getChromiumPath() {
  if (process.env.PUPPETEER_EXECUTABLE_PATH) return process.env.PUPPETEER_EXECUTABLE_PATH;

  try {
    const p = execSync("which chromium", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
    if (p) return p;
  } catch (_) {}

  try {
    const p = execSync("which chromium-browser", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
    if (p) return p;
  } catch (_) {}

  try {
    const p = execSync("which google-chrome", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
    if (p) return p;
  } catch (_) {}

  try {
    const p = execSync("ls -1 /nix/store/*-chromium-*/bin/chromium 2>/dev/null | head -n 1", {
      shell: "/bin/bash",
      stdio: ["ignore", "pipe", "ignore"],
    }).toString().trim();
    if (p) return p;
  } catch (_) {}

  return null;
}

const app = express();
app.use(express.json({ limit: "10mb" }));

app.use((req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});

app.get("/", (req, res) => {
  res.send("OK - PDF API running");
});

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function n2(x) {
  const v = Number(x);
  return Number.isFinite(v) ? v : 0;
}

function money(x) {
  return n2(x).toFixed(2) + "$";
}

function buildHtml(pdfData, cairoRegularB64, cairoBoldB64) {
  const clientName = escapeHtml(pdfData.clientName || "عميل");
  const clientPhone = escapeHtml(pdfData.clientPhone || "");
  const totalDriversAll = money(pdfData.totalDriversAll);
  const totalPaymentsAll = money(pdfData.totalPaymentsAll);
  const totalBalance = money(pdfData.totalBalance);

  const receipts = Array.isArray(pdfData.receipts) ? pdfData.receipts : [];

  const receiptsHtml = receipts
    .map((r) => {
      const title = escapeHtml(r.name || `وصل ${r.index || ""}`);
      const date = escapeHtml(r.date || "");

      const previousTotal = money(r.previousTotal);
      const driversTotal = money(r.driversTotal);
      const paymentsTotal = money(r.paymentsTotal);
      const receiptBalance = money(r.receiptBalance);
      const runningBalance = money(r.runningBalance);

      const drivers = Array.isArray(r.drivers) ? r.drivers : [];
      const payments = Array.isArray(r.payments) ? r.payments : [];

      const driversRows = drivers
        .map(
          (d, i) => `
          <tr>
            <td>${i + 1}</td>
            <td>${escapeHtml(d.date || "")}</td>
            <td>${escapeHtml(d.name || "")}</td>
            <td>${escapeHtml(d.car || "")}</td>
            <td>${escapeHtml(d.city || "")}</td>
            <td class="num">${money(d.amount)}</td>
          </tr>
        `
        )
        .join("");

      const paymentsRows = payments
        .map(
          (p, i) => `
          <tr>
            <td>${i + 1}</td>
            <td>${escapeHtml(p.date || "")}</td>
            <td>${escapeHtml(p.note || "")}</td>
            <td class="num">${money(p.amount)}</td>
          </tr>
        `
        )
        .join("");

      const driversTable =
        drivers.length > 0
          ? `
        <table class="tbl">
          <thead>
            <tr>
              <th>#</th><th>التاريخ</th><th>الاسم</th><th>السيارة</th><th>المحافظة</th><th>المبلغ</th>
            </tr>
          </thead>
          <tbody>${driversRows}</tbody>
        </table>
      `
          : `<div class="empty">لا يوجد سواق</div>`;

      const paymentsTable =
        payments.length > 0
          ? `
        <table class="tbl pay">
          <thead>
            <tr>
              <th>#</th><th>التاريخ</th><th>ملاحظة</th><th>المبلغ</th>
            </tr>
          </thead>
          <tbody>${paymentsRows}</tbody>
        </table>
      `
          : `<div class="empty">لا توجد قبوضات</div>`;

      return `
      <section class="receipt">
        <div class="receipt-head">
          <div class="rt">
            <div class="rtitle">📄 ${title}</div>
            <div class="rmeta">📅 ${date}</div>
          </div>
          <div class="chips">
            <div class="chip gray">الحساب القديم: <b>${previousTotal}</b></div>
            <div class="chip green">سواق: <b>${driversTotal}</b></div>
            <div class="chip orange">قبوضات: <b>${paymentsTotal}</b></div>
            <div class="chip blue">صافي الوصل: <b>${receiptBalance}</b></div>
            <div class="chip gold">الرصيد التراكمي: <b>${runningBalance}</b></div>
          </div>
        </div>

        <div class="two">
          <div>
            <div class="stitle">🚛 السواق</div>
            ${driversTable}
          </div>
          <div>
            <div class="stitle">💰 القبوضات</div>
            ${paymentsTable}
          </div>
        </div>
      </section>
    `;
    })
    .join("");

  return `
<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <style>
    @font-face {
      font-family: "Cairo";
      src: url(data:font/ttf;base64,${cairoRegularB64}) format("truetype");
      font-weight: 400;
    }
    @font-face {
      font-family: "Cairo";
      src: url(data:font/ttf;base64,${cairoBoldB64}) format("truetype");
      font-weight: 700;
    }

    :root{
      --brand1:#003366; --brand2:#004b95; --gold:#c2a356;
      --green:#008d5f; --orange:#ff9500; --muted:#666;
    }
    *{ box-sizing:border-box; }
    body{ margin:0; font-family:"Cairo", sans-serif; color:#111; }
    .header{
      background: linear-gradient(90deg, var(--brand1), var(--brand2), var(--gold));
      color:#fff; border-radius:14px; padding:16px 18px;
      display:flex; justify-content:space-between; align-items:center; gap:14px;
    }
    .h1{ font-weight:700; font-size:18px; margin:0; }
    .sub{ opacity:.95; font-size:13px; margin-top:4px; }

    .summary{ margin-top:14px; display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; }
    .card{
      border-radius:14px; padding:12px; background:#fff;
      box-shadow: 0 6px 18px rgba(0,0,0,.08); border-top:4px solid #ddd;
    }
    .card .lbl{ color:var(--muted); font-size:12px; margin-bottom:6px; }
    .card .val{ font-size:16px; font-weight:700; }
    .card.green{ border-top-color: var(--green); }
    .card.orange{ border-top-color: var(--orange); }
    .card.gold{ border-top-color: var(--gold); }

    .receipt{
      margin-top:14px; background:#fff; border-radius:14px; padding:14px;
      box-shadow: 0 6px 18px rgba(0,0,0,.08);
      page-break-inside: avoid;
    }
    .receipt-head{
      display:flex; flex-direction:column; gap:10px;
      border-right:5px solid var(--brand2); padding-right:12px; margin-bottom:10px;
    }
    .rtitle{ font-weight:700; font-size:16px; }
    .rmeta{ color:var(--muted); font-size:13px; }

    .chips{ display:flex; flex-wrap:wrap; gap:8px; }
    .chip{ background:#f3f6ff; border:1px solid #e6ecff; padding:6px 10px; border-radius:999px; font-size:12px; }
    .chip.gray{ background:#f5f5f5; border-color:#e8e8e8; }
    .chip.green{ background:#eafff6; border-color:#c8f3e1; }
    .chip.orange{ background:#fff4e6; border-color:#ffe0b8; }
    .chip.blue{ background:#eef5ff; border-color:#dbe9ff; }
    .chip.gold{ background:#fff8e1; border-color:#f3e1a7; }

    .two{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    .stitle{ font-weight:700; margin:8px 0; }

    .tbl{ width:100%; border-collapse:collapse; border-radius:12px; overflow:hidden; border:1px solid #eef2ff; }
    .tbl thead th{
      background: linear-gradient(90deg, var(--brand1), var(--brand2));
      color:#fff; padding:9px 8px; font-size:12px; text-align:center;
    }
    .tbl.pay thead th{ background: linear-gradient(90deg, #e67e22, #f39c12); }
    .tbl td{ padding:8px 8px; font-size:12px; border-bottom:1px solid #f0f2f7; text-align:center; }
    .tbl tr:last-child td{ border-bottom:none; }
    .num{ font-weight:700; }

    .empty{ padding:12px; border-radius:12px; background:#fafafa; color:#888; text-align:center; border:1px dashed #ddd; }

    @page { size:A4; margin:12mm; }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="h1">كشف حساب العميل</div>
      <div class="sub">شركة الغدير للنقل والتخليص المكرمي</div>
    </div>
    <div style="text-align:left; direction:ltr;">
      <div style="font-weight:700;">${clientName}</div>
      <div style="font-size:13px; opacity:.95;">${clientPhone ? "📞 " + clientPhone : ""}</div>
    </div>
  </div>

  <div class="summary">
    <div class="card green">
      <div class="lbl">مجموع السواق</div>
      <div class="val">${totalDriversAll}</div>
    </div>
    <div class="card orange">
      <div class="lbl">مجموع القبوضات</div>
      <div class="val">${totalPaymentsAll}</div>
    </div>
    <div class="card gold">
      <div class="lbl">الرصيد النهائي</div>
      <div class="val">${totalBalance}</div>
    </div>
  </div>

  ${receiptsHtml || `<div class="receipt"><div class="empty">لا توجد وصولات</div></div>`}
</body>
</html>
  `;
}

// Health check سريع
app.get("/", (req, res) => {
  res.send("OK - PDF API running");
});

app.post("/api/client-pdf/:clientId", async (req, res) => {
  let browser = null;
  try {
    const pdfData = req.body;

    if (!pdfData || !Array.isArray(pdfData.receipts)) {
      return res.status(400).send("بيانات غير صحيحة: receipts مفقود");
    }

    const cairoRegularPath = path.join(__dirname, "fonts", "Cairo-Regular.ttf");
    const cairoBoldPath = path.join(__dirname, "fonts", "Cairo-Bold.ttf");

    if (!fs.existsSync(cairoRegularPath) || !fs.existsSync(cairoBoldPath)) {
      return res.status(500).send("الخطوط غير موجودة: ضع Cairo-Regular.ttf و Cairo-Bold.ttf داخل مجلد fonts");
    }

    const cairoRegularB64 = fs.readFileSync(cairoRegularPath).toString("base64");
    const cairoBoldB64 = fs.readFileSync(cairoBoldPath).toString("base64");

    const html = buildHtml(pdfData, cairoRegularB64, cairoBoldB64);

    const executablePath = getChromiumPath();
    console.log("Using Chromium at:", executablePath);

    browser = await puppeteer.launch({
      headless: "new",
      executablePath,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--font-render-hinting=none",
      ],
    });

    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: "networkidle0" });

    const pdfBuffer = await page.pdf({
      format: "A4",
      printBackground: true,
      margin: { top: "12mm", right: "12mm", bottom: "12mm", left: "12mm" },
    });

    const safeName = (pdfData.clientName || "عميل")
      .toString()
      .replace(/[\\/:*?"<>|]+/g, "_");

    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Disposition", `attachment; filename="كشف_حساب_${safeName}.pdf"`);

    return res.send(pdfBuffer);
  } catch (err) {
    console.error("PDF endpoint error:", err);
    return res.status(500).send("حدث خطأ أثناء إنشاء PDF: " + (err?.message || err));
  } finally {
    if (browser) {
      try { await browser.close(); } catch (_) {}
    }
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log("Server running on port", PORT));