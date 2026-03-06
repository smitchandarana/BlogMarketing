import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from database import get_scheduled_posts, update_post_status
from linkedin_publisher import publish_post

logger = logging.getLogger(__name__)


def run_scheduled_posts():
    """Fetch all scheduled posts and publish them to LinkedIn."""
    posts = get_scheduled_posts()
    if not posts:
        logger.info('No scheduled posts to publish.')
        return

    for post in posts:
        try:
            full_text = f"{post['linkedin_text']}\n\n{post['hashtags']}"
            publish_post(full_text)
            update_post_status(post['id'], 'posted')
            logger.info('Published post ID %d — %s', post['id'], post['topic'])
        except Exception as exc:
            logger.error('Failed to publish post ID %d: %s', post['id'], exc)


def start_scheduler(hour: int = 9, minute: int = 0):
    """Start a blocking scheduler that runs daily at hour:minute."""
    scheduler = BlockingScheduler(timezone='Asia/Kolkata')
    scheduler.add_job(
        run_scheduled_posts,
        CronTrigger(hour=hour, minute=minute),
        id='publish_scheduled_posts',
        name='Publish scheduled LinkedIn posts',
    )
    logger.info('Scheduler started — runs daily at %02d:%02d IST', hour, minute)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info('Scheduler stopped.')
