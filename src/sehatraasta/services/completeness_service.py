from sehatraasta.domain import PresenceState, ReviewCategory


class CompletenessService:
    def group_categories(self, bundle):
        reviews = {review.category: review for review in bundle.category_reviews}
        groups = {
            "present": [],
            "missing": [],
            "pending": [],
            "not_reviewed": [],
            "not_applicable": [],
        }

        for category in ReviewCategory:
            review = reviews.get(category)
            if review is None:
                groups["not_reviewed"].append(category)
            elif review.state == PresenceState.PRESENT:
                groups["present"].append(category)
            elif review.state == PresenceState.MISSING:
                groups["missing"].append(category)
            elif review.state == PresenceState.PENDING:
                groups["pending"].append(category)
            elif review.state == PresenceState.NOT_APPLICABLE:
                groups["not_applicable"].append(category)

        return groups
