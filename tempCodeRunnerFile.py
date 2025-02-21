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

# Process the commands
@bot.command()
async def up(ctx, *, command):
    await process_upload_command(ctx, f"up {command}")