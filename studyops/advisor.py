from __future__ import annotations

from collections import Counter
from typing import Any


class StudyAdvisor:
    """Small rule-based advisor for StudyOps."""

    TOPICS = {
        "IELTS / English": ("ielts", "english", "speaking", "listening", "reading", "writing"),
        "Japanese / JLPT": ("japanese", "jlpt", "n5", "n4", "n3", "kanji"),
        "Coding / Algorithm": ("python", "java", "leetcode", "algorithm", "runtime", "code"),
        "Math": ("math", "algebra", "calculus", "probability"),
        "System / DevOps": ("linux", "system", "devops", "docker", "network", "server"),
    }
    TAGS = {
        "IELTS / English": ["#english", "#ielts"],
        "Japanese / JLPT": ["#japanese", "#jlpt"],
        "Coding / Algorithm": ["#coding", "#algorithm"],
        "Math": ["#math"],
        "System / DevOps": ["#system", "#devops"],
        "General Study": ["#study"],
    }

    async def generate_question_note(self, question: str, *, author_name: str | None = None) -> dict[str, Any]:
        topic = self.detect_topic(question)
        tags = self.TAGS.get(topic, ["#study"])
        note = self.note_text(question, topic)
        owner = f" for **{author_name}**" if author_name else ""
        text = "\n".join([
            f"Learning note{owner}", "", "Question:", question[:1500], "",
            "Predicted topic:", topic, "", "Clarify:",
            "- What exactly are you trying to understand or apply?",
            "- What have you tried so far?",
            "- Can you create a small example?", "", "Thinking guide:",
            "- Break the question into smaller parts.",
            "- State your assumptions first.",
            "- Test with a simple example.", "", "Study note:",
            note, "", "Tags: " + " ".join(tags), "", "Status: Unresolved",
        ])
        return {"topic": topic, "tags": tags, "note": note, "status": "unresolved", "text": text}

    def detect_topic(self, text: str) -> str:
        lowered = text.casefold()
        scores: Counter[str] = Counter()
        for topic, keywords in self.TOPICS.items():
            for keyword in keywords:
                if keyword.casefold() in lowered:
                    scores[topic] += 1
        return scores.most_common(1)[0][0] if scores else "General Study"

    async def generate_deep_dive_checklist(self, question: str, topic: str) -> str:
        return "\n".join([
            "Deep-dive checklist", "", f"Topic: {topic}", f"Original question: {question[:500]}", "",
            "1. Rewrite the problem in your own words.",
            "2. List the background knowledge to review.",
            "3. Create a small example.",
            "4. Save the final conclusion as a review note.",
        ])

    async def generate_daily_summary(self, sessions: list[dict[str, Any]], *, label: str) -> str:
        total = sum(int(item.get("duration_minutes", 0)) for item in sessions)
        subjects = [item.get("subject", "Other") for item in sessions]
        subject_text = ", ".join(dict.fromkeys(subjects)) if subjects else "None"
        return "\n".join([
            f"Study Summary - {label}", "",
            f"Total time: {self.format_minutes(total)}",
            f"Subjects: {subject_text}",
            f"One percent better: {self.one_percent_action(total, sessions)}", "",
            "Next optimization:",
            "1. Start with a 10-minute warm-up.",
            "2. Split large tasks into 25-45 minute blocks.",
            "3. Write the next action after each session.",
        ])

    async def generate_vocab_explanation(self, item: dict[str, Any], correct: bool) -> str:
        marker = "Correct." if correct else "Not yet."
        lines = [marker, "", f"Answer: {item['answer']}. {item['options'][item['answer']]}", f"Meaning: {item['meaning_vi']}"]
        if item.get("language") == "japanese":
            lines += [f"Term: {item['term']}", f"Reading: {item.get('reading', '-')}", f"Example: {item.get('example', '-')}"]
        else:
            lines += [f"Word: {item['term']}", f"Pronunciation: {item.get('pronunciation', '-')}", f"Collocation: {item.get('collocation', '-')}", f"Example: {item.get('example', '-')}"]
        lines.append(f"Explanation: {item.get('explanation', 'Review the example and make your own sentence.')}")
        return "\n".join(lines)

    def note_text(self, question: str, topic: str) -> str:
        cleaned = " ".join(question.split())
        if len(cleaned) > 180:
            cleaned = cleaned[:177] + "..."
        return f"Review this {topic} question: {cleaned}"

    @staticmethod
    def format_minutes(minutes: int) -> str:
        hours, rest = divmod(max(0, int(minutes)), 60)
        if hours and rest:
            return f"{hours}h {rest:02d}m"
        if hours:
            return f"{hours}h"
        return f"{rest}m"

    @staticmethod
    def one_percent_action(total_minutes: int, sessions: list[dict[str, Any]]) -> str:
        if total_minutes <= 0:
            return "Log one small study session."
        if len(sessions) >= 2:
            return "You completed more than one study block."
        if total_minutes >= 25:
            return "You completed at least one real focus block."
        return "You started instead of waiting for motivation."
