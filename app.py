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
orders_history = {}   # {sender_id: [order1, order2, ...]}
MAX_HISTORY = 10

SYSTEM_PROMPT = """Ban la nhan vien tu van ban hang than thien cua {shop}.
Su dung danh sach san pham duoi day de tra loi khach hang.

=== DANH SACH SAN PHAM ===
{products}
=== HET DANH SACH ===

Huong dan chung:
- Tra loi ngan gon, than thien, bang tieng Viet
- Cung cap day du thong tin size, mau, gia khi khach hoi san pham
- Neu co gia sale: luon de cap ca gia goc va gia sale
- Neu khong co thong tin: noi "De minh hoi lai shop nhe!"
- Neu khach can tu van phuc tap (doi tra, khieu nai): ket thuc tin nhan bang [CHUYEN_NHAN_VIEN]

Quy trinh dat hang (khi khach muon mua / chot don):
1. Thu thap lan luot cac thong tin con thieu (khong hoi nhieu truong mot luc):
   - Ten khach hang
   - So dien thoai
   - San pham, size, mau sac, so luong
   - Ngay can giao (neu co)
   - Dia chi nhan hang
2. Khi da co DU TAT CA thong tin tren, xac nhan lai voi khach mot lan.
3. Sau khi khach xac nhan, CHUYEN SANG DONG CUOI cua tin nhan them the sau (khong de lo ra ngoai):
   [DAT_HANG:{{"ten":"<ten>","sdt":"<sdt>","facebook":"","san_pham":"<sp>","size":"<size>","mau":"<mau>","so_luong":"<sl>","ngay_can":"<ngay>","dia_chi":"<dc>"}}]
   Va noi voi khach: "Shop da nhan don cua ban! Minh se lien he xac nhan trong thoi gian som nhat nhe!"

Luu y quan trong:
- Chi them the [DAT_HANG:...] khi khach DA XAC NHAN don hang
- The [DAT_HANG:...] phai la JSON hop le, nam CUOI tin nhan
- Khong bao gio them [DAT_HANG:...] neu chua du thong tin
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
            model=CLAUDE_MODEL, max_tokens=600,
            system=SYSTEM_PROMPT.format(shop=SHOP_NAME, products=PRODUCTS_JSON),
            messages=history,
        )
        reply = response.content[0].text

        # --- Parse [DAT_HANG:...] ---
        order_data = None
        import re
        order_match = re.search(r'\[DAT_HANG:(\{.*?\})\]', reply, re.DOTALL)
        if order_match:
            try:
                order_data = json.loads(order_match.group(1))
            except Exception as e:
                print(f"Loi parse don hang JSON: {e}")
            reply = reply[:order_match.start()].strip()

        # --- Parse [CHUYEN_NHAN_VIEN] ---
        escalate = "[CHUYEN_NHAN_VIEN]" in reply
        reply_clean = reply.replace("[CHUYEN_NHAN_VIEN]", "").strip()
        if escalate:
            reply_clean += "\n\nMinh se chuyen ban qua nhan vien ho tro truc tiep ngay nhe!"

        history.append({"role": "assistant", "content": reply_clean})
        return reply_clean, escalate, order_data
    except Exception as e:
        print(f"Loi Claude API: {e}")
        return "Xin loi ban, he thong dang ban. Vui long nhan lai sau it phut!", False, None

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
        reply, escalated, order_data = get_claude_reply(sender_id, text)
        send_fb_message(sender_id, reply)
        sender_name = get_sender_name(sender_id)
        try:
            from sheet_logger import logger
            logger.log(sender_id=sender_id, question=text, answer=reply,
                      sender_name=sender_name, escalated=escalated)
        except Exception as e:
            print(f"Loi ghi log: {e}")
        # --- Xu ly don hang moi ---
        if order_data:
            previous_orders = orders_history.get(sender_id, [])
            order_count = len(previous_orders) + 1
            print(f"[DON HANG MOI #{order_count}] sender={sender_id} ten={order_data.get('ten','?')}")
            # Luu vao lich su don hang
            orders_history.setdefault(sender_id, []).append(order_data)
            # Reset lich su hoi thoai ve trang thai sau khi chot don
            # Claude biet don cu da xong, san sang nhan don moi
            conversation_history[sender_id] = [{
                "role": "assistant",
                "content": f"Da ghi nhan don hang #{order_count} cua ban thanh cong! Ban can ho tro them gi khong?"
            }]
            try:
                from sheet_logger import logger as _logger
                _logger.log_order(sender_id=sender_id, order_data=order_data,
                                  sender_name=sender_name, order_count=order_count)
            except Exception as e:
                print(f"Loi ghi don hang: {e}")
            try:
                from email_report import send_order_notification
                threading.Thread(
                    target=send_order_notification,
                    args=(order_data, sender_id, sender_name, previous_orders),
                    daemon=True
                ).start()
            except Exception as e:
                print(f"Loi gui email don hang: {e}")
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
