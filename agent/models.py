from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FlightOffer:
    airline: str
    price: float
    currency: str
    departure_time: datetime
    arrival_time: datetime
    duration: str
    stops: int
    origin: str
    destination: str
    recorded_at: datetime = field(default_factory=datetime.now)
    booking_url: str | None = None

    def display_price(self) -> str:
        return f"{self.currency} {self.price:,.2f}"
