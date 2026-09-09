from __future__ import annotations

import argparse
import json
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


TOPIC_KEYWORDS = {
    "bug": ("bug", "error", "broken", "failure", "crash"),
    "documentation": ("docs", "documentation", "readme", "guide", "instructions"),
    "data access": ("download", "access", "dataset", "dicom", "bids", "file"),
    "usability": ("ui", "ux", "widget", "form", "submit", "interface"),
    "feature request": ("feature", "enhancement", "request", "would like", "please add"),
}


@dataclass
class FeedbackSubmission:
    id: str
    created_at: str
    name: str
    email: str
    source_url: str
    category: str
    message: str


class FeedbackService:
    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.feedback_dir = self.data_dir / "feedback"
        self.issue_dir = self.data_dir / "issues"
        self.summary_path = self.data_dir / "summaries" / "topics.json"

    def submit_feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        cleaned = self._validate_payload(payload)
        topic = self.infer_topic(cleaned["category"], cleaned["message"])
        submission = FeedbackSubmission(
            id=str(uuid.uuid4()),
            created_at=self._timestamp(),
            name=cleaned["name"],
            email=cleaned["email"],
            source_url=cleaned["source_url"],
            category=cleaned["category"],
            message=cleaned["message"],
        )
        feedback_record = asdict(submission) | {"topic": topic}
        issue_payload = self.build_issue_payload(submission, topic)

        self._write_json(self.feedback_dir / f"{submission.id}.json", feedback_record)
        self._write_json(self.issue_dir / f"{submission.id}.json", issue_payload)
        summary = self.refresh_summary()

        return {
            "feedback": feedback_record,
            "issue": issue_payload,
            "summary": summary,
        }

    def build_issue_payload(self, submission: FeedbackSubmission, topic: str) -> dict[str, Any]:
        short_message = submission.message.strip().splitlines()[0][:72]
        title = f"[{submission.category}] {short_message or 'Repository feedback'}"
        labels = ["feedback", f"topic:{topic}"]
        if submission.category and submission.category != topic:
            labels.append(submission.category)

        body = "\n".join(
            [
                "## Repository feedback",
                "",
                f"- **Submitted at:** {submission.created_at}",
                f"- **Name:** {submission.name or 'Anonymous'}",
                f"- **Email:** {submission.email or 'Not provided'}",
                f"- **Source URL:** {submission.source_url or 'Not provided'}",
                f"- **Category:** {submission.category}",
                f"- **Topic:** {topic}",
                "",
                "### Message",
                submission.message,
            ]
        )

        return {
            "title": title,
            "body": body,
            "labels": labels,
            "topic": topic,
            "created_at": submission.created_at,
        }

    def refresh_summary(self) -> dict[str, Any]:
        topic_counter: Counter[str] = Counter()
        examples: dict[str, list[str]] = defaultdict(list)

        for feedback_file in sorted(self.feedback_dir.glob("*.json")):
            item = json.loads(feedback_file.read_text(encoding="utf-8"))
            topic = item.get("topic") or self.infer_topic(
                str(item.get("category", "")),
                str(item.get("message", "")),
            )
            topic_counter[topic] += 1
            if len(examples[topic]) < 3 and item.get("message"):
                examples[topic].append(str(item["message"]).strip())

        summary = {
            "generated_at": self._timestamp(),
            "total_feedback": sum(topic_counter.values()),
            "topics": [
                {
                    "name": topic,
                    "count": count,
                    "examples": examples[topic],
                }
                for topic, count in topic_counter.most_common()
            ],
        }
        self._write_json(self.summary_path, summary)
        return summary

    def infer_topic(self, category: str, message: str) -> str:
        normalized_category = category.strip().lower()
        if normalized_category and normalized_category != "general":
            return normalized_category

        lowered_message = message.strip().lower()
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(keyword in lowered_message for keyword in keywords):
                return topic
        return "general"

    def _validate_payload(self, payload: dict[str, Any]) -> dict[str, str]:
        cleaned = {
            "name": str(payload.get("name", "")).strip(),
            "email": str(payload.get("email", "")).strip(),
            "source_url": str(payload.get("source_url", "")).strip(),
            "category": str(payload.get("category", "general")).strip().lower() or "general",
            "message": str(payload.get("message", "")).strip(),
        }
        if not cleaned["message"]:
            raise ValueError("Feedback message is required.")
        if cleaned["source_url"]:
            parsed = urlparse(cleaned["source_url"])
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("source_url must be a valid http(s) URL.")
        return cleaned

    def _write_json(self, destination: Path, content: dict[str, Any]) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(content, indent=2), encoding="utf-8")

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()


class FeedbackRequestHandler(BaseHTTPRequestHandler):
    service: FeedbackService
    static_root: Path

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_common_headers("application/json")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/index.html"}:
            self._serve_file("index.html", "text/html; charset=utf-8")
            return
        if self.path == "/widget.js":
            self._serve_file("widget.js", "application/javascript; charset=utf-8")
            return
        if self.path == "/api/summary":
            summary = self.service.refresh_summary()
            self._send_json(HTTPStatus.OK, summary)
            return
        if self.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/feedback":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            response = self.service.submit_feedback(payload)
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Request body must be valid JSON."})
            return
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._send_json(HTTPStatus.CREATED, response)

    def _serve_file(self, filename: str, content_type: str) -> None:
        file_path = self.static_root / filename
        if not file_path.exists():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Static file not found"})
            return

        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._send_common_headers(content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_common_headers("application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_common_headers(self, content_type: str) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    data_dir: str | Path = "data",
    static_root: str | Path = "frontend",
) -> ThreadingHTTPServer:
    service = FeedbackService(data_dir)
    handler = type(
        "ConfiguredFeedbackRequestHandler",
        (FeedbackRequestHandler,),
        {
            "service": service,
            "static_root": Path(static_root),
        },
    )
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Brain Imaging Repository Feedback service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--static-root", default="frontend")
    args = parser.parse_args()

    server = create_server(
        host=args.host,
        port=args.port,
        data_dir=args.data_dir,
        static_root=args.static_root,
    )
    print(f"Serving feedback app on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
