#!/usr/bin/env python3
"""Minimal HTTPS mock of the AWS SSM GetParameters API (awsJson1.1 protocol).

Usage: mock_ssm.py CERT KEY REQUEST_LOG

Every request is appended to REQUEST_LOG as one JSON line:
  {"target": "<X-Amz-Target>", "body": {...request json...}}

Names starting with "/missing" are reported as InvalidParameters; every other
name gets value "value-for-<name with slashes replaced by dashes>".
"""
import json
import ssl
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

CERT, KEY, LOG = sys.argv[1], sys.argv[2], sys.argv[3]


def value_for(name):
    return "value-for-" + name.strip("/").replace("/", "-")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            req = json.loads(raw or b"{}")
        except Exception:
            req = {}
        with open(LOG, "a") as f:
            f.write(json.dumps({"target": self.headers.get("X-Amz-Target"), "body": req}) + "\n")
        names = req.get("Names", []) or []
        params = []
        invalid = []
        for nm in names:
            if nm.startswith("/missing"):
                invalid.append(nm)
            else:
                params.append({
                    "Name": nm,
                    "Value": value_for(nm),
                    "Type": "String",
                    "Version": 1,
                    "ARN": "arn:aws:ssm:us-east-1:123456789012:parameter" + (nm if nm.startswith("/") else "/" + nm),
                })
        out = json.dumps({"Parameters": params, "InvalidParameters": invalid}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/x-amz-json-1.1")
        self.send_header("Content-Length", str(len(out)))
        self.send_header("x-amzn-RequestId", "00000000-0000-0000-0000-000000000000")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


class Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


srv = Server(("127.0.0.1", 443), Handler)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(CERT, KEY)
srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
srv.serve_forever()
