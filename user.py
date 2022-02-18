import logging
import functools
import db
import util
from datetime import date, datetime
from dateutil import parser # Convert to DateTime object
from copy import deepcopy

logger = logging.getLogger(__name__)

def update_local_data(local_data, chat_id):
    local_data.clear()

    user_data = db.all_profiles_col.find_one({'chat_id': str(chat_id)})
    if user_data:
        local_data.update(user_data)

def save_to_db(data, is_update=True):
    '''
    Saves user data to MongoDB
    '''

    # Remvoe all temp_data before saving user data
    data.pop(db.TEMP_DATA, None)

    data_to_save = deepcopy(data)

    doc = util.format_context(data_to_save, is_update=is_update)

    if is_update:
        db.all_profiles_col.update_one({db.STUDENT_ID: data_to_save[db.STUDENT_ID]}, {"$set": data_to_save})
    else:
        db.all_profiles_col.insert_one(doc)