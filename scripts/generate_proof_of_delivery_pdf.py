#!/usr/bin/env python3
"""Generate Ekko proof-of-delivery PDF for Milestones 2 and 3."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


REPO_WEB = "https://github.com/web3ekko/ekko-ce"
REPO_BLOB = f"{REPO_WEB}/blob/main"


def link(path: str, label: str | None = None) -> str:
    text = label or path
    return f'<link href="{REPO_BLOB}/{path}" color="#1d4ed8">{text}</link>'


def ext_link(url: str, label: str) -> str:
    return f'<link href="{url}" color="#1d4ed8">{label}</link>'


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleMain",
            parent=styles["Title"],
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Meta",
            parent=styles["Normal"],
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#334155"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            fontSize=15,
            leading=19,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=14,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubSection",
            parent=styles["Heading3"],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=8,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1e293b"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="Cell",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#0f172a"),
        )
    )
    return styles


def milestone_rows(styles):
    m2 = [
        (
            "Initiate partnerships with key enterprises in Avalanche L1s (Target: 5 partners)",
            "Partnership-ready workflows and group subscription UX shipped for enterprise onboarding.",
            "<br/>".join(
                [
                    link("screens/18-alert-groups-overview-current.png", "Alert Groups overview"),
                    link("screens/04-alert-group-visibility-step.png", "Group visibility controls"),
                    ext_link("https://app.ekko.zone", "Hosted production portal"),
                    "External artifact to attach: signed partner roster / MoUs (internal).",
                ]
            ),
        ),
        (
            "Design Community Edition branding and UI adjustments",
            "CE branding, positioning, and OSS launch assets prepared.",
            "<br/>".join(
                [
                    link("README.md", "CE product README"),
                    link("screens/GITHUB-SOCIAL-PREVIEW-SPEC.md", "GitHub social preview spec"),
                    link("screens/social-preview-ekko-ce-v1.png", "Social preview image"),
                ]
            ),
        ),
        (
            "Outreach to community developers for collaboration",
            "Developer-facing API and onboarding materials published in CE docs.",
            "<br/>".join(
                [
                    link("api/API_ENDPOINTS.md", "API endpoints"),
                    link("api/README.md", "API developer guide"),
                    link("dashboard/src/pages/DeveloperAPIPage.tsx", "Developer API UI page"),
                ]
            ),
        ),
        (
            "Implement core notification features for Community Edition",
            "Notification center UI and backend notification endpoints implemented.",
            "<br/>".join(
                [
                    link("screens/14-alert-detail-notifications-open.png", "Live notification panel screenshot"),
                    link("api/app/urls.py", "Notification API routes"),
                    link("api/docs/NOTIFICATION_CACHE_SCHEMA.md", "Notification cache schema"),
                ]
            ),
        ),
        (
            "Adapt frontend interfaces for Community Edition",
            "Dashboard, alert groups, alert detail, and template flows adapted for CE workflows.",
            "<br/>".join(
                [
                    link("screens/02-dashboard-logged-in.png", "Dashboard screenshot"),
                    link("screens/08-alert-template-add-modal.png", "Template assignment modal"),
                    link("dashboard/README.md", "Dashboard implementation overview"),
                ]
            ),
        ),
        (
            "Public access for Community Edition",
            "Public repository and self-hosted quick-start published.",
            "<br/>".join(
                [
                    ext_link(REPO_WEB, "Public GitHub repository"),
                    link("docker-compose.yml", "One-command compose deployment"),
                    link(".env.example", "Public environment template"),
                ]
            ),
        ),
        (
            "Prepare documentation and tutorials",
            "Technical docs published for API, dashboard, wasmCloud, and setup workflows.",
            "<br/>".join(
                [
                    link("README.md", "Root documentation"),
                    link("api/API_DOCUMENTATION.md", "API documentation"),
                    link("wasmcloud/README.md", "wasmCloud docs"),
                ]
            ),
        ),
        (
            "Release beta version with at least 5 partners included",
            "Beta delivery package prepared with partner-oriented alert group workflows and hosted onboarding.",
            "<br/>".join(
                [
                    link("screens/18-alert-groups-overview-current.png", "Beta UI snapshot"),
                    ext_link("https://app.ekko.zone", "Hosted beta/go-live environment"),
                    "External artifact to attach: partner inclusion ledger (internal).",
                ]
            ),
        ),
    ]

    m3 = [
        (
            "Testing and QA for both editions",
            "Comprehensive backend and runtime test suites present across CE services.",
            "<br/>".join(
                [
                    link("api/tests/", "API test suite"),
                    link("wasmcloud/tests/", "wasmCloud test suite"),
                    link("api/app/tests/", "Application service tests"),
                ]
            ),
        ),
        (
            "Testing and QA for the clients (web and mobile)",
            "Web client unit and E2E coverage present; mobile release links tracked externally.",
            "<br/>".join(
                [
                    link("dashboard/tests/", "Dashboard QA tests"),
                    ext_link("https://ekko.zone", "Landing page and docs"),
                    ext_link("https://app.ekko.zone", "Live app"),
                ]
            ),
        ),
        (
            "Testing and QA for browser extensions",
            "Browser extension QA tracked as external artifact for delivery package.",
            "<br/>".join(
                [
                    ext_link(REPO_WEB + "/issues", "Issue tracker / QA logs"),
                    "External artifact to attach: extension QA report.",
                ]
            ),
        ),
        (
            "Security testing and vulnerability assessments",
            "Security-focused authentication architecture and validation tests included.",
            "<br/>".join(
                [
                    link("api/authentication/README.md", "Authentication security overview"),
                    link("api/tests/test_authentication.py", "Authentication test coverage"),
                    link("api/authentication/API_DOCUMENTATION.md", "Auth API contract"),
                ]
            ),
        ),
        (
            "Bug fixes and performance optimizations",
            "Iterative fixes and runtime improvements documented through tests and optimized data flow components.",
            "<br/>".join(
                [
                    link("wasmcloud/providers/polars-eval/", "Polars evaluation provider"),
                    link("api/app/services/", "Core service layer"),
                    ext_link(REPO_WEB + "/commits/main", "Commit history"),
                ]
            ),
        ),
        (
            "Official release of Ekko Community Edition",
            "Community Edition launch assets and public onboarding completed.",
            "<br/>".join(
                [
                    ext_link(REPO_WEB, "Public CE repository"),
                    link("README.md", "Official CE launch README"),
                    ext_link(REPO_WEB + "/releases", "Release records"),
                ]
            ),
        ),
        (
            "Launch of paid features in Enterprise Edition",
            "Enterprise paid feature rollout tracked via hosted production platform and private product controls.",
            "<br/>".join(
                [
                    ext_link("https://app.ekko.zone", "Enterprise hosted platform"),
                    "External artifact to attach: billing/feature flag rollout report.",
                ]
            ),
        ),
        (
            "API documentation for developers",
            "Developer-facing API contracts and onboarding docs published.",
            "<br/>".join(
                [
                    link("api/API_ENDPOINTS.md", "API endpoint catalog"),
                    link("api/API_DOCUMENTATION.md", "Detailed API documentation"),
                    link("README.md", "Quick-start and API onboarding"),
                ]
            ),
        ),
        (
            "Feedback collection and iteration on both editions",
            "Feedback loops supported through issue tracking, release iterations, and roadmap updates.",
            "<br/>".join(
                [
                    ext_link(REPO_WEB + "/issues", "Issue-based feedback channel"),
                    ext_link(REPO_WEB + "/pulls", "Iteration and delivery PRs"),
                    ext_link(REPO_WEB + "/commits/main", "Continuous iteration log"),
                ]
            ),
        ),
        (
            "Ongoing API support and developer onboarding",
            "Persistent support artifacts available in docs and endpoint references.",
            "<br/>".join(
                [
                    link("api/README.md", "API support documentation"),
                    link("api/API_ENDPOINTS.md", "Endpoint usage reference"),
                    link("dashboard/src/pages/DeveloperAPIPage.tsx", "Developer onboarding UI"),
                ]
            ),
        ),
        (
            "Planning for future features and updates",
            "Forward-looking updates tracked through roadmap docs and release planning artifacts.",
            "<br/>".join(
                [
                    link("README.md", "Current release scope"),
                    link("screens/GITHUB-SOCIAL-PREVIEW-SPEC.md", "Launch collateral planning"),
                    ext_link(REPO_WEB + "/projects", "Roadmap board (if enabled)"),
                ]
            ),
        ),
        (
            "Release go-live version (alpha)",
            "Go-live alpha package delivered with public CE deployment path and hosted environment.",
            "<br/>".join(
                [
                    ext_link("https://ekko.zone", "Landing page and docs"),
                    ext_link("https://app.ekko.zone", "Hosted go-live endpoint"),
                    link("screens/02-dashboard-logged-in.png", "Go-live UI screenshot"),
                ]
            ),
        ),
    ]

    return m2, m3


def build_table(title: str, rows, styles):
    header = [
        Paragraph("<b>Delivery item</b>", styles["Cell"]),
        Paragraph("<b>Highlights</b>", styles["Cell"]),
        Paragraph("<b>Links</b>", styles["Cell"]),
    ]
    data = [header]

    for item, highlights, evidence in rows:
        data.append(
            [
                Paragraph(item, styles["Cell"]),
                Paragraph(highlights, styles["Cell"]),
                Paragraph(evidence, styles["Cell"]),
            ]
        )

    table = Table(data, colWidths=[170, 150, 195], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return [Paragraph(title, styles["Section"]), table]


def scaled_image(path: Path, width: float):
    img = Image(str(path))
    img._restrictSize(width, 5.2 * inch)
    return img


def generate_pdf(output_path: Path):
    styles = build_styles()
    m2_rows, m3_rows = milestone_rows(styles)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=34,
        leftMargin=34,
        topMargin=30,
        bottomMargin=30,
        title="Ekko - Milestones 2+3 Proof of Delivery",
        author="Ekko Core Team",
        subject="Proof of Delivery",
    )

    build_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    repo_root = Path(__file__).resolve().parents[1]
    screens = repo_root / "screens"

    story = []
    story.append(Paragraph("Ekko - Milestones 2+3", styles["TitleMain"]))
    story.append(Paragraph("Version: 0.3", styles["Meta"]))
    story.append(Paragraph("Prepared by: Ekko Core Team", styles["Meta"]))
    story.append(Paragraph(f"Generated: {build_date}", styles["Meta"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("How to read this document", styles["Section"]))
    bullets = ListFlowable(
        [
            ListItem(Paragraph("Highlights - concise summary of what was achieved.", styles["BodySmall"]), leftIndent=14),
            ListItem(Paragraph("Links - direct links to repositories, screenshots, or delivery documents.", styles["BodySmall"]), leftIndent=14),
            ListItem(Paragraph("Screenshots - visual confirmation of implemented workflows.", styles["BodySmall"]), leftIndent=14),
        ],
        bulletType="bullet",
        leftIndent=8,
    )
    story.append(bullets)
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            f"Primary OSS repository: {ext_link(REPO_WEB, REPO_WEB)}",
            styles["BodySmall"],
        )
    )

    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "1. Go-live version of the application with mobile submissions to iOS App Store and Google Play Store",
            styles["Section"],
        )
    )
    story.append(Paragraph("Highlights", styles["SubSection"]))
    story.append(
        Paragraph(
            "Go-live CE stack is publicly available and deployable via Docker Compose. "
            "Go-live references are provided via the landing page and live app endpoints, "
            "with final submission receipts to be attached to this pack.",
            styles["BodySmall"],
        )
    )
    story.append(Paragraph("Links", styles["SubSection"]))
    go_live_evidence = ListFlowable(
        [
            ListItem(Paragraph(ext_link("https://ekko.zone", "Ekko landing page and docs"), styles["BodySmall"]), leftIndent=14),
            ListItem(Paragraph(ext_link("https://app.ekko.zone", "Ekko live app"), styles["BodySmall"]), leftIndent=14),
            ListItem(Paragraph(link("README.md", "Public CE launch readme"), styles["BodySmall"]), leftIndent=14),
            ListItem(Paragraph("External attachment expected: submission confirmation screenshots and review status exports.", styles["BodySmall"]), leftIndent=14),
        ],
        bulletType="bullet",
        leftIndent=8,
    )
    story.append(go_live_evidence)

    story.append(PageBreak())
    story.extend(build_table("Milestone 2", m2_rows, styles))

    story.append(PageBreak())
    story.extend(build_table("Milestone 3", m3_rows, styles))

    story.append(PageBreak())
    story.append(Paragraph("Screenshots", styles["Section"]))
    story.append(
        Paragraph(
            "These screenshots are from the public repository and validate live product workflows for Community Edition.",
            styles["BodySmall"],
        )
    )
    story.append(Spacer(1, 8))

    screenshot_items = [
        ("Dashboard Home", "02-dashboard-logged-in.png"),
        ("Alert Groups Overview", "18-alert-groups-overview-current.png"),
        ("Create Group Visibility Step", "04-alert-group-visibility-step.png"),
        ("Add Template Modal", "08-alert-template-add-modal.png"),
        ("Alert Detail (Live)", "13-alert-detail-live-and-unread.png"),
        ("Alert Detail with Notifications", "14-alert-detail-notifications-open.png"),
    ]

    for idx, (caption, filename) in enumerate(screenshot_items, start=1):
        path = screens / filename
        story.append(Paragraph(f"{idx}. {caption}", styles["SubSection"]))
        story.append(Paragraph(link(f"screens/{filename}", f"GitHub link: {filename}"), styles["BodySmall"]))
        story.append(Spacer(1, 4))
        if path.exists():
            story.append(scaled_image(path, width=5.4 * inch))
        else:
            story.append(Paragraph(f"Screenshot missing in repo: {filename}", styles["BodySmall"]))
        story.append(Spacer(1, 10))

    story.append(PageBreak())
    story.append(Paragraph("Delivery Notes", styles["Section"]))
    story.append(
        Paragraph(
            "This proof-of-delivery package prioritizes verifiable links from the public OSS repository. "
            "Items that require private operational systems (partner contracts, store submission receipts, enterprise billing) "
            "are explicitly marked as external attachments for the final client delivery bundle.",
            styles["BodySmall"],
        )
    )

    doc.build(story)


def main():
    repo_root = Path(__file__).resolve().parents[1]
    out_dir = repo_root / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)

    output_pdf = out_dir / "proof-of-delivery-ekko-milestones-2-3-v0.3.pdf"
    generate_pdf(output_pdf)
    print(output_pdf)


if __name__ == "__main__":
    main()
