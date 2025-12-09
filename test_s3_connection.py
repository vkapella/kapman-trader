import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

def test_s3_connection():
    print("=== Testing S3 Connection ===")
    
    # Get credentials from environment
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    endpoint_url = os.getenv("S3_ENDPOINT_URL")
    bucket_name = "flatfiles"
    
    print(f"Connecting to S3 endpoint: {endpoint_url}")
    print(f"Using bucket: {bucket_name}")
    
    try:
        # Initialize S3 client
        s3 = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            endpoint_url=endpoint_url,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}
            ),
            region_name="us-east-1"
        )
        
        print("\n✅ Successfully connected to S3")
        
        # List bucket contents
        print("\nListing bucket contents (first 10 items):")
        response = s3.list_objects_v2(
            Bucket=bucket_name,
            MaxKeys=10
        )
        
        if 'Contents' in response:
            for obj in response['Contents']:
                print(f"- {obj['Key']} (Size: {obj['Size']} bytes, Last Modified: {obj['LastModified']})")
        else:
            print("No objects found in the bucket. Trying to list prefixes...")
            response = s3.list_objects_v2(
                Bucket=bucket_name,
                Delimiter='/',
                MaxKeys=10
            )
            if 'CommonPrefixes' in response:
                for prefix in response['CommonPrefixes']:
                    print(f"- {prefix['Prefix']} (Prefix)")
            else:
                print("No contents or prefixes found in the bucket")
                
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"\n❌ S3 Error ({error_code}): {error_message}")
        if error_code == 'AccessDenied':
            print("\nPossible issues:")
            print("1. Incorrect AWS credentials")
            print("2. Insufficient permissions for the bucket")
            print("3. Incorrect bucket name or region")
        elif error_code == 'NoSuchBucket':
            print("\nThe specified bucket does not exist or you don't have permission to access it")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_s3_connection()
