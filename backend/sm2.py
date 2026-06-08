from datetime import date, timedelta
from typing import Tuple

class SM2Algorithm:
    """
    SM-2 spaced repetition algorithm for calculating review intervals.
    Based on SuperMemo 2 algorithm by Piotr Wozniak.
    """
    
    @staticmethod
    def calculate_next_review(
        easiness_factor: float,
        interval: int,
        repetitions: int,
        quality: int = 4,  # Default: "perfect response" (0-5 scale)
        reference_date: date = None  # Optional: use custom date instead of today
    ) -> Tuple[float, int, int, date]:
        """
        Calculate next review date and update SM-2 parameters.
        
        Args:
            easiness_factor: Current EF (difficulty), 1.3-2.5
            interval: Current interval in days
            repetitions: Number of successful reviews
            quality: Response quality (0-5). 0=total blackout, 5=perfect
            reference_date: Optional reference date (defaults to today)
        
        Returns:
            (new_ef, new_interval, new_repetitions, next_review_date)
        """
        # Update easiness factor based on quality
        new_ef = easiness_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        
        # Ensure EF stays within bounds
        if new_ef < 1.3:
            new_ef = 1.3
        
        # If quality < 3, reset repetitions (failed recall)
        if quality < 3:
            new_repetitions = 0
            new_interval = 1
        else:
            new_repetitions = repetitions + 1
            
            # Calculate new interval based on repetition count
            if new_repetitions == 1:
                new_interval = 1
            elif new_repetitions == 2:
                new_interval = 6
            else:
                new_interval = round(interval * new_ef)
        
        # Calculate next review date
        base_date = reference_date if reference_date else date.today()
        next_review_date = base_date + timedelta(days=new_interval)
        
        return new_ef, new_interval, new_repetitions, next_review_date
    
    @staticmethod
    def initialize_topic(reference_date: date = None) -> Tuple[float, int, int, date]:
        """
        Initialize SM-2 parameters for a new topic.
        
        Args:
            reference_date: Optional reference date (defaults to today)
        
        Returns:
            (initial_ef, initial_interval, initial_reps, next_review_date)
        """
        initial_ef = 2.5
        initial_interval = 1
        initial_reps = 0
        base_date = reference_date if reference_date else date.today()
        next_review_date = base_date + timedelta(days=1)
        
        return initial_ef, initial_interval, initial_reps, next_review_date
    
    @staticmethod
    def is_due_for_review(next_review_date: date) -> bool:
        """Check if a topic is due for review"""
        return date.today() >= next_review_date
    
    @staticmethod
    def get_days_overdue(next_review_date: date) -> int:
        """Calculate how many days overdue a review is"""
        if date.today() < next_review_date:
            return 0
        return (date.today() - next_review_date).days
