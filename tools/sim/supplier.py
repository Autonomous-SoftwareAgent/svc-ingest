"""Nhà cung cấp mô phỏng: gửi một gói tồn, điều kiện bán và giá mẫu tới Ingest.

Chỉ dùng thư viện chuẩn. Ví dụ:
  python tools/sim/supplier.py --url http://127.0.0.1:8080 --user acme-user --password '...' \
      --hotel HTL001 --room DLX --plan BAR
Gửi lại cùng --trace thì Ingest trả đúng TicketId cũ (khử trùng); đổi nội dung mà giữ --trace thì bị 409.
Đây là mô phỏng theo mô tả gói JSON của người dùng, KHÔNG phải nhà cung cấp thật.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
import uuid


def build(hotel: str, room: str, plan: str, rooms: int, price: int) -> dict:
    return {
        "hotelid": hotel,
        "room": [
            {
                "roomid": room,
                "date": [
                    {
                        "from": "2026-11-14",
                        "to": "2026-11-16",
                        "rate": [{"rateplanid": plan}],
                        "roomstosell": rooms,
                        "price": [{"NumberOfGuests": 1, "value": price}, {"NumberOfGuests": 2, "value": price}],
                        "extraadultrate": 300000,
                        "extrachildrate": 150000,
                        "closed": "0",
                        "closedonarrival": "0",
                        "closedondeparture": "0",
                        "minimumstay": 1,
                        "maximumstay": 14,
                        "dow": [1, 2, 3, 4, 5, 6, 7],
                    }
                ],
            }
        ],
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # console Windows (cp1252) không in được chữ có dấu
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--hotel", default="HTL001")
    ap.add_argument("--room", default="DLX")
    ap.add_argument("--plan", default="BAR")
    ap.add_argument("--rooms", type=int, default=2)
    ap.add_argument("--price", type=int, default=2150000)
    ap.add_argument("--channel", default="sim")
    ap.add_argument("--trace", default=None, help="X-Trace-Id (UUID); mặc định sinh mới")
    a = ap.parse_args()
    raw = json.dumps(build(a.hotel, a.room, a.plan, a.rooms, a.price)).encode()
    req = urllib.request.Request(
        a.url.rstrip("/") + "/v1/inventory-rates",
        data=raw,
        method="POST",
        headers={
            "Authorization": "Basic " + base64.b64encode(f"{a.user}:{a.password}".encode()).decode(),
            "X-Trace-Id": a.trace or str(uuid.uuid4()),
            "X-Channel-Id": a.channel,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(r.status, r.read().decode())
            return 0
    except urllib.error.HTTPError as e:
        print(e.code, e.read().decode())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
