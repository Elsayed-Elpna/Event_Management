import logging

from celery import shared_task

from .services.expiry_service import (
    expire_reservations,
    expire_subscriptions,
    fail_expired_orders,
    finish_events,
)

logger = logging.getLogger(__name__)


@shared_task(name="jobs.tasks.expire_subscriptions")
def expire_subscriptions_task():
    count = expire_subscriptions()
    logger.info("Expired %s subscription(s).", count)
    return count


@shared_task(name="jobs.tasks.finish_events")
def finish_events_task():
    count = finish_events()
    logger.info("Finished %s event(s).", count)
    return count


@shared_task(name="jobs.tasks.expire_reservations")
def expire_reservations_task():
    count = expire_reservations()
    logger.info("Expired %s reservation(s).", count)
    return count


@shared_task(name="jobs.tasks.fail_expired_orders")
def fail_expired_orders_task():
    count = fail_expired_orders()
    logger.info("Failed %s order(s).", count)
    return count
