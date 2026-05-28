import os, json, threading, requests, openpyxl
from datetime import datetime
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import anthropic

load_dotenv()
app = Flask(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
VERIFY_TOKEN      = os.getenv("FB_VERIFY_TOKEN", "my_shop_verify_token_2024")
SHOP_NAME         = os.getenv("SHOP_NAME", "Shop thoi trang")
PRODUCTS_FILE     = os.getenv("PRODUCTS_FILE", "products.xlsx")
CLAUDE_MODEL      = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

def load_products():
    try:
        wb = openpyxl.load_workbook(PRODUCTS_FILE)
        ws = wb.active
        headers = [cell.value for cell in ws[1]]
        products = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if any(row):
                products.append({str(h): str(v) for h, v in zip(headers, row) if v is not None})
        wb.close()
        return json.dumps(products, ensure_ascii=False)
    except FileNotFoundError:
        print(f"Khong tim thay '{PRODUCTS_FILE}'. Chay 'python products_sample.py' truoc.")
        return "[]"

PRODUCTS_JSON = load_products()
print(f"Da load san pham tu: {PRODUCTS_FILE}")

def reload_products():
    import time
    while True:
        time.sleep(300)
        global PRODUCTS_JSON
        PRODUCTS_JSON = load_products()

threading.Thread(target=reload_products, daemon=True).start()

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
conversation_history = {}
MAX_HISTORY = 10

SYSTEM_PROMPT = """Ban la nhan vien tu van ban hang than thien cua {shop}.
Su dung danh sach san pham duoi day de tra loi khach hang.

=== DANH SACH SAN PHAM ===
{products}
=== HET DANH SACH ===

Huong dan:
- Tra loi ngan gon, than thien, bang tieng Viet
- Cung cap day du thong tin size, mau, gia khi khach hoi san pham
- Neu co gia sale: luon de cap ca gia goc va gia sale
- Neu khong co thong tin: noi "De minh hoi lai shop nhe!"
- Neu khach can tu van phuc tap (doi tra, khieu nai, dat so luong lon):
  ket thuc tin nhan bang [CHUYEN_NHAN_VIEN]
"""

def get_claude_reply(sender_id, user_message):
    if sender_id not in conversation_history:
        conversation_history[sender_id] = []
    history = conversation_history[sender_id]
    history.append({"role": "user", "content": user_message})
    if len(history) > MAX_HISTORY * 2:
        history = history[-MAX_HISTORY * 2:]
        conversation_history[sender_id] = history
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=400,
            system=SYSTEM_PROMPT.format(shop=SHOP_NAME, products=PRODUCTS_JSON),
            messages=history,
        )
        reply = response.content[0].text
        escalate = "[CHUYEN_NHAN_VIEN]" in reply
        reply_clean = reply.replace("[CHUYEN_NHAN_VIEN]", "").strip()
        if escalate:
            reply_clean += "\n\nMinh se chuyen ban qua nhan vien ho tro truc tiep ngay nhe!"
        history.append({"role": "assistant", "content": reply_clean})
        return reply_clean, escalate
    except Exception as e:
        print(f"Loi Claude API: {e}")
        return "Xin loi ban, he thong dang ban. Vui long nhan lai sau it phut!", False

def send_fb_message(recipient_id, text):
    try:
        resp = requests.post(
            "https://graph.facebook.com/v19.0/me/messages",
            json={"recipient": {"id": recipient_id}, "message": {"text": text}, "messaging_type": "RESPONSE"},
            params={"access_token": PAGE_ACCESS_TOKEN}, timeout=10
        )
        if resp.status_code != 200:
            print(f"Loi gui FB: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Loi ket noi Facebook: {e}")

def get_sender_name(sender_id):
    try:
        resp = requests.get(f"https://graph.facebook.com/v19.0/{sender_id}",
            params={"fields": "first_name,last_name", "access_token": PAGE_ACCESS_TOKEN}, timeout=5)
        d = resp.json()
        return f"{d.get('first_name','')} {d.get('last_name','')}".strip()
    except:
        return ""

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "running", "shop": SHOP_NAME, "model": CLAUDE_MODEL})

@app.route("/webhook", methods=["GET"])
def webhook_verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
        print("Webhook verified!")
        return request.args.get("hub.challenge"), 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def webhook_receive():
    data = request.json
    if data.get("object") != "page":
        return "OK", 200
    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_id = messaging.get("sender", {}).get("id", "")
            message = messaging.get("message", {})
            text = message.get("text", "").strip()
            if message.get("is_echo") or not text:
                continue
            print(f"[{sender_id}] {text[:80]}")
            threading.Thread(target=handle_message, args=(sender_id, text), daemon=True).start()
    return "EVENT_RECEIVED", 200

def handle_message(sender_id, text):
    try:
        reply, escalated = get_claude_reply(sender_id, text)
        send_fb_message(sender_id, reply)
        try:
            from sheet_logger import logger
            logger.log(sender_id=sender_id, question=text, answer=reply,
                      sender_name=get_sender_name(sender_id), escalated=escalated)
        except Exception as e:
            print(f"Loi ghi log: {e}")
    except Exception as e:
        print(f"Loi xu ly tin nhan [{sender_id}]: {e}")
        send_fb_message(sender_id, "Xin loi, he thong gap su co. Vui long thu lai!")

def schedule_daily_report():
    import time
    while True:
        now = datetime.now()
        if now.hour == 21 and now.minute == 0:
            try:
                from email_report import main as send_report
                send_report()
            except Exception as e:
                print(f"Loi gui bao cao: {e}")
            time.sleep(60)
        time.sleep(30)

threading.Thread(target=schedule_daily_report, daemon=True).start()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n{'='*45}\n  {SHOP_NAME} - Facebook Chatbot\n  Port: {port}\n{'='*45}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
