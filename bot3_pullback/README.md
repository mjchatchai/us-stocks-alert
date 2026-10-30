# 🚀 BOT 3: US Trend Leader Pullback & R-Multiple Trading System

ระบบสแกนหุ้นและบริหารความเสี่ยงอัตโนมัติสำหรับหุ้นสหรัฐฯ (US Stocks) โดยใช้หลักการ **Trend Following + Volatility Contraction (VCP) + Support Confluence First Retest + R-Multiple Trade Management**

---

## 🎯 4 ขั้นตอนของระบบ (Core 4-Step Methodology)

### 📌 [1/4] คัดหุ้นแข็งแกร่ง แล้วดูการสร้างฐาน (Momentum Screener & VCP Base)
* **คัดกรองสภาพคล่อง (Liquidity):** กรองหุ้นที่มี Volume เฉลี่ย 20 วัน $\ge 500,000$ หุ้น หรือมูลค่าซื้อขาย $\ge \$5,000,000$/วัน
* **วัดความแข็งแกร่ง (Momentum & RS Rank):**
  * คำนวณผลตอบแทนย้อนหลัง 1 เดือน (21 วัน), 3 เดือน (63 วัน) และ 6 เดือน (126 วัน)
  * เน้นหุ้นที่ขึ้นมากกว่า **+30%** และอยู่ในกลุ่มนำตลาด **Top 20–30% (RS Percentile $\ge 70$)**
* **กราฟรายสัปดาห์ (Weekly Chart):** ยืนเหนือ Weekly EMA 10/20 โครงสร้างภาพใหญ่เป็นขาขึ้น
* **กราฟรายวัน (Daily Base Building):**
  * จุดต่ำสุดยกสูงขึ้น (Higher Lows: Swing Low ล่าสุด $\ge$ Swing Low ก่อนหน้า)
  * การแกว่งตัวแคบลง (Volatility Contraction: ATR หรือ Bollinger Bandwidth บีบตัว)
  * ราคากลับมายืนเหนือ **EMA 9 และ 21 วัน** และความชัน (Slope) เริ่มแบนราบหรือหันหัวขึ้น

---

### 📌 [2/4] กำหนดแนวรับ แล้วรอสัญญาณซื้อ (Confluence Support & Entry Trigger)
* **โซนแนวรับร่วม (Confluence Support Zone):**
  * **Dynamic MAs:** EMA 9, EMA 21, EMA 50
  * **AVWAP (Anchored VWAP):** ต้นทุนเฉลี่ยถ่วงน้ำหนักวอลุ่มนับจากฐานราคา
  * **Prior High (S/R Flip):** ยอดเดิมที่เพิ่งเบรกเอาท์ผ่านขึ้นมา
  * **Gap Support:** ขอบบน/ขอบล่างของช่องว่างกระโดดราคาที่ยังไม่ถูกปิด
* **First Retest Filter:** ตรวจสอบว่าเป็น **"การย่อลงมาแตะแนวรับครั้งแรก (First Retest)"** หลังการ Breakout ภายใน 1–7 แท่งเทียน
* **สัญญาณเข้าซื้อ (The Trigger):**
  * ราคาย่อลงมาทดสอบโซนแนวรับแล้วดีดกลับ
  * เข้าซื้อทันทีเมื่อราคาทะลุผ่านจุดสูงสุดของแท่งเทียนก่อนหน้า:
    $$\text{Entry Price} > \text{High ของแท่งก่อนหน้า (Prior Candle High)}$$

---

### 📌 [3/4] ตั้ง Stop Loss ก่อน แล้วคำนวณจำนวนหุ้น (Risk-Based Position Sizing)
* **จุดตัดขาดทุน (Stop Loss):**
  $$\text{Stop Loss} = \min(\text{Intraday Low}, \text{Prior Candle Low}) - \$0.02$$
* **ระยะเสี่ยงต่อหุ้น (1R):**
  $$1R = \text{Entry Price} - \text{Stop Loss}$$
* **สูตรคำนวณจำนวนหุ้น (Risk Budgeting):**
  * ขนาดพอร์ต: $\$10,000$ (ตั้งค่าได้ใน `config.json`)
  * ยอมเสี่ยงต่อไม้: $0.5\%$ ($10,000 \times 0.5\% = \$50$)
  * จำนวนหุ้นที่เข้าซื้อ:
    $$\text{Shares} = \left\lfloor \frac{\$50}{1R} \right\rfloor$$
  * เงินลงทุนทั้งหมด: $\text{Shares} \times \text{Entry Price}$
  * เพดานความเสี่ยง (Safety Cap): กำหนดสัดส่วนไม่เกิน $25\%$ ของพอร์ตต่อหุ้นหนึ่งตัว

---

### 📌 [4/4] ทยอยขายกำไร แล้วติดตามหุ้นที่เหลือ (R-Multiple Exits & Trailing EMA 9)

| ขั้นตอน | ระดับราคาเป้าหมาย | แผนการจัดการ (Action) |
| :--- | :--- | :--- |
| **เป้าหมายที่ 1 (3R)** | $\text{Entry} + 3R$ | **ขายทำกำไร 50%** และ **เลื่อน Stop Loss ขึ้นมาที่ทุน (Breakeven)** ทันที เพื่อกำจัดความเสี่ยง |
| **เป้าหมายที่ 2 (5R)** | $\text{Entry} + 5R$ | **ขายทำกำไรก้อนที่สอง (50% ของที่เหลือ)** ล็อคกำไรก้อนโต |
| **Trailing Stop (Runner)** | หุ้นส่วนที่เหลือ | **รันเทรนด์ด้วย Daily EMA 9** จนกว่าแท่งเทียนวันจะปิดหลุดเส้น EMA 9 จึงปิดทั้งหมด |
| **Climax Alert** | ราคาพุ่งห่าง EMA 9 $\ge 15\%$ | แจ้งเตือนทยอยแบ่งขายลดความเสี่ยง ป้องกันกำไรหายจากการทุบกลับ |

---

## ⚙️ การตั้งค่าและการใช้งาน

### 1. ไฟล์การตั้งค่า: `config/config.json`
```json
{
  "portfolio_equity": 10000.0,
  "risk_per_trade_pct": 0.5,
  "max_allocation_per_trade_pct": 25.0,
  "tp1_r_multiple": 3.0,
  "tp1_sell_ratio": 0.5,
  "tp2_r_multiple": 5.0,
  "tp2_sell_ratio": 0.5,
  "trailing_ema": 9,
  "universe": ["NVDA", "PLTR", "TSLA", "META", "..."]
}
```

### 2. ตั้งค่า Telegram Bot ใน `.env`
1. เปิด Telegram ค้นหา `@BotFather`
2. ส่งคำสั่ง `/newbot` ตั้งชื่อ เช่น `US Pullback VIP Bot` และ username เช่น `Mj_us_pullback_bot`
3. คัดลอก HTTP API Token มาใส่ใน `bot3_pullback/.env`:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCDefgh...
TELEGRAM_CHAT_ID=8964251574
```

### 3. รันโปรแกรม
* ดับเบิ้ลคลิกไฟล์ `bot3_pullback/run_bot3.bat` หรือรันผ่านคำสั่ง:
```bash
python -m bot3_pullback.src.main
```
* เปิดดูหน้า Dashboard ที่ `bot3_pullback/docs/index.html`
