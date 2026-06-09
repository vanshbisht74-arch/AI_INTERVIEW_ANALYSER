"""
report_generator.py
--------------------
Generates a professional PDF interview performance report using ReportLab.
Saves output to the reports/ directory.
"""

import os
import time
from datetime import datetime
from typing import TYPE_CHECKING

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether
    )
    from reportlab.graphics.shapes import Drawing, Rect, String, Circle
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics import renderPDF
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

if TYPE_CHECKING:
    from interview_manager import InterviewSession


# ─── Color palette ────────────────────────────────────────────────────────────
C_DARK    = colors.HexColor("#0D1117")
C_CARD    = colors.HexColor("#161B22")
C_ACCENT  = colors.HexColor("#00D4FF")
C_GREEN   = colors.HexColor("#3FB950")
C_ORANGE  = colors.HexColor("#F78166")
C_YELLOW  = colors.HexColor("#E3B341")
C_WHITE   = colors.white
C_GRAY    = colors.HexColor("#8B949E")
C_LIGHT   = colors.HexColor("#C9D1D9")


class ReportGenerator:
    """Builds and saves a PDF performance report for an interview session."""

    def __init__(self, settings=None):
        self.settings    = settings
        self.reports_dir = settings.reports_dir if settings else "reports"
        os.makedirs(self.reports_dir, exist_ok=True)

    # ─── Public API ───────────────────────────────────────────────────────────

    def generate(self, session) -> str:
        """
        Build the PDF report and return the file path.
        Falls back to a plain-text report if ReportLab is not available.
        """
        ts       = time.strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in session.candidate_name if c.isalnum() or c in " _-")
        filename  = f"report_{safe_name}_{ts}.pdf"
        filepath  = os.path.join(self.reports_dir, filename)

        if not REPORTLAB_AVAILABLE:
            return self._generate_text_report(session, filepath.replace(".pdf", ".txt"))

        try:
            self._build_pdf(session, filepath)
            return filepath
        except Exception as e:
            print(f"[ReportGenerator] PDF error: {e}")
            return self._generate_text_report(session, filepath.replace(".pdf", ".txt"))

    # ─── PDF builder ──────────────────────────────────────────────────────────

    def _build_pdf(self, session, filepath: str):
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=1.5*cm, leftMargin=1.5*cm,
            topMargin=1.5*cm,   bottomMargin=1.5*cm,
        )

        styles = self._build_styles()
        story  = []

        # ── Header ────────────────────────────────────────────────────────────
        story.append(self._header_block(session, styles))
        story.append(Spacer(1, 0.4*cm))
        story.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT))
        story.append(Spacer(1, 0.4*cm))

        # ── Score cards row ───────────────────────────────────────────────────
        story.append(Paragraph("PERFORMANCE OVERVIEW", styles["section_title"]))
        story.append(Spacer(1, 0.3*cm))
        story.append(self._score_cards_table(session.scores, styles))
        story.append(Spacer(1, 0.5*cm))

        # ── Detailed metrics ──────────────────────────────────────────────────
        story.append(Paragraph("DETAILED METRICS", styles["section_title"]))
        story.append(Spacer(1, 0.3*cm))
        story.append(self._metrics_table(session, styles))
        story.append(Spacer(1, 0.5*cm))

        # ── Filler words ──────────────────────────────────────────────────────
        filler_data = session.metrics.get("filler_totals", {})
        if filler_data.get("counts"):
            story.append(Paragraph("FILLER WORD ANALYSIS", styles["section_title"]))
            story.append(Spacer(1, 0.3*cm))
            story.append(self._filler_table(filler_data, styles))
            story.append(Spacer(1, 0.5*cm))

        # ── Strengths ─────────────────────────────────────────────────────────
        story.append(Paragraph("✓  STRENGTHS", styles["strength_title"]))
        story.append(Spacer(1, 0.2*cm))
        for s in session.strengths:
            story.append(Paragraph(f"• {s}", styles["bullet"]))
        story.append(Spacer(1, 0.4*cm))

        # ── Areas for improvement ─────────────────────────────────────────────
        story.append(Paragraph("⚑  AREAS FOR IMPROVEMENT", styles["improve_title"]))
        story.append(Spacer(1, 0.2*cm))
        for s in session.improvements:
            story.append(Paragraph(f"• {s}", styles["bullet"]))
        story.append(Spacer(1, 0.5*cm))

        # ── Performance summary ───────────────────────────────────────────────
        story.append(HRFlowable(width="100%", thickness=1, color=C_GRAY))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph("PERFORMANCE SUMMARY", styles["section_title"]))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(self._summary_text(session), styles["body"]))

        # ── Footer ────────────────────────────────────────────────────────────
        story.append(Spacer(1, 0.5*cm))
        story.append(HRFlowable(width="100%", thickness=1, color=C_ACCENT))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(
            "Generated by AI Interview Analyzer — Confidential",
            styles["footer"]
        ))

        doc.build(story)

    # ─── Component builders ───────────────────────────────────────────────────

    def _header_block(self, session, styles):
        date_str = datetime.now().strftime("%B %d, %Y  %H:%M")
        dur_min  = int(session.duration_sec // 60)
        dur_sec  = int(session.duration_sec % 60)

        data = [
            [
                Paragraph("AI INTERVIEW ANALYZER", styles["main_title"]),
                Paragraph(f"Date: {date_str}", styles["header_right"]),
            ],
            [
                Paragraph(f"Candidate: {session.candidate_name}", styles["candidate"]),
                Paragraph(f"Duration: {dur_min}m {dur_sec}s", styles["header_right"]),
            ],
        ]
        t = Table(data, colWidths=["65%", "35%"])
        t.setStyle(TableStyle([
            ("VALIGN",    (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",(0, 0), (-1, -1), 4),
        ]))
        return t

    def _score_cards_table(self, scores: dict, styles):
        """Render five score cards in a horizontal table."""
        cards = [
            ("CONFIDENCE",    scores.get("confidence_score",    0), C_ACCENT),
            ("EYE CONTACT",   scores.get("eye_contact_score",   0), C_GREEN),
            ("COMMUNICATION", scores.get("communication_score", 0), C_YELLOW),
            ("SPEECH",        scores.get("speech_score",        0), C_ORANGE),
            ("OVERALL",       scores.get("overall_score",       0), C_ACCENT),
        ]

        headers = [Paragraph(label, styles["card_label"]) for label, _, _ in cards]
        values  = []
        for _, val, col in cards:
            style = ParagraphStyle(
                "score_val",
                fontSize=26, fontName="Helvetica-Bold",
                textColor=col, alignment=TA_CENTER
            )
            values.append(Paragraph(f"{val:.0f}", style))
        bars = []
        for _, val, col in cards:
            # Simple % bar using colored Paragraph
            filled  = int(val / 10)
            empty   = 10 - filled
            bar_txt = "█" * filled + "░" * empty
            bar_sty = ParagraphStyle(
                "bar", fontSize=7, fontName="Helvetica",
                textColor=col, alignment=TA_CENTER
            )
            bars.append(Paragraph(bar_txt, bar_sty))

        data = [headers, values, bars]
        t = Table(data, colWidths=["20%"] * 5)
        t.setStyle(TableStyle([
            ("BACKGROUND",  (0, 0), (-1, -1), C_CARD),
            ("ROWBACKGROUND",(0, 0), (-1, 0), C_DARK),
            ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",  (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING",(0, 0),(-1, -1), 8),
            ("ROUNDEDCORNERS",(0,0),(-1,-1), 4),
            ("BOX",         (0, 0), (-1, -1), 1, C_ACCENT),
            ("INNERGRID",   (0, 0), (-1, -1), 0.5, C_GRAY),
        ]))
        return t

    def _metrics_table(self, session, styles):
        metrics = session.metrics
        scores  = session.scores

        rows = [
            ["Metric", "Value", "Rating"],
            ["Eye Contact",      f"{metrics.get('eye_contact_pct', 0):.1f}%",
             self._rating(scores.get("eye_contact_score", 0))],
            ["Speaking Speed",   f"{metrics.get('words_per_minute', 0):.0f} WPM",
             self._rating(scores.get("speech_score", 0))],
            ["Speaking Time",    f"{metrics.get('speaking_time_sec', 0):.0f} sec",
             "—"],
            ["Pause Count",      str(metrics.get("pause_count", 0)),
             "—"],
            ["Filler Words",     str(metrics.get("filler_word_count", 0)),
             self._rating(100 - min(100, metrics.get("filler_word_count", 0) * 5))],
            ["Smile Detected",   f"{metrics.get('smile_percentage', 0):.1f}%",
             "—"],
            ["Head Stability",   f"{metrics.get('head_stability', 0) * 100:.0f}%",
             self._rating(metrics.get("head_stability", 0) * 100)],
            ["Overall Score",    f"{scores.get('overall_score', 0):.1f}/100",
             self._rating(scores.get("overall_score", 0))],
        ]

        t = Table(rows, colWidths=["40%", "30%", "30%"])
        style = TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), C_ACCENT),
            ("TEXTCOLOR",     (0, 0), (-1, 0), C_DARK),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 10),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_CARD, C_DARK]),
            ("TEXTCOLOR",     (0, 1), (-1, -1), C_LIGHT),
            ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",      (0, 1), (-1, -1), 9),
            ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
            ("ALIGN",         (0, 0), (0, -1),  "LEFT"),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (0, -1),  8),
            ("BOX",           (0, 0), (-1, -1), 1, C_ACCENT),
            ("INNERGRID",     (0, 0), (-1, -1), 0.3, C_GRAY),
        ])
        t.setStyle(style)
        return t

    def _filler_table(self, filler_data: dict, styles):
        counts = filler_data.get("counts", {})
        rows   = [["Filler Word", "Occurrences"]]
        for word, cnt in sorted(counts.items(), key=lambda x: -x[1]):
            rows.append([word.title(), str(cnt)])
        rows.append(["TOTAL", str(filler_data.get("total", 0))])

        t = Table(rows, colWidths=["60%", "40%"])
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0),  C_ORANGE),
            ("TEXTCOLOR",    (0, 0), (-1, 0),  C_DARK),
            ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("ROWBACKGROUNDS",(0,1), (-1, -2), [C_CARD, C_DARK]),
            ("BACKGROUND",   (0,-1),(-1, -1),  C_CARD),
            ("FONTNAME",     (0,-1),(-1, -1),  "Helvetica-Bold"),
            ("TEXTCOLOR",    (0, 1),(-1, -1),  C_LIGHT),
            ("ALIGN",        (1, 0),(-1, -1),  "CENTER"),
            ("TOPPADDING",   (0, 0),(-1, -1),  5),
            ("BOTTOMPADDING",(0, 0),(-1, -1),  5),
            ("BOX",          (0, 0),(-1, -1),  1, C_ORANGE),
            ("INNERGRID",    (0, 0),(-1, -1),  0.3, C_GRAY),
        ]))
        return t

    # ─── Styles ───────────────────────────────────────────────────────────────

    def _build_styles(self):
        return {
            "main_title": ParagraphStyle(
                "main_title", fontSize=18, fontName="Helvetica-Bold",
                textColor=C_ACCENT, spaceAfter=4
            ),
            "candidate": ParagraphStyle(
                "candidate", fontSize=13, fontName="Helvetica-Bold",
                textColor=C_WHITE
            ),
            "header_right": ParagraphStyle(
                "header_right", fontSize=9, fontName="Helvetica",
                textColor=C_GRAY, alignment=TA_RIGHT
            ),
            "section_title": ParagraphStyle(
                "section_title", fontSize=11, fontName="Helvetica-Bold",
                textColor=C_ACCENT, spaceAfter=4, spaceBefore=4
            ),
            "card_label": ParagraphStyle(
                "card_label", fontSize=8, fontName="Helvetica-Bold",
                textColor=C_GRAY, alignment=TA_CENTER
            ),
            "strength_title": ParagraphStyle(
                "strength_title", fontSize=11, fontName="Helvetica-Bold",
                textColor=C_GREEN, spaceAfter=4
            ),
            "improve_title": ParagraphStyle(
                "improve_title", fontSize=11, fontName="Helvetica-Bold",
                textColor=C_ORANGE, spaceAfter=4
            ),
            "bullet": ParagraphStyle(
                "bullet", fontSize=9, fontName="Helvetica",
                textColor=C_LIGHT, leftIndent=12, spaceAfter=3
            ),
            "body": ParagraphStyle(
                "body", fontSize=9, fontName="Helvetica",
                textColor=C_LIGHT, leading=14
            ),
            "footer": ParagraphStyle(
                "footer", fontSize=8, fontName="Helvetica",
                textColor=C_GRAY, alignment=TA_CENTER
            ),
        }

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _rating(self, score: float) -> str:
        if score >= 85: return "Excellent"
        if score >= 70: return "Good"
        if score >= 55: return "Fair"
        return "Needs Work"

    def _summary_text(self, session) -> str:
        overall = session.scores.get("overall_score", 0)
        if overall >= 85:
            tier = "outstanding"
        elif overall >= 70:
            tier = "strong"
        elif overall >= 55:
            tier = "promising"
        else:
            tier = "developing"

        return (
            f"{session.candidate_name} delivered a {tier} interview performance "
            f"with an overall score of {overall:.0f}/100. "
            f"The session lasted {int(session.duration_sec // 60)} minutes and "
            f"{int(session.duration_sec % 60)} seconds. "
            "Focus on the areas for improvement above to continue growing. "
            "Regular practice with the AI Interview Analyzer will help track "
            "progress and build lasting interview confidence."
        )

    def _generate_text_report(self, session, filepath: str) -> str:
        """Plain-text fallback when ReportLab is not installed."""
        filepath = filepath.replace(".pdf", ".txt")
        lines = [
            "=" * 60,
            "         AI INTERVIEW ANALYZER — PERFORMANCE REPORT",
            "=" * 60,
            f"Candidate : {session.candidate_name}",
            f"Date      : {datetime.now().strftime('%B %d, %Y %H:%M')}",
            f"Duration  : {int(session.duration_sec // 60)}m {int(session.duration_sec % 60)}s",
            "",
            "─── SCORES ───────────────────────────────────────────────",
        ]
        for k, v in session.scores.items():
            if not k.startswith("_"):
                lines.append(f"  {k:<25} {v}")
        lines += [
            "",
            "─── METRICS ──────────────────────────────────────────────",
        ]
        for k, v in session.metrics.items():
            lines.append(f"  {k:<25} {v}")
        lines += ["", "─── STRENGTHS ────────────────────────────────────────────"]
        for s in session.strengths:
            lines.append(f"  • {s}")
        lines += ["", "─── AREAS FOR IMPROVEMENT ────────────────────────────────"]
        for s in session.improvements:
            lines.append(f"  • {s}")
        lines += ["", "=" * 60,
                  "Generated by AI Interview Analyzer", "=" * 60]

        with open(filepath, "w") as f:
            f.write("\n".join(lines))
        return filepath
