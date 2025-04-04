import os
import logging
import dotenv
import asyncio
import math
import requests
import time

# Set up logging first
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Check for fallback modules before importing solana
try:
    # Try to import setup_fallback and run it if available
    import setup_fallback
    setup_fallback.setup_fallback_modules()
    logger.info("Fallback module setup complete")
except ImportError:
    logger.warning("setup_fallback.py not found, skipping fallback module setup")
except Exception as e:
    logger.error(f"Error setting up fallback modules: {str(e)}")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from airalo_api import AiraloAPI
from solana_payments import get_payment_manager, SPL_TOKEN_SYMBOL

# Load environment variables
dotenv.load_dotenv()

# Initialize bot token and Airalo API
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
airalo_api = AiraloAPI()
payment_manager = get_payment_manager()

# Testing mode settings
TESTING_MODE = os.getenv('TESTING_MODE', 'true').lower() == 'true'
TEST_TOKEN_AMOUNT = 1  # Always require just 1 token for testing

# Get token address from environment variable
SPL_TOKEN_MINT = os.getenv('SPL_TOKEN_MINT', '3zJ7RxtzPahndBTEn5PGUyo9xBMv6MJP9J4TPqdFpump')

# Price markup configuration
PRICE_MARKUP_MULTIPLIER = 1.69  # Markup all prices by 1.69x

# In-memory payment tracking
payment_checks = {}  # Maps chat_id to payment address
payment_tasks = {}   # Maps payment address to asyncio task

# Token price cache to avoid frequent API calls
token_price_cache = {
    'price': None,
    'timestamp': 0,
    'cache_duration': 300  # Cache for 5 minutes (300 seconds)
}

def round_price_to_95_cents(price):
    """Round a price to end with .95 cents."""
    # Round down to the nearest dollar
    base_price = math.floor(price)
    # Add 0.95 to get the final price
    return base_price + 0.95

def get_token_price_usd():
    """Fetch the current token price in USD from DexScreener API."""
    current_time = int(time.time())
    
    # Check if we have a cached price that's still valid
    if token_price_cache['price'] and (current_time - token_price_cache['timestamp'] < token_price_cache['cache_duration']):
        logger.info(f"Using cached token price: ${token_price_cache['price']}")
        return token_price_cache['price']
    
    try:
        # Fetch the token price from DexScreener API
        url = f"https://api.dexscreener.com/tokens/v1/solana/{SPL_TOKEN_MINT}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                # Extract the price from the response
                price_usd = float(data[0].get('priceUsd', 0))
                
                if price_usd > 0:
                    # Update the cache
                    token_price_cache['price'] = price_usd
                    token_price_cache['timestamp'] = current_time
                    
                    logger.info(f"Fetched token price: ${price_usd}")
                    return price_usd
                else:
                    logger.error("Token price from API is zero or invalid")
            else:
                logger.error("Invalid response format from DexScreener API")
        else:
            logger.error(f"Failed to fetch token price: {response.status_code} - {response.text}")
    
    except Exception as e:
        logger.error(f"Error fetching token price: {str(e)}")
    
    # Return a default price if we couldn't fetch a new one
    # If we had a cached price previously, use that as a fallback
    if token_price_cache['price']:
        logger.warning(f"Using expired cached token price as fallback: ${token_price_cache['price']}")
        return token_price_cache['price']
    
    # If all else fails, use a hardcoded fallback price
    fallback_price = 0.001333  # Default fallback price
    logger.warning(f"Using hardcoded fallback token price: ${fallback_price}")
    return fallback_price

def calculate_token_amount(usd_price):
    """Convert USD price to token amount, rounded up to the nearest whole token."""
    token_price_usd = get_token_price_usd()
    if token_price_usd <= 0:
        logger.error(f"Invalid token price: ${token_price_usd}")
        # Use a fallback price to avoid division by zero
        token_price_usd = 0.001333
    
    # Calculate how many tokens equal the USD price
    token_amount = usd_price / token_price_usd
    
    # Round up to the nearest whole token
    token_amount = math.ceil(token_amount)
    
    logger.info(f"Price conversion: ${usd_price} at token price ${token_price_usd} = {token_amount} {SPL_TOKEN_SYMBOL}")
    return token_amount

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
                # Apply price markup
                original_price = float(package['price'])
                marked_up_price = round_price_to_95_cents(original_price * PRICE_MARKUP_MULTIPLIER)
                
                # Store both the original and marked up price in the callback data
                button_text = f"{package['title']} - ${marked_up_price}"
                callback_data = f"topup_{package['id']}_{original_price}_{marked_up_price}"
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
                # Apply price markup
                original_price = float(package['price'])
                marked_up_price = round_price_to_95_cents(original_price * PRICE_MARKUP_MULTIPLIER)
                
                # Store both the original and marked up price in the callback data
                button_text = f"{package['title']} - ${marked_up_price}"
                callback_data = f"topup_{package['id']}_{original_price}_{marked_up_price}"
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
    # Check if we have the marked up price in callback data
    callback_parts = query.data.split('_')
    if len(callback_parts) == 4:
        # New format with original and marked up price
        _, package_id, original_price, marked_up_price = callback_parts
        original_price_float = float(original_price)
        marked_up_price_float = float(marked_up_price)
    else:
        # Old format with just the original price
        _, package_id, original_price = callback_parts
        original_price_float = float(original_price)
        marked_up_price_float = round_price_to_95_cents(original_price_float * PRICE_MARKUP_MULTIPLIER)
    
    # Store selected package in user data with both prices
    context.user_data['selected_package'] = {
        'id': package_id,
        'original_price': original_price_float,
        'marked_up_price': marked_up_price_float
    }
    
    # Create a payment for this order
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Get the ICCID from user data
    iccid = context.user_data.get('iccid')
    if not iccid:
        logger.warning("Missing ICCID when creating payment. This may cause issues with order processing.")
    
    # Calculate the number of tokens based on the marked-up USD price
    # Use TEST_TOKEN_AMOUNT for testing mode, otherwise calculate based on real price
    if TESTING_MODE:
        token_amount = TEST_TOKEN_AMOUNT
    else:
        token_amount = calculate_token_amount(marked_up_price_float)
    
    # Make sure to pass the package_id to the payment
    payment = payment_manager.create_payment(
        amount=token_amount,
        user_id=user_id,
        package_id=package_id  # Store the actual package ID in the payment
    )
    
    # Store the ICCID in the payment object
    if iccid:
        payment.iccid = iccid
    
    # Store payment address in context
    context.user_data['payment_address'] = payment.address
    
    # Track this payment for checking status
    payment_checks[chat_id] = payment.address
    
    # Create payment message showing the marked up price to the user
    payment_msg = (
        f"📦 Selected package: {package_id}\n"
        f"💰 Price: ${marked_up_price_float}\n\n"
        f"Please send exactly {token_amount} {SPL_TOKEN_SYMBOL} tokens to complete your payment:\n\n"
        f"`{payment.address}`\n\n"
        f"⏱️ Payment window: {payment.expires_at.strftime('%H:%M:%S')}\n"
        f"(You have {payment.time_remaining() // 60:.0f} minutes and {payment.time_remaining() % 60:.0f} seconds to complete payment)"
    )
    
    # Create payment status checking task
    task = asyncio.create_task(check_payment_status_loop(chat_id, payment.address, context))
    payment_tasks[payment.address] = task
    
    keyboard = [[InlineKeyboardButton("🔄 Check Payment Status", callback_data=f"check_payment_{payment.address}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(payment_msg, reply_markup=reply_markup, parse_mode='Markdown')

async def check_payment_status_loop(chat_id, payment_address, context):
    """Loop to check payment status periodically."""
    application = context.application
    tries = 0
    max_tries = 30  # 10 minutes with 20-second checks
    
    while tries < max_tries:
        try:
            result = await payment_manager.check_payment_status(payment_address)
            
            if result['success']:
                # Payment completed
                payment = result.get('payment')
                
                # Check if a topup order has already been placed for this payment
                if payment and not payment.topup_ordered:
                    # Get the ICCID from the payment object or from user data
                    iccid = payment.iccid
                    
                    # If the payment doesn't have an ICCID, try to get it from user data
                    if not iccid:
                        user_data = context.user_data
                        iccid = user_data.get('iccid')
                    
                    # Get the package ID from the payment or from user data
                    package_id = payment.package_id
                    if not package_id and 'selected_package' in context.user_data:
                        package_id = context.user_data['selected_package'].get('id')
                    
                    if iccid and package_id:
                        try:
                            # Submit the order to Airalo
                            description = f"Topup for {iccid} (Payment: {payment_address})"
                            
                            logger.info(f"Placing topup order with Airalo: Package {package_id} for ICCID {iccid}")
                            order_response = await airalo_api.submit_topup_order(package_id, iccid, description)
                            
                            if 'data' in order_response and 'id' in order_response['data']:
                                order_id = order_response['data']['id']
                                # Mark the payment as having an order placed
                                payment.topup_ordered = True
                                payment.topup_order_id = order_id
                                
                                logger.info(f"Topup order placed successfully: Order ID {order_id}")
                                await application.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"✅ Payment completed and top-up order placed! Your data package will be activated shortly."
                                )
                            else:
                                logger.error(f"Failed to place topup order: {order_response}")
                                await application.bot.send_message(
                                    chat_id=chat_id,
                                    text="✅ Payment completed! Your top-up is being processed, but we're experiencing some delays. Our team will ensure your package is activated soon."
                                )
                        except Exception as e:
                            logger.error(f"Error placing topup order: {str(e)}")
                            await application.bot.send_message(
                                chat_id=chat_id,
                                text="✅ Payment completed! Your top-up is being processed manually due to a temporary issue. Our team will ensure your package is activated soon."
                            )
                    else:
                        logger.error(f"Missing data for topup order: ICCID={iccid}, Package ID={package_id}")
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text="✅ Payment completed! Your top-up will be processed manually by our team."
                        )
                else:
                    # Payment completed but order already placed or payment object missing
                    if payment and payment.topup_ordered:
                        logger.info(f"Topup already ordered for payment {payment_address}")
                        if payment.topup_order_id:
                            await application.bot.send_message(
                                chat_id=chat_id,
                                text=f"✅ Payment verified! Your top-up order #{payment.topup_order_id} has been placed and is being processed."
                            )
                        else:
                            await application.bot.send_message(
                                chat_id=chat_id,
                                text="✅ Payment verified! Your top-up order has been placed and is being processed."
                            )
                    else:
                        logger.warning(f"Payment completed but payment object missing from result")
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text="✅ Payment verified! Your top-up is being processed."
                        )
                
                # Sweep funds to main wallet
                sweep_result = await payment_manager.sweep_funds(payment_address)
                if sweep_result['success']:
                    logger.info(f"Funds swept for payment {payment_address}")
                    
                    # Check if this needed manual handling due to blockhash errors
                    if sweep_result.get('needs_manual_handling'):
                        logger.warning(f"Payment {payment_address} marked for manual sweeping due to blockhash errors")
                else:
                    error_msg = sweep_result.get('message', 'Unknown error')
                    logger.error(f"Failed to sweep funds for payment {payment_address}: {error_msg}")
                
                # Clean up
                if chat_id in payment_checks:
                    del payment_checks[chat_id]
                break
                
            elif result['status'] == 'expired':
                # Payment expired
                await application.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏰ Payment window expired. Please try again if you still want to complete your top-up."
                )
                
                # Clean up
                if chat_id in payment_checks:
                    del payment_checks[chat_id]
                break
            
            # Still waiting
            tries += 1
            await asyncio.sleep(20)  # Check every 20 seconds
            
        except Exception as e:
            logger.error(f"Error in payment status loop: {str(e)}")
            tries += 1
            await asyncio.sleep(20)
    
    # If we get here and haven't broken out of the loop, the payment timed out
    if tries >= max_tries and chat_id in payment_checks:
        await application.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ Payment checking timed out. Use the Check Payment Status button to verify if your payment went through."
        )

async def handle_payment_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle check payment status button."""
    query = update.callback_query
    await query.answer()
    
    if not query.data.startswith('check_payment_'):
        return
    
    # Extract payment address
    payment_address = query.data.split('_')[2]
    
    # Check payment status
    result = await payment_manager.check_payment_status(payment_address)
    
    if result['success']:
        # Payment completed
        payment = result.get('payment')
        
        # Check if a topup order has already been placed for this payment
        if payment and not payment.topup_ordered:
            # Get the ICCID from the payment object or from user data
            iccid = payment.iccid
            
            # If the payment doesn't have an ICCID, try to get it from user data
            if not iccid:
                user_data = context.user_data
                iccid = user_data.get('iccid')
            
            # Get the package ID from the payment or from user data
            package_id = payment.package_id
            if not package_id and 'selected_package' in context.user_data:
                package_id = context.user_data['selected_package'].get('id')
            
            if iccid and package_id:
                try:
                    # Submit the order to Airalo
                    description = f"Topup for {iccid} (Payment: {payment_address})"
                    
                    logger.info(f"Placing topup order with Airalo: Package {package_id} for ICCID {iccid}")
                    order_response = await airalo_api.submit_topup_order(package_id, iccid, description)
                    
                    if 'data' in order_response and 'id' in order_response['data']:
                        order_id = order_response['data']['id']
                        # Mark the payment as having an order placed
                        payment.topup_ordered = True
                        payment.topup_order_id = order_id
                        
                        logger.info(f"Topup order placed successfully: Order ID {order_id}")
                        await query.message.reply_text(
                            f"✅ Payment verified and top-up order placed! Your data package will be activated shortly."
                        )
                    else:
                        logger.error(f"Failed to place topup order: {order_response}")
                        await query.message.reply_text(
                            "✅ Payment verified! Your top-up is being processed, but we're experiencing some delays. Our team will ensure your package is activated soon."
                        )
                except Exception as e:
                    logger.error(f"Error placing topup order: {str(e)}")
                    await query.message.reply_text(
                        "✅ Payment verified! Your top-up is being processed manually due to a temporary issue. Our team will ensure your package is activated soon."
                    )
            else:
                logger.error(f"Missing data for topup order: ICCID={iccid}, Package ID={package_id}")
                await query.message.reply_text(
                    "✅ Payment verified! Your top-up will be processed manually by our team."
                )
        else:
            # Payment completed but order already placed or payment object missing
            if payment and payment.topup_ordered:
                logger.info(f"Topup already ordered for payment {payment_address}")
                if payment.topup_order_id:
                    await query.message.reply_text(
                        f"✅ Payment verified! Your top-up order #{payment.topup_order_id} has been placed and is being processed."
                    )
                else:
                    await query.message.reply_text(
                        "✅ Payment verified! Your top-up order has been placed and is being processed."
                    )
            else:
                logger.warning(f"Payment completed but payment object missing from result")
                await query.message.reply_text(
                    "✅ Payment verified! Your top-up is being processed."
                )
                
        # Sweep funds to main wallet if not already done
        sweep_result = await payment_manager.sweep_funds(payment_address)
        if sweep_result['success']:
            logger.info(f"Funds swept for payment {payment_address}")
            
            # Check if this needed manual handling due to blockhash errors
            if sweep_result.get('needs_manual_handling'):
                logger.warning(f"Payment {payment_address} marked for manual sweeping due to blockhash errors")
        else:
            error_msg = sweep_result.get('message', 'Unknown error')
            logger.error(f"Failed to sweep funds for payment {payment_address}: {error_msg}")
            
    elif result['status'] == 'expired':
        # Payment expired
        await query.message.reply_text(
            "⏰ Payment window expired. Please make a new top-up request if you still want to complete your purchase."
        )
    else:
        # Still waiting
        expires_in = result.get('expires_in', 0)
        minutes = int(expires_in // 60)
        seconds = int(expires_in % 60)
        
        # Retrieve payment amount from result and format message
        payment = result.get('payment')
        payment_amount = payment.amount if payment else "the requested amount"
        
        await query.message.reply_text(
            f"⏳ Payment pending. Please complete your payment of {payment_amount} {SPL_TOKEN_SYMBOL}.\n\n"
            f"Time remaining: {minutes} minutes and {seconds} seconds."
        )

async def update_token_price_background():
    """Background task to periodically update the token price cache."""
    while True:
        try:
            # Fetch new price to update the cache
            price = get_token_price_usd()
            logger.info(f"Background token price update: ${price}")
        except Exception as e:
            logger.error(f"Error in background token price update: {str(e)}")
        
        # Wait before updating again (every 5 minutes)
        await asyncio.sleep(300)  # 5 minutes

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
    application.add_handler(CallbackQueryHandler(handle_payment_check, pattern="^check_payment_"))
    application.add_handler(CallbackQueryHandler(handle_topup_selection, pattern="^topup_"))
    application.add_handler(CallbackQueryHandler(handle_service_selection))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_iccid_input))

    # Set up a pre-run callback to start the background task within the event loop
    async def post_init(application):
        """Tasks to run after application startup."""
        # Start the background task for price updates
        application.create_task(update_token_price_background())
    
    # Register the post_init callback
    application.post_init = post_init

    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 