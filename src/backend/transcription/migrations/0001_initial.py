"""Initial schema for meeting transcription."""

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0020_personalaccesstoken"),
    ]

    operations = [
        migrations.CreateModel(
            name="MeetingUtterance",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "speaker_identity",
                    models.CharField(db_index=True, max_length=255),
                ),
                ("speaker_name", models.CharField(blank=True, max_length=255)),
                ("text", models.TextField()),
                ("language", models.CharField(blank=True, max_length=10)),
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("is_final", models.BooleanField(default=True)),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="utterances",
                        to="core.room",
                    ),
                ),
            ],
            options={
                "verbose_name": "Meeting utterance",
                "verbose_name_plural": "Meeting utterances",
                "db_table": "meet_meeting_utterance",
                "ordering": ("room", "started_at"),
            },
        ),
        migrations.AddIndex(
            model_name="meetingutterance",
            index=models.Index(
                fields=["room", "started_at"],
                name="meet_utt_room_time_idx",
            ),
        ),
    ]
