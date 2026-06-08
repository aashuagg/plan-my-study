from backend.database import SessionLocal
from backend.models import Newsletter, CurriculumItem, LearningHistory

def delete_last_diary_entry():
    db = SessionLocal()
    try:
        # Find the special diary newsletter
        diary_newsletter = db.query(Newsletter).filter(
            Newsletter.month == "Diary",
            Newsletter.year == 0
        ).first()
        
        if not diary_newsletter:
            print("No manual diary newsletter found.")
            return
            
        # Find the latest curriculum item under this newsletter
        last_item = db.query(CurriculumItem).filter(
            CurriculumItem.newsletter_id == diary_newsletter.id
        ).order_by(CurriculumItem.id.desc()).first()
        
        if not last_item:
            print("No diary entries found in database.")
            return
            
        print(f"Found latest diary entry to delete:")
        print(f"  ID: {last_item.id}")
        print(f"  Date: {last_item.start_date}")
        print(f"  Subject: {last_item.subject}")
        print(f"  Topic: {last_item.topic}")
        
        # Also clean up the learning history for this topic if it exists
        # NOTE: Be careful only to delete it if it's not used elsewhere
        lh_item = db.query(LearningHistory).filter(
            LearningHistory.subject == last_item.subject,
            LearningHistory.topic == last_item.topic
        ).first()
        
        if lh_item:
            print(f"Deleting associated learning history item: {lh_item.topic}")
            db.delete(lh_item)
            
        db.delete(last_item)
        db.commit()
        print("Successfully deleted the diary entry and associated learning history!")
        
    except Exception as e:
        db.rollback()
        print("An error occurred:", e)
    finally:
        db.close()

if __name__ == "__main__":
    delete_last_diary_entry()
