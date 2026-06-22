from shared.celery_app import celery_app


def queue_admin_notification(report_id: int) -> None:
    celery_app.send_task("admin_bot.worker.notify_admins", args=[report_id])
