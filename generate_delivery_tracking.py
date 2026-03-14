import random
import time
import json
from dataclasses import dataclass, asdict
from typing import Optional
import threading
import queue
import argparse
import logging
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
@dataclass
class DeliveryPosition:
    timestamp: int
    driver_id: str
    delivery_id: str
    latitude: float
    longitude: float
    status: str

class DeliveryTrackingGenerator:
    _positions_queue: queue.Queue
    _updates_per_sec: int
    _num_drivers: int
    
    # Starting coordinates for simulation (e.g., São Paulo, Brazil area)
    _LAT_START = -23.5505
    _LON_START = -46.6333
    _COORDINATE_DELTA = 0.001 # Small step for movement

    def __init__(self, updates_per_sec: int = 5, num_drivers: int = 20, max_queue_size: int = 1000):
        self._positions_queue = queue.Queue(maxsize=max_queue_size)
        self._updates_per_sec = updates_per_sec
        self._num_drivers = num_drivers
        
        # Initialize drivers with random positions and statuses
        self._drivers_state = {}
        for i in range(self._num_drivers):
            driver_id = f"driver_{100 + i}"
            self._drivers_state[driver_id] = {
                "delivery_id": f"del_{1000 + i}",
                "lat": self._LAT_START + random.uniform(-0.05, 0.05),
                "lon": self._LON_START + random.uniform(-0.05, 0.05),
                "status": random.choice(["PICKING_UP", "DELIVERING"])
            }
        
        # Create Kafka producer ONCE - reuse for all messages
        logging.info("Connecting to Kafka brokers...")
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=['localhost:9092', 'localhost:9093', 'localhost:9094'],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: str(k).encode('utf-8'),
                acks='all',  # Wait for all replicas to acknowledge
                retries=3,   # Retry failed sends
                max_in_flight_requests_per_connection=5,
                compression_type='snappy'  # Compress messages for better throughput
            )
            logging.info("Successfully connected to Kafka")
        except KafkaError as e:
            logging.error(f"Failed to connect to Kafka: {e}")
            raise

    def _update_driver_position(self, driver_id: str) -> DeliveryPosition:
        state = self._drivers_state[driver_id]
        
        # Simulate movement: add a small random delta to lat/lon
        state["lat"] += random.uniform(-self._COORDINATE_DELTA, self._COORDINATE_DELTA)
        state["lon"] += random.uniform(-self._COORDINATE_DELTA, self._COORDINATE_DELTA)
        
        # Occasionally change status or delivery_id to simulate new deliveries
        if random.random() < 0.01:
            if state["status"] == "DELIVERING":
                state["status"] = "PICKING_UP"
                state["delivery_id"] = f"del_{random.randint(2000, 9999)}"
            else:
                state["status"] = "DELIVERING"

        return DeliveryPosition(
            timestamp=int(time.time()),
            driver_id=driver_id,
            delivery_id=state["delivery_id"],
            latitude=round(state["lat"], 6),
            longitude=round(state["lon"], 6),
            status=state["status"]
        )

    def _tracking_thread(self) -> None:
        delay = 1 / self._updates_per_sec
        driver_ids = list(self._drivers_state.keys())
        
        while True:
            # Pick a random driver to update
            driver_id = random.choice(driver_ids)
            position_update = self._update_driver_position(driver_id)
            self._positions_queue.put(position_update)
            time.sleep(delay)

    def generate_tracking_data(self):
        # Start the background thread for updates
        threading.Thread(target=self._tracking_thread, daemon=True).start()

        while True:
            position = self._positions_queue.get()
            yield position
            self._positions_queue.task_done()

    def send_to_kafka(self, driver_id: str, latitude: float, longitude: float, timestamp: int, status: str):
        """Send driver location to Kafka using the reusable producer."""
        driver_data = {
            'driver_id': driver_id,
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': timestamp,
            'status': status
        }

        try:
            # Use the existing producer - no need to create a new one!
            future = self.producer.send(
                topic='driver-locations',
                key=driver_id,
                value=driver_data
            )
            # Optional: get result to ensure message was sent (adds latency)
            # record_metadata = future.get(timeout=10)
        except KafkaError as e:
            logging.error(f"Failed to send message for {driver_id}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error sending message: {e}")
    
    def close(self):
        """Cleanup resources - flush and close the Kafka producer."""
        if hasattr(self, 'producer') and self.producer:
            logging.info("Flushing remaining messages and closing producer...")
            try:
                self.producer.flush(timeout=10)
                self.producer.close(timeout=10)
                logging.info("Producer closed successfully")
            except Exception as e:
                logging.error(f"Error closing producer: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Simulate a delivery tracking stream.')
    parser.add_argument('--drivers', type=int, default=10, help='Number of drivers to simulate (default: 10)')
    parser.add_argument('--updates', type=float, default=5.0, help='Updates per second (default: 5.0)')
    parser.add_argument('--verbose', action='store_true', help='Print each message to console')
    
    args = parser.parse_args()

    tracking_gen = None
    count = 0
    
    try:
        # Simulate a delivery tracking stream
        tracking_gen = DeliveryTrackingGenerator(updates_per_sec=args.updates, num_drivers=args.drivers)
        logging.info(f"Starting Delivery Tracking Simulation for {args.drivers} drivers at {args.updates} updates/sec...")
        logging.info("Press Ctrl+C to stop")
        
        for pos in tracking_gen.generate_tracking_data():
            count += 1
            pos_dict = asdict(pos)
            tracking_gen.send_to_kafka(
                pos_dict['driver_id'], 
                pos_dict['latitude'], 
                pos_dict['longitude'], 
                pos_dict['timestamp'], 
                pos_dict['status']
            )
            
            # Print message if verbose mode
            if args.verbose:
                print(json.dumps(pos_dict))
            
            # Log progress every 100 messages
            if count % 100 == 0:
                logging.info(f"Sent {count} messages...")

    except KeyboardInterrupt:
        logging.info(f"\nSimulation stopped by user. {count} tracking updates generated.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        # Always cleanup the producer
        if tracking_gen:
            tracking_gen.close()
        logging.info(f"Total messages sent: {count}")
