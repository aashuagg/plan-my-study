import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from typing import Optional, List
from datetime import datetime, date, timedelta
import json

from backend.database import SessionLocal, init_db
from backend.crud import (
    create_user, get_user, update_user,
    create_newsletter, add_curriculum_items,
    get_due_topics, get_learning_history,
    get_current_curriculum, save_weekly_plan, get_latest_weekly_plan,
    record_study_session, get_study_sessions, get_sessions_by_date
)
from backend.schemas import UserCreate, NewsletterUpload, CurriculumItemSchema, PlanRequest
from backend.newsletter_parser import NewsletterParser
from backend.ollama_validator import OllamaValidator
from backend.scheduler import get_scheduler
from backend.models import LearningHistory

app = typer.Typer(help="Study Planner CLI - AI-powered study scheduling for kids")
console = Console()

@app.command()
def init():
    """Initialize database tables"""
    init_db()
    console.print("[green]✓[/green] Database initialized successfully!")

@app.command()
def reset_db():
    """Delete all data and reinitialize database (WARNING: irreversible!)"""
    confirm = typer.confirm("⚠️  This will DELETE ALL DATA. Are you sure?")
    if not confirm:
        console.print("[yellow]Cancelled.[/yellow]")
        return
    
    from backend.database import engine, Base
    console.print("[yellow]Dropping all tables...[/yellow]")
    Base.metadata.drop_all(bind=engine)
    console.print("[yellow]Recreating tables...[/yellow]")
    Base.metadata.create_all(bind=engine)
    console.print("[green]✓[/green] Database reset complete! All data deleted.")

@app.command()
def create_profile(
    name: str = typer.Option(..., prompt="Child's name"),
    grade: str = typer.Option(..., prompt="Grade/Standard (e.g., UKG, 1st, 2nd)"),
    board: str = typer.Option(..., prompt="Board (e.g., CBSE, ICSE, Other)"),
    duration: int = typer.Option(..., prompt="Daily study duration (minutes)"),
    frequency: int = typer.Option(..., prompt="Study days per week (e.g., 6)"),
    subjects: str = typer.Option(..., prompt="Subjects (comma-separated, e.g., Math,English,Science)")
):
    """Create a new student profile"""
    db = SessionLocal()
    try:
        subject_list = [s.strip() for s in subjects.split(",")]
        
        user_data = UserCreate(
            name=name,
            grade=grade,
            board=board,
            daily_duration_minutes=duration,
            weekly_frequency=frequency,
            subjects=subject_list
        )
        
        user = create_user(db, user_data)
        console.print(f"[green]✓[/green] Profile created successfully! User ID: {user.id}")
        console.print(f"  Name: {user.name}")
        console.print(f"  Grade: {user.grade} ({user.board})")
        console.print(f"  Study plan: {user.daily_duration_minutes} min/day, {user.weekly_frequency} days/week")
        console.print(f"  Subjects: {', '.join(user.subjects)}")
    finally:
        db.close()

@app.command()
def update_profile(
    user_id: int = typer.Option(..., prompt="User ID"),
    duration: Optional[int] = typer.Option(None, help="New daily duration (minutes)"),
    frequency: Optional[int] = typer.Option(None, help="New weekly frequency"),
    subjects: Optional[str] = typer.Option(None, help="New subjects (comma-separated)")
):
    """Update student profile settings"""
    db = SessionLocal()
    try:
        updates = {}
        if duration:
            updates["daily_duration_minutes"] = duration
        if frequency:
            updates["weekly_frequency"] = frequency
        if subjects:
            updates["subjects"] = [s.strip() for s in subjects.split(",")]
        
        user = update_user(db, user_id, updates)
        if user:
            console.print(f"[green]✓[/green] Profile updated successfully!")
        else:
            console.print(f"[red]✗[/red] User ID {user_id} not found")
    finally:
        db.close()

@app.command()
def view_profile(user_id: int):
    """View student profile"""
    db = SessionLocal()
    try:
        user = get_user(db, user_id)
        if not user:
            console.print(f"[red]✗[/red] User ID {user_id} not found")
            return
        
        console.print("\n[bold]Student Profile[/bold]")
        console.print(f"  ID: {user.id}")
        console.print(f"  Name: {user.name}")
        console.print(f"  Grade: {user.grade}")
        console.print(f"  Board: {user.board}")
        console.print(f"  Study Duration: {user.daily_duration_minutes} minutes/day")
        console.print(f"  Study Frequency: {user.weekly_frequency} days/week")
        console.print(f"  Subjects: {', '.join(user.subjects)}")
    finally:
        db.close()

@app.command()
def upload_newsletter(
    user_id: int = typer.Option(..., prompt="User ID"),
    file_path: str = typer.Option(..., prompt="Newsletter file path (.csv or .xlsx)"),
    month: str = typer.Option(..., prompt="Month (e.g., March)"),
    year: int = typer.Option(..., prompt="Year (e.g., 2026)")
):
    """Upload and parse monthly newsletter (CSV or Excel)"""
    db = SessionLocal()
    try:
        console.print(f"[yellow]Parsing newsletter...[/yellow]")
        
        # Parse newsletter
        raw_items = NewsletterParser.auto_parse(file_path)
        console.print(f"[green]✓[/green] Extracted {len(raw_items)} curriculum items")
        
        # Create newsletter record
        newsletter_data = NewsletterUpload(
            user_id=user_id,
            month=month,
            year=year,
            file_path=file_path
        )
        newsletter = create_newsletter(db, newsletter_data)
        
        # Add curriculum items - convert dates
        curriculum_items = []
        for item in raw_items:
            try:
                # Parse date string to date object
                from datetime import datetime
                if isinstance(item.get("start_date"), str):
                    date_str = item["start_date"]
                    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"]:
                        try:
                            item["start_date"] = datetime.strptime(date_str, fmt).date()
                            break
                        except ValueError:
                            continue
                
                if item.get("end_date") and isinstance(item["end_date"], str):
                    date_str = item["end_date"]
                    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"]:
                        try:
                            item["end_date"] = datetime.strptime(date_str, fmt).date()
                            break
                        except ValueError:
                            continue
                
                # Skip if no valid start date
                if not item.get("start_date") or isinstance(item["start_date"], str):
                    console.print(f"[red]Skipping - no valid date: {item}[/red]")
                    continue
                
                curriculum_items.append(CurriculumItemSchema(**item))
            except Exception as e:
                console.print(f"[red]Error: {item.get('subject', '?')} - {str(e)}[/red]")
        
        add_curriculum_items(db, newsletter.id, curriculum_items)
        
        console.print(f"[green]✓[/green] Newsletter uploaded successfully! ID: {newsletter.id}")
        console.print(f"  Added {len(curriculum_items)} topics to curriculum")
        console.print(f"  Initialized SM-2 tracking for new topics")
        
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {str(e)}")
    finally:
        db.close()

@app.command()
def list_subjects(user_id: int):
    """List all unique subjects in the curriculum"""
    db = SessionLocal()
    try:
        from sqlalchemy import select, distinct
        from backend.models.curriculum import CurriculumItem
        from backend.models.newsletter import Newsletter
        
        stmt = select(distinct(CurriculumItem.subject)).join(Newsletter).where(Newsletter.user_id == user_id)
        subjects = db.execute(stmt).scalars().all()
        
        console.print(f"\n[bold]Subjects in curriculum for user {user_id}:[/bold]")
        for subject in sorted(subjects):
            console.print(f"  - {subject}")
    finally:
        db.close()

@app.command()
def generate_plan(
    user_id: int = typer.Option(..., prompt="User ID"),
    start_date: Optional[str] = typer.Option(None, help="Week start date (YYYY-MM-DD). Default: next Monday"),
    focus: Optional[str] = typer.Option(None, help="Focus request (e.g., 'extra Math this week')"),
    events: Optional[str] = typer.Option(None, help="Upcoming events (e.g., 'Olympiad on March 20')")
):
    """Generate weekly study plan using Ollama"""
    db = SessionLocal()
    try:
        # Get user profile
        user = get_user(db, user_id)
        if not user:
            console.print(f"[red]✗[/red] User ID {user_id} not found")
            return
        
        # Determine week start date
        if start_date:
            week_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        else:
            # Next Monday
            today = date.today()
            days_ahead = 0 - today.weekday() + 7 if today.weekday() != 0 else 7
            week_start = today + timedelta(days=days_ahead)
        
        console.print(f"\n[bold]Generating plan for week starting {week_start}...[/bold]")
        
        # Gather data
        console.print("[yellow]Gathering curriculum data...[/yellow]")
        current_curriculum = get_current_curriculum(db, user_id, week_start)
        due_topics = get_due_topics(db, user_id)
        learning_history = get_learning_history(db, user_id)
        
        console.print(f"  Current curriculum: {len(current_curriculum)} topics")
        console.print(f"  Topics due for review: {len(due_topics)} topics")
        console.print(f"  Total learning history: {len(learning_history)} topics")
        
        # Prepare data for scheduler
        user_profile = {
            "name": user.name,
            "grade": user.grade,
            "board": user.board,
            "daily_duration_minutes": user.daily_duration_minutes,
            "weekly_frequency": user.weekly_frequency,
            "subjects": user.subjects
        }
        
        curriculum_data = [
            {
                "subject": item.subject,
                "topic": item.topic,
                "start_date": item.start_date.strftime("%Y-%m-%d")
            }
            for item in current_curriculum
        ]
        
        due_data = [
            {
                "subject": item.subject,
                "topic": item.topic,
                "next_review": item.next_review,
                "easiness_factor": item.easiness_factor
            }
            for item in due_topics
        ]
        
        history_data = [
            {
                "subject": item.subject,
                "topic": item.topic,
                "last_reviewed": item.last_reviewed,
                "easiness_factor": item.easiness_factor
            }
            for item in learning_history
        ]
        
        # Generate plan with Ollama
        console.print("[yellow]Generating plan with Ollama (this may take a moment)...[/yellow]")
        scheduler = get_scheduler()
        plan = scheduler.generate_weekly_plan(
            user_profile,
            curriculum_data,
            due_data,
            history_data,
            week_start,
            focus,
            events
        )
        
        # Fix Ollama response structure - sometimes rationale is in the list
        weekly_plan_items = plan.get("weekly_plan", [])
        rationale = plan.get("rationale", "")
        
        # Extract rationale if it's the last element in weekly_plan list
        if weekly_plan_items and isinstance(weekly_plan_items[-1], dict) and "rationale" in weekly_plan_items[-1] and "subjects" not in weekly_plan_items[-1]:
            rationale = weekly_plan_items[-1]["rationale"]
            weekly_plan_items = weekly_plan_items[:-1]
        
        # Rebuild plan structure
        plan_fixed = {
            "weekly_plan": weekly_plan_items,
            "rationale": rationale
        }
        
        # Save plan
        plan_request = PlanRequest(
            user_id=user_id,
            week_start_date=week_start,
            focus_request=focus,
            events=events
        )
        save_weekly_plan(db, plan_request, plan_fixed)
        
        # Display plan
        console.print("\n[green]✓[/green] [bold]Weekly Study Plan Generated![/bold]\n")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Date", style="cyan", width=12)
        table.add_column("Subjects", style="green")
        table.add_column("Topics", style="yellow")
        table.add_column("Duration", style="blue", justify="right")
        
        for day in plan_fixed["weekly_plan"]:
            subjects_str = ", ".join(day["subjects"])
            topics_str = "\n".join([
                f"{'[NEW]' if day['is_new_topic'][i] else '[REV]'} {topic}"
                for i, topic in enumerate(day["topics"])
            ])
            
            table.add_row(
                day["date"],
                subjects_str,
                topics_str,
                f"{day['duration_minutes']} min"
            )
        
        console.print(table)
        
        console.print(f"\n[bold]Rationale:[/bold]")
        console.print(f"{plan_fixed['rationale']}\n")
        
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {str(e)}")
        import traceback
        console.print(traceback.format_exc())
    finally:
        db.close()

@app.command()
def view_plan(user_id: int):
    """View latest generated weekly plan"""
    db = SessionLocal()
    try:
        plan = get_latest_weekly_plan(db, user_id)
        if not plan:
            console.print(f"[yellow]No plans found for user {user_id}[/yellow]")
            return
        
        console.print(f"\n[bold]Latest Weekly Plan[/bold]")
        console.print(f"Week starting: {plan.week_start_date}")
        console.print(f"Generated: {plan.generated_at.strftime('%Y-%m-%d %H:%M')}")
        
        if plan.focus_request:
            console.print(f"Focus: {plan.focus_request}")
        if plan.events:
            console.print(f"Events: {plan.events}")
        
        console.print()
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Date", style="cyan")
        table.add_column("Subjects", style="green")
        table.add_column("Topics", style="yellow")
        table.add_column("Duration", style="blue")
        
        for day in plan.plan_data["weekly_plan"]:
            subjects_str = ", ".join(day["subjects"])
            topics_str = "\n".join(day["topics"])
            
            table.add_row(
                day["date"],
                subjects_str,
                topics_str,
                f"{day['duration_minutes']} min"
            )
        
        console.print(table)
        
    finally:
        db.close()

@app.command()
def record_session(
    user_id: int = typer.Option(..., prompt="User ID"),
    topic_search: str = typer.Option(..., prompt="Topic (search term)"),
    session_type: str = typer.Option(..., prompt="Session type (study/review)"),
    quality: Optional[int] = typer.Option(None, help="Quality rating 0-5 (required for review)"),
    session_date: Optional[str] = typer.Option(None, help="Session date (YYYY-MM-DD), default: today"),
    notes: Optional[str] = typer.Option(None, help="Optional notes")
):
    """Record a study or review session for a topic"""
    db = SessionLocal()
    try:
        # Parse date
        if session_date:
            sess_date = datetime.strptime(session_date, "%Y-%m-%d").date()
        else:
            sess_date = date.today()
        
        # Validate session type
        if session_type not in ["study", "review"]:
            console.print(f"[red]✗[/red] Invalid session type. Use 'study' or 'review'")
            return
        
        # Validate quality for review
        if session_type == "review" and quality is None:
            console.print(f"[red]✗[/red] Quality rating (0-5) is required for review sessions")
            return
        
        if quality is not None and (quality < 0 or quality > 5):
            console.print(f"[red]✗[/red] Quality rating must be between 0 and 5")
            return
        
        # Search for topic in learning history
        learning_items = db.query(LearningHistory).filter(
            LearningHistory.user_id == user_id,
            LearningHistory.topic.ilike(f"%{topic_search}%")
        ).all()
        
        if not learning_items:
            console.print(f"[yellow]No topics found matching '{topic_search}'[/yellow]")
            return
        
        if len(learning_items) > 1:
            console.print(f"[yellow]Multiple topics found:[/yellow]")
            for i, item in enumerate(learning_items[:10], 1):
                console.print(f"  {i}. [{item.subject}] {item.topic}")
            
            choice = typer.prompt("Select topic number", type=int)
            if choice < 1 or choice > len(learning_items):
                console.print(f"[red]✗[/red] Invalid selection")
                return
            selected = learning_items[choice - 1]
        else:
            selected = learning_items[0]
        
        # Record session
        session = record_study_session(
            db,
            user_id=user_id,
            learning_history_id=selected.id,
            session_date=sess_date,
            session_type=session_type,
            quality_rating=quality,
            notes=notes
        )
        
        console.print(f"[green]✓[/green] Session recorded!")
        console.print(f"  Topic: [{selected.subject}] {selected.topic}")
        console.print(f"  Type: {session_type}")
        if quality is not None:
            console.print(f"  Quality: {quality}/5")
        
        # Show updated review info
        db.refresh(selected)
        if session_type == "review":
            console.print(f"  Next review: {selected.next_review} (in {selected.interval} days)")
            console.print(f"  Easiness: {selected.easiness_factor:.2f}")
        else:
            console.print(f"  First review scheduled: {selected.next_review}")
        
    finally:
        db.close()

@app.command()
def view_progress(user_id: int):
    """View learning progress and topics due for review"""
    db = SessionLocal()
    try:
        user = get_user(db, user_id)
        if not user:
            console.print(f"[red]✗[/red] User ID {user_id} not found")
            return
        
        # Get statistics
        all_topics = get_learning_history(db, user_id)
        due_topics = get_due_topics(db, user_id)
        recent_sessions = get_study_sessions(db, user_id, limit=10)
        
        console.print(f"\n[bold]Learning Progress - {user.name}[/bold]\n")
        
        # Statistics
        console.print(f"[cyan]Statistics:[/cyan]")
        console.print(f"  Total topics tracked: {len(all_topics)}")
        console.print(f"  Topics due for review: {len(due_topics)}")
        
        if all_topics:
            avg_ef = sum(t.easiness_factor for t in all_topics) / len(all_topics)
            console.print(f"  Average easiness: {avg_ef:.2f}")
        
        # Due topics
        if due_topics:
            console.print(f"\n[yellow]Topics Due for Review:[/yellow]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Subject", style="cyan")
            table.add_column("Topic", style="green")
            table.add_column("Due Date", style="yellow")
            table.add_column("Days Overdue", style="red")
            
            for topic in due_topics[:20]:
                days_overdue = (date.today() - topic.next_review).days
                table.add_row(
                    topic.subject,
                    topic.topic[:50],
                    str(topic.next_review),
                    str(days_overdue) if days_overdue > 0 else "Today"
                )
            
            console.print(table)
            if len(due_topics) > 20:
                console.print(f"[dim]... and {len(due_topics) - 20} more topics[/dim]")
        
        # Recent sessions
        if recent_sessions:
            console.print(f"\n[cyan]Recent Study Sessions:[/cyan]")
            for session in recent_sessions[:5]:
                lh = db.query(LearningHistory).filter(LearningHistory.id == session.learning_history_id).first()
                quality_str = f" (quality: {session.quality_rating}/5)" if session.quality_rating is not None else ""
                console.print(f"  {session.session_date} - [{lh.subject}] {lh.topic[:40]} - {session.session_type}{quality_str}")
        
    finally:
        db.close()

if __name__ == "__main__":
    app()

