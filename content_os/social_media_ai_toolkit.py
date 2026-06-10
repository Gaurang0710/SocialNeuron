import asyncio
import json
import logging
import os
import re
import smtplib
from datetime import datetime, timedelta
from email import encoders
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Union

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

# ---------------------------
# Logging
# ---------------------------

def setup_logger(name: str = "social_media_ai_toolkit", level: int = logging.INFO, log_file: Optional[str] = None) -> logging.Logger:
    """Set up a logger with console and optional file output."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

logger = setup_logger()

# ---------------------------
# Ollama Client
# ---------------------------

class Settings:
    def __init__(self) -> None:
        self.OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud")
        self.OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.7"))
        self.OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "512"))
        self.OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "60.0"))

settings = Settings()

async def call_ollama(messages: list, model: Optional[str] = None, stream: bool = False, options: Optional[Dict[str, Any]] = None) -> str:
    logger.info(f"[OLLAMA] model={model or settings.OLLAMA_MODEL}")
    print(f"[OLLAMA] model={model or settings.OLLAMA_MODEL}")
    if options is None:
        options = {"temperature": settings.OLLAMA_TEMPERATURE, "num_predict": settings.OLLAMA_NUM_PREDICT}

    async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model or settings.OLLAMA_MODEL,
                "messages": messages,
                "stream": stream,
                "options": options,
            },
        )
        response.raise_for_status()

        response_text = response.text
        if not response_text or not response_text.strip():
            raise ValueError("Ollama returned empty response body")

        try:
            response_json = response.json()
        except ValueError as exc:
            logger.error(f"OLLAMA response is not valid JSON: {response_text}")
            raise ValueError(f"OLLAMA invalid JSON response: {exc}") from exc

        if "message" not in response_json or "content" not in response_json["message"]:
            logger.error(f"Unexpected Ollama response structure: {response_json}")
            raise ValueError(f"Unexpected Ollama response structure: {response_json}")

        return response_json["message"]["content"]

def extract_json_from_text(content: str) -> str:
    """Extract JSON payload from a text response that may include markdown or explanation."""
    stripped = content.strip()

    # Remove code fences if present
    if stripped.startswith("```") and stripped.endswith("```"):
        stripped = stripped.strip('`')
    if stripped.startswith("```json"):
        stripped = stripped[6:].strip('`')

    # Find the first JSON object in the text
    start = stripped.find('{')
    end = stripped.rfind('}')
    if start != -1 and end != -1 and end > start:
        return stripped[start:end + 1]

    return stripped

async def generate_completion(
    model: str,
    prompt: str,
    options: Optional[Dict[str, Any]] = None,
    stream: bool = False
) -> str:
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": prompt}
    ]
    return await call_ollama(messages=messages, model=model, stream=stream, options=options)

async def generate_json(
    model: str,
    prompt: str,
    schema: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    content = await generate_completion(model=model, prompt=prompt, options=options)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        cleaned = extract_json_from_text(content)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse JSON from Ollama output: {content}")
            logger.error(f"Extracted json content: {cleaned}")
            raise ValueError(f"Invalid JSON from Ollama: {exc}") from exc

async def stream_completion(
    model: str,
    prompt: str,
    options: Optional[Dict[str, Any]] = None
) -> str:
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": prompt}
    ]
    return await call_ollama(messages=messages, model=model, stream=True, options=options)

# ---------------------------
# Prompts
# ---------------------------

LINKEDIN_POST_PROMPT = """
Generate a professional LinkedIn post about: {topic}

Requirements:
- Hook: Start with an engaging question or statement
- Caption: 100-150 words, professional tone
- CTA: Clear call-to-action
- Hashtags: 3-5 relevant hashtags
- Image Prompt: Description for a professional image

Topic: {topic}
Platform: LinkedIn
Tone: {tone}
Audience: {audience}

Return as JSON with keys: hook, caption, cta, hashtags (array), image_prompt
"""

INSTAGRAM_POST_PROMPT = """
Generate an engaging Instagram post about: {topic}

Requirements:
- Hook: Attention-grabbing opening
- Caption: 80-120 words, conversational tone
- CTA: Encourage engagement
- Hashtags: 5-8 relevant hashtags
- Image Prompt: Vibrant, modern social media style

Topic: {topic}
Platform: Instagram
Tone: {tone}
Audience: {audience}

Return as JSON with keys: hook, caption, cta, hashtags (array), image_prompt
"""

TWITTER_POST_PROMPT = """
Generate a concise Twitter/X post about: {topic}

Requirements:
- Hook: Punchy opening
- Caption: 200 characters max, engaging
- CTA: Call to action or question
- Hashtags: 2-4 relevant hashtags
- Image Prompt: Eye-catching thumbnail style

Topic: {topic}
Platform: Twitter/X
Tone: {tone}
Audience: {audience}

Return as JSON with keys: hook, caption, cta, hashtags (array), image_prompt
"""

REEL_SCRIPT_PROMPT = """
Generate a compelling reel script about: {topic}

Requirements:
- Hook: Strong opening scene (5-10 seconds)
- Voiceover: Natural, engaging narration
- Scenes: 4-6 scenes with visual and text overlay
- Caption: Instagram caption for the reel
- Hashtags: 8-12 relevant hashtags

Each scene should have:
- scene_number: sequential number
- visual: description of what's shown
- text: text overlay or voiceover for that scene

Topic: {topic}
Platform: Instagram
Tone: {tone}
Audience: {audience}

Return as JSON with keys: hook, voiceover, scenes (array), caption, hashtags (array)
"""

IMAGE_PROMPT_PROMPT = """
Generate a detailed image prompt for AI image generation about: {topic}

Style: {style} (cinematic, realistic, modern social media)

Requirements:
- Highly detailed description
- Include lighting, composition, colors
- Suitable for SDXL, FLUX, or DALL-E
- Professional quality
- Social media optimized

Topic: {topic}
Style: {style}

Return as JSON with key: prompt
"""

MONTHLY_TOPICS_PROMPT = """
Generate a monthly content calendar for social media.

Niche: {niche}
Platforms: {platforms}
Number of days: {number_of_days}

Requirements:
- Balanced mix: 40% educational, 30% promotional, 20% case studies, 10% trends/personal branding
- Distribute across platforms evenly
- Include variety in post types: posts, reels, stories
- Topics should be relevant and engaging

Return as JSON array with objects containing: date, platform, post_type, topic
"""

# ---------------------------
# Excel and CSV Processing
# ---------------------------

REQUIRED_COLUMNS = ['Date', 'Platform', 'Post Type', 'Topic']

DATE_FORMATS = ['%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y', '%m/%d/%y']


def load_calendar_file(file_path: str) -> pd.DataFrame:
    """Load calendar data from CSV or Excel."""
    try:
        if file_path.lower().endswith('.csv'):
            df = pd.read_csv(file_path)
            logger.info(f"Loaded CSV calendar from {file_path} with {len(df)} rows")
        elif file_path.lower().endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_path, engine='openpyxl')
            logger.info(f"Loaded Excel calendar from {file_path} with {len(df)} rows")
        else:
            raise ValueError(f"Unsupported file format: {file_path}. Use .csv or .xlsx")
        return df
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error loading file: {e}")
        raise ValueError(f"Invalid file: {e}")


def validate_calendar_columns(df: pd.DataFrame) -> bool:
    """Validate required columns are present."""
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        logger.error(f"Missing required columns: {missing_columns}")
        return False
    logger.info("Calendar columns validation passed")
    return True


def parse_date(date_str: Any) -> datetime:
    """Parse a date string or datetime into datetime."""
    if isinstance(date_str, datetime):
        return date_str
    normalized = str(date_str).strip()
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(normalized, fmt)
            if parsed.year < 100:
                parsed = parsed.replace(year=parsed.year + 2000)
            return parsed
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_str}")


def normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize the Date column to datetime objects."""
    df_copy = df.copy()
    df_copy['Date'] = df_copy['Date'].apply(parse_date)
    logger.info("Dates normalized successfully")
    return df_copy


def convert_calendar_to_dict(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert calendar DataFrame to list of dictionaries."""
    df_normalized = normalize_dates(df)
    records = df_normalized.to_dict('records')
    for record in records:
        if isinstance(record.get('Date'), datetime):
            record['Date'] = record['Date'].isoformat()
    logger.info(f"Converted {len(records)} records to dictionary format")
    return records


def process_calendar_file(file_path: str) -> List[Dict[str, Any]]:
    """Load, validate, normalize, and convert a calendar file."""
    df = load_calendar_file(file_path)
    if not validate_calendar_columns(df):
        raise ValueError("Invalid calendar format: missing required columns")
    return convert_calendar_to_dict(df)

# ---------------------------
# Content Generation
# ---------------------------

PLATFORM_PROMPTS = {
    'linkedin': LINKEDIN_POST_PROMPT,
    'instagram': INSTAGRAM_POST_PROMPT,
    'twitter': TWITTER_POST_PROMPT,
    'x': TWITTER_POST_PROMPT,
}


async def generate_social_post(
    topic: str,
    platform: str,
    tone: str = "professional",
    audience: str = "general",
    model: str = "llama3"
) -> Dict[str, Any]:
    """Generate a social media post for a given platform."""
    platform_lower = platform.lower()
    if platform_lower not in PLATFORM_PROMPTS:
        raise ValueError(f"Unsupported platform: {platform}. Supported: {list(PLATFORM_PROMPTS.keys())}")
    prompt = PLATFORM_PROMPTS[platform_lower].format(topic=topic, tone=tone, audience=audience)
    logger.info(f"Generating {platform} post for topic: {topic}")
    result = await generate_json(model=model, prompt=prompt)
    required_keys = ['hook', 'caption', 'cta', 'hashtags', 'image_prompt']
    missing_keys = [key for key in required_keys if key not in result]
    if missing_keys:
        raise ValueError(f"Generated post missing keys: {missing_keys}")
    if not isinstance(result['hashtags'], list):
        result['hashtags'] = [result['hashtags']]
    return result


async def generate_reel_script(
    topic: str,
    tone: str = "engaging",
    audience: str = "general",
    model: str = "llama3"
) -> Dict[str, Any]:
    """Generate a reel script with scenes and voiceover."""
    prompt = REEL_SCRIPT_PROMPT.format(topic=topic, tone=tone, audience=audience)
    logger.info(f"Generating reel script for topic: {topic}")
    result = await generate_json(model=model, prompt=prompt)
    required_keys = ['hook', 'voiceover', 'scenes', 'caption', 'hashtags']
    missing_keys = [key for key in required_keys if key not in result]
    if missing_keys:
        raise ValueError(f"Generated reel script missing keys: {missing_keys}")
    if not isinstance(result['scenes'], list):
        raise ValueError("Scenes must be a list")
    for scene in result['scenes']:
        if not isinstance(scene, dict):
            raise ValueError("Each scene must be a dictionary")
        required_scene_keys = ['scene_number', 'visual', 'text']
        missing_scene_keys = [key for key in required_scene_keys if key not in scene]
        if missing_scene_keys:
            raise ValueError(f"Scene missing keys: {missing_scene_keys}")
    if not isinstance(result['hashtags'], list):
        result['hashtags'] = [result['hashtags']]
    return result


async def generate_image_prompt(
    topic: str,
    style: str = "modern social media",
    model: str = "llama3"
) -> str:
    """Generate a detailed image prompt for AI image generation."""
    supported_styles = ['cinematic', 'realistic', 'modern social media']
    if style not in supported_styles:
        raise ValueError(f"Unsupported style: {style}. Supported: {supported_styles}")
    prompt = IMAGE_PROMPT_PROMPT.format(topic=topic, style=style)
    logger.info(f"Generating image prompt for topic: {topic} style: {style}")
    result = await generate_json(model=model, prompt=prompt)
    if 'prompt' not in result:
        raise ValueError("Generated response missing 'prompt' key")
    prompt_text = result['prompt']
    if not isinstance(prompt_text, str) or not prompt_text.strip():
        raise ValueError("Generated prompt is not a valid string")
    return prompt_text.strip()


async def generate_monthly_topics(
    niche: str,
    platforms: List[str],
    number_of_days: int = 30,
    start_date: Optional[datetime] = None,
    model: str = "llama3"
) -> List[Dict[str, Any]]:
    """Generate monthly content topics with balanced mix."""
    if not platforms:
        raise ValueError("At least one platform must be specified")
    if number_of_days <= 0:
        raise ValueError("Number of days must be positive")
    if start_date is None:
        start_date = datetime.now()
    platforms_str = ", ".join(platforms)
    prompt = MONTHLY_TOPICS_PROMPT.format(niche=niche, platforms=platforms_str, number_of_days=number_of_days)
    logger.info(f"Generating monthly topics for niche: {niche}")
    result = await generate_json(model=model, prompt=prompt)
    if not isinstance(result, list):
        raise ValueError("Generated topics must be a list")
    validated_topics: List[Dict[str, Any]] = []
    current_date = start_date
    for i, topic in enumerate(result):
        if not isinstance(topic, dict):
            raise ValueError(f"Topic {i} must be a dictionary")
        required_keys = ['platform', 'post_type', 'topic']
        missing_keys = [key for key in required_keys if key not in topic]
        if missing_keys:
            raise ValueError(f"Topic {i} missing keys: {missing_keys}")
        if 'date' not in topic:
            topic['date'] = current_date.isoformat()
            current_date += timedelta(days=1)
        else:
            if isinstance(topic['date'], str):
                try:
                    datetime.fromisoformat(topic['date'])
                except ValueError:
                    raise ValueError(f"Invalid date format in topic {i}: {topic['date']}")
            else:
                topic['date'] = str(topic['date'])
        validated_topics.append(topic)
    return validated_topics

# ---------------------------
# Scheduling Utilities
# ---------------------------

GENERATION_DAYS_AHEAD = 3


def calculate_generation_date(post_date: datetime) -> datetime:
    """Calculate the date when content should be generated."""
    return post_date - timedelta(days=GENERATION_DAYS_AHEAD)


def should_generate_today(post_date: datetime, current_date: Optional[datetime] = None) -> bool:
    """Return true if content generation should happen today."""
    if current_date is None:
        current_date = datetime.now()
    return current_date.date() == calculate_generation_date(post_date).date()


def get_upcoming_posts(
    calendar: List[Dict[str, Any]],
    days_ahead: int = 7,
    current_date: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Return upcoming posts that need generation."""
    if current_date is None:
        current_date = datetime.now()
    upcoming_posts: List[Dict[str, Any]] = []
    for entry in calendar:
        try:
            date_value = entry.get('Date')
            post_date = datetime.fromisoformat(date_value) if isinstance(date_value, str) else date_value
            generation_date = calculate_generation_date(post_date)
            days_until_generation = (generation_date.date() - current_date.date()).days
            if 0 <= days_until_generation <= days_ahead:
                upcoming_posts.append({**entry, 'generation_date': generation_date.isoformat(), 'days_until_generation': days_until_generation})
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Skipping invalid calendar entry: {e}")
            continue
    upcoming_posts.sort(key=lambda x: x['generation_date'])
    logger.info(f"Found {len(upcoming_posts)} upcoming posts to generate")
    return upcoming_posts


def get_posts_due_today(
    calendar: List[Dict[str, Any]],
    current_date: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """Return posts due for generation today."""
    if current_date is None:
        current_date = datetime.now()
    due_today: List[Dict[str, Any]] = []
    for entry in calendar:
        try:
            date_value = entry.get('Date')
            post_date = datetime.fromisoformat(date_value) if isinstance(date_value, str) else date_value
            if should_generate_today(post_date, current_date):
                due_today.append(entry)
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Skipping invalid calendar entry: {e}")
            continue
    logger.info(f"Found {len(due_today)} posts due for generation today")
    return due_today

# ---------------------------
# Email Utilities
# ---------------------------


def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: Optional[str] = None,
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587,
    attachments: Optional[List[str]] = None
) -> bool:
    """Send an email with optional attachments."""
    smtp_email = os.getenv('SMTP_EMAIL')
    smtp_password = os.getenv('SMTP_PASSWORD')
    if not smtp_email or not smtp_password:
        raise ValueError("SMTP_EMAIL and SMTP_PASSWORD environment variables must be set")
    if from_email is None:
        from_email = smtp_email

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    if attachments:
        for attachment_path in attachments:
            if not os.path.exists(attachment_path):
                logger.warning(f"Attachment not found: {attachment_path}")
                continue
            with open(attachment_path, 'rb') as f:
                if attachment_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    img = MIMEImage(f.read())
                    img.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
                    msg.attach(img)
                else:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(attachment_path)}"')
                    msg.attach(part)

    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(smtp_email, smtp_password)
    server.sendmail(from_email, to_email, msg.as_string())
    server.quit()
    logger.info(f"Email sent successfully to {to_email}")
    return True


def send_generated_content_email(
    to_email: str,
    content_data: Dict[str, Any],
    content_type: str = "post",
    attachments: Optional[List[str]] = None
) -> bool:
    """Send generated social media content via email."""
    subject = f"Generated {content_type.title()} Content"
    body = ["<html><body>", f"<h2>Generated {content_type.title()} Content</h2>"]

    if content_type == "post":
        body.append(f"<h3>Topic: {content_data.get('topic', 'N/A')}</h3>")
        body.append(f"<p><strong>Hook:</strong> {content_data.get('hook', '')}</p>")
        body.append(f"<p><strong>Caption:</strong> {content_data.get('caption', '')}</p>")
        body.append(f"<p><strong>CTA:</strong> {content_data.get('cta', '')}</p>")
        body.append(f"<p><strong>Hashtags:</strong> {' '.join(content_data.get('hashtags', []))}</p>")
        body.append(f"<p><strong>Image Prompt:</strong> {content_data.get('image_prompt', '')}</p>")
    elif content_type == "reel":
        body.append(f"<h3>Topic: {content_data.get('topic', 'N/A')}</h3>")
        body.append(f"<p><strong>Hook:</strong> {content_data.get('hook', '')}</p>")
        body.append(f"<p><strong>Voiceover:</strong> {content_data.get('voiceover', '')}</p>")
        body.append("<h4>Scenes:</h4><ol>")
        for scene in content_data.get('scenes', []):
            body.append(
                f"<li><strong>Scene {scene.get('scene_number', '')}:</strong><br>Visual: {scene.get('visual', '')}<br>Text: {scene.get('text', '')}</li>"
            )
        body.append("</ol>")
        body.append(f"<p><strong>Caption:</strong> {content_data.get('caption', '')}</p>")
        body.append(f"<p><strong>Hashtags:</strong> {' '.join(content_data.get('hashtags', []))}</p>")

    body.append("</body></html>")
    return send_email(to_email=to_email, subject=subject, body=''.join(body), attachments=attachments)

# ---------------------------
# Validation Helpers
# ---------------------------

VALID_PLATFORMS = ['linkedin', 'instagram', 'twitter', 'x', 'facebook', 'tiktok']
VALID_POST_TYPES = ['post', 'reel', 'story', 'carousel', 'thread']


def validate_email(email: str) -> bool:
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is not None


def validate_platform(platform: str) -> bool:
    return platform.lower() in VALID_PLATFORMS


def validate_post_type(post_type: str) -> bool:
    return post_type.lower() in VALID_POST_TYPES


def validate_date(date_str: str) -> bool:
    try:
        datetime.fromisoformat(date_str)
        return True
    except ValueError:
        return False


def validate_calendar_entry(entry: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for field in REQUIRED_COLUMNS:
        if field not in entry or not entry[field]:
            errors.append(f"Missing or empty required field: {field}")
    if errors:
        return errors
    if not validate_date(str(entry['Date'])):
        errors.append(f"Invalid date format: {entry['Date']}")
    if not validate_platform(str(entry['Platform'])):
        errors.append(f"Unsupported platform: {entry['Platform']}")
    if not validate_post_type(str(entry['Post Type'])):
        errors.append(f"Unsupported post type: {entry['Post Type']}")
    return errors


def validate_generated_post(post: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for key in ['hook', 'caption', 'cta', 'hashtags', 'image_prompt']:
        if key not in post or not post[key]:
            errors.append(f"Missing or empty key: {key}")
    if 'hashtags' in post and not isinstance(post['hashtags'], list):
        errors.append("Hashtags must be a list")
    return errors


def validate_generated_reel(reel: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for key in ['hook', 'voiceover', 'scenes', 'caption', 'hashtags']:
        if key not in reel or not reel[key]:
            errors.append(f"Missing or empty key: {key}")
    if 'scenes' in reel:
        if not isinstance(reel['scenes'], list):
            errors.append("Scenes must be a list")
        else:
            for i, scene in enumerate(reel['scenes']):
                if not isinstance(scene, dict):
                    errors.append(f"Scene {i} must be a dictionary")
                else:
                    for key in ['scene_number', 'visual', 'text']:
                        if key not in scene:
                            errors.append(f"Scene {i} missing key: {key}")
    if 'hashtags' in reel and not isinstance(reel['hashtags'], list):
        errors.append("Hashtags must be a list")
    return errors

# ---------------------------
# Example Usage
# ---------------------------

async def example_post_generation() -> None:
    print("=== Generating Social Media Post ===")
    post = await generate_social_post(
        topic="AI Automation Tools",
        platform="linkedin",
        tone="professional",
        audience="tech professionals"
    )
    print("Generated Post:")
    print(f"Hook: {post['hook']}")
    print(f"Caption: {post['caption']}")
    print(f"CTA: {post['cta']}")
    print(f"Hashtags: {', '.join(post['hashtags'])}")
    print(f"Image Prompt: {post['image_prompt']}")
    print()


async def example_reel_generation() -> None:
    print("=== Generating Reel Script ===")
    reel = await generate_reel_script(
        topic="Machine Learning Basics",
        tone="educational",
        audience="beginners"
    )
    print("Generated Reel:")
    print(f"Hook: {reel['hook']}")
    print(f"Voiceover: {reel['voiceover']}")
    print("Scenes:")
    for scene in reel['scenes']:
        print(f"  Scene {scene['scene_number']}: {scene['visual']} - {scene['text']}")
    print(f"Caption: {reel['caption']}")
    print(f"Hashtags: {', '.join(reel['hashtags'])}")
    print()


async def example_image_prompt_generation() -> None:
    print("=== Generating Image Prompt ===")
    prompt = await generate_image_prompt(
        topic="Remote Work Productivity",
        style="modern social media"
    )
    print(f"Image Prompt: {prompt}")
    print()


async def example_monthly_topics() -> None:
    print("=== Generating Monthly Topics ===")
    topics = await generate_monthly_topics(
        niche="Technology Consulting",
        platforms=["linkedin", "instagram", "twitter"],
        number_of_days=10
    )
    print("Generated Topics:")
    for topic in topics:
        print(f"  {topic['date']}: {topic['platform']} - {topic['post_type']} - {topic['topic']}")
    print()


async def example_calendar_processing() -> List[Dict[str, Any]]:
    print("=== Calendar Processing Example ===")
    try:
        calendar_data = process_calendar_file("may_month_calender.csv")
        print("Processed Calendar Data:")
        for entry in calendar_data:
            print(f"  {entry['Date']}: {entry['Platform']} - {entry['Post Type']} - {entry['Topic']}")
        print()
        return calendar_data
    except Exception as e:
        print(f"Error processing calendar file: {e}")
        fallback = [
            {"Date": "2026-05-11T00:00:00", "Platform": "Instagram", "Post Type": "Post", "Topic": "MCP Server"},
            {"Date": "2026-05-13T00:00:00", "Platform": "Instagram", "Post Type": "Reel", "Topic": "Sports Academy Management System"},
            {"Date": "2026-05-14T00:00:00", "Platform": "LinkedIn", "Post Type": "Post", "Topic": "Top HR Tips"}
        ]
        print("Using fallback sample calendar data")
        for entry in fallback:
            print(f"  {entry['Date']}: {entry['Platform']} - {entry['Post Type']} - {entry['Topic']}")
        print()
        return fallback


def example_scheduler(calendar_data: Optional[List[Dict[str, Any]]] = None) -> None:
    print("=== Scheduler Example ===")
    if calendar_data is None:
        calendar_data = [
            {"Date": "2026-05-11T00:00:00", "Platform": "Instagram", "Post Type": "Post", "Topic": "MCP Server"},
            {"Date": "2026-05-13T00:00:00", "Platform": "Instagram", "Post Type": "Reel", "Topic": "Sports Academy Management System"},
        ]
    upcoming = get_upcoming_posts(calendar_data, days_ahead=5)
    print(f"Upcoming posts to generate: {len(upcoming)}")
    for post in upcoming:
        print(f"  Generate on {post['generation_date']}: {post['Topic']}")
    print()


async def main() -> None:
    print("Social Media AI Toolkit - Standalone Example")
    print("=" * 50)
    try:
        await example_post_generation()
        await example_reel_generation()
        await example_image_prompt_generation()
        await example_monthly_topics()
        calendar_data = await example_calendar_processing()
        example_scheduler(calendar_data)
        print("Example run completed successfully.")
    except Exception as e:
        logger.error(f"Error running examples: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())