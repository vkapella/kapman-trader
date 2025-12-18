from __future__ import annotations

import gzip
import io
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

import boto3
from botocore.config import Config


@dataclass(frozen=True)
class S3FlatfilesConfig:
    endpoint_url: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    prefix: str


def default_s3_flatfiles_config() -> S3FlatfilesConfig:
    endpoint_url = os.environ.get("S3_ENDPOINT_URL")
    bucket = os.environ.get("S3_BUCKET")
    access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    prefix = os.environ.get("POLYGON_S3_OHLCV_PREFIX", "us_stocks_sip/day_aggs_v1")

    missing: list[str] = []
    if not endpoint_url:
        missing.append("S3_ENDPOINT_URL")
    if not bucket:
        missing.append("S3_BUCKET")
    if not access_key_id:
        missing.append("AWS_ACCESS_KEY_ID")
    if not secret_access_key:
        missing.append("AWS_SECRET_ACCESS_KEY")
    if missing:
        raise RuntimeError(f"Missing required S3 env vars: {', '.join(missing)}")

    return S3FlatfilesConfig(
        endpoint_url=endpoint_url,
        bucket=bucket,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        prefix=prefix,
    )


def get_s3_client(cfg: S3FlatfilesConfig):
    return boto3.client(
        "s3",
        endpoint_url=cfg.endpoint_url,
        aws_access_key_id=cfg.access_key_id,
        aws_secret_access_key=cfg.secret_access_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def build_day_aggs_key(prefix: str, current_date: date) -> str:
    # Promoted from archive/scripts/init/04_load_ohlcv_base.py (Massive/Polygon flatfiles layout)
    return (
        f"{prefix}/{current_date.year}/{current_date.month:02d}/"
        f"{current_date.isoformat()}.csv.gz"
    )


def list_available_dates_in_range(
    s3,
    *,
    bucket: str,
    prefix: str,
    start: date,
    end: date,
) -> list[date]:
    if end < start:
        return []

    dates: set[date] = set()
    paginator = s3.get_paginator("list_objects_v2")

    # List by YYYY/MM prefixes to avoid scanning the whole bucket.
    cur = date(start.year, start.month, 1)
    while cur <= end:
        month_prefix = f"{prefix}/{cur.year}/{cur.month:02d}/"
        for page in paginator.paginate(Bucket=bucket, Prefix=month_prefix):
            for obj in page.get("Contents", []) or []:
                key = obj.get("Key") or ""
                filename = key.rsplit("/", 1)[-1]
                if not filename.endswith(".csv.gz"):
                    continue
                date_str = filename.removesuffix(".csv.gz")
                try:
                    d = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if start <= d <= end:
                    dates.add(d)

        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)

    return sorted(dates)


def fetch_gzipped_csv_bytes(s3, *, bucket: str, key: str) -> bytes:
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read()
    if not isinstance(body, (bytes, bytearray)):
        raise RuntimeError(f"Unexpected S3 body type for {key}: {type(body)!r}")
    return bytes(body)


def open_gzip_bytes(gz_bytes: bytes) -> io.TextIOBase:
    gz = gzip.GzipFile(fileobj=io.BytesIO(gz_bytes))
    return io.TextIOWrapper(gz, encoding="utf-8")


def iter_calendar_dates(start: date, end: date) -> Iterable[date]:
    cur = start
    while cur <= end:
        yield cur
        cur = cur.fromordinal(cur.toordinal() + 1)


def list_latest_available_dates(
    s3,
    *,
    bucket: str,
    prefix: str,
    limit: int,
    as_of: date | None = None,
) -> list[date]:
    if limit <= 0:
        return []

    as_of = as_of or (date.today() - timedelta(days=1))
    dates: set[date] = set()

    def end_of_month(month_start: date) -> date:
        if month_start.month == 12:
            next_month = date(month_start.year + 1, 1, 1)
        else:
            next_month = date(month_start.year, month_start.month + 1, 1)
        return next_month - timedelta(days=1)

    cur = date(as_of.year, as_of.month, 1)
    while len(dates) < limit:
        month_end = min(end_of_month(cur), as_of)
        month_dates = list_available_dates_in_range(
            s3,
            bucket=bucket,
            prefix=prefix,
            start=cur,
            end=month_end,
        )
        dates.update(month_dates)

        if cur.year == 1970:
            break
        if cur.month == 1:
            cur = date(cur.year - 1, 12, 1)
        else:
            cur = date(cur.year, cur.month - 1, 1)

    latest = sorted(dates)
    if len(latest) < limit:
        raise RuntimeError(
            f"Only found {len(latest)} available Polygon S3 daily files; need {limit}"
        )
    return latest[-limit:]
