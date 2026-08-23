import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from .services.refund_service import (
    PermanentProviderError,
    TransientProviderError,
    finalize_refund,
    mark_refund_failed,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_COUNTDOWN = 10


@shared_task(bind=True, max_retries=MAX_RETRIES)
def process_refund_task(self, refund_id):
    try:
        finalize_refund(refund_id=refund_id)
    except TransientProviderError as exc:
        logger.warning(
            "Transient refund failure for refund %s: %s", refund_id, exc
        )

        try:
            raise self.retry(
                exc=exc,
                countdown=BASE_COUNTDOWN * (2**self.request.retries),
            )
        except MaxRetriesExceededError:
            mark_refund_failed(
                refund_id=refund_id,
                detail="Provider unreachable after multiple attempts.",
            )

    except PermanentProviderError as exc:
        logger.error(
            "Permanent refund failure for refund %s: %s", refund_id, exc
        )
