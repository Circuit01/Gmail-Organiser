import os
import pickle
import imaplib
import email
from email.header import decode_header
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from nltk import word_tokenize, pos_tag

# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Provide the path to the credentials.json file from an environment variable
CREDENTIALS_PATH = os.getenv('CREDENTIALS_PATH')

def authenticate_gmail():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def fetch_emails():
    creds = authenticate_gmail()
    if not creds:
        print("Failed to authenticate with Gmail")
        return

    # Get the access token and use it with imaplib
    access_token = creds.token

    # Create an IMAP client
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    auth_string = f"user={creds.client_id}\1auth=Bearer {access_token}\1\1"
    mail.authenticate("XOAUTH2", lambda x: auth_string)

    mail.select('inbox')

    status, messages = mail.search(None, 'ALL')
    messages = messages[0].split()

    categories = ['work', 'personal', 'travel']
    for category in categories:
        if not os.path.exists(category):
            os.makedirs(category)

    for mail_id in messages:
        _, msg = mail.fetch(mail_id, '(RFC822)')
        for response_part in msg:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject, encoding = decode_header(msg['subject'])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else 'utf-8')

                body = ''
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body += part.get_payload(decode=True).decode()

                tokens = word_tokenize(body)
                tagged = pos_tag(tokens)
                categories_found = []
                for word, pos in tagged:
                    if pos in ['NN', 'NNS']:  # Nouns
                        if word.lower() in categories:
                            categories_found.append(word.lower())

                for category in categories_found:
                    mail.store(mail_id, '+X-GM-LABELS', category)
                    for part in msg.walk():
                        if part.get_content_maintype() == 'multipart':
                            continue
                        if part.get('Content-Disposition') is None:
                            continue
                        filename = part.get_filename()
                        if filename:
                            filepath = os.path.join(category, filename)
                            if not os.path.isfile(filepath):
                                with open(filepath, 'wb') as fp:
                                    fp.write(part.get_payload(decode=True))

    mail.close()
    mail.logout()

if __name__ == '__main__':
    fetch_emails()
