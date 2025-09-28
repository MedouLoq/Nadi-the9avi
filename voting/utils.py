# utils.py
import requests
from django.conf import settings
import logging
import random

logger = logging.getLogger(__name__)

def send_sms_otp(phone_number, otp_code=None):
    """
    Send OTP via SMS using Chinguisoft SMS Validation API
    """
    try:
        # Get configuration from settings
        validation_key = getattr(settings, 'CHINGUISOFT_VALIDATION_KEY', 'ciSPuRWNvl4HUyUP')
        validation_token = getattr(settings, 'CHINGUISOFT_VALIDATION_TOKEN', '5r3mCILnkw2ht85UUGcSm3e7VedjcYIb')
        default_language = getattr(settings, 'SMS_DEFAULT_LANGUAGE', 'fr')  # 'ar' or 'fr'
        
        if not validation_key or not validation_token:
            logger.error("Chinguisoft credentials not configured")
            return False, "SMS service not configured"
        
        # Generate OTP if not provided
        if not otp_code:
            otp_code = str(random.randint(100000, 999999))
        
        # Format phone number for Mauritanian format (remove country code if present)
        formatted_phone = format_mauritanian_phone(phone_number)
        if not formatted_phone:
            logger.error(f"Invalid phone number format: {phone_number}")
            return False, "Invalid phone number format"
        
        # Chinguisoft API endpoint
        api_url = f"https://chinguisoft.com/api/sms/validation/{validation_key}"
        
        # Request headers
        headers = {
            'Validation-token': validation_token,
            'Content-Type': 'application/json',
        }
        
        # Request payload
        payload = {
            'phone': formatted_phone,
            'lang': default_language,
            'code': otp_code
        }
        
        # Make the API call
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        
        # Handle different response codes
        if response.status_code == 200:
            response_data = response.json()
            balance = response_data.get('balance', 'Unknown')
            logger.info(f"OTP sent successfully to {phone_number}. Balance: {balance}")
            return True, otp_code
            
        elif response.status_code == 422:
            # Validation error
            errors = response.json().get('errors', {})
            logger.error(f"Validation error for {phone_number}: {errors}")
            return False, "Invalid phone number or parameters"
            
        elif response.status_code == 429:
            # Too many requests
            logger.error(f"Rate limited for {phone_number}")
            return False, "Too many requests, please try again later"
            
        elif response.status_code == 401:
            # Unauthorized
            logger.error("Unauthorized: Invalid validation key or token")
            return False, "SMS service authentication failed"
            
        elif response.status_code == 402:
            # Payment required
            response_data = response.json()
            balance = response_data.get('balance', 0)
            logger.error(f"Insufficient balance: {balance}")
            return False, "SMS service balance insufficient"
            
        elif response.status_code == 503:
            # Service unavailable
            logger.error("Chinguisoft service temporarily unavailable")
            return False, "SMS service temporarily unavailable"
            
        else:
            logger.error(f"Unexpected response from Chinguisoft: {response.status_code} - {response.text}")
            return False, "SMS service error"
    
    except requests.exceptions.Timeout:
        logger.error(f"Timeout sending OTP to {phone_number}")
        return False, "SMS service timeout"
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error sending OTP to {phone_number}: {str(e)}")
        return False, "Network error"
    except Exception as e:
        logger.error(f"Unexpected error sending OTP to {phone_number}: {str(e)}")
        return False, "Unexpected error"


def format_mauritanian_phone(phone_number):
    """
    Format phone number for Mauritanian SMS API
    Expected format: 8 digits starting with 2, 3, or 4
    """
    # Remove all non-digit characters
    digits_only = ''.join(filter(str.isdigit, phone_number))
    
    # Handle international format (+222...)
    if digits_only.startswith('222') and len(digits_only) == 11:
        # Remove country code +222
        digits_only = digits_only[3:]
    elif digits_only.startswith('00222') and len(digits_only) == 13:
        # Remove international prefix 00222
        digits_only = digits_only[5:]
    
    # Validate Mauritanian phone number format
    if len(digits_only) == 8 and digits_only[0] in ['2', '3', '4']:
        return digits_only
    
    # Try to extract 8 digits starting with 2, 3, or 4
    if len(digits_only) >= 8:
        for i in range(len(digits_only) - 7):
            candidate = digits_only[i:i+8]
            if candidate[0] in ['2', '3', '4']:
                return candidate
    
    return None


def send_sms_notification(phone_number, message):
    """
    Send general SMS notifications
    """
    try:
        api_url = getattr(settings, 'SMS_API_URL', 'https://your-sms-api.com/send')
        api_key = getattr(settings, 'SMS_API_KEY', 'your-api-key')
        
        payload = {
            'api_key': api_key,
            'to': phone_number,
            'message': message,
            'sender_id': getattr(settings, 'SMS_SENDER_ID', 'VotingApp')
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Notification sent successfully to {phone_number}")
            return True
        else:
            logger.error(f"Failed to send notification to {phone_number}")
            return False
    
    except Exception as e:
        logger.error(f"Error sending notification to {phone_number}: {str(e)}")
        return False


# Alternative implementations for popular SMS providers:

def send_otp_twilio(phone_number, otp_code):
    """
    Twilio implementation example
    pip install twilio
    """
    try:
        from twilio.rest import Client
        
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        from_number = getattr(settings, 'TWILIO_PHONE_NUMBER', '')
        
        client = Client(account_sid, auth_token)
        
        message = f"Your verification code is: {otp_code}. Valid for 5 minutes."
        
        message = client.messages.create(
            body=message,
            from_=from_number,
            to=phone_number
        )
        
        logger.info(f"OTP sent via Twilio to {phone_number}, SID: {message.sid}")
        return True
    
    except Exception as e:
        logger.error(f"Twilio SMS error: {str(e)}")
        return False


def send_otp_firebase(phone_number, otp_code):
    """
    Firebase/FCM implementation example
    You would typically use Firebase Auth for this
    """
    # Firebase Auth typically handles OTP internally
    # This is just a placeholder for custom implementation
    pass


# Utility function to validate phone number format
def validate_phone_number(phone_number):
    """
    Validate phone number format
    """
    import re
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone_number)
    
    # Basic validation (adjust regex based on your country/region)
    if re.match(r'^\+?[1-9]\d{1,14}$', cleaned):
        return cleaned
    
    return None


# Rate limiting utility
from django.core.cache import cache
from django.utils import timezone

def check_rate_limit(identifier, max_attempts=5, window_minutes=10):
    """
    Check if identifier (phone number/IP) has exceeded rate limit
    """
    cache_key = f"rate_limit_{identifier}"
    attempts = cache.get(cache_key, 0)
    
    if attempts >= max_attempts:
        return False
    
    # Increment attempts
    cache.set(cache_key, attempts + 1, window_minutes * 60)
    return True