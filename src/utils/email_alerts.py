# Créer src/utils/email_alerts.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailAlert:
    def __init__(self):
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.alert_email = os.getenv('ALERT_EMAIL')
    
    def send_alert(self, subject: str, body: str):
        """Envoie une alerte par email."""
        msg = MIMEMultipart()
        msg['From'] = self.smtp_user
        msg['To'] = self.alert_email
        msg['Subject'] = f"🚨 Dashboard Alert: {subject}"
        
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)