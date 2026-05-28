import os, sys, smtplib, argparse
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic
from sheet_logger import logger

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SMTP_HOST         = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT         = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER         = os.getenv("SMTP_USER", "")
SMTP_PASSWORD     = os.getenv("SMTP_PASSWORD", "")
REPORT_EMAIL_TO   = os.getenv("REPORT_EMAIL_TO", "")
SHOP_NAME         = os.getenv("SHOP_NAME", "Shop thoi trang")

def summarize_with_claude(logs):
    if not logs:
        return "Hom nay chua co hoi thoai nao."
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    conversations_text = ""
    for i, row in enumerate(logs, 1):
        conversations_text += f"\n[{i}] {row.get('Thoi gian','')} | Khach: {row.get('Cau hoi','')} | Bot: {row.get('Bot tra loi','')[:100]} | Chuyen NV: {row.get('Chuyen nhan vien?','Khong')}\n"
    response = client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=500,
        messages=[{"role": "user", "content": f"Viet bao cao ngan gon (duoi 200 tu) tieng Viet ve {len(logs)} hoi thoai cua chatbot Facebook {SHOP_NAME}:\n{conversations_text}\nBao gom: tong hoi thoai, san pham duoc hoi nhieu, chat luong bot, goi y cai thien."}]
    )
    return response.content[0].text

def build_email_html(logs, summary, date_str):
    total = len(logs)
    escalated = sum(1 for r in logs if r.get("Chuyen nhan vien?") == "Co")
    rows_html = ""
    for row in logs[-20:]:
        rows_html += f"<tr><td style='padding:6px;border-bottom:1px solid #eee'>{row.get('Thoi gian','')}</td><td style='padding:6px;border-bottom:1px solid #eee'>{row.get('Cau hoi','')}</td><td style='padding:6px;border-bottom:1px solid #eee'>{str(row.get('Bot tra loi',''))[:100]}</td><td style='padding:6px;border-bottom:1px solid #eee;text-align:center'>{'Co' if row.get('Chuyen nhan vien?')=='Co' else 'Khong'}</td></tr>"
    return f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px">
<div style="background:#2196F3;color:white;padding:20px;border-radius:8px 8px 0 0"><h2 style="margin:0">Bao cao chatbot - {SHOP_NAME}</h2><p style="margin:4px 0 0;opacity:.85">Ngay {date_str}</p></div>
<div style="background:#f5f5f5;padding:16px;display:flex;gap:12px">
<div style="background:white;border-radius:8px;padding:16px;flex:1;text-align:center"><div style="font-size:28px;font-weight:bold;color:#2196F3">{total}</div><div style="color:#666;font-size:13px">Tong hoi thoai</div></div>
<div style="background:white;border-radius:8px;padding:16px;flex:1;text-align:center"><div style="font-size:28px;font-weight:bold;color:#e53e3e">{escalated}</div><div style="color:#666;font-size:13px">Can chuyen nhan vien</div></div>
<div style="background:white;border-radius:8px;padding:16px;flex:1;text-align:center"><div style="font-size:28px;font-weight:bold;color:#38a169">{total-escalated}</div><div style="color:#666;font-size:13px">Bot tu xu ly</div></div>
</div>
<div style="background:white;padding:20px;border-left:4px solid #2196F3;margin:16px 0;border-radius:4px"><h3 style="margin:0 0 10px;color:#2196F3">Phan tich tong hop</h3><p style="line-height:1.7;white-space:pre-line">{summary}</p></div>
<div style="background:white;padding:20px;border-radius:8px"><h3 style="margin:0 0 12px">Chi tiet hoi thoai</h3>
<table style="width:100%;border-collapse:collapse;font-size:13px"><thead><tr style="background:#f5f5f5"><th style="padding:8px;text-align:left">Thoi gian</th><th style="padding:8px;text-align:left">Cau hoi</th><th style="padding:8px;text-align:left">Bot tra loi</th><th style="padding:8px;text-align:center">Chuyen NV</th></tr></thead><tbody>{rows_html}</tbody></table></div>
<p style="color:#aaa;font-size:12px;text-align:center">Email tu dong - {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
</body></html>"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    date_str = datetime.now().strftime("%d/%m/%Y")
    logs = logger.get_today_logs()
    summary = summarize_with_claude(logs)
    if args.test:
        print(f"\nBAO CAO NGAY {date_str} - {SHOP_NAME}\n{'='*50}\n{summary}\n{'='*50}")
        return
    html = build_email_html(logs, summary, date_str)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{SHOP_NAME}] Bao cao chatbot {date_str} - {len(logs)} hoi thoai"
    msg["From"] = SMTP_USER
    msg["To"] = REPORT_EMAIL_TO
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo(); server.starttls(); server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, REPORT_EMAIL_TO, msg.as_string())
    print(f"Da gui bao cao toi {REPORT_EMAIL_TO}")

if __name__ == "__main__":
    main()
