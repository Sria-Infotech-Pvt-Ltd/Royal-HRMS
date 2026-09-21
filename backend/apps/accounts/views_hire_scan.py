"""
"Scan & fill" for the Hire wizard — POST /hire-actions/<id>/scan-document/.

Real text extraction only, never fabricated field guesses:
- PDF: pypdf reads whatever text is actually embedded in the file (works
  for offer letters, ID cards or resumes exported/printed to PDF — the
  overwhelming majority of real documents this gets used on).
- JPEG/PNG: this environment has no OCR engine installed (no Tesseract
  binary, confirmed absent from PATH) — rather than silently returning
  nothing or faking a result, this responds with a clear, honest message
  that image OCR isn't set up yet and asks for a text-based PDF instead.

Field detection is plain regex over the extracted text — PAN/Aadhaar/
email/phone have fixed, unambiguous formats; name/DOB/PIN code are matched
next to their own label (e.g. "Name:", "DOB:") to avoid false positives.
Every suggestion returned is a literal substring actually found in the
document — nothing here invents or infers a value that isn't on the page.
"""
import logging
import re

from pypdf import PdfReader
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

from core.file_validation import validate_file_content
from core.permissions import has_perm as _has_perm
from core.responses import error, success
from apps.accounts.models import HireAction

logger = logging.getLogger(__name__)

_DENIED = 'You do not have permission to perform this action.'
_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB, same limit as every other upload in this app
_ALLOWED_CONTENT_TYPES = {'application/pdf', 'image/jpeg', 'image/png'}

_EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
_PHONE_RE = re.compile(r'(?:\+?91[-\s]?)?[6-9]\d{9}\b')
_PAN_RE = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
_AADHAAR_RE = re.compile(r'\b(\d{4}\s?\d{4}\s?\d{4})\b')
_DATE_RE = re.compile(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b')

# Labeled fields — only matched right after their own label, since a bare
# name or 6-digit number has no fixed format to detect safely on its own.
_LABELED_PATTERNS = {
    'name':      re.compile(r'(?:full\s*name|name)\s*[:\-]\s*([A-Za-z][A-Za-z .]{2,60})', re.IGNORECASE),
    'date_of_birth': re.compile(r'(?:date\s*of\s*birth|dob)\s*[:\-]\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})', re.IGNORECASE),
    'pin_code':  re.compile(r'(?:pin\s*code|pincode|pin)\s*[:\-]?\s*(\d{6})\b', re.IGNORECASE),
}


def _normalize_date(raw: str) -> str | None:
    m = _DATE_RE.match(raw)
    if not m:
        return None
    day, month, year = m.groups()
    if len(year) == 2:
        year = f'20{year}' if int(year) < 50 else f'19{year}'
    try:
        day_i, month_i, year_i = int(day), int(month), int(year)
        if not (1 <= day_i <= 31 and 1 <= month_i <= 12):
            return None
        return f'{year_i:04d}-{month_i:02d}-{day_i:02d}'
    except ValueError:
        return None


def _extract_fields(text: str) -> dict:
    suggestions = {}

    email_match = _EMAIL_RE.search(text)
    if email_match:
        suggestions['email'] = email_match.group(0)

    phone_match = _PHONE_RE.search(text)
    if phone_match:
        suggestions['phone'] = re.sub(r'[-\s]', '', phone_match.group(0))[-10:]

    pan_match = _PAN_RE.search(text)
    if pan_match:
        suggestions['pan_number'] = pan_match.group(0)

    aadhaar_match = _AADHAAR_RE.search(text)
    if aadhaar_match:
        digits = re.sub(r'\s', '', aadhaar_match.group(1))
        if len(digits) == 12:
            suggestions['aadhaar_number'] = digits

    name_match = _LABELED_PATTERNS['name'].search(text)
    if name_match:
        suggestions['full_name'] = name_match.group(1).strip()

    dob_match = _LABELED_PATTERNS['date_of_birth'].search(text)
    if dob_match:
        normalized = _normalize_date(dob_match.group(1))
        if normalized:
            suggestions['date_of_birth'] = normalized

    pin_match = _LABELED_PATTERNS['pin_code'].search(text)
    if pin_match:
        suggestions['current_pin_code'] = pin_match.group(1)

    return suggestions


class HireActionScanDocumentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'employees.create'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)

        action = HireAction.objects.filter(pk=pk, status=HireAction.STATUS_DRAFT).first()
        if not action:
            return error('Hire action not found or already completed.', http_status=status.HTTP_404_NOT_FOUND)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('Attach a file to scan.')
        if uploaded.size > _MAX_FILE_SIZE:
            return error('File must be under 5 MB.')
        if uploaded.content_type not in _ALLOWED_CONTENT_TYPES:
            return error('Only PDF, JPG or PNG files are supported.')
        content_error = validate_file_content(uploaded, uploaded.content_type)
        if content_error:
            return error(content_error)

        if uploaded.content_type in ('image/jpeg', 'image/png'):
            return success('Scan not available for images.', data={
                'suggestions': {},
                'warnings': [
                    'This environment has no OCR engine set up for image files yet — '
                    'upload a text-based PDF instead (e.g. export the offer letter, ID or resume as a PDF).',
                ],
            })

        try:
            reader = PdfReader(uploaded)
            text = '\n'.join((page.extract_text() or '') for page in reader.pages)
        except Exception as exc:
            logger.warning('Hire wizard scan-and-fill failed to read PDF for hire_action=%s: %s', pk, exc)
            return error('Could not read this PDF — it may be corrupted or password-protected.')

        if not text.strip():
            return success('No extractable text found.', data={
                'suggestions': {},
                'warnings': [
                    'No text could be extracted from this PDF — it may be a scanned image with no embedded text layer.',
                ],
            })

        suggestions = _extract_fields(text)
        warnings = [] if suggestions else ['No recognizable fields (name, email, phone, PAN, Aadhaar, DOB, PIN code) were found in this document.']
        return success('Document scanned.', data={'suggestions': suggestions, 'warnings': warnings})
