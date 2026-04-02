#!/usr/bin/env python3
"""
Email operations for Claude Code — Gmail & Outlook unified.
Reads account config from .env.email in the same directory as this script.

Supported providers: Gmail, Google Workspace, Outlook, Microsoft 365.
All operations use standard IMAP protocol.
"""

import imaplib
import email
import re
import sys
import os
import json
import mimetypes
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate, parseaddr, getaddresses

# --- Configuration ---

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.environ.get("EMAIL_ENV_FILE", os.path.join(SCRIPT_DIR, ".env.email"))
TEMPLATE_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "templates")

# Provider presets
PROVIDERS = {
  "gmail": {
    "host": "imap.gmail.com",
    "port": 993,
    "drafts_folder": "[Gmail]/Drafts",
  },
  "outlook": {
    "host": "outlook.office365.com",
    "port": 993,
    "drafts_folder": "Drafts",
  },
}


def load_env():
  """Load key=value pairs from .env.email file."""
  env = {}
  if not os.path.exists(ENV_FILE):
    print(json.dumps({"error": f".env.email not found at {ENV_FILE}"}))
    sys.exit(1)
  with open(ENV_FILE) as f:
    for line in f:
      line = line.strip()
      if "=" in line and not line.startswith("#"):
        key, val = line.split("=", 1)
        env[key.strip()] = val.strip()
  return env


def get_accounts():
  """Build account registry from .env.email.

  Expected format in .env.email:
    ACCOUNTS=work,personal       (comma-separated account names)
    work_PROVIDER=gmail          (gmail or outlook)
    work_USER=you@gmail.com
    work_PASSWORD=xxxx-xxxx-xxxx-xxxx
    personal_PROVIDER=outlook
    personal_USER=you@company.com
    personal_PASSWORD=xxxx
  """
  env = load_env()
  account_names = [a.strip() for a in env.get("ACCOUNTS", "default").split(",")]
  accounts = {}
  for name in account_names:
    provider_key = env.get(f"{name}_PROVIDER", "gmail").lower()
    provider = PROVIDERS.get(provider_key)
    if not provider:
      print(json.dumps({"error": f"Unknown provider '{provider_key}' for account '{name}'"}))
      sys.exit(1)
    user = env.get(f"{name}_USER", "")
    password = env.get(f"{name}_PASSWORD", "")
    if not user or not password:
      print(json.dumps({"error": f"Missing USER or PASSWORD for account '{name}'"}))
      sys.exit(1)
    # Allow per-account override of drafts folder
    drafts = env.get(f"{name}_DRAFTS_FOLDER", provider["drafts_folder"])
    port = int(env.get(f"{name}_PORT", provider["port"]))
    # Security: explicit override or auto-detect from port
    security = env.get(f"{name}_SECURITY", "").lower()
    if not security:
      security = "ssl" if port == 993 else "starttls"
    accounts[name] = {
      "host": env.get(f"{name}_HOST", provider["host"]),
      "port": port,
      "security": security,
      "user": user,
      "password": password,
      "drafts_folder": drafts,
    }
  return accounts


def connect(account_name):
  """Connect and login to IMAP server. Returns (connection, drafts_folder, user)."""
  accounts = get_accounts()
  if account_name not in accounts:
    available = ", ".join(accounts.keys())
    print(json.dumps({"error": f"Account '{account_name}' not found. Available: {available}"}))
    sys.exit(1)
  acct = accounts[account_name]
  security = acct.get("security", "ssl")
  if security == "none":
    print(json.dumps({"warning": "IMAP connection uses plain text (no encryption). Credentials sent unencrypted."}), file=sys.stderr)
  if security == "ssl":
    try:
      m = imaplib.IMAP4_SSL(acct["host"], acct["port"], timeout=30)
    except TypeError:
      # Python < 3.9: timeout not supported
      m = imaplib.IMAP4_SSL(acct["host"], acct["port"])
      m.socket().settimeout(30)
  else:
    try:
      m = imaplib.IMAP4(acct["host"], acct["port"], timeout=30)
    except TypeError:
      # Python < 3.9: timeout not supported
      m = imaplib.IMAP4(acct["host"], acct["port"])
      m.socket().settimeout(30)
    if security == "starttls":
      m.starttls()
  m.login(acct["user"], acct["password"])
  return m, acct["drafts_folder"], acct["user"]


def detect_drafts_folder(m, configured_folder):
  """Try configured drafts folder, fallback to common alternatives.
  Gmail Chinese UI uses UTF-7 encoded folder names.
  Returns the working drafts folder name."""
  # Common drafts folder names across providers and languages
  candidates = [
    configured_folder,
    "[Gmail]/Drafts",
    "[Gmail]/&g0l6Pw-",       # Gmail Chinese UI (UTF-7 encoded)
    "Drafts",
    "&g0l6Pw-",               # Outlook Chinese
    "INBOX.Drafts",
  ]
  # Deduplicate while preserving order
  seen = set()
  unique = []
  for c in candidates:
    if c not in seen:
      seen.add(c)
      unique.append(c)
  for folder in unique:
    try:
      status, _ = m.select(folder)
      if status == "OK":
        m.select("INBOX")  # Reset selection
        return folder
    except Exception:
      continue
  print(json.dumps({"warning": f"No drafts folder found. Tried: {unique}. Falling back to '{configured_folder}'."}), file=sys.stderr)
  return configured_folder  # Fallback to configured


# --- Helpers ---

def decode_subject(raw_subject):
  """Decode email subject header to string."""
  if not raw_subject:
    return "(no subject)"
  parts = decode_header(raw_subject)
  decoded = []
  for part, charset in parts:
    if isinstance(part, bytes):
      decoded.append(part.decode(charset or "utf-8", errors="replace"))
    else:
      decoded.append(part)
  return "".join(decoded)


def decode_addr(raw_header):
  """Decode a MIME-encoded address header to readable string."""
  if not raw_header:
    return ""
  parts = decode_header(raw_header)
  decoded = []
  for part, charset in parts:
    if isinstance(part, bytes):
      decoded.append(part.decode(charset or "utf-8", errors="replace"))
    else:
      decoded.append(part)
  return "".join(decoded)


def attach_files(msg, file_paths):
  """Attach files to a MIMEMultipart message."""
  for fpath in file_paths:
    if not os.path.exists(fpath):
      print(json.dumps({"warning": f"File not found: {fpath}"}), file=sys.stderr)
      continue
    mime_type, _ = mimetypes.guess_type(fpath)
    if mime_type is None:
      mime_type = "application/octet-stream"
    main_type, sub_type = mime_type.split("/", 1)
    with open(fpath, "rb") as f:
      part = MIMEBase(main_type, sub_type)
      part.set_payload(f.read())
    encoders.encode_base64(part)
    filename = os.path.basename(fpath)
    part.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(part)


def parse_attach_args(argv):
  """Parse --attach flags from argv. Returns (clean_argv, file_list)."""
  files = []
  clean = []
  i = 0
  while i < len(argv):
    if argv[i] == "--attach" and i + 1 < len(argv):
      i += 1
      files.append(argv[i])
    else:
      clean.append(argv[i])
    i += 1
  return clean, files


def sanitize_html(html_body):
  """Replace email-unsafe HTML tags to prevent mobile rendering issues.
  iOS Mail renders <blockquote> as indented blocks with colored bars."""
  html_body = re.sub(
    r'<blockquote[^>]*>',
    '<div style="margin:0;padding:0;">',
    html_body,
    flags=re.IGNORECASE,
  )
  html_body = re.sub(
    r'</blockquote>',
    '</div>',
    html_body,
    flags=re.IGNORECASE,
  )
  return html_body


def load_theme():
  """Load HTML email theme template."""
  theme_path = os.path.join(TEMPLATE_DIR, "default.html")
  if os.path.exists(theme_path):
    with open(theme_path) as f:
      return f.read()
  return None


def apply_theme(body_html):
  """Wrap body HTML in theme template. Returns full HTML."""
  template = load_theme()
  if template and "{{BODY}}" in template:
    return template.replace("{{BODY}}", body_html)
  return body_html


# --- Commands ---

def cmd_status(accounts=None):
  """Print unread count for each account. JSON output."""
  all_accounts = get_accounts()
  targets = accounts or list(all_accounts.keys())
  results = {}
  for name in targets:
    m = None
    try:
      m, _, _ = connect(name)
      m.select("INBOX")
      _, data = m.search(None, "UNSEEN")
      count = len(data[0].split()) if data[0] else 0
      results[name] = {"unread": count, "status": "ok"}
    except Exception as e:
      results[name] = {"unread": -1, "status": str(e)}
    finally:
      if m:
        try:
          m.logout()
        except Exception:
          pass
  print(json.dumps(results, indent=2))


def cmd_check(account_name, limit=10, mailbox="INBOX"):
  """List unread emails for an account. JSON output."""
  m, _, _ = connect(account_name)
  try:
    m.select(mailbox)
    _, data = m.search(None, "UNSEEN")
    ids = data[0].split() if data[0] else []
    results = []
    for uid in ids[-limit:]:
      _, msg_data = m.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
      if msg_data and isinstance(msg_data[0], tuple):
        header = email.message_from_bytes(msg_data[0][1])
        results.append({
          "id": uid.decode(),
          "from": decode_addr(header.get("From", "")),
          "subject": decode_subject(header.get("Subject")),
          "date": header.get("Date", ""),
        })
    print(json.dumps(results, indent=2, ensure_ascii=False))
  finally:
    try:
      m.logout()
    except Exception:
      pass


def cmd_read(account_name, msg_id, mailbox="INBOX"):
  """Read full email content. JSON output."""
  m, _, _ = connect(account_name)
  try:
    m.select(mailbox)
    _, msg_data = m.fetch(msg_id.encode(), "(BODY.PEEK[])")
    if not msg_data or not isinstance(msg_data[0], tuple):
      print(json.dumps({"error": "Message not found"}))
      return
    msg = email.message_from_bytes(msg_data[0][1])

    # Extract body (prefer plain text, fallback to HTML)
    body = ""
    html_body = ""
    attachments = []
    if msg.is_multipart():
      for part in msg.walk():
        ct = part.get_content_type()
        cd = str(part.get("Content-Disposition", ""))
        if "attachment" in cd:
          filename = part.get_filename()
          if filename:
            attachments.append(decode_subject(filename))
          continue
        if ct == "text/plain" and not body:
          payload = part.get_payload(decode=True)
          if payload:
            charset = part.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
        elif ct == "text/html" and not html_body:
          payload = part.get_payload(decode=True)
          if payload:
            charset = part.get_content_charset() or "utf-8"
            html_body = payload.decode(charset, errors="replace")
    else:
      payload = msg.get_payload(decode=True)
      if payload:
        charset = msg.get_content_charset() or "utf-8"
        body = payload.decode(charset, errors="replace")

    # Use HTML body if no plain text available
    if not body and html_body:
      body = html_body

    result = {
      "id": msg_id,
      "from": decode_addr(msg.get("From", "")),
      "to": decode_addr(msg.get("To", "")),
      "cc": decode_addr(msg.get("Cc", "")),
      "subject": decode_subject(msg.get("Subject")),
      "date": msg.get("Date", ""),
      "message_id": msg.get("Message-ID", ""),
      "body": body,
    }
    if attachments:
      result["attachments"] = attachments
    print(json.dumps(result, indent=2, ensure_ascii=False))
  finally:
    try:
      m.logout()
    except Exception:
      pass


def cmd_list_folders(account_name):
  """List all IMAP folders for an account. Useful for finding the correct drafts folder name."""
  m, _, _ = connect(account_name)
  try:
    status, folders = m.list()
    results = []
    if status == "OK":
      for f in folders:
        # Parse IMAP LIST response: (flags) "delimiter" "name"
        decoded = f.decode("utf-8", errors="replace")
        # Extract folder name — match any single-char delimiter
        match = re.match(r'\(.*?\)\s+"(.)"\s+(.*)', decoded)
        if match:
          name = match.group(2).strip('"')
          results.append(name)
        else:
          results.append(decoded)
    print(json.dumps({"account": account_name, "folders": results}, indent=2, ensure_ascii=False))
  finally:
    try:
      m.logout()
    except Exception:
      pass


def cmd_draft(account_name, to_addr, subject, body, cc=None, html=False, theme=False, attachments=None):
  """Create a draft email in the Drafts folder."""
  m, drafts_folder, user = connect(account_name)
  try:
    drafts_folder = detect_drafts_folder(m, drafts_folder)

    if html:
      body = sanitize_html(body)
      if theme:
        body = apply_theme(body)

    has_attachments = attachments and len(attachments) > 0
    needs_multipart = has_attachments or (html and theme)

    if needs_multipart:
      msg = MIMEMultipart("mixed")
      content_type = "html" if html else "plain"
      msg.attach(MIMEText(body, content_type, "utf-8"))
      if has_attachments:
        attach_files(msg, attachments)
    else:
      content_type = "html" if html else "plain"
      msg = MIMEText(body, content_type, "utf-8")

    msg["From"] = user
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    if cc:
      msg["Cc"] = cc

    status, result = m.append(drafts_folder, "\\Draft", None, msg.as_bytes())
    output = {"status": status, "folder": drafts_folder, "account": account_name}
    if has_attachments:
      output["attachments"] = [os.path.basename(f) for f in attachments]
    print(json.dumps(output))
  finally:
    try:
      m.logout()
    except Exception:
      pass


def cmd_reply(account_name, msg_id, body, reply_all=False, html=False, theme=False, attachments=None, mailbox="INBOX"):
  """Create a reply draft with proper threading headers."""
  m, drafts_folder, user = connect(account_name)
  try:
    drafts_folder = detect_drafts_folder(m, drafts_folder)

    m.select(mailbox)
    _, msg_data = m.fetch(msg_id.encode(), "(BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT MESSAGE-ID REFERENCES)])")
    if not msg_data or not isinstance(msg_data[0], tuple):
      print(json.dumps({"error": "Original message not found"}))
      return

    orig = email.message_from_bytes(msg_data[0][1])
    orig_from = orig.get("From", "")
    orig_to = orig.get("To", "")
    orig_cc = orig.get("Cc", "")
    orig_subject = decode_subject(orig.get("Subject"))
    orig_msg_id = orig.get("Message-ID", "")
    orig_refs = orig.get("References", "")

    reply_subject = orig_subject if orig_subject.startswith("Re:") else f"Re: {orig_subject}"
    _, reply_to_addr = parseaddr(orig_from)

    cc_addrs = ""
    if reply_all:
      all_addrs = []
      for header_val in [orig_to, orig_cc]:
        if header_val:
          all_addrs.append(decode_addr(header_val))
      combined = ", ".join(all_addrs)
      parsed = getaddresses([combined])
      filtered = [
        f"{name} <{addr}>" if name else addr
        for name, addr in parsed
        if addr.lower() != user.lower() and addr.lower() != reply_to_addr.lower()
      ]
      cc_addrs = ", ".join(filtered) if filtered else ""

    references = f"{orig_refs} {orig_msg_id}".strip() if orig_refs else orig_msg_id

    if html:
      body = sanitize_html(body)
      if theme:
        body = apply_theme(body)

    has_attachments = attachments and len(attachments) > 0
    needs_multipart = has_attachments or (html and theme)

    if needs_multipart:
      msg = MIMEMultipart()
      content_type = "html" if html else "plain"
      msg.attach(MIMEText(body, content_type, "utf-8"))
      if has_attachments:
        attach_files(msg, attachments)
    else:
      content_type = "html" if html else "plain"
      msg = MIMEText(body, content_type, "utf-8")

    msg["From"] = user
    msg["To"] = reply_to_addr
    msg["Subject"] = reply_subject
    msg["Date"] = formatdate(localtime=True)
    if cc_addrs:
      msg["Cc"] = cc_addrs
    if orig_msg_id:
      msg["In-Reply-To"] = orig_msg_id
    if references:
      msg["References"] = references

    status, result = m.append(drafts_folder, "\\Draft", None, msg.as_bytes())
    output = {
      "status": status,
      "folder": drafts_folder,
      "account": account_name,
      "to": reply_to_addr,
      "cc": cc_addrs,
      "subject": reply_subject,
    }
    if has_attachments:
      output["attachments"] = [os.path.basename(f) for f in attachments]
    print(json.dumps(output, ensure_ascii=False))
  finally:
    try:
      m.logout()
    except Exception:
      pass


def cmd_mark_read(account_name, msg_ids, mailbox="INBOX"):
  """Mark messages as read."""
  m, _, _ = connect(account_name)
  try:
    m.select(mailbox)
    for uid in msg_ids:
      m.store(uid.encode(), "+FLAGS", "\\Seen")
    print(json.dumps({"marked_read": len(msg_ids), "account": account_name}))
  finally:
    try:
      m.logout()
    except Exception:
      pass


def cmd_search(account_name, query, limit=10, mailbox="INBOX"):
  """Search emails by subject or from. Supports non-ASCII via client-side filter."""
  m, _, _ = connect(account_name)
  try:
    m.select(mailbox, readonly=True)

    is_ascii = True
    try:
      query.encode("ascii")
    except UnicodeEncodeError:
      is_ascii = False

    if is_ascii:
      safe_query = query.replace('\\', '\\\\').replace('"', '\\"')
      _, data = m.search(None, f'(SUBJECT "{safe_query}")')
      ids = data[0].split() if data[0] else []
      if not ids:
        _, data = m.search(None, f'(FROM "{safe_query}")')
        ids = data[0].split() if data[0] else []
    else:
      scan_count = max(limit * 20, 200)
      _, data = m.search(None, "ALL")
      all_ids = data[0].split() if data[0] else []
      candidate_ids = all_ids[-scan_count:]
      ids = []
      for uid in candidate_ids:
        _, msg_data = m.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
        if msg_data and isinstance(msg_data[0], tuple):
          header = email.message_from_bytes(msg_data[0][1])
          subj = decode_subject(header.get("Subject"))
          from_decoded = decode_addr(header.get("From", ""))
          if query in subj or query in from_decoded:
            ids.append(uid)
        if len(ids) >= limit:
          break

    results = []
    for uid in ids[-limit:]:
      _, msg_data = m.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
      if msg_data and isinstance(msg_data[0], tuple):
        header = email.message_from_bytes(msg_data[0][1])
        results.append({
          "id": uid.decode(),
          "from": decode_addr(header.get("From", "")),
          "subject": decode_subject(header.get("Subject")),
          "date": header.get("Date", ""),
        })
    print(json.dumps(results, indent=2, ensure_ascii=False))
  finally:
    try:
      m.logout()
    except Exception:
      pass


# --- CLI ---

def safe_int(value, default):
  """Parse int from string, return default on failure."""
  try:
    return int(value)
  except (ValueError, TypeError):
    return default


def cli_error(msg):
  """Print JSON error and exit."""
  print(json.dumps({"error": msg}))
  sys.exit(1)


if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("Usage: email_ops.py <command> [args]")
    print("Commands: status, check, read, draft, reply, mark_read, search, list_folders")
    print("Config: .env.email in same directory (or set EMAIL_ENV_FILE)")
    sys.exit(1)

  cmd = sys.argv[1]

  if cmd == "status":
    accounts = sys.argv[2:] if len(sys.argv) > 2 else None
    cmd_status(accounts)

  elif cmd == "check":
    account = sys.argv[2] if len(sys.argv) > 2 else "default"
    limit = safe_int(sys.argv[3] if len(sys.argv) > 3 else None, 10)
    cmd_check(account, limit)

  elif cmd == "read":
    if len(sys.argv) < 4:
      cli_error("Usage: read <account> <msg_id>")
    account = sys.argv[2]
    msg_id = sys.argv[3]
    cmd_read(account, msg_id)

  elif cmd == "draft":
    is_html = "--html" in sys.argv
    is_theme = "--theme" in sys.argv
    raw_args = [a for a in sys.argv[2:] if a not in ("--html", "--theme")]
    clean_args, attach_list = parse_attach_args(raw_args)
    if len(clean_args) < 4:
      cli_error("Usage: draft <account> <to> <subject> <body> [cc] [--html] [--theme] [--attach file]")
    account = clean_args[0]
    to_addr = clean_args[1]
    subject = clean_args[2]
    body = clean_args[3]
    cc = clean_args[4] if len(clean_args) > 4 else None
    cmd_draft(account, to_addr, subject, body, cc, html=is_html, theme=is_theme,
              attachments=attach_list if attach_list else None)

  elif cmd == "reply":
    is_all = "--all" in sys.argv
    is_html = "--html" in sys.argv
    is_theme = "--theme" in sys.argv
    raw_args = [a for a in sys.argv[2:] if a not in ("--all", "--html", "--theme")]
    clean_args, attach_list = parse_attach_args(raw_args)
    if len(clean_args) < 3:
      cli_error("Usage: reply <account> <msg_id> <body> [--all] [--html] [--theme] [--attach file]")
    account = clean_args[0]
    msg_id = clean_args[1]
    body = clean_args[2]
    cmd_reply(account, msg_id, body, reply_all=is_all, html=is_html, theme=is_theme,
              attachments=attach_list if attach_list else None)

  elif cmd == "mark_read":
    if len(sys.argv) < 4:
      cli_error("Usage: mark_read <account> <msg_id> [msg_id...]")
    account = sys.argv[2]
    msg_ids = sys.argv[3:]
    cmd_mark_read(account, msg_ids)

  elif cmd == "search":
    account = sys.argv[2] if len(sys.argv) > 2 else "default"
    query = sys.argv[3] if len(sys.argv) > 3 else ""
    limit = safe_int(sys.argv[4] if len(sys.argv) > 4 else None, 10)
    cmd_search(account, query, limit)

  elif cmd == "list_folders":
    account = sys.argv[2] if len(sys.argv) > 2 else "default"
    cmd_list_folders(account)

  else:
    cli_error(f"Unknown command: {cmd}")
