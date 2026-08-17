import tracker.models


class ScoreSideConverter:
    regex = "|".join(tracker.models.ScoreEvent.Side.values)

    def to_python(self, value: str) -> tracker.models.ScoreEvent.Side:
        return tracker.models.ScoreEvent.Side(value)

    def to_url(self, value: tracker.models.ScoreEvent.Side | str) -> str:
        return str(value)
