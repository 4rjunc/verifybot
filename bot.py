import logging
import requests
import telebot
import json
import cv2
import re
import numpy as np
import utils.logger as logger_save
from configuration.config import API_TOKEN
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
import io  # For in-memory operations
import pytesseract
from PIL import Image, ImageFilter, ImageDraw
import queue
import threading
import time

# dynamic group id message forwarding ✅
# change the inline keyboard after revewing ✅
# get the payment verifyed message reply to the recipt image messsage ✅
# setting verifyer group and payment group ✅
# auto blur images ✅
# stress test

# Configuring logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize your custom logger (assuming it writes to a file)
logger_save.init_logger(f"logs/botlog.log")


# Initializing bot with 4 thread workers for handling multiple requests
bot = telebot.TeleBot(API_TOKEN, threaded=True, num_threads=4)

verifier_group_ids = []  # Stores verifiers group ID


# Funtions to save verifier group ID in JSON file
def save_verifier_group_id():
    with open("verifier_config.json", "w") as file:
        json.dump({"verifier_group_id": verifier_group_ids}, file)


# Load the verifier group ID from a JSON file
def load_verifier_group_id():
    global verifier_group_id
    try:
        with open("verifier_config.json", "r") as file:
            data = json.load(file)
            verifier_group_id = data.get("verifier_group_id", None)
    except (FileNotFoundError, json.JSONDecodeError):
        verifier_group_id = None


# Call this function at bot startup to load the group ID
load_verifier_group_id()
PASSKEY = "r?eG6c06$Ms="


@bot.message_handler(commands=["setverifier"])
def set_verifier_group(message):
    global verifier_group_ids
    chat_id = message.chat.id

    # Check if the message is from a group chat
    if message.chat.type == "group" or message.chat.type == "supergroup":
        try:
            # Extract passkey from the message (expected format: /setverifier <passkey>)
            provided_passkey = message.text.split()[1]

            # Validate the passkey
            if provided_passkey == PASSKEY:
                if chat_id not in verifier_group_ids:
                    verifier_group_ids.append(chat_id)
                    bot.reply_to(
                        message, f"Group {chat_id} has been added as a verifier group."
                    )
                else:
                    bot.reply_to(
                        message, f"Group {chat_id} is already a verifier group."
                    )
            else:
                bot.reply_to(
                    message, "Invalid passkey. Please provide the correct passkey."
                )
        except IndexError:
            bot.reply_to(
                message, "Please provide a passkey after the /setverifier command."
            )
    else:
        bot.reply_to(message, "This command can only be used in a group.")


# Capture the group ID dynamically to remove it
@bot.message_handler(commands=["removeverifier"])
def remove_verifier_group(message):
    global verifier_group_ids
    chat_id = message.chat.id

    # Check if the message is from a group chat
    if message.chat.type == "group" or message.chat.type == "supergroup":
        try:
            # Extract passkey from the message (expected format: /removeverifier <passkey>)
            provided_passkey = message.text.split()[1]

            # Validate the passkey
            if provided_passkey == PASSKEY:
                if chat_id in verifier_group_ids:
                    verifier_group_ids.remove(chat_id)
                    bot.reply_to(
                        message,
                        f"Group {chat_id} has been removed from the verifier list.",
                    )
                else:
                    bot.reply_to(
                        message, f"Group {chat_id} is not in the verifier list."
                    )
            else:
                bot.reply_to(
                    message, "Invalid passkey. Please provide the correct passkey."
                )
        except IndexError:
            bot.reply_to(
                message, "Please provide a passkey after the /removeverifier command."
            )
    else:
        bot.reply_to(message, "This command can only be used in a group.")


# /start command handler
@bot.message_handler(commands=["start"])
def start(message):
    save_verifier_group_id()
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


# Dictionary to keep track of message IDs for each verifier group per receipt
verifier_group_message_ids = {}  # Key: original_message_id, Value: {group_id: list of message_ids}


# Create a queue for processing images
# image_processing_queue = queue.Queue()
#
#
# def image_processing_worker():
#     while True:
#         message = image_processing_queue.get()
#         if message is None:
#             break  # Exit the loop if None is sent to the queue
#         try:
#             handle_image(message)  # Call a function to handle the image processing
#         finally:
#             image_processing_queue.task_done()
#
#
# # Start a thread to process images
# worker_thread = threading.Thread(target=image_processing_worker)
# worker_thread.start()
#


# @bot.message_handler(content_types=["photo"])
# def handle_photo(message):
#     global verifier_group_ids
#
#     if not verifier_group_ids:
#         bot.reply_to(
#             message, "No verifier groups are set. Please set them using /setverifier."
#         )
#         return
#
#     # Enqueue the message for processing
#     image_processing_queue.put(message)
#


# Function to automatically blur text in the image using OCR
def detect_and_blur_sensitive_info(image):
    # Convert the PIL image to a format OpenCV can work with
    image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    # Perform OCR with bounding box info
    data = pytesseract.image_to_data(image_cv, output_type=pytesseract.Output.DICT)

    # Sensitive patterns for text detection
    sensitive_patterns = [
        r"\b₹?\d{1,3}(,\d{3})*(\.\d{2})?\b",  # Amount pattern (e.g., ₹50,000.00)
        r"\d+[A-Za-z]*|\b[A-Za-z]+\d+\b",  # Pattern for alphanumeric strings
        r"\b[A-Z]\b\s[A-Z][a-z]+\b",  # Name pattern: initial and last name (e.g., "M Sahad")
    ]

    # Iterate through the OCR results
    for i in range(len(data["text"])):
        text = data["text"][i].strip()  # Remove extra spaces

        # Skip if the text is empty or too short (usually irrelevant)
        if text == "" or len(text) < 2:
            continue

        print("text:", text)  # For debugging to see OCR text

        # Check if the text matches any sensitive pattern or is an email-like string
        if (
            not any(re.search(pattern, text) for pattern in sensitive_patterns)
        ) or re.match(r"^\d{10}@.+$", text):
            # Get bounding box coordinates
            print("text to blur: ", text)
            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i]
            h = data["height"][i]

            # Extract the region of interest (ROI)
            roi = image_cv[y : y + h, x : x + w]

            # Apply Gaussian blur to the ROI
            blurred_roi = cv2.GaussianBlur(roi, (23, 23), 30)

            # Replace the original region with the blurred one
            image_cv[y : y + h, x : x + w] = blurred_roi

    # Convert back to PIL format
    return Image.fromarray(cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB))


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    global verifier_group_ids, verifier_group_message_ids

    if not verifier_group_ids:
        bot.reply_to(
            message, "No verifier groups are set. Please set them using /setverifier."
        )
        return
    chat_id = message.chat.id  # Dynamically capture the chat ID of the group
    photo = message.photo[-1].file_id  # Get the highest resolution photo
    message_id = message.message_id  # ID of the original message

    # keyboard = InlineKeyboardMarkup()
    # received_btn = InlineKeyboardButton(
    #     text="Received 👍", callback_data=f"received|{chat_id}|{message_id}"
    # )
    # nreceived_btn = InlineKeyboardButton(
    #     text="Not Received 👎", callback_data=f"nreceived|{chat_id}|{message_id}"
    # )
    # keyboard.add(received_btn)
    # keyboard.add(nreceived_btn)

    # Track the message IDs in verifier groups for this original message
    verifier_group_message_ids[message_id] = {}

    # Send the photo to all verifier groups and store the message IDs
    for group_id in verifier_group_ids:
        send_message = bot.send_photo(
            group_id,
            photo,
            caption="Please verify the payment.",
            reply_markup=keyboard,
        )
        # Append the sent message ID to the list for this group, for this specific receipt
        verifier_group_message_ids[message_id][group_id] = send_message.message_id


# this function is for bluring
# def handle_image(message):
#     chat_id = message.chat.id
#     photo = message.photo[-1].file_id  # Get the highest resolution photo
#     message_id = message.message_id  # ID of the original message
#
#     # Ensure the message_id key is initialized in the verifier_group_message_ids dictionary
#     if message_id not in verifier_group_message_ids:
#         verifier_group_message_ids[message_id] = {}
#
#     # Use the file_id to get the photo
#     photo_file = bot.get_file(photo)
#
#     # Retry logic
#     for attempt in range(3):  # Try 3 times
#         try:
#             photo_bytes = bot.download_file(photo_file.file_path)
#             break  # Exit loop if successful
#         except requests.exceptions.ConnectionError:
#             if attempt < 2:  # If not the last attempt
#                 time.sleep(1)  # Delay before retrying
#             else:
#                 bot.reply_to(
#                     message, "Failed to download the photo. Please try again later."
#                 )
#                 return
#
#     # Open the image using PIL directly from bytes
#     image = Image.open(io.BytesIO(photo_bytes))
#
#     # Call the function to blur sensitive info
#     processed_image = detect_and_blur_sensitive_info(image)
#
#     # Save the processed image to a BytesIO object
#     img_byte_arr = io.BytesIO()
#     processed_image.save(img_byte_arr, format="JPEG")
#     img_byte_arr.seek(0)
#
#     keyboard = InlineKeyboardMarkup()
#     received_btn = InlineKeyboardButton(
#         text="Received 👍", callback_data=f"received|{chat_id}|{message_id}"
#     )
#     nreceived_btn = InlineKeyboardButton(
#         text="Not Received 👎", callback_data=f"nreceived|{chat_id}|{message_id}"
#     )
#     keyboard.add(received_btn)
#     keyboard.add(nreceived_btn)
#
#     # Send the processed photo to all verifier groups
#     for group_id in verifier_group_ids:
#         try:
#             send_message = bot.send_photo(
#                 group_id,
#                 img_byte_arr.getvalue(),  # Use the byte array of the processed image
#                 caption="Please verify the payment.",
#                 reply_markup=keyboard,
#             )
#             # Store the message_id in the verifier_group_message_ids dictionary
#             verifier_group_message_ids[message_id][group_id] = send_message.message_id
#         except Exception as e:
#             logger.error(f"Error sending message to group {group_id}: {e}")
#


# Handle the button click with callback_data
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    global verifier_group_ids, verifier_group_message_ids
    data = call.data.split("|")
    action = data[0]
    chat_id = int(data[1])
    original_message_id = int(data[2])

    # Prepare the new inline keyboard (no more buttons after decision)
    if action == "received":
        new_keyboard = InlineKeyboardMarkup()
        new_keyboard.add(
            InlineKeyboardButton(text="✅ Payment Verified", callback_data="noop")
        )

        # Update the inline keyboard in all verifier groups for the specific receipt
        if original_message_id in verifier_group_message_ids:
            for group_id, group_message_id in verifier_group_message_ids[
                original_message_id
            ].items():
                try:
                    bot.edit_message_reply_markup(
                        chat_id=group_id,
                        message_id=group_message_id,
                        reply_markup=new_keyboard,
                    )
                except Exception as e:
                    logger.error(
                        f"Error updating inline keyboard in group {group_id}: {e}"
                    )

        # Notify the original group that payment was verified
        bot.send_message(
            chat_id, "Payment Verified ✅", reply_to_message_id=original_message_id
        )

    elif action == "nreceived":
        new_keyboard = InlineKeyboardMarkup()
        new_keyboard.add(
            InlineKeyboardButton(text="❌ Payment Not Received", callback_data="noop")
        )

        # Update the inline keyboard in all verifier groups for the specific receipt
        if original_message_id in verifier_group_message_ids:
            for group_id, group_message_id in verifier_group_message_ids[
                original_message_id
            ].items():
                try:
                    bot.edit_message_reply_markup(
                        chat_id=group_id,
                        message_id=group_message_id,
                        reply_markup=new_keyboard,
                    )
                except Exception as e:
                    logger.error(
                        f"Error updating inline keyboard in group {group_id}: {e}"
                    )

        # Notify the original group that payment was not received
        bot.send_message(
            chat_id, "Payment Not Received ❌", reply_to_message_id=original_message_id
        )


# Main function to start the bot
def start_bot():
    bot.enable_save_next_step_handlers(delay=2)

    # Load next step handlers from the save file
    bot.load_next_step_handlers()

    # Logging bot start
    logger.info("Bot started and polling...")

    # Start polling (infinite loop to keep the bot running)
    # bot.infinity_polling(allowed_updates=update_types) # for welcome messages
    bot.infinity_polling()

if __name__ == "__main__":
    start_bot()
