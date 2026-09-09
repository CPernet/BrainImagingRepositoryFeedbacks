import json
import tempfile
import unittest
from pathlib import Path

from backend.app import FeedbackService


class FeedbackServiceTests(unittest.TestCase):
    def test_submit_feedback_persists_feedback_issue_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = FeedbackService(tmp_dir)

            response = service.submit_feedback(
                {
                    "name": "Researcher",
                    "email": "researcher@example.org",
                    "source_url": "https://example.org/datasets/brain-study",
                    "category": "bug",
                    "message": "The download button fails for the BIDS archive.",
                }
            )

            feedback_files = list((Path(tmp_dir) / "feedback").glob("*.json"))
            issue_files = list((Path(tmp_dir) / "issues").glob("*.json"))
            summary_path = Path(tmp_dir) / "summaries" / "topics.json"

            self.assertEqual(len(feedback_files), 1)
            self.assertEqual(len(issue_files), 1)
            self.assertTrue(summary_path.exists())
            self.assertEqual(response["feedback"]["topic"], "bug")
            self.assertIn("topic:bug", response["issue"]["labels"])

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["total_feedback"], 1)
            self.assertEqual(summary["topics"][0]["name"], "bug")
            self.assertEqual(summary["analysis"]["lexical_frequency"][0]["term"], "download")
            self.assertEqual(summary["analysis"]["semantic_phrases"][0]["phrase"], "download button")

    def test_infer_topic_falls_back_to_message_keywords(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = FeedbackService(tmp_dir)

            response = service.submit_feedback(
                {
                    "category": "general",
                    "message": "Please add clearer documentation for the MRI preprocessing steps.",
                }
            )

            self.assertEqual(response["feedback"]["topic"], "documentation")
            self.assertEqual(response["summary"]["topics"][0]["name"], "documentation")
            self.assertIn(
                {"term": "documentation", "count": 1},
                response["summary"]["analysis"]["lexical_frequency"],
            )

    def test_summary_analysis_prioritizes_semantics_and_lexical_frequency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = FeedbackService(tmp_dir)

            summary = service.submit_feedback(
                {
                    "message": (
                        "Phonology analysis is not useful, it's more about extracting "
                        "semantics -- lexical freq is useful though."
                    ),
                }
            )["summary"]

            self.assertIn(
                {"term": "semantics", "count": 1},
                summary["analysis"]["lexical_frequency"],
            )
            self.assertIn(
                {"term": "lexical", "count": 1},
                summary["analysis"]["lexical_frequency"],
            )
            self.assertIn(
                {"phrase": "extracting semantics", "count": 1},
                summary["analysis"]["semantic_phrases"],
            )

    def test_invalid_source_url_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = FeedbackService(tmp_dir)

            with self.assertRaisesRegex(ValueError, "source_url must be a valid http"):
                service.submit_feedback(
                    {
                        "source_url": "ftp://example.org/bad",
                        "message": "The widget should reject unsupported URLs.",
                    }
                )


if __name__ == "__main__":
    unittest.main()
