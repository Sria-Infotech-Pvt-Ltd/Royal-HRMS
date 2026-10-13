from django.urls import path

from apps.platform_core import (
    views, views_attachments, views_events_notifications, views_import_export, views_list_views,
    views_meta, views_privacy, views_rules, views_scheduler, views_workflow,
)

urlpatterns = [
    path('entities/', views_meta.EntityDefinitionListCreateView.as_view(), name='platform-entity-list'),
    path('entities/<int:pk>/', views_meta.EntityDefinitionDetailView.as_view(), name='platform-entity-detail'),
    path('entities/<int:pk>/publish/', views_meta.EntityDefinitionPublishView.as_view(), name='platform-entity-publish'),
    path('fields/', views_meta.FieldDefinitionListCreateView.as_view(), name='platform-field-list'),
    path('fields/<int:pk>/', views_meta.FieldDefinitionDetailView.as_view(), name='platform-field-detail'),
    path('form-layouts/', views_meta.FormLayoutListCreateView.as_view(), name='platform-form-layout-list'),
    path('form-layouts/<int:pk>/', views_meta.FormLayoutDetailView.as_view(), name='platform-form-layout-detail'),
    path('entities/<str:entity_code>/resolve-layout/', views_meta.ResolveLayoutView.as_view(), name='platform-resolve-layout'),

    path('custom/<str:entity_code>/records/', views_meta.CustomRecordListCreateView.as_view(), name='platform-custom-record-list'),
    path('custom/<str:entity_code>/records/<uuid:pk>/', views_meta.CustomRecordDetailView.as_view(), name='platform-custom-record-detail'),

    path('list-views/', views_list_views.ListViewDefinitionListCreateView.as_view(), name='platform-list-view-list'),
    path('list-views/<int:pk>/', views_list_views.ListViewDefinitionDetailView.as_view(), name='platform-list-view-detail'),
    path('entities/<str:entity_code>/default-list-view/', views_list_views.MyDefaultListViewView.as_view(), name='platform-default-list-view'),

    path('attachments/<str:entity_code>/<str:record_id>/<str:field_code>/', views_attachments.AttachmentUploadView.as_view(), name='platform-attachment-upload'),
    path('attachments/<str:entity_code>/<str:record_id>/<str:field_code>/list/', views_attachments.AttachmentListView.as_view(), name='platform-attachment-list'),
    path('attachments/<int:pk>/', views_attachments.AttachmentDownloadView.as_view(), name='platform-attachment-detail'),

    path('custom/<str:entity_code>/import-template/', views_import_export.ImportTemplateDownloadView.as_view(), name='platform-import-template'),
    path('custom/<str:entity_code>/import-jobs/', views_import_export.ImportJobListCreateView.as_view(), name='platform-import-job-list'),
    path('import-jobs/<uuid:job_id>/validate/', views_import_export.ImportJobValidateView.as_view(), name='platform-import-job-validate'),
    path('import-jobs/<uuid:job_id>/commit/', views_import_export.ImportJobCommitView.as_view(), name='platform-import-job-commit'),
    path('import-jobs/<uuid:job_id>/rollback/', views_import_export.ImportJobRollbackView.as_view(), name='platform-import-job-rollback'),
    path('import-jobs/<uuid:job_id>/status/', views_import_export.ImportJobStatusView.as_view(), name='platform-import-job-status'),
    path('custom/<str:entity_code>/export/', views_import_export.ExportView.as_view(), name='platform-export'),

    path('privacy/my-requests/', views_privacy.MyDataSubjectRequestListCreateView.as_view(), name='platform-privacy-my-requests'),
    path('privacy/queue/', views_privacy.DataSubjectRequestQueueView.as_view(), name='platform-privacy-queue'),
    path('privacy/requests/<uuid:pk>/fulfil/', views_privacy.DataSubjectRequestFulfilView.as_view(), name='platform-privacy-fulfil'),

    path('countries/', views.CountryListCreateView.as_view(), name='platform-country-list'),
    path('countries/<int:pk>/', views.CountryDetailView.as_view(), name='platform-country-detail'),
    path('currencies/', views.CurrencyListCreateView.as_view(), name='platform-currency-list'),
    path('currencies/<int:pk>/', views.CurrencyDetailView.as_view(), name='platform-currency-detail'),
    path('timezones/', views.TimezoneListView.as_view(), name='platform-timezone-list'),
    path('exchange-rates/', views.ExchangeRateListCreateView.as_view(), name='platform-exchange-rate-list'),
    path('exchange-rates/<int:pk>/', views.ExchangeRateDetailView.as_view(), name='platform-exchange-rate-detail'),

    path('lookup-types/', views.LookupTypeListCreateView.as_view(), name='platform-lookup-type-list'),
    path('lookup-types/<int:pk>/', views.LookupTypeDetailView.as_view(), name='platform-lookup-type-detail'),
    path('lookup-values/', views.LookupValueListCreateView.as_view(), name='platform-lookup-value-list'),
    path('lookup-values/<int:pk>/', views.LookupValueDetailView.as_view(), name='platform-lookup-value-detail'),
    path('translations/', views.TranslationListCreateView.as_view(), name='platform-translation-list'),

    path('legal-entities/', views.LegalEntityListCreateView.as_view(), name='platform-legal-entity-list'),
    path('legal-entities/<uuid:pk>/', views.LegalEntityDetailView.as_view(), name='platform-legal-entity-detail'),
    path('entity-identifiers/', views.EntityIdentifierListCreateView.as_view(), name='platform-entity-identifier-list'),
    path('entity-bank-accounts/', views.EntityBankAccountListCreateView.as_view(), name='platform-entity-bank-account-list'),
    path('entity-signatories/', views.AuthorisedSignatoryListCreateView.as_view(), name='platform-entity-signatory-list'),

    path('number-series/', views.NumberSeriesListCreateView.as_view(), name='platform-number-series-list'),
    path('number-series/<int:pk>/', views.NumberSeriesDetailView.as_view(), name='platform-number-series-detail'),
    path('number-series/<str:code>/preview/', views.NumberSeriesPreviewView.as_view(), name='platform-number-series-preview'),

    path('feature-flags/', views.FeatureFlagListCreateView.as_view(), name='platform-feature-flag-list'),
    path('feature-flags/<int:pk>/', views.FeatureFlagDetailView.as_view(), name='platform-feature-flag-detail'),
    path('feature-flag-overrides/', views.FeatureFlagOverrideListCreateView.as_view(), name='platform-feature-flag-override-list'),
    path('module-toggles/', views.ModuleToggleListCreateView.as_view(), name='platform-module-toggle-list'),
    path('module-toggles/<int:pk>/', views.ModuleToggleDetailView.as_view(), name='platform-module-toggle-detail'),

    path('history/', views.ChangeHistoryListView.as_view(), name='platform-change-history-list'),

    # ─── Phase 3A: rules ─────────────────────────────────────────────────
    path('rules/', views_rules.RuleDefinitionListCreateView.as_view(), name='platform-rule-list'),
    path('rules/<int:pk>/', views_rules.RuleDefinitionDetailView.as_view(), name='platform-rule-detail'),
    path('rules/<int:pk>/validate/', views_rules.RuleValidateView.as_view(), name='platform-rule-validate'),
    path('rules/<int:pk>/test-run/', views_rules.RuleTestRunView.as_view(), name='platform-rule-test-run'),
    path('rules/<int:pk>/publish/', views_rules.RulePublishView.as_view(), name='platform-rule-publish'),
    path('rules/<int:pk>/retire/', views_rules.RuleRetireView.as_view(), name='platform-rule-retire'),
    path('rules/<int:pk>/where-used/', views_rules.RuleWhereUsedView.as_view(), name='platform-rule-where-used'),
    path('rules/<int:pk>/versions/', views_rules.RuleVersionListView.as_view(), name='platform-rule-versions'),
    path('rule-test-cases/', views_rules.RuleTestCaseListCreateView.as_view(), name='platform-rule-test-case-list'),
    path('rule-test-cases/<int:pk>/', views_rules.RuleTestCaseDetailView.as_view(), name='platform-rule-test-case-detail'),
    path('rule-tables/', views_rules.RuleTableListCreateView.as_view(), name='platform-rule-table-list'),
    path('rule-tables/<int:pk>/', views_rules.RuleTableDetailView.as_view(), name='platform-rule-table-detail'),
    path('rule-table-versions/', views_rules.RuleTableVersionListCreateView.as_view(), name='platform-rule-table-version-list'),

    # ─── Phase 3A: policies ──────────────────────────────────────────────
    path('policy-types/', views_rules.PolicyTypeListView.as_view(), name='platform-policy-type-list'),
    path('policies/', views_rules.PolicyListCreateView.as_view(), name='platform-policy-list'),
    path('policies/<int:pk>/', views_rules.PolicyDetailView.as_view(), name='platform-policy-detail'),
    path('policies/<int:pk>/affected-employees/', views_rules.PolicyAffectedEmployeesView.as_view(), name='platform-policy-affected-employees'),
    path('policy-assignments/', views_rules.PolicyAssignmentListCreateView.as_view(), name='platform-policy-assignment-list'),
    path('policy-assignments/<int:pk>/', views_rules.PolicyAssignmentDetailView.as_view(), name='platform-policy-assignment-detail'),
    path('policies/effective/', views_rules.PolicyExplainerView.as_view(), name='platform-policy-explainer'),

    # ─── Phase 3B: workflow definitions ──────────────────────────────────
    path('workflow-definitions/', views_workflow.WorkflowDefinitionListCreateView.as_view(), name='platform-workflow-definition-list'),
    path('workflow-definitions/<int:pk>/', views_workflow.WorkflowDefinitionDetailView.as_view(), name='platform-workflow-definition-detail'),
    path('workflow-definitions/<int:pk>/validate/', views_workflow.WorkflowDefinitionValidateView.as_view(), name='platform-workflow-definition-validate'),
    path('workflow-definitions/<int:pk>/publish/', views_workflow.WorkflowDefinitionPublishView.as_view(), name='platform-workflow-definition-publish'),
    path('workflow-definitions/<int:pk>/impact-preview/', views_workflow.WorkflowDefinitionImpactPreviewView.as_view(), name='platform-workflow-definition-impact-preview'),
    path('workflow-steps/', views_workflow.WorkflowStepListCreateView.as_view(), name='platform-workflow-step-list'),
    path('workflow-steps/<int:pk>/', views_workflow.WorkflowStepDetailView.as_view(), name='platform-workflow-step-detail'),
    path('workflow-approver-overrides/', views_workflow.WorkflowApproverOverrideListCreateView.as_view(), name='platform-workflow-approver-override-list'),
    path('workflow-approver-overrides/<int:pk>/', views_workflow.WorkflowApproverOverrideDetailView.as_view(), name='platform-workflow-approver-override-detail'),
    path('delegations/', views_workflow.DelegationListCreateView.as_view(), name='platform-delegation-list'),

    # ─── Phase 3B: inbox and runtime actions ─────────────────────────────
    path('workflow/tasks/', views_workflow.MyApprovalsInboxView.as_view(), name='platform-workflow-tasks'),
    path('workflow/tasks/counts/', views_workflow.MyApprovalsCountsView.as_view(), name='platform-workflow-task-counts'),
    path('workflow/tasks/<uuid:task_id>/action/', views_workflow.WorkflowTaskActionView.as_view(), name='platform-workflow-task-action'),
    path('workflow/tasks/<uuid:task_id>/reassign/', views_workflow.WorkflowTaskReassignView.as_view(), name='platform-workflow-task-reassign'),
    path('workflow/tasks/bulk-action/', views_workflow.WorkflowTaskBulkActionView.as_view(), name='platform-workflow-task-bulk-action'),
    path('workflow/instances/<uuid:instance_id>/withdraw/', views_workflow.WorkflowInstanceWithdrawView.as_view(), name='platform-workflow-instance-withdraw'),
    path('workflow/instances/<str:content_type>/<str:object_id>/', views_workflow.WorkflowInstanceDetailView.as_view(), name='platform-workflow-instance-detail'),

    # ─── Phase 3B: events and notifications ──────────────────────────────
    path('event-types/', views_events_notifications.EventTypeListView.as_view(), name='platform-event-type-list'),
    path('message-templates/', views_events_notifications.MessageTemplateListCreateView.as_view(), name='platform-message-template-list'),
    path('message-templates/<int:pk>/', views_events_notifications.MessageTemplateDetailView.as_view(), name='platform-message-template-detail'),
    path('message-templates/<int:pk>/preview/', views_events_notifications.MessageTemplatePreviewView.as_view(), name='platform-message-template-preview'),
    path('message-templates/<int:pk>/test-send/', views_events_notifications.MessageTemplateTestSendView.as_view(), name='platform-message-template-test-send'),
    path('notification-rules/', views_events_notifications.NotificationRuleListCreateView.as_view(), name='platform-notification-rule-list'),
    path('notification-rules/<int:pk>/', views_events_notifications.NotificationRuleDetailView.as_view(), name='platform-notification-rule-detail'),
    path('notification-deliveries/', views_events_notifications.NotificationDeliveryListView.as_view(), name='platform-notification-delivery-list'),
    path('my-notification-preferences/', views_events_notifications.MyNotificationPreferencesView.as_view(), name='platform-my-notification-preferences'),

    # ─── Phase 3B: scheduler ──────────────────────────────────────────────
    path('job-types/', views_scheduler.JobTypeListView.as_view(), name='platform-job-type-list'),
    path('scheduled-jobs/', views_scheduler.ScheduledJobListCreateView.as_view(), name='platform-scheduled-job-list'),
    path('scheduled-jobs/<int:pk>/', views_scheduler.ScheduledJobDetailView.as_view(), name='platform-scheduled-job-detail'),
    path('scheduled-jobs/<int:pk>/run-now/', views_scheduler.ScheduledJobRunNowView.as_view(), name='platform-scheduled-job-run-now'),
    path('scheduled-jobs/<int:pk>/runs/', views_scheduler.JobRunListView.as_view(), name='platform-scheduled-job-runs'),
]
