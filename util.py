import os
import re # Regex expression
import pytz # For timezone
import logging
# import py7zr # Compressing
import db
from bson import ObjectId # To create a unique objectId for pymongo
from datetime import datetime
from dateutil import parser
from dotenv import load_dotenv
from telegram import (
    ParseMode,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
)
from telegram.ext import (
    ConversationHandler,
)
from googleapiclient.http import MediaFileUpload
from auth import spreadsheet_service, drive_service
   
  


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()



# service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)

# Ensure that time is in SG timezone
def utc_to_sg(naive, timezone="Singapore"):
    return naive.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(timezone))

def cancel(update, context):
    # Workaround: To end conversations without notifying the user; Used to switch to anon chat without sending help message errorneously
    if update.message.text != "/cancel":
        return ConversationHandler.END

    first_name = update.message.from_user.first_name
    logger.info("User %s cancelled the conversation.", first_name)
    update.message.reply_text(
        'Bye! See you soon! Type /start to talk to me again', reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

def format_context(user_data, is_update=False):
    '''Converting the message into a dictionary'''
    now = utc_to_sg(datetime.utcnow())
    time = f"{now.strftime('%B %d, %Y')} at {now.strftime('%H:%M:%S')}"

    doc = user_data

    doc[db.TIME] = now
    doc[db.TIME_FORMATTED] = time

    if not is_update:
        doc[db.TIME_CREATED] = now
        doc['_id'] = str(ObjectId())
    else:
        # Remove '_id' if can find so that '_id' will not be updated which will throw an error
        doc.pop('_id', None)

    return doc

def format_feedback_content(feedback_doc):
    file_id = feedback_doc.get(db.FILE_ID)
    feedback_id = feedback_doc.get(db.FEEDBACK_ID)
    title = feedback_doc.get(db.TITLE)
    category = feedback_doc.get(db.CATEGORY)
    description = feedback_doc.get(db.DESCRIPTION)
    time_sent = feedback_doc.get(db.TIME_CREATED_FORMATTED)
    status = "Closed" if feedback_doc.get(db.IS_CLOSED) == True else "Pending"
    message = f'''<b>Title</b>: {title}
<b>Category</b>: {category}
<b>Description</b>: {description}
<b>Time Sent</b>: {time_sent}
<b>Status</b>: {status}

Click the ❤️ to let us know that you are facing a similar issue!
'''
    likes = feedback_doc.get(db.LIKES, [])
        
    keyboard = [
        [InlineKeyboardButton(f"❤️ ({len(likes)})", callback_data=f"{db.LIKES}_{feedback_id}"),]
        ]
    return message, keyboard, file_id

def format_categories_keyboard():
    '''Helps to display all feedback categories in a 2 column keyboard'''
    keyboard = [[InlineKeyboardButton("View All Feedback", url="https://docs.google.com/spreadsheets/d/1NG6q-00260JpkXuKK7BnJvYslWFOTkTo9RaHBtL0FmU/edit?usp=sharing")]]
    inner_keyboard = []

    # Display lists of feedback categories to user
    for i, el in enumerate(db.FEEDBACK_CATEGORIES):
        # For long words, append it directly to keyboard and continue with loop (Do NOT empty inner_keyboard!)
        if len(el) >= 16:
            keyboard.append([InlineKeyboardButton(el, callback_data=el)])
            continue
        inner_keyboard.append(InlineKeyboardButton(el, callback_data=el))
 
        if len(inner_keyboard) == 2:
            keyboard.append(inner_keyboard)
            inner_keyboard = []
        elif i == len(db.FEEDBACK_CATEGORIES)-1:
            keyboard.append(inner_keyboard)
    
    if inner_keyboard != [] and inner_keyboard not in keyboard:
        keyboard.append(inner_keyboard)

    return keyboard

def cancel(update, context):
    # Workaround: To end conversations without notifying the user; Used to switch to anon chat without sending help message errorneously
    if update.message.text != "/cancel":
        return ConversationHandler.END

    first_name = update.message.from_user.first_name
    logger.info("User %s cancelled the conversation.", first_name)
    update.message.reply_text(
        'Bye! See you soon! Type /start to talk to me again', reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

def handle_temp_data(update, context,  key, value=None, get=False, set=False, overwrite=False, send_error=True, send_to_dev=True):
    '''Safely handles setting / getting of values from temp_data by wrapping within a try-catch
    - If overwrite == True, temp_data will be reinitialised if it does not exist. Else, if temp_data does not exist, an error will be thrown.
    - If send_error == False && get == True, None will be returned and an error will only be sent to developer. Otherwise, an error will be sent to both user & developer.
    '''
    user_data = context.user_data
    try:
        if get:
            return user_data[db.TEMP_DATA][key]
        if set:
            if overwrite:
                if context.user_data.get(db.TEMP_DATA):
                    context.user_data[db.TEMP_DATA][key] = value
                else:
                    context.user_data[db.TEMP_DATA] = {key: value}
            else:
                context.user_data[db.TEMP_DATA][key] = value
    except Exception as e:
        name = update.effective_user.first_name
        username = update.effective_user.username
        chat_id = update.effective_user.id
        
        if get == True and send_error == False:
            message_error_to_admin = f"The following user, {name} (@{username}) received an error in handle_temp_data() while send_error == False\nKey:{key}\nError: {e}"
            
            if send_to_dev:
                context.bot.send_message(chat_id=db.DEVELOPER_CHAT_ID, text=message_error_to_admin, parse_mode=ParseMode.HTML)
            return None
        
        context.bot.send_message(chat_id=chat_id, text=db.ERROR_MESSAGE, parse_mode=ParseMode.HTML)
        message_error_to_admin = f"The following user, {name} (@{username}) received an error in handle_temp_data()\nKey:{key}\nError: {e}"
        context.bot.send_message(chat_id=db.DEVELOPER_CHAT_ID, text=message_error_to_admin, parse_mode=ParseMode.HTML)
        return ConversationHandler.END 
        
def get_feedback_doc(feedback_id):
    find = {db.FEEDBACK_ID: feedback_id}

    return db.all_feedback_col.find_one(find)


def write_to_col(update, context, id=None, col=None, data=None, is_update=False, is_delete=False, upsert=False):
    '''
    If is_chat_id = True, searches by chat_id. Else, searches by message_id
    If upsert == True, db will insert a document if no document exists and update if document exists
    '''

    now = utc_to_sg(datetime.utcnow())
    time = f"{now.strftime('%B %d, %Y')} at {now.strftime('%H:%M:%S')}"

    if col == db.all_profiles_col:
        find = {db.STUDENT_ID: id}
    elif col == db.all_feedback_col:
        find = {db.FEEDBACK_ID: id}


    if is_update:
        data.update(
            {
                db.TIME: now, 
                db.TIME_FORMATTED: time,
            }
        )

        col.update_one(find, {'$set': data}, upsert=upsert)
        return
    if is_delete:
        col.delete_many(find)
        return

    data.update(
        {
            db.TIME_CREATED: now, 
            db.TIME_CREATED_FORMATTED: time,
        }
    )

    if col == db.all_feedback_col:
        # Write to publicly available Google spreadsheet if inserting a new feedback
        file_id = data.get(db.FILE_ID)
        feedback_id = data[db.FEEDBACK_ID]
        title = data[db.TITLE]
        category = data[db.CATEGORY]
        description = data[db.DESCRIPTION]

        worksheet_name = 'All Feedback!'
        cell_range_insert = 'A2:D'
        values = (
            (feedback_id, title, category, description, time),
        )
        value_range_body = {
            'majorDimension': 'ROWS',
            'values': values
        }

        spreadsheet_service.spreadsheets().values().append(
            spreadsheetId=db.SPREADSHEET_ID,
            valueInputOption='USER_ENTERED',
            range=worksheet_name + cell_range_insert,
            body=value_range_body
        ).execute()

        # TODO: Upload file to google drive (WIP)
        # if file_id:
        #     file = context.bot.getFile(file_id)
        #     print(file)
        #     file.download(file.file_path)
        #     print(file)
        #     match = re.search(r'^https://api.telegram.org/file/', file.file_path)
        #     file_path_formatted = file.file_path[match.end():]
        #     filename = f"{feedback_id} - {title}"

        #     with open(file.file_path, 'rb') as f:
        #         print(f)

        #     metadata = {'name': file_path_formatted}
        #     media = MediaFileUpload(f"{filename}", chunksize=1024 * 1024, mimetype="image/png",  resumable=True)
        #     request = drive_service.files().create(body=metadata,
        #             media_body=media, fields='id').execute()
                    
        #     response = None
        #     while response is None:
        #         status, response = request.next_chunk()
        #         if status:
        #             print( "Uploaded %d%%." % int(status.progress() * 100))

        #     context.bot.send_message(chat_id=update.effective_chat.id, text="✅ File uploaded!")
   

    col.insert_one(data)

