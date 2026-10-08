from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TestTimingCapture",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("test_result_id", models.PositiveBigIntegerField(db_index=True, unique=True)),
                ("event_key", models.CharField(db_index=True, max_length=96)),
                ("tested_quantity", models.DecimalField(decimal_places=6, max_digits=20)),
                ("captured_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["test_result_id"]},
        ),
    ]
