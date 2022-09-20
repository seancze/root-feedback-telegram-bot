# root-feedback-telegram-bot

## Deployment

### Prerequisite files

1. A `.env` file (Contact @seancze on Telegram for more details)
2. A `client_secret.json` file which you ought to be able to retrieve by following [this Medium link](https://owaisqureshi.medium.com/access-google-sheets-api-in-python-using-service-account-3a0c6d89d5fc)

### Deployment

1. Download required packages - `pip -r requirements.txt`
2. Deploy the bot - `python bot.py`

Note: To deploy on DigitalOcean, follow [this](https://www.infotelbot.com/2020/12/Host-Telegram-Bot-on-Digital-Ocean.html) very helpful tutorial

## Current Features

1. Create a new feedback
2. Add feedback to publicly viewable Google Sheet
3. Send feedback to school email
4. Send picture
5. Upvote feedback
6. View all feedback sorted by popularity [ADMIN]
7. Close feedback [ADMIN]
8. Update announcement for feedback category [ADMIN]

## To Do

- [ ] Upload pictures into Google Drive
- [ ] Migrate to Google Cloud

## Future Dev

- [ ] Admin Feature: Ability to link similar issues together so that users can see
