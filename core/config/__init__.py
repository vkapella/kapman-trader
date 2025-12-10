import os
from dotenv import load_dotenv
from botocore.client import Config

# Load environment variables from .env file
load_dotenv()

class Settings:
    # AWS settings
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    S3_BUCKET = os.getenv('S3_BUCKET', 'flatfiles')
    S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL', 'https://files.massive.com')
    
    # S3 client configuration
    S3_CONFIG = Config(
        signature_version='s3v4',
        s3={'addressing_style': 'path'},
        retries={'max_attempts': 3, 'mode': 'standard'}
    )
    
    # Database settings
    DB_NAME = os.getenv('DB_NAME', 'kapman')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')

# Create a settings instance
settings = Settings()
