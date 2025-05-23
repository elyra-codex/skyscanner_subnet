import typing
import bittensor as bt
from pydantic import BaseModel, Field
from typing import Optional, Literal, List

# ----------------------------------------------------------------------
# PROTOCOL: Validator ↔ Miner for Skyscanner “cheapest flight” queries
# ----------------------------------------------------------------------

class FlightSearchRequest(bt.Synapse, BaseModel):
    """
    Sent by the validator to request flight options from a miner.
    """
    date: str = Field(
        ...,
        description="Departure date in YYYY-MM-DD format"
    )
    # airport IATA code
    departure_airport_code: str = Field(
        ...,
        description="Departure city or airport name"
    )
    # originId: str = Field(
    #     ...,
    #     description="Skyscanner SkyId for the origin airport"
    # )
    arrival_airport_code: str = Field(
        ...,
        description="Destination city or airport name"
    )
    # destinationId: str = Field(
    #     ...,
    #     description="Skyscanner SkyId for the destination airport"
    # )
    cabinClass: Optional[Literal["Economy", "Business", "First", "Premium_Economy"]] = Field(
        default='Economy',
        description="Cabin class for the search"
    )
    adults: Optional[int] = Field(
        default=1,
        ge=1,
        description="Number of adult passengers (≥1)"
    )
    children: Optional[int] = Field(
        default=0,
        ge=0,
        description="Number of child passengers"
    )
    infants: Optional[int] = Field(
        default=0,
        ge=0,
        description="Number of infant passengers"
    )
    # locale: Optional[str] = Field(
    #     default='en-US',
    #     description="Locale for displayed results"
    # )
    # region ISO code
    market: str = Field(
        default='US',
        description="Market/country code for pricing"
    )
    currency: Optional[str] = Field(
        default='USD',
        description="Currency code for price values (USD, INR, EUR)"
    )


    def deserialize(self) -> None:
        """
        Hook after deserialization; you could validate date formats here
        or convert to a datetime.date if you prefer.
        """
        pass


class FlightSearchResponse(bt.Synapse, BaseModel):
    """
    Returned by the miner with details for one flight option.
    If you set limit>1, the validator can collect multiple of these.
    """
    market: str = Field(
        ...,
        description="Market/country code for pricing"
    )
    # category: Literal['Cheapest', 'Fastest', 'Best'] = Field(
    #     ...,
    #     description="Type of flight option"
    # )
    price: float = Field(
        ...,
        description="Total price amount"
    )
    currency: str = Field(
        ...,
        description="Currency code for the price"
    )
    departure_time: str = Field(
        ...,
        description="Departure timestamp (ISO 8601)"
    )
    arrival_time: str = Field(
        ...,
        description="Arrival timestamp (ISO 8601)"
    )
    departure_city: str = Field(
        ...,
        description="Name of departure city"
    )
    arrival_city: str = Field(
        ...,
        description="Name of arrival city"
    )
    stops: int = Field(
        ...,
        ge=0,
        description="Number of stops (0 = direct)"
    )
    carrier: str = Field(
        ...,
        description="Airline agent name"
    )
    duration_duration: float = Field(
        ...,
        gt=0,
        description="Total trip duration in days"
    )

    def deserialize(self) -> None:
        """
        Hook after deserialization; you could parse the timestamps
        into datetime objects here.
        """
        pass


class FlightSearchBatchRequest(bt.Synapse, BaseModel):
    """
    Batch of flight search queries, each with potentially different market settings.
    """
    queries: List[FlightSearchRequest] = Field(
        ..., description="List of individual FlightSearchRequest objects"
    )

    def deserialize(self) -> None:
        pass


class FlightSearchBatchResponse(bt.Synapse, BaseModel):
    """
    Batch response containing, for each query, a list of FlightSearchResponse objects.
    """
    responses: List[List[FlightSearchResponse]] = Field(
        ..., description="List of response lists corresponding to each query"
    )

    def deserialize(self) -> None:
        pass

class Dummy(bt.Synapse):
    """
    A simple dummy protocol representation which uses bt.Synapse as its base.
    This protocol helps in handling dummy request and response communication between
    the miner and the validator.

    Attributes:
    - dummy_input: An integer value representing the input request sent by the validator.
    - dummy_output: An optional integer value which, when filled, represents the response from the miner.
    """

    # Required request input, filled by sending dendrite caller.
    dummy_input: int

    # Optional request output, filled by receiving axon.
    dummy_output: typing.Optional[int] = None

    def deserialize(self) -> int:
        """
        Deserialize the dummy output. This method retrieves the response from
        the miner in the form of dummy_output, deserializes it and returns it
        as the output of the dendrite.query() call.

        Returns:
        - int: The deserialized response, which in this case is the value of dummy_output.

        Example:
        Assuming a Dummy instance has a dummy_output value of 5:
        >>> dummy_instance = Dummy(dummy_input=4)
        >>> dummy_instance.dummy_output = 5
        >>> dummy_instance.deserialize()
        5
        """
        return self.dummy_output
