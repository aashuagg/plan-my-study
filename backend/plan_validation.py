"""Check generated plans against the exact topics offered to the scheduler."""

from datetime import timedelta


def correct_unambiguous_topics(plan, curriculum, due_topics):
    """Repair a wrong subject or added subject prefix when the source has one exact match."""
    candidates = {(item["subject"], item["topic"]) for item in curriculum[:20] + due_topics[:30]}
    for day in plan.get("weekly_plan", []):
        if not isinstance(day, dict):
            continue
        topics, subjects = day.get("topics"), day.get("subjects")
        if not isinstance(topics, list) or not isinstance(subjects, list) or not topics:
            continue
        corrected_topics = list(topics)
        corrected_subjects = [
            subjects[index] if index < len(subjects) else (subjects[0] if subjects else None)
            for index in range(len(topics))
        ]
        changed = False
        for index, topic in enumerate(topics):
            if not isinstance(topic, str):
                continue
            exact = [pair for pair in candidates if pair[1] == topic]
            matches = exact
            if not matches and ":" in topic:
                prefix, _, bare_topic = topic.partition(":")
                matches = [
                    pair for pair in candidates
                    if pair[0] == prefix.strip().upper() and pair[1] == bare_topic.strip()
                ]
            if len(matches) == 1:
                subject, source_topic = matches[0]
                if (corrected_subjects[index], topic) != (subject, source_topic):
                    corrected_subjects[index] = subject
                    corrected_topics[index] = source_topic
                    changed = True
        if changed:
            day["topics"] = corrected_topics
            day["subjects"] = (
                corrected_subjects[:1] if len(set(corrected_subjects)) == 1
                else corrected_subjects
            )
    return plan


def validate_weekly_plan(plan, profile, curriculum, due_topics, week_start):
    """Return actionable errors; an empty list means the plan can be saved."""
    errors = []
    allowed_new = {(item["subject"], item["topic"]) for item in curriculum[:20]}
    allowed_due = {(item["subject"], item["topic"]) for item in due_topics[:30]}
    allowed = allowed_new | allowed_due
    expected_dates = {
        (week_start + timedelta(days=offset)).isoformat()
        for offset in range(profile["weekly_frequency"])
    }
    days = plan.get("weekly_plan") if isinstance(plan, dict) else None
    if not isinstance(days, list):
        return ["weekly_plan must be a list of days"]
    if len(days) != len(expected_dates):
        errors.append(f"Expected {len(expected_dates)} study days; got {len(days)}")

    seen_dates = set()
    seen_topics = set()
    for index, day in enumerate(days, 1):
        if not isinstance(day, dict):
            errors.append(f"Day {index} must be an object")
            continue
        day_date = day.get("date")
        label = f"Day {index} ({day_date})"
        if not isinstance(day_date, str) or day_date not in expected_dates:
            errors.append(f"{label}: date is outside the requested study week")
        if isinstance(day_date, str) and day_date in seen_dates:
            errors.append(f"{label}: date appears more than once")
        if isinstance(day_date, str):
            seen_dates.add(day_date)

        subjects = day.get("subjects")
        topics = day.get("topics")
        new_flags = day.get("is_new_topic")
        if not isinstance(subjects, list) or not all(isinstance(s, str) for s in subjects):
            errors.append(f"{label}: subjects must be a list of names")
            continue
        if not isinstance(topics, list) or not all(isinstance(t, str) for t in topics):
            errors.append(f"{label}: topics must be a list of names")
            continue
        if not 1 <= len(topics) <= 2:
            errors.append(f"{label}: must have 1 or 2 topics")
        if not 1 <= len(subjects) <= 2:
            errors.append(f"{label}: must have 1 or 2 subjects")
        if len(subjects) > len(topics):
            errors.append(f"{label}: more subjects than topics")
        if len(subjects) == 2 and len(topics) == 2 and subjects[0] == subjects[1]:
            errors.append(f"{label}: duplicate subject labels")
        if not isinstance(new_flags, list) or len(new_flags) != len(topics) or not all(isinstance(flag, bool) for flag in new_flags):
            errors.append(f"{label}: is_new_topic must contain one boolean per topic")
            new_flags = []
        if day.get("duration_minutes") != profile["daily_duration_minutes"]:
            errors.append(f"{label}: duration must be {profile['daily_duration_minutes']} minutes")

        for topic_index, topic in enumerate(topics):
            subject = subjects[topic_index] if topic_index < len(subjects) else (subjects[0] if subjects else None)
            pair = (subject, topic)
            if subject not in profile["subjects"]:
                errors.append(f"{label}: {subject!r} is not in the student profile")
            if pair not in allowed:
                errors.append(f"{label}: {pair!r} is not an exact subject/topic pair in the supplied curriculum or due set")
            if pair in seen_topics:
                errors.append(f"{label}: {pair!r} is already scheduled this week")
            seen_topics.add(pair)
            if topic_index < len(new_flags):
                if new_flags[topic_index] and pair not in allowed_new:
                    errors.append(f"{label}: {pair!r} is marked new but is only in the due set")
                if not new_flags[topic_index] and pair not in allowed_due:
                    errors.append(f"{label}: {pair!r} is marked review but is only in the new set")

    for missing_date in sorted(expected_dates - seen_dates):
        errors.append(f"Missing study day {missing_date}")
    return errors
