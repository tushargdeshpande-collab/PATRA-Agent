import unittest

from patra.tools.resume_parser import parse_resume_text


class EnhancedParserTests(unittest.TestCase):
    def test_extra_sections_are_parsed_without_invention(self):
        raw = """Riya Kulkarni
riya@example.com
SUMMARY
Electronics student interested in embedded systems.
SKILLS
Python, Git
EXPERIENCE
Engineering Intern at Sample Labs | June 2025 - August 2025
- Tested sensor firmware using Python.
EDUCATION
B.E. Electronics, Sample University, 2027
PROJECTS
- Built an ESP32 environmental monitor.
CERTIFICATIONS
- Python Essentials certificate.
ACHIEVEMENTS
- Finalist in a college hackathon.
LEADERSHIP
- Coordinated the technical club.
LINKS
github.com/riya/sample
"""
        profile = parse_resume_text(raw)
        self.assertEqual(profile["name"], "Riya Kulkarni")
        self.assertEqual(len(profile["projects"]), 1)
        self.assertEqual(len(profile["certifications"]), 1)
        self.assertEqual(len(profile["achievements"]), 1)
        self.assertEqual(len(profile["leadership"]), 1)
        self.assertIn("github.com/riya/sample", profile["links"])

    def test_month_year_date_range_is_preserved(self):
        raw = """Riya Kulkarni
riya@example.com
SUMMARY
Engineering student with testing experience.
SKILLS
Python
EXPERIENCE
QA Intern at Sample Labs | June 2025 - August 2025
- Tested APIs using Python.
EDUCATION
B.E. Electronics, Sample University, 2027
"""
        profile = parse_resume_text(raw)
        self.assertIn("June 2025", profile["experience"][0]["period"])
        self.assertIn("August 2025", profile["experience"][0]["period"])


if __name__ == "__main__":
    unittest.main()
