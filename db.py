import os
from datetime import date
from typing import List
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

MONGO_DB = os.environ.get('MONGO_DB')
MONGO_URL = os.environ.get('MONGO_URL')
DEVELOPER_CHAT_ID = os.environ.get('DEVELOPER_CHAT_ID')
CLIENT_SECRET_FILE = os.environ.get('CLIENT_SECRET_FILE')
API_NAME = os.environ.get('API_NAME')
API_VERSION = os.environ.get('API_VERSION')
SCOPES = os.environ.get('SCOPES').split(",")
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
client = MongoClient(MONGO_URL, tlsCAFile=certifi.where())
database = client[MONGO_DB]

#MongoDB
ALL_PROFILES = "all_profiles"
ALL_FEEDBACK = "all_feedback"
ADMIN_UPDATES = "admin_updates"

all_profiles_col = database[ALL_PROFILES]
all_feedback_col = database[ALL_FEEDBACK]
admin_updates_col = database[ADMIN_UPDATES]

# Admin
ADMIN_IDS = ["295921684", "703800195", "767642353", "1178458197", "1243726422", "469198116"] # Sean, Sky, Oakarr, Darren, Zhuo Xuan, Marcus

# Generic constants
TEMP_DATA = "temp_data"
BACK = "back"
NO = "no"
YES = "yes"

# Feedback Categories
FEEDBACK_CATEGORIES = ["Academics", "Canteen", "Career", "Fifth Row", "Infrastructure", "Others"]
START_VERIFIED_PATTERN = "|".join(FEEDBACK_CATEGORIES)

# Conversation Flow
START = "start"
START_VERIFIED = "start_verified"
SEND_EMAIL = "send_email"
VERIFY_OTP = "verify_otp"
VIEW_CATEGORY = "view_category"
VIEW_FEEDBACK = "view_feedback"
FEEDBACK_TITLE = "feedback_title"
FEEDBACK_DESCRIPTION = "feedback_description"
FEEDBACK_CONFIRM = "feedback_confirm"

# Keys for user document
CHAT_ID = "chat_id"
NAME = "name"
USERNAME = "username"
STUDENT_ID = "student_id"
OTP = "otp"
OTP_EXPIRY = 300
OTP_OBJECT = "otp_object"
IS_ADMIN = "is_admin"
TIME = "time"
TIME_FORMATTED = "time_formatted"
TIME_CREATED = "time_created"
TIME_CREATED_FORMATTED = "time_created_formatted"

# Keys for feedback document
FEEDBACK_ID = "feedback_id"
TITLE = "title"
DESCRIPTION = "description"
CATEGORY = "category"
SENDER_CHAT_ID = "sender_chat_id"
SENDER_NAME = "sender_name"
SENDER_USERNAME = "sender_username"
SENDER_STUDENT_ID = "sender_student_id"
LIKES = "likes"
NUM_LIKES = "num_likes"
SIMILAR_ISSUES = "similar_issues"
IS_CLOSED = "is_closed"
CLOSED_BY = "closed_by"
FILE_ID = "file_id"
IS_PHOTO = "is_photo"

# Keys for admin announcements
DOCUMENT_ID = "document_id"
ADMIN_CHAT_ID = "admin_chat_id"
ADMIN_NAME = "admin_name"
ADMIN_USERNAME = "admin_username"
ADMIN_STUDENT_ID = "admin_student_id"

# Admin Flow
ADMIN_MENU = "admin_menu"
POPULAR_FEEDBACK = "popular_feedback"
CLOSE_FEEDBACK_ID = "close_feedback_id"
CLOSE_FEEDBACK_REASON = "close_feedback_reason"
CLOSE_FEEDBACK_CONFIRM = "close_feedback_confirm"
ANNOUNCEMENT_CATEGORY = "announcement_category"
ANNOUNCEMENT_MESSAGE = "announcement_message"
ANNOUNCEMENT_CONFIRM = "announcement_confirm"




ERROR_MESSAGE = "An error occurred. Try typing /cancel followed by /start to reset the bot. If this does not fix the error, please try again later."
