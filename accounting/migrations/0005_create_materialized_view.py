# SQL migration to create the MaterializedView for CategoryMonthlyStat

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0004_add_insight_fact_model'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Create Materialized View for monthly category statistics
            -- This view aggregates validated journal entries by category and month
            CREATE MATERIALIZED VIEW accounting_categorymonthlystat AS
            SELECT
                ROW_NUMBER() OVER (ORDER BY account_id, DATE_TRUNC('month', je.date)) AS id,
                account_id AS category_id,
                DATE_TRUNC('month', je.date)::date AS month,
                SUM(CASE 
                    WHEN account.account_type IN ('EXPENSE', 'ASSET') THEN tl.amount
                    WHEN account.account_type IN ('LIABILITY', 'REVENUE', 'EQUITY') THEN -tl.amount
                    ELSE tl.amount
                END) AS total_amount,
                COUNT(*) AS transaction_count,
                CASE 
                    WHEN COUNT(*) = 0 THEN 0
                    ELSE SUM(CASE 
                        WHEN account.account_type IN ('EXPENSE', 'ASSET') THEN tl.amount
                        WHEN account.account_type IN ('LIABILITY', 'REVENUE', 'EQUITY') THEN -tl.amount
                        ELSE tl.amount
                    END) / COUNT(*)
                END AS avg_ticket
            FROM
                accounting_transactionline tl
            JOIN
                accounting_account account ON tl.account_id = account.id
            JOIN
                accounting_journalentry je ON tl.journal_entry_id = je.id
            WHERE
                je.is_reconciled = true
            GROUP BY
                account_id,
                DATE_TRUNC('month', je.date)
            ORDER BY
                account_id,
                DATE_TRUNC('month', je.date) DESC;
            
            -- Create index on the materialized view for fast lookups
            CREATE UNIQUE INDEX accounting_categorymonthlystat_account_month 
                ON accounting_categorymonthlystat (category_id, month);
            CREATE INDEX accounting_categorymonthlystat_month 
                ON accounting_categorymonthlystat (month);
            """,
            reverse_sql="""
            -- Drop the materialized view and its indexes
            DROP MATERIALIZED VIEW IF EXISTS accounting_categorymonthlystat CASCADE;
            """
        ),
    ]

