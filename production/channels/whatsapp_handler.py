"""
WhatsApp Integration Handler for Customer Success FTE.

This module handles WhatsApp messaging via Twilio API for receiving
and sending support messages with proper formatting and rate limiting.

Features:
- Twilio WhatsApp API integration
- Webhook validation for security
- Message splitting for length limits
- Media message support
- Rate limiting and error handling
"""

from twilio.rest import Client
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import PlainTextResponse
import hmac
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging
import re

logger = logging.getLogger(__name__)

# WhatsApp message length limits
WHATSAPP_MAX_LENGTH = 1600  # Recommended max for good UX
WHATSAPP_HARD_LIMIT = 4096  # Actual WhatsApp limit
SEGMENT_LENGTH = 160  # Standard SMS segment length


class WhatsAppHandler:
    """
    Handler for WhatsApp messaging via Twilio API.
    
    Manages webhook validation, message processing, and sending
    responses with proper formatting and length handling.
    """
    
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        whatsapp_number: str,
        webhook_verify_token: Optional[str] = None
    ):
        """
        Initialize WhatsApp handler with Twilio credentials.
        
        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            whatsapp_number: WhatsApp number in E.164 format (e.g., 'whatsapp:+14155238886')
            webhook_verify_token: Optional token for webhook verification
        """
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.whatsapp_number = whatsapp_number
        self.webhook_verify_token = webhook_verify_token
        
        # Initialize Twilio client
        self.client = Client(account_sid, auth_token)
        
        # Request validator for webhook security
        self.validator = RequestValidator(auth_token)
        
        logger.info(f"WhatsApp handler initialized for {whatsapp_number}")
    
    def validate_webhook(
        self,
        request: Request,
        signature: str,
        body: str
    ) -> bool:
        """
        Validate incoming webhook request from Twilio.
        
        This ensures the webhook is actually from Twilio and not
        a malicious actor.
        
        Args:
            request: FastAPI request object
            signature: X-Twilio-Signature header value
            body: Raw request body
            
        Returns:
            True if webhook is valid, False otherwise
        """
        try:
            # Get the full URL of the request
            url = str(request.url)
            
            # Validate the signature
            is_valid = self.validator.validate(
                uri=url,
                params=body,
                signature=signature
            )
            
            if is_valid:
                logger.debug("Webhook signature validated successfully")
            else:
                logger.warning("Webhook signature validation failed")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error validating webhook: {e}")
            return False
    
    def validate_webhook_token(
        self,
        verify_token: str,
        mode: str,
        challenge: str
    ) -> Optional[str]:
        """
        Validate webhook using Meta's verify token (for WhatsApp Cloud API).
        
        Args:
            verify_token: Token sent by Meta for verification
            mode: Webhook mode (should be 'subscribe')
            challenge: Challenge string to return
            
        Returns:
            Challenge string if valid, None otherwise
        """
        if mode == "subscribe" and verify_token == self.webhook_verify_token:
            logger.info("WhatsApp webhook verification successful")
            return challenge
        
        logger.warning("WhatsApp webhook verification failed")
        return None
    
    async def process_webhook(
        self,
        request: Request,
        signature: str,
        body: str
    ) -> Optional[Dict[str, Any]]:
        """
        Process incoming WhatsApp webhook from Twilio.
        
        Args:
            request: FastAPI request object
            signature: X-Twilio-Signature header
            body: Raw request body as form data
            
        Returns:
            Processed message dictionary or None if invalid
        """
        # Validate webhook signature
        if not self.validate_webhook(request, signature, body):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        try:
            # Parse form data
            form_data = await request.form()
            
            # Extract message details
            from_number = form_data.get('From', '')
            to_number = form_data.get('To', '')
            message_body = form_data.get('Body', '')
            message_sid = form_data.get('MessageSid', '')
            
            # Handle media messages
            media_urls = []
            media_content_types = []
            
            # Twilio sends media info as NumMedia, MediaUrl0, MediaContentType0, etc.
            num_media = int(form_data.get('NumMedia', 0))
            for i in range(num_media):
                media_url = form_data.get(f'MediaUrl{i}', '')
                media_type = form_data.get(f'MediaContentType{i}', '')
                
                if media_url:
                    media_urls.append(media_url)
                    media_content_types.append(media_type)
            
            # Clean phone numbers (remove 'whatsapp:' prefix if present)
            from_clean = from_number.replace('whatsapp:', '')
            to_clean = to_number.replace('whatsapp:', '')
            
            message_data = {
                'channel': 'whatsapp',
                'channel_message_id': message_sid,
                'customer_phone': from_clean,
                'customer_name': form_data.get('ProfileName', ''),  # WhatsApp profile name
                'content': message_body,
                'received_at': datetime.utcnow().isoformat(),
                'media': [
                    {'url': url, 'type': ctype}
                    for url, ctype in zip(media_urls, media_content_types)
                ],
                'metadata': {
                    'to': to_clean,
                    'from': from_number,
                    'num_media': num_media,
                    'sms_sid': form_data.get('SmsSid', ''),
                    'account_sid': form_data.get('AccountSid', '')
                }
            }
            
            logger.info(
                f"Received WhatsApp message from {from_clean}. "
                f"SID: {message_sid}, Length: {len(message_body)}"
            )
            
            return message_data
            
        except Exception as e:
            logger.error(f"Error processing WhatsApp webhook: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error processing webhook: {str(e)}"
            )
    
    def format_response(
        self,
        message: str,
        max_length: int = WHATSAPP_MAX_LENGTH
    ) -> List[str]:
        """
        Format response for WhatsApp with message splitting for length limits.
        
        WhatsApp has a 4096 character limit, but for better UX we recommend
        keeping messages under 1600 characters. Longer messages are split
        into multiple parts.
        
        Args:
            message: Original message content
            max_length: Maximum length per segment (default 1600)
            
        Returns:
            List of message segments
        """
        if not message:
            return []
        
        # If message fits in one segment, return as-is
        if len(message) <= max_length:
            return [message]
        
        # Split message into segments
        segments = []
        
        # Try to split at sentence boundaries first
        sentences = re.split(r'(?<=[.!?])\s+', message)
        current_segment = ""
        
        for sentence in sentences:
            # If a single sentence is too long, split by words
            if len(sentence) > max_length:
                # First, send any accumulated content
                if current_segment:
                    segments.append(current_segment)
                    current_segment = ""
                
                # Split long sentence by words
                words = sentence.split()
                current_word_segment = ""
                
                for word in words:
                    if len(current_word_segment) + len(word) + 1 <= max_length:
                        current_word_segment += (" " if current_word_segment else "") + word
                    else:
                        if current_word_segment:
                            segments.append(current_word_segment)
                        current_word_segment = word
                
                if current_word_segment:
                    current_segment = current_word_segment
            
            # Normal sentence - add to current segment if it fits
            elif len(current_segment) + len(sentence) + 1 <= max_length:
                current_segment += (" " if current_segment else "") + sentence
            
            # Sentence doesn't fit, start new segment
            else:
                if current_segment:
                    segments.append(current_segment)
                current_segment = sentence
        
        # Don't forget the last segment
        if current_segment:
            segments.append(current_segment)
        
        # Add segment indicators if multiple parts
        if len(segments) > 1:
            for i, segment in enumerate(segments):
                segments[i] = f"({i+1}/{len(segments)}) {segment}"
        
        logger.info(f"Split message into {len(segments)} segments")
        return segments
    
    async def send_message(
        self,
        to_number: str,
        message: str,
        media_url: Optional[str] = None,
        split_long_messages: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Send a WhatsApp message via Twilio.
        
        Args:
            to_number: Recipient phone number (with or without 'whatsapp:' prefix)
            message: Message content
            media_url: Optional URL of media to send (image, document, etc.)
            split_long_messages: Whether to split long messages automatically
            
        Returns:
            List of send results (one per segment if split)
        """
        # Ensure proper format
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'
        
        from_number = self.whatsapp_number
        if not from_number.startswith('whatsapp:'):
            from_number = f'whatsapp:{from_number}'
        
        results = []
        
        # Split message if needed
        if split_long_messages:
            segments = self.format_response(message)
        else:
            segments = [message]
        
        for i, segment in enumerate(segments):
            try:
                # Send with media if provided (only for first segment)
                if media_url and i == 0:
                    message_obj = self.client.messages.create(
                        from_=from_number,
                        to=to_number,
                        body=segment,
                        media_url=media_url
                    )
                else:
                    message_obj = self.client.messages.create(
                        from_=from_number,
                        to=to_number,
                        body=segment
                    )
                
                result = {
                    'success': True,
                    'channel_message_id': message_obj.sid,
                    'segment': i + 1,
                    'total_segments': len(segments),
                    'sent_at': datetime.utcnow().isoformat(),
                    'to': to_number,
                    'status': message_obj.status
                }
                
                logger.info(
                    f"Sent WhatsApp message segment {i+1}/{len(segments)} "
                    f"to {to_number}. SID: {message_obj.sid}"
                )
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Failed to send WhatsApp message segment {i+1}: {e}")
                results.append({
                    'success': False,
                    'error': str(e),
                    'segment': i + 1,
                    'total_segments': len(segments)
                })
        
        return results
    
    async def send_media_message(
        self,
        to_number: str,
        media_url: str,
        caption: str = "",
        media_type: str = "image"
    ) -> Dict[str, Any]:
        """
        Send a media message (image, document, video) via WhatsApp.
        
        Args:
            to_number: Recipient phone number
            media_url: URL of the media file
            caption: Optional caption for the media
            media_type: Type of media ('image', 'document', 'video')
            
        Returns:
            Send result dictionary
        """
        results = await self.send_message(
            to_number=to_number,
            message=caption,
            media_url=media_url
        )
        
        if results and results[0].get('success'):
            return results[0]
        elif results:
            return {'success': False, 'error': results[0].get('error', 'Unknown error')}
        else:
            return {'success': False, 'error': 'No results returned'}
    
    async def get_message_status(
        self,
        message_sid: str
    ) -> Dict[str, Any]:
        """
        Get the delivery status of a sent message.
        
        Args:
            message_sid: Twilio message SID
            
        Returns:
            Message status information
        """
        try:
            message = self.client.messages(message_sid).fetch()
            
            return {
                'channel_message_id': message.sid,
                'status': message.status,
                'to': message.to,
                'from': message.from_,
                'date_sent': message.date_sent.isoformat() if message.date_sent else None,
                'error_code': message.error_code,
                'error_message': message.error_message
            }
            
        except Exception as e:
            logger.error(f"Error getting message status: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_twiml_response(
        self,
        message: str,
        media_urls: Optional[List[str]] = None
    ) -> str:
        """
        Create a TwiML response for immediate reply to webhook.
        
        Use this when you want to reply immediately in the webhook handler
        rather than asynchronously.
        
        Args:
            message: Message to send
            media_urls: Optional list of media URLs
            
        Returns:
            TwiML XML string
        """
        response = MessagingResponse()
        msg = response.message(message)
        
        if media_urls:
            for url in media_urls:
                msg.media(url)
        
        return str(response)


# =============================================================================
# FASTAPI ROUTER FOR WHATSAPP WEBHOOKS
# =============================================================================

def create_whatsapp_webhook_router(handler: WhatsAppHandler) -> APIRouter:
    """
    Create a FastAPI router for WhatsApp webhook endpoints.
    
    Args:
        handler: WhatsAppHandler instance
        
    Returns:
        Configured APIRouter
    """
    router = APIRouter()
    
    @router.post("/whatsapp/webhook")
    async def whatsapp_webhook(request: Request):
        """
        Handle incoming WhatsApp messages from Twilio.
        """
        # Get signature from headers
        signature = request.headers.get('X-Twilio-Signature', '')
        
        # Get raw body
        body = await request.body()
        body_str = body.decode('utf-8')
        
        # Process webhook
        message_data = await handler.process_webhook(request, signature, body_str)
        
        if not message_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process message"
            )
        
        # Here you would typically:
        # 1. Publish to Kafka for async processing
        # 2. Return empty 200 (Twilio will retry if error)
        
        logger.info(f"Webhook processed successfully: {message_data['channel_message_id']}")
        
        # Return empty response (Twilio doesn't need TwiML for async processing)
        return PlainTextResponse("", status_code=200)
    
    @router.get("/whatsapp/webhook")
    async def whatsapp_webhook_verify(
        mode: str = "",
        verify_token: str = "",
        challenge: str = ""
    ):
        """
        Handle WhatsApp webhook verification (Meta Cloud API).
        """
        result = handler.validate_webhook_token(verify_token, mode, challenge)
        
        if result:
            return PlainTextResponse(result)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid verification token"
            )
    
    return router
