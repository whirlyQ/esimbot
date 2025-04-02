import os
import logging
import dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from airalo_api import AiraloAPI

# Load environment variables
dotenv.load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize bot token and Airalo API
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
airalo_api = AiraloAPI()

def get_welcome_message(user):
    """Generate welcome message for both start and help commands."""
    return (
        f"👋 Welcome {user.first_name}!\n\n"
        "I'm your eSIM package assistant. Here's what I can do:\n"
        "/usage - Check your eSIM data usage\n"
        "/topup - Purchase a topup for your current eSIM package\n"
        "/help - Show this help message"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    keyboard = [
        [
            InlineKeyboardButton("📊 Check Usage", callback_data='check_usage'),
            InlineKeyboardButton("🔋 Top Up Data", callback_data='topup_flow')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(get_welcome_message(user), reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    user = update.effective_user
    keyboard = [
        [
            InlineKeyboardButton("📊 Check Usage", callback_data='check_usage'),
            InlineKeyboardButton("🔋 Top Up Data", callback_data='topup_flow')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(get_welcome_message(user), reply_markup=reply_markup)

async def topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle service topup requests."""
    context.user_data['awaiting_iccid'] = True
    await update.message.reply_text(
        "Please enter your eSIM ICCID to view available top-up packages."
    )

async def usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle usage check requests."""
    context.user_data['awaiting_iccid'] = True
    context.user_data['awaiting_usage'] = True  # Flag to identify usage requests
    await update.message.reply_text(
        "Please enter your eSIM ICCID to check your data usage."
    )

async def handle_service_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle service selection and initiate payment process."""
    query = update.callback_query
    await query.answer()
    
    # Handle welcome message buttons
    if query.data == 'check_usage':
        context.user_data['awaiting_iccid'] = True
        context.user_data['awaiting_usage'] = True
        await query.message.reply_text(
            "Please enter your eSIM ICCID to check your data usage."
        )
        return
    elif query.data == 'topup_flow':
        context.user_data['awaiting_iccid'] = True
        await query.message.reply_text(
            "Please enter your eSIM ICCID to view available top-up packages."
        )
        return
    
    # Handle regular service selection
    if query.data.startswith('service'):
        context.user_data['selected_service'] = query.data
        context.user_data['awaiting_payment'] = True
        
        payment_message = (
            f"Selected service: {query.data}\n\n"
            "Please provide your payment details to proceed.\n"
            "You can pay with supported cryptocurrencies."
        )
        await query.message.reply_text(payment_message)

async def handle_iccid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ICCID input and fetch data."""
    if not context.user_data.get('awaiting_iccid'):
        return

    iccid = update.message.text.strip()
    try:
        if context.user_data.get('awaiting_usage'):
            # Handle usage check
            response = await airalo_api.get_usage(iccid)
            usage_data = response.get('data', {})
            
            # Format usage message
            status_emoji = {
                'ACTIVE': '✅',
                'NOT_ACTIVE': '❌',
                'FINISHED': '🏁',
                'UNKNOWN': '❓',
                'EXPIRED': '⏰'
            }.get(usage_data.get('status', 'UNKNOWN'), '❓')

            message = (
                f"{status_emoji} eSIM Status: {usage_data.get('status', 'UNKNOWN')}\n\n"
                f"📊 Data Usage:\n"
                f"• Remaining: {usage_data.get('remaining', 0)} MB\n"
                f"• Total: {usage_data.get('total', 0)} MB\n"
                f"• Unlimited: {'Yes' if usage_data.get('is_unlimited') else 'No'}\n\n"
                f"📞 Voice:\n"
                f"• Remaining: {usage_data.get('remaining_voice', 0)} minutes\n"
                f"• Total: {usage_data.get('total_voice', 0)} minutes\n\n"
                f"💬 Text:\n"
                f"• Remaining: {usage_data.get('remaining_text', 0)} messages\n"
                f"• Total: {usage_data.get('total_text', 0)} messages\n\n"
                f"⏰ Expires: {usage_data.get('expired_at', 'N/A')}"
            )
            
            # Add Top Up button
            keyboard = [[InlineKeyboardButton("🔋 Top Up Data", callback_data=f"topup_usage_{iccid}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, reply_markup=reply_markup)
        else:
            # Handle topup packages (existing code)
            response = await airalo_api.get_topup_packages(iccid)
            packages = response.get('data', [])

            if not packages:
                await update.message.reply_text(
                    "No top-up packages found for this eSIM. Please check your ICCID and try again."
                )
                return

            keyboard = []
            for package in packages:
                button_text = f"{package['title']} - ${package['price']}"
                callback_data = f"topup_{package['id']}_{package['price']}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Available top-up packages:",
                reply_markup=reply_markup
            )

        # Store ICCID in context for later use
        context.user_data['iccid'] = iccid
        context.user_data['awaiting_iccid'] = False
        context.user_data['awaiting_usage'] = False

    except Exception as e:
        error_message = str(e)
        logger.error(f"Error fetching data: {error_message}")
        
        if "Invalid ICCID" in error_message:
            await update.message.reply_text(error_message)
        elif "Rate limit exceeded" in error_message or "Too Many Attempts" in error_message:
            await update.message.reply_text(error_message)
        else:
            await update.message.reply_text(
                f"Sorry, there was an error: {error_message}"
            )
        
        context.user_data['awaiting_iccid'] = False
        context.user_data['awaiting_usage'] = False

async def handle_topup_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle top-up package selection."""
    query = update.callback_query
    await query.answer()

    if not query.data.startswith('topup_'):
        return

    # Check if this is a topup from usage message or welcome message
    if query.data in ['topup_flow', 'topup_usage']:
        context.user_data['awaiting_iccid'] = True
        await query.message.reply_text(
            "Please enter your eSIM ICCID to view available top-up packages."
        )
        return

    # Check if this is a topup from usage message
    if query.data.startswith('topup_usage_'):
        iccid = query.data.split('_')[2]
        context.user_data['iccid'] = iccid
        # Fetch topup packages for this ICCID
        try:
            response = await airalo_api.get_topup_packages(iccid)
            packages = response.get('data', [])

            if not packages:
                await query.message.reply_text(
                    "No top-up packages found for this eSIM. Please check your ICCID and try again."
                )
                return

            keyboard = []
            for package in packages:
                button_text = f"{package['title']} - ${package['price']}"
                callback_data = f"topup_{package['id']}_{package['price']}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "Available top-up packages:",
                reply_markup=reply_markup
            )
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error fetching topup packages: {error_message}")
            await query.message.reply_text(error_message)
        return

    # Handle regular topup package selection
    _, package_id, price = query.data.split('_')
    
    # Store selected package in user data
    context.user_data['selected_package'] = {
        'id': package_id,
        'price': float(price)
    }
    context.user_data['awaiting_payment'] = True

    # Send payment request
    await query.message.reply_text(
        f"Selected package: {package_id}\n"
        f"Price: ${price}\n\n"
        "Please provide your payment details to proceed.\n"
        "You can pay with supported cryptocurrencies."
    )

async def handle_payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment information and process the order."""
    if not context.user_data.get('awaiting_payment'):
        # If we're not in the payment flow, ignore the message
        return
    
    # Here you would:
    # 1. Verify the payment
    # 2. Process the order with your service API
    # 3. Send confirmation to the user
    
    await update.message.reply_text(
        "Thank you for your payment! Your order is being processed."
    )
    
    # Reset the payment state
    context.user_data['awaiting_payment'] = False

def main():
    """Start the bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("topup", topup))
    application.add_handler(CommandHandler("usage", usage))
    
    # Add callback handlers in correct order (more specific handlers first)
    application.add_handler(CallbackQueryHandler(handle_topup_selection, pattern="^topup_"))
    application.add_handler(CallbackQueryHandler(handle_service_selection))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_iccid_input))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_payment_info))

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 