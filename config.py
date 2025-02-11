from datetime import timedelta

# Celery Configuration
CELERY_CONFIG = {
    'BROKER_URL': 'redis://red-cuki0556l47c73cc9vi0:6379/0',
    'RESULT_BACKEND': 'redis://red-cuki0556l47c73cc9vi0:6379/0',
    'BROKER_CONNECTION_RETRY_ON_STARTUP': True
}

# Flask Configuration
FLASK_CONFIG = {
    'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,  # 16MB
    'CORS_ORIGINS': "*"
}

# File Storage Configuration
STORAGE_CONFIG = {
    'PDF_TEMP_DIR': '/tmp',
    'PDF_STORAGE_DIR': '/home/render/pdfs',
    'S3_PDF_PREFIX': 'pdfs'
}

# API Configuration
API_CONFIG = {
    'MISTRAL_MODEL': 'mistral-medium',
    'MAX_TOKENS': 800,
    'STORY_SECTIONS': 3,
    'URL_EXPIRATION': timedelta(days=1).total_seconds()
}

# Image Generation Configuration
IMAGE_CONFIG = {
    'MODEL': 'stability-ai/stable-diffusion-3',
    'WIDTH': 256,
    'HEIGHT': 256
}

# Base URLs
BASE_URLS = {
    'DOWNLOAD': 'https://story-backend-g7he.onrender.com/download'
}

STORY_LENGTH_CONFIG = {
    "short": {
        "max_tokens": 800,
        "target_sections": 3,
        "price": 0,  # Free tier
        "description": "A perfect bedtime story (~3 pages)",
        "is_premium": False
    },
    "medium": {
        "max_tokens": 1600,
        "target_sections": 5,
        "price": 2.99,  # Example price
        "description": "A more detailed adventure (~6 pages)",
        "is_premium": True
    },
    "long": {
        "max_tokens": 2400,
        "target_sections": 7,
        "price": 4.99,  # Example price
        "description": "An epic journey (~9 pages)",
        "is_premium": True
    }
}
