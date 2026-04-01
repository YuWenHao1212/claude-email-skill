# BP1: Email Workflow Automation

> Part of the [Enterprise AI Breakpoint Framework](https://github.com/YuWenHao1212?tab=repositories&q=bp&type=&language=&sort=) — 9 universal patterns for AI-powered enterprise workflows.

Let Claude read your emails, discuss replies with you, draft responses, and save them to your Drafts folder. You review and hit send.

**Gmail + Outlook supported. Mac + Windows supported.**

## Install

```bash
git clone https://github.com/YuWenHao1212/bp1-email.git
cd bp1-email
bash install.sh
```

This copies the email skill to `~/.claude/skills/email/` (global — works in any directory).

## Setup

After installing, open Claude Code (or Cowork) and say:

> "幫我設定 email"

Claude will guide you through:
1. Checking Python is installed
2. Setting up your email credentials (App Password)
3. Testing the connection
4. Confirming your Drafts folder

**You fill in your own password using a text editor. Claude never sees it.**

## After Setup

Just talk to Claude:

> "幫我看這封信在說什麼，然後我們討論怎麼回。"

> "幫我查有沒有 David 寄來的信。"

> "幫我批次產出這 10 封報價信的草稿。"

## What It Can Do

| Feature | Description |
|---------|-------------|
| Read & summarize | Extract key points from emails |
| Discuss & draft | Talk through your reply, Claude writes it |
| Refine | Adjust tone, add details, iterate |
| Reply with threading | Keeps the conversation thread intact |
| Attachments | Attach local files (PDF, Excel, etc.) |
| Batch templates | Same template × multiple recipients |
| Search | Find emails by subject or sender (supports CJK) |
| Gmail + Outlook | Standard IMAP, works with both |

## Security

| Rule | How it's enforced |
|------|-------------------|
| Never sends email | **Code-level** — `email_ops.py` has no `send` command |
| Never deletes email | **Code-level** — `email_ops.py` has no `delete` command |
| Draft-first | All output goes to your Drafts folder |
| Password protected | Claude guides you to edit credentials yourself, never reads them |

## Requirements

- Python 3.8+
- Claude Pro (Claude Code or Cowork)
- Gmail / Google Workspace / Outlook / Microsoft 365
- App Password ([Gmail](https://myaccount.google.com/apppasswords) · [Outlook](https://account.live.com/proofs/AppPassword))

## Enterprise AI Breakpoint Framework

This is **BP1 (Email)** — one of 9 universal patterns:

| BP | Pattern | Repo |
|----|---------|------|
| **1** | **Email Workflow** | **this repo** |
| 2 | Calendar & Meeting Setup | coming soon |
| 3 | Cross-source Data Consolidation | coming soon |
| 4 | Research → Copy → Visual | coming soon |
| 5 | Meeting Lifecycle | coming soon |
| 6 | Approval Tracking | coming soon |
| 7 | Document Comparison | coming soon |
| 8 | Recurring Reports | coming soon |
| 9 | Knowledge Base | coming soon |

## License

MIT
