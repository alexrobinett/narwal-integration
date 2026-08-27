#!/usr/bin/env python3
"""Passive Narwal MQTT capture. Subscribes to push topics only; never publishes.
Appends one JSON line per message to ./capture.jsonl with a generic protobuf
decode. Run: nohup .venv/bin/python -u scripts/capture.py &

Credentials come from environment variables:
  NARWAL_PRODUCT_KEY, NARWAL_DEVICE_ID, NARWAL_USER_UUID, NARWAL_ACCESS_TOKEN
or, if NARWAL_STORAGE_CONFIG_ENTRIES is set, from that Home Assistant
.storage/core.config_entries file (first narwal entry).
"""
import json, os, ssl, struct, sys, time, uuid
import paho.mqtt.client as mqtt

if os.environ.get("NARWAL_STORAGE_CONFIG_ENTRIES"):
    ce = [e for e in json.load(open(os.environ["NARWAL_STORAGE_CONFIG_ENTRIES"]))['data']['entries'] if e['domain'] == 'narwal'][0]['data']
    PK, DN, UUID_, TOKEN = ce['product_key'], ce['device_name'], ce['user_uuid'], ce['access_token']
else:
    try:
        PK, DN, UUID_, TOKEN = (os.environ[k] for k in ("NARWAL_PRODUCT_KEY", "NARWAL_DEVICE_ID", "NARWAL_USER_UUID", "NARWAL_ACCESS_TOKEN"))
    except KeyError as e:
        sys.exit(f"ERROR: environment variable {e.args[0]} is required (or set NARWAL_STORAGE_CONFIG_ENTRIES)")
BASE = f"/{PK}/{DN}"
TOPICS = ["status/robot_base_status", "status/working_status", "status/upgrade_status", "map/display_map"]
OUT = open('capture.jsonl', 'a')

def read_varint(b, i):
    r = s = 0
    while True:
        c = b[i]; r |= (c & 0x7F) << s; i += 1; s += 7
        if not c & 0x80: return r, i

def parse(b, depth=0):
    """Generic protobuf field parse; LEN fields recursively tried as messages."""
    out = {}; i = 0
    try:
        while i < len(b):
            key, i = read_varint(b, i); f, wt = key >> 3, key & 7
            if wt == 0: v, i = read_varint(b, i)
            elif wt == 1: v = {"fixed64": b[i:i+8].hex(), "f64": struct.unpack('<d', b[i:i+8])[0]}; i += 8
            elif wt == 5:
                raw = b[i:i+4]; i += 4
                v = {"u32": struct.unpack('<I', raw)[0], "f32": round(struct.unpack('<f', raw)[0], 3)}
            elif wt == 2:
                ln, i = read_varint(b, i); chunk = b[i:i+ln]; i += ln
                v = None
                if depth < 4 and ln > 0:
                    sub = parse(chunk, depth + 1)
                    if sub is not None: v = sub
                if v is None:
                    try:
                        s = chunk.decode('utf-8'); v = s if s.isprintable() else chunk.hex()
                    except UnicodeDecodeError: v = chunk.hex() if ln <= 64 else f"<{ln} bytes> {chunk[:24].hex()}…"
            else: return None
            out.setdefault(str(f), []).append(v)
    except Exception:
        return None
    return {k: (v[0] if len(v) == 1 else v) for k, v in out.items()}

def strip_frame(p):
    if p and p[0] == 0x01:
        i = 1
        while p[i] & 0x80: i += 1
        return p[i+1:]
    return p

def on_connect(c, u, f, rc, p=None):
    print(time.strftime('%H:%M:%S'), "connected", rc, flush=True)
    for t in TOPICS: c.subscribe(f"{BASE}/{t}", qos=1)

def on_message(c, u, msg):
    suffix = msg.topic.replace(BASE, "").lstrip("/")
    body = strip_frame(msg.payload)
    rec = {"ts": time.strftime('%Y-%m-%dT%H:%M:%S'), "topic": suffix, "len": len(msg.payload),
           "raw": msg.payload.hex() if len(msg.payload) <= 600 else msg.payload[:600].hex() + "…",
           "fields": parse(body)}
    OUT.write(json.dumps(rec) + "\n"); OUT.flush()
    f = rec["fields"] or {}
    summary = {k: f[k] for k in ("2", "3", "11", "47") if k in f} if suffix == "status/robot_base_status" else {k: f.get(k) for k in ("3", "13", "15")} if suffix == "status/working_status" else {"keys": list(f.keys())[:12]}
    print(rec["ts"][11:], suffix, rec["len"], "b", json.dumps(summary)[:220], flush=True)

def on_disconnect(c, u, df=None, rc=None, p=None):
    print(time.strftime('%H:%M:%S'), "disconnected", rc, flush=True)

c = mqtt.Client(client_id=f"app_{UUID_}_{uuid.uuid4()}", protocol=mqtt.MQTTv5, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
c.username_pw_set(UUID_, TOKEN); c.tls_set_context(ssl.create_default_context())
c.on_connect = on_connect; c.on_message = on_message; c.on_disconnect = on_disconnect
c.reconnect_delay_set(2, 30)
c.connect("us-01.mqtt.narwaltech.com", 8883, keepalive=30)
c.loop_forever(retry_first_connection=True)
