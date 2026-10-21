#!/usr/bin/env python3
import json
import logging
import os
import sys
import time
import boto3
import requests
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)
s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    """Returns a tuple of three strings: the list file, index path, and bucket. If one or more doesn't exist, it exits
    """
    if len(sys.argv) < 4:
        log.error("Usage: stage_books.py BOOK_LIST INDEX_HTML_BUCKET")
        sys.exit(1)
    return sys.argv[1], sys.argv[2], sys.argv[3]

def download_books(list_file, dest_dir):
    """Downloads each Book URL in the list_file into dest_dir. Skips the download if the file already exists
    """
    os.makedirs(dest_dir,exist_ok=True)
    paths = []

    with open(list_file) as p:
        urls = [line.strip() for line in p if line.strip()]
    log.info(f"Found {len(urls)} book URLS in {list_file}")

    for url in urls:
        file_name = url.rsplit("/",1)[-1]
        path = os.path.join(dest_dir,file_name)
        if os.path.exists(path):
            log.info(f"Already downloaded: {path}")
            paths.append(path)
            continue

        try:
            response = requests.get(url)
            response.raise_for_status()
            with open(path,"wb") as out:
                out.write(response.content)
            log.info(f"Downloaded {url} -> {path}")
            paths.append(path)
        except requests.RequestException as err:
            log.error(f"Error downloading {url}:{err}")

        time.sleep(1)

    return paths


def create_bucket(bucket):
    """Create the bucket unless it already exists. Return True if it exists afterwards."""
    try:
        s3.head_bucket(Bucket=bucket)
        log.info(f"Bucket already exists: {bucket}")
        return True
    except ClientError:
        log.info(f"Bucket {bucket} not found, creating it")
    try:
        # us-east-1: omit LocationConstraint or create_bucket fails
        s3.create_bucket(Bucket=bucket)
        log.info(f"Created bucket: {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error creating bucket {bucket}: {e}")
        return False


def make_public(bucket):
    """Allows anyone to accesss and read objects in the bucket, Claude really helped with understanding this function
    """
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )
        log.info(f"Turned off Block Public Access for {bucket}")
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket}/*",
                }
            ],
        }
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info(f"Attached public-read policy to {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error making {bucket} public: {e}")
        return False

def upload_files(bucket, file_paths):
    """Uploads files to the bucket
    """
    count = 0
    for path in file_paths:
        key = os.path.basename(path)
        try:
            with open(path,"rb") as f:
                s3.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=f,
                    ContentType="text/plain; charset=utf-8"
                )
            count += 1
            log.info(f"Uploaded {path} to s3://{bucket}/{key}")
        except FileNotFoundError:
            log.error(f"Local file not found: {path}")
        except ClientError as e:
            log.error(f"Error uploading {path}: {e}")
    log.info(f"Uploaded {count} {len(file_paths)} files")
    return count

def upload_index(bucket,index_path):
    """Upload the index page as index.html
    """
    try:
        with open(index_path,"rb") as f:
            s3.put_object(
                Bucket=bucket,
                Key="index.html",
                Body=f,
                ContentType="text/html",
            )
        log.info(f"Uploaded {index_path} to s3://{bucket}/index.html")
        return True
    except FileNotFoundError:
        log.error(f"Local file not found: {index_path}")
        return False
    except ClientError as err:
        log.error(f"Error uploading index page: {err}")
        return False

def main():
    """Downloads books, creates a public bucket, and uploads it all
    """
    list_file, index_path, bucket = parse_args()
    paths = download_books(list_file,"books")
    if not paths:
        log.error("No books downloaded, stopping")
        sys.exit(1)

    if not create_bucket(bucket):
        sys.exit(1)

    if not make_public(bucket):
        sys.exit(1)

    uploaded = upload_files(bucket,paths)
    index_ok = upload_index(bucket, index_path)

    if uploaded == len(paths) and index_ok:
        log.info("Success: all books and index page uploaded")
    else:
        log.error("finished with errors, check the log above")
    log.info(f"Public index page: https://{bucket}.s3.amazonaws.com/index.html")

if __name__ == "__main__":
    main()