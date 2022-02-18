import os
from telegram.ext.dispatcher import run_async # For parsing datetime
from dotenv import load_dotenv
import requests
import user
import db
import util
from uuid import uuid4

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
SEND_FEEDBACK_EMAIL_URL = os.environ.get('SEND_FEEDBACK_EMAIL_URL')
SEND_CLOSE_FEEDBACK_EMAIL_URL = os.environ.get('SEND_CLOSE_FEEDBACK_EMAIL_URL')

def menu(update, context):
    first_name = update.message.from_user.first_name
    username = update.message.from_user.username
    chat_id = str(update.message.chat_id)

    user.update_local_data(context.user_data, chat_id)

    if context.user_data.get(db.STUDENT_ID) == None:
        message = "Sorry, please sign up for an account by pressing /start first"
        update.message.reply_text(text=message)
        return ConversationHandler.END
    elif chat_id not in db.ADMIN_IDS:
        return ConversationHandler.END 
    
    context.user_data[db.IS_ADMIN] = True
    context.user_data[db.USERNAME] = username
    user.save_to_db(context.user_data)

    message = f"Hi {first_name}, what would you like to do today?"

    keyboard = [
    [InlineKeyboardButton("View All Feedback", url="https://docs.google.com/spreadsheets/d/1NG6q-00260JpkXuKK7BnJvYslWFOTkTo9RaHBtL0FmU/edit?usp=sharing")],
    [InlineKeyboardButton("Popular Feedback", callback_data=db.POPULAR_FEEDBACK), InlineKeyboardButton("Close Feedback", callback_data=db.CLOSE_FEEDBACK_ID)],
    [InlineKeyboardButton("Update Announcement", callback_data=db.ANNOUNCEMENT_CATEGORY)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)  

    return db.ADMIN_MENU

def popular_feedback(update, context):
    chat_id = update.effective_user.id

    message = "<u><b>Most Popular Feedback</b></u>"

    for i, doc in enumerate(db.all_feedback_col.find().sort(db.NUM_LIKES, -1)):
        # NOTE: Added here so that I do not send 'Most Popular Feedback' twice in the event len(message) >= 3800 on the last index
        if message == "":
            message = "<u><b>Most Popular Feedback</b></u>"
        num_likes = doc.get(db.NUM_LIKES)
        title = doc.get(db.TITLE)
        feedback_id = doc.get(db.FEEDBACK_ID)
        message += f"\n{i+1}. {title} ({num_likes}❤️)\n<b>More Details</b>: /view_{feedback_id}\n"
        if len(message) >= 3800:
            context.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)
            message = ""
    
    if len(message) > 0:
        try:
            context.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)
        except Exception as e:
            message_error = f"Failed to send popular_feedback message to {chat_id}\nError is {e}"
            context.bot.send_message(chat_id=db.DEVELOPER_CHAT_ID, text=message_error, parse_mode=ParseMode.HTML)
        


def close_feedback_id(update, context):
    query = update.callback_query
    query.answer()

    message = "Please enter the ID of the feedback you would like to close"

    query.edit_message_text(text=message, parse_mode=ParseMode.HTML)

    return db.CLOSE_FEEDBACK_ID

def close_feedback_reason(update, context):
    query = update.callback_query
    # Handle 'Back' button
    if query:
        query.answer()
        feedback_id = util.handle_temp_data(update, context, key=db.FEEDBACK_ID, get=True)
    else:
        feedback_id = update.message.text
        # Save feedback_id into temp_data
        util.handle_temp_data(update, context, key=db.FEEDBACK_ID, value=feedback_id, set=True, overwrite=True)
        
    feedback_doc = util.get_feedback_doc(feedback_id)
    is_closed = feedback_doc.get(db.IS_CLOSED)
    if is_closed:
        message = "This feedback has already been closed. Press /start to continue."
        update.message.reply_text(text=message, parse_mode=ParseMode.HTML)
        return ConversationHandler.END 

    title = feedback_doc[db.TITLE]
    category = feedback_doc[db.CATEGORY]
    description = feedback_doc[db.DESCRIPTION]

    message = f'''<b>Title</b>: {title}
<b>Category</b>: {category}
<b>Description</b>: {description}

Why are you closing this feedback?'''
    keyboard = [[InlineKeyboardButton("Back", callback_data=db.BACK)],]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)  

    return db.CLOSE_FEEDBACK_REASON

def close_feedback_confirm(update, context):
    close_feedback_reason = update.message.text
    util.handle_temp_data(update, context, key=db.CLOSE_FEEDBACK_REASON, value=close_feedback_reason, set=True, overwrite=True)

    feedback_id = util.handle_temp_data(update, context, key=db.FEEDBACK_ID, get=True)
    feedback_doc = util.get_feedback_doc(feedback_id)

    message = f'''<b>Reason for closing feedback</b>: {close_feedback_reason}

Are you sure you would like to close this feedback? An email will be sent to the user who sent the feedback and all users who are currently experiencing a similar / the same issue.
'''
    keyboard = [[InlineKeyboardButton("Back", callback_data=db.BACK)],
    [InlineKeyboardButton("No", callback_data=db.NO), InlineKeyboardButton("Yes", callback_data=db.YES)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)  

    return db.CLOSE_FEEDBACK_CONFIRM

def send_close_feedback_email(update, context):
    query = update.callback_query
    query.answer()

    if query.data == db.NO:
        message = "Action cancelled. Please press /start to continue"
        query.edit_message_text(text=message, parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    chat_id = str(query.message.chat_id) # (NOT BOT)
    username = query.from_user.username
    first_name = query.message.chat.first_name
    admin_student_id = context.user_data[db.STUDENT_ID]

    message_loading = "Closing feedback..."
    query.edit_message_text(text=message_loading, parse_mode=ParseMode.HTML)

    close_feedback_reason = util.handle_temp_data(update, context, key=db.CLOSE_FEEDBACK_REASON, get=True)
    feedback_id = util.handle_temp_data(update, context, key=db.FEEDBACK_ID, get=True)
    feedback_doc = util.get_feedback_doc(feedback_id)
    title = feedback_doc[db.TITLE]
    category = feedback_doc[db.CATEGORY]
    description = feedback_doc[db.DESCRIPTION]

    likes = feedback_doc[db.LIKES]
    # Ensure that email is sent to admin too
    if admin_student_id not in likes:
        likes.append(admin_student_id)


    # Update feedback doc in MongoDB
    data = {
        db.CLOSE_FEEDBACK_REASON: close_feedback_reason,
        db.IS_CLOSED: True,
        db.CLOSED_BY: {
            db.ADMIN_STUDENT_ID: admin_student_id,
            db.ADMIN_CHAT_ID: chat_id,
            db.ADMIN_NAME: first_name,
            db.ADMIN_USERNAME: username,
        },
    }
    util.write_to_col(update, context, id=feedback_id, col=db.all_feedback_col, data=data, is_update=True)

    # Send email updating that feedback has been closed

    # Cloud function URL
    url = SEND_CLOSE_FEEDBACK_EMAIL_URL

    # Call cloud function send email with OTP to user's school email
    data = {
        db.LIKES: likes, # Everybody facing the same issue
        db.TITLE: title,
        db.DESCRIPTION: description,
        db.CATEGORY: category,
        db.CLOSE_FEEDBACK_REASON: close_feedback_reason,
    }
    context.dispatcher.run_async(requests.post, url, data)

    message = "Feedback closed! Press /start to continue"
    query.edit_message_text(text=message, parse_mode=ParseMode.HTML)
    return ConversationHandler.END

def announcement_category(update, context):
    '''Used to select the category in which the admin would like to change the update message for'''
    query = update.callback_query
    query.answer()

    keyboard = util.format_categories_keyboard()
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = "Which category would you like to update?"

    query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return db.ANNOUNCEMENT_CATEGORY

def announcement_message(update, context):
    query = update.callback_query
    query.answer()

    if query.data == db.BACK:
        pass
    else:
        util.handle_temp_data(update, context, key=db.CATEGORY, value=query.data, set=True, overwrite=True)
    
    category = util.handle_temp_data(update, context, key=db.CATEGORY, get=True)

    cursor_count = db.admin_updates_col.count_documents({})
    if cursor_count == 0:
        message = f"No admin updates for {category} yet"
    else:
        for doc in db.admin_updates_col.find().sort(db.TIME_CREATED, -1).limit(1):
            current_announcement = doc[category]
            message = f"<b>Current Admin Message</b>\n{current_announcement}"

        

    message += "\n\nPlease input in your new admin message"

    keyboard = [[InlineKeyboardButton("Back", callback_data=db.BACK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return db.ANNOUNCEMENT_MESSAGE

def announcement_confirm(update, context):
    new_announcement = update.message.text
    util.handle_temp_data(update, context, key=db.ANNOUNCEMENT_MESSAGE, value=new_announcement, set=True)

    message = f'''This is how your new announcement would look like:
{new_announcement}

Would you like to confirm the change?'''

    keyboard = [[InlineKeyboardButton("Back", callback_data=db.BACK)],
    [InlineKeyboardButton("No", callback_data=db.NO), InlineKeyboardButton("Yes", callback_data=db.YES)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(text=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    return db.ANNOUNCEMENT_CONFIRM

def update_announcement(update, context):
    query = update.callback_query
    query.answer()

    if query.data == db.NO:
        message = "Action cancelled. Please press /start to continue"
        query.edit_message_text(text=message, parse_mode=ParseMode.HTML)
        return ConversationHandler.END

    chat_id = str(query.message.chat_id) # (NOT BOT)
    username = query.from_user.username
    first_name = query.message.chat.first_name
    admin_student_id = context.user_data[db.STUDENT_ID]

    message_loading = "Updating announcement..."
    query.edit_message_text(text=message_loading, parse_mode=ParseMode.HTML)

    new_announcment = util.handle_temp_data(update, context, key=db.ANNOUNCEMENT_MESSAGE, get=True)
    category = util.handle_temp_data(update, context, key=db.CATEGORY, get=True)

    # Insert a new document
    latest_doc_list = list(db.admin_updates_col.find().sort(db.TIME_CREATED, -1).limit(1))
    document_id = uuid4().hex[:16]

    if len(latest_doc_list) == 0:
        data = {
            db.DOCUMENT_ID: document_id,
            category: new_announcment,
        }
    else:
        data = latest_doc_list[0]
        data[db.DOCUMENT_ID] = document_id
        data[category] = new_announcment

    util.write_to_col(update, context, id=document_id, col=db.admin_updates_col, data=data)

    message = "Announcement Updated! Press /start to continue"
    query.edit_message_text(text=message, parse_mode=ParseMode.HTML)

    return ConversationHandler.END


    











