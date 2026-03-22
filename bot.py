import os
from telebot import types
import gspread
from google.auth import service_account
from dotenv import load_dotenv

load_dotenv()

# --- 1. Google Sheets Setup ---
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Handle both local (file) and Render (env var) deployment
google_creds_env = os.getenv("GOOGLE_CREDS")
if google_creds_env:
    import json
    creds_info = json.loads(google_creds_env)
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
else:
    creds = service_account.Credentials.from_service_account_file(
        os.getenv("GOOGLE_CREDS_FILE", "conmaret-key.json"),
        scopes=SCOPES
    )
client = gspread.authorize(creds)
sheet = client.open("Conmaret Price List").sheet1

# --- 2. Telegram Bot Setup ---
TOKEN = os.getenv("TELEGRAM_TOKEN")  # Get from @BotFather
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # Get from @userinfobot

import telebot
bot = telebot.TeleBot(TOKEN)

# Rebar weights (kg per meter)
REBAR_WEIGHTS = {
    "8mm": 4.74,
    "10mm": 7.40,
    "12mm": 10.66,
    "14mm": 14.50,
    "16mm": 18.94,
    "20mm": 29.59
}

# Store order info temporarily
order_data = {}

def get_live_prices():
    """Fetch live prices from Google Sheet"""
    try:
        data = sheet.get_all_values()
        return {
            "local_rebar": float(data[0][1]),  # Cell B1
            "turk_rebar": float(data[1][1]),    # Cell B2
            "dangote": data[2][1],              # Cell B3
            "derba": data[3][1],                # Cell B4
            "g28_roof": data[4][1]              # Cell B5
        }
    except Exception as e:
        print(f"Error reading sheet: {e}")
        return None

# --- Start Command ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('📊 የዛመድ ዋጋ ዝርዝር')
    btn2 = types.KeyboardButton('🧮 ብረት ዋጋ አስላ')
    btn3 = types.KeyboardButton('📞 ያግኙን')
    markup.add(btn1, btn2, btn3)
    
    welcome_text = (
        f"ሰላም {message.from_user.first_name}!\n"
        "ወደ ኮንማረት (Conmaret) የግንባታ እቃዎች ዋጋ ማሳወቂያ ቦት በደህና መጡ።\n"
        "የዛመድን ገበያ ለማወቅ ከታች ያሉትን አማራጮች ይጠቀሙ።"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

# --- Show Prices ---
@bot.message_handler(func=lambda message: message.text == '📊 የዛመድ ዋጋ ዝርዝር')
def show_prices(message):
    prices = get_live_prices()
    if not prices:
        bot.send_message(message.chat.id, "ይቅርታ፣ መረጃውን ማንበብ አልተቻለም። እባክዎ ቆይተው ይሞክሩ።")
        return
    
    text = (
        "🏗️ **የዛመድ የግንባታ እቃዎች ዋጋ**\n\n"
        f"🧱 **ሲሚንቶ (በኩንታል)፦**\n"
        f"- ዳንጎቴ፡ {prices['dangote']} ብር\n"
        f"- ደርባ፡ {prices['derba']} ብር\n\n"
        f"🏠 **ቆርቆሮ (በቁራጭ)፦**\n"
        f"- G28 (0.32mm)፡ {prices['g28_roof']} ብር\n\n"
        "🏗️ **የአርማታ ብረት (በኪሎ)፦**\n"
        f"- ሀገር ውስጥ፡ {prices['local_rebar']} ብር\n"
        f"- ቱርክ፡ {prices['turk_rebar']} ብር\n\n"
        "💡 *ለማስላት 'ብረት ዋጋ አስላ' የሚለውን ይጫኑ።*"
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# --- Rebar Calculator ---
@bot.message_handler(func=lambda message: message.text == '🧮 ብረት ዋጋ አስላ')
def choose_size(message):
    markup = types.InlineKeyboardMarkup()
    for size in REBAR_WEIGHTS.keys():
        markup.add(types.InlineKeyboardButton(size, callback_data=f"calc_{size}"))
    bot.send_message(message.chat.id, "እባክዎ የብረቱን ውፍረት (Size) ይምረጡ፦", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('calc_'))
def ask_qty(call):
    size = call.data.split('_')[1]
    msg = bot.send_message(call.message.chat.id, f"ስንት ቤርጋ **{size}** ይፈልጋሉ? (ብዛቱን በቁጥር ብቻ ያስገቡ)")
    bot.register_next_step_handler(msg, perform_calculation, size)

def perform_calculation(message, size):
    try:
        qty = float(message.text)
        prices = get_live_prices()
        weight = REBAR_WEIGHTS[size]
        total_weight = round(qty * weight, 2)
        cost_local = round(total_weight * prices['local_rebar'], 2)
        cost_turk = round(total_weight * prices['turk_rebar'], 2)
        
        result_text = (
            f"🧮 **ለ {qty:,.0f} ቤርጋ {size} የተሰራ ስሌት፦**\n\n"
            f"⚖️ ጠቅላላ ክብደት: {total_weight:,} ኪ.ግ\n"
            f"🇪🇹 ሀገር ውስጥ: **{cost_local:,} ብር**\n"
            f"🇹🇷 የቱርክ ብረት: **{cost_turk:,} ብር**"
        )
        
        # Store order info for later
        order_data[message.chat.id] = result_text
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🛒 አሁን እዘዝ", callback_data="place_order"))
        bot.send_message(message.chat.id, result_text, parse_mode='Markdown', reply_markup=markup)
    except:
        bot.send_message(message.chat.id, "❌ ስህተት! እባክዎ ብዛቱን በቁጥር ብቻ ያስገቡ።")

# --- Place Order ---
@bot.callback_query_handler(func=lambda call: call.data == "place_order")
def get_order(call):
    msg = bot.send_message(call.message.chat.id, "ትዕዛዝዎን ለመመዝገብ እባክዎ **የስልክ ቁጥርዎን** ያስገቡ፦")
    bot.register_next_step_handler(msg, notify_admin)

def notify_admin(message):
    phone = message.text
    user = message.from_user
    order_info = order_data.get(message.chat.id, "No details")
    
    admin_msg = (
        f"🚨 **አዲስ ትዕዛዝ ደርሷል!**\n\n"
        f"👤 ስም፦ {user.first_name}\n"
        f"📞 ስልክ፦ {phone}\n"
        f"📝 ዝርዝር፦\n{order_info}"
    )
    bot.send_message(ADMIN_ID, admin_msg, parse_mode='Markdown')
    bot.send_message(message.chat.id, "✅ ትዕዛዝዎ ደርሶናል። በቅርቡ በስልክ እንገናኛለን። እናመሰግናለን!")

# --- Contact Us ---
@bot.message_handler(func=lambda message: message.text == '📞 ያግኙን')
def contact_us(message):
    contact_text = (
        "📍 **ኮንማረት (Conmaret)**\n"
        "አድራሻ፦ መርካቶ | ተክለኃይማኖት | ዊንጌት\n"
        "📞 ስልክ፦ [የእርስዎ ስልክ]\n"
        "🌐 ድረ-ገጽ፦ Conmaret.com"
    )
    bot.send_message(message.chat.id, contact_text, parse_mode='Markdown')

if __name__ == "__main__":
    bot.polling(none_stop=True)