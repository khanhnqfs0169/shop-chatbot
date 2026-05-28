import os, sys, argparse
from datetime import datetime
import anthropic
import resend
from sheet_logger import logger

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
RESEND_API_KEY    = os.getenv("RESEND_API_KEY", "")
REPORT_EMAIL_TO   = os.getenv("REPORT_EMAIL_TO", "")
SHOP_NAME         = os.getenv("SHOP_NAME", "Shop thoi trang")

resend.api_key = RESEND_API_KEY
EMAIL_FROM = "Shop Chatbot <onboarding@resend.dev>"

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

def send_order_notification(order_data, sender_id="", sender_name=""):
    """Gui email ngay lap tuc khi co don hang moi (dung Resend API)."""
    if not RESEND_API_KEY or not REPORT_EMAIL_TO:
        print("Chua cau hinh RESEND_API_KEY hoac REPORT_EMAIL_TO -> bo qua.")
        return
    now_str  = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    ten      = order_data.get("ten", sender_name or sender_id)
    sdt      = order_data.get("sdt", "Chua cung cap")
    facebook = order_data.get("facebook", "")
    san_pham = order_data.get("san_pham", "")
    size     = order_data.get("size", "")
    mau      = order_data.get("mau", "")
    so_luong = order_data.get("so_luong", "")
    ngay_can = order_data.get("ngay_can", "Khong co")
    dia_chi  = order_data.get("dia_chi", "")

    rows_html = ""
    fields = [
        ("Ten khach", ten), ("So dien thoai", sdt), ("Facebook / ID", facebook or sender_id),
        ("San pham", san_pham), ("Size", size), ("Mau", mau), ("So luong", so_luong),
        ("Ngay can", ngay_can), ("Dia chi giao hang", dia_chi),
    ]
    for label, val in fields:
        rows_html += f"<tr><td style='padding:8px 12px;background:#f9f9f9;font-weight:bold;border-bottom:1px solid #eee;width:40%'>{label}</td><td style='padding:8px 12px;border-bottom:1px solid #eee'>{val}</td></tr>"

    html = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
<div style="background:#e53935;color:white;padding:20px;border-radius:8px 8px 0 0">
  <h2 style="margin:0">Don hang moi - {SHOP_NAME}</h2>
  <p style="margin:4px 0 0;opacity:.9">{now_str}</p>
</div>
<div style="background:white;border:1px solid #eee;border-top:none;border-radius:0 0 8px 8px;overflow:hidden">
  <table style="width:100%;border-collapse:collapse;font-size:14px">{rows_html}</table>
</div>
<p style="color:#aaa;font-size:12px;text-align:center;margin-top:16px">Email tu dong tu chatbot Facebook - {SHOP_NAME}</p>
</body></html>"""

    try:
        params = {
            "from": EMAIL_FROM,
            "to": [REPORT_EMAIL_TO],
            "subject": f"[DON HANG MOI] {ten} - {san_pham} (x{so_luong}) - {SHOP_NAME}",
            "html": html,
        }
        resend.Emails.send(params)
        print(f"Da gui email don hang (Resend): {ten} - {san_pham}")
    except Exception as e:
        print(f"Loi gui email don hang: {e}")


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
    params = {
        "from": EMAIL_FROM,
        "to": [REPORT_EMAIL_TO],
        "subject": f"[{SHOP_NAME}] Bao cao chatbot {date_str} - {len(logs)} hoi thoai",
        "html": html,
    }
    resend.Emails.send(params)
    print(f"Da gui bao cao toi {REPORT_EMAIL_TO}")

if __name__ == "__main__":
    main()
