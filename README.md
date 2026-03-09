# 🧠 AI 行銷早會機器人

每天早上 9 點，5 位 AI 員工自動在 LINE 群組開會，產出行銷策略與執行任務包。

---

## 🚀 Railway 部署步驟

### 第一步：上傳程式碼到 GitHub

1. 在 GitHub 建立一個新的 **私人** repository
2. 把這個資料夾的所有檔案上傳上去

### 第二步：在 Railway 建立專案

1. 前往 https://railway.app
2. 點「New Project」→「Deploy from GitHub repo」
3. 選你剛才建立的 repo
4. Railway 會自動偵測是 Python 專案

### 第三步：設定環境變數

在 Railway 的專案頁面：
1. 點「Variables」
2. 逐一加入以下變數：

```
LINE_CHANNEL_ACCESS_TOKEN = DhBxllL/NNF5262Fi...（你的完整 Token）
LINE_CHANNEL_SECRET       = cd9c0b21df786132...
LINE_CHANNEL_ID           = 2009372553
GEMINI_API_KEY            = AIzaSyCa_n9-OMbu...
```

### 第四步：取得 Railway 網址

部署完成後，Railway 會給你一個網址，例如：
```
https://ai-meeting-bot-production.up.railway.app
```

### 第五步：設定 LINE Webhook

1. 前往 LINE Developers Console
2. 點你的 Channel → Messaging API
3. Webhook URL 填入：
   ```
   https://你的railway網址/webhook
   ```
4. 點「Verify」確認連線成功
5. 開啟「Use webhook」

### 第六步：取得 LINE 群組 ID

1. 在 LINE 建立一個群組
2. 把你的 LINE OA 加入群組
3. 在群組裡傳任意一句話
4. 傳「/id」→ 機器人會回覆群組 ID

---

## 💬 指令列表

| 指令 | 功能 |
|------|------|
| `開會` | 手動觸發開會（老闆參與模式） |
| `/id` | 查看群組 ID |
| `/status` | 查看系統狀態 |
| `/task` | 手動產出任務包 |
| `停止` | 停止今日執行 |
| `改B` | 切換到方案 B |

---

## 🕐 自動排程

| 時間 | 動作 |
|------|------|
| 08:55 | 總監詢問老闆是否參與 |
| 09:00 | 早會開始（依老闆回覆決定模式） |
| 09:15 | 總監給出結論 |
| 09:30 | 自動模式：任務包產出 |

---

## 👥 AI 員工

| 名字 | 職稱 | 個性 |
|------|------|------|
| 王雅婷 | 數據師 | 只信數字，質疑直覺 |
| 林建宏 | 策略師 | 野心派，搶市場時機 |
| 陳柔安 | 文案師 | 感性，每個字都有用 |
| 張偉誠 | 設計師 | 完美主義，視覺潔癖 |
| 陳志遠 | 總監 | 務實，整合衝突，做決定 |

---

## 🛠 本地測試

```bash
# 安裝套件
pip install -r requirements.txt

# 建立 .env 檔案
cp .env.example .env
# 填入你的 Keys

# 啟動
uvicorn main:app --reload --port 8000

# 測試 webhook（需要 ngrok）
ngrok http 8000
```
