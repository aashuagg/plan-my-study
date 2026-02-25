from langchain_ollama import ChatOllama
#from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from datetime import date, timedelta
from backend.config import settings


def get_scheduler():
    """Factory function to return the appropriate scheduler based on config"""
    if settings.ai_provider.lower() == "claude":
        return ClaudeScheduler()
    else:
        return OllamaScheduler()


class DailyPlan(BaseModel):
    """Schema for a single day's study plan"""
    date: str = Field(description="Date in YYYY-MM-DD format")
    subjects: List[str] = Field(description="List of subjects for the day")
    topics: List[str] = Field(description="List of specific topics to study")
    is_new_topic: List[bool] = Field(description="Boolean list indicating if each topic is new (True) or review (False)")
    duration_minutes: int = Field(description="Total study duration in minutes")

class WeeklyPlanOutput(BaseModel):
    """Schema for complete weekly study plan"""
    weekly_plan: List[DailyPlan] = Field(description="6-day study plan")
    rationale: str = Field(description="Explanation of how topics were balanced and scheduled")


class BaseScheduler:
    """Base class for AI-powered weekly study plan generation"""
    
    def __init__(self):
        self.llm = None
        self.parser = JsonOutputParser(pydantic_object=WeeklyPlanOutput)
    
    def generate_weekly_plan(
        self,
        user_profile: Dict[str, Any],
        current_curriculum: List[Dict[str, Any]],
        due_topics: List[Dict[str, Any]],
        learning_history: List[Dict[str, Any]],
        week_start_date: date,
        focus_request: str = None,
        events: str = None
    ) -> Dict[str, Any]:
        """
        Generate a balanced weekly study plan using AI.
        
        Args:
            user_profile: Student info (grade, subjects, duration, frequency)
            current_curriculum: Topics from current month's newsletter
            due_topics: Topics due for SM-2 review
            learning_history: Full learning history with SM-2 params
            week_start_date: Starting date for the week
            focus_request: Optional user emphasis (e.g., "focus on Math")
            events: Optional upcoming events (e.g., "Olympiad on March 20")
            
        Returns:
            Dict with weekly_plan and rationale
        """
        
        # Build combined prompt
        full_prompt = self._build_full_prompt(
            user_profile,
            current_curriculum,
            due_topics,
            learning_history,
            week_start_date,
            focus_request,
            events
        )

        system_prompt = self._build_system_prompt()

        print(f"Generated prompt for {self.__class__.__name__}:")
        print(system_prompt)
        print(full_prompt)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", full_prompt + "\n\n{format_instructions}")
        ])
        
        chain = prompt | self.llm | self.parser
        
        result = chain.invoke({
            "format_instructions": self.parser.get_format_instructions()
        })
        
        return result
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for LLM"""
        return """You are an expert educational planner specializing in creating balanced study schedules for children using spaced repetition principles.

**Your Responsibilities:**
1. Create daily study plans that balance NEW curriculum topics with REVIEW of previously learned topics
2. Follow the SM-2 spaced repetition algorithm - prioritize topics that are due for review
3. Ensure NO subject is neglected for more than 7 consecutive days
4. Distribute subjects evenly across the week to maintain engagement
5. Respect time constraints (daily duration and weekly frequency)
6. Adapt plans based on upcoming events (e.g., olympiads, tests)
7. Honor user's focus requests while maintaining balance

**CRITICAL:**
ONLY use subjects and topics from the curriculum data provided. DO NOT make up or invent subjects or topics.

**SM-2 Spaced Repetition Guidelines:**
- Topics with next_review <= today are DUE and should be prioritized
- Topics not practiced in 7+ days risk being forgotten
- Balance: ~60% time on NEW topics, ~40% on REVIEW topics
- Mix subjects within each day when possible (max 2 subjects per day)

**Scheduling Principles:**
- Variety: Don't repeat same subjects on consecutive days unless necessary
- Difficulty distribution: Mix easier and harder topics within a session
- Context switching: If doing 2 subjects in one day, space them mentally (e.g., Math then English, not Math then Physics)
- Age-appropriate: Adjust complexity and pacing based on grade level

**Output Requirements:**
- Exactly match the requested number of study days per week
- Stay within daily time limits
- Provide clear rationale for scheduling decisions
- Mark each topic as new or review
- ONLY use subjects from the provided curriculum list"""

    def _build_full_prompt(
        self,
        user_profile: Dict[str, Any],
        current_curriculum: List[Dict[str, Any]],
        due_topics: List[Dict[str, Any]],
        learning_history: List[Dict[str, Any]],
        week_start_date: date,
        focus_request: str,
        events: str
    ) -> str:
        """Build complete prompt with user context"""
        
        # Format dates for the week
        week_dates = [
            (week_start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(user_profile["weekly_frequency"])
        ]
        
        context = f"""**Student Profile:**
- Name: {user_profile["name"]}
- Grade: {user_profile["grade"]}
- Board: {user_profile["board"]}
- Daily Study Duration: {user_profile["daily_duration_minutes"]} minutes
- Study Days Per Week: {user_profile["weekly_frequency"]} days
- Subjects: {", ".join(user_profile["subjects"])}

**Week to Plan:** {week_dates[0]} to {week_dates[-1]} ({user_profile["weekly_frequency"]} study days)

**Current Curriculum (New Topics to Cover):**
{self._format_curriculum(current_curriculum)}

**Topics Due for Review (SM-2 Algorithm):**
{self._format_due_topics(due_topics)}

**Learning History Summary:**
{self._format_learning_history(learning_history)}
"""
        
        if focus_request:
            context += f"\n**User's Focus Request:** {focus_request}"
        
        if events:
            context += f"\n**Upcoming Events:** {events}"
        
        context += f"""

**Task:** Generate a {user_profile["weekly_frequency"]}-day study plan for the dates listed above.

**CRITICAL RULES - YOU MUST FOLLOW THESE EXACTLY:**
1. ONLY use subjects and topics from the "Current Curriculum" and "Topics Due for Review" sections above
2. DO NOT invent, create, or make up ANY subjects or topics
3. Each day should total {user_profile["daily_duration_minutes"]} minutes
4. Ensure ALL subjects appear at least 2 times during the week - no subject should appear only once
5. Balance subject distribution: Hindi, Kannada, Literacy, Numeracy, General Awareness should each get 2-3 appearances
6. Balance new curriculum topics (~60%) with review topics (~40%)
7. Copy topic names EXACTLY as they appear in the curriculum data
8. The last day of the week follows the SAME rules as every other day.There is no "catch-up" day. If week ends with unscheduled topics, they move to next week.
9. Provide a clear rationale explaining your scheduling decisions

SUBJECT-TOPIC MATCHING RULE:
Each topic must belong to one of the subjects listed for that day.
Before finalizing each day, verify: does every topic's subject appear in that day's subject list?
If not, either change the topic or change the day's subjects.

ABSOLUTE HARD LIMIT: Maximum 2 topics per day, no exceptions.
It is CORRECT and EXPECTED to leave topics unscheduled.
Unscheduled topics automatically carry over to next week.
A plan with 2 topics per day is a PERFECT plan.
A plan with 3+ topics on any day is a FAILED plan.

**Rationale must explain:**
- How you balanced subjects across the week
- Why certain topics were prioritized
- How you ensured no subject was neglected"""
        
        return context
    
    def _format_curriculum(self, curriculum: List[Dict[str, Any]]) -> str:
        """Format curriculum items for prompt"""
        if not curriculum:
            return "No new curriculum topics for this period."
        
        items = []
        for item in curriculum[:20]:  # Limit to prevent token overflow
            items.append(f"  - {item['subject']}: {item['topic']} (starts {item['start_date']})")
        
        return "\n".join(items)
    
    def _format_due_topics(self, due_topics: List[Dict[str, Any]]) -> str:
        """Format topics due for review"""
        if not due_topics:
            return "No topics currently due for review."
        
        items = []
        for topic in due_topics[:15]:  # Limit to prevent token overflow
            days_overdue = (date.today() - topic["next_review"]).days if isinstance(topic["next_review"], date) else 0
            items.append(
                f"  - {topic['subject']}: {topic['topic']} "
                f"(due: {topic['next_review']}, {days_overdue} days overdue, "
                f"easiness: {topic['easiness_factor']:.1f})"
            )
        
        return "\n".join(items)
    
    def _format_learning_history(self, history: List[Dict[str, Any]]) -> str:
        """Format learning history summary"""
        if not history:
            return "No learning history yet."
        
        # Group by subject to show last practiced dates
        # ONLY include subjects that have actually been practiced (last_reviewed is not None)
        subject_summary = {}
        for item in history:
            # Skip topics that have never been reviewed - they're not "overdue", they're just new
            if not item.get("last_reviewed"):
                continue
                
            subj = item["subject"]
            if subj not in subject_summary:
                subject_summary[subj] = {
                    "last_date": item["last_reviewed"],
                    "topic_count": 0
                }
            subject_summary[subj]["topic_count"] += 1
            
            # Track most recent date
            if item["last_reviewed"] > subject_summary[subj]["last_date"]:
                subject_summary[subj]["last_date"] = item["last_reviewed"]
        
        if not subject_summary:
            return "No topics have been practiced yet - focus on introducing new curriculum."
        
        summary = []
        for subj, data in subject_summary.items():
            last_date_str = data["last_date"].strftime("%Y-%m-%d")
            days_since = (date.today() - data["last_date"]).days
            summary.append(
                f"  - {subj}: {data['topic_count']} topics practiced, "
                f"last session {last_date_str} ({days_since} days ago)"
            )
        
        return "\n".join(summary)


class OllamaScheduler(BaseScheduler):
    """Scheduler using local Ollama for development"""
    
    def __init__(self):
        super().__init__()
        self.llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.0,
            format="json"
        )


class ClaudeScheduler(BaseScheduler):
    """Scheduler using Claude API for production"""
    
    def __init__(self):
        super().__init__()
        if not settings.claude_api_key:
            raise ValueError("CLAUDE_API_KEY not set in environment variables")
        
        self.llm = ChatAnthropic(
            model=settings.claude_model,
            api_key=settings.claude_api_key,
            temperature=0.0
        )
