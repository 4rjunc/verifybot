import logging
import telebot
from configuration.config import API_TOKEN
import utils.logger as logger_save
from telebot.util import update_types
from telebot.types import (
    InputFile,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ChatMemberUpdated,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# dynamic group id message forwarding ✅
# change the inline keyboard after revewing ✅
# get the payment verifyed message reply to the recipt image messsage ✅
# setting verifyer group and payment group

# Configuring logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize your custom logger (assuming it writes to a file)
logger_save.init_logger(f"logs/botlog.log")


# Initializing bot with 4 thread workers for handling multiple requests
bot = telebot.TeleBot(API_TOKEN, threaded=True, num_threads=4)


# /gm command handler
@bot.message_handler(commands=["start"])
def start(message):
    username = message.from_user.username
    chat_id = message.chat.id

    # Logging when a user sends a /start command
    logger.info(f"Received /start command from {username} (chat_id: {chat_id})")

    # Respond to the user with a good morning message
    # bot.send_message(chat_id, f"start, {username} {random_emoji}")
    bot.reply_to(
        message, f"Hi 👋 {username}, verify your payment by  sending the receipt"
    )
    return


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    chat_id = message.chat.id  # Dynamically capture the chat ID of the group
    verifyer_chat_id = -1002340040662
    photo = message.photo[-1].file_id  # Get the highest resolution photo
    message_id = message.message_id

    keyboard = InlineKeyboardMarkup()
    received_btn = InlineKeyboardButton(
        text="Received 👍", callback_data=f"received|{chat_id}|{message_id}"
    )
    nreceived_btn = InlineKeyboardButton(
        text="Not Received 👎", callback_data=f"nreceived|{chat_id}|{message_id}"
    )
    keyboard.add(received_btn)
    keyboard.add(nreceived_btn)

    # Send the photo back to the user
    bot.send_photo(
        verifyer_chat_id,
        photo,
        caption="Please verify the payment.",
        reply_markup=keyboard,
    )


# Handle the button click with callback_data
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    data = call.data.split("|")
    action = data[0]
    chat_id = int(data[1])
    message_id = int(data[2])

    if action == "received":
        # bot.send_message(chat_id, "Payment Verified ✅")
        # Replacing the inline keyboard after receiving verifiers review
        new_keyboard = InlineKeyboardMarkup()
        new_keyboard.add(
            InlineKeyboardButton(text="✅ Payment Verified", callback_data="noop")
        )
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=new_keyboard,
        )

        bot.send_message(chat_id, "Payment Verified ✅", reply_to_message_id=message_id)

    if action == "nreceived":
        # bot.send_message(chat_id, "Payment Not Received ❌")
        # Replacing the inline keyboard after receiving verifiers review
        new_keyboard = InlineKeyboardMarkup()
        new_keyboard.add(
            InlineKeyboardButton(text="❌ Payment Not Received", callback_data="noop")
        )
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=new_keyboard,
        )
        bot.send_message(
            chat_id, "Payment Not Received ❌", reply_to_message_id=message_id
        )


# Enable saving next step handlers to file "./.handlers-saves/step.save"
bot.enable_save_next_step_handlers(delay=2)

# Load next step handlers from the save file
bot.load_next_step_handlers()

# Logging bot start
logger.info("Bot started and polling...")

# Start polling (infinite loop to keep the bot running)
# bot.infinity_polling(allowed_updates=update_types) # for welcome messages
bot.infinity_polling()
