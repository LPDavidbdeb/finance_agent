from django.contrib import admin

from .models import ConsistencyReportFinding, ConsistencyReportRun


@admin.register(ConsistencyReportRun)
class ConsistencyReportRunAdmin(admin.ModelAdmin):
    list_display = ('id', 'family', 'trigger_source', 'status', 'started_at', 'finished_at')
    list_filter = ('trigger_source', 'status')
    search_fields = ('family__name', 'error_message')


@admin.register(ConsistencyReportFinding)
class ConsistencyReportFindingAdmin(admin.ModelAdmin):
    list_display = ('id', 'run', 'severity', 'category', 'title', 'created_at')
    list_filter = ('severity', 'category')
    search_fields = ('title', 'message')


