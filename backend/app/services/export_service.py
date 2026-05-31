import io
import csv
from typing import List, Generator
import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.pdfgen import canvas

from app.models.database import Exam, Submission, Answer

class ExportService:
    @staticmethod
    def generate_submissions_csv_generator(exam: Exam, submissions: List[Submission]) -> Generator[str, None, None]:
        """
        Memory-efficient generator that yields formatted CSV rows for the exam submissions.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 1. Create dynamic header columns based on exam questions
        header = [
            "Submission ID",
            "Student ID",
            "Student Name",
            "Status",
            "Total Score",
            "Max Marks",
            "AI Confidence (%)"
        ]
        
        num_questions = len(exam.questions)
        for idx in range(num_questions):
            q_num = idx + 1
            header.append(f"Q{q_num} Score")
            header.append(f"Q{q_num} Feedback")
            
        writer.writerow(header)
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)
        
        max_marks = sum(q.max_marks for q in exam.questions)
        
        # 2. Yield submission rows
        for sub in submissions:
            row = [
                sub.id,
                sub.student_id or "",
                sub.student_name,
                sub.status.value,
                sub.total_score or 0.0,
                max_marks,
                round((sub.ai_confidence or 0.0) * 100, 1)
            ]
            
            # Map answers by question number for quick lookup
            ans_map = {a.question_number: a for a in sub.answers}
            for idx in range(num_questions):
                q_num = idx + 1
                ans = ans_map.get(q_num)
                if ans:
                    row.append(ans.final_score)
                    row.append(ans.ai_reasoning or "")
                else:
                    row.append(0.0)
                    row.append("No response graded.")
                    
            writer.writerow(row)
            yield output.getvalue()
            output.truncate(0)
            output.seek(0)

    @staticmethod
    def generate_student_pdf_bytes(submission: Submission, exam: Exam) -> bytes:
        """
        Compiles and renders a publication-quality vector PDF report card matching the ScorePilot visual system.
        """
        buffer = io.BytesIO()
        
        # Page geometry
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        
        # Premium design styles
        styles = getSampleStyleSheet()
        
        # Custom color system matching ScorePilot dark-glass themes
        primary_color = colors.HexColor("#0b0f19")   # Deep base dark
        accent_color = colors.HexColor("#22d3ee")    # Vibrant cyan
        accent_dark = colors.HexColor("#0891b2")     # Cyan dark accent
        text_white = colors.HexColor("#ffffff")
        text_light = colors.HexColor("#f1f5f9")
        text_muted = colors.HexColor("#64748b")
        border_color = colors.HexColor("#1e293b")
        card_bg = colors.HexColor("#111827")
        row_even = colors.HexColor("#161b26")
        row_odd = colors.HexColor("#1d2433")
        
        # Register new styled configurations
        title_style = ParagraphStyle(
            'PdfTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=22,
            textColor=text_white,
            leading=26
        )
        
        subtitle_style = ParagraphStyle(
            'PdfSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=accent_color,
            leading=14,
            spaceAfter=4
        )
        
        meta_label_style = ParagraphStyle(
            'MetaLabel',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=text_muted,
            leading=11
        )
        
        meta_value_style = ParagraphStyle(
            'MetaValue',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9.5,
            textColor=text_light,
            leading=11
        )
        
        summary_title_style = ParagraphStyle(
            'SummaryTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=text_muted,
            leading=12,
            alignment=1 # Center
        )
        
        score_style = ParagraphStyle(
            'SummaryScore',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=34,
            textColor=text_white,
            leading=40,
            alignment=1
        )
        
        th_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            textColor=text_white,
            leading=10
        )
        
        td_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            textColor=text_light,
            leading=11
        )
        
        td_bold_style = ParagraphStyle(
            'TableCellBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            textColor=text_light,
            leading=11
        )

        td_feedback_style = ParagraphStyle(
            'TableCellFeedback',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=7.5,
            textColor=text_muted,
            leading=10
        )

        story = []
        
        # --- HEADER BANNER ---
        header_data = [
            [
                Paragraph("OFFICIAL ACADEMIC EVALUATION", subtitle_style),
                ""
            ],
            [
                Paragraph("ScorePilot<font color='#22d3ee'>AI</font>", title_style),
                Paragraph(f"DATE: {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d')}", meta_label_style)
            ]
        ]
        
        header_table = Table(header_data, colWidths=[380, 160])
        header_table.setStyle(TableStyle([
            ('SPAN', (0, 0), (1, 0)),
            ('ALIGN', (1, 1), (1, 1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        # Wrapping header inside styled frame using drawBackground later
        story.append(header_table)
        story.append(Spacer(1, 20))
        
        # --- STUDENT METADATA PANEL ---
        max_marks = sum(q.max_marks for q in exam.questions)
        percentage = round((submission.total_score / max_marks) * 100, 1) if max_marks else 0.0
        status_text = "PASSED" if percentage >= 50 else "FAILED"
        status_color = "#10b981" if percentage >= 50 else "#ef4444"
        
        meta_data = [
            [
                Paragraph("STUDENT NAME", meta_label_style),
                Paragraph(submission.student_name, meta_value_style),
                Paragraph("EXAM TITLE", meta_label_style),
                Paragraph(exam.title, meta_value_style)
            ],
            [
                Paragraph("STUDENT ID", meta_label_style),
                Paragraph(submission.student_id or "N/A", meta_value_style),
                Paragraph("EXAM CODE", meta_label_style),
                Paragraph(exam.title[:8].upper().replace(" ", "-"), meta_value_style)
            ],
            [
                Paragraph("GRADED STATUS", meta_label_style),
                Paragraph(f"<font color='{status_color}'><b>{status_text}</b></font> ({submission.status.value.upper()})", meta_value_style),
                Paragraph("AI CONFIDENCE", meta_label_style),
                Paragraph(f"{round((submission.ai_confidence or 0.0) * 100, 1)}%", meta_value_style)
            ]
        ]
        
        meta_table = Table(meta_data, colWidths=[100, 170, 90, 180])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), card_bg),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 10),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#1e293b")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#1e293b")),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 20))
        
        # --- OVERALL GRADE CARD ---
        score_card_data = [
            [Paragraph("OVERALL SCORE VERIFIED", summary_title_style)],
            [Paragraph(f"{submission.total_score} <font size='16' color='#475569'>/ {max_marks}</font>", score_style)],
            [Paragraph(f"<font color='{status_color}'>SCORE PERCENTAGE: <b>{percentage}%</b></font>", summary_title_style)]
        ]
        
        score_table = Table(score_card_data, colWidths=[540])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#0f172a")),
            ('BOX', (0, 0), (-1, -1), 1, accent_dark),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('PADDING', (0, 0), (-1, -1), 12),
        ]))
        story.append(score_table)
        story.append(Spacer(1, 20))
        
        # --- DETAIL BREAKDOWN TABLE ---
        breakdown_header = [
            Paragraph("Q#", th_style),
            Paragraph("QUESTION & FEEDBACK SUMMARY", th_style),
            Paragraph("MARKS", th_style)
        ]
        
        breakdown_rows = [breakdown_header]
        
        ans_map = {a.question_number: a for a in submission.answers}
        for idx, q in enumerate(exam.questions):
            q_num = idx + 1
            ans = ans_map.get(q_num)
            score_got = ans.final_score if ans else 0.0
            feedback_text = ans.ai_reasoning if ans else "No response graded."
            
            q_text_paragraph = Paragraph(f"<b>{q.text[:80]}...</b>", td_bold_style)
            feedback_paragraph = Paragraph(feedback_text, td_feedback_style)
            
            # Combine question and feedback in a single cell using dynamic height Table or stacked Paragraphs
            cell_content = [q_text_paragraph, Spacer(1, 3), feedback_paragraph]
            
            breakdown_rows.append([
                Paragraph(f"Q{q_num}", td_bold_style),
                cell_content,
                Paragraph(f"<b>{score_got}</b> <font size='6.5' color='#64748b'>/ {q.max_marks}</font>", td_bold_style)
            ])
            
        breakdown_table = Table(breakdown_rows, colWidths=[40, 420, 80])
        
        # Generate row styling styles dynamically
        t_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
            ('BOX', (0, 0), (-1, -1), 1, border_color),
        ]
        
        for idx in range(1, len(breakdown_rows)):
            bg = row_even if idx % 2 == 0 else row_odd
            t_styles.append(('BACKGROUND', (0, idx), (-1, idx), bg))
            
        breakdown_table.setStyle(TableStyle(t_styles))
        story.append(breakdown_table)
        story.append(Spacer(1, 25))
        
        # --- VERIFICATION FOOTER ---
        footer_style = ParagraphStyle(
            'PdfFooter',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=7,
            textColor=text_muted,
            leading=9,
            alignment=1
        )
        
        verification_text = f"This report is programmatically compiled and verified by the ScorePilot AI grading pipeline.<br/>" \
                            f"Verification ID: {submission.id} • Generated at {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')} • Verified Role: SYSTEM"
                            
        story.append(Paragraph(verification_text, footer_style))
        
        # Custom Canvas drawer to enforce cinematic background color on pages!
        def draw_page_bg(canvas, doc):
            canvas.saveState()
            canvas.setFillColor(primary_color)
            canvas.rect(0, 0, letter[0], letter[1], fill=1)
            canvas.restoreState()
            
        doc.build(story, onFirstPage=draw_page_bg, onLaterPages=draw_page_bg)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
