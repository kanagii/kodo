from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("profile", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="avatar",
            field=models.ImageField(blank=True, null=True, upload_to="avatars/"),
        ),
        migrations.AddField(
            model_name="profile",
            name="theme",
            field=models.CharField(
                choices=[("dark", "Dark"), ("light", "Light")],
                default="dark",
                max_length=10,
            ),
        ),
    ]
