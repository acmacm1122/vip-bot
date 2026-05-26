import telebot
import requests
from PIL import Image
from pyzbar.pyzbar import decode
import io
import os
import logging
from datetime import datetime

# ── Logging ─────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)
log = logging.getLogger(__name__)

# ── Config ──────────────────────────────
BOT_TOKEN      = "8933611445:AAHPmOqrC2Hg8FymDSgidP-KON90Kho8JqQ"
KBZPAY_NUMBER  = "09894396106"
ADMIN_ID       = 8060259093  # မင်းရဲ့ Telegram User ID ထည့်

PLANS = {
    1: {
        "name"     : "1 ကျပ် — Test Plan",
        "duration" : "1 ရက်",
        "link"     : "https://t.me/+example1link",
    },
    2: {
        "name"     : "2 ကျပ် — Test Plan",
        "duration" : "2 ရက်",
        "link"     : "https://t.me/+example2link",
    },
    3: {
        "name"     : "3 ကျပ် — Test Plan",
        "duration" : "3 ရက်",
        "link"     : "https://t.me/+example3link",
    },
}

BILLS_FILE = "used_bills.txt"
USERS_FILE = "users.txt"
# ────────────────────────────────────────


# ── Helpers ─────────────────────────────

def is_bill_used(bill_no: str) -> bool:
    if not os.path.exists(BILLS_FILE):
        return False
    with open(BILLS_FILE, "r") as f:
        return bill_no in f.read().splitlines()


def save_bill(bill_no: str, user_id: int, amount: int):
    with open(BILLS_FILE, "a") as f:
        f.write(f"{bill_no}\n")
    with open(USERS_FILE, "a") as f:
        f.write(
            f"{user_id} | {amount} ကျပ် | "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        )


def scan_qr(image_bytes: bytes) -> str | None:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # ကြည်လင်အောင် grayscale ပြောင်း
        img = img.convert("L")
        decoded = decode(img)
        for obj in decoded:
            url = obj.data.decode("utf-8")
            if "kbzpay.com" in url:
                log.info(f"QR URL တွေ့တယ်: {url}")
                return url
        return None
    except Exception as e:
        log.error(f"QR Scan Error: {e}")
        return None


def verify_kbzpay(url: str) -> dict | None:
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 10) "
                "AppleWebKit/537.36 Chrome/91.0 Safari/537.36"
            )
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator=" ")

        # Amount ရှာ
        amount = 0
        for word in text.split():
            clean = word.replace(",", "").replace("MMK", "").strip()
            if clean.isdigit():
                candidate = int(clean)
                if candidate > 0:
                    amount = candidate
                    break

        # Status ရှာ
        if "Success" in text:
            status = "Success"
        elif "Failed" in text or "Fail" in text:
            status = "Failed"
        else:
            status = "Unknown"

        # Bill No ရှာ
        bill_no = None
        for word in text.split():
            if len(word) > 8 and word.isalnum():
                bill_no = word
                break

        result = {
            "amount"  : amount,
            "status"  : status,
            "bill_no" : bill_no,
        }
        log.info(f"KBZPay Data: {result}")
        return result

    except Exception as e:
        log.error(f"KBZPay Verify Error: {e}")
        return None


def notify_admin(bot: telebot.TeleBot, msg: str):
    try:
        bot.send_message(ADMIN_ID, msg)
    except Exception as e:
        log.error(f"Admin notify Error: {e}")


# ── Bot Handlers ────────────────────────

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


@bot.message_handler(commands=["start"])
def cmd_start(msg):
    name = msg.from_user.first_name or "သူငယ်ချင်း"
    text = (
        f"👋 မင်္ဂလာပါ <b>{name}</b>!\n\n"
        f"🔐 VIP Group ဝင်ဖို့ KBZPay နဲ့ Pay လုပ်ပါ။\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 <b>Plan တွေ</b>\n\n"
    )
    for amount, plan in PLANS.items():
        text += (
            f"• <b>{plan['name']}</b>\n"
            f"  ⏳ {plan['duration']}\n\n"
        )
    text += (
        f"━━━━━━━━━━━━━━━\n"
        f"📱 <b>KBZPay Number</b>\n"
        f"<code>{KBZPAY_NUMBER}</code>\n\n"
        f"✅ Pay ပြီးရင် Slip Screenshot တင်ပါ။\n"
        f"⚠️ Slip တစ်ခုကို တစ်ကြိမ်သာ သုံးလို့ရတယ်။"
    )
    bot.send_message(msg.chat.id, text)


@bot.message_handler(commands=["plans"])
def cmd_plans(msg):
    cmd_start(msg)


@bot.message_handler(commands=["stats"])
def cmd_stats(msg):
    if msg.from_user.id != ADMIN_ID:
        bot.send_message(msg.chat.id, "❌ Admin သာ သုံးလို့ရတယ်။")
        return

    bills = 0
    users = 0

    if os.path.exists(BILLS_FILE):
        with open(BILLS_FILE) as f:
            bills = len(f.read().splitlines())

    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            users = len(f.read().splitlines())

    bot.send_message(
        msg.chat.id,
        f"📊 <b>Stats</b>\n\n"
        f"💳 Total Payments: <b>{bills}</b>\n"
        f"👥 Total Users: <b>{users}</b>"
    )


@bot.message_handler(content_types=["photo"])
def handle_slip(msg):
    user_id   = msg.from_user.id
    user_name = msg.from_user.first_name or "Unknown"

    processing = bot.send_message(
        msg.chat.id,
        "⏳ Slip စစ်ဆေးနေတယ်...\nခဏစောင့်ပါ။"
    )

    # ── Step 1: Image Download ───────────
    try:
        file_info   = bot.get_file(msg.photo[-1].file_id)
        image_bytes = bot.download_file(file_info.file_path)
    except Exception as e:
        log.error(f"Image download Error: {e}")
        bot.edit_message_text(
            "❌ Image download မအောင်မြင်ဘူး။ ထပ်စမ်းပါ။",
            msg.chat.id, processing.message_id
        )
        return

    # ── Step 2: QR Scan ──────────────────
    url = scan_qr(image_bytes)
    if not url:
        bot.edit_message_text(
            "❌ QR Code မတွေ့ဘူး။\n\n"
            "📌 သေချာတဲ့ Slip Screenshot တင်ပါ။\n"
            "💡 Screenshot မှာ QR Code ပါဖို့ လိုတယ်။",
            msg.chat.id, processing.message_id
        )
        return

    # ── Step 3: KBZPay Verify ────────────
    data = verify_kbzpay(url)
    if not data:
        bot.edit_message_text(
            "❌ KBZPay Server နဲ့ ချိတ်ဆက်မရဘူး။\n"
            "နည်းနည်းကြာပြီး ထပ်စမ်းပါ။",
            msg.chat.id, processing.message_id
        )
        return

    # ── Step 4: Status Check ─────────────
    if data["status"] != "Success":
        bot.edit_message_text(
            "❌ Payment မအောင်မြင်ဘူး။\n"
            "KBZPay မှာ စစ်ကြည့်ပြီး ထပ်စမ်းပါ။",
            msg.chat.id, processing.message_id
        )
        return

    # ── Step 5: Bill Reuse Check ─────────
    bill_no = data.get("bill_no")
    if bill_no and is_bill_used(bill_no):
        bot.edit_message_text(
            "❌ ဒီ Slip ကို အသုံးပြုပြီးသားဖြစ်တယ်။\n"
            "တစ်ကြိမ်သာ သုံးလို့ရတယ်။",
            msg.chat.id, processing.message_id
        )
        notify_admin(
            bot,
            f"⚠️ Slip Reuse ကြိုးစားတယ်!\n"
            f"👤 User: {user_name} ({user_id})\n"
            f"🧾 Bill: {bill_no}"
        )
        return

    # ── Step 6: Amount Check ─────────────
    amount = data.get("amount", 0)
    if amount not in PLANS:
        bot.edit_message_text(
            f"❌ Amount မမှန်ဘူး။\n\n"
            f"📤 ပို့ထားတဲ့ Amount: <b>{amount} ကျပ်</b>\n"
            f"✅ မှန်ကန်တဲ့ Amount: "
            f"<b>1, 2, သို့မဟုတ် 3 ကျပ်</b>\n\n"
            f"Plan တွေကြည့်ဖို့ /plans နှိပ်ပါ။",
            msg.chat.id, processing.message_id
        )
        return

    # ── Step 7: Save & Send Link ─────────
    if bill_no:
        save_bill(bill_no, user_id, amount)

    plan = PLANS[amount]
    bot.edit_message_text(
        f"✅ <b>Payment အောင်မြင်တယ်!</b>\n\n"
        f"📦 Plan: <b>{plan['name']}</b>\n"
        f"⏳ Duration: <b>{plan['duration']}</b>\n\n"
        f"🔗 VIP Group Link:\n"
        f"👉 {plan['link']}\n\n"
        f"⚠️ Link က တစ်ကြိမ်သာ သုံးလို့ရတယ်။\n"
        f"🙏 ကျေးဇူးတင်ပါတယ်!",
        msg.chat.id, processing.message_id
    )

    notify_admin(
        bot,
        f"💰 Payment အသစ် ရတယ်!\n"
        f"👤 User: {user_name} ({user_id})\n"
        f"💵 Amount: {amount} ကျပ်\n"
        f"📦 Plan: {plan['name']}\n"
        f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )

    log.info(
        f"Payment OK — User:{user_id} "
        f"Amount:{amount} Bill:{bill_no}"
    )


@bot.message_handler(func=lambda m: True)
def handle_unknown(msg):
    bot.send_message(
        msg.chat.id,
        "💡 Slip Screenshot တင်ပါ သို့မဟုတ် /start နှိပ်ပါ။"
    )


# ── Run ─────────────────────────────────
if __name__ == "__main__":
    log.info("Bot စတင်နေတယ်...")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
