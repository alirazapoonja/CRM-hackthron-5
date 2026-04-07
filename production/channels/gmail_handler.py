"""
Gmail Integration Handler for Customer Success FTE.

This module handles Gmail API integration for receiving and sending
support emails with proper threading support.

Features:
- OAuth2 authentication with Gmail API
- Push notifications via Google Cloud Pub/Sub
- Message parsing with MIME support
- Threaded reply support for conversation continuity
"""

from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import pubsub_v1
from googleapiclient.errors import HttpError
import base64
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import json
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class GmailHandler:
    """
    Handler for Gmail API integration.
    
    Manages OAuth2 authentication, push notifications, message retrieval,
    and sending replies with proper threading support.
    """
    
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/pubsub'
    ]
    
    def __init__(
        self,
        credentials_path: str,
        project_id: str,
        topic_name: str
    ):
        """
        Initialize Gmail handler with credentials and Pub/Sub configuration.
        
        Args:
            credentials_path: Path to OAuth2 credentials JSON file
            project_id: Google Cloud project ID for Pub/Sub
            topic_name: Pub/Sub topic name for push notifications
        """
        self.credentials_path = Path(credentials_path)
        self.project_id = project_id
        self.topic_name = topic_name
        self.topic_full_name = f"projects/{project_id}/topics/{topic_name}"
        
        self.credentials = None
        self.service = None
        self.pubsub_client = None
        
        self._authenticate()
    
    def _authenticate(self) -> None:
        """
        Authenticate with Gmail API using OAuth2 credentials.
        
        Raises:
            FileNotFoundError: If credentials file not found
            ValueError: If credentials are invalid
        """
        try:
            # Try service account credentials first
            if self.credentials_path.suffix == '.json':
                self.credentials = service_account.Credentials.from_service_account_file(
                    str(self.credentials_path),
                    scopes=self.SCOPES
                )
            else:
                # OAuth2 user credentials
                self.credentials = Credentials.from_authorized_user_file(
                    str(self.credentials_path),
                    self.SCOPES
                )
            
            self.service = build('gmail', 'v1', credentials=self.credentials)
            self.pubsub_client = pubsub_v1.PublisherClient(
                credentials=self.credentials
            )
            
            logger.info("Successfully authenticated with Gmail API")
            
        except FileNotFoundError:
            logger.error(f"Credentials file not found: {self.credentials_path}")
            raise
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise
    
    async def setup_push_notifications(self) -> Dict[str, Any]:
        """
        Set up Gmail push notifications via Pub/Sub.
        
        This enables real-time processing of incoming support emails
        without polling.
        
        Returns:
            Dict with history_id and expiration timestamp
            
        Raises:
            HttpError: If setup fails
        """
        try:
            # Create Pub/Sub topic if it doesn't exist
            try:
                self.pubsub_client.create_topic(
                    request={"name": self.topic_full_name}
                )
                logger.info(f"Created Pub/Sub topic: {self.topic_full_name}")
            except Exception:
                # Topic may already exist
                logger.info(f"Using existing Pub/Sub topic: {self.topic_full_name}")
            
            # Create subscription for the topic
            subscription_name = f"{self.topic_name}-subscription"
            subscription_full_name = f"projects/{self.project_id}/subscriptions/{subscription_name}"
            
            try:
                self.pubsub_client.create_subscription(
                    request={
                        "name": subscription_full_name,
                        "topic": self.topic_full_name
                    }
                )
                logger.info(f"Created Pub/Sub subscription: {subscription_full_name}")
            except Exception:
                logger.info(f"Using existing Pub/Sub subscription: {subscription_full_name}")
            
            # Set up Gmail watch
            request = {
                'labelIds': ['INBOX', 'IMPORTANT'],
                'topicName': self.topic_full_name,
                'labelFilterAction': 'include'
            }
            
            response = self.service.users().watch(
                userId='me',
                body=request
            ).execute()
            
            history_id = response.get('historyId')
            expiration = response.get('expiration')
            
            logger.info(
                f"Gmail watch set up. History ID: {history_id}, "
                f"Expires: {datetime.fromtimestamp(int(expiration)/1000)}"
            )
            
            return {
                'history_id': history_id,
                'expiration': expiration,
                'topic': self.topic_full_name,
                'subscription': subscription_full_name
            }
            
        except HttpError as e:
            logger.error(f"Gmail watch setup failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Pub/Sub setup failed: {e}")
            raise
    
    async def process_notification(
        self,
        pubsub_message: pubsub_v1.types.PubsubMessage
    ) -> List[Dict[str, Any]]:
        """
        Process incoming Pub/Sub notification from Gmail.
        
        Args:
            pubsub_message: Pub/Sub message containing Gmail notification
            
        Returns:
            List of processed message dictionaries
        """
        try:
            # Decode Pub/Sub message data
            data_str = base64.b64decode(pubsub_message.data).decode('utf-8')
            data = json.loads(data_str)
            
            history_id = data.get('historyId')
            email_address = data.get('emailAddress')
            
            logger.info(
                f"Received Gmail notification. "
                f"History ID: {history_id}, Email: {email_address}"
            )
            
            # Get new messages since last history ID
            history = self.service.users().history().list(
                userId='me',
                startHistoryId=history_id,
                historyTypes=['messageAdded']
            ).execute()
            
            messages = []
            for record in history.get('history', []):
                for msg_added in record.get('messagesAdded', []):
                    msg_id = msg_added['message']['id']
                    message = await self.get_message(msg_id)
                    if message:
                        messages.append(message)
            
            logger.info(f"Processed {len(messages)} new messages")
            return messages
            
        except Exception as e:
            logger.error(f"Error processing notification: {e}")
            return []
    
    async def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch and parse a Gmail message.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Parsed message dictionary with headers, body, and metadata
        """
        try:
            msg = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Extract headers
            headers = msg['payload'].get('headers', [])
            header_dict = {h['name']: h['value'] for h in headers}
            
            # Extract body
            body = self._extract_body(msg['payload'])
            
            # Extract attachments info
            attachments = self._extract_attachments_info(msg['payload'])
            
            # Parse From header to get email and name
            from_header = header_dict.get('From', '')
            from_email = self._extract_email(from_header)
            from_name = self._extract_name(from_header)
            
            return {
                'channel': 'email',
                'channel_message_id': message_id,
                'thread_id': msg.get('threadId'),
                'customer_email': from_email,
                'customer_name': from_name,
                'subject': header_dict.get('Subject', ''),
                'to': header_dict.get('To', ''),
                'cc': header_dict.get('Cc', ''),
                'content': body,
                'received_at': datetime.utcnow().isoformat(),
                'labels': msg.get('labelIds', []),
                'attachments': attachments,
                'metadata': {
                    'headers': header_dict,
                    'snippet': msg.get('snippet', ''),
                    'internal_date': msg.get('internalDate', '')
                }
            }
            
        except HttpError as e:
            logger.error(f"Failed to get message {message_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing message {message_id}: {e}")
            return None
    
    def _extract_body(self, payload: Dict[str, Any]) -> str:
        """
        Extract the text body from a message payload.
        
        Args:
            payload: Gmail message payload
            
        Returns:
            Message body as string
        """
        # Try to get plain text body first
        if 'body' in payload and payload['body'].get('data'):
            body_data = payload['body']['data']
            return base64.urlsafe_b64decode(body_data).decode('utf-8')
        
        # Check multipart messages
        if 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                
                # Prefer plain text over HTML
                if mime_type == 'text/plain' and 'body' in part:
                    if part['body'].get('data'):
                        body_data = part['body']['data']
                        return base64.urlsafe_b64decode(body_data).decode('utf-8')
                
                # Fallback to HTML if no plain text
                if mime_type == 'text/html' and 'body' in part:
                    if part['body'].get('data'):
                        body_data = part['body']['data']
                        html_content = base64.urlsafe_b64decode(body_data).decode('utf-8')
                        # Simple HTML to text conversion
                        return self._html_to_text(html_content)
        
        return ''
    
    def _html_to_text(self, html: str) -> str:
        """
        Convert HTML to plain text (simple implementation).
        
        Args:
            html: HTML content
            
        Returns:
            Plain text content
        """
        # Remove script and style tags
        import re
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Remove all HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        # Clean up whitespace
        text = ' '.join(text.split())
        return text
    
    def _extract_attachments_info(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract attachment information from message payload.
        
        Args:
            payload: Gmail message payload
            
        Returns:
            List of attachment info dictionaries
        """
        attachments = []
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename') and part['body'].get('attachmentId'):
                    attachments.append({
                        'filename': part['filename'],
                        'mime_type': part.get('mimeType', ''),
                        'size': part['body'].get('size', 0),
                        'attachment_id': part['body']['attachmentId']
                    })
        
        return attachments
    
    def _extract_email(self, from_header: str) -> str:
        """
        Extract email address from From header.
        
        Args:
            from_header: From header value (e.g., "John Doe <john@example.com>")
            
        Returns:
            Email address
        """
        import re
        match = re.search(r'<([^>]+)>', from_header)
        if match:
            return match.group(1)
        return from_header.strip()
    
    def _extract_name(self, from_header: str) -> str:
        """
        Extract name from From header.
        
        Args:
            from_header: From header value
            
        Returns:
            Name (or empty string if not found)
        """
        import re
        match = re.search(r'^([^<]+)<', from_header)
        if match:
            return match.group(1).strip()
        return ''
    
    async def send_reply(
        self,
        thread_id: str,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        in_reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a reply email with proper threading support.
        
        Args:
            thread_id: Gmail thread ID to reply to
            to_email: Recipient email address
            subject: Email subject (Re: will be added if needed)
            body: Email body content
            cc: CC email addresses (optional)
            in_reply_to: Message ID to reply to (optional)
            
        Returns:
            Sent message information including Gmail message ID
        """
        try:
            # Create MIME message
            message = MIMEMultipart('alternative')
            message['to'] = to_email
            message['from'] = 'me'  # Will be replaced by Gmail
            message['subject'] = subject
            message['threadId'] = thread_id
            
            # Add In-Reply-To header for threading
            if in_reply_to:
                message['In-Reply-To'] = in_reply_to
                message['References'] = in_reply_to
            
            # Add CC if provided
            if cc:
                message['cc'] = cc
            
            # Add plain text and HTML versions
            message.attach(MIMEText(body, 'plain'))
            message.attach(MIMEText(body.replace('\n', '<br>'), 'html'))
            
            # Encode the message
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode('utf-8')
            
            # Send the message
            sent_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message, 'threadId': thread_id}
            ).execute()
            
            # Get the full message to return details
            full_message = await self.get_message(sent_message['id'])
            
            logger.info(f"Sent reply to {to_email} in thread {thread_id}")
            
            return {
                'success': True,
                'channel_message_id': sent_message['id'],
                'thread_id': sent_message['threadId'],
                'sent_at': datetime.utcnow().isoformat(),
                'to': to_email,
                'subject': subject
            }
            
        except HttpError as e:
            logger.error(f"Failed to send reply: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Error sending reply: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def send_new_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a new email (not a reply).
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body content
            cc: CC email addresses (optional)
            
        Returns:
            Sent message information
        """
        # For new emails, thread_id will be generated by Gmail
        return await self.send_reply(
            thread_id='',  # Empty for new thread
            to_email=to_email,
            subject=subject,
            body=body,
            cc=cc
        )
    
    async def stop_notifications(self) -> None:
        """
        Stop Gmail push notifications.
        
        Should be called during cleanup or when reconfiguring.
        """
        try:
            self.service.users().stop().execute()
            logger.info("Stopped Gmail push notifications")
        except Exception as e:
            logger.error(f"Error stopping notifications: {e}")
    
    async def refresh_watch(self) -> Dict[str, Any]:
        """
        Refresh the Gmail watch before it expires.
        
        Gmail watches expire after 7 days. Call this periodically.
        
        Returns:
            New watch information
        """
        return await self.setup_push_notifications()


# =============================================================================
# POLLING FALLBACK (for development/testing)
# =============================================================================

class GmailPollingHandler(GmailHandler):
    """
    Fallback handler that polls Gmail instead of using push notifications.
    
    Useful for development and testing when Pub/Sub setup is complex.
    """
    
    def __init__(
        self,
        credentials_path: str,
        project_id: str,
        topic_name: str,
        poll_interval_seconds: int = 60
    ):
        """
        Initialize polling handler.
        
        Args:
            credentials_path: Path to OAuth2 credentials
            project_id: Google Cloud project ID
            topic_name: Pub/Sub topic name (not used in polling mode)
            poll_interval_seconds: How often to check for new messages
        """
        super().__init__(credentials_path, project_id, topic_name)
        self.poll_interval = poll_interval_seconds
        self.last_history_id: Optional[str] = None
    
    async def poll_for_messages(self) -> List[Dict[str, Any]]:
        """
        Poll Gmail for new messages since last check.
        
        Returns:
            List of new messages
        """
        try:
            # Get profile to find latest history ID
            profile = self.service.users().getProfile().execute()
            current_history_id = profile.get('historyId')
            
            if not self.last_history_id:
                self.last_history_id = current_history_id
                return []
            
            # Get messages since last history ID
            history = self.service.users().history().list(
                userId='me',
                startHistoryId=self.last_history_id,
                historyTypes=['messageAdded']
            ).execute()
            
            messages = []
            for record in history.get('history', []):
                for msg_added in record.get('messagesAdded', []):
                    msg_id = msg_added['message']['id']
                    message = await self.get_message(msg_id)
                    if message:
                        messages.append(message)
            
            self.last_history_id = current_history_id
            
            if messages:
                logger.info(f"Polled {len(messages)} new messages")
            
            return messages
            
        except Exception as e:
            logger.error(f"Error polling Gmail: {e}")
            return []
