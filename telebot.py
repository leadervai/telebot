from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get the Telegram bot token from environment variables
token = os.getenv("TELEGRAM_TOKEN")

# Initialize your bot with the token
from telegram import Bot

bot = Bot(token=token)

# Your existing bot code...

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, ConversationHandler, CommandHandler
import json
import logging
import re

# Logging setup
logging.basicConfig(level=logging.INFO)

# Custom prefix
PREFIX = "J"  # Can be changed as needed

# Constants
FILE_NAME = 'codes.json'
REMOVED_FILE_NAME = 'used.json'
TOTAL_DUE_FILE = 'total_due.json'

# States for the conversation
ASKING_FOR_CODES = range(1)

# ✅ Helper functions
def load_json(file_name, default_data=None):
    if os.path.exists(file_name):
        try:
            with open(file_name, 'r') as file:
                return json.load(file)
        except json.JSONDecodeError:
            logging.error(f"JSON file {file_name} is corrupted. Resetting.")
    return default_data if default_data else {"codes": []}

def save_json(data, file_name):
    try:
        with open(file_name, 'w') as file:
            json.dump(data, file, indent=4)
    except IOError as e:
        logging.error(f"Error saving {file_name}: {e}")

def parse_command(message):
    """ Extract command and arguments from a prefixed message """
    match = re.match(rf"^{PREFIX}(\w+)\s*(.*)", message, re.IGNORECASE)
    if match:
        command = match.group(1).lower()
        args = match.group(2).split() if match.group(2) else []
        return command, args
    return None, []

import re

def escape_markdown_v2(text):
    escape_chars = r'_*\[\]()~`>#+-=|{}.!'
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

# ✅ Telegram Command Handlers
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Handles prefixed commands """
    message = update.message.text.strip()
    command, args = parse_command(message)

    if not command:
        return

    if command == "start":
        await update.message.reply_text("Hello! I'm your UC bot. Use Jhelp to see available commands.")
    elif command == "help":
        help_text = """Available commands:
Jstart - Start the bot
Jhelp - Show this help message
Jbaki <amount> <count> - Retrieve UC codes
Jprice <amount> <price> - Set price for UC
Jstock - Show available stock
Jcheck - Check removed codes
Jrate - Show UC prices
Jclear - Clear all used codes and reset dues
Jup <amount> <code1> [<code2> ...] - Upload new codes
Jload <amount> - Load new codes for a specific amount"""
        await update.message.reply_text(help_text)
    elif command == "rate":
        await rate(update, context)
    elif command == "baki":
        await baki(update, context, args)
    elif command == "price":
        await price(update, context, args)
    elif command == "stock":
        await stock(update, context)
    elif command == "check":
        await check(update, context)
    elif command == "clear":
        await clear(update, context)
    elif command == "up":
        await upload_codes(update, context, args)
    elif command == "load":
        await load_codes_command(update, context, args)
    else:
        await update.message.reply_text(f"Unknown command: {command}")

async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_json(FILE_NAME)
    if not data['codes']:
        await update.message.reply_text("No pricing data available.")
        return

    sorted_codes = sorted(data['codes'], key=lambda group: group['amount'])
    result = ["💰 UC Pricing List:\n"]

    for group in sorted_codes:
        amount = group['amount']
        price = group.get('price', None)
        if price is not None:
            result.append(f"☞︎︎︎ {amount:<3} 🆄︎🅲︎  ➪ {price} \n")

    await update.message.reply_text("\n".join(result) if len(result) > 1 else "No pricing data available.")

# ✅ FIXED: Move this function OUTSIDE of `rate`
def get_codes(amount, count):
    """Retrieve a specified number of unused codes for the given amount."""
    data = load_json(FILE_NAME)
    used_data = load_json(REMOVED_FILE_NAME)

    # Find the group matching the requested amount
    group = next((item for item in data['codes'] if item['amount'] == amount), None)

    if not group:
        return None  # No such amount exists in stock

    # Get only non-redeemed codes
    available_codes = [code for code in group['codes'] if not code['redeemed']]

    if len(available_codes) < count:
        return None  # Not enough stock

    # Select the required number of codes
    selected_codes = available_codes[:count]

    # Mark codes as redeemed and remove from `codes.json`
    for code in selected_codes:
        group['codes'].remove(code)  # Remove from available codes
        code['redeemed'] = True  # Mark as used

    # Move used codes to `used.json`
    used_group = next((item for item in used_data['codes'] if item['amount'] == amount), None)

    if not used_group:
        # If no existing group, create new
        used_data['codes'].append({"amount": amount, "codes": selected_codes, "price": group.get("price", 0)})
    else:
        # Add to existing group
        used_group['codes'].extend(selected_codes)

    # Save changes to both files
    save_json(data, FILE_NAME)  # Update available stock
    save_json(used_data, REMOVED_FILE_NAME)  # Update used codes

    return amount, [code['code'] for code in selected_codes]

async def baki(update: Update, context: ContextTypes.DEFAULT_TYPE, args):
    """Retrieve UC codes and move them to used.json"""
    if len(args) < 1:
        await update.message.reply_text("Usage: Jbaki <amount> [count]\nExample: Jbaki 36 or Jbaki 36 2")
        return

    try:
        amount = int(args[0])
        count = int(args[1]) if len(args) > 1 else 1  # Default to 1 if count is not provided
    except ValueError:
        await update.message.reply_text("Invalid amount or count.")
        return

    result = get_codes(amount, count)

    if result:
        amount, codes = result
        codes_output = '\n'.join(codes)
        codes_output = escape_markdown_v2(codes_output)  # Escape special characters
        await update.message.reply_text(f"\n{codes_output}", parse_mode="MarkdownV2")
    else:
        await update.message.reply_text(f"⚠ {amount} UC Stock Out ⚠")

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE, args):
    """Update the price for a specific UC amount in both codes.json and used.json."""
    if len(args) < 2:
        await update.message.reply_text("Usage: Jprice <amount> <price>")
        return

    try:
        amount = int(args[0])
        price = float(args[1])
    except ValueError:
        await update.message.reply_text("Invalid amount or price.")
        return

    # Load both JSON files
    data = load_json(FILE_NAME)
    used_data = load_json(REMOVED_FILE_NAME)

    # Update price in `codes.json`
    group = next((item for item in data['codes'] if item['amount'] == amount), None)
    if group:
        group['price'] = price

    # Update price in `used.json`
    used_group = next((item for item in used_data['codes'] if item['amount'] == amount), None)
    if used_group:
        used_group['price'] = price  # Update price

    # Save changes
    save_json(data, FILE_NAME)
    save_json(used_data, REMOVED_FILE_NAME)

    await update.message.reply_text(f"✅ Price for {amount} UC updated to {price} in both stock & used records.")

async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_json(FILE_NAME)
    if not data['codes']:
        await update.message.reply_text("No codes available.")
        return

    total_price = 0  # Store the total price of available stock
    result = ["💰 Stock Available:\n"]

    for group in sorted(data['codes'], key=lambda group: group['amount']):
        amount = group['amount']
        price = group.get('price', 0)  # Use 0 if price is not set
        available_codes = len([c for c in group['codes'] if not c['redeemed']])
        stock_value = price * available_codes  # Calculate total worth for this UC group
        total_price += stock_value  # Add to total sum

        result.append(f"☞︎︎︎ {amount:<3} 🆄︎🅲︎  ➪ {available_codes} pcs \n")

    result.append("\n▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔")
    result.append(f"Wᴏʀᴛʜ Oғ : {total_price} ")

    await update.message.reply_text("\n".join(result))

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_json(REMOVED_FILE_NAME)
    if not data['codes']:
        await update.message.reply_text("No dues available, All clear ✅✅✅.")
        return

    total_used_price = 0  # Store the total price of used codes
    result = ["💰 Used Codes Summary:\n"]

    for group in sorted(data['codes'], key=lambda group: group['amount']):
        amount = group['amount']
        price = group.get('price', 0)  # Default price to 0 if not set
        used_codes_count = len(group['codes'])  # Number of used codes
        used_value = price * used_codes_count  # Calculate total value for this UC group
        total_used_price += used_value  # Add to total sum

        result.append(f"☞︎︎︎ {amount:<3} 🆄︎🅲︎  ➪ {used_codes_count} pcs \n")

    result.append("\n▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔")
    result.append(f"☞︎︎︎ Tᴏᴛᴀʟ Dᴜᴇ ➪ {total_used_price}")

    await update.message.reply_text("\n".join(result))

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_json({"codes": []}, REMOVED_FILE_NAME)
    await update.message.reply_text("Cleared all dues ✅ ✅.")

# Add codes grouped by amount
async def add_codes(update, amount, codes, file_name=FILE_NAME):
    data = load_json(file_name, {"codes": []})

    group = next((item for item in data['codes'] if item['amount'] == amount), None)
    if not group:
        group = {"amount": amount, "codes": [], "price": 0}
        data['codes'].append(group)

    existing_codes = {code['code'] for code in group['codes']}
    new_codes = []

    for code in codes:
        if code.strip() not in existing_codes:
            new_codes.append({"code": code.strip(), "redeemed": False})
            existing_codes.add(code.strip())
        else:
            warning_message = f"Duplicate code detected: ```{code.strip()}```"
            logging.warning(warning_message)
            await update.message.reply_text(warning_message)

    group['codes'].extend(new_codes)

    save_json(data, file_name)

    log_message = f"Added {len(new_codes)} codes for amount: {amount}"
    logging.info(log_message)
    await update.message.reply_text(log_message)

# Function to process the upload command
async def process_upload_command(update, command):
    parts = command.split(' ', 2)
    if len(parts) < 3:
        logging.error("Invalid command format. Use: .up <amount>uc <codes>")
        await update.message.reply_text("Invalid command format. Use: .up <amount>uc <codes>")
        return

    amount_code, codes = parts[1], parts[2]
    try:
        amount = int(amount_code[:-2])
    except ValueError:
        logging.error("Invalid amount format. Please provide a valid number before 'uc'.")
        await update.message.reply_text("Invalid amount format. Please provide a valid number before 'uc'.")
        return

    # Handle multi-line input by replacing newlines with spaces
    codes = codes.replace('\n', ' ')

    # Extract each code using a flexible pattern
    pattern = r'[a-zA-Z]{4}-[a-zA-Z]-S-\d{8} \d{4}-\d{4}-\d{4}-\d{4}'
    clean_codes = re.findall(pattern, codes)

    if not clean_codes:
        logging.error("No valid codes found.")
        await update.message.reply_text("No valid codes found.")
        return

    # Limit to 10 codes at a time
    clean_codes = clean_codes[:10]

    await add_codes(update, amount, clean_codes)

# Update the upload_codes command handler
async def upload_codes(update: Update, context: ContextTypes.DEFAULT_TYPE, args):
    """Upload new codes to the codes.json file."""
    if len(args) < 2:
        await update.message.reply_text("Usage: Jup <amount> <code1> [<code2> ...]\nExample: Jup 80 BDMB-K-S-00982283 1963-1773-2113-7118 BDMB-L-S-00422493 4516-7279-2257-5235")
        return

    amount = args[0]
    codes = args[1:]

    try:
        amount = int(amount)
    except ValueError:
        await update.message.reply_text("Invalid amount format. Please provide a valid number.")
        return

    await add_codes(update, amount, codes)

# New command handler for jload
async def load_codes_command(update: Update, context: ContextTypes.DEFAULT_TYPE, args):
    """Initiate the process to load new codes for a specific amount."""
    if len(args) < 1:
        await update.message.reply_text("Usage: Jload <amount>")
        return

    try:
        amount = int(args[0])
    except ValueError:
        await update.message.reply_text("Invalid amount format. Please provide a valid number.")
        return

    context.user_data['amount'] = amount
    await update.message.reply_text(f"Upload codes for {amount} UC:")
    return ASKING_FOR_CODES

# Handler to receive the codes
async def receive_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = context.user_data.get('amount')
    if not amount:
        await update.message.reply_text("No amount specified. Please use the Jload command first.")
        return ConversationHandler.END

    codes = update.message.text.strip()

    # Extract each code using a flexible pattern
    pattern = r'[a-zA-Z]{4}-[a-zA-Z]-S-\d{8} \d{4}-\d{4}-\d{4}-\d{4}'
    clean_codes = re.findall(pattern, codes)

    if not clean_codes:
        logging.error("No valid codes found.")
        await update.message.reply_text("No valid codes found.")
        return ConversationHandler.END

    # Limit to 10 codes at a time
    clean_codes = clean_codes[:10]

    await add_codes(update, amount, clean_codes)
    return ConversationHandler.END



# ✅ Main function to start the bot
def main():
    app = Application.builder().token(token).build()  # Use the `token` variable

    # Conversation handler for jload command
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('jload', load_codes_command)],
        states={
            ASKING_FOR_CODES: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_codes)],
        },
        fallbacks=[],
    )

    # Handle all messages that start with "J" or "j"
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(rf"^[Jj]\w*"), handle_message))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()