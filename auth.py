# auth.py
from __future__ import print_function
import os
from googleapiclient.discovery import build 
from google.oauth2 import service_account
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

SCOPES = os.environ.get('SCOPES').split(",")
CLIENT_SECRET_FILE = os.environ.get('CLIENT_SECRET_FILE')

credentials = service_account.Credentials.from_service_account_file(CLIENT_SECRET_FILE, scopes=SCOPES)
spreadsheet_service = build('sheets', 'v4', credentials=credentials)
drive_service = build('drive', 'v3', credentials=credentials)