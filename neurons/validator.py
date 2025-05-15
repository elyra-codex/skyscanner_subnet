import time
import pandas as pd
import bittensor as bt
import random
import numpy as np
from typing import List
import datetime

from template.base.validator import BaseValidatorNeuron
from template.protocol import (
    FlightSearchRequest,
    FlightSearchBatchRequest,
    FlightSearchBatchResponse,
    FlightSearchResponse
)
from template.utils.uids import get_random_uids
from template.utils.misc import generate_random_date

class Validator(BaseValidatorNeuron):
    """
    Your validator neuron class for batched flight search.
    Implements:
    - Generating multiple flight search queries for different markets
    - Querying miners with a batch request
    - Gathering all responses
    - Rewarding miners
    - Updating and saving scores
    """

    def __init__(self, config=None):
        super().__init__(config=config)
        self.API = False  # For a scenario where we might or might not fill all fields

        bt.logging.info("Loading validator state")
        self.load_state()

        # Load markets list
        markets_file = self.config.get('markets_file', '/root/subnet_test/bittensor-subnet-template/markets.csv')
        try:
            df_markets = pd.read_csv(markets_file)
            self.markets = df_markets['MarketCode'].dropna().tolist()
        except Exception as e:
            bt.logging.error(f"Failed to load markets: {e}")
            self.markets = []

        # Load airports list
        airports_file = self.config.get('airports_file', '/root/subnet_test/bittensor-subnet-template/total_airports.csv')
        try:
            df_airports = pd.read_csv(airports_file)
            # Filter only airports
            self.airports = df_airports[df_airports['entityType']=='AIRPORT'].to_dict('records')
        except Exception as e:
            bt.logging.error(f"Failed to load airports: {e}")
            self.airports = []

        # Determine batch size
        self.batch_size = min(len(self.markets), self.config.get('batch_size', 10))

    async def forward(self, synapse: FlightSearchRequest) -> List[FlightSearchResponse]:
        """
        Receives a single FlightSearchRequest from the caller (BaseValidatorNeuron)
        but actually uses it to generate a batch of queries to send to miners.
        """
        # 1. Generate batch queries for different markets
        queries: List[FlightSearchRequest] = []
        for _ in range(self.batch_size):
            # Pick random market and two distinct airports
            market = random.choice(self.markets)
            origin, destination = random.sample(self.airports, 2)
            random_date = generate_random_date()  # returns a single string date

            # If using a certain "API" scenario, copy some fields from the passed-in synapse
            if self.API:
                q = FlightSearchRequest(
                    date=random_date,
                    origin=str(origin['skyId']),
                    originId=str(origin['entityId']),
                    destination=str(destination['skyId']),
                    destinationId=str(destination['entityId']),
                    cabinClass=synapse.cabinClass,
                    adults=synapse.adults,
                    children=synapse.children,
                    infants=synapse.infants,
                    locale=synapse.locale,
                    currency=synapse.currency,
                    market=market,
                )
            else:
                # Minimal fields, rely on defaults for the rest
                q = FlightSearchRequest(
                    date=random_date,
                    origin=str(origin['skyId']),
                    originId=str(origin['entityId']),
                    destination=str(destination['skyId']),
                    destinationId=str(destination['entityId']),
                    market=market,
                )

            queries.append(q)

        batch = FlightSearchBatchRequest(queries=queries)
        bt.logging.info(f"Dispatching batch of {len(queries)} requests")
        bt.logging.info(f"Sample queries: {queries[:2]} ...")

        # 2. Select miners and send batch
        miner_uids = get_random_uids(self, k=self.batch_size)
        axons = [self.metagraph.axons[uid] for uid in miner_uids]

        # We'll receive a list of FlightSearchBatchResponse (one per axon)
        batch_responses: List[FlightSearchBatchResponse] = await self.dendrite(
            axons=axons,
            synapse=batch,
            deserialize=True
        )
        bt.logging.info(f"Received {len(batch_responses)} batch responses")

        # 3. Collect all individual FlightSearchResponse from each batch
        all_responses: List[FlightSearchResponse] = []
        for batch_resp in batch_responses:
            for resp_list in batch_resp.responses:
                all_responses.extend(resp_list)

        if not all_responses:
            bt.logging.warning("No flight options returned from miners")
            return []

        # 4. Sort by price and reward
        all_responses.sort(key=lambda r: r.price)
        best_price = all_responses[0].price
        for resp in all_responses:
            profit = max(0.0, best_price - resp.price)
            bt.logging.info(f"Rewarding miner {resp.uid} with profit {profit}")
            self.backpropagate(resp, profit)

        self.save_state()

        # 5. Return top results (based on original request limit)
        # e.g. if synapse.limit was 3, return first 3 flights
        return all_responses[:synapse.limit]

    def backpropagate(self, synapse: FlightSearchResponse, profit: float) -> None:
        """
        Optionally do your own reward or scoring logic here.
        For now, calls the parent method that updates self.scores.
        """
        bt.logging.info(f"Backpropagating profit {profit} for synapse: {synapse}")
        super().backpropagate(synapse, profit)

if __name__ == "__main__":
    # Start the validator in a background thread, blocking while we do a simple loop
    with Validator() as validator:
        while True:
            bt.logging.info(f"Validator running... {time.time()}")
            time.sleep(5)
