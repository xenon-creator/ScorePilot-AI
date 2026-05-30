import os
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

class NotificationService:
    @staticmethod
    def generate_html_email(
        student_name: str,
        exam_title: str,
        total_score: float,
        max_marks: float,
        breakdown: list[dict]
    ) -> str:
        """Generates a premium, layout-responsive HTML email for score release."""
        
        # Build question breakdown table rows
        rows_html = ""
        for idx, item in enumerate(breakdown):
            bg_color = "#16161c" if idx % 2 == 0 else "#1d1d26"
            q_num = item.get("question_number", idx + 1)
            q_text = item.get("question_text", f"Question {q_num}")
            if len(q_text) > 80:
                q_text = q_text[:80] + "..."
            score = item.get("score", 0.0)
            max_m = item.get("max_marks", 0.0)
            feedback = item.get("feedback", "No specific feedback.")
            
            rows_html += f"""
            <tr style="background-color: {bg_color}; color: #ffffff;">
                <td style="padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.06); font-family: monospace; font-size: 13px;">Q{q_num}</td>
                <td style="padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 13px;">
                    <div style="font-weight: 600; color: #e2e8f0; margin-bottom: 4px;">{q_text}</div>
                    <div style="font-size: 11px; color: #94a3b8; font-style: italic;">{feedback}</div>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.06); text-align: right; font-weight: bold; font-size: 14px; color: #22d3ee;">{score} <span style="font-size: 11px; color: #64748b; font-weight: normal;">/ {max_m}</span></td>
            </tr>
            """

        percentage = round((total_score / max_marks) * 100, 1) if max_marks else 0.0
        badge_color = "#10b981" if percentage >= 50 else "#f59e0b"
        badge_bg = "rgba(16, 185, 129, 0.1)" if percentage >= 50 else "rgba(245, 158, 11, 0.1)"

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Exam Results Released</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #0b0f19; padding: 40px 10px;">
        <tr>
            <td align="center">
                <table width="100%" max-width="600" style="max-width: 600px; width: 100%; border-collapse: collapse; background-color: #111827; border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 30px; text-align: center; border-bottom: 1px solid rgba(255, 255, 255, 0.06); background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);">
                            <div style="display: inline-flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                                <span style="font-size: 20px; font-weight: bold; color: #ffffff; letter-spacing: -0.5px;">ScorePilot<span style="color: #22d3ee;">AI</span></span>
                            </div>
                            <h1 style="margin: 0; font-size: 20px; font-weight: 700; color: #ffffff; letter-spacing: -0.5px;">Exam Results Released</h1>
                        </td>
                    </tr>

                    <!-- Body Content -->
                    <tr>
                        <td style="padding: 35px 30px;">
                            <p style="margin: 0 0 16px; font-size: 15px; line-height: 24px; color: #94a3b8;">
                                Hello <strong style="color: #ffffff;">{student_name}</strong>,
                            </p>
                            <p style="margin: 0 0 24px; font-size: 15px; line-height: 24px; color: #94a3b8;">
                                Your answers for <strong style="color: #ffffff;">{exam_title}</strong> have been graded and reviewed. Here is your evaluation breakdown:
                            </p>

                            <!-- Score Card -->
                            <div style="background-color: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.04); border-radius: 12px; padding: 20px; margin-bottom: 30px; text-align: center;">
                                <div style="font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Overall Score</div>
                                <div style="font-size: 42px; font-weight: 800; color: #ffffff; margin-bottom: 8px;">
                                    {total_score} <span style="font-size: 20px; color: #475569; font-weight: 600;">/ {max_marks}</span>
                                </div>
                                <span style="display: inline-block; padding: 6px 12px; font-size: 12px; font-weight: 600; color: {badge_color}; background-color: {badge_bg}; border-radius: 9999px;">
                                    Score Percentage: {percentage}%
                                </span>
                            </div>

                            <!-- Breakdown Table -->
                            <h3 style="margin: 0 0 12px; font-size: 14px; font-weight: 600; color: #cbd5e1; text-transform: uppercase; letter-spacing: 0.5px;">Question Breakdown</h3>
                            <table width="100%" style="border-collapse: collapse; margin-bottom: 30px;">
                                <thead>
                                    <tr style="background-color: rgba(255,255,255,0.04); text-align: left; color: #94a3b8; font-size: 11px; text-transform: uppercase;">
                                        <th style="padding: 10px 12px; width: 60px;">Q#</th>
                                        <th style="padding: 10px 12px;">Details</th>
                                        <th style="padding: 10px 12px; text-align: right; width: 80px;">Marks</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rows_html}
                                </tbody>
                            </table>

                            <!-- CTA Button -->
                            <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin-top: 10px;">
                                <tr>
                                    <td align="center">
                                        <a href="{settings.STUDENT_PORTAL_URL}/dashboard" target="_blank" style="display: inline-block; padding: 14px 30px; font-size: 14px; font-weight: 600; color: #000000; background-color: #22d3ee; border-radius: 12px; text-decoration: none; box-shadow: 0 4px 12px rgba(34, 211, 238, 0.25); transition: background-color 0.2s;">
                                            Go to Student Portal
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 24px; text-align: center; border-t: 1px solid rgba(255,255,255,0.06); background-color: #0b0f17;">
                            <p style="margin: 0 0 6px; font-size: 12px; color: #475569;">
                                This is an automated notification from ScorePilot AI. Please do not reply.
                            </p>
                            <p style="margin: 0; font-size: 11px; color: #334155;">
                                &copy; {datetime.datetime.utcnow().year} ScorePilot AI. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    @staticmethod
    def send_score_release_email(
        student_name: str,
        student_email: str,
        exam_title: str,
        total_score: float,
        max_marks: float,
        breakdown: list[dict]
    ) -> bool:
        """Sends score release email via SMTP or falls back to writing local HTML sandboxes."""
        html_content = NotificationService.generate_html_email(
            student_name=student_name,
            exam_title=exam_title,
            total_score=total_score,
            max_marks=max_marks,
            breakdown=breakdown
        )
        
        # Check if SMTP details are fully configured
        if settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD:
            try:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = f"Exam Results Released: {exam_title}"
                msg['From'] = settings.SMTP_FROM_EMAIL
                msg['To'] = student_email
                
                # Render clean fallback plain text
                plain_text = f"Hello {student_name},\n\nYour results for '{exam_title}' have been released. Total Score: {total_score}/{max_marks}.\nPlease log in to the student portal to review the detailed feedback."
                msg.attach(MIMEText(plain_text, 'plain'))
                msg.attach(MIMEText(html_content, 'html'))
                
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.sendmail(settings.SMTP_FROM_EMAIL, [student_email], msg.as_string())
                return True
            except Exception as e:
                # Log exception and fall back to saving locally
                import logging
                logging.getLogger(__name__).error(f"Failed to send email via SMTP: {e}. Writing to local mailbox sandbox instead.")
        
        # Local Sandbox Fallback
        try:
            # Create local sandbox directory inside backend
            # Note: Cwd is d:\projects\ai assisant\backend
            mailbox_dir = os.path.join("mailboxes", "score_releases")
            os.makedirs(mailbox_dir, exist_ok=True)
            
            safe_name = student_name.replace(" ", "_").lower()
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_name}_{timestamp}.html"
            filepath = os.path.join(mailbox_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
                
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to write score release email to local sandbox: {e}")
            return False
