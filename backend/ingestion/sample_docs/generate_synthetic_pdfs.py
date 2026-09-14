"""Generates 5 realistic synthetic university PDFs to test the ingestion pipeline against,
covering the scenarios the project needs to prove out:
  - CS4780 syllabus: prerequisite that references another course (STAT 3000) by code
  - STAT3000 syllabus: the course being asked about, no prerequisites
  - Prerequisite Override Policy: university-wide, deliberately STALE (tests staleness detection)
  - Academic Integrity Policy: university-wide, current
  - CS5000 syllabus: restricted to professor/admin only (tests permission filtering)

Run with: python generate_synthetic_pdfs.py
"""
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT_DIR = Path(__file__).parent

TITLE_STYLE = ParagraphStyle(name="Title", fontName="Helvetica-Bold", fontSize=18, spaceAfter=18)
HEADING_STYLE = ParagraphStyle(name="Heading", fontName="Helvetica-Bold", fontSize=14, spaceBefore=16, spaceAfter=8)
BODY_STYLE = ParagraphStyle(name="Body", fontName="Helvetica", fontSize=10.5, leading=15, spaceAfter=10)


def build_pdf(filename: str, title: str, sections: list[tuple[str, str]]) -> None:
    path = OUT_DIR / filename
    doc = SimpleDocTemplate(
        str(path), pagesize=LETTER,
        topMargin=0.9 * inch, bottomMargin=0.9 * inch, leftMargin=0.9 * inch, rightMargin=0.9 * inch,
    )
    story = [Paragraph(title, TITLE_STYLE), Spacer(1, 0.1 * inch)]
    for heading, body in sections:
        story.append(Paragraph(heading, HEADING_STYLE))
        for para in body.strip().split("\n\n"):
            story.append(Paragraph(para.strip().replace("\n", " "), BODY_STYLE))
    doc.build(story)
    print(f"wrote {path}")


def main() -> None:
    build_pdf(
        "CS4780_ML_Syllabus.pdf",
        "CS 4780 — Machine Learning: Course Syllabus",
        [
            ("1. Course Information",
             "Department: Computer Science. Credits: 4. Term: Fall 2025. Meeting Time: "
             "Tuesday/Thursday, 10:00-11:15am. Instructor: Prof. A. Rossi."),
            ("2. Prerequisites",
             "Students must complete STAT 3000 (Introduction to Statistics) or an equivalent "
             "statistics course with a grade of C or better before enrolling in CS 4780.\n\n"
             "Students who have not completed this prerequisite must request an override from "
             "the instructor prior to the add/drop deadline, using the university's Prerequisite "
             "Override Petition. Concurrent enrollment in STAT 3000 during the same term as CS 4780 "
             "is not permitted; the statistics requirement must be completed beforehand."),
            ("3. Course Description",
             "This course introduces the mathematical foundations and practical implementation of "
             "supervised and unsupervised machine learning methods, including linear and logistic "
             "regression, decision trees, neural networks, clustering, and dimensionality reduction. "
             "Heavy use is made of probability and statistics covered in the prerequisite course."),
            ("4. Grading Policy",
             "Homework 30%, Midterm Exam 25%, Final Project 30%, Participation 15%. Late homework "
             "is penalized 10% per day unless a university-approved extension is granted."),
            ("5. Course Schedule",
             "Weeks 1-2: Probability and statistics review. Weeks 3-4: Linear and logistic regression. "
             "Weeks 5-6: Decision trees and ensembles. Weeks 7-9: Neural networks. Weeks 10-11: "
             "Unsupervised learning. Weeks 12-14: Final project work and presentations."),
            ("6. Academic Integrity",
             "All students are bound by the university's Academic Integrity Policy. Suspected "
             "violations will be referred to the Office of Academic Affairs."),
        ],
    )

    build_pdf(
        "STAT3000_Syllabus.pdf",
        "STAT 3000 — Introduction to Statistics: Course Syllabus",
        [
            ("1. Course Information",
             "Department: Statistics. Credits: 3. Term: Fall 2025 and Spring 2026. "
             "Instructor: Prof. L. Chen."),
            ("2. Prerequisites",
             "None. This is an introductory course open to all undergraduates regardless of major "
             "or prior coursework. High-school algebra is assumed but no prior statistics or "
             "probability background is required."),
            ("3. Course Description",
             "Covers descriptive statistics, probability distributions, hypothesis testing, "
             "confidence intervals, and simple linear regression, with applications in R."),
            ("4. Grading Policy",
             "Homework 25%, Two Midterms 40%, Final Exam 35%."),
            ("5. Course Schedule",
             "Weeks 1-3: Descriptive statistics and probability. Weeks 4-6: Distributions and the "
             "Central Limit Theorem. Weeks 7-10: Hypothesis testing and confidence intervals. "
             "Weeks 11-14: Regression."),
        ],
    )

    build_pdf(
        "Prerequisite_Override_Policy.pdf",
        "University Policy: Prerequisite Override and Waiver Procedure",
        [
            ("1. Purpose",
             "This policy governs the process by which a student may request permission to enroll "
             "in a course without having completed its listed prerequisite(s)."),
            ("2. Eligibility",
             "A student may petition for a prerequisite override if they have completed equivalent "
             "coursework at another accredited institution, demonstrate equivalent knowledge through "
             "a placement exam, or have written support from the course instructor."),
            ("3. Petition Process",
             "Students seeking a prerequisite override must submit a Prerequisite Override Petition "
             "to the Office of the Registrar, accompanied by written approval from both the course "
             "instructor and the department chair, no later than the add/drop deadline for the term "
             "in which the course is offered.\n\n"
             "Petitions submitted without instructor approval will not be considered. Approved "
             "overrides are valid only for the specific term requested and do not permanently waive "
             "the prerequisite requirement on the student's academic record."),
            ("4. Appeals",
             "A denied petition may be appealed once to the Dean of the relevant college within "
             "10 business days of the denial notice."),
            ("5. Effective Date",
             "This policy took effect January 15, 2021 and was last formally reviewed on that date."),
        ],
    )

    build_pdf(
        "Academic_Integrity_Policy.pdf",
        "University Academic Integrity Policy",
        [
            ("1. Purpose",
             "This policy defines academic integrity expectations for all students, faculty, and "
             "staff, and establishes procedures for addressing violations."),
            ("2. Violations",
             "Violations include but are not limited to plagiarism, unauthorized collaboration, "
             "fabrication of data, multiple submission of the same work without permission, and "
             "facilitating another student's violation."),
            ("3. Reporting Process",
             "Faculty who suspect a violation must file a report with the Office of Academic Affairs "
             "within 15 business days of discovery, including all supporting evidence."),
            ("4. Sanctions",
             "First violations typically result in a failing grade on the assignment; repeat "
             "violations may result in course failure, suspension, or expulsion, determined by the "
             "Academic Integrity Board."),
            ("5. Effective Date",
             "This policy took effect March 1, 2025 and was last reviewed on that date."),
        ],
    )

    build_pdf(
        "CS5000_DeepLearning_Syllabus.pdf",
        "CS 5000 — Deep Learning: Course Syllabus (Draft — Instructor Use Only)",
        [
            ("1. Course Information",
             "Department: Computer Science. Credits: 4. Term: Spring 2026 (pending approval). "
             "Instructor: Prof. A. Rossi. Status: DRAFT, not yet published to students."),
            ("2. Prerequisites",
             "CS 4780 (Machine Learning) and STAT 3000 (Introduction to Statistics), or equivalent, "
             "each completed with a grade of B or better."),
            ("3. Course Description",
             "Graduate-level treatment of deep learning: backpropagation, convolutional and "
             "recurrent architectures, transformers, and generative models. Draft topic list "
             "pending curriculum committee review."),
            ("4. Grading Policy (Draft)",
             "Proposed: Homework 25%, Midterm 20%, Final Project 40%, Participation 15%. "
             "Not finalized; subject to change before publication."),
        ],
    )


if __name__ == "__main__":
    main()
