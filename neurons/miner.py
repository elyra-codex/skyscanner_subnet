import os
import time
import random
import datetime
import requests
import bittensor as bt

from typing import List, Tuple
from template.base.miner import BaseMinerNeuron
from template.protocol import (
    FlightSearchBatchRequest,
    FlightSearchBatchResponse,
    FlightSearchRequest,
    FlightSearchResponse
)

class Miner(BaseMinerNeuron):
    """
    Miner that calls the Skyscanner API for each incoming flight-search request,
    returning real flight data (if available) in a FlightSearchBatchResponse.

    Setup:
    1. Set your Skyscanner API key in an environment variable e.g.
       export SKYSCANNER_API_KEY="your_rapid_api_key"
    2. Or store the key in your config and read it in __init__ below.

    This example uses requests.get() in a blocking manner. For
    a fully async approach, consider using an async library such as aiohttp.
    """

    def __init__(self, config=None):
        super(Miner, self).__init__(config=config)

        # Attempt to read from environment variable or config
        # (Replace or remove fallback if you want to enforce secrets must be set.)
        self.skyscanner_api_key = os.getenv("SKYSCANNER_API_KEY") or getattr(self.config, "skyscanner_api_key", None)

        if not self.skyscanner_api_key:
            bt.logging.warning(
                "No Skyscanner API key found. You must set an env var 'SKYSCANNER_API_KEY' "
                "or define config.skyscanner_api_key. We'll fallback to mock flights."
            )

        # For example, if the user also wants to store x-rapidapi-host:
        self.rapidapi_host = "skyscanner89.p.rapidapi.com"

    async def forward(self, synapse: FlightSearchBatchRequest) -> FlightSearchBatchResponse:
        """
        Main method. We expect a FlightSearchBatchRequest from the validator,
        containing multiple FlightSearchRequest objects in `synapse.queries`.
        We call the Skyscanner API for each request and build the FlightSearchBatchResponse.

        Args:
            synapse: FlightSearchBatchRequest with .queries list

        Returns:
            FlightSearchBatchResponse with an array of responses for each query
        """
        all_responses: List[List[FlightSearchResponse]] = []
        
        # For each query in the batch, call the Skyscanner API or mock if no API key
        for req in synapse.queries:
            flights_for_this_query: List[FlightSearchResponse] = []

            if self.skyscanner_api_key:
                # Build the request
                url = "https://skyscanner89.p.rapidapi.com/flights/one-way/list"
                
                # The user might want to adapt date, cabin, etc. for these parameters
                # For demonstration, we only pass a few mandatory fields
                query_params = {
                    "origin": req.origin,               # e.g. "NYCA"
                    "originId": req.originId,           # e.g. "27537542"
                    "destination": req.destination,     # e.g. "HNL"
                    "destinationId": req.destinationId, # e.g. "95673827"
                    "date": req.date,                 # e.g. "2023-10-01"
                    "market": req.market,               # e.g. "US"
                    # Potentially add "date" or "departDate" if Skyscanner requires it
                }
                headers = {
                    "x-rapidapi-key": self.skyscanner_api_key,
                    "x-rapidapi-host": self.rapidapi_host
                }

                # Perform the GET request
                try:
                    r = requests.get(url, headers=headers, params=query_params, timeout=10)
                    r.raise_for_status()
                    data = r.json()

                    # Now parse `data` from Skyscanner’s response structure
                    # to fill a FlightSearchResponse object. The actual JSON shape
                    # will differ, so adapt to the real structure.

                    # Example pseudo-parse:
                    flight_json_list = data.get("result", {}).get("flights", [])
                    if not flight_json_list:
                        # If no flights found, we might fallback
                        bt.logging.info("No flights returned by Skyscanner for query, returning empty list.")
                    else:
                        # Convert each flight JSON to a FlightSearchResponse
                        # This is a highly simplified example:
                        for flight_item in flight_json_list[: req.limit or 1]:  # only up to limit
                            fsr = FlightSearchResponse(
                                market=req.market,
                                category="Cheapest",
                                price=float(flight_item.get("price", 0.0)),
                                currency=req.currency or "USD",
                                departure_time=str(flight_item.get("departure", {}).get("time", "")),
                                arrival_time=str(flight_item.get("arrival", {}).get("time", "")),
                                departure_city=req.origin,
                                arrival_city=req.destination,
                                stops=flight_item.get("stops", 0),
                                carrier=str(flight_item.get("carrier", "Skyscanner")),
                                duration_days=1.0  # or compute from times
                            )
                            flights_for_this_query.append(fsr)

                except requests.RequestException as e:
                    bt.logging.warning(f"Skyscanner request failed: {e}")
                    # fallback to mock
                    flights_for_this_query.append(self._mock_flight(req))
            else:
                # No valid API key, use a mock flight
                flights_for_this_query.append(self._mock_flight(req))

            # If no flights, can fallback:
            if not flights_for_this_query:
                flights_for_this_query.append(self._mock_flight(req))

            # Collect
            all_responses.append(flights_for_this_query)

        return FlightSearchBatchResponse(responses=all_responses)

    def _mock_flight(self, req: FlightSearchRequest) -> FlightSearchResponse:
        """
        Example fallback if we fail to call real API or it returns no data.
        """
        bt.logging.info("Using mock flight data as a fallback.")
        return FlightSearchResponse(
            market=req.market,
            category="Cheapest",
            price=random.uniform(100, 2000),
            currency=req.currency or "USD",
            departure_time=str(datetime.datetime.now() + datetime.timedelta(hours=5)),
            arrival_time=str(datetime.datetime.now() + datetime.timedelta(hours=10)),
            departure_city=req.origin,
            arrival_city=req.destination,
            stops=1,
            carrier="MockAir",
            duration_days=0.5
        )

    async def blacklist(self, synapse: FlightSearchBatchRequest) -> Tuple[bool, str]:
        """
        Decide whether to block the request. E.g. block unknown hotkeys or non-validators if required.
        """
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            bt.logging.warning("Received a request without a dendrite or hotkey.")
            return True, "Missing dendrite or hotkey"

        uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
        # Disallow unknown hotkeys if config says so
        if (not self.config.blacklist.allow_non_registered
            and synapse.dendrite.hotkey not in self.metagraph.hotkeys):
            return True, "Unrecognized hotkey"

        # If forcing validator permit, ensure caller is a validator
        if self.config.blacklist.force_validator_permit:
            if not self.metagraph.validator_permit[uid]:
                bt.logging.warning(f"Blacklisting request from non-validator hotkey {synapse.dendrite.hotkey}")
                return True, "Non-validator hotkey"

        return False, "Hotkey recognized!"

    async def priority(self, synapse: FlightSearchBatchRequest) -> float:
        """
        Return a numeric priority for this request. 
        """
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            bt.logging.warning("Received a request without a dendrite or hotkey.")
            return 0.0
        caller_uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
        return float(self.metagraph.S[caller_uid])  # stake-based priority


if __name__ == "__main__":
    with Miner() as miner:
        while True:
            bt.logging.info(f"Miner running... {time.time()}")
            time.sleep(5)
