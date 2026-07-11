from abc import ABC, abstractmethod
from agent.models import FlightOffer


class FlightProvider(ABC):
    @abstractmethod
    def search(
        self,
        origin: str,
        destination: str,
        date: str,
        adults: int = 1,
        currency: str = "USD",
    ) -> list[FlightOffer]:
        """Search for flight offers. date format: YYYY-MM-DD"""
        ...

    @property
    @abstractmethod
    def name(self) -> str: ...
