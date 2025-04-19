from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuración del servidor de correo
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),  # Tu correo de Gmail
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),  # Tu contraseña de aplicación
    MAIL_FROM=os.getenv("MAIL_FROM"),         # Tu correo de Gmail
    MAIL_PORT=int(os.getenv("MAIL_PORT")),     # 587 para TLS
    MAIL_SERVER=os.getenv("MAIL_SERVER"),     # smtp.gmail.com
    MAIL_STARTTLS=True,                       # Usar TLS
    MAIL_SSL_TLS=False,                       # No usar SSL
    USE_CREDENTIALS=True                      # Usar credenciales
)

# Configuración para la solicitud de recuperación de contraseña
class EmailSchema(BaseModel):
    email: EmailStr

# Función para enviar el correo con el enlace de recuperación
async def send_reset_email(email: str, token: str):
    logger.debug(f"Preparando para enviar correo a: {email}")
    reset_url = f"http://localhost:5173/ResetPassword?token={token}"
    logger.debug(f"URL de recuperación: {reset_url}")

    message = MessageSchema(
    subject="Restablecer contraseña",
    recipients=[email],
    body=f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; backgraund-color: #ffff;">
        <h1 style="color: #d80000; font-size: 24px;">Fogones</h1>
        
        <h2 style="font-size: 20px; color: #333;">Restablecer contraseña</h2>
        <p style="font-size: 16px; color: #333;">Haz clic <a href="{reset_url}" style="color: #f47521; text-decoration: none;">aquí</a> para restablecer tu contraseña.</p>
        
        <p style="font-size: 14px; color: #666;">Si no solicitaste restablecer la contraseña y recibiste este correo, contáctanos para resolver este problema.</p>
        
        <hr style="border: 0; border-top: 1px solid #ddd; margin: 20px 0;">
        
        <div style="font-size: 12px; color: #999;">
            <p><strong>Fogones Restaurante Campestre</strong></p>
            
            <p>Este correo es enviado a {email} para<br>
            Restablecer la contraseña de su cuenta | Fogones Restaurante Campestre</p>
        </div>
    </div>
    """,
    subtype="html"
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message)
        logger.info(f"Correo enviado exitosamente a: {email}")
    except Exception as e:
        logger.error(f"Error al enviar el correo: {e}")
        raise