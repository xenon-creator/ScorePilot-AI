import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

logger = logging.getLogger(__name__)

def send_score_notification(to_email: str, student_name: str, exam_title: str, total_score: float) -> bool:
    """
    Sends a score notification email to the student using Python's standard smtplib.
    If SMTP server configuration is incomplete or fails, logs a warning and returns False without crashing.
    """
    smtp_host = getattr(settings, "SMTP_HOST", os.getenv("SMTP_HOST", ""))
    smtp_port = int(getattr(settings, "SMTP_PORT", os.getenv("SMTP_PORT", "587")))
    smtp_user = getattr(settings, "SMTP_USER", os.getenv("SMTP_USER", ""))
    smtp_password = getattr(settings, "SMTP_PASSWORD", os.getenv("SMTP_PASSWORD", ""))
    smtp_from = getattr(settings, "SMTP_FROM_EMAIL", os.getenv("SMTP_FROM", "ScorePilot AI <noreply@scorepilot.ai>"))

    if not smtp_host or not smtp_user or not smtp_password:
        logger.warning(
            f"SMTP is not configured. Skipping sending email notification to {student_name} ({to_email}). "
            f"Result: {total_score} on '{exam_title}'"
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Exam Results Released: {exam_title}"
        msg["From"] = smtp_from
        msg["To"] = to_email

        text = (
            f"Hello {student_name},\n\n"
            f"Your results for '{exam_title}' have been released.\n"
            f"Total Score: {total_score}\n\n"
            f"Regards,\nScorePilot AI Team"
        )
        html = f"""
        <html>
          <body>
            <h2>Hello {student_name},</h2>
            <p>Your results for <strong>{exam_title}</strong> have been released.</p>
            <p>Total Score: <strong>{total_score}</strong></p>
            <br/>
            <p>Regards,<br/>ScorePilot AI Team</p>
          </body>
        </html>
        """

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [to_email], msg.as_string())
        
        logger.info(f"Score notification successfully sent to {to_email}")
        return True
    except Exception as e:
        logger.warning(f"Failed to send score notification email to {to_email}: {e}")
        return False
