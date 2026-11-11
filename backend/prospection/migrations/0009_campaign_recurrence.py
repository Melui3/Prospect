from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("prospection", "0008_email_draft")]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="repeat_days",
            field=models.PositiveSmallIntegerField(
                choices=[(0, "Désactivée"), (7, "Chaque semaine"), (14, "Toutes les deux semaines"), (30, "Chaque mois")],
                default=0,
            ),
        ),
        migrations.AddField(
            model_name="campaign",
            name="next_search_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
