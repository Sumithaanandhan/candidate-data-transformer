from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

styles = getSampleStyleSheet()

def make_resume(path, lines):
    doc = SimpleDocTemplate(path, pagesize=letter)
    story = []
    for line in lines:
        story.append(Paragraph(line, styles['Normal']))
        story.append(Spacer(1, 6))
    doc.build(story)

make_resume("sources/resume_aarav_sharma.pdf", [
    "Aarav Sharma",
    "Email: aarav.sharma@gmail.com | Phone: +91-9876543210 | Bengaluru, Karnataka, India",
    "",
    "SUMMARY",
    "Software Engineer with 3 years experience building backend systems.",
    "",
    "SKILLS",
    "Python, Django, PostgreSQL, AWS, Docker, JS",
    "",
    "EXPERIENCE",
    "TechNova Solutions - Software Engineer II (2023-01 to Present)",
    "Building scalable APIs for the candidate matching platform.",
    "",
    "TechNova Solutions - Software Engineer (2021-06 to 2022-12)",
    "Worked on backend microservices.",
    "",
    "EDUCATION",
    "B.E. Computer Science, Sri Krishna College of Technology, 2021",
])

# Rohit's resume deliberately has no phone (CSV had it blank too) and has a skill
# alias ("JS") plus a slightly different company title than the CSV, to exercise
# the merge/conflict-resolution policy.
make_resume("sources/resume_rohit_verma.pdf", [
    "Rohit Verma",
    "rohit.verma@yahoo.com | Pune, Maharashtra, India",
    "",
    "SKILLS",
    "Java, Spring Boot, JS, MySQL, Kubernetes",
    "",
    "EXPERIENCE",
    "CloudSpire Inc - Backend Engineer (2022-03 to Present)",
    "Designed event-driven services handling 2M+ requests/day.",
    "",
    "EDUCATION",
    "B.Tech Information Technology, Anna University, 2020",
])

print("done")
