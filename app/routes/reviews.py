from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from ..deps import get_db, require_admin, require_user
from ..services.review_crawler import crawl_reviews
from ..db_models import ProductReviewDB, ReviewPageDB

router = APIRouter()

@router.post("/crawl")
def trigger_crawl(background_tasks: BackgroundTasks, db: Session = Depends(get_db), current=Depends(require_admin)):
    """
    Trigger a background crawl for product reviews.
    """
    background_tasks.add_task(crawl_reviews, db, region="IN")
    return {"ok": True, "message": "Crawl started in background"}

@router.get("/stats")
def review_stats(db: Session = Depends(get_db), current=Depends(require_user)):
    """
    Get statistics on crawled reviews.
    """
    review_count = db.query(ProductReviewDB).count()
    page_count = db.query(ReviewPageDB).count()
    return {"ok": True, "reviews": review_count, "pages_crawled": page_count}
