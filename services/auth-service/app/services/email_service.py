# services/auth-service/app/services/email_service.py
"""Email service for sending notifications"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
from pathlib import Path

from ..config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails"""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD.get_secret_value() if settings.SMTP_PASSWORD else None
        self.from_email = settings.SMTP_FROM_EMAIL
        self.from_name = settings.SMTP_FROM_NAME
        
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """Send email"""
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            
            # Add text version
            if text_content:
                msg.attach(MIMEText(text_content, "plain"))
            
            # Add HTML version
            msg.attach(MIMEText(html_content, "html"))
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    async def send_verification_email(self, to_email: str, token: str) -> bool:
        """Send email verification link"""
        verification_url = settings.VERIFY_EMAIL_URL.format(
            frontend_url=settings.FRONTEND_URL,
            token=token
        )
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .button {{
                    display: inline-block;
                    padding: 12px 24px;
                    background: #4CAF50;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    margin: 20px 0;
                }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Agriculture AI Platform</h1>
                </div>
                <div class="content">
                    <h2>Verify Your Email Address</h2>
                    <p>Thank you for registering! Please verify your email address to get started.</p>
                    <a href="{verification_url}" class="button">Verify Email Address</a>
                    <p>Or copy this link: <a href="{verification_url}">{verification_url}</a></p>
                    <p>This link will expire in 7 days.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2024 Agriculture AI Platform. All rights reserved.</p>
                    <p>This is an automated message, please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Welcome to Agriculture AI Platform!
        
        Please verify your email address by visiting:
        {verification_url}
        
        This link will expire in 7 days.
        """
        
        return await self.send_email(
            to_email,
            "Verify Your Email Address",
            html_content,
            text_content
        )
    
    async def send_password_reset_email(self, to_email: str, token: str) -> bool:
        """Send password reset link"""
        reset_url = settings.RESET_PASSWORD_URL.format(
            frontend_url=settings.FRONTEND_URL,
            token=token
        )
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #ff9800; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .button {{
                    display: inline-block;
                    padding: 12px 24px;
                    background: #ff9800;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    margin: 20px 0;
                }}
                .warning {{ background: #fff3e0; padding: 15px; border-left: 4px solid #ff9800; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset Request</h1>
                </div>
                <div class="content">
                    <p>We received a request to reset your password. Click the button below to create a new password:</p>
                    <a href="{reset_url}" class="button">Reset Password</a>
                    <div class="warning">
                        <strong>⚠️ Security Notice</strong>
                        <p>If you didn't request this, please ignore this email. Your password will remain unchanged.</p>
                    </div>
                    <p>Or copy this link: <a href="{reset_url}">{reset_url}</a></p>
                    <p>This link will expire in 24 hours.</p>
                </div>
                <div class="footer">
                    <p>&copy; 2024 Agriculture AI Platform. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Password Reset Request
        
        We received a request to reset your password. Visit this link to create a new password:
        {reset_url}
        
        This link will expire in 24 hours.
        
        If you didn't request this, please ignore this email.
        """
        
        return await self.send_email(
            to_email,
            "Reset Your Password",
            html_content,
            text_content
        )
    
    async def send_welcome_email(self, to_email: str, username: str) -> bool:
        """Send welcome email after verification"""
        dashboard_url = f"{settings.FRONTEND_URL}/dashboard"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .feature {{ margin: 20px 0; padding: 10px; background: #f5f5f5; border-radius: 4px; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Agriculture AI Platform, {username}!</h1>
                </div>
                <div class="content">
                    <p>Your email has been verified. You're now ready to start using the platform!</p>
                    
                    <div class="feature">
                        <strong>📱 Mobile App</strong>
                        <p>Download our mobile app for on-the-go disease detection.</p>
                    </div>
                    
                    <div class="feature">
                        <strong>🌿 AI Disease Detection</strong>
                        <p>Upload plant photos and get instant disease diagnosis.</p>
                    </div>
                    
                    <div class="feature">
                        <strong>📊 Analytics Dashboard</strong>
                        <p>Track your farm's health and disease patterns.</p>
                    </div>
                    
                    <a href="{dashboard_url}" class="button">Go to Dashboard</a>
                </div>
                <div class="footer">
                    <p>&copy; 2024 Agriculture AI Platform. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(
            to_email,
            "Welcome to Agriculture AI Platform!",
            html_content
        )


# Global email service instance
email_service = EmailService()