import math
from datetime import datetime


def calculate_rake(
    seated_at: datetime,
    left_at: datetime,
    rake_interval_minutes: int,
    rake_amount: int,
) -> int:
    duration_minutes = (left_at - seated_at).total_seconds() / 60
    if duration_minutes <= 0:
        return 0
    return math.ceil(duration_minutes / rake_interval_minutes) * rake_amount
