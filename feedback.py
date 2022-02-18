import os
# import py7zr # Compressing
from telegram.ext.dispatcher import run_async # For parsing datetime
from dotenv import load_dotenv
from uuid import uuid4 # For security
import requests
import db
import util
import re
import user


from telegram import (
    ParseMode,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ConversationHandler,
)

# Load environment variables from .env file
load_dotenv()

MONGO_DB = os.environ.get('MONGO_DB')
MONGO_URL = os.environ.get('MONGO_URL')
BOT_ID = int(os.environ.get('BOT_ID'))
DEVELOPER_CHAT_ID = int(os.environ.get('DEVELOPER_CHAT_ID'))
TOKEN = os.environ.get('TOKEN')
VERIFIED_SHARER_CODE = os.environ.get('VERIFIED_SHARER_CODE')
SEND_VERIFICATION_EMAIL_URL = os.environ.get('SEND_VERIFICATION_EMAIL_URL')
SEND_FEEDBACK_EMAIL_URL = os.environ.get('SEND_FEEDBACK_EMAIL_URL')


def view(update, context):
    chat_id = update.effective_user.id
    
    match = re.search(r'^/view_', update.message.text)
    feedback_id = update.message.text[match.end():]
    feedback_doc = util.get_feedback_doc(feedback_id)

    if feedback_doc:
        message, keyboard, file_id = util.format_feedback_content(feedback_doc)
        reply_markup = InlineKeyboardMarkup(keyboard)

        if file_id:
            context.bot.send_photo(chat_id=chat_id, caption=message, photo=file_id, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        else:
            update.message.reply_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        message_error = "Hmmm, it seems that this feedback document no longer exists. Please press /start to continue."
        update.message.reply_text(text=message_error, parse_mode=ParseMode.HTML)

    return db.VIEW_FEEDBACK

def like(update, context):
    query = update.callback_query
    query.answer()
    chat_id = str(query.message.chat_id)

    message_loading = "Loading..."
    try:
        query.edit_message_text(text=message_loading, parse_mode=ParseMode.HTML)
    except:
        query.edit_message_caption(caption=message_loading, parse_mode=ParseMode.HTML)



    match = re.search(rf'^{db.LIKES}_', query.data)
    feedback_id = query.data[match.end():]
    feedback_doc = util.get_feedback_doc(feedback_id)
    likes = feedback_doc[db.LIKES]

    user.update_local_data(context.user_data, chat_id)
    student_id = context.user_data[db.STUDENT_ID]

    if student_id in likes:
        likes.remove(student_id)
        feedback_doc[db.LIKES] = likes
        feedback_doc[db.NUM_LIKES] -= 1
    else:
        likes.append(student_id)
        feedback_doc[db.LIKES] = likes
        feedback_doc[db.NUM_LIKES] += 1

    # Save to MongoDB
    util.write_to_col(update, context, id=feedback_id, col=db.all_feedback_col, data=feedback_doc, is_update=True)

    # Edit feedback message
    message, keyboard, file_id = util.format_feedback_content(feedback_doc)
    reply_markup = InlineKeyboardMarkup(keyboard)
    if file_id:
        query.edit_message_caption(caption=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

def title(update, context):
    query = update.callback_query

    message = f'''<b>New Feedback</b>
What is the title of your feedback?'''

    keyboard = [[InlineKeyboardButton("Back", callback_data=db.BACK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return db.FEEDBACK_TITLE

def description(update, context):
    query = update.callback_query

    # Used to handle 'Back' button
    if query:
        query.answer()
    else:
        util.handle_temp_data(update, context, key=db.TITLE, value=update.message.text, set=True, overwrite=True)

    message = "What is your feedback?"

    keyboard = [[InlineKeyboardButton("Back", callback_data=db.BACK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    else:
        update.message.reply_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return db.FEEDBACK_DESCRIPTION

def confirm(update, context):
    chat_id = update.effective_user.id
    is_photo = False
    
    if update.message.photo:
        is_photo = True
        photos = update.message.photo
        file_id = photos[0].file_id
        description = update.message.caption
        util.handle_temp_data(update, context, key=db.FILE_ID, value=file_id, set=True)
    else:
        description = update.message.text

    title = util.handle_temp_data(update, context, key=db.TITLE, get=True)
    util.handle_temp_data(update, context, key=db.DESCRIPTION, value=description, set=True)

    message = f'''<b>Confirmation</b>
<b>Title</b>: {title}
<b>Description</b>: {description}

Would you like to send the following feedback? You will <b>no longer be able to edit your feedback after this point</b>. 
Additionally, you will receive an email confirmation once you have successfully sent in your feedback.'''
    keyboard = [[InlineKeyboardButton("Back", callback_data=db.BACK)], 
    [InlineKeyboardButton("No", callback_data=db.NO),InlineKeyboardButton("Yes", callback_data=db.YES),]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_photo:
        context.bot.send_photo(chat_id=chat_id, caption=message, photo=file_id, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        update.message.reply_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return db.FEEDBACK_CONFIRM

def send_email(update, context):
    query = update.callback_query
    query.answer()

    if query.data == db.NO:
        message = "Feedback cancelled. Please press /start to continue"
        query.edit_message_text(text=message, parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    message_loading = "Sending feedback..."
    try:
        query.edit_message_text(text=message_loading, parse_mode=ParseMode.HTML)
    except:
        query.edit_message_caption(caption=message_loading, parse_mode=ParseMode.HTML)
        
    
    feedback_title = util.handle_temp_data(update, context, key=db.TITLE, get=True)
    feedback_description = util.handle_temp_data(update, context, key=db.DESCRIPTION, get=True)
    feedback_category = util.handle_temp_data(update, context, key=db.CATEGORY, get=True)
    feedback_file_id = util.handle_temp_data(update, context, key=db.FILE_ID, get=True, send_error=False, send_to_dev=False)

    student_id = context.user_data[db.STUDENT_ID]
    name = context.user_data[db.NAME]
    username = context.user_data[db.USERNAME]
    
    # Save feedback to MongoDB
    feedback_id = uuid4().hex[:16]
    data = {
        db.FEEDBACK_ID: feedback_id,
        db.TITLE: feedback_title,
        db.DESCRIPTION: feedback_description,
        db.FILE_ID: feedback_file_id,
        db.CATEGORY: feedback_category,
        db.SENDER_STUDENT_ID: student_id,
        db.SENDER_CHAT_ID: context.user_data[db.CHAT_ID],
        db.SENDER_NAME: name,
        db.SENDER_USERNAME: username,
        db.LIKES: [student_id],
        db.NUM_LIKES: 1,
    }

    if feedback_file_id:
        data[db.IS_PHOTO] = True
        data[db.FILE_ID] = feedback_file_id

    util.write_to_col(update, context, id=feedback_id, col=db.all_feedback_col, data=data)

    # Cloud function URL
    url = SEND_FEEDBACK_EMAIL_URL

    # Send email to ROOT informing of new feedback
    data = {
        db.STUDENT_ID: student_id,
        db.NAME: name,
        db.USERNAME: username,
        db.TITLE: feedback_title,
        db.DESCRIPTION: feedback_description,
        db.CATEGORY: feedback_category
    }
    context.dispatcher.run_async(requests.post, url, data)

    message = "Feedback sent! Please give us up to 5 working days to get back to you. Thank you! Press /start to continue\n\nNote: If you do not receive an email within 5min, please send in your feedback again. Thank you!"

    try:
        query.edit_message_text(text=message, parse_mode=ParseMode.HTML)
    except:
        query.edit_message_caption(caption=message, parse_mode=ParseMode.HTML)

    return ConversationHandler.END