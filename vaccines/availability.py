from vaccines.models import Product, Series


class AvailabilityResolver:
    def is_product_available(self, product: Product) -> bool:
        return bool(product.active and product.available)

    def series_product_priority(self, series: Series, product_id: int) -> int:
        for link in series.series_products.all():
            if link.product_id == product_id:
                return link.priority
        return 9999

    def choose_due_state(self, series: Series, valid_records, states):
        available_states = [state for state in states if state['is_available']]
        if available_states:
            return self.choose_preferred_state(series, valid_records, available_states)
        return self.choose_preferred_state(series, valid_records, states)

    def choose_upcoming_state(self, series: Series, valid_records, states):
        available_states = [state for state in states if state['is_available']]
        if available_states:
            states = available_states
        return sorted(
            states,
            key=lambda state: (
                state['target_date'],
                -state['rule'].min_age_days,
                0 if state['last_product_match'] else 1,
                state['priority'],
                state['rule'].product.vaccine.name,
            ),
        )[0]

    def choose_preferred_state(self, series: Series, valid_records, states):
        available_states = [state for state in states if state['is_available']]
        if available_states:
            states = available_states
        return sorted(
            states,
            key=lambda state: (
                -state['rule'].min_age_days,
                0 if state['last_product_match'] else 1,
                state['priority'],
                state['rule'].product.vaccine.name,
            ),
        )[0]
