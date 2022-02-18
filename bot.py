#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os
import re # Regex expression
import traceback
import html
import json
import pytz
# import py7zr # Compressing
from telegram.ext.dispatcher import run_async # For parsing datetime
from dotenv import load_dotenv
from datetime import datetime, timedelta, time
from uuid import uuid4 # For security
import pyotp
import requests
import user
import db
import util
import feedback
import admin

from telegram import (
    ParseMode,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    replymarkup
)
from telegram.ext import (
    Updater,
    CommandHandler,
    PicklePersistence,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    ConversationHandler,
    InlineQueryHandler,
    messagequeue as mq,
)
from telegram.error import BadRequest

# Load environment variables from .env file
load_dotenv()

MONGO_DB = os.environ.get('MONGO_DB')
MONGO_URL = os.environ.get('MONGO_URL')
BOT_ID = int(os.environ.get('BOT_ID'))
DEVELOPER_CHAT_ID = int(os.environ.get('DEVELOPER_CHAT_ID'))
TOKEN = os.environ.get('TOKEN')
VERIFIED_SHARER_CODE = os.environ.get('VERIFIED_SHARER_CODE')
SEND_VERIFICATION_EMAIL_URL = os.environ.get('SEND_VERIFICATION_EMAIL_URL')


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get('PORT', 5000))

def start_verified(update, context):
    '''Displays message to VERIFIED users'''

    query = update.callback_query
    if query:
        query.answer()
        first_name = query.message.chat.first_name
        username = query.from_user.username
    else:
        first_name = update.message.from_user.first_name
        username = update.message.from_user.username

    # Ensure that username is updated in MongoDB
    context.user_data[db.USERNAME] = username
    user.save_to_db(context.user_data)

    message = "<u><b>Latest Feedback</b></u>"

    for i, el in enumerate(db.all_feedback_col.find().sort(db.TIME_CREATED, -1).limit(3)):
        title = el.get(db.TITLE)
        feedback_id = el.get(db.FEEDBACK_ID)
        message += f"\n{i+1}. {title}\n<b>More Details</b>: /view_{feedback_id}\n"

    message += "\n<u><b>Most Popular Feedback</b></u>"
    for i, el in enumerate(db.all_feedback_col.find().sort(db.NUM_LIKES, -1).limit(3)):
        num_likes = el.get(db.NUM_LIKES)
        title = el.get(db.TITLE)
        feedback_id = el.get(db.FEEDBACK_ID)
        message += f"\n{i+1}. {title} ({num_likes}❤️)\n<b>More Details</b>: /view_{feedback_id}\n"


    message += f"\nHi {first_name}, please select a category."
    keyboard = util.format_categories_keyboard()
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send message
    if query:
        query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        update.message.reply_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)   

    return db.START_VERIFIED 

def start(update, context):
    """Prompts user for a student ID if chat_id does not exist in DB"""

    chat_id = str(update.message.chat_id)

    user.update_local_data(context.user_data, chat_id)

    if context.user_data.get(db.STUDENT_ID):
        return start_verified(update, context)


    # user.update_local_data(context.user_data, chat_id)

    message = "Hi! Please enter your Student ID"

    update.message.reply_text(text=message, parse_mode=ParseMode.HTML)

    return db.START


def send_email(update, context):
    first_name = update.message.from_user.first_name
    username = update.message.from_user.username
    chat_id = str(update.message.chat_id)
    # Reinitialise variables
    context.user_data[db.USERNAME] = username
    context.user_data[db.CHAT_ID] = str(chat_id)
    context.user_data[db.NAME] = first_name

    match = re.search(r'^100\d{4}$', update.message.text)

    if match == None:
        message_error = "Invalid Student ID"
        update.message.reply_text(text=message_error, parse_mode=ParseMode.HTML)
        return db.START

    # Get secret key and OTP
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret, interval=db.OTP_EXPIRY)
    url = SEND_VERIFICATION_EMAIL_URL

    # Save OTP_OBJECT to temp_data
    util.handle_temp_data(update, context, key=db.OTP_OBJECT, value=totp, set=True, overwrite=True)

    # Save Student ID value to a key
    context.user_data[db.STUDENT_ID] = update.message.text

    # Call cloud function send email with OTP to user's school email
    data = {
        db.STUDENT_ID: update.message.text,
        db.OTP: totp.now(),
    }

    context.dispatcher.run_async(requests.post, url, data)

    message = f"Thank you! We have just sent you an email with a 6-digit verification code. Please input the 6-digit code. This code will expire in {int(db.OTP_EXPIRY/60)}min."

    update.message.reply_text(text=message, parse_mode=ParseMode.HTML)

    return db.SEND_EMAIL

def verify_otp(update, context):    
    # Check if valid
    totp = util.handle_temp_data(update, context, key=db.OTP_OBJECT, get=True)
    is_valid = totp.verify(update.message.text)

    if not is_valid:
        message_error = "Invalid OTP. Please press /start to continue."
        update.message.reply_text(text=message_error, parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    # If valid, authenticate user + save user's username, chat_id and first_name into DB so that there's no need to reauthenticate
    # Save to DB
    user.save_to_db(context.user_data, is_update=False)
    
    return start_verified(update, context)

def view_category(update, context):
    '''
    Shows the main page for the category - Currently finds the latest 5 issues related to that category
    '''

    query = update.callback_query
    query.answer()

    if query.data == db.BACK:
        pass
    else:
        # Save category to temp_data
        util.handle_temp_data(update, context, key=db.CATEGORY, value=query.data, set=True, overwrite=True)

    find_category = {db.CATEGORY: query.data}
    cursor_count = db.all_feedback_col.count_documents(find_category)

    if cursor_count == 0:
        message = "We have yet to receive any feedback for this topic."
    else:
        message = f"<b>Latest Feedback related to {query.data.upper()}</b>"

    for i, el in enumerate(db.all_feedback_col.find(find_category).sort(db.TIME_CREATED, -1).limit(5)):
        title = el.get(db.TITLE)
        feedback_id = el.get(db.FEEDBACK_ID)
        message += f"\n{i+1}. {title}\n<b>More Details</b>: /view_{feedback_id}\n"

    for doc in db.admin_updates_col.find().sort(db.TIME_CREATED, -1).limit(1):
        admin_announcement = doc.get(query.data)
        # Handle case whereby admin_announcement for that category no longer exists yet
        if admin_announcement:
            message += f"\n\n<b>Admin Updates</b>\n{admin_announcement}\n"

    keyboard = [[InlineKeyboardButton("Back", callback_data=db.BACK)],
    [InlineKeyboardButton("New Feedback", callback_data=db.FEEDBACK_TITLE)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return db.VIEW_CATEGORY


def error(update, context):
    """Log the error and send a telegram message to notify the developer."""

    # if not BadRequest:
    error = str(context.error)
    print(error == "Message is not modified: specified new message content and reply markup are exactly the same as a current content and reply markup of the message")
    if error == "Message is not modified: specified new message content and reply markup are exactly the same as a current content and reply markup of the message":
        logger.error(msg=f"Skipping Error: {error}")
        return
    elif error == "'ObjectId' object has no attribute '__id'":
        logger.error(msg=f"Skipping Error: {error}")
        return

    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    chat_id = context.user_data.get(db.CHAT_ID)
    username = context.user_data.get(db.USERNAME)
    first_error_msg = f"The following user, @{username} received the following error:\n{error}"
    context.bot.send_message(chat_id=DEVELOPER_CHAT_ID, text=f"{first_error_msg}", parse_mode=ParseMode.HTML)
    context.bot.send_message(chat_id=chat_id, text="An error occurred. Try typing /cancel followed by /start to reset the bot. If this does not fix the error, please try again later.")

    # Mongodb is replacing value of _id and picklePeristence is automatically updating it ._.

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    message = (
        'An exception was raised while handling an update\n'
        '<pre>update = {}</pre>\n\n'
        '<pre>context.chat_data = {}</pre>\n\n'
        '<pre>context.user_data = {}</pre>\n\n'
        '<pre>{}</pre>'
    ).format(
        html.escape(json.dumps(update.to_dict(), indent=2, ensure_ascii=False)),
        html.escape(str(context.chat_data)),
        html.escape(str(context.user_data)),
        html.escape(tb_string),
    )

    # Finally, send the message to developer and user respectively
    context.bot.send_message(chat_id=DEVELOPER_CHAT_ID, text=message, parse_mode=ParseMode.HTML)
    return ConversationHandler.END

def main():
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(TOKEN, use_context=True, workers=32)


    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start, run_async=True),
    ],
        states={
            db.START: [
                MessageHandler(~Filters.command & Filters.text, send_email),
            ],
            db.SEND_EMAIL: [
                MessageHandler(~Filters.command & Filters.text, verify_otp),
            ],
            db.START_VERIFIED: [
                CallbackQueryHandler(view_category, pattern=rf'^{db.START_VERIFIED_PATTERN}$'),
            ],
            db.VIEW_CATEGORY: [
                CallbackQueryHandler(start_verified, pattern=rf'^{db.BACK}$'),
                CallbackQueryHandler(feedback.title, pattern=rf'^{db.FEEDBACK_TITLE}$'),
            ],
            db.FEEDBACK_TITLE: [
                CallbackQueryHandler(view_category, pattern=rf'^{db.BACK}$'),
                MessageHandler(~Filters.command & Filters.text, feedback.description),
            ],
            db.FEEDBACK_DESCRIPTION: [
                CallbackQueryHandler(feedback.title, pattern=rf'^{db.BACK}$'),
                MessageHandler(~Filters.command & Filters.text | Filters.photo | Filters.document, feedback.confirm),
            ],
            db.FEEDBACK_CONFIRM: [
                CallbackQueryHandler(feedback.description, pattern=rf'^{db.BACK}$'),
                CallbackQueryHandler(feedback.send_email, pattern=rf'{db.YES}|{db.NO}'),
            ],
            
        },
        fallbacks=[
            CommandHandler('cancel', util.cancel),
            ],
        name="user_options",
        allow_reentry=True,
    )

    admin_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('admin', admin.menu),
    ],
        states={
            db.ADMIN_MENU: [
                CallbackQueryHandler(admin.close_feedback_id, pattern=rf'^{db.CLOSE_FEEDBACK_ID}$'),
                CallbackQueryHandler(admin.announcement_category, pattern=rf'^{db.ANNOUNCEMENT_CATEGORY}$'),
                CallbackQueryHandler(admin.popular_feedback, pattern=rf'^{db.POPULAR_FEEDBACK}$'),
            ],
            db.CLOSE_FEEDBACK_ID: [
                CallbackQueryHandler(admin.menu, pattern=rf'^{db.BACK}$'),
                MessageHandler(~Filters.command & Filters.text, admin.close_feedback_reason),
            ],
            db.CLOSE_FEEDBACK_REASON: [
                CallbackQueryHandler(admin.close_feedback_id, pattern=rf'^{db.BACK}$'),
                MessageHandler(~Filters.command & Filters.text, admin.close_feedback_confirm),
            ],
            db.CLOSE_FEEDBACK_CONFIRM: [
                CallbackQueryHandler(admin.close_feedback_reason, pattern=rf'^{db.BACK}$'),
                CallbackQueryHandler(admin.send_close_feedback_email, pattern=rf'{db.YES}|{db.NO}'),
            ],
            db.ANNOUNCEMENT_CATEGORY: [
                CallbackQueryHandler(admin.menu, pattern=rf'^{db.BACK}$'),
                CallbackQueryHandler(admin.announcement_message),
            ],
            db.ANNOUNCEMENT_MESSAGE: [
                CallbackQueryHandler(admin.announcement_category, pattern=rf'^{db.BACK}$'),
                MessageHandler(~Filters.command & Filters.text, admin.announcement_confirm),
            ],
            db.ANNOUNCEMENT_CONFIRM: [
                CallbackQueryHandler(admin.announcement_message, pattern=rf'^{db.BACK}$'),
                CallbackQueryHandler(admin.update_announcement, pattern=rf'{db.YES}|{db.NO}'),
            ],
        },
        fallbacks=[
            CommandHandler('cancel', util.cancel),
            ],
        name="user_options",
        allow_reentry=True,
    )

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    dp.add_handler(CallbackQueryHandler(feedback.like, pattern=rf'^{db.LIKES}_'))
    dp.add_handler(MessageHandler(Filters.regex(r'^/view_'), feedback.view))

    dp.add_handler(admin_conv_handler, 1)
    dp.add_handler(conv_handler, 1)
    
    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    # updater.start_polling()
    updater.start_webhook(listen="0.0.0.0",
                            port=int(PORT),
                            url_path=TOKEN)
    updater.bot.setWebhook('https://sutd-root-bot.herokuapp.com/' + TOKEN)

    # Run the bot until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

if __name__ == '__main__':
    main()