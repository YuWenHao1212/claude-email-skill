---
name: email
description: Email assistant — read, reply, draft, search emails via IMAP (Gmail & Outlook). This skill should be used when the user wants to read, write, search, reply, or manage emails. Triggers on "check email", "read email", "draft", "reply", "help me with this email", or any email-related request.
---

# Email 工作流

## 環境設定

讀取同目錄下的 `env.md` 取得 python 指令、email_ops.py 路徑、帳號名稱。

如果 `env.md` 不存在，執行下方的「首次設定」。如果存在，跳到「工具指令」直接開始工作。

---

## 首次設定（僅在 env.md 不存在時執行）

### Step 1：確認 Python

執行 `python3 --version`。如果失敗，試 `python --version`。
記住能用的指令。如果都沒有，告訴使用者安裝 Python 3.8+：
- Mac：通常已內建
- Windows：到 https://www.python.org/downloads/ 下載，安裝時勾選「Add Python to PATH」

### Step 2：確認 email_ops.py 路徑

email_ops.py 在此 SKILL.md 同目錄下的 `scripts/email_ops.py`。
用此 SKILL.md 所在目錄拼出絕對路徑，確認檔案存在。

### Step 3：建立 .env.email

檢查 `scripts/` 目錄下是否有 `.env.email`（email_ops.py 讀的是同目錄下的 .env.email）。

如果不存在，引導使用者：

```
需要先設定你的 email 帳號：

1. 複製模板：
   cp {此skill目錄}/assets/env.email.template {此skill目錄}/scripts/.env.email

2. 用文字編輯器（VS Code、記事本等）打開 scripts/.env.email，填入：
   - work_PROVIDER：填 gmail 或 outlook
   - work_USER：你的 email 地址
   - work_PASSWORD：你的 App Password

   App Password 不是登入密碼，取得方式見 .env.email 裡的說明。

3. 儲存後告訴我「設定好了」。
```

**安全規則：不要讓使用者在對話中輸入密碼。引導他們自己用文字編輯器填寫。不要用 Read 工具讀取 .env.email。**

### Step 4：測試連線

```bash
{python} {email_ops_path} status
```

確認回傳 `"status": "ok"`。
如果失敗，讀取 `references/test-commands.md` 的常見錯誤段落協助排除。

### Step 5：確認草稿匣

```bash
{python} {email_ops_path} list_folders {account}
```

確認能找到草稿匣資料夾。email_ops.py 有自動偵測功能（支援 Gmail 中文介面）。
如果仍然有問題，引導使用者在 `scripts/.env.email` 加上 `work_DRAFTS_FOLDER=正確名稱`。

### Step 6：產出 env.md

在此 SKILL.md 同目錄下建立 `env.md`：

```
python: {確認過的 python 指令}
email_ops: {email_ops.py 的絕對路徑}
account: {帳號名稱}
```

完成後告訴使用者：「Email 設定完成。以後說『幫我看這封信』就能開始。」

---

## 工具指令

讀取 `env.md` 取得 python、email_ops、account 的值。

執行格式：
```bash
{python} {email_ops} <command> [args]
```

### 指令速查

| 指令 | 用途 |
|------|------|
| `status` | 查看各帳號未讀數 |
| `check {account} [limit]` | 列出未讀信件 |
| `read {account} <id>` | 讀一封信的完整內容 |
| `search {account} <query> [limit]` | 搜尋信件（支援中文） |
| `draft {account} <to> <subject> <body> [cc] [--html] [--attach file]` | 產草稿 |
| `reply {account} <id> <body> [--all] [--html] [--attach file]` | 回覆 |
| `mark_read {account} <id> [id...]` | 標記已讀 |
| `list_folders {account}` | 列出所有信箱資料夾 |

## 安全規則

- **草稿優先**：所有信件先存草稿匣，不自動寄出（email_ops.py 沒有 send 指令）
- **人工確認**：產完草稿後告訴使用者去草稿匣確認，不要說「已寄出」
- **不刪信**：只標記已讀，不刪除（email_ops.py 沒有 delete 指令）
- **不洩漏**：不讀取、不顯示 .env.email 內容

## 工作流程

### 回信（任何信件）

使用者說「幫我看這封信」或貼了信件內容時：

1. 讀信：用 `read` 或直接讀使用者貼的內容
2. 摘要：告訴使用者這封信在說什麼（重點、對方要什麼、截止日）
3. 討論：問使用者想怎麼回（哪些答應、哪些拒絕、語氣偏好）
4. 出草稿：根據討論寫完整回覆信
5. 微調：使用者提修改意見 → 修改 → 直到滿意
6. 存草稿：用 `draft` 或 `reply` 存到草稿匣
7. 告知：「草稿已存到草稿匣，請確認後寄出。」

### 批次（重複信件）

使用者有大量結構相同的信件時：

1. 確認模板：信件格式、必填欄位
2. 確認資料來源：使用者提供資料表或口述
3. 產第一封：先做一封讓使用者確認
4. 批次產出：確認後逐封存草稿匣
5. 回報：產了幾封、收件人各是誰

### 查信

使用者問「有沒有某人寄來的信」時：

1. 用 `search` 搜尋
2. 列出結果（寄件人、主旨、日期）
3. 使用者選一封 → 用 `read` 讀取

## 信件風格指南

使用者可以請你在此段落加入：語氣偏好、簽名檔、常用信件模板。
