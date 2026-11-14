
from __future__ import annotations

import logging
import math
import re
import unicodedata

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from langchain_core.documents import Document


logger = logging.getLogger(__name__)


@dataclass
class PDFExtractionConfig:
    # Remove repeated page headers and footers.
    remove_repeated_headers_footers: bool = True

    # Remove standalone equation-like lines.
    # Inline equations inside normal sentences are preserved.
    remove_standalone_equations: bool = True

    # Remove extracted PDF coordinate metadata such as /x0, /y0.
    remove_coordinate_artifacts: bool = True

    # Remove isolated page-number lines in page margins.
    remove_page_numbers: bool = True

    # Optional: remove long, numeric-only sequences that may be
    # graph axis ticks. Keep False to protect numeric table content.
    drop_numeric_axis_lines: bool = False

    # Header/footer detection region.
    margin_ratio: float = 0.08

    # Repeated header/footer lines must occur on at least this
    # fraction of the document's pages (minimum two pages).
    repeated_line_fraction: float = 0.30


class ExtractData:

    _COORDINATE_FIELD = re.compile(
        r"(?i)(?<!\w)/(?:x0|y0|x1|y1|width|height|bbox|block_no)"
        r"\s*(?:[:=]\s*)?-?(?:\d+(?:\.\d*)?|\.\d+)?"
    )

    _COORDINATE_TOKEN = re.compile(
        r"(?i)(?<!\w)/(?:x0|y0|x1|y1|width|height|bbox|block_no)(?!\w)"
    )

    _JSON_COORDINATE = re.compile(
        r"""(?i)["']?(?:x0|y0|x1|y1)["']?\s*[:=]\s*
        ["']?-?\d+(?:\.\d+)?["']?""",
        re.VERBOSE,
    )

    _IMAGE_VECTOR_PLACEHOLDER = re.compile(
        r"(?i)^\s*<(?:image|vector)\b.*>\s*$"
    )

    _PAGE_NUMBER = re.compile(
        r"(?i)^\s*(?:page\s*)?\d+(?:\s*(?:of|/)\s*\d+)?\s*$"
    )

    _LATEX_COMMAND = re.compile(
        r"""\\(?:begin|end)\s*\{
            (?:equation|align|math|displaymath)
        \}
        |
        \\(?:frac|sum|int|prod|lim|cdot|times|mathbf|
            mathrm|mathcal|sqrt|partial|nabla|left|right)\b
        """,
        re.VERBOSE,
    )

    _MATH_SYMBOLS = set(
        "=+-*/^_{}[]∑∫√≈≠≤≥∈∉∝→←↔×÷±∂∇"
    )

    _NUMERIC_TOKEN = re.compile(
        r"^[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$"
    )

    def __init__(
        self,
        config: PDFExtractionConfig | None = None,
    ):
        self.config = config or PDFExtractionConfig()

    # ---------------------------------------------------------
    # Main extraction method
    # ---------------------------------------------------------

    def extract(
        self,
        pdf_path: str,
        document_id: str | None = None,
        filename: str | None = None,
    ) -> list[Document]:

        pdf = None

        try:
            path = Path(pdf_path)

            if not path.is_file():
                raise FileNotFoundError(
                    f"PDF file not found: {path}"
                )

            filename = filename or path.name

            pdf = fitz.open(str(path))

            if pdf.needs_pass and not pdf.authenticate(""):
                raise ValueError(
                    "PDF is password-protected. "
                    "Password-based extraction is not configured."
                )

            # Find repeated headers and footers before extraction.
            repeated_lines = {}

            if self.config.remove_repeated_headers_footers:
                repeated_lines = self._find_repeated_margin_lines(pdf)

            extracted_documents = []

            total_skipped_blocks = 0

            for page_index in range(pdf.page_count):

                page = pdf.load_page(page_index)

                page_height = page.rect.height

                top_margin = (
                    page_height * self.config.margin_ratio
                )

                bottom_margin = (
                    page_height * (
                        1 - self.config.margin_ratio
                    )
                )

                page_text_blocks = []
                skipped_blocks = 0

                # Each block contains coordinates, text,
                # block number and block type.
                blocks = page.get_text(
                    "blocks",
                    sort=True,
                )

                for block in blocks:

                    if len(block) < 5:
                        continue

                    x0, y0, x1, y1, raw_text = block[:5]

                    block_type = (
                        block[6] if len(block) > 6 else 0
                    )

                    # Type 0 = text.
                    # Image/vector blocks are not useful as plain text.
                    if block_type != 0:
                        skipped_blocks += 1
                        continue

                    is_margin_block = (
                        y0 <= top_margin
                        or y1 >= bottom_margin
                    )

                    cleaned_text = self._clean_block(
                        raw_text=str(raw_text),
                        page_index=page_index,
                        is_margin_block=is_margin_block,
                        repeated_lines=repeated_lines,
                    )

                    if cleaned_text:
                        page_text_blocks.append(cleaned_text)

                total_skipped_blocks += skipped_blocks

                page_text = "\n\n".join(page_text_blocks)
                page_text = self._normalize_page_text(page_text)

                # Skip genuinely empty or image-only pages.
                if not page_text:
                    logger.warning(
                        "No usable text extracted from page %s: %s",
                        page_index + 1,
                        filename,
                    )
                    continue

                metadata = {
                    "source": str(path),
                    "filename": filename,
                    "document_id": document_id,
                    "page": page_index,
                    "page_number": page_index + 1,
                    "extraction_method": "pymupdf",
                    "text_length": len(page_text),
                }

                extracted_documents.append(
                    Document(
                        page_content=page_text,
                        metadata=metadata,
                    )
                )

            logger.info(
                "PDF extraction completed: filename=%s, "
                "pages=%s, extracted_pages=%s, "
                "skipped_nontext_blocks=%s",
                filename,
                pdf.page_count,
                len(extracted_documents),
                total_skipped_blocks,
            )

            if not extracted_documents:
                logger.warning(
                    "No text was extracted from %s. "
                    "The PDF may be scanned or image-only.",
                    filename,
                )

            return extracted_documents

        except Exception:
            logger.exception(
                "PDF extraction failed: %s",
                pdf_path,
            )
            raise

        finally:
            if pdf is not None:
                pdf.close()

    # ---------------------------------------------------------
    # Detect repeated headers and footers
    # ---------------------------------------------------------

    def _find_repeated_margin_lines(self, pdf) -> dict:

        line_pages = defaultdict(set)

        total_pages = pdf.page_count

        for page_index in range(total_pages):

            page = pdf.load_page(page_index)

            height = page.rect.height

            top = height * self.config.margin_ratio
            bottom = height * (
                1 - self.config.margin_ratio
            )

            for block in page.get_text(
                "blocks",
                sort=True,
            ):

                if len(block) < 7:
                    continue

                x0, y0, x1, y1, raw_text, _, block_type = block

                if block_type != 0:
                    continue

                is_margin = y0 <= top or y1 >= bottom

                if not is_margin:
                    continue

                for raw_line in str(raw_text).splitlines():

                    line = self._normalize_line(raw_line)

                    if len(line) < 6:
                        continue

                    if self._PAGE_NUMBER.fullmatch(line):
                        continue

                    fingerprint = self._fingerprint(line)

                    line_pages[fingerprint].add(page_index)

        minimum_repeats = max(
            2,
            math.ceil(
                total_pages *
                self.config.repeated_line_fraction
            ),
        )

        # Keep the first occurrence and remove later repeats.
        repeated = {
            fingerprint: min(page_indexes)
            for fingerprint, page_indexes in line_pages.items()
            if len(page_indexes) >= minimum_repeats
        }

        return repeated

    @staticmethod
    def _fingerprint(line: str) -> str:

        line = unicodedata.normalize("NFKC", line)

        line = re.sub(r"\d+", "#", line)

        line = re.sub(r"\s+", " ", line)

        return line.strip().casefold()

    # ---------------------------------------------------------
    # Block cleaning
    # ---------------------------------------------------------

    def _clean_block(
        self,
        raw_text: str,
        page_index: int,
        is_margin_block: bool,
        repeated_lines: dict,
    ) -> str:

        cleaned_lines = []

        for raw_line in raw_text.splitlines():

            line = self._normalize_line(raw_line)

            if not line:
                continue

            fingerprint = self._fingerprint(line)

            # Remove repeated header/footer occurrences,
            # but keep the first occurrence in the document.
            if (
                is_margin_block
                and fingerprint in repeated_lines
                and page_index != repeated_lines[fingerprint]
            ):
                continue

            if self._is_noise_line(
                line,
                is_margin_block,
            ):
                continue

            # Avoid consecutive duplicate extraction artefacts.
            if (
                cleaned_lines
                and cleaned_lines[-1].casefold() == line.casefold()
            ):
                continue

            cleaned_lines.append(line)

        text = "\n".join(cleaned_lines)

        # Join words split across lines by PDF hyphenation.
        text = re.sub(
            r"(?<=\w)-\n(?=\w)",
            "",
            text,
        )

        return text.strip()

    # ---------------------------------------------------------
    # Unicode and structural artefact normalization
    # ---------------------------------------------------------

    def _normalize_line(self, text: str) -> str:

        if not text:
            return ""

        # Normalize compatibility characters and ligatures.
        text = unicodedata.normalize("NFKC", text)

        # Remove soft hyphen.
        text = text.replace("\u00ad", "")

        # Remove zero-width and directional formatting characters.
        text = re.sub(
            r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]",
            "",
            text,
        )

        # Remove invalid/control/private-use characters.
        # Greek letters and ordinary mathematical Unicode
        # characters are retained.
        cleaned_chars = []

        for char in text:

            if char in "\t ":
                cleaned_chars.append(" ")
                continue

            category = unicodedata.category(char)

            if char == "\ufffd":
                continue

            if category in {"Cc", "Cf", "Cs", "Co"}:
                continue

            cleaned_chars.append(char)

        text = "".join(cleaned_chars)

        if self.config.remove_coordinate_artifacts:

            # Remove PDF coordinate fragments such as /x0 12.3.
            text = self._COORDINATE_FIELD.sub(" ", text)

            # Remove remaining standalone coordinate labels.
            text = self._COORDINATE_TOKEN.sub(" ", text)

            # Only remove unprefixed x0/y0/x1/y1 key-value
            # pairs when at least two coordinate keys are present.
            coordinate_matches = list(
                self._JSON_COORDINATE.finditer(text)
            )

            if len(coordinate_matches) >= 2:
                text = self._JSON_COORDINATE.sub(" ", text)

        # Remove textual image/vector metadata placeholders.
        text = re.sub(
            r"(?i)<(?:image|vector)\b[^>]*>",
            " ",
            text,
        )

        # Normalize whitespace.
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()

    # ---------------------------------------------------------
    # Noise detection
    # ---------------------------------------------------------

    def _is_noise_line(
        self,
        line: str,
        is_margin_block: bool,
    ) -> bool:

        if not line:
            return True

        # Remove lines that contain no letters or numbers.
        if not any(char.isalnum() for char in line):
            return True

        # Remove isolated page numbers only in page margins.
        if (
            self.config.remove_page_numbers
            and is_margin_block
            and self._PAGE_NUMBER.fullmatch(line)
        ):
            return True

        # Remove standalone image/vector metadata.
        if self._IMAGE_VECTOR_PLACEHOLDER.fullmatch(line):
            return True

        # Remove standalone equations, not inline equations
        # embedded inside normal explanatory sentences.
        if (
            self.config.remove_standalone_equations
            and self._is_equation_line(line)
        ):
            return True

        # Optional filter for graph-axis tick sequences.
        # Disabled by default because numeric-only table rows
        # may contain important information.
        if (
            self.config.drop_numeric_axis_lines
            and self._is_numeric_axis_line(line)
        ):
            return True

        return False

    def _is_equation_line(self, line: str) -> bool:

        words = re.findall(
            r"[A-Za-z]{2,}",
            line,
        )

        # LaTeX display equation fragments.
        if (
            self._LATEX_COMMAND.search(line)
            and len(words) <= 6
        ):
            return True

        # Standalone symbolic expressions.
        math_count = sum(
            char in self._MATH_SYMBOLS
            for char in line
        )

        return (
            len(words) <= 2
            and math_count >= 3
        )

    def _is_numeric_axis_line(self, line: str) -> bool:

        tokens = line.replace(",", " ").split()

        return (
            len(tokens) >= 5
            and all(
                self._NUMERIC_TOKEN.fullmatch(token)
                for token in tokens
            )
        )

    # ---------------------------------------------------------
    # Final page normalization
    # ---------------------------------------------------------

    @staticmethod
    def _normalize_page_text(text: str) -> str:

        if not text:
            return ""

        # Remove spaces before newlines.
        text = re.sub(r"[ \t]+\n", "\n", text)

        # Normalize excessive blank lines.
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove excessive spaces.
        text = re.sub(r"[ \t]{2,}", " ", text)

        return text.strip()
