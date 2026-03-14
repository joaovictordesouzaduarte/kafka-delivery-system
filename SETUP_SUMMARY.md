# Delivery Tracking System - Setup Summary

## What's Currently Running

Your Kafka-based delivery tracking system is now up and running with the following components:

### Infrastructure Status

| Service | Container Name | Status | Ports | Purpose |
|---------|---------------|--------|-------|---------|
| Kafka Broker 1 | kafka1 | Running | 9092 | Main Kafka broker |
| Kafka Broker 2 | kafka2 | Running | 9093 | Kafka broker (replica) |
| Kafka Broker 3 | kafka3 | Running | 9094 | Kafka broker (replica) |
| Redis | my-redis | Running | 6379 | In-memory state store |
| PostgreSQL | my-postgres | Running | 5432 | Relational database |
| Kafka Connect | kafka-connect | Running | 8083 | Connector framework |
| Prometheus | prometheus | Running | 9090 | Metrics collection |
| Grafana | grafana | Running | 3000 | Monitoring dashboard |

### Access URLs

- **Grafana Dashboard**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Kafka Connect API**: http://localhost:8083
- **Redis**: localhost:6379
- **PostgreSQL**: localhost:5432 (my_user/abcd1234)

---

## Architecture Overview

```
[Driver Location Data (Python Producer)]
            ↓
    [Kafka Topic: driver-locations]
      (3 brokers, replication factor 3)
      (Log compaction enabled)
            ↓
    [Kafka Connect + Redis Sink Connector]
            ↓
    [Redis - Latest Driver Locations]
```

### Key Features

- **3-Node Kafka Cluster**: Using Apache Kafka 4.1.1 with KRaft (no ZooKeeper)
- **Fault Tolerance**: Replication factor of 3 across all brokers
- **Log Compaction**: Configured to keep only the latest location per driver
- **Monitoring**: Prometheus + Grafana for system metrics

---

## Next Steps

### 1. Create the `driver-locations` Topic

```bash
docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --create \
  --bootstrap-server kafka1:9092 \
  --topic driver-locations \
  --partitions 3 \
  --replication-factor 3 \
  --config cleanup.policy=compact \
  --config compression.type=snappy \
  --config min.cleanable.dirty.ratio=0.01 \
  --config segment.ms=10000 \
  --config delete.retention.ms=100
```

### 2. Install Redis Sink Connector

The Kafka Connect container needs a Redis Sink Connector plugin. Install it:

```bash
# Create connectors directory if not exists
mkdir -p connectors

# Download and install Redis Kafka Connector
# Option 1: Using Confluent Hub (recommended)
docker exec kafka-connect confluent-hub install --no-prompt jcustenborder/kafka-connect-redis:latest

# Then restart Kafka Connect
docker restart kafka-connect
```

### 3. Configure Redis Sink Connector

Create a file `redis-sink-connector.json`:

```json
{
  "name": "redis-sink-driver-locations",
  "config": {
    "connector.class": "io.confluent.connect.redis.RedisSinkConnector",
    "tasks.max": "3",
    "topics": "driver-locations",
    "redis.hosts": "my-redis:6379",
    "redis.key.pattern": "driver:${topic}:${key}",
    "key.converter": "org.apache.kafka.connect.storage.StringConverter",
    "value.converter": "org.apache.kafka.connect.json.JsonConverter",
    "value.converter.schemas.enable": "false"
  }
}
```

Deploy the connector:

```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d @redis-sink-connector.json
```

### 4. Implement the Python Producer

Update your `generate_delivery_tracking.py` to send data to Kafka:

```python
from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    key_serializer=lambda k: str(k).encode('utf-8')
)

# Send driver location
driver_data = {
    'driver_id': 'driver_123',
    'latitude': -23.550520,
    'longitude': -46.633308,
    'timestamp': '2026-03-07T10:00:00Z',
    'status': 'available'
}

producer.send(
    topic='driver-locations',
    key=driver_data['driver_id'],  # CRITICAL: Use driver_id as key
    value=driver_data
)

producer.flush()
```

### 5. Test the Complete Pipeline

```bash
# 1. Produce a test message
echo 'driver_123:{"driver_id":"driver_123","latitude":-23.550520,"longitude":-46.633308,"timestamp":"2026-03-07T10:00:00Z","status":"available"}' | \
docker exec -i kafka1 /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka1:9092 \
  --topic driver-locations \
  --property "parse.key=true" \
  --property "key.separator=:"

# 2. Verify in Kafka
docker exec kafka1 /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka1:9092 \
  --topic driver-locations \
  --from-beginning \
  --property print.key=true \
  --max-messages 1

# 3. Check Redis
docker exec -it my-redis redis-cli GET "driver:driver-locations:driver_123"
```

### 6. Configure Grafana Dashboard

1. Open http://localhost:3000 (login: admin/admin)
2. Add Prometheus data source:
   - URL: http://prometheus:9090
3. Import or create a dashboard with metrics:
   - Kafka broker metrics
   - Kafka Connect metrics
   - Topic throughput
   - Consumer lag

---

## Useful Commands

### Check Cluster Status

```bash
# List all topics
docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --list \
  --bootstrap-server kafka1:9092

# Check Kafka Connect status
curl http://localhost:8083/connectors

# Check Redis keys
docker exec my-redis redis-cli KEYS "*"
```

### Monitor Logs

```bash
# Kafka broker logs
docker logs -f kafka1

# Kafka Connect logs
docker logs -f kafka-connect

# All services
docker compose logs -f
```

### Troubleshooting

```bash
# Restart a specific service
docker compose restart kafka1

# Stop all services
docker compose down

# Start all services
docker compose up -d

# Check service health
docker compose ps
```

---

## Project Structure

```
kafka-delivery-system/
├── docker-compose.yml           # All service definitions
├── KAFKA_TOPICS.md             # Topic creation documentation
├── SETUP_SUMMARY.md            # This file
├── generate_delivery_tracking.py  # Driver location generator
├── monitoring/
│   └── prometheus.yml          # Prometheus configuration
├── connectors/                 # Kafka Connect plugins (to be added)
├── kafka-data1/                # Kafka broker 1 data
├── kafka-data2/                # Kafka broker 2 data
├── kafka-data3/                # Kafka broker 3 data
├── redis-data/                 # Redis persistence
├── prometheus-data/            # Prometheus metrics storage
└── grafana-data/               # Grafana dashboards
```

---

## Assignment Requirements Status

| Requirement | Status | Notes |
|-------------|--------|-------|
| 3-node Kafka cluster | ✅ Complete | kafka1, kafka2, kafka3 |
| Fault tolerance | ✅ Complete | Replication factor 3 |
| Log compaction | ⚠️ Pending | Topic needs to be created with config |
| Python Producer | ⚠️ Pending | Needs implementation |
| Kafka Connect to Redis | ⚠️ Pending | Connector needs to be installed & configured |
| Redis as state store | ✅ Complete | Running on port 6379 |
| Prometheus monitoring | ✅ Complete | Running on port 9090 |
| Grafana dashboard | ⚠️ Pending | Running but needs configuration |

---

## Questions?

- **Kafka Topics Documentation**: See `KAFKA_TOPICS.md`
- **Docker Compose Configuration**: See `docker-compose.yml`
- **Monitoring**: Access Prometheus at http://localhost:9090

---

**Your Kafka cluster is ready! Follow the next steps to complete the implementation.**
