from telethon import TelegramClient, events
import os
from dotenv import load_dotenv
import json
import logging
import re

# Load environment variables
load_dotenv()

# Get API credentials (Create an app on my.telegram.org to get these)
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

# Check if API_ID and API_HASH are loaded correctly
if not API_ID or not API_HASH:
    raise ValueError("Your API ID or Hash cannot be empty or None. Please check your .env file.")

# Create a Telegram client for your personal account
client = TelegramClient("my_account", API_ID, API_HASH)

# Logging setup
logging.basicConfig(level=logging.INFO)

# Custom prefix
PREFIX = "J"  # Can be changed as needed

# Constants
FILE_NAME = 'codes.json'
REMOVED_FILE_NAME = 'used.json'
TOTAL_DUE_FILE = 'total_due.json'

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

def escape_markdown_v2(text):
    escape_chars = r'_*\[\]()~`>#+-=|{}!.'
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

# ✅ Telegram Command Handlers
@client.on(events.NewMessage(incoming=True))
async def handle_message(event):
    """ Handles prefixed commands """
    message = event.message.message.strip()
    command, args = parse_command(message)

    if not command:
        return

    if command == "start":
        await event.respond("Hello! I'm your UC bot. Use Jhelp to see available commands.")
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
Jstop - Stop the bot"""
        await event.respond(help_text)
    elif command == "rate":
        await rate(event)
    elif command == "baki":
        await baki(event, args)
    elif command == "price":
        await price(event, args)
    elif command == "stock":
        await stock(event)
    elif command == "check":
        await check(event)
    elif command == "clear":
        await clear(event)
    elif command == "up":
        await upload_codes(event, args)
    elif command == "stop":
        await stop_bot(event)
    else:
        await event.respond(f"Unknown command: {command}")

async def rate(event):
    data = load_json(FILE_NAME)
    if not data['codes']:
        await event.respond("No pricing data available.")
        return

    sorted_codes = sorted(data['codes'], key=lambda group: group['amount'])
    result = ["💰 UC Pricing List:\n"]

    for group in sorted_codes:
        amount = group['amount']
        price = group.get('price', None)
        if price is not None:
            result.append(f"☞︎︎︎ {amount:<3} 🆄︎🅲︎  ➪ {price} \n")

    await event.respond("\n".join(result) if len(result) > 1 else "No pricing data available.")

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

async def baki(event, args):
    """Retrieve UC codes and move them to used.json"""
    if len(args) < 1:
        await event.respond("Usage: Jbaki <amount> [count]\nExample: Jbaki 36 or Jbaki 36 2")
        return

    try:
        amount = int(args[0])
        count = int(args[1]) if len(args) > 1 else 1  # Default to 1 if count is not provided
    except ValueError:
        await event.respond("Invalid amount or count.")
        return

    result = get_codes(amount, count)

    if result:
        amount, codes = result
        codes_output = '\n'.join([f"`{code}`" for code in codes])  # Format each code in monospace

        # Get the price for the given amount from the codes.json file
        data = load_json(FILE_NAME)
        group = next((item for item in data['codes'] if item['amount'] == amount), None)
        if group:
            price_per_code = group.get('price', 0)
        else:
            price_per_code = 0

        total_due = price_per_code * count

        # Update total due in total_due.json
        total_due_data = load_json(TOTAL_DUE_FILE, {"total_due": 0})
        previous_due = total_due_data["total_due"]
        total_due_data["total_due"] += total_due
        save_json(total_due_data, TOTAL_DUE_FILE)

        response = f"{codes_output}\n\n✓ {amount} 🆄︎🅲︎  x  {count}  ✓\n\nTᴏᴛᴀʟ Dᴜᴇ : ({previous_due}) + ({price_per_code}x{count}) = {total_due_data['total_due']}"
        await event.respond(response)
    else:
        await event.respond(f"⚠ {amount} UC Stock Out ⚠")

async def price(event, args):
    """Update the price for a specific UC amount in both codes.json and used.json."""
    if len(args) < 2:
        await event.respond("Usage: Jprice <amount> <price>")
        return

    try:
        amount = int(args[0])
        price = float(args[1])
    except ValueError:
        await event.respond("Invalid amount or price.")
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

    await event.respond(f"✅ Price for {amount} UC updated to {price} in both stock & used records.")

async def stock(event):
    data = load_json(FILE_NAME)
    if not data['codes']:
        await event.respond("No codes available.")
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

    await event.respond("\n".join(result))

async def check(event):
    data = load_json(REMOVED_FILE_NAME)
    if not data['codes']:
        await event.respond("No dues available, All clear ✅✅✅.")
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

    await event.respond("\n".join(result))

async def clear(event):
    save_json({"codes": []}, REMOVED_FILE_NAME)
    save_json({"total_due": 0}, TOTAL_DUE_FILE)
    await event.respond("Cleared all dues ✅ ✅.")

# Add codes grouped by amount
async def add_codes(event, amount, codes, file_name=FILE_NAME):
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
            await event.respond(warning_message)

    group['codes'].extend(new_codes)

    save_json(data, file_name)

    log_message = f"Added {len(new_codes)} codes for amount: {amount}"
    logging.info(log_message)
    await event.respond(log_message)

# Function to process the upload command
async def process_upload_command(event, command):
    parts = command.split(' ', 2)
    if len(parts) < 3:
        logging.error("Invalid command format. Use: .up <amount>uc <codes>")
        await event.respond("Invalid command format. Use: .up <amount>uc <codes>")
        return

    amount_code, codes = parts[1], parts[2]
    try:
        amount = int(amount_code[:-2])
    except ValueError:
        logging.error("Invalid amount format. Please provide a valid number before 'uc'.")
        await event.respond("Invalid amount format. Please provide a valid number before 'uc'.")
        return

    # Handle multi-line input by replacing newlines with spaces
    codes = codes.replace('\n', ' ')

    # Extract each code using a flexible pattern
    pattern = r'[a-zA-Z]{4}-[a-zA-Z]-S-\d{8} \d{4}-\d{4}-\d{4}-\d{4}'
    clean_codes = re.findall(pattern, codes)

    if not clean_codes:
        logging.error("No valid codes found.")
        await event.respond("No valid codes found.")
        return

    # Limit to 10 codes at a time
    clean_codes = clean_codes[:10]

    await add_codes(event, amount, clean_codes)

# Update the upload_codes command handler
async def upload_codes(event, args):
    """Upload new codes to the codes.json file."""
    if len(args) < 2:
        await event.respond("Usage: Jup <amount> <code1> [<code2> ...]\nExample: Jup 80 UPBD-N-S-04811675 1679-5939-2679-5224 UPBD-N-S-04810010 4491-9257-2419-2723")
        return

    amount = args[0]
    codes = args[1:]

    try:
        amount = int(amount)
    except ValueError:
        await event.respond("Invalid amount format. Please provide a valid number.")
        return

    # Combine adjacent code parts into single codes
    combined_codes = []
    for i in range(0, len(codes), 2):
        combined_code = f"{codes[i]} {codes[i+1]}"
        combined_codes.append(combined_code)

    # Limit to 10 codes at a time
    combined_codes = combined_codes[:10]

    await add_codes(event, amount, combined_codes)

async def stop_bot(event):
    """Stop the bot gracefully."""
    await event.respond("Stopping the bot...")
    await client.disconnect()

# ✅ Main function to start the bot
print("Bot is running...")
client.start()
client.run_until_disconnected()
