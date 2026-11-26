"""The company's logo on the payslip and Form 16 PDFs: drawn when there is a readable one, and a PDF is still produced when there is not."""
import datetime
import io
from types import SimpleNamespace

from django.test import SimpleTestCase
from PIL import Image
from reportlab.pdfgen import canvas as pdfcanvas

from apps.payroll import services_form16_pdf, services_payslip_pdf
from apps.payroll.services_pdf_branding import BADGE_HEIGHT, TITLE_MIN_SIZE, TITLE_SIZE, draw_company_logo, draw_company_title


def _png(width=120, height=60, colour=(200, 40, 40, 255)) -> bytes:
    buffer = io.BytesIO()
    Image.new('RGBA', (width, height), colour).save(buffer, format='PNG')
    return buffer.getvalue()


def _company(data: bytes | None, **extra):
    logo = SimpleNamespace(open=lambda mode='rb': io.BytesIO(data), __bool__=lambda self: True) if data is not None else None
    # SimpleNamespace has no truthiness hook: a tiny class gives the same shape as a Django FieldFile (truthy when a file is set).
    class _Logo:
        def open(self, mode='rb'):
            return io.BytesIO(data)

        def __bool__(self):
            return True

    return SimpleNamespace(company_name='Sria Infotech Pvt Ltd', city='Hyderabad', state='Telangana', pan='', tan='', logo=_Logo() if logo else None, **extra)


def _canvas():
    buffer = io.BytesIO()
    return pdfcanvas.Canvas(buffer, pagesize=services_payslip_pdf.A4), buffer


class DrawCompanyLogoTests(SimpleTestCase):
    def test_draws_a_readable_logo_and_says_how_far_to_move_the_name(self):
        c, buffer = _canvas()
        used = draw_company_logo(c, _company(_png()), 40, 800)
        c.showPage(); c.save()
        self.assertGreater(used, 0)
        # A 2:1 logo is fitted into the badge, so the badge is as wide as the logo is tall x 2 (plus its margin), not the full maximum.
        self.assertLess(used, 40 * 3.0 + BADGE_HEIGHT * 3)
        self.assertGreater(len(buffer.getvalue()), 1000)

    def test_no_logo_draws_nothing_and_uses_no_space(self):
        c, _ = _canvas()
        self.assertEqual(draw_company_logo(c, SimpleNamespace(logo=None), 40, 800), 0.0)
        self.assertEqual(draw_company_logo(c, None, 40, 800), 0.0)

    def test_an_unreadable_or_unsupported_file_is_left_out_without_failing(self):
        c, _ = _canvas()
        for data in (b'not an image at all', b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', b''):
            self.assertEqual(draw_company_logo(c, _company(data), 40, 800), 0.0, data[:20])

    def test_a_file_that_cannot_be_opened_is_left_out_without_failing(self):
        class _Missing:
            def open(self, mode='rb'):
                raise FileNotFoundError('gone from storage')

            def __bool__(self):
                return True

        c, _ = _canvas()
        self.assertEqual(draw_company_logo(c, SimpleNamespace(logo=_Missing()), 40, 800), 0.0)

    def test_a_very_tall_and_a_very_wide_logo_both_fit_the_badge(self):
        for width, height in ((30, 400), (900, 30)):
            c, _ = _canvas()
            used = draw_company_logo(c, _company(_png(width, height)), 40, 800)
            self.assertGreater(used, 0)
            self.assertLessEqual(used, 34 * 2.8346 + 4 * 2.8346 + 0.5, (width, height))   # the badge never grows past its maximum width


class StatementHeadersTests(SimpleTestCase):
    def _header_size(self, module, company, **ctx_extra):
        c, buffer = _canvas()
        ctx = SimpleNamespace(c=c, company=company, cycle=SimpleNamespace(cycle_start=datetime.date(2026, 10, 1)), fy_label='2025-26', y=module.PAGE_H, **ctx_extra)
        module._draw_header(ctx)
        c.showPage(); c.save()
        return len(buffer.getvalue())

    def test_both_statements_produce_a_header_with_a_logo_and_without(self):
        for module in (services_payslip_pdf, services_form16_pdf):
            with_logo = self._header_size(module, _company(_png()))
            without_logo = self._header_size(module, _company(None))
            self.assertGreater(with_logo, without_logo, module.__name__)   # the picture is really in the file

    def test_a_broken_logo_does_not_break_either_statement(self):
        for module in (services_payslip_pdf, services_form16_pdf):
            self.assertGreater(self._header_size(module, _company(b'garbage')), 500, module.__name__)


class CompanyTitleTests(SimpleTestCase):
    def test_a_short_name_keeps_the_full_size(self):
        c, _ = _canvas()
        self.assertEqual(draw_company_title(c, 'Sria Infotech', 40, 780, 400), TITLE_SIZE)

    def test_a_long_name_shrinks_to_fit_and_never_passes_the_limit(self):
        c, _ = _canvas()
        size = draw_company_title(c, 'Sria Infotech Information Technology Services Private Limited', 40, 780, 300)
        self.assertLess(size, TITLE_SIZE)
        self.assertGreaterEqual(size, TITLE_MIN_SIZE)

    def test_a_name_too_long_even_at_the_smallest_size_is_cut_with_an_ellipsis(self):
        calls = []
        c, _ = _canvas()
        original = c.drawString
        c.drawString = lambda x, y, text, *a, **k: (calls.append(text), original(x, y, text, *a, **k))[1]
        draw_company_title(c, 'X' * 200, 40, 780, 200)
        self.assertTrue(calls[-1].endswith('...'))
        self.assertLessEqual(c.stringWidth(calls[-1], 'Helvetica-Bold', TITLE_MIN_SIZE), 200 - 40)
