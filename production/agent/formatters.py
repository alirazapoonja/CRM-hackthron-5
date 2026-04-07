"""
Channel-aware response formatting for Customer Success FTE.

This module provides functions to format agent responses appropriately
for each communication channel (email, WhatsApp, web form).

Each channel has different:
- Tone requirements (formal vs. conversational)
- Length limits
- Formatting conventions
- Emoji usage policies
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# CHANNEL CONFIGURATION
# =============================================================================

CHANNEL_CONFIGS = {
    "email": {
        "max_length": 2000,
        "max_words": 500,
        "tone": "formal",
        "requires_greeting": True,
        "requires_signature": True,
        "allows_emojis": False,
        "paragraph_spacing": "\n\n",
        "line_width": 80,
    },
    "whatsapp": {
        "max_length": 1600,
        "preferred_length": 160,
        "tone": "conversational",
        "requires_greeting": False,
        "requires_signature": False,
        "allows_emojis": True,
        "max_emojis": 2,
        "segment_indicator": True,
    },
    "web_form": {
        "max_length": 1500,
        "max_words": 300,
        "tone": "semi-formal",
        "requires_greeting": True,
        "requires_signature": False,
        "allows_emojis": False,
        "requires_ticket_ref": True,
    },
}

# =============================================================================
# GREETINGS AND SIGNATURES
# =============================================================================

EMAIL_GREETINGS = [
    "Dear {name},",
    "Hello {name},",
    "Hi {name},",
]

EMAIL_SIGNATURE = """
Best regards,
Customer Success Team
{company_name}

📧 support@company.com
📞 1-800-XXX-XXXX
🌐 https://support.company.com

Ticket Reference: {ticket_id}
"""

WHATSAPP_GREETINGS = [
    "Hi {name}! 👋",
    "Hello {name}!",
    "Hey {name},",
]

WEB_FORM_GREETING = """
Hello {name},

Thank you for contacting us. Regarding your inquiry:
"""

# =============================================================================
# FORMATTING FUNCTIONS
# =============================================================================


def format_for_email(
    content: str,
    customer_name: str,
    ticket_id: str,
    company_name: str = "Our Company"
) -> str:
    """
    Format response for email delivery.

    Args:
        content: Raw response content
        customer_name: Customer's name for greeting
        ticket_id: Ticket reference number
        company_name: Company name for signature

    Returns:
        Formatted email with greeting, body, and signature
    """
    # Select greeting
    greeting = EMAIL_GREETINGS[0].format(name=customer_name or "there")
    
    # Format body with proper paragraph spacing
    body = content.strip()
    body = re.sub(r'\n\s*\n', '\n\n', body)  # Normalize paragraph breaks
    
    # Format signature
    signature = EMAIL_SIGNATURE.format(
        company_name=company_name,
        ticket_id=ticket_id
    )
    
    # Combine
    full_email = f"{greeting}\n\n{body}\n{signature}"
    
    # Check length
    word_count = len(body.split())
    if word_count > 500:
        logger.warning(f"Email response exceeds 500 words: {word_count} words")
    
    if len(full_email) > 2000:
        logger.warning(f"Email response exceeds 2000 characters: {len(full_email)}")
    
    return full_email


def format_for_whatsapp(
    content: str,
    customer_name: Optional[str] = None,
    ticket_id: Optional[str] = None,
    split_long: bool = True
) -> List[str]:
    """
    Format response for WhatsApp delivery.

    Splits long messages into segments with indicators.

    Args:
        content: Raw response content
        customer_name: Customer's name (optional for greeting)
        ticket_id: Ticket reference (appended to last segment)
        split_long: Whether to split into multiple segments

    Returns:
        List of message segments
    """
    config = CHANNEL_CONFIGS["whatsapp"]
    
    # Remove any existing emojis to count properly
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags
        "]+", flags=re.UNICODE)
    
    # Limit emojis
    content_no_emoji = emoji_pattern.sub('', content)
    emoji_count = len(content) - len(content_no_emoji)
    
    if emoji_count > config.get("max_emojis", 2):
        # Remove excess emojis
        content = content_no_emoji
    
    # Add greeting if name provided
    if customer_name:
        greeting = f"Hi {customer_name}! "
        content = greeting + content
    
    # Add ticket reference if provided
    if ticket_id:
        content = content + f"\n\n📋 Ref: {ticket_id}"
    
    # Split into segments if needed
    if split_long and len(content) > config["preferred_length"]:
        segments = split_message(content, config["preferred_length"])
        
        # Add segment indicators
        if len(segments) > 1:
            for i in range(len(segments)):
                segments[i] = f"({i+1}/{len(segments)}) {segments[i]}"
        
        return segments
    else:
        return [content]


def format_for_web_form(
    content: str,
    customer_name: str,
    ticket_id: str
) -> str:
    """
    Format response for web form display.

    Args:
        content: Raw response content
        customer_name: Customer's name
        ticket_id: Ticket reference number

    Returns:
        Formatted response for web display
    """
    config = CHANNEL_CONFIGS["web_form"]
    
    # Add greeting
    greeting = WEB_FORM_GREETING.format(name=customer_name or "there")
    
    # Format body
    body = content.strip()
    body = re.sub(r'\n\s*\n', '\n\n', body)
    
    # Check length
    word_count = len(body.split())
    if word_count > config["max_words"]:
        logger.warning(f"Web form response exceeds {config['max_words']} words: {word_count}")
    
    # Combine
    response = f"{greeting}\n\n{body}"
    
    return response


def split_message(content: str, max_length: int = 160) -> List[str]:
    """
    Split a message into segments at appropriate boundaries.

    Tries to split at sentence boundaries first, then word boundaries.

    Args:
        content: Message content to split
        max_length: Maximum length per segment

    Returns:
        List of message segments
    """
    if len(content) <= max_length:
        return [content]
    
    segments = []
    remaining = content
    
    while len(remaining) > max_length:
        # Try to find sentence boundary
        split_point = -1
        
        # Look for sentence endings
        for ending in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
            pos = remaining.rfind(ending, 0, max_length)
            if pos > max_length * 0.5:  # Only if past halfway
                split_point = pos + len(ending)
                break
        
        # If no sentence boundary, try word boundary
        if split_point == -1:
            space_pos = remaining.rfind(' ', 0, max_length)
            if space_pos > max_length * 0.5:
                split_point = space_pos + 1
        
        # If still no good split point, hard split
        if split_point == -1:
            split_point = max_length
        
        # Add segment
        segment = remaining[:split_point].strip()
        if segment:
            segments.append(segment)
        
        # Continue with remaining
        remaining = remaining[split_point:].strip()
    
    # Add final segment
    if remaining:
        segments.append(remaining)
    
    return segments


def adapt_tone(content: str, target_tone: str) -> str:
    """
    Adapt the tone of content for the target channel.

    Args:
        content: Original content
        target_tone: Target tone ('formal', 'semi-formal', 'conversational')

    Returns:
        Content with adapted tone
    """
    if target_tone == "conversational":
        # Make more conversational
        replacements = {
            "cannot": "can't",
            "will not": "won't",
            "do not": "don't",
            "we are": "we're",
            "I am": "I'm",
            "please": "",  # Sometimes remove for brevity
            "kindly": "",
            "regarding": "about",
            "furthermore": "also",
            "however": "but",
            "therefore": "so",
        }
        
        for formal, casual in replacements.items():
            content = content.replace(formal, casual)
        
        # Add friendly opener if missing
        if not any(content.startswith(x) for x in ["Hi", "Hello", "Hey", "Thanks"]):
            content = "Thanks for reaching out! " + content
    
    elif target_tone == "formal":
        # Make more formal
        replacements = {
            "can't": "cannot",
            "won't": "will not",
            "don't": "do not",
            "we're": "we are",
            "I'm": "I am",
            "about": "regarding",
            "also": "furthermore",
            "but": "however",
            "so": "therefore",
            "got": "received",
            "need": "require",
        }
        
        for casual, formal in replacements.items():
            content = content.replace(casual, formal)
    
    return content.strip()


def format_error_response(
    error_type: str,
    channel: str,
    ticket_id: Optional[str] = None
) -> str:
    """
    Format an error response appropriately for the channel.

    Args:
        error_type: Type of error ('technical', 'unavailable', 'escalated')
        channel: Target channel
        ticket_id: Optional ticket reference

    Returns:
        Formatted error message
    """
    error_messages = {
        "technical": {
            "email": "We are currently experiencing technical difficulties. Our team has been notified and is working to resolve this issue. We apologize for any inconvenience.",
            "whatsapp": "We're having some technical issues right now. Our team is on it! 🔧",
            "web_form": "We're experiencing technical difficulties. Please try again in a few minutes.",
        },
        "unavailable": {
            "email": "The information you requested is temporarily unavailable. A member of our team will follow up with you shortly.",
            "whatsapp": "Let me check on that for you. One moment please!",
            "web_form": "This information is currently unavailable. We'll follow up via email.",
        },
        "escalated": {
            "email": f"Your case has been escalated to a specialist who will review your situation and respond within 24 hours. Your ticket reference is {ticket_id}.",
            "whatsapp": f"I've escalated this to our specialist team. They'll reach out soon! Ref: {ticket_id}",
            "web_form": f"Your request has been escalated. We'll contact you at your email address. Ref: {ticket_id}",
        },
    }
    
    return error_messages.get(error_type, {}).get(channel, "An error occurred. Please try again.")


# =============================================================================
# MAIN FORMAT FUNCTION
# =============================================================================


def format_response(
    content: str,
    channel: str,
    customer_name: Optional[str] = None,
    ticket_id: Optional[str] = None,
    company_name: str = "Our Company"
) -> str | List[str]:
    """
    Main function to format response for any channel.

    Args:
        content: Raw response content
        channel: Target channel ('email', 'whatsapp', 'web_form')
        customer_name: Customer's name
        ticket_id: Ticket reference number
        company_name: Company name

    Returns:
        Formatted response (string or list of segments for WhatsApp)
    """
    if channel == "email":
        return format_for_email(content, customer_name, ticket_id, company_name)
    
    elif channel == "whatsapp":
        return format_for_whatsapp(content, customer_name, ticket_id)
    
    elif channel == "web_form":
        return format_for_web_form(content, customer_name, ticket_id)
    
    else:
        logger.error(f"Unknown channel: {channel}")
        return content
