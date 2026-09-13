import io
import unittest

import docx as docx_lib
from reportlab.pdfgen import canvas

from patra.config import ALLOWED_RESUME_EXTENSIONS, MAX_UPLOAD_BYTES
from patra.tools.evidence import build_uploaded_evidence
from patra.tools.file_extract import UnsupportedFileError, extract_text
from patra.tools.resume_parser import parse_resume_text


def _make_pdf_bytes(text_lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    y = 800
    for line in text_lines:
        c.drawString(40, y, line)
        y -= 18
    c.save()
    return buffer.getvalue()


def _make_docx_bytes(text_lines: list[str]) -> bytes:
    document = docx_lib.Document()
    for line in text_lines:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


SAMPLE_RESUME_LINES = [
    "Jordan Rivera",
    "jordan.rivera@example.com | +1 555 123 4567",
    "SUMMARY",
    "Backend engineer focused on distributed systems and reliability.",
    "SKILLS",
    "Python, SQL, Git, Docker, Kubernetes, CI/CD",
    "EXPERIENCE",
    "Backend Engineer — Acme Corp | 2021-2024",
    "- Built Python microservices deployed with Docker and Kubernetes.",
    "- Automated CI/CD pipelines used by the whole engineering team.",
    "EDUCATION",
    "B.Tech Computer Science, State University, 2021",
]


class FileExtractionTests(unittest.TestCase):
    def test_extract_txt(self):
        text = extract_text("\n".join(SAMPLE_RESUME_LINES).encode(), "resume.txt")
        self.assertIn("Jordan Rivera", text)

    def test_extract_pdf(self):
        data = _make_pdf_bytes(SAMPLE_RESUME_LINES)
        text = extract_text(data, "resume.pdf")
        self.assertIn("Jordan Rivera", text)

    def test_extract_docx(self):
        data = _make_docx_bytes(SAMPLE_RESUME_LINES)
        text = extract_text(data, "resume.docx")
        self.assertIn("Jordan Rivera", text)

    def test_empty_file_rejected(self):
        with self.assertRaises(UnsupportedFileError):
            extract_text(b"", "resume.txt")

    def test_unsupported_extension_rejected(self):
        with self.assertRaises(UnsupportedFileError):
            extract_text(b"hello", "resume.exe", ALLOWED_RESUME_EXTENSIONS)

    def test_corrupted_pdf_rejected(self):
        with self.assertRaises(UnsupportedFileError):
            extract_text(b"%PDF-1.4 this is not a real pdf stream", "broken.pdf")

    def test_corrupted_docx_rejected(self):
        with self.assertRaises(UnsupportedFileError):
            extract_text(b"not a real zip/docx", "broken.docx")

    def test_oversized_file_rejected(self):
        data = b"a" * (MAX_UPLOAD_BYTES + 1)
        with self.assertRaises(UnsupportedFileError):
            extract_text(data, "huge.txt")

    def test_empty_text_file_rejected(self):
        with self.assertRaises(UnsupportedFileError):
            extract_text(b"   \n\n  ", "blank.txt")

    def test_scanned_pdf_with_no_text_rejected(self):
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer)
        c.save()  # a valid but blank/text-free PDF page
        with self.assertRaises(UnsupportedFileError):
            extract_text(buffer.getvalue(), "scanned.pdf")


class ResumeParserTests(unittest.TestCase):
    def test_parses_name_contact_skills_experience_education(self):
        raw = "\n".join(SAMPLE_RESUME_LINES)
        profile = parse_resume_text(raw)
        self.assertEqual(profile["name"], "Jordan Rivera")
        self.assertIn("jordan.rivera@example.com", profile["contact"])
        self.assertIn("Python", profile["skills"])
        self.assertTrue(profile["experience"])
        self.assertIn("Acme Corp", profile["experience"][0]["company"])
        self.assertTrue(any("Docker" in b["text"] for b in profile["experience"][0]["bullets"]))
        self.assertTrue(profile["education"])
        self.assertEqual(profile["_parse_warnings"], [])

    def test_never_invents_skills_not_in_text(self):
        raw = "\n".join(SAMPLE_RESUME_LINES)
        profile = parse_resume_text(raw)
        self.assertNotIn("Java", profile["skills"])
        self.assertNotIn("Selenium", profile["skills"])

    def test_malformed_resume_flags_warnings_instead_of_guessing(self):
        raw = "asdkjhasd asjkdhaskjd\nqweqweqwe\n12345"
        profile = parse_resume_text(raw)
        self.assertTrue(profile["_parse_warnings"])
        self.assertIn("not detected", profile["name"] + profile["contact"] + profile["summary"])

    def test_empty_resume_rejected(self):
        with self.assertRaises(ValueError):
            parse_resume_text("")

    def test_parsed_profile_is_valid_shape(self):
        from patra.tools.evidence import validate_profile
        raw = "\n".join(SAMPLE_RESUME_LINES)
        profile = parse_resume_text(raw)
        profile.pop("_parse_warnings")
        validated = validate_profile(profile)  # should not raise
        self.assertEqual(validated["name"], "Jordan Rivera")


class UploadedEvidenceTests(unittest.TestCase):
    def test_builds_records_for_valid_files(self):
        files = [("cert.txt", b"AWS Certified Solutions Architect, issued 2023.")]
        records, errors = build_uploaded_evidence(files)
        self.assertEqual(len(records), 1)
        self.assertEqual(errors, [])
        self.assertEqual(records[0]["source"], "cert.txt")
        self.assertIn("AWS Certified", records[0]["text"])

    def test_skips_malformed_files_without_aborting(self):
        files = [
            ("good.txt", b"Verified project evidence text."),
            ("bad.pdf", b"not a real pdf"),
        ]
        records, errors = build_uploaded_evidence(files)
        self.assertEqual(len(records), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("bad.pdf", errors[0])

    def test_empty_upload_list_returns_empty(self):
        records, errors = build_uploaded_evidence([])
        self.assertEqual(records, [])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
