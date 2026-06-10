"""
Service de génération PDF.

Trois responsabilités :
  1. Générer le rapport principal (page 1) avec ReportLab.
  2. Convertir une image (JPG/JPEG/PNG) en page PDF A4 (Pillow + ReportLab).
  3. Fusionner le tout en UN seul PDF final (pypdf).

La conversion image -> PDF est volontairement isolée pour rester
clairement traçable, même si l'utilisateur ne la déclenche pas
manuellement.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from constants import (
    CONTROL_ITEMS,
    MAX_IMAGE_DIMENSION,
    STATUS_OK,
    STATUS_PROBLEM,
    status_label,
)
from services.file_service import get_extension, is_image
from services.logging_service import get_logger

logger = get_logger()

# Couleurs des statuts dans le PDF (texte robuste : pas de glyphe ✓/✗, non
# garantis dans les polices standard de ReportLab).
_COLOR_OK = colors.HexColor("#1a7f37")
_COLOR_PROBLEM = colors.HexColor("#b42318")
_COLOR_NONE = colors.HexColor("#6b7280")


def _escape(text: str) -> str:
    """Échappe le texte libre avant un rendu Paragraph (markup type XML)."""
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# --------------------------------------------------------------------------- #
# Structures de données
# --------------------------------------------------------------------------- #
@dataclass
class Attachment:
    """Un document téléversé, prêt à être intégré au PDF final."""

    filename: str
    data: bytes

    @property
    def is_image(self) -> bool:
        return is_image(self.filename)

    @property
    def is_pdf(self) -> bool:
        return get_extension(self.filename) == "pdf"


@dataclass
class ReportMetadata:
    """Données nécessaires à la page 1 du rapport."""

    branch: str
    control_date: str  # déjà formaté (YYYY-MM-DD)
    controller: str
    generated_at: str  # date + heure de génération
    # statut par point de contrôle : "ok" | "problem" | "" (non renseigné)
    statuses: dict[str, str]
    # commentaire éventuel par point de contrôle en problème
    problem_comments: dict[str, str] = field(default_factory=dict)
    observations: str = ""
    attachment_names: list[str] = field(default_factory=list)


@dataclass
class BuildResult:
    """Résultat de la construction du PDF final."""

    pdf_bytes: bytes
    errors: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# 1. Rapport principal (page 1)
# --------------------------------------------------------------------------- #
def generate_main_report_pdf(meta: ReportMetadata) -> bytes:
    """Génère le PDF de la page principale et retourne ses octets."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        title="Rapport de contrôle niveau 1",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        spaceAfter=6,
        textColor=colors.HexColor("#1f2d3d"),
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#5a6b7b"),
        spaceAfter=18,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        spaceBefore=14,
        spaceAfter=6,
        textColor=colors.HexColor("#1f2d3d"),
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"], fontSize=10, leading=14
    )
    ok_style = ParagraphStyle(
        "Ok", parent=body_style, textColor=_COLOR_OK, fontName="Helvetica-Bold",
    )
    problem_style = ParagraphStyle(
        "Problem", parent=body_style, textColor=_COLOR_PROBLEM,
        fontName="Helvetica-Bold",
    )
    none_style = ParagraphStyle(
        "None", parent=body_style, textColor=_COLOR_NONE,
    )
    comment_style = ParagraphStyle(
        "Comment", parent=body_style, fontName="Helvetica-Oblique",
        textColor=colors.HexColor("#374151"), leftIndent=8,
    )

    story: list = []

    # En-tête
    story.append(Paragraph("Rapport de contrôle niveau 1", title_style))
    story.append(
        Paragraph("Application de contrôle agences", subtitle_style)
    )

    # Bloc informations générales
    info_rows = [
        ["Agence", meta.branch],
        ["Date du contrôle", meta.control_date],
        ["Nom du contrôleur", meta.controller],
        ["Date et heure de génération", meta.generated_at],
    ]
    info_table = Table(info_rows, colWidths=[6 * cm, 10 * cm])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1f2d3d")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f4f7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d7de")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(info_table)

    # Checklist
    story.append(Paragraph("Points de contrôle", section_style))
    check_rows = [["Point de contrôle", "Statut"]]
    for key, label in CONTROL_ITEMS:
        status = meta.statuses.get(key) or ""
        status_text = status_label(status)
        if status == STATUS_OK:
            status_para = Paragraph(status_text, ok_style)
        elif status == STATUS_PROBLEM:
            status_para = Paragraph(status_text, problem_style)
        else:
            status_para = Paragraph(status_text, none_style)
        check_rows.append([Paragraph(label, body_style), status_para])

    check_table = Table(check_rows, colWidths=[11 * cm, 5 * cm])
    check_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2d3d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d7de")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f7f9fb")],
                ),
            ]
        )
    )
    story.append(check_table)

    # Problèmes signalés (uniquement pour les points en statut "problem")
    problems = [
        (label, (meta.problem_comments.get(key) or "").strip())
        for key, label in CONTROL_ITEMS
        if (meta.statuses.get(key) or "") == STATUS_PROBLEM
    ]
    if problems:
        story.append(Paragraph("Problèmes signalés", section_style))
        for label, comment in problems:
            story.append(Paragraph(f"<b>{_escape(label)}</b>", body_style))
            text = _escape(comment) if comment else "(sans commentaire)"
            story.append(Paragraph(text.replace("\n", "<br/>"), comment_style))
            story.append(Spacer(1, 0.2 * cm))

    # Observations
    story.append(Paragraph("Observations", section_style))
    observations = meta.observations.strip() or "Aucune observation."
    # On échappe les retours à la ligne pour le rendu Paragraph.
    observations_html = _escape(observations).replace("\n", "<br/>")
    story.append(Paragraph(observations_html, body_style))

    # Documents joints
    story.append(Paragraph("Documents scannés joints", section_style))
    if meta.attachment_names:
        for name in meta.attachment_names:
            story.append(Paragraph(f"&bull; {_escape(name)}", body_style))
    else:
        story.append(Paragraph("Aucun document joint.", body_style))

    story.append(Spacer(1, 1 * cm))

    doc.build(story)
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# 2. Conversion image -> page PDF A4
# --------------------------------------------------------------------------- #
def image_to_pdf_bytes(image_data: bytes) -> bytes:
    """
    Convertit une image en une page PDF A4 :
      - fond blanc,
      - conversion RGB sûre (gestion de la transparence),
      - redimensionnement de sécurité si l'image est très grande,
      - image centrée, ratio préservé.

    Lève une exception en cas d'image illisible/corrompue.
    """
    with Image.open(io.BytesIO(image_data)) as raw:
        raw.load()  # force la lecture (détecte les images corrompues)

        # Gestion de la transparence -> aplatissement sur fond blanc.
        if raw.mode in ("RGBA", "LA") or (
            raw.mode == "P" and "transparency" in raw.info
        ):
            rgba = raw.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            background.alpha_composite(rgba)
            img = background.convert("RGB")
        else:
            img = raw.convert("RGB")

    # Redimensionnement de sécurité (évite les images démesurées).
    if max(img.size) > MAX_IMAGE_DIMENSION:
        img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))

    buffer = io.BytesIO()
    page_width, page_height = A4
    c = canvas.Canvas(buffer, pagesize=A4)

    margin = 1.5 * cm
    avail_w = page_width - 2 * margin
    avail_h = page_height - 2 * margin

    img_w, img_h = img.size
    scale = min(avail_w / img_w, avail_h / img_h)
    draw_w = img_w * scale
    draw_h = img_h * scale
    x = (page_width - draw_w) / 2
    y = (page_height - draw_h) / 2

    c.drawImage(
        ImageReader(img),
        x,
        y,
        width=draw_w,
        height=draw_h,
        preserveAspectRatio=True,
        anchor="c",
    )
    c.showPage()
    c.save()
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# 3. Fusion PDF
# --------------------------------------------------------------------------- #
def merge_pdfs(pdf_chunks: list[bytes]) -> bytes:
    """Fusionne plusieurs PDF (en octets) en un seul, dans l'ordre fourni."""
    writer = PdfWriter()
    for chunk in pdf_chunks:
        reader = PdfReader(io.BytesIO(chunk))
        for page in reader.pages:
            writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    writer.close()
    return output.getvalue()


# --------------------------------------------------------------------------- #
# Orchestration : rapport principal + pièces jointes -> PDF final unique
# --------------------------------------------------------------------------- #
def build_final_report(
    meta: ReportMetadata, attachments: list[Attachment]
) -> BuildResult:
    """
    Construit le PDF final :
      page 1 = rapport principal,
      pages suivantes = documents joints (images converties, PDF fusionnés).

    Les erreurs par fichier sont collectées (et journalisées) sans interrompre
    le reste : un document illisible est ignoré et signalé.
    """
    errors: list[str] = []

    main_pdf = generate_main_report_pdf(meta)
    chunks: list[bytes] = [main_pdf]

    for att in attachments:
        try:
            if att.is_image:
                logger.info("Conversion image -> PDF : %s", att.filename)
                chunks.append(image_to_pdf_bytes(att.data))
            elif att.is_pdf:
                logger.info("Intégration du PDF : %s", att.filename)
                # On valide la lisibilité avant d'ajouter.
                PdfReader(io.BytesIO(att.data))
                chunks.append(att.data)
            else:
                msg = f"Format non pris en charge ignoré : {att.filename}"
                logger.warning(msg)
                errors.append(msg)
        except (PdfReadError, OSError, ValueError) as exc:
            msg = f"Document illisible ou corrompu, ignoré : {att.filename}"
            logger.error("%s (%s)", msg, exc)
            errors.append(msg)
        except Exception as exc:  # garde-fou : on n'interrompt jamais le rapport
            msg = f"Erreur lors du traitement de : {att.filename}"
            logger.exception("%s", msg)
            errors.append(msg)

    try:
        final_pdf = merge_pdfs(chunks)
    except Exception as exc:
        logger.exception("Échec de la fusion PDF : %s", exc)
        # En dernier recours, on renvoie au moins le rapport principal.
        errors.append(
            "La fusion des pièces jointes a échoué : seul le rapport "
            "principal a été conservé."
        )
        final_pdf = main_pdf

    return BuildResult(pdf_bytes=final_pdf, errors=errors)
