"""Supporting-document rules on apply follow the leave type's settings:
Attachment Required -> always; Medical Certificate Required -> for leave of
medical_certificate_after_days or more days; neither -> optional."""
from apps.hrms.tests_leave_gender import PINK, GenderLeaveBase


class LeaveDocumentRuleTests(GenderLeaveBase):
    def setUp(self):
        super().setUp()
        self.balance(self.woman)

    def test_attachment_required_blocks_without_document(self):
        self.pink(applicable_gender='all', attachment_required=True)
        resp = self.apply('gl.woman@test.com')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('attachment is required', resp.data['message'])

    def test_medical_certificate_only_from_the_threshold(self):
        policy = self.pink(applicable_gender='all', medical_certificate_required=True, medical_certificate_after_days=1)
        resp = self.apply('gl.woman@test.com')                      # 1 day >= 1 -> certificate needed
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('medical certificate', resp.data['message'])
        policy.medical_certificate_after_days = 3
        policy.save()                                               # 1 day < 3 -> optional
        self.assertEqual(self.apply('gl.woman@test.com').status_code, 201)

    def test_no_document_rule_means_optional(self):
        self.pink(applicable_gender='all')
        self.assertEqual(self.apply('gl.woman@test.com').status_code, 201)
